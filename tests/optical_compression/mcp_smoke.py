"""End-to-end stdio smoke test for the optical-compression MCP server.

Launches the server exactly as Claude Code and Codex do — a subprocess speaking
JSON-RPC over stdio — and asserts the wire contract rather than the Python API.

Run directly:  python tests/optical_compression/mcp_smoke.py

Kept out of the default pytest run (no `test_` prefix) because it spawns a real
subprocess, matching `tests/gpt_image_2/mcp_smoke.py`.

The load-bearing assertion is `structuredContent is None`. Codex checks
`structuredContent` *before* content blocks, so if it is ever populated the
image is silently discarded and the agent receives text with no error at all
(openai/codex issue #10334). A regression there would be invisible in
production, so it is caught here.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

PAYLOAD = "agent history line with ordinary narrative content and no identifiers. " * 200
RISKY = "sha256=30b7e9ba6b5b7642c92af44eddf7b4f6 build finished cleanly. " * 200


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    return condition


async def run() -> int:
    store = Path(tempfile.gettempdir()) / "optical-smoke-store"
    env = {**os.environ, "OPTICAL_COMPRESSION_DIR": str(store)}
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(REPOSITORY_ROOT / "run_optical_compression_server.py")],
        env=env,
    )

    ok = True
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            ok &= check("three tools registered",
                        {"optical_compress", "optical_retrieve", "optical_stats"} <= set(tools))
            ok &= check("no tool declares an output schema (Codex image-drop guard)",
                        all(getattr(t, "outputSchema", None) in (None, {}) for t in tools.values()))

            result = await session.call_tool(
                "optical_compress", {"content": PAYLOAD, "source": "smoke.log"}
            )
            kinds = [block.type for block in result.content]
            ok &= check("returns text + image blocks", kinds.count("image") >= 1, str(kinds))
            ok &= check("framing text precedes the image", kinds and kinds[0] == "text")
            ok &= check("structuredContent is absent", result.structuredContent is None)

            images = [b for b in result.content if b.type == "image"]
            ok &= check("image is png", all(b.mimeType == "image/png" for b in images))

            texts = [b.text for b in result.content if b.type == "text"]
            framing = texts[0]
            ok &= check("framing names the transform", "system-side transformation" in framing)
            ok &= check("framing offers retrieval", "optical_retrieve" in framing)

            metadata = json.loads(texts[-1]) if texts[-1].lstrip().startswith("{") else {}
            if metadata:
                ok &= check("metadata reports a real saving",
                            metadata.get("image_tokens", 1) < metadata.get("text_tokens", 0),
                            f"{metadata.get('ratio')}x")

            match = re.search(r'digest="([0-9a-f]+)"', framing)
            ok &= check("framing carries a digest", match is not None)
            if match:
                digest = match.group(1)
                back = await session.call_tool(
                    "optical_retrieve", {"digest": digest, "start": 0, "length": 40}
                )
                payload = json.loads(back.content[0].text)
                ok &= check("retrieval returns exact text",
                            payload["text"] == PAYLOAD[:40], repr(payload["text"][:30]))

            missing = await session.call_tool("optical_retrieve", {"digest": "deadbeefdeadbeef"})
            ok &= check("unknown digest is a clean miss",
                        json.loads(missing.content[0].text)["status"] == "not_found")

            bad = await session.call_tool("optical_retrieve", {"digest": "../../etc/passwd"})
            ok &= check("path traversal is rejected", bool(bad.isError))

            small = await session.call_tool("optical_compress", {"content": "too small"})
            ok &= check("tiny payload is declined",
                        json.loads(small.content[0].text)["status"] == "declined")

            stats = await session.call_tool("optical_stats", {"preview": RISKY})
            body = json.loads(stats.content[0].text)
            ok &= check("stats report host capabilities", "automatic_hook" in body["capabilities"])
            ok &= check("stats preview flags risky content",
                        body["preview"]["guard"]["safe_for_auto"] is False,
                        ",".join(body["preview"]["guard"]["reasons"][:3]))

    print(f"\n{'SMOKE PASS' if ok else 'SMOKE FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
