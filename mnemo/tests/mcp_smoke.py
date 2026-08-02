"""End-to-end MCP smoke test: drive the real stdio server (real OpenAI embeddings
+ real Qdrant) exactly as Claude Code / Codex would. Uses a throwaway collection.

Run:  py -3.12 mnemo/tests/mcp_smoke.py
"""

import asyncio
import json
import os
import sys
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from qdrant_client import QdrantClient

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SERVER = os.path.join(os.path.dirname(HERE), "run_server.py")


def _content_text(result):
    parts = []
    for c in result.content:
        parts.append(getattr(c, "text", str(c)))
    return "\n".join(parts)


async def main() -> int:
    collection = f"mnemo_smoke_{uuid.uuid4().hex[:8]}"
    qdrant_url = os.environ.get("MNEMO_QDRANT_URL", "http://127.0.0.1:1337")
    env = {
        **os.environ,
        "MNEMO_COLLECTION": collection,
        "MNEMO_AGENT_ID": "smoke-agent",
        "MNEMO_QDRANT_URL": qdrant_url,
    }
    params = StdioServerParameters(command="py", args=["-3.12", RUN_SERVER], env=env)

    try:
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

                status = json.loads(_content_text(await session.call_tool("memory_status", {})))
                print("STATUS ok:", status.get("ok") is True)

                w = await session.call_tool("memory_write", {
                    "text": "mnemo smoke: the shared memory substrate is Qdrant on port 1337",
                    "namespace": "smoke",
                    "type": "fact",
                    "tags": ["smoke"],
                })
                memory_id = json.loads(_content_text(w))["memory_id"]
                print("WRITE ok:", bool(memory_id))

                s = await session.call_tool("memory_search", {
                    "query": "what port is the shared memory vector db on",
                    "namespace": "smoke",
                })
                search_payload = json.loads(_content_text(s))
                assert any(
                    item["memory_id"] == memory_id for item in search_payload["results"]
                ), "search did not return the written memory"
                print("SEARCH ok:", True)

                tc = await session.call_tool("task_context", {
                    "task": "set up shared memory", "query": "vector db port", "namespace": "smoke",
                })
                tc_payload = json.loads(_content_text(tc))
                print("TASK_CONTEXT ok:", tc_payload["contract_version"] == 2)

                exact = await session.call_tool("memory_get", {"memory_id": memory_id})
                exact_payload = json.loads(_content_text(exact))
                assert "1337" in exact_payload["text"], "memory_get did not return the exact authorized item"
                print("GET ok:", True)

                forgotten = await session.call_tool(
                    "memory_forget",
                    {"memory_id": memory_id, "reason": "stdio smoke cleanup"},
                )
                assert json.loads(_content_text(forgotten))["ok"] is True
                after = json.loads(
                    _content_text(
                        await session.call_tool(
                            "memory_search",
                            {"query": "shared memory vector db", "namespace": "smoke"},
                        )
                    )
                )
                assert all(
                    item["memory_id"] != memory_id for item in after["results"]
                ), "forgotten memory remained searchable"
                print("FORGET ok:", True)
    finally:
        try:
            QdrantClient(url=qdrant_url).delete_collection(collection)
        except Exception:
            pass

    print("\nMCP SMOKE: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except AssertionError as e:
        print("MCP SMOKE: FAIL —", e)
        sys.exit(1)
