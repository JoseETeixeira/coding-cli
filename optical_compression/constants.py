"""Fixed values for optical compression.

Every number here is either published by a vendor or was measured by the
feasibility study in `.batman/agentic-image-compression/experiments/`. Nothing
is a guess; where a value is an estimate, it is documented as a floor.
"""

from __future__ import annotations

SERVER_NAME = "optical-compression"

# --- Claude vision billing -------------------------------------------------
# Claude bills whole 28x28-pixel patches: tokens = ceil(w/28) * ceil(h/28).
# Validated exactly against Anthropic's published size->token table
# (200x200 -> 64, 1000x1000 -> 1296, 1092x1092 -> 1521).
CLAUDE_PATCH = 28

TIERS: dict[str, dict[str, int]] = {
    "standard": {"max_edge": 1568, "max_tokens": 1568},
    "highres": {"max_edge": 2576, "max_tokens": 4784},  # Claude 4.7+
}
DEFAULT_TIER = "standard"

# --- Density presets -------------------------------------------------------
# Compression ratio depends only on font size: ratio = 196 / (char_w * line_h).
# Break-even is ~17px; above that an image costs MORE than the text it replaces.
#
# Measured decode fidelity, 12 trials over code / identifiers / logs / prose:
#   fs12 -> 100% character AND 100% critical-token accuracy
#   fs10 -> 100% character AND 100% critical-token accuracy
#   fs8  -> 99.4% character but only 95.8% critical-token: it corrupted a UUID
#           (3c197fdfa164 -> 3c197fdfe164) and an access-key-shaped string.
DENSITIES: dict[str, dict[str, object]] = {
    "safe": {
        "font_size": 12,
        "expected_ratio": 2.11,
        "verified_lossless": True,
        "note": "100% character and critical-token accuracy in trials.",
    },
    "balanced": {
        "font_size": 10,
        "expected_ratio": 2.90,
        "verified_lossless": True,
        "note": "100% character and critical-token accuracy in trials. Default.",
    },
    "aggressive": {
        "font_size": 8,
        "expected_ratio": 5.35,
        "verified_lossless": False,
        "note": (
            "95.8% critical-token accuracy: corrupted a UUID and an "
            "access-key-shaped string in trials. Never use for identifiers."
        ),
    },
}
DEFAULT_DENSITY = "balanced"

# The density the automatic hook is allowed to use. Deliberately not
# configurable up: the hook compresses content nobody chose to compress.
HOOK_DENSITY = "balanced"

# --- Payload bounds --------------------------------------------------------
# Below this, rendering LOSES: padding does not amortise. Measured, a 428-char
# code sample at fs12 scored 0.95x - worse than sending the text.
MIN_PAYLOAD_CHARS = 8_000

# The automatic hook is more conservative still than a deliberate tool call.
HOOK_MIN_CHARS = 10_000

# A rendered page is pure black on white, so it is re-encoded to 1-bit PNG.
# Measured on a full page: 507 KB RGB -> 85 KB 1-bit, an 83% saving, free.
RENDER_MODE = "1"

MAX_PAGES = 8
MAX_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024

# --- Fonts -----------------------------------------------------------------
# Monospace only: a proportional face wastes horizontal space and makes the
# column arithmetic non-deterministic.
MONO_FONT_CANDIDATES = (
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
)

# Newlines become a visible marker so the decode is reversible without
# preserving physical line breaks.
NEWLINE_MARKER = " \u00ac "

PADDING_PX = 8

# --- Storage ---------------------------------------------------------------
STORE_DIRNAME = ".optical-compression"
DIGEST_CHARS = 16
DEFAULT_RETENTION_DAYS = 14
