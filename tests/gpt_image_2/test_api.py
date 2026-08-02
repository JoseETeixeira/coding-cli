"""The OpenAI boundary: request shape, retry discipline, and error mapping.

Covers IMG-AC-003 (the approved request shape reaches the SDK, `model` is fixed
to gpt-image-2, and nothing this tool forbids is ever sent) and IMG-AC-008
(user and moderation errors are attempted exactly once, transient errors follow
the bounded retry/deadline policy, and safe request IDs survive the failure).

Nothing here sleeps, reads a wall clock, or touches a socket. `FakeClock` and
`RecordingSleep` replace the two timing seams, `FakeClientFactory` replaces the
client, and the autouse guard in `conftest` turns any attempt to build a real
`openai.AsyncOpenAI` into a loud failure.

Async entry points are driven with `anyio.run` from a plain sync test: this repo
does not configure `pytest-asyncio`, so `@pytest.mark.asyncio` would silently
skip the body.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import anyio
import openai
import pytest
from conftest import (
    CANARY_SECRET,
    FakeClientFactory,
    FakeClock,
    FakeOpenAI,
    FakeParsedResponse,
    FakeRawResponse,
    FakeUsage,
    RecordingSleep,
    b64_image,
    connection_error,
    status_error,
    timeout_error,
    write_image,
)

from gpt_image_2 import api, constants, errors
from gpt_image_2.credentials import Secret
from gpt_image_2.models import EditRequest, GenerateRequest, validate_edit, validate_generate

#: Every argument this subsystem must never put on the wire. `api_key` is
#: IMG-REQ-005; `headers`/`endpoint`/`url`/`file_id` are the IMG-REQ-002
#: escapes; `overwrite` is IMG-REQ-006; the rest are streaming/legacy DALL-E
#: parameters that gpt-image-2 either rejects or that this release does not use.
FORBIDDEN_KEYS: tuple[str, ...] = (
    "api_key",
    "headers",
    "endpoint",
    "url",
    "file_id",
    "overwrite",
    "stream",
    "partial_images",
    "response_format",
    "style",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Drive one coroutine function to completion on a fresh event loop."""
    return anyio.run(partial(func, *args, **kwargs))


def _generate_request(tmp_path: Path, **overrides: Any) -> GenerateRequest:
    params: dict[str, Any] = {
        "prompt": "a calm harbour at dawn",
        "output_dir": str(tmp_path / "out"),
    }
    params.update(overrides)
    return validate_generate(**params)


def _edit_request(
    tmp_path: Path,
    references: list[Path],
    mask: Path | None = None,
    **overrides: Any,
) -> EditRequest:
    params: dict[str, Any] = {
        "prompt": "repaint the sky",
        "image_paths": [str(p) for p in references],
        "mask_path": str(mask) if mask is not None else None,
        "output_dir": str(tmp_path / "out"),
    }
    params.update(overrides)
    return validate_edit(**params)


def _ok(
    payloads: list[str | None] | None = None,
    *,
    request_id: str = "req_fake_001",
    usage: FakeUsage | None = None,
    revised_prompt: str | None = None,
) -> FakeRawResponse:
    return FakeRawResponse(
        FakeParsedResponse(
            [b64_image()] if payloads is None else payloads,
            usage=usage,
            revised_prompt=revised_prompt,
        ),
        headers={"x-request-id": request_id},
    )


def _factory(*script: Any) -> FakeClientFactory:
    return FakeClientFactory(client=FakeOpenAI(script=list(script)))


@pytest.fixture
def second_png(tmp_path: Path) -> Path:
    """A second reference, same geometry and format as `reference_png`."""
    return write_image(tmp_path, "second.png", fmt="png", mode="RGBA", alpha=255)


# ---------------------------------------------------------------------------
# IMG-AC-003 — generate request shape
# ---------------------------------------------------------------------------


def test_generate_kwargs_are_exactly_the_approved_body(tmp_path: Path) -> None:
    request = _generate_request(
        tmp_path,
        prompt="a calm harbour at dawn",
        size="1024x1536",
        quality="low",
        output_format="jpeg",
        n=3,
        output_compression=77,
        background="opaque",
        moderation="low",
    )

    assert api.build_generate_kwargs(request) == {
        "model": "gpt-image-2",
        "prompt": "a calm harbour at dawn",
        "n": 3,
        "size": "1024x1536",
        "quality": "low",
        "output_format": "jpeg",
        "background": "opaque",
        "moderation": "low",
        "output_compression": 77,
    }


def test_generate_model_is_the_fixed_constant(tmp_path: Path) -> None:
    kwargs = api.build_generate_kwargs(_generate_request(tmp_path))
    assert kwargs["model"] == "gpt-image-2"
    assert kwargs["model"] == constants.MODEL


@pytest.mark.parametrize(
    ("output_format", "output_compression", "expected"),
    [
        ("png", None, None),
        ("jpeg", None, None),
        ("jpeg", 0, 0),
        ("jpeg", 100, 100),
        ("webp", 55, 55),
    ],
    ids=["png-omitted", "jpeg-omitted", "jpeg-zero", "jpeg-max", "webp-mid"],
)
def test_generate_output_compression_is_sent_only_when_set(
    tmp_path: Path,
    output_format: str,
    output_compression: int | None,
    expected: int | None,
) -> None:
    kwargs = api.build_generate_kwargs(
        _generate_request(
            tmp_path, output_format=output_format, output_compression=output_compression
        )
    )
    if expected is None:
        assert "output_compression" not in kwargs
    else:
        assert kwargs["output_compression"] == expected


@pytest.mark.parametrize("forbidden", FORBIDDEN_KEYS)
def test_generate_kwargs_never_carry_a_forbidden_key(
    tmp_path: Path, forbidden: str
) -> None:
    request = _generate_request(
        tmp_path, output_format="webp", output_compression=42, background="opaque"
    )
    assert forbidden not in api.build_generate_kwargs(request)


# ---------------------------------------------------------------------------
# IMG-AC-003 — edit request shape
# ---------------------------------------------------------------------------


def test_edit_image_list_preserves_reference_order(
    tmp_path: Path, reference_png: Path, second_png: Path
) -> None:
    request = _edit_request(tmp_path, [second_png, reference_png])

    kwargs = api.build_edit_kwargs(request)
    uploaded = kwargs["image"]

    assert isinstance(uploaded, list)
    assert [entry[0] for entry in uploaded] == ["second.png", "reference.png"]
    assert [entry[0] for entry in uploaded] == [
        ref.path.name for ref in request.references
    ]
    for entry, ref in zip(uploaded, request.references):
        assert isinstance(entry, tuple) and len(entry) == 3
        assert entry[1] == ref.path.read_bytes()
        assert entry[2] == "image/png"


@pytest.mark.parametrize("with_mask", [True, False], ids=["mask", "no-mask"])
def test_edit_mask_is_sent_only_when_supplied(
    tmp_path: Path, reference_png: Path, mask_png: Path, with_mask: bool
) -> None:
    request = _edit_request(
        tmp_path, [reference_png], mask=mask_png if with_mask else None
    )

    kwargs = api.build_edit_kwargs(request)

    if with_mask:
        assert kwargs["mask"] == (
            "mask.png",
            mask_png.read_bytes(),
            "image/png",
        )
    else:
        assert "mask" not in kwargs


def test_edit_kwargs_are_exactly_the_approved_body(
    tmp_path: Path, reference_png: Path, second_png: Path, mask_png: Path
) -> None:
    request = _edit_request(
        tmp_path,
        [reference_png, second_png],
        mask=mask_png,
        size="1024x1024",
        quality="medium",
        output_format="png",
        n=2,
        background="opaque",
    )

    kwargs = api.build_edit_kwargs(request)

    assert set(kwargs) == {
        "model",
        "prompt",
        "image",
        "n",
        "size",
        "quality",
        "output_format",
        "background",
        "mask",
    }
    assert kwargs["model"] == constants.MODEL == "gpt-image-2"
    assert kwargs["n"] == 2
    assert kwargs["size"] == "1024x1024"
    assert kwargs["quality"] == "medium"
    assert kwargs["output_format"] == "png"
    assert kwargs["background"] == "opaque"


def test_edit_never_sends_moderation(
    tmp_path: Path, reference_png: Path, mask_png: Path
) -> None:
    """`POST /v1/images/edits` has no `moderation` parameter."""
    request = _edit_request(tmp_path, [reference_png], mask=mask_png)

    assert "moderation" not in api.build_edit_kwargs(request)
    assert not hasattr(request, "moderation")


@pytest.mark.parametrize("omitted", constants.OMITTED_EDIT_PARAMS)
def test_edit_never_sends_an_omitted_edit_param(
    tmp_path: Path, reference_png: Path, omitted: str
) -> None:
    """`input_fidelity` must be absent by construction for gpt-image-2."""
    assert omitted == "input_fidelity"
    assert omitted not in api.build_edit_kwargs(_edit_request(tmp_path, [reference_png]))


@pytest.mark.parametrize("forbidden", FORBIDDEN_KEYS)
def test_edit_kwargs_never_carry_a_forbidden_key(
    tmp_path: Path, reference_png: Path, mask_png: Path, forbidden: str
) -> None:
    request = _edit_request(tmp_path, [reference_png], mask=mask_png)
    assert forbidden not in api.build_edit_kwargs(request)


def test_edit_rereads_a_reference_that_grew_past_the_local_limit(
    tmp_path: Path, reference_png: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The size re-check happens at send time, not only at validation time."""
    request = _edit_request(tmp_path, [reference_png])

    real_stat = Path.stat

    def fake_stat(self: Path, *args: Any, **kwargs: Any):
        result = real_stat(self, *args, **kwargs)
        if self.name == "reference.png":
            class _Grown:
                st_size = constants.MAX_EDIT_FILE_BYTES + 1
            return _Grown()
        return result

    monkeypatch.setattr(Path, "stat", fake_stat)

    with pytest.raises(errors.ImageToolError) as raised:
        api.build_edit_kwargs(request)
    assert raised.value.code == errors.INVALID_INPUT_FILE


# ---------------------------------------------------------------------------
# IMG-AC-003 — a whole call through the boundary
# ---------------------------------------------------------------------------


def test_call_generate_sends_the_body_and_returns_the_result(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    payload = b64_image()
    factory = _factory(
        _ok(
            [payload],
            request_id="req_gen_42",
            usage=FakeUsage(),
            revised_prompt="a calm harbour at dawn, cinematic",
        )
    )
    request = _generate_request(tmp_path, quality="high", output_format="png", n=1)

    result = _run(
        api.call_generate,
        request,
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    assert result.payloads == (payload,)
    assert result.request_id == "req_gen_42"
    assert result.usage == {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33}
    assert result.revised_prompt == "a calm harbour at dawn, cinematic"
    assert result.attempts == 1
    assert sleeper.delays == []

    assert factory.client.call_count == 1
    call = factory.client.calls[0]
    assert call.operation == "generate"
    assert call.kwargs["model"] == "gpt-image-2"
    assert call.kwargs["prompt"] == "a calm harbour at dawn"
    assert call.kwargs["timeout"] == constants.API_ATTEMPT_TIMEOUT_S
    for forbidden in FORBIDDEN_KEYS:
        assert forbidden not in call.kwargs
    assert factory.secrets_seen == [secret]


def test_call_edit_sends_the_body_and_returns_the_result(
    tmp_path: Path,
    reference_png: Path,
    second_png: Path,
    mask_png: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    first, second = b64_image(), b64_image(size=(32, 32))
    factory = _factory(_ok([first, second], request_id="req_edit_7", usage=FakeUsage()))
    request = _edit_request(
        tmp_path, [reference_png, second_png], mask=mask_png, n=2
    )

    result = _run(
        api.call_edit,
        request,
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    assert result.payloads == (first, second)
    assert result.request_id == "req_edit_7"
    assert result.revised_prompt is None
    assert result.attempts == 1

    call = factory.client.calls[0]
    assert call.operation == "edit"
    assert call.kwargs["model"] == "gpt-image-2"
    assert [entry[0] for entry in call.kwargs["image"]] == [
        "reference.png",
        "second.png",
    ]
    assert call.kwargs["mask"][0] == "mask.png"
    assert "moderation" not in call.kwargs
    for omitted in constants.OMITTED_EDIT_PARAMS:
        assert omitted not in call.kwargs
    for forbidden in FORBIDDEN_KEYS:
        assert forbidden not in call.kwargs


def test_missing_provider_usage_is_not_invented(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    factory = _factory(_ok())

    result = _run(
        api.call_generate,
        _generate_request(tmp_path),
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    assert result.usage is None
    assert result.revised_prompt is None


# ---------------------------------------------------------------------------
# build_client
# ---------------------------------------------------------------------------


def test_build_client_disables_sdk_retries_and_bounds_one_attempt(
    secret: Secret, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`max_retries=0` is the spend-control invariant, not a tuning knob."""
    seen: dict[str, Any] = {}

    class _RecordingClient:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

    monkeypatch.setattr(openai, "AsyncOpenAI", _RecordingClient)

    client = api.build_client(secret)

    assert isinstance(client, _RecordingClient)
    assert seen["max_retries"] == 0
    assert seen["timeout"] == constants.API_ATTEMPT_TIMEOUT_S
    assert seen["timeout"] == 150.0
    assert seen["api_key"] == secret.reveal() == CANARY_SECRET
    assert set(seen) == {"api_key", "max_retries", "timeout"}


def test_build_client_is_stopped_by_the_offline_guard(secret: Secret) -> None:
    """The suite must be unable to spend money even by accident."""
    with pytest.raises(AssertionError, match="offline"):
        api.build_client(secret)


# ---------------------------------------------------------------------------
# IMG-AC-008 — retry discipline
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", constants.RETRYABLE_STATUS)
def test_retryable_status_is_retried_exactly_once_then_succeeds(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
    status: int,
) -> None:
    factory = _factory(status_error(status), _ok(request_id="req_after_retry"))

    result = _run(
        api.call_generate,
        _generate_request(tmp_path),
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    assert factory.client.call_count == 2
    assert result.attempts == 2
    assert result.request_id == "req_after_retry"
    assert sleeper.delays == [constants.RETRY_BASE_DELAY_S]


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (429, errors.RATE_LIMITED),
        (500, errors.SERVICE_ERROR),
        (503, errors.SERVICE_ERROR),
    ],
    ids=["rate-limited", "internal", "unavailable"],
)
def test_retry_budget_stops_at_max_attempts(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
    status: int,
    expected_code: str,
) -> None:
    factory = _factory(
        status_error(status, headers={"x-request-id": "req_persistent"}),
        status_error(status, headers={"x-request-id": "req_persistent"}),
        _ok(request_id="never-reached"),
    )

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == expected_code
    assert factory.client.call_count == constants.MAX_API_ATTEMPTS == 2
    assert raised.value.request_id == "req_persistent"
    assert raised.value.status_code == status
    assert len(sleeper.delays) == 1
    assert CANARY_SECRET not in str(raised.value)


def test_timeout_is_never_retried(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    """A timed-out request may have completed and been billed. One attempt."""
    factory = _factory(timeout_error(), _ok())

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == errors.API_TIMEOUT
    assert factory.client.call_count == 1
    assert sleeper.delays == []


def test_connection_error_is_never_retried(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    factory = _factory(connection_error(), _ok())

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == errors.CONNECTION_ERROR
    assert factory.client.call_count == 1
    assert sleeper.delays == []


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (400, errors.USER_ERROR),
        (401, errors.AUTHENTICATION_ERROR),
        (403, errors.ACCESS_DENIED),
        (404, errors.USER_ERROR),
        (422, errors.USER_ERROR),
    ],
    ids=["bad-request", "unauthorized", "forbidden", "not-found", "unprocessable"],
)
def test_user_error_is_attempted_once(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
    status: int,
    expected_code: str,
) -> None:
    factory = _factory(
        status_error(status, headers={"x-request-id": "req_user_err"}), _ok()
    )

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == expected_code
    assert raised.value.request_id == "req_user_err"
    assert factory.client.call_count == 1
    assert sleeper.delays == []
    assert not raised.value.retryable


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("your request was rejected", "moderation_blocked"),
        (
            "Your request was rejected as a result of our safety system. "
            "Your prompt may contain text that is not allowed by our content policy.",
            None,
        ),
        ("blocked by the moderation system", None),
    ],
    ids=["body-code", "content-policy-prose", "moderation-prose"],
)
def test_moderation_block_is_attempted_once(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
    message: str,
    code: str | None,
) -> None:
    factory = _factory(
        status_error(
            400, message, code=code, headers={"x-request-id": "req_moderation"}
        ),
        _ok(),
    )

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == errors.MODERATION_BLOCKED
    assert raised.value.request_id == "req_moderation"
    assert raised.value.status_code == 400
    assert factory.client.call_count == 1
    assert sleeper.delays == []


@pytest.mark.parametrize(
    ("retry_after", "expected_delay"),
    [
        ("5", 5.0),
        ("0", 0.0),
        ("600", constants.MAX_RETRY_AFTER_S),
        ("next tuesday", constants.RETRY_BASE_DELAY_S),
        ("Wed, 21 Oct 2026 07:28:00 GMT", constants.RETRY_BASE_DELAY_S),
        ("-3", constants.RETRY_BASE_DELAY_S),
        ("", constants.RETRY_BASE_DELAY_S),
    ],
    ids=["honoured", "zero", "clamped", "garbage", "http-date", "negative", "blank"],
)
def test_retry_after_header_policy(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
    retry_after: str,
    expected_delay: float,
) -> None:
    factory = _factory(
        status_error(429, headers={"retry-after": retry_after}), _ok()
    )

    result = _run(
        api.call_generate,
        _generate_request(tmp_path),
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    assert result.attempts == 2
    assert sleeper.delays == [expected_delay]
    assert sleeper.delays[0] <= constants.MAX_RETRY_AFTER_S


def test_default_backoff_adds_bounded_jitter(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
) -> None:
    factory = _factory(status_error(429), _ok())

    _run(
        api.call_generate,
        _generate_request(tmp_path),
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=lambda: 1.0,
    )

    assert sleeper.delays == [
        constants.RETRY_BASE_DELAY_S + constants.RETRY_MAX_JITTER_S
    ]


def test_retry_is_skipped_when_too_little_budget_remains(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    clock: FakeClock,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    """A retry that cannot plausibly finish must not burn the rest of the budget."""
    # Leave less than RETRY_MIN_REMAINING_S once the backoff is subtracted.
    clock.advance(constants.OPERATION_DEADLINE_S - 15.0)
    assert 0 < budget.remaining_s < constants.RETRY_MIN_REMAINING_S

    factory = _factory(
        status_error(429, headers={"x-request-id": "req_tight"}), _ok()
    )

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == errors.RATE_LIMITED
    assert raised.value.request_id == "req_tight"
    assert factory.client.call_count == 1
    assert sleeper.delays == []


def test_expired_deadline_makes_no_call_at_all(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    clock: FakeClock,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    clock.advance(constants.OPERATION_DEADLINE_S + 1.0)
    assert budget.remaining_s < 0

    factory = _factory(_ok())

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == errors.DEADLINE_EXCEEDED
    assert factory.client.call_count == 0
    assert sleeper.delays == []


def test_attempt_timeout_shrinks_to_the_remaining_budget(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    clock: FakeClock,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    clock.advance(constants.OPERATION_DEADLINE_S - 40.0)
    factory = _factory(_ok())

    _run(
        api.call_generate,
        _generate_request(tmp_path),
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    sent = factory.client.last_kwargs["timeout"]
    assert sent == pytest.approx(40.0)
    assert sent < constants.API_ATTEMPT_TIMEOUT_S


# ---------------------------------------------------------------------------
# IMG-AC-008 — the closed error mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (400, errors.USER_ERROR),
        (401, errors.AUTHENTICATION_ERROR),
        (403, errors.ACCESS_DENIED),
        (404, errors.USER_ERROR),
        (409, errors.USER_ERROR),
        (422, errors.USER_ERROR),
        (429, errors.RATE_LIMITED),
        (500, errors.SERVICE_ERROR),
        (502, errors.SERVICE_ERROR),
        (503, errors.SERVICE_ERROR),
        (504, errors.SERVICE_ERROR),
    ],
)
def test_map_exception_status_table(status: int, expected_code: str) -> None:
    mapped = api.map_exception(
        status_error(status, headers={"x-request-id": "req_mapped"})
    )

    assert mapped.code == expected_code
    assert mapped.code in errors.ERROR_CODES
    assert mapped.status_code == status
    assert mapped.request_id == "req_mapped"


@pytest.mark.parametrize(
    ("factory", "expected_code"),
    [
        (timeout_error, errors.API_TIMEOUT),
        (connection_error, errors.CONNECTION_ERROR),
    ],
    ids=["timeout", "connection"],
)
def test_map_exception_transport_table(factory: Any, expected_code: str) -> None:
    mapped = api.map_exception(factory())

    assert mapped.code == expected_code
    assert mapped.code in errors.ERROR_CODES
    assert mapped.request_id is None


def test_map_exception_hides_an_unknown_exception_message() -> None:
    """Only the type name is a safe signal; the text never escapes."""
    leak = "prompt-text-and-a-path-C:/private/secret-detail"

    mapped = api.map_exception(ValueError(leak))

    assert mapped.code == errors.INTERNAL_ERROR
    assert leak not in mapped.message
    assert leak not in str(mapped)
    assert mapped.details["exception_type"] == "ValueError"


def test_map_exception_passes_our_own_error_through() -> None:
    original = errors.invalid_request("nope", field="prompt")
    assert api.map_exception(original) is original


def _real_sdk_status_error(
    status: int, body: dict[str, Any], headers: dict[str, str] | None = None
) -> openai.APIStatusError:
    """Rebuild an exception exactly the way the live SDK builds one.

    `openai._base_client.BaseClient._make_status_error_from_response` sets
    `message = f"Error code: {status} - {decoded_body}"` and passes the *whole*
    decoded body, so `exc.code` is read from the top level — not from the
    nested `error` object the Image API actually returns. `conftest.status_error`
    is deliberately kinder than that, so this helper covers the real shape.
    """
    import httpx

    request = httpx.Request("POST", "https://api.openai.com/v1/images/generations")
    response = httpx.Response(
        status_code=status, headers=headers or {}, request=request
    )
    cls = openai.BadRequestError if status == 400 else openai.APIStatusError
    return cls(f"Error code: {status} - {body}", response=response, body=body)


#: The body the Image API really returns for a moderation block.
_REAL_MODERATION_BODY: dict[str, Any] = {
    "error": {
        "code": "moderation_blocked",
        "message": (
            "Your request was rejected as a result of our safety system. Your "
            "prompt may contain text that is not allowed by our safety system."
        ),
        "param": None,
        "type": "image_generation_user_error",
    }
}


def test_moderation_is_detected_in_the_real_sdk_error_shape() -> None:
    """The live SDK nests `code`, so detection must survive on the message."""
    exc = _real_sdk_status_error(400, _REAL_MODERATION_BODY)
    assert exc.code is None  # nested under "error"; the top level has none

    mapped = api.map_exception(exc)

    assert mapped.code == errors.MODERATION_BLOCKED
    assert mapped.status_code == 400


# Regression: map_exception used to relay the SDK's composite `exc.message`
# ("Error code: N - <decoded body>"), pushing the whole response body through
# MCP. _provider_message now reads only body["message"].
def test_provider_body_is_not_relayed_to_the_caller() -> None:
    exc = _real_sdk_status_error(400, _REAL_MODERATION_BODY)

    mapped = api.map_exception(exc)

    # Fields the tool never chose to surface must not ride along in the message.
    assert "image_generation_user_error" not in mapped.message
    assert "'param'" not in mapped.message


def test_map_exception_redacts_a_provider_echoed_key() -> None:
    mapped = api.map_exception(
        status_error(403, f"key {CANARY_SECRET} is not allowed"),
        secret=CANARY_SECRET,
    )

    assert mapped.code == errors.ACCESS_DENIED
    assert CANARY_SECRET not in mapped.message
    assert errors.REDACTED in mapped.message


# ---------------------------------------------------------------------------
# Response reading
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payloads",
    [[], [None], [None, None]],
    ids=["empty-data", "one-null", "all-null"],
)
def test_response_without_image_data_is_an_output_error(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
    payloads: list[str | None],
) -> None:
    factory = _factory(_ok(payloads))

    with pytest.raises(errors.ImageToolError) as raised:
        _run(
            api.call_generate,
            _generate_request(tmp_path),
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=no_jitter,
        )

    assert raised.value.code == errors.OUTPUT_ERROR
    # An empty body is our failure, not a transient one: never a second charge.
    assert factory.client.call_count == 1
    assert sleeper.delays == []


def test_partial_response_keeps_only_the_usable_entries(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    good = b64_image()
    factory = _factory(_ok([None, good]))

    result = _run(
        api.call_generate,
        _generate_request(tmp_path),
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    assert result.payloads == (good,)


def test_missing_request_id_header_is_reported_as_none(
    tmp_path: Path,
    secret: Secret,
    budget: api.Budget,
    sleeper: RecordingSleep,
    no_jitter: Any,
) -> None:
    # A non-empty header map without `x-request-id`: `FakeRawResponse` falls back
    # to its canned id only when the map is empty.
    factory = _factory(
        FakeRawResponse(
            FakeParsedResponse([b64_image()]),
            headers={"content-type": "application/json"},
        )
    )

    result = _run(
        api.call_generate,
        _generate_request(tmp_path),
        secret=secret,
        budget=budget,
        client_factory=factory,
        sleep=sleeper,
        jitter=no_jitter,
    )

    assert result.request_id is None
