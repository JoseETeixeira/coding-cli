"""Claude Code PostToolUse hook: swap oversized text results for a rendered page.

Claude Code only. Codex parses `updatedMCPToolOutput` and then rejects it in
`output_parser.rs::unsupported_post_tool_use_hook_specific_output`; the upstream
PR to support it was closed unmerged. There is no image-capable hook channel
there, so this module is a no-op if it is ever run under Codex.

Two design rules, both defensive:

1. **Fail open, always.** Any surprise — an unexpected payload shape, a missing
   font, an unreadable store — produces NO output, which leaves the original
   tool result untouched. A hook that mangles tool output is far worse than a
   hook that does nothing. Claude Code also ignores an `updatedToolOutput` that
   does not match the tool's schema and keeps the original, so a shape mistake
   degrades to a no-op rather than to data loss.
2. **Refuse more than it accepts.** This compresses content nobody chose to
   compress, so it runs the identifier guard in enforcing mode, sticks to the
   verified-lossless density, and gives up unless the whole payload fits on a
   single page.

Kill switch: set `OPTICAL_COMPRESSION_HOOK=0`.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any

# Tools whose results are worth intercepting. Read is the primary target: its
# result has no declared size ceiling, whereas Bash declares
# `maxResultSizeChars: 30000`, which a full rendered page exceeds.
DEFAULT_TOOLS = ("Read",)

_TRUTHY_OFF = {"0", "false", "no", "off"}


def _enabled() -> bool:
    return os.environ.get("OPTICAL_COMPRESSION_HOOK", "1").strip().lower() not in _TRUTHY_OFF


def _tools() -> tuple[str, ...]:
    raw = os.environ.get("OPTICAL_COMPRESSION_HOOK_TOOLS", "").strip()
    if not raw:
        return DEFAULT_TOOLS
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def extract_text(response: Any) -> tuple[str | None, str | None]:
    """Pull the text body out of a Read-shaped tool response.

    Returns (text, file_path). Anything unrecognised returns (None, None) so the
    caller declines rather than guesses.
    """
    if not isinstance(response, dict):
        return None, None

    payload = response.get("file")
    if isinstance(payload, dict) and isinstance(payload.get("content"), str):
        # Only plain text results are candidates; an image result is already
        # in the target form and a notebook result is structured.
        if response.get("type") not in (None, "text"):
            return None, None
        path = payload.get("filePath")
        return payload["content"], path if isinstance(path, str) else None

    return None, None


def build_output(png: bytes, original_size: int) -> dict[str, Any]:
    """Claude Code's Read image result shape."""
    return {
        "type": "image",
        "file": {
            "base64": base64.b64encode(png).decode("ascii"),
            "type": "image/png",
            "originalSize": original_size,
        },
    }


def evaluate(event: dict[str, Any]) -> dict[str, Any] | None:
    """Decide the hook response for one PostToolUse event, or None to stand down."""
    if not _enabled():
        return None
    if event.get("tool_name") not in _tools():
        return None

    text, path = extract_text(event.get("tool_response"))
    if not text:
        return None

    # Imported lazily so a missing Pillow degrades to a no-op hook rather than a
    # traceback on every single tool call.
    from . import constants, pipeline
    from .store import OpticalStore

    if len(text) < constants.HOOK_MIN_CHARS:
        return None

    outcome = pipeline.compress(
        text,
        density=constants.HOOK_DENSITY,
        store=OpticalStore(),
        min_chars=constants.HOOK_MIN_CHARS,
        enforce_guard=True,
        source=path or "tool output",
    )
    if not outcome.accepted or outcome.result is None:
        return None

    # One page only: the Read image shape carries a single image, and splitting a
    # file across results would reorder content.
    if len(outcome.result.pages) != 1:
        return None

    page = outcome.result.pages[0]
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": build_output(page.png, len(text)),
            # The image shape has no text field, so the framing — which the
            # model needs in order to trust the substitution and to know how to
            # get exact values back — travels alongside it.
            "additionalContext": pipeline.framing_text(outcome, source=path),
        }
    }


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        response = evaluate(json.loads(raw))
        if response is not None:
            sys.stdout.write(json.dumps(response))
    except Exception:  # noqa: BLE001 - fail open, never disturb the tool result
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
