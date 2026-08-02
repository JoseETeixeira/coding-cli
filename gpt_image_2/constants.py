"""Every API and policy constant for the GPT Image 2 subsystem.

This module is data only: no logic, no local imports. It exists so that each
bound has exactly one owner (task constitution principles 2 and 3) and so that
`api` and `server` never import the validation module merely to read a number.

Two classes of value live here and they are NOT interchangeable:

* **Verified API rules** — confirmed 2026-08-02 against
  https://developers.openai.com/api/docs/guides/image-generation. These describe
  the service.
* **Local policy caps** — bounds the service does not publish. These describe
  *us*. Error messages must say so, because a caller who hits one is being
  stopped by this tool, not by OpenAI.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

#: The only model this subsystem will ever send. Requirements IMG-REQ-002
#: forbids caller-supplied models and automatic fallback.
#:
#: Note: `openai` 2.8.1 types `model` as `Union[str, ImageModel, None]` and its
#: `ImageModel` literal still enumerates only dall-e-2 / dall-e-3 /
#: gpt-image-1 / gpt-image-1-mini. That literal is a type hint; the runtime
#: forwards the string verbatim. Do not "fix" this by pinning to the SDK enum.
MODEL = "gpt-image-2"

SERVER_NAME = "gpt-image-2"

#: Environment variable holding the API key. Never a tool argument.
CREDENTIAL_ENV_VAR = "OPENAI_API_KEY"

#: Windows per-user environment store, read as the second credential source.
WINDOWS_ENV_REGISTRY_KEY = r"Environment"

# ---------------------------------------------------------------------------
# Verified API rules
# ---------------------------------------------------------------------------

#: Documented: `low`, `medium`, `high`, `auto`.
QUALITIES: tuple[str, ...] = ("auto", "low", "medium", "high")

#: Requirements IMG-REQ-003 fixes the normal-use default at `high`; the live
#: smoke overrides it to `low` explicitly to minimise cost.
DEFAULT_QUALITY = "high"

#: Documented: `png` (default), `jpeg`, `webp`.
OUTPUT_FORMATS: tuple[str, ...] = ("png", "jpeg", "webp")
DEFAULT_OUTPUT_FORMAT = "png"

MIME_BY_FORMAT: dict[str, str] = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

EXTENSION_BY_FORMAT: dict[str, str] = {
    "png": ".png",
    "jpeg": ".jpg",
    "webp": ".webp",
}

#: Pillow reports JPEG as "JPEG" and JPG files as "JPEG" too, so the mapping
#: from a Pillow format name back to our vocabulary is one-to-one.
FORMAT_BY_PILLOW_NAME: dict[str, str] = {
    "PNG": "png",
    "JPEG": "jpeg",
    "WEBP": "webp",
}

#: Documented: `output_compression` applies to JPEG and WebP only.
COMPRESSIBLE_FORMATS: tuple[str, ...] = ("jpeg", "webp")
MIN_COMPRESSION = 0
MAX_COMPRESSION = 100

#: Documented: `opaque` or `auto`. gpt-image-2 does NOT support transparent
#: backgrounds, so `transparent` is rejected loudly rather than rewritten.
BACKGROUNDS: tuple[str, ...] = ("auto", "opaque")
UNSUPPORTED_BACKGROUNDS: tuple[str, ...] = ("transparent",)
DEFAULT_BACKGROUND = "auto"

#: Documented: `auto` (default) or `low`. Present on the generate endpoint only
#: — `POST /v1/images/edits` has no `moderation` parameter.
MODERATIONS: tuple[str, ...] = ("auto", "low")
DEFAULT_MODERATION = "auto"

#: Size rules, all documented:
#:   * `auto`, or explicit WIDTHxHEIGHT
#:   * both edges multiples of 16px
#:   * maximum edge <= 3840px
#:   * long:short ratio <= 3:1
#:   * total pixels between 655,360 and 8,294,400
SIZE_AUTO = "auto"
DEFAULT_SIZE = "1024x1024"
SIZE_EDGE_MULTIPLE = 16
MIN_EDGE_PX = 16
MAX_EDGE_PX = 3840
MIN_TOTAL_PIXELS = 655_360
MAX_TOTAL_PIXELS = 8_294_400
MAX_ASPECT_RATIO = 3.0

#: Documentation states: for gpt-image-2, omit `input_fidelity` — the API does
#: not allow changing it. We therefore never send the field at all; this
#: constant exists so tests can assert its absence by name.
OMITTED_EDIT_PARAMS: tuple[str, ...] = ("input_fidelity",)

# ---------------------------------------------------------------------------
# Local policy caps (NOT published service limits)
# ---------------------------------------------------------------------------

#: Requirements IMG-REQ-003. The service's true prompt ceiling is not published.
MAX_PROMPT_CHARS = 32_000

#: Requirements IMG-REQ-003. The service's true `n` range is not published.
MIN_N = 1
MAX_N = 10
DEFAULT_N = 1

#: Constitution principle 3.
MAX_EDIT_IMAGES = 16
MAX_EDIT_FILE_BYTES = 50 * 1024 * 1024

#: Documented edit input types.
EDIT_INPUT_FORMATS: tuple[str, ...] = ("png", "jpeg", "webp")

#: Decompression-bomb ceiling, checked against the header's declared dimensions
#: before any decode. The 50 MB byte cap does not bound this: a 68-byte PNG can
#: declare 60000x60000 and force a multi-hundred-megabyte allocation. Set well
#: above the API's own 8,294,400-pixel output cap so a legitimate reference (or
#: a large photograph) is never refused.
MAX_DECODE_PIXELS = 50_000_000

# ---------------------------------------------------------------------------
# Output policy
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_SUBDIR = "generated-images"

#: Generic on purpose. Requirements IMG-REQ-006 forbids deriving a filename
#: from prompt content.
DEFAULT_BASENAME = "image"

MAX_BASENAME_CHARS = 64

#: Collision suffixes start at 2 and produce image.png, image-2.png, image-3.png.
FIRST_COLLISION_SUFFIX = 2
MAX_COLLISION_SUFFIX = 9999

TEMP_SUFFIX = ".part"

#: Windows reserved device names. Rejected case-insensitively, with or without
#: an extension, because `CON.png` is just as unopenable as `CON`.
WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

# ---------------------------------------------------------------------------
# Timing, retry, and transport bounds
# ---------------------------------------------------------------------------

#: Constitution "Performance": each API attempt gets 150s.
API_ATTEMPT_TIMEOUT_S = 150.0

#: Constitution "Performance": the whole operation gets 180s.
OPERATION_DEADLINE_S = 180.0

#: ADR 0015: one retry maximum, so two attempts total.
MAX_API_ATTEMPTS = 2

RETRY_BASE_DELAY_S = 2.0
RETRY_MAX_JITTER_S = 1.0

#: Do not burn the remaining budget on a retry that cannot plausibly finish.
RETRY_MIN_REMAINING_S = 20.0

#: Upper bound on an honoured `Retry-After`, so a hostile or broken header
#: cannot park the operation for the entire deadline.
MAX_RETRY_AFTER_S = 30.0

#: Requirements IMG-REQ-008: the selected retryable statuses.
RETRYABLE_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)

#: Constitution principle 6: at most one inline preview, at most 5 MiB decoded.
MAX_INLINE_PREVIEW_BYTES = 5 * 1024 * 1024
MAX_INLINE_PREVIEWS = 1

#: Hard ceiling on any provider-supplied string we relay. Long enough to stay
#: useful, short enough that an HTML error page or a JSON body cannot be
#: forwarded whole.
MAX_RELAYED_MESSAGE_CHARS = 400
