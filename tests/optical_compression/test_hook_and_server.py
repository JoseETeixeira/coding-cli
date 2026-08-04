"""Hook behaviour and MCP contract gates.

The hook tests are mostly about NOT acting: it rewrites tool output that nobody
asked it to touch, so every ambiguity must resolve to standing down.

The server tests are contract gates. `structured_output=False` in particular is
load-bearing for Codex, where a present `structuredContent` silently discards
the image (openai/codex issue #10334) and the agent gets text with no error.
"""

from __future__ import annotations

import base64
import io
import json

import pytest
from PIL import Image

from optical_compression import constants, hook, server

BULK = "ordinary log narrative with nothing precision critical in it at all. "
BIG = (BULK * ((constants.HOOK_MIN_CHARS // len(BULK)) + 40))[: constants.HOOK_MIN_CHARS + 3_000]


def read_event(content: str, *, tool: str = "Read", path: str = "/tmp/big.log") -> dict:
    return {
        "tool_name": tool,
        "tool_response": {"type": "text", "file": {"filePath": path, "content": content}},
    }


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("OPTICAL_COMPRESSION_DIR", str(tmp_path / "store"))
    monkeypatch.delenv("OPTICAL_COMPRESSION_HOOK", raising=False)
    monkeypatch.delenv("OPTICAL_COMPRESSION_HOOK_TOOLS", raising=False)


# --- standing down ---------------------------------------------------------


def test_hook_ignores_other_tools():
    assert hook.evaluate(read_event(BIG, tool="Bash")) is None


def test_hook_ignores_small_payloads():
    assert hook.evaluate(read_event("short")) is None


def test_hook_ignores_unrecognised_shapes():
    assert hook.evaluate({"tool_name": "Read", "tool_response": "a bare string"}) is None
    assert hook.evaluate({"tool_name": "Read", "tool_response": {}}) is None
    assert hook.evaluate({"tool_name": "Read"}) is None


def test_hook_ignores_an_already_image_result():
    event = {
        "tool_name": "Read",
        "tool_response": {"type": "image", "file": {"content": BIG}},
    }
    assert hook.evaluate(event) is None


def test_hook_respects_the_kill_switch(monkeypatch):
    monkeypatch.setenv("OPTICAL_COMPRESSION_HOOK", "0")
    assert hook.evaluate(read_event(BIG)) is None


def test_hook_refuses_identifier_bearing_output():
    """The whole point of the guard: this content must pass through as text."""
    risky = BIG[:2000] + " sha256=30b7e9ba6b5b7642c92af44eddf7b4f6 " * 200
    assert hook.evaluate(read_event(risky)) is None


def test_hook_tool_list_is_configurable(monkeypatch):
    monkeypatch.setenv("OPTICAL_COMPRESSION_HOOK_TOOLS", "Grep")
    assert hook.evaluate(read_event(BIG)) is None
    assert hook.evaluate(read_event(BIG, tool="Grep")) is not None


# --- acting ----------------------------------------------------------------


def test_hook_replaces_a_large_clean_read():
    response = hook.evaluate(read_event(BIG))
    assert response is not None
    specific = response["hookSpecificOutput"]
    assert specific["hookEventName"] == "PostToolUse"
    assert specific["updatedToolOutput"]["type"] == "image"


def test_hook_emits_a_decodable_png():
    specific = hook.evaluate(read_event(BIG))["hookSpecificOutput"]
    payload = base64.b64decode(specific["updatedToolOutput"]["file"]["base64"])
    with Image.open(io.BytesIO(payload)) as image:
        assert image.size[0] > 0


def test_hook_reports_the_original_size():
    specific = hook.evaluate(read_event(BIG))["hookSpecificOutput"]
    assert specific["updatedToolOutput"]["file"]["originalSize"] == len(BIG)


def test_hook_carries_framing_in_additional_context():
    """The image shape has no text field, so framing travels alongside it."""
    specific = hook.evaluate(read_event(BIG))["hookSpecificOutput"]
    framing = specific["additionalContext"]
    assert "optical_retrieve" in framing
    assert "system-side transformation" in framing


def test_hook_output_is_json_serialisable():
    json.dumps(hook.evaluate(read_event(BIG)))


def test_hook_main_fails_open_on_garbage(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_hook_main_is_silent_on_empty_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("   "))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_extract_text_pulls_content_and_path():
    text, path = hook.extract_text({"type": "text", "file": {"filePath": "/a.log", "content": "x"}})
    assert (text, path) == ("x", "/a.log")


# --- server contract gates -------------------------------------------------


@pytest.mark.anyio
async def test_all_three_tools_are_registered():
    names = {tool.name for tool in await server.mcp.list_tools()}
    assert {"optical_compress", "optical_retrieve", "optical_stats"} <= names


@pytest.mark.anyio
async def test_no_tool_declares_structured_output():
    """Codex drops the image when structuredContent is present (issue #10334)."""
    for tool in await server.mcp.list_tools():
        assert getattr(tool, "outputSchema", None) in (None, {}), tool.name


@pytest.mark.anyio
async def test_descriptions_warn_about_lossiness():
    tools = {tool.name: (tool.description or "") for tool in await server.mcp.list_tools()}
    assert "LOSSY" in tools["optical_compress"]
    assert "optical_retrieve" in tools["optical_compress"]


def test_capabilities_report_the_host_asymmetry(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_SESSION", raising=False)
    assert server.host_capabilities()["automatic_hook"] is True

    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setenv("CODEX_SESSION", "1")
    capabilities = server.host_capabilities()
    assert capabilities["automatic_hook"] is False
    assert capabilities["mcp_tools"] is True
    assert "Codex" in capabilities["explanation"]


def test_fail_wraps_errors_as_json():
    error = server._fail(ValueError("bad input"))
    payload = json.loads(str(error)[str(error).index("{") :])
    assert payload["status"] == "error"


def test_fail_hides_unexpected_internals():
    error = server._fail(RuntimeError("secret internal detail"))
    assert "secret internal detail" not in str(error)


@pytest.fixture
def anyio_backend():
    return "asyncio"
