"""The OpenAI boundary. The only module in this package that touches a network.

Three policies live here and nowhere else:

* **Spend control.** The SDK's own retry is switched off (`max_retries=0`).
  Leaving it on would double a paid request invisibly and would sit outside our
  deadline accounting, so the two mechanisms would fight.
* **Retry discipline.** At most one retry, and only after an explicit HTTP
  response with a retryable status. A timeout or a dropped connection is never
  retried: the request may well have completed and been billed server-side, and
  a duplicate image is worse than a clear error.
* **Error mapping.** Every provider exception becomes one of the closed codes
  in `errors`. Raw bodies never escape.

`sleep`, `monotonic`, and `jitter` are injected so retry and deadline behaviour
is testable instantly and deterministically.
"""

from __future__ import annotations

import inspect
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import anyio
import openai

from . import constants, errors
from .credentials import Secret
from .models import EditRequest, GenerateRequest

log = logging.getLogger("gpt_image_2.api")

__all__ = ["ApiResult", "Budget", "build_client", "call_generate", "call_edit"]


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class Budget:
    """A monotonic deadline for one whole operation.

    Created at tool entry, so validation, file inspection, the API attempts, and
    publication all draw on the same 180 seconds. `monotonic` is injected because
    a wall clock can jump and because tests must not actually wait.
    """

    def __init__(
        self,
        total_s: float = constants.OPERATION_DEADLINE_S,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.total_s = total_s
        self._monotonic = monotonic
        self._started = monotonic()

    @property
    def elapsed_s(self) -> float:
        return self._monotonic() - self._started

    @property
    def remaining_s(self) -> float:
        return self.total_s - self.elapsed_s


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApiResult:
    payloads: tuple[str, ...]
    request_id: str | None
    usage: dict[str, Any] | None
    revised_prompt: str | None
    attempts: int


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def build_client(secret: Secret) -> openai.AsyncOpenAI:
    """Construct the SDK client.

    `max_retries=0` is not a tuning choice — it is the spend-control invariant
    from ADR 0015. `timeout` bounds a single attempt; `Budget` bounds the whole
    operation.
    """
    return openai.AsyncOpenAI(
        api_key=secret.reveal(),
        max_retries=0,
        timeout=constants.API_ATTEMPT_TIMEOUT_S,
    )


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------


def build_generate_kwargs(request: GenerateRequest) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": constants.MODEL,
        "prompt": request.prompt,
        "n": request.n,
        "size": request.size,
        "quality": request.quality,
        "output_format": request.output_format,
        "background": request.background,
        "moderation": request.moderation,
    }
    if request.output_compression is not None:
        kwargs["output_compression"] = request.output_compression
    return kwargs


def build_edit_kwargs(request: EditRequest) -> dict[str, Any]:
    """Build the edit body.

    `input_fidelity` is absent by construction: the documentation says to omit
    it for gpt-image-2, and the safest way to honour that is never to have a
    code path that sets it. Likewise `moderation`, which the edit endpoint does
    not accept.
    """
    kwargs: dict[str, Any] = {
        "model": constants.MODEL,
        "prompt": request.prompt,
        "image": [_file_tuple(ref) for ref in request.references],
        "n": request.n,
        "size": request.size,
        "quality": request.quality,
        "output_format": request.output_format,
        "background": request.background,
    }
    if request.mask is not None:
        kwargs["mask"] = _file_tuple(request.mask)
    if request.output_compression is not None:
        kwargs["output_compression"] = request.output_compression
    return kwargs


def _file_tuple(local_image: Any) -> tuple[str, bytes, str]:
    """Read an already-validated reference for upload.

    The bytes are read now rather than retained from validation so that sixteen
    50 MB references cannot pin 800 MB of memory for the whole call. The size is
    re-checked because the file could have been replaced between validation and
    send, and a swapped file must not slip past the limit.
    """
    path = local_image.path
    try:
        size_bytes = path.stat().st_size
        if size_bytes >= constants.MAX_EDIT_FILE_BYTES:
            raise errors.invalid_input_file(
                "File grew past this tool's local size limit between validation "
                "and upload.",
                path=str(path),
            )
        data = path.read_bytes()
    except errors.ImageToolError:
        raise
    except OSError:
        raise errors.invalid_input_file(
            "File became unreadable between validation and upload.", path=str(path)
        ) from None

    return (path.name, data, constants.MIME_BY_FORMAT[local_image.format])


# ---------------------------------------------------------------------------
# Response reading
# ---------------------------------------------------------------------------


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _header(headers: Any, name: str) -> str | None:
    try:
        value = headers.get(name)
    except AttributeError:  # pragma: no cover - defensive
        return None
    return str(value) if value else None


def _read_usage(parsed: Any) -> dict[str, Any] | None:
    usage = getattr(parsed, "usage", None)
    if usage is None:
        return None
    fields = ("input_tokens", "output_tokens", "total_tokens")
    collected = {name: getattr(usage, name, None) for name in fields}
    collected = {k: v for k, v in collected.items() if isinstance(v, int)}
    return collected or None


def _read_payloads(parsed: Any) -> tuple[tuple[str, ...], str | None]:
    data = getattr(parsed, "data", None) or []
    payloads: list[str] = []
    revised: str | None = None
    for entry in data:
        b64 = getattr(entry, "b64_json", None)
        if b64:
            payloads.append(b64)
        if revised is None:
            candidate = getattr(entry, "revised_prompt", None)
            if candidate:
                # Provider-controlled text goes to the caller, so it gets the
                # same treatment as every other provider string: scrubbed and
                # length-bounded. Relaying it verbatim would let the service
                # echo an unbounded blob — or a token — into the MCP channel.
                revised = errors.redact(str(candidate))
    if not payloads:
        raise errors.output_error("The API returned no image data.")
    return tuple(payloads), revised


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

_MODERATION_MARKERS = (
    "moderation",
    "content_policy",
    "content policy",
    "safety_violation",
    "safety system",
    "rejected as a result of our safety",
)


def _response_of(exc: BaseException) -> Any:
    return getattr(exc, "response", None)


def _request_id_of(exc: BaseException) -> str | None:
    response = _response_of(exc)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    return _header(headers, "x-request-id")


def _provider_message(exc: BaseException) -> str:
    """A coarse, redacted, length-bounded provider explanation — never the body.

    Deliberately does NOT use `exc.message`. The SDK composes that as
    `"Error code: {status} - {decoded body}"`, so relaying it would push the
    whole response body through the MCP channel — exactly what constitution
    principle 1 forbids, and merely truncating it to 400 characters would not
    make it not-a-body.

    Instead read the one structured field that is meant to be human-facing:
    `body["message"]` (or `body["error"]["message"]`, the older nesting). If the
    provider gave us no such field, we say so rather than inventing detail.
    """
    body = getattr(exc, "body", None)
    candidate: object = None
    if isinstance(body, dict):
        candidate = body.get("message")
        if candidate is None:
            nested = body.get("error")
            if isinstance(nested, dict):
                candidate = nested.get("message")

    if not isinstance(candidate, str) or not candidate.strip():
        return ""
    return errors.redact(candidate)


def _looks_like_moderation(exc: BaseException) -> bool:
    code = getattr(exc, "code", None)
    haystack = " ".join(
        part.lower()
        for part in (str(code or ""), _provider_message(exc))
        if part
    )
    return any(marker in haystack for marker in _MODERATION_MARKERS)


def map_exception(exc: BaseException, *, secret: str | None = None) -> errors.ImageToolError:
    """Total, closed mapping from an SDK exception to one of our codes."""
    request_id = _request_id_of(exc)
    message = _provider_message(exc)
    status = getattr(exc, "status_code", None)

    if isinstance(exc, openai.APITimeoutError):
        return errors.ImageToolError(
            errors.API_TIMEOUT,
            "The image request timed out. It was not retried, because a timed-out "
            "request may still have completed and been billed.",
            request_id=request_id,
            secret=secret,
        )

    if isinstance(exc, openai.APIConnectionError):
        return errors.ImageToolError(
            errors.CONNECTION_ERROR,
            "Could not reach the OpenAI API. Check network access and try again.",
            request_id=request_id,
            secret=secret,
        )

    if isinstance(exc, openai.AuthenticationError):
        return errors.ImageToolError(
            errors.AUTHENTICATION_ERROR,
            f"OpenAI rejected the credential. Check {constants.CREDENTIAL_ENV_VAR}.",
            request_id=request_id,
            status_code=status,
            secret=secret,
        )

    if isinstance(exc, openai.PermissionDeniedError):
        return errors.ImageToolError(
            errors.ACCESS_DENIED,
            "OpenAI denied access to image generation. This usually means the "
            "organization is not verified for this model, or billing is not "
            f"active. Provider said: {message or 'no detail supplied'}",
            request_id=request_id,
            status_code=status,
            secret=secret,
        )

    if isinstance(exc, openai.RateLimitError):
        return errors.ImageToolError(
            errors.RATE_LIMITED,
            "OpenAI rate-limited the request and the retry budget is exhausted.",
            request_id=request_id,
            status_code=status,
            secret=secret,
        )

    if isinstance(exc, openai.BadRequestError):
        if _looks_like_moderation(exc):
            return errors.ImageToolError(
                errors.MODERATION_BLOCKED,
                "The request was blocked by OpenAI's content moderation and was "
                "not retried. Revise the prompt or the reference images to "
                f"comply with the usage policies. Provider said: "
                f"{message or 'no detail supplied'}",
                request_id=request_id,
                status_code=status,
                secret=secret,
            )
        return errors.ImageToolError(
            errors.USER_ERROR,
            f"OpenAI rejected the request as invalid and it was not retried. "
            f"Provider said: {message or 'no detail supplied'}",
            request_id=request_id,
            status_code=status,
            secret=secret,
        )

    if isinstance(exc, openai.APIStatusError):
        if isinstance(status, int) and 400 <= status < 500:
            return errors.ImageToolError(
                errors.USER_ERROR,
                f"OpenAI rejected the request (HTTP {status}) and it was not "
                f"retried. Provider said: {message or 'no detail supplied'}",
                request_id=request_id,
                status_code=status,
                secret=secret,
            )
        return errors.ImageToolError(
            errors.SERVICE_ERROR,
            f"OpenAI returned a server error (HTTP {status}). "
            f"Provider said: {message or 'no detail supplied'}",
            request_id=request_id,
            status_code=status,
            secret=secret,
        )

    if isinstance(exc, errors.ImageToolError):
        return exc

    return errors.internal_error(exc)


def _is_retryable_response_error(exc: BaseException) -> bool:
    """Only an explicit HTTP response with a selected status may be retried."""
    if not isinstance(exc, openai.APIStatusError):
        return False
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return False  # pragma: no cover - not APIStatusError subclasses anyway
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and status in constants.RETRYABLE_STATUS


def _retry_after_s(exc: BaseException) -> float | None:
    response = _response_of(exc)
    headers = getattr(response, "headers", None)
    raw = _header(headers, "retry-after") if headers is not None else None
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        # The HTTP-date form is legal but useless here; ignore it and use the
        # default backoff rather than parsing a date we cannot trust.
        return None
    if seconds < 0:
        return None
    return min(seconds, constants.MAX_RETRY_AFTER_S)


# ---------------------------------------------------------------------------
# The call
# ---------------------------------------------------------------------------


async def _call_with_retry(
    operation: str,
    kwargs_factory: Callable[[], dict[str, Any]],
    *,
    secret: Secret,
    budget: Budget,
    client_factory: Callable[[Secret], Any] | None = None,
    sleep: Callable[[float], Awaitable[None]] = anyio.sleep,
    jitter: Callable[[], float] = random.random,
) -> ApiResult:
    # Resolved here, not as a keyword default, so monkeypatching
    # `api.build_client` actually takes effect.
    factory = build_client if client_factory is None else client_factory
    client = factory(secret)
    revealed = secret.reveal()
    last_exc: BaseException | None = None

    for attempt in range(1, constants.MAX_API_ATTEMPTS + 1):
        remaining = budget.remaining_s
        if remaining <= 0:
            raise errors.ImageToolError(
                errors.DEADLINE_EXCEEDED,
                f"The operation exceeded its {budget.total_s:g}-second budget "
                f"before attempt {attempt} could start.",
                request_id=_request_id_of(last_exc) if last_exc else None,
            )

        attempt_timeout = min(constants.API_ATTEMPT_TIMEOUT_S, remaining)
        kwargs = dict(kwargs_factory())
        kwargs["timeout"] = attempt_timeout

        try:
            raw = await _maybe_await(
                getattr(client.images.with_raw_response, operation)(**kwargs)
            )
            parsed = await _maybe_await(raw.parse())
            payloads, revised = _read_payloads(parsed)
            return ApiResult(
                payloads=payloads,
                request_id=_header(getattr(raw, "headers", None), "x-request-id"),
                usage=_read_usage(parsed),
                revised_prompt=revised,
                attempts=attempt,
            )
        except errors.ImageToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - mapped exhaustively below
            last_exc = exc
            mapped = map_exception(exc, secret=revealed)

            can_retry = (
                attempt < constants.MAX_API_ATTEMPTS
                and _is_retryable_response_error(exc)
            )
            if not can_retry:
                log.warning(
                    "gpt_image_2 %s failed code=%s attempts=%d request_id=%s",
                    operation,
                    mapped.code,
                    attempt,
                    mapped.request_id or "-",
                )
                raise mapped from None

            delay = _retry_after_s(exc)
            if delay is None:
                delay = constants.RETRY_BASE_DELAY_S + jitter() * constants.RETRY_MAX_JITTER_S

            if budget.remaining_s - delay < constants.RETRY_MIN_REMAINING_S:
                log.warning(
                    "gpt_image_2 %s not retried: insufficient budget code=%s request_id=%s",
                    operation,
                    mapped.code,
                    mapped.request_id or "-",
                )
                raise mapped from None

            log.warning(
                "gpt_image_2 %s retrying once after code=%s status=%s request_id=%s",
                operation,
                mapped.code,
                getattr(exc, "status_code", None),
                mapped.request_id or "-",
            )
            await sleep(delay)

    # Unreachable: the loop either returns or raises. Kept so a future change to
    # MAX_API_ATTEMPTS cannot silently fall through to None.
    if last_exc is not None:  # pragma: no cover
        raise map_exception(last_exc, secret=revealed)
    raise errors.ImageToolError(  # pragma: no cover
        errors.INTERNAL_ERROR, "The retry loop ended without a result."
    )


async def call_generate(
    request: GenerateRequest,
    *,
    secret: Secret,
    budget: Budget,
    client_factory: Callable[[Secret], Any] | None = None,
    sleep: Callable[[float], Awaitable[None]] = anyio.sleep,
    jitter: Callable[[], float] = random.random,
) -> ApiResult:
    return await _call_with_retry(
        "generate",
        lambda: build_generate_kwargs(request),
        secret=secret,
        budget=budget,
        client_factory=client_factory,
        sleep=sleep,
        jitter=jitter,
    )


async def call_edit(
    request: EditRequest,
    *,
    secret: Secret,
    budget: Budget,
    client_factory: Callable[[Secret], Any] | None = None,
    sleep: Callable[[float], Awaitable[None]] = anyio.sleep,
    jitter: Callable[[], float] = random.random,
) -> ApiResult:
    return await _call_with_retry(
        "edit",
        lambda: build_edit_kwargs(request),
        secret=secret,
        budget=budget,
        client_factory=client_factory,
        sleep=sleep,
        jitter=jitter,
    )
