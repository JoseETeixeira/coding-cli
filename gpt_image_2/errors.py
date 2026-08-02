"""Closed error taxonomy and the redaction that guards every string leaving.

Two jobs, both security-critical:

1. **A closed set of codes.** Callers get a stable machine-readable `code` and
   can branch on it. Nothing here ever relays a raw exception string, so a
   provider error body, an SDK repr, or a traceback frame cannot smuggle a
   credential or a prompt into the MCP channel.

2. **Defence-in-depth redaction.** `redact()` runs on every message before it
   is logged or returned. It does not assume we know the secret: the pattern
   scrub catches a key we never resolved (an SDK echo, a proxy error page),
   and the truncation stops a whole HTML page being relayed.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from . import constants

# ---------------------------------------------------------------------------
# Codes
# ---------------------------------------------------------------------------

#: Local, pre-network failures.
INVALID_REQUEST = "invalid_request"
UNSUPPORTED_OPTION = "unsupported_option"
INVALID_INPUT_FILE = "invalid_input_file"
INVALID_MASK = "invalid_mask"
MISSING_CREDENTIAL = "missing_credential"

#: Provider-reported failures.
MODERATION_BLOCKED = "moderation_blocked"
USER_ERROR = "user_error"
AUTHENTICATION_ERROR = "authentication_error"
ACCESS_DENIED = "access_denied"
RATE_LIMITED = "rate_limited"
SERVICE_ERROR = "service_error"
API_TIMEOUT = "api_timeout"
CONNECTION_ERROR = "connection_error"

#: Ours, after the provider succeeded or while budgeting.
DEADLINE_EXCEEDED = "deadline_exceeded"
OUTPUT_ERROR = "output_error"
INTERNAL_ERROR = "internal_error"

ERROR_CODES: frozenset[str] = frozenset(
    {
        INVALID_REQUEST,
        UNSUPPORTED_OPTION,
        INVALID_INPUT_FILE,
        INVALID_MASK,
        MISSING_CREDENTIAL,
        MODERATION_BLOCKED,
        USER_ERROR,
        AUTHENTICATION_ERROR,
        ACCESS_DENIED,
        RATE_LIMITED,
        SERVICE_ERROR,
        API_TIMEOUT,
        CONNECTION_ERROR,
        DEADLINE_EXCEEDED,
        OUTPUT_ERROR,
        INTERNAL_ERROR,
    }
)

#: Codes for which retrying the *unchanged* request is pointless or harmful.
#: Requirements IMG-REQ-008: a user error or moderation block is never retried.
NON_RETRYABLE_CODES: frozenset[str] = frozenset(
    {
        INVALID_REQUEST,
        UNSUPPORTED_OPTION,
        INVALID_INPUT_FILE,
        INVALID_MASK,
        MISSING_CREDENTIAL,
        MODERATION_BLOCKED,
        USER_ERROR,
        AUTHENTICATION_ERROR,
        ACCESS_DENIED,
    }
)

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

#: OpenAI-style keys (`sk-...`, `sk-proj-...`) and anything else long and
#: token-shaped that follows a bearer/authorization marker.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)authorization\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bapi[_\-]?key\s*[:=]\s*\S+"),
)

REDACTED = "***"


def redact(
    text: object,
    secret: str | None = None,
    *,
    max_chars: int | None = constants.MAX_RELAYED_MESSAGE_CHARS,
) -> str:
    """Return `text` as a string that is safe to log or return.

    Order matters. The exact secret goes first so that a key which does not
    match any pattern is still removed; the patterns then catch keys we never
    held; truncation runs last so the length bound is the final word.

    `max_chars=None` skips truncation. That is for stderr diagnostics such as a
    traceback, where the whole point is to keep the detail — the scrubbing still
    applies, only the length bound is lifted.
    """
    rendered = text if isinstance(text, str) else str(text)

    if secret:
        # A short or blank "secret" would turn into a catastrophic replace of
        # every character, so require something key-shaped before substituting.
        stripped = secret.strip()
        if len(stripped) >= 8:
            rendered = rendered.replace(stripped, REDACTED)

    for pattern in _SECRET_PATTERNS:
        rendered = pattern.sub(REDACTED, rendered)

    if max_chars is not None and len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "..."

    return rendered


def _safe_detail(value: Any, secret: str | None = None) -> Any:
    """Details are scalars only. Anything else becomes its redacted string.

    The secret is threaded through: a detail value can carry a credential just
    as easily as a message can, and a key that matches none of the patterns
    would otherwise survive into `to_payload()`.
    """
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(value, secret)


# ---------------------------------------------------------------------------
# The exception
# ---------------------------------------------------------------------------


class ImageToolError(Exception):
    """The only exception this subsystem raises across a module boundary.

    `message` is assumed to be author-written and safe, but it is redacted
    anyway — the whole point of defence in depth is not trusting that
    assumption.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        request_id: str | None = None,
        details: Mapping[str, Any] | None = None,
        status_code: int | None = None,
        secret: str | None = None,
    ) -> None:
        if code not in ERROR_CODES:  # pragma: no cover - programming error
            raise ValueError(f"unknown error code: {code!r}")
        self.code = code
        self.message = redact(message, secret)
        self.request_id = request_id
        self.status_code = status_code
        self.details: dict[str, Any] = {
            key: _safe_detail(val, secret) for key, val in (details or {}).items()
        }
        super().__init__(f"{self.code}: {self.message}")

    @property
    def retryable(self) -> bool:
        return self.code not in NON_RETRYABLE_CODES

    def to_payload(self) -> dict[str, Any]:
        """The exact JSON shape the MCP edge surfaces on failure."""
        payload: dict[str, Any] = {
            "status": "error",
            "code": self.code,
            "message": self.message,
        }
        if self.request_id:
            payload["request_id"] = self.request_id
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        if self.details:
            payload["details"] = dict(self.details)
        return payload

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return f"ImageToolError(code={self.code!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# Constructors for the common shapes
# ---------------------------------------------------------------------------


def invalid_request(message: str, *, field: str | None = None) -> ImageToolError:
    return ImageToolError(
        INVALID_REQUEST, message, details={"field": field} if field else None
    )


def unsupported_option(message: str, *, field: str | None = None) -> ImageToolError:
    return ImageToolError(
        UNSUPPORTED_OPTION, message, details={"field": field} if field else None
    )


def invalid_input_file(message: str, *, path: str | None = None) -> ImageToolError:
    return ImageToolError(
        INVALID_INPUT_FILE, message, details={"path": path} if path else None
    )


def invalid_mask(message: str, *, path: str | None = None) -> ImageToolError:
    return ImageToolError(
        INVALID_MASK, message, details={"path": path} if path else None
    )


def missing_credential() -> ImageToolError:
    return ImageToolError(
        MISSING_CREDENTIAL,
        (
            f"{constants.CREDENTIAL_ENV_VAR} is not set in this server's process "
            "environment or in the current Windows user environment. Set it, then "
            "reload the MCP server so the new value is inherited."
        ),
    )


def output_error(message: str, *, index: int | None = None) -> ImageToolError:
    return ImageToolError(
        OUTPUT_ERROR, message, details={"image_index": index} if index is not None else None
    )


def internal_error(exc: BaseException) -> ImageToolError:
    """Never relay `str(exc)`. The type name is the entire safe signal."""
    return ImageToolError(
        INTERNAL_ERROR,
        "The image tool failed unexpectedly. See the server's stderr log for the "
        "exception type and traceback.",
        details={"exception_type": type(exc).__name__},
    )
