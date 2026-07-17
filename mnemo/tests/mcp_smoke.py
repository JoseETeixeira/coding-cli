"""End-to-end MCP smoke test: drive the real stdio server (real OpenAI embeddings
+ real Qdrant) exactly as Claude Code / Codex would. Uses a throwaway collection.

Run:  py -3.12 mnemo/tests/mcp_smoke.py
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SERVER = os.path.join(os.path.dirname(HERE), "run_server.py")


def _content_text(result):
    parts = []
    for c in result.content:
        parts.append(getattr(c, "text", str(c)))
    return "\n".join(parts)


async def main() -> int:
    env = {
        **os.environ,
        "MNEMO_COLLECTION": "mnemo_smoke",
        "MNEMO_AGENT_ID": "smoke-agent",
        "MNEMO_QDRANT_URL": os.environ.get("MNEMO_QDRANT_URL", "http://127.0.0.1:1337"),
    }
    params = StdioServerParameters(command="py", args=["-3.12", RUN_SERVER], env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("TOOLS:", names)
            expected = {
                "memory_status", "memory_write", "memory_search", "task_context",
                "memory_get", "memory_list", "memory_forget", "memory_stats",
            }
            assert expected.issubset(set(names)), f"missing tools: {expected - set(names)}"

            status = await session.call_tool("memory_status", {})
            print("STATUS:", _content_text(status)[:200])

            w = await session.call_tool("memory_write", {
                "text": "mnemo smoke: the shared memory substrate is Qdrant on port 1337",
                "namespace": "smoke",
                "type": "fact",
                "tags": ["smoke"],
            })
            wtext = _content_text(w)
            print("WRITE:", wtext[:200])

            s = await session.call_tool("memory_search", {
                "query": "what port is the shared memory vector db on",
                "namespace": "smoke",
            })
            stext = _content_text(s)
            print("SEARCH:", stext[:300])
            assert "1337" in stext, "search did not return the written memory"

            tc = await session.call_tool("task_context", {
                "task": "set up shared memory", "query": "vector db port", "namespace": "smoke",
            })
            print("TASK_CONTEXT ok:", "1337" in _content_text(tc))

    print("\nMCP SMOKE: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except AssertionError as e:
        print("MCP SMOKE: FAIL —", e)
        sys.exit(1)
