"""GPT Image 2 MCP server (FastMCP, stdio).

The protocol edge and nothing more: it translates tool arguments into validated
requests, orchestrates the credential/API/publish sequence, and presents the
result. It owns no validation rule, no HTTP policy, and no filesystem policy —
those live in `models`, `api`, and `images` so they stay testable without stdio.

stdout is the JSON-RPC channel. Never `print()` here or anywhere in this
package; logging goes to stderr, exactly as `mnemo/mnemo/server.py` does.

Deliberately absent from both tool schemas, and each absence is the enforcement
of a requirement: `model` (IMG-REQ-002 fixes gpt-image-2), `api_key`
(IMG-REQ-005 forbids a credential argument), `headers` / `endpoint` / `url` /
`file_id` (IMG-REQ-002 forbids escapes and remote inputs), `overwrite`
(IMG-REQ-006 has no overwrite mode), and `input_fidelity` (the API does not
allow changing it for this model).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations

from . import api, constants, credentials, errors, images, models

def _configure_logging() -> None:
    """Attach a stderr handler to THIS package's logger only.

    Two things went wrong with the obvious `logging.basicConfig(level=...)`:

    1. `basicConfig` sets the level on the ROOT logger. A knob named
       `GPT_IMAGE_2_LOG_LEVEL=DEBUG` would therefore also switch on DEBUG for
       `openai` and `httpx`, and `openai._base_client` logs the full request
       options at that level — the user's prompt, and for an edit the raw
       reference-image and mask bytes — straight to stderr. Constitution
       principle 1 forbids exactly that. So the level is applied to the
       `gpt_image_2` logger, and the noisy third-party loggers are pinned at
       WARNING regardless of what the operator asks for.
    2. `level=` rejects a lowercase name with `ValueError: Unknown level:
       'info'` — raised at import, which kills the MCP server at startup with a
       traceback instead of serving. The value is now normalised and an
       unrecognised one falls back to WARNING rather than crashing.

    stderr, never stdout: stdout is the JSON-RPC channel.
    """
    requested = os.environ.get("GPT_IMAGE_2_LOG_LEVEL", "WARNING").strip().upper()
    level = logging.getLevelNamesMapping().get(requested, logging.WARNING)

    package_logger = logging.getLogger("gpt_image_2")
    package_logger.setLevel(level)
    if not package_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        package_logger.addHandler(handler)
    # Do not let our records climb to a root handler a host may have installed.
    package_logger.propagate = False

    # Never let a verbose setting here turn into content logging over there.
    for noisy in ("openai", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_configure_logging()
log = logging.getLogger("gpt_image_2.server")

mcp = FastMCP(constants.SERVER_NAME)

_PAID_NOTICE = (
    "Calls OpenAI's Image API: this costs money, is subject to OpenAI "
    "moderation, and can take up to about two minutes. Writes image files to "
    "disk and never overwrites an existing file."
)

_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,  # never overwrites; only ever creates new files
    idempotentHint=False,  # every call is a fresh, separately billed generation
    openWorldHint=True,  # external service
)


# ---------------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------------


def _publish_all(
    result: api.ApiResult,
    output_format: str,
    output_dir: Path,
    basename: str,
    extension: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[images.DecodedImage]]:
    """Decode every image before publishing any, then publish the valid ones.

    Requirements IMG-REQ-006: a malformed entry in a multi-image response must
    not leave an invalid partial file behind, and must not stop the valid
    images from being reported.
    """
    decoded: list[tuple[int, images.DecodedImage]] = []
    failures: list[dict[str, Any]] = []

    for index, payload in enumerate(result.payloads):
        try:
            decoded.append(
                (index, images.decode_image_payload(payload, output_format, index=index))
            )
        except errors.ImageToolError as exc:
            failures.append(
                {"index": index, "code": exc.code, "message": exc.message}
            )

    if not decoded:
        first = failures[0] if failures else None
        raise errors.output_error(
            first["message"] if first else "The API returned no usable image data.",
            index=first["index"] if first else None,
        )

    published: list[dict[str, Any]] = []
    kept: list[images.DecodedImage] = []
    for index, image in decoded:
        # Guarded per image. An unguarded loop meant that a disk-full or
        # permission failure on image 2 aborted the whole call: images already
        # written to disk were orphaned and the error payload named none of
        # them, even though every image had already been paid for. IMG-REQ-006
        # and IMG-REQ-007 both require the opposite — report what landed.
        try:
            path = images.publish_atomic(image.data, output_dir, basename, extension)
        except errors.ImageToolError as exc:
            failures.append({"index": index, "code": exc.code, "message": exc.message})
            continue
        except OSError as exc:
            failures.append(
                {
                    "index": index,
                    "code": errors.OUTPUT_ERROR,
                    "message": f"Writing the output image failed: {type(exc).__name__}.",
                }
            )
            continue

        kept.append(image)
        published.append(
            {
                "index": index,
                "path": str(path),
                "format": image.format,
                "mime_type": constants.MIME_BY_FORMAT[image.format],
                "bytes": image.size_bytes,
                "width": image.width,
                "height": image.height,
            }
        )

    if not published:
        first = failures[0] if failures else None
        raise errors.output_error(
            first["message"] if first else "No image could be written to disk.",
            index=first["index"] if first else None,
        )

    return published, failures, kept


def _preview(kept: list[images.DecodedImage]) -> tuple[list[Image], dict[str, Any]]:
    """At most one inline image, at most 5 MiB decoded (constitution 6).

    The reason is always reported, so an agent that receives no pixels knows
    whether to open the file or whether more files exist.
    """
    if not kept:  # pragma: no cover - _publish_all guarantees at least one
        return [], {"included": False, "reason": "no_images"}

    first = kept[0]
    if first.size_bytes > constants.MAX_INLINE_PREVIEW_BYTES:
        return [], {"included": False, "reason": "too_large"}

    blocks = [Image(data=first.data, format=first.format)]
    if len(kept) > constants.MAX_INLINE_PREVIEWS:
        return blocks, {"included": True, "reason": "first_of_n"}
    return blocks, {"included": True, "reason": None}


def _metadata(
    *,
    operation: str,
    request: models._CommonRequest,
    result: api.ApiResult,
    published: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    preview: dict[str, Any],
    budget: api.Budget,
) -> dict[str, Any]:
    requested: dict[str, Any] = {
        "size": request.size,
        "quality": request.quality,
        "output_format": request.output_format,
        "n": request.n,
        "background": request.background,
    }
    if request.output_compression is not None:
        requested["output_compression"] = request.output_compression
    if isinstance(request, models.GenerateRequest):
        requested["moderation"] = request.moderation

    metadata: dict[str, Any] = {
        "operation": operation,
        "model": constants.MODEL,
        "status": "ok",
        "images": published,
        "failed_images": failures,
        "request_id": result.request_id,
        "usage": result.usage,
        "revised_prompt": result.revised_prompt,
        "requested": requested,
        # A short response — the provider returning fewer images than `n` — used
        # to read as a clean success. An agent seeing `"status": "ok"` with
        # `"n": 3` and one path had no way to tell it was shorted, so the
        # shortfall is now explicit.
        "provider_returned": len(result.payloads),
        "complete": len(published) == request.n and not failures,
        "attempts": result.attempts,
        "duration_ms": int(budget.elapsed_s * 1000),
        "preview": preview,
    }
    return metadata


def _fail(exc: BaseException, secret: credentials.Secret | None = None) -> ToolError:
    """Convert anything into the single closed, redacted failure payload.

    `ToolError` makes the host mark the result `isError`, and the message raised
    here is exactly one JSON object.

    Know what a real host actually delivers, though:
    `mcp.server.fastmcp.tools.base.Tool.run` catches every exception, including
    this one, and re-raises `ToolError(f"Error executing tool {name}: {e}")`.
    So over the wire the agent sees that prefix followed by our JSON, and
    `json.loads` on the whole string fails — the payload is the JSON object
    beginning at the first `{`. That prefix is FastMCP's, not ours, and it is
    not worth distorting this function's contract to work around it.
    """
    import json
    import traceback

    revealed = secret.reveal() if secret is not None else None

    if isinstance(exc, errors.ImageToolError):
        mapped = exc
    else:
        # Never `log.exception`: it writes the raw traceback, and `str(exc)` on a
        # provider error can carry a credential or a request body. Format it,
        # scrub it, then log it — the detail is kept, the secret is not.
        formatted = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        log.error(
            "gpt_image_2 unexpected failure\n%s",
            errors.redact(formatted, revealed, max_chars=None),
        )
        mapped = errors.internal_error(exc)

    return ToolError(json.dumps(mapped.to_payload(), ensure_ascii=False))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="generate_image",
    description=(
        "Generate a new raster image from a text prompt with OpenAI "
        f"{constants.MODEL}, save it locally, and return its path plus a "
        f"bounded preview. {_PAID_NOTICE} Defaults: quality=high, "
        "size=1024x1024, output_format=png, n=1, output to "
        "<working-directory>/generated-images/image.png. Transparent "
        "backgrounds are not supported by this model."
    ),
    annotations=_ANNOTATIONS,
    structured_output=False,
)
async def generate_image(
    prompt: str,
    size: str | None = None,
    quality: str | None = None,
    output_format: str | None = None,
    n: int | None = None,
    output_compression: int | None = None,
    background: str | None = None,
    moderation: str | None = None,
    output_dir: str | None = None,
    basename: str | None = None,
) -> list:
    budget = api.Budget()
    secret: credentials.Secret | None = None
    try:
        request = models.validate_generate(
            prompt=prompt,
            size=size,
            quality=quality,
            output_format=output_format,
            n=n,
            output_compression=output_compression,
            background=background,
            moderation=moderation,
            output_dir=output_dir,
            basename=basename,
        )

        # First credential touch: strictly after every local check.
        secret = credentials.resolve_api_key()
        result = await api.call_generate(request, secret=secret, budget=budget)

        published, failures, kept = _publish_all(
            result,
            request.output_format,
            request.output_dir,
            request.basename,
            request.extension,
        )
        blocks, preview = _preview(kept)
        metadata = _metadata(
            operation="generate",
            request=request,
            result=result,
            published=published,
            failures=failures,
            preview=preview,
            budget=budget,
        )
        log.info(
            "gpt_image_2 generate ok images=%d attempts=%d request_id=%s duration_ms=%d",
            len(published),
            result.attempts,
            result.request_id or "-",
            metadata["duration_ms"],
        )
        return [*blocks, metadata]
    except Exception as exc:  # noqa: BLE001 - every path becomes a safe payload
        raise _fail(exc, secret) from None


@mcp.tool(
    name="edit_image",
    description=(
        "Edit one or more local reference images with a text prompt using "
        f"OpenAI {constants.MODEL}, save the result locally, and return its "
        f"path plus a bounded preview. {_PAID_NOTICE} References must be local "
        "PNG, JPEG, or WebP files; the first one is the mask target and the "
        "order is preserved. An optional mask must match the first reference's "
        "dimensions and format and must be transparent where the image should "
        "be redrawn. Remote URLs and OpenAI file IDs are not accepted."
    ),
    annotations=_ANNOTATIONS,
    structured_output=False,
)
async def edit_image(
    prompt: str,
    image_paths: list[str],
    mask_path: str | None = None,
    size: str | None = None,
    quality: str | None = None,
    output_format: str | None = None,
    n: int | None = None,
    output_compression: int | None = None,
    background: str | None = None,
    output_dir: str | None = None,
    basename: str | None = None,
) -> list:
    budget = api.Budget()
    secret: credentials.Secret | None = None
    try:
        request = models.validate_edit(
            prompt=prompt,
            image_paths=image_paths,
            mask_path=mask_path,
            size=size,
            quality=quality,
            output_format=output_format,
            n=n,
            output_compression=output_compression,
            background=background,
            output_dir=output_dir,
            basename=basename,
        )

        secret = credentials.resolve_api_key()
        result = await api.call_edit(request, secret=secret, budget=budget)

        published, failures, kept = _publish_all(
            result,
            request.output_format,
            request.output_dir,
            request.basename,
            request.extension,
        )
        blocks, preview = _preview(kept)
        metadata = _metadata(
            operation="edit",
            request=request,
            result=result,
            published=published,
            failures=failures,
            preview=preview,
            budget=budget,
        )
        metadata["references"] = len(request.references)
        metadata["mask_used"] = request.mask is not None
        log.info(
            "gpt_image_2 edit ok images=%d refs=%d attempts=%d request_id=%s duration_ms=%d",
            len(published),
            len(request.references),
            result.attempts,
            result.request_id or "-",
            metadata["duration_ms"],
        )
        return [*blocks, metadata]
    except Exception as exc:  # noqa: BLE001 - every path becomes a safe payload
        raise _fail(exc, secret) from None


def main() -> None:
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
