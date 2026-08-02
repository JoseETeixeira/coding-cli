"""Stdio contract smoke for the gpt-image-2 MCP server (IMG-AC-009).

Drives the *real* server through the *real* launcher — `run_gpt_image_2_server.py`,
byte-for-byte the command all six host registrations invoke — over
`mcp.client.stdio`, exactly as Claude Code / Codex / Copilot would, with the
OpenAI boundary and the credential lookup replaced inside the child by
`fake_backend`. Zero network, zero spend, zero credential.

Run:
    <python3.12> tests/gpt_image_2/mcp_smoke.py

Exits 0 on success, 1 on failure. This is deliberately NOT a pytest module:
the filename does not match `test_*.py` / `*_test.py` and no function is named
`test_*`, so pytest will not collect it. `test_contract_gates.py` runs it as a
subprocess so it is part of the default `pytest tests/gpt_image_2` gate.

What it proves:
  0. The launcher itself works. This used to bootstrap with
     `from gpt_image_2.server import main; main()`, which reproduced what the
     launcher does instead of running it — so a renamed `main`, a moved file, a
     dropped `sys.path` insert, or a syntax error in `run_gpt_image_2_server.py`
     would have shipped green and broken every host registration at once.
  1. `initialize` completes.
  2. `tools/list` exposes exactly {generate_image, edit_image} — no credential,
     model-override, URL-input, or overwrite tool sneaks in (IMG-AC-002).
  3. One valid `generate_image` call returns parseable metadata pinned to
     model `gpt-image-2`, and the path it reports really exists on disk and
     really decodes as a PNG (IMG-REQ-006, IMG-REQ-007).
  4. One invalid `generate_image` call (`background=transparent`) comes back as
     an error carrying the closed code `unsupported_option` (IMG-REQ-003).

The "stdout stayed clean" assertion is structural rather than a separate check:
every step below is a JSON-RPC round trip over the child's stdout. A stray
`print()` anywhere in the server, or any non-JSON-RPC byte on that stream,
corrupts the framing and the client raises a parse/validation error long before
these assertions run. Completing the whole exchange *is* the proof.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import traceback
from io import BytesIO
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from PIL import Image as PILImage  # noqa: E402

from gpt_image_2 import constants, errors  # noqa: E402

#: The child must be this interpreter: same 3.12 runtime, same site-packages.
#: Hardcoding a machine path here would break the moment the checkout moves.
PYTHON = sys.executable

#: The exact file every host registration names in its `args`. Running anything
#: else here would smoke a code path no host ever takes.
LAUNCHER = REPO_ROOT / "run_gpt_image_2_server.py"

#: `fake_backend` swaps the OpenAI client and the credential lookup *before*
#: the launcher runs, so the production package needs no test switch. Then
#: `runpy.run_path(..., run_name="__main__")` executes the launcher exactly as
#: `python run_gpt_image_2_server.py` would, `if __name__ == "__main__"` guard
#: and all — the only difference being that `fake_backend` is already imported.
BOOTSTRAP = (
    "import fake_backend; import runpy; "
    f"runpy.run_path({str(LAUNCHER)!r}, run_name='__main__')"
)

EXPECTED_TOOLS = {"generate_image", "edit_image"}

PROMPT = "a flat vector icon of a blue circle on a white background"


class SmokeFailure(AssertionError):
    """Raised by `_require` so a failed check is distinguishable from a crash."""


def _require(condition: object, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _text_blocks(result: Any) -> list[str]:
    return [
        block.text
        for block in result.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]


def _image_blocks(result: Any) -> list[Any]:
    return [block for block in result.content if getattr(block, "type", None) == "image"]


def _json_objects(result: Any) -> list[dict[str, Any]]:
    """Every text block that is, or embeds, a JSON object.

    FastMCP re-wraps a `ToolError` as ``Error executing tool <name>: <text>``,
    so the failure payload arrives with a human prefix in front of the JSON.
    Slicing from the first brace keeps this smoke pinned to the *payload*
    contract rather than to that prefix.
    """
    found: list[dict[str, Any]] = []
    for text in _text_blocks(result):
        candidate = text[text.index("{"):] if "{" in text else text
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            found.append(parsed)
    return found


def _result_payload(result: Any, label: str) -> dict[str, Any]:
    payloads = _json_objects(result)
    _require(payloads, f"{label}: no JSON object in the result content")
    return payloads[-1]


async def _drive(temp_dir: Path) -> None:
    out_dir = temp_dir / "images"

    # Say so plainly rather than letting the child die with a runpy traceback
    # buried in the stderr of a process the client is still handshaking with.
    _require(
        LAUNCHER.is_file(),
        f"launcher not found at {LAUNCHER}; every host registration names this "
        "exact file, so its absence breaks all of them",
    )

    env = {
        # Both roots: the package lives at the repo root, `fake_backend` lives
        # beside this file. `stdio_client` merges this over a safe default env
        # that deliberately does NOT inherit OPENAI_API_KEY.
        "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(HERE)]),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "GPT_IMAGE_2_LOG_LEVEL": "ERROR",
    }

    params = StdioServerParameters(
        command=PYTHON,
        args=["-c", BOOTSTRAP],
        env=env,
        # A throwaway cwd, so a tool that fell back to its default output
        # location would still write into scratch space and never into the
        # checkout.
        cwd=str(temp_dir),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("INITIALIZE ok")

            # -- tools/list -------------------------------------------------
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            print("TOOLS:", sorted(names))
            _require(
                names == EXPECTED_TOOLS,
                f"tools/list must be exactly {sorted(EXPECTED_TOOLS)}; got {sorted(names)}",
            )

            schema = next(t for t in listed.tools if t.name == "generate_image").inputSchema
            forbidden = {"api_key", "model", "url", "endpoint", "headers", "file_id", "overwrite"}
            leaked = forbidden & set(schema.get("properties", {}))
            _require(not leaked, f"generate_image schema exposes forbidden arguments: {sorted(leaked)}")
            print("SCHEMA ok: no credential/model/url/overwrite argument")

            # -- one valid call ---------------------------------------------
            ok = await session.call_tool(
                "generate_image",
                {"prompt": PROMPT, "output_dir": str(out_dir), "quality": "low"},
            )
            _require(
                not ok.isError,
                f"valid generate_image was reported as an error: {_text_blocks(ok)}",
            )

            metadata = _result_payload(ok, "generate_image")
            _require(
                metadata.get("model") == constants.MODEL,
                f"metadata model must be {constants.MODEL!r}; got {metadata.get('model')!r}",
            )
            _require(
                metadata.get("status") == "ok" and metadata.get("operation") == "generate",
                f"unexpected metadata envelope: {metadata.get('status')!r}/{metadata.get('operation')!r}",
            )

            published = metadata.get("images") or []
            _require(len(published) == 1, f"expected exactly one published image; got {len(published)}")
            entry = published[0]

            saved = Path(entry["path"])
            _require(saved.is_absolute(), f"reported path is not absolute: {saved}")
            _require(saved.exists(), f"reported path does not exist on disk: {saved}")
            _require(
                saved.parent == out_dir,
                f"image landed outside the requested output_dir: {saved.parent} != {out_dir}",
            )

            with PILImage.open(BytesIO(saved.read_bytes())) as decoded:
                decoded.load()
                pil_format = decoded.format
                pil_size = decoded.size
            _require(pil_format == "PNG", f"saved file is {pil_format}, not PNG")
            _require(
                entry["format"] == "png"
                and entry["mime_type"] == constants.MIME_BY_FORMAT["png"]
                and (entry["width"], entry["height"]) == pil_size
                and entry["bytes"] == saved.stat().st_size,
                f"metadata does not describe the file on disk: {entry}",
            )
            _require(
                len(_image_blocks(ok)) == constants.MAX_INLINE_PREVIEWS,
                "expected exactly one bounded inline preview block",
            )
            print("GENERATE ok:", saved.name, pil_format, pil_size, f"{entry['bytes']}B")

            # -- one invalid call -------------------------------------------
            bad = await session.call_tool(
                "generate_image",
                {"prompt": PROMPT, "output_dir": str(out_dir), "background": "transparent"},
            )
            _require(bad.isError, "background='transparent' should have been rejected")

            failure = _result_payload(bad, "invalid generate_image")
            _require(
                failure.get("code") == errors.UNSUPPORTED_OPTION,
                f"expected code {errors.UNSUPPORTED_OPTION!r}; got {failure.get('code')!r}",
            )
            _require(
                failure.get("status") == "error",
                f"failure payload must carry status='error'; got {failure.get('status')!r}",
            )
            _require(
                (failure.get("details") or {}).get("field") == "background",
                f"failure payload should name the offending field; got {failure.get('details')!r}",
            )
            print("REJECT ok:", failure["code"])

            # Nothing new landed: the rejected call must not have written a file.
            written = sorted(p.name for p in out_dir.iterdir())
            _require(
                written == [saved.name],
                f"the rejected call left files behind: {written}",
            )
            print("NO-SPILL ok:", written)


async def _run() -> int:
    temp_dir = Path(tempfile.mkdtemp(prefix="gpt_image_2_smoke_"))
    try:
        await _drive(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return 0


def _first_smoke_failure(exc: BaseException) -> SmokeFailure | None:
    """Dig a `SmokeFailure` out of the ExceptionGroup anyio's task group raises.

    `stdio_client` runs the reader/writer inside a task group, so an assertion
    raised in the body surfaces wrapped. Without this the useful message would
    be buried under a generic traceback.
    """
    if isinstance(exc, SmokeFailure):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for inner in exc.exceptions:
            found = _first_smoke_failure(inner)
            if found is not None:
                return found
    return None


def run() -> int:
    try:
        asyncio.run(_run())
    except BaseException as exc:  # noqa: BLE001 - every failure becomes exit 1
        failure = _first_smoke_failure(exc)
        if failure is not None:
            print("\nMCP SMOKE: FAIL -", failure)
        else:
            print("\nMCP SMOKE: FAIL - unexpected exception")
            traceback.print_exc()
        return 1
    print("\nMCP SMOKE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(run())
