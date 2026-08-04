"""Optical compression MCP server (FastMCP, stdio).

Mirrors `gpt_image_2/server.py`: the protocol edge and nothing more. Policy
lives in `pipeline`, rasterisation in `render`, safety in `guard`, persistence
in `store`, so all of it stays testable without stdio.

stdout is the JSON-RPC channel. Never `print()` here or anywhere in this
package; logging goes to stderr.

`structured_output=False` on every tool is load-bearing, not stylistic. Codex's
`as_function_call_output_payload` checks `structuredContent` *before* content
blocks, so a server that sets it silently discards the image and the agent
receives text with no error (openai/codex issue #10334). FastMCP only omits
`structuredContent` when the tool declares no output schema, which is exactly
what this flag does.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations

from . import constants, guard, pipeline
from . import render as render_module
from .store import OpticalStore, StoreError, validate_digest


def _configure_logging() -> None:
    """Attach a stderr handler to THIS package's logger only.

    `logging.basicConfig` would set the level on the ROOT logger, so a debug
    setting here would also switch on debug for every third-party library in the
    process. stderr, never stdout: stdout is the JSON-RPC channel.
    """
    requested = os.environ.get("OPTICAL_COMPRESSION_LOG_LEVEL", "WARNING").strip().upper()
    level = logging.getLevelNamesMapping().get(requested, logging.WARNING)

    package_logger = logging.getLogger("optical_compression")
    package_logger.setLevel(level)
    if not package_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        package_logger.addHandler(handler)
    package_logger.propagate = False


_configure_logging()
log = logging.getLogger("optical_compression.server")

mcp = FastMCP(constants.SERVER_NAME)

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
# compress writes cache and original files; it never modifies caller data.
_WRITES_CACHE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

_DENSITY_HELP = (
    "Density presets, with measured decode fidelity: "
    "'safe' (12px, 2.11x, 100% character and identifier accuracy), "
    "'balanced' (10px, 2.90x, 100% character and identifier accuracy, default), "
    "'aggressive' (8px, 5.35x, but only 95.8% identifier accuracy - it corrupted "
    "a UUID and an access-key in trials, so it is refused for payloads that "
    "contain identifiers)."
)


def _fail(exc: BaseException) -> ToolError:
    """Convert anything into one closed JSON failure payload."""
    if isinstance(exc, (render_module.RenderError, StoreError, ValueError)):
        payload = {"status": "error", "code": type(exc).__name__, "message": str(exc)}
    else:
        log.error(
            "optical_compression unexpected failure\n%s",
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
        payload = {
            "status": "error",
            "code": "internal_error",
            "message": f"Unexpected failure: {type(exc).__name__}.",
        }
    return ToolError(json.dumps(payload, ensure_ascii=False))


@mcp.tool(
    name="optical_compress",
    description=(
        "Render a large text payload into images that cost fewer "
        "tokens than the text, and store the exact original for retrieval. Use "
        "on large read-mostly content - long logs, transcripts, histories, "
        "already-reviewed diffs - where you need the gist and can fetch exact "
        "values back on demand. THIS IS LOSSY FOR EXACT VALUES: read the image "
        "for gist and navigation, then call optical_retrieve before relying on "
        "any hash, UUID, key, path, line number, or numeric literal. Declines "
        f"payloads under {constants.MIN_PAYLOAD_CHARS} characters, because page "
        "padding does not amortise below that and rendering would cost more "
        f"than the text. {_DENSITY_HELP}"
    ),
    annotations=_WRITES_CACHE,
    structured_output=False,
)
async def optical_compress(
    content: str,
    density: str | None = None,
    source: str | None = None,
    tier: str | None = None,
) -> list:
    try:
        store = OpticalStore()
        outcome = pipeline.compress(
            content,
            density=density or constants.DEFAULT_DENSITY,
            tier=tier or constants.DEFAULT_TIER,
            store=store,
            source=source,
            enforce_guard=False,
        )
        metadata: dict[str, Any] = {"status": "ok", **outcome.to_dict()}

        if not outcome.accepted:
            metadata["status"] = "declined"
            metadata["guidance"] = (
                "Send the original text instead; compressing it would not pay off."
            )
            log.info("optical_compress declined reason=%s", outcome.reason)
            return [metadata]

        result = outcome.result
        assert result is not None
        blocks = [Image(data=page.png, format="png") for page in result.pages]
        metadata["framing"] = pipeline.framing_text(outcome, source=source)
        log.info(
            "optical_compress ok pages=%d ratio=%.2f reduction=%.1f%% hits=%d",
            len(result.pages),
            result.ratio,
            result.reduction * 100,
            result.cache_hits,
        )
        # Framing text FIRST: it must be read before the images it describes.
        return [metadata["framing"], *blocks, metadata]
    except Exception as exc:  # noqa: BLE001 - every path becomes a safe payload
        raise _fail(exc) from None


@mcp.tool(
    name="optical_retrieve",
    description=(
        "Retrieve the exact, verbatim original text behind a previous "
        "optical_compress call, by digest. This is the safety valve that makes "
        "optical compression usable: always call it before quoting or acting on "
        "any exact value you read from a rendered image. Supports a bounded span "
        "via start/length so you can pull back one identifier without paying for "
        "the whole payload again."
    ),
    annotations=_READ_ONLY,
    structured_output=False,
)
async def optical_retrieve(
    digest: str,
    start: int | None = None,
    length: int | None = None,
) -> list:
    try:
        digest = validate_digest(digest)
        store = OpticalStore()
        stored = store.get_original(digest)
        if stored is None:
            return [
                {
                    "status": "not_found",
                    "digest": digest,
                    "message": (
                        "No stored original for that digest. It may have been "
                        "pruned, or produced in a different working directory."
                    ),
                }
            ]

        span = store.slice_original(digest, start=start or 0, length=length)
        return [
            {
                "status": "ok",
                "digest": digest,
                "total_chars": stored.chars,
                "start": start or 0,
                "returned_chars": len(span or ""),
                "exact": True,
                "text": span,
            }
        ]
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from None


@mcp.tool(
    name="optical_stats",
    description=(
        "Report optical-compression store statistics, the density presets with "
        "their measured fidelity, and this host's capability profile - "
        "specifically whether automatic hook interception is available here. "
        "Call this to find out why automatic compression is or is not happening."
    ),
    annotations=_READ_ONLY,
    structured_output=False,
)
async def optical_stats(preview: str | None = None) -> list:
    try:
        store = OpticalStore()
        payload: dict[str, Any] = {
            "status": "ok",
            "store": store.stats(),
            "densities": constants.DENSITIES,
            "minimum_chars": constants.MIN_PAYLOAD_CHARS,
            "hook_minimum_chars": constants.HOOK_MIN_CHARS,
            "capabilities": host_capabilities(),
        }
        if preview:
            payload["preview"] = {
                **render_module.preflight(preview),
                "guard": guard.scan(preview).to_dict(),
                "max_safe_density": guard.max_safe_density(preview),
            }
        return [payload]
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from None


def host_capabilities() -> dict[str, Any]:
    """Report what this host can actually do, so nothing silently no-ops.

    The asymmetry is permanent, not a gap waiting to be filled: Codex parses
    `updatedMCPToolOutput` and then explicitly rejects it in
    `output_parser.rs::unsupported_post_tool_use_hook_specific_output`, and the
    upstream PR to support it was closed unmerged. Claude Code, by contrast,
    honours `PostToolUse.updatedToolOutput` — verified end to end.
    """
    host = _detect_host()
    return {
        "detected_host": host,
        "mcp_tools": True,
        "automatic_hook": host == "claude-code",
        "explanation": (
            "Automatic hook interception is available on Claude Code only. "
            "Codex hooks cannot rewrite tool output: updatedMCPToolOutput is "
            "explicitly rejected upstream and the PR to support it was closed "
            "unmerged. On Codex, call optical_compress explicitly."
        ),
    }


def _detect_host() -> str:
    if os.environ.get("CLAUDE_CODE_SESSION") or os.environ.get("CLAUDECODE"):
        return "claude-code"
    if os.environ.get("CODEX_SESSION") or os.environ.get("CODEX_SANDBOX"):
        return "codex"
    return "unknown"


def main() -> None:
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
