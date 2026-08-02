"""`gpt_image_2.server`: the MCP edge.

Traces IMG-AC-002 (the advertised tool surface) and IMG-AC-007 (bounded,
useful results), plus the failure contract IMG-AC-008 depends on.

Two seams are replaced and nothing else:

* `server.credentials.resolve_api_key` — so no real key is read, and so a test
  can prove the credential is *not* touched on a locally-rejected request.
* `server.api.call_generate` / `call_edit` — replaced by a thin wrapper that
  still runs the *real* retry/response-reading code from `api`, but hands it
  the conftest `FakeClientFactory`. The autouse network guard therefore stays
  armed: nothing here can construct `openai.AsyncOpenAI`.

Every coroutine is driven with `asyncio.run` because this repo configures no
pytest-asyncio plugin.
"""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.types import Image

from gpt_image_2 import api, constants, errors, images, server

from conftest import (  # noqa: E402 - pytest puts this directory on sys.path
    FakeClientFactory,
    FakeOpenAI,
    FakeParsedResponse,
    FakeRawResponse,
    FakeUsage,
    b64_image,
)

# ---------------------------------------------------------------------------
# The arguments that must never appear, on either tool
# ---------------------------------------------------------------------------

#: Each name is the enforcement of a requirement, not a style preference:
#: `model` (IMG-REQ-002), `api_key` (IMG-REQ-005), `headers` / `endpoint` /
#: `url` / `file_id` (IMG-REQ-002), `overwrite` (IMG-REQ-006), and
#: `input_fidelity` (the API forbids changing it for this model).
FORBIDDEN_ARGS: frozenset[str] = frozenset(
    {
        "model",
        "api_key",
        "headers",
        "endpoint",
        "url",
        "file_id",
        "overwrite",
        "input_fidelity",
    }
)

TOOL_NAMES = ("generate_image", "edit_image")


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class _CredentialSpy:
    """Stands in for `resolve_api_key` and counts how often it was reached."""

    def __init__(self, secret: Any) -> None:
        self._secret = secret
        self.calls = 0

    def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        return self._secret


@dataclass
class Harness:
    client: FakeOpenAI
    factory: FakeClientFactory
    creds: _CredentialSpy
    requests: list[Any] = field(default_factory=list)
    delays: list[float] = field(default_factory=list)

    def script(self, *entries: Any) -> None:
        self.client.script = list(entries)
        self.client._index = 0

    @property
    def recorded(self) -> dict[str, Any]:
        return self.client.last_kwargs


@pytest.fixture
def harness(
    monkeypatch: pytest.MonkeyPatch,
    fake_factory: FakeClientFactory,
    secret: Any,
    no_jitter: Any,
) -> Harness:
    spy = _CredentialSpy(secret)
    bundle = Harness(client=fake_factory.client, factory=fake_factory, creds=spy)

    # Capture the originals *before* patching, or the wrappers recurse.
    real_generate = api.call_generate
    real_edit = api.call_edit

    async def _sleep(seconds: float) -> None:
        bundle.delays.append(seconds)

    async def fake_generate(request: Any, *, secret: Any, budget: Any, **_: Any) -> Any:
        bundle.requests.append(request)
        return await real_generate(
            request,
            secret=secret,
            budget=budget,
            client_factory=fake_factory,
            sleep=_sleep,
            jitter=no_jitter,
        )

    async def fake_edit(request: Any, *, secret: Any, budget: Any, **_: Any) -> Any:
        bundle.requests.append(request)
        return await real_edit(
            request,
            secret=secret,
            budget=budget,
            client_factory=fake_factory,
            sleep=_sleep,
            jitter=no_jitter,
        )

    monkeypatch.setattr(server.credentials, "resolve_api_key", spy)
    monkeypatch.setattr(server.api, "call_generate", fake_generate)
    monkeypatch.setattr(server.api, "call_edit", fake_edit)
    return bundle


def raw(
    payloads: list[str],
    *,
    usage: FakeUsage | None = None,
    revised_prompt: str | None = None,
    headers: dict[str, str] | None = None,
) -> FakeRawResponse:
    return FakeRawResponse(
        FakeParsedResponse(payloads, usage=usage, revised_prompt=revised_prompt),
        headers=headers,
    )


def generate(**kwargs: Any) -> list:
    return asyncio.run(server.generate_image(**kwargs))


def edit(**kwargs: Any) -> list:
    return asyncio.run(server.edit_image(**kwargs))


def metadata_of(result: list) -> dict[str, Any]:
    payload = result[-1]
    assert isinstance(payload, dict), "the last element must be the metadata mapping"
    return payload


def image_blocks(result: list) -> list[Image]:
    return [block for block in result if isinstance(block, Image)]


def error_payload(exc: BaseException) -> dict[str, Any]:
    """A tool failure is a `ToolError` whose message is our JSON contract."""
    assert isinstance(exc, ToolError)
    return json.loads(str(exc))


def files_in(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(entry.name for entry in directory.iterdir())


#: Captured once, at import, before any test can patch the module attribute.
_REAL_PUBLISH_ATOMIC = images.publish_atomic


@dataclass
class FlakyPublisher:
    """A `publish_atomic` that fails on chosen call numbers and really writes otherwise.

    The successful calls delegate to the genuine primitive, so the surviving
    files are real files with real collision-suffixed names — which is the only
    way to prove the failure did not orphan them.
    """

    fail_on: frozenset[int]
    error: Callable[[], BaseException]
    calls: int = 0

    def __call__(
        self, data: bytes, dest_dir: Path, basename: str, extension: str
    ) -> Path:
        current = self.calls
        self.calls += 1
        if current in self.fail_on:
            raise self.error()
        return _REAL_PUBLISH_ATOMIC(data, dest_dir, basename, extension)


def three_distinct_payloads() -> list[str]:
    return [
        b64_image(color=(200, 30, 30)),
        b64_image(color=(30, 200, 30)),
        b64_image(color=(30, 30, 200)),
    ]


# ===========================================================================
# IMG-AC-002 — the advertised tool surface
# ===========================================================================


@pytest.fixture(scope="module")
def listed_tools() -> dict[str, Any]:
    tools = asyncio.run(server.mcp.list_tools())
    return {tool.name: tool for tool in tools}


def test_exposes_exactly_the_two_approved_tools(listed_tools: dict[str, Any]) -> None:
    assert set(listed_tools) == set(TOOL_NAMES)
    assert len(listed_tools) == 2


@pytest.mark.parametrize(
    ("tool_name", "required"),
    [
        ("generate_image", {"prompt"}),
        ("edit_image", {"prompt", "image_paths"}),
    ],
)
def test_required_arguments(
    listed_tools: dict[str, Any], tool_name: str, required: set[str]
) -> None:
    schema = listed_tools[tool_name].inputSchema
    assert set(schema.get("required", [])) == required


@pytest.mark.parametrize(
    ("tool_name", "has_moderation"),
    [
        # `POST /v1/images/edits` has no `moderation` parameter, so advertising
        # one on edit_image would be a lie the caller pays for.
        ("generate_image", True),
        ("edit_image", False),
    ],
)
def test_moderation_is_generate_only(
    listed_tools: dict[str, Any], tool_name: str, has_moderation: bool
) -> None:
    properties = listed_tools[tool_name].inputSchema["properties"]
    assert ("moderation" in properties) is has_moderation


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_no_forbidden_argument_is_exposed(
    listed_tools: dict[str, Any], tool_name: str
) -> None:
    properties = set(listed_tools[tool_name].inputSchema["properties"])
    assert FORBIDDEN_ARGS & properties == set()


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
@pytest.mark.parametrize(
    ("hint", "expected"),
    [
        ("readOnlyHint", False),
        ("destructiveHint", False),
        ("idempotentHint", False),
        ("openWorldHint", True),
    ],
)
def test_annotations_are_truthful(
    listed_tools: dict[str, Any], tool_name: str, hint: str, expected: bool
) -> None:
    annotations = listed_tools[tool_name].annotations
    assert annotations is not None
    assert getattr(annotations, hint) is expected


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_description_discloses_cost_and_disk_writes(
    listed_tools: dict[str, Any], tool_name: str
) -> None:
    description = (listed_tools[tool_name].description or "").lower()
    assert "costs money" in description
    assert "writes image files to disk" in description
    assert "never overwrites" in description


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_output_controls_are_offered_on_both_tools(
    listed_tools: dict[str, Any], tool_name: str
) -> None:
    properties = set(listed_tools[tool_name].inputSchema["properties"])
    assert {"output_dir", "basename", "output_format", "n", "size", "quality"} <= properties


# ===========================================================================
# End to end with fakes — the success contract
# ===========================================================================


def test_generate_returns_preview_then_metadata(
    harness: Harness, out_dir: Path
) -> None:
    payload = b64_image()
    harness.script(raw([payload]))

    result = generate(prompt="a small red square", output_dir=str(out_dir))

    blocks = image_blocks(result)
    assert len(blocks) == 1
    assert result[0] is blocks[0]

    content = blocks[0].to_image_content()
    assert content.mimeType == constants.MIME_BY_FORMAT["png"]
    assert base64.b64decode(content.data) == base64.b64decode(payload)

    meta = metadata_of(result)
    assert meta["operation"] == "generate"
    assert meta["model"] == constants.MODEL
    assert meta["model"] == "gpt-image-2"
    assert meta["status"] == "ok"
    assert meta["failed_images"] == []

    image = meta["images"][0]
    assert image["index"] == 0
    assert image["format"] == "png"
    assert image["mime_type"] == "image/png"
    assert image["bytes"] == len(base64.b64decode(payload))
    assert (image["width"], image["height"]) == (64, 64)
    written = Path(image["path"])
    assert written.is_file()
    assert written.parent == out_dir
    assert written.read_bytes() == base64.b64decode(payload)


def test_generate_metadata_echoes_the_requested_controls(
    harness: Harness, out_dir: Path
) -> None:
    harness.script(raw([b64_image(fmt="jpeg")]))

    result = generate(
        prompt="a small red square",
        size="1024x1024",
        quality="low",
        output_format="jpeg",
        n=1,
        background="opaque",
        moderation="low",
        output_compression=80,
        output_dir=str(out_dir),
    )

    requested = metadata_of(result)["requested"]
    assert requested == {
        "size": "1024x1024",
        "quality": "low",
        "output_format": "jpeg",
        "n": 1,
        "background": "opaque",
        "output_compression": 80,
        "moderation": "low",
    }


def test_generate_metadata_defaults_are_the_documented_ones(
    harness: Harness, out_dir: Path
) -> None:
    harness.script(raw([b64_image()]))

    result = generate(prompt="a small red square", output_dir=str(out_dir))

    assert metadata_of(result)["requested"] == {
        "size": constants.DEFAULT_SIZE,
        "quality": constants.DEFAULT_QUALITY,
        "output_format": constants.DEFAULT_OUTPUT_FORMAT,
        "n": constants.DEFAULT_N,
        "background": constants.DEFAULT_BACKGROUND,
        "moderation": constants.DEFAULT_MODERATION,
    }


def test_generate_reports_attempts_and_a_sane_duration(
    harness: Harness, out_dir: Path
) -> None:
    harness.script(raw([b64_image()]))

    meta = metadata_of(generate(prompt="a square", output_dir=str(out_dir)))

    assert meta["attempts"] == 1
    assert isinstance(meta["duration_ms"], int)
    assert not isinstance(meta["duration_ms"], bool)
    assert meta["duration_ms"] >= 0
    assert meta["duration_ms"] < constants.OPERATION_DEADLINE_S * 1000


def test_generate_sends_the_fixed_model_and_no_escape_hatches(
    harness: Harness, out_dir: Path
) -> None:
    harness.script(raw([b64_image()]))

    generate(
        prompt="a small red square",
        quality="medium",
        background="opaque",
        moderation="low",
        output_dir=str(out_dir),
    )

    assert harness.client.call_count == 1
    assert harness.client.calls[0].operation == "generate"
    sent = harness.recorded
    assert sent["model"] == "gpt-image-2"
    assert sent["prompt"] == "a small red square"
    assert sent["quality"] == "medium"
    assert sent["background"] == "opaque"
    assert sent["moderation"] == "low"
    assert sent["n"] == constants.DEFAULT_N
    assert sent["size"] == constants.DEFAULT_SIZE
    assert sent["output_format"] == constants.DEFAULT_OUTPUT_FORMAT
    # The forbidden surface must not reappear on the wire either.
    assert (FORBIDDEN_ARGS - {"model"}) & set(sent) == set()
    assert harness.creds.calls == 1


# ---------------------------------------------------------------------------
# Pass-through: present when supplied, None when the provider omitted it
# ---------------------------------------------------------------------------


def test_provider_fields_are_passed_through(harness: Harness, out_dir: Path) -> None:
    harness.script(
        raw(
            [b64_image()],
            usage=FakeUsage(input_tokens=11, output_tokens=22),
            revised_prompt="a small crimson square, studio lit",
            headers={"x-request-id": "req_passthrough_42"},
        )
    )

    meta = metadata_of(generate(prompt="a square", output_dir=str(out_dir)))

    assert meta["request_id"] == "req_passthrough_42"
    assert meta["usage"] == {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33}
    assert meta["revised_prompt"] == "a small crimson square, studio lit"


def test_absent_provider_fields_are_none_never_invented(
    harness: Harness, out_dir: Path
) -> None:
    harness.script(
        raw(
            [b64_image()],
            usage=None,
            revised_prompt=None,
            # A header map without x-request-id: the provider said nothing.
            headers={"content-type": "application/json"},
        )
    )

    meta = metadata_of(generate(prompt="a square", output_dir=str(out_dir)))

    assert meta["request_id"] is None
    assert meta["usage"] is None
    assert meta["revised_prompt"] is None


# ===========================================================================
# IMG-AC-007 — bounded inline previews
# ===========================================================================


def test_single_small_image_is_previewed_inline(
    harness: Harness, out_dir: Path
) -> None:
    harness.script(raw([b64_image()]))

    result = generate(prompt="a square", output_dir=str(out_dir))

    assert len(image_blocks(result)) == 1
    assert metadata_of(result)["preview"] == {"included": True, "reason": None}


def test_oversized_image_is_not_inlined_but_the_path_survives(
    harness: Harness, out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b64_image()
    decoded_size = len(base64.b64decode(payload))
    # Move the ceiling instead of manufacturing 5 MiB of pixels: the policy is
    # "decoded bytes above the cap", and the cap is the thing under test.
    monkeypatch.setattr(constants, "MAX_INLINE_PREVIEW_BYTES", decoded_size - 1)
    harness.script(raw([payload]))

    result = generate(prompt="a square", output_dir=str(out_dir))

    assert image_blocks(result) == []
    meta = metadata_of(result)
    assert meta["preview"] == {"included": False, "reason": "too_large"}
    assert len(meta["images"]) == 1
    assert Path(meta["images"][0]["path"]).is_file()
    assert meta["images"][0]["bytes"] == decoded_size


def test_three_images_inline_only_the_first(harness: Harness, out_dir: Path) -> None:
    payloads = [
        b64_image(color=(200, 30, 30)),
        b64_image(color=(30, 200, 30)),
        b64_image(color=(30, 30, 200)),
    ]
    harness.script(raw(payloads))

    result = generate(prompt="three squares", n=3, output_dir=str(out_dir))

    blocks = image_blocks(result)
    assert len(blocks) == 1
    assert base64.b64decode(blocks[0].to_image_content().data) == base64.b64decode(
        payloads[0]
    )

    meta = metadata_of(result)
    assert meta["preview"] == {"included": True, "reason": "first_of_n"}
    assert [entry["index"] for entry in meta["images"]] == [0, 1, 2]

    paths = [Path(entry["path"]) for entry in meta["images"]]
    assert len({str(p) for p in paths}) == 3
    assert all(p.is_file() for p in paths)
    # Collision suffixes start at 2 and never overwrite (IMG-REQ-006).
    assert [p.name for p in paths] == ["image.png", "image-2.png", "image-3.png"]
    assert files_in(out_dir) == ["image-2.png", "image-3.png", "image.png"]


@pytest.mark.parametrize(
    ("count", "expected_reason"),
    [
        (1, None),
        (2, "first_of_n"),
        (4, "first_of_n"),
    ],
)
def test_preview_reason_matrix(
    harness: Harness, out_dir: Path, count: int, expected_reason: str | None
) -> None:
    harness.script(raw([b64_image() for _ in range(count)]))

    result = generate(prompt="squares", n=count, output_dir=str(out_dir))

    assert metadata_of(result)["preview"] == {
        "included": True,
        "reason": expected_reason,
    }
    assert len(image_blocks(result)) == constants.MAX_INLINE_PREVIEWS
    assert len(metadata_of(result)["images"]) == count


# ===========================================================================
# Partial failure: the valid images still land
# ===========================================================================


def test_one_bad_payload_does_not_lose_the_good_ones(
    harness: Harness, out_dir: Path
) -> None:
    good_first = b64_image(color=(200, 30, 30))
    good_third = b64_image(color=(30, 30, 200))
    harness.script(raw([good_first, "@@@ not base64 @@@", good_third]))

    result = generate(prompt="three squares", n=3, output_dir=str(out_dir))

    meta = metadata_of(result)
    assert meta["status"] == "ok"
    assert [entry["index"] for entry in meta["images"]] == [0, 2]
    assert [failure["index"] for failure in meta["failed_images"]] == [1]
    assert meta["failed_images"][0]["code"] == errors.OUTPUT_ERROR

    written = [Path(entry["path"]) for entry in meta["images"]]
    assert all(path.is_file() for path in written)
    assert written[0].read_bytes() == base64.b64decode(good_first)
    assert written[1].read_bytes() == base64.b64decode(good_third)
    # Exactly two files: no invalid partial, no leftover `.part`.
    assert files_in(out_dir) == ["image-2.png", "image.png"]


def test_every_payload_invalid_fails_the_call(harness: Harness, out_dir: Path) -> None:
    harness.script(raw(["@@@ not base64 @@@", "### also not ###"]))

    with pytest.raises(ToolError) as excinfo:
        generate(prompt="three squares", n=2, output_dir=str(out_dir))

    payload = error_payload(excinfo.value)
    assert payload["status"] == "error"
    assert payload["code"] == errors.OUTPUT_ERROR
    assert files_in(out_dir) == []


# ===========================================================================
# Failure shape
# ===========================================================================


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    [
        pytest.param({"prompt": "   "}, errors.INVALID_REQUEST, id="blank-prompt"),
        pytest.param({"prompt": ""}, errors.INVALID_REQUEST, id="empty-prompt"),
        pytest.param(
            {"prompt": "x" * (constants.MAX_PROMPT_CHARS + 1)},
            errors.INVALID_REQUEST,
            id="prompt-too-long",
        ),
        pytest.param(
            {"prompt": "ok", "size": "1000x1000"},
            errors.INVALID_REQUEST,
            id="size-not-multiple-of-16",
        ),
        pytest.param(
            {"prompt": "ok", "quality": "ultra"},
            errors.INVALID_REQUEST,
            id="unknown-quality",
        ),
        pytest.param({"prompt": "ok", "n": 0}, errors.INVALID_REQUEST, id="n-below-range"),
        pytest.param(
            {"prompt": "ok", "output_compression": 50},
            errors.INVALID_REQUEST,
            id="png-with-compression",
        ),
        pytest.param(
            {"prompt": "ok", "background": "transparent"},
            errors.UNSUPPORTED_OPTION,
            id="transparent-background",
        ),
    ],
)
def test_local_rejections_are_json_tool_errors(
    harness: Harness, out_dir: Path, kwargs: dict[str, Any], expected_code: str
) -> None:
    with pytest.raises(ToolError) as excinfo:
        generate(output_dir=str(out_dir), **kwargs)

    payload = error_payload(excinfo.value)
    assert payload["status"] == "error"
    assert payload["code"] == expected_code
    assert payload["code"] in errors.ERROR_CODES
    assert isinstance(payload["message"], str) and payload["message"]

    # Nothing was paid for and no credential was read.
    assert harness.creds.calls == 0
    assert harness.client.call_count == 0
    assert files_in(out_dir) == []


def test_tool_error_message_is_parseable_json(harness: Harness, out_dir: Path) -> None:
    with pytest.raises(ToolError) as excinfo:
        generate(prompt="   ", output_dir=str(out_dir))

    payload = json.loads(str(excinfo.value))
    assert set(payload) >= {"status", "code", "message"}
    assert payload["code"] == errors.INVALID_REQUEST


def test_protocol_edge_failure_carries_our_payload_behind_fastmcp_prefix(
    harness: Harness, out_dir: Path
) -> None:
    """The same contract, observed the way a real MCP host observes it.

    `mcp.server.fastmcp.tools.base.Tool.run` catches EVERY exception, ours
    included, and re-raises `ToolError(f"Error executing tool {name}: {e}")`.
    That prefix is FastMCP's and we cannot remove it without bypassing the
    framework, so this test pins the contract that actually ships: the message
    carries the prefix, and our payload is the JSON object starting at the
    first `{`.

    This is not an accepted defect being waved through — it is the real,
    stable delivered shape, and pinning it means a future FastMCP change that
    breaks payload extraction fails here instead of silently reaching agents.
    """
    with pytest.raises(ToolError) as excinfo:
        asyncio.run(
            server.mcp.call_tool(
                "generate_image", {"prompt": "   ", "output_dir": str(out_dir)}
            )
        )

    delivered = str(excinfo.value)
    assert delivered.startswith("Error executing tool generate_image: ")

    payload = json.loads(delivered[delivered.index("{") :])
    assert payload["status"] == "error"
    assert payload["code"] == errors.INVALID_REQUEST
    assert set(payload) >= {"status", "code", "message"}


def test_protocol_edge_success_survives_content_conversion(
    harness: Harness, out_dir: Path
) -> None:
    """The happy path *does* survive FastMCP's conversion, so the bug is scoped."""
    harness.script(raw([b64_image()]))

    blocks = asyncio.run(
        server.mcp.call_tool(
            "generate_image", {"prompt": "a square", "output_dir": str(out_dir)}
        )
    )
    if isinstance(blocks, tuple):  # pragma: no cover - shape differs by mcp version
        blocks = blocks[0]

    kinds = [block.type for block in blocks]
    assert kinds == ["image", "text"]
    meta = json.loads(blocks[-1].text)
    assert meta["model"] == "gpt-image-2"
    assert Path(meta["images"][0]["path"]).is_file()


# ===========================================================================
# edit_image
# ===========================================================================


def test_edit_metadata_carries_references_and_mask_used(
    harness: Harness, out_dir: Path, reference_png: Path, mask_png: Path
) -> None:
    harness.script(raw([b64_image()]))

    result = edit(
        prompt="repaint the sky",
        image_paths=[str(reference_png)],
        mask_path=str(mask_png),
        output_dir=str(out_dir),
    )

    meta = metadata_of(result)
    assert meta["operation"] == "edit"
    assert meta["model"] == "gpt-image-2"
    assert meta["status"] == "ok"
    assert meta["references"] == 1
    assert meta["mask_used"] is True
    assert Path(meta["images"][0]["path"]).is_file()
    # The edit endpoint has no `moderation`, so the echo must not invent one.
    assert "moderation" not in meta["requested"]
    assert meta["preview"] == {"included": True, "reason": None}


def test_edit_without_a_mask_reports_mask_used_false(
    harness: Harness, out_dir: Path, reference_png: Path
) -> None:
    harness.script(raw([b64_image()]))

    meta = metadata_of(
        edit(
            prompt="repaint the sky",
            image_paths=[str(reference_png)],
            output_dir=str(out_dir),
        )
    )

    assert meta["mask_used"] is False
    assert meta["references"] == 1


def test_edit_sends_ordered_references_and_omits_forbidden_fields(
    harness: Harness, out_dir: Path, reference_png: Path, mask_png: Path
) -> None:
    harness.script(raw([b64_image()]))

    edit(
        prompt="repaint the sky",
        image_paths=[str(reference_png)],
        mask_path=str(mask_png),
        output_dir=str(out_dir),
    )

    assert harness.client.calls[0].operation == "edit"
    sent = harness.recorded
    assert sent["model"] == "gpt-image-2"
    assert [item[0] for item in sent["image"]] == [reference_png.name]
    assert sent["mask"][0] == mask_png.name
    assert "moderation" not in sent
    assert (FORBIDDEN_ARGS - {"model"}) & set(sent) == set()
    for omitted in constants.OMITTED_EDIT_PARAMS:
        assert omitted not in sent


def test_edit_rejects_a_missing_reference_before_any_spend(
    harness: Harness, out_dir: Path, tmp_path: Path
) -> None:
    with pytest.raises(ToolError) as excinfo:
        edit(
            prompt="repaint the sky",
            image_paths=[str(tmp_path / "nope.png")],
            output_dir=str(out_dir),
        )

    payload = error_payload(excinfo.value)
    assert payload["code"] == errors.INVALID_INPUT_FILE
    assert harness.creds.calls == 0
    assert harness.client.call_count == 0


# ===========================================================================
# Publication failure part-way through a multi-image response
#
# Every payload here is valid and every image has already been paid for. The
# only thing that fails is the write. `_publish_all` guards each
# `publish_atomic` call individually for exactly this reason (IMG-REQ-006,
# IMG-REQ-007): report what landed rather than abandoning it.
# ===========================================================================


def test_disk_failure_on_the_second_image_keeps_the_other_two(
    harness: Harness, out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MUTATION CAUGHT: reverting `_publish_all` to an unguarded publish loop.

    Unguarded, the `OSError` from image 2 escapes the loop and the tool's
    `except Exception` turns it into `internal_error` — so the call raises
    instead of returning, image 1 is orphaned on disk with nothing naming it,
    and image 3 is never even attempted. Three separate assertions below fail
    under that revert: the call raising at all, `publisher.calls == 3`, and the
    two real paths in `metadata["images"]`.
    """
    payloads = three_distinct_payloads()
    harness.script(raw(payloads))
    publisher = FlakyPublisher(
        fail_on=frozenset({1}), error=lambda: OSError("disk full")
    )
    monkeypatch.setattr(server.images, "publish_atomic", publisher)

    result = generate(prompt="three squares", n=3, output_dir=str(out_dir))

    meta = metadata_of(result)
    assert meta["status"] == "ok"
    # The third image was still attempted: the loop continued past the failure.
    assert publisher.calls == 3

    # The two that landed are named, with their real on-disk paths.
    assert [entry["index"] for entry in meta["images"]] == [0, 2]
    written = [Path(entry["path"]) for entry in meta["images"]]
    assert [path.name for path in written] == ["image.png", "image-2.png"]
    assert all(path.is_file() for path in written)
    assert written[0].read_bytes() == base64.b64decode(payloads[0])
    assert written[1].read_bytes() == base64.b64decode(payloads[2])
    # Exactly the two survivors; no orphan, no leftover `.part`.
    assert files_in(out_dir) == ["image-2.png", "image.png"]

    # The one that did not land is named too, under the output_error code.
    assert [failure["index"] for failure in meta["failed_images"]] == [1]
    failure = meta["failed_images"][0]
    assert failure["code"] == errors.OUTPUT_ERROR
    assert failure["code"] in errors.ERROR_CODES
    # The OSError's own text is a filesystem detail, not ours to relay.
    assert "disk full" not in failure["message"]
    assert "OSError" in failure["message"]

    # A partial publish is not a clean success.
    assert meta["provider_returned"] == 3
    assert meta["complete"] is False


def test_image_tool_error_from_publish_keeps_the_other_two(
    harness: Harness, out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MUTATION CAUGHT: dropping the `except errors.ImageToolError` arm of the
    per-image publish guard (the arm that catches the *mapped* failure
    `publish_atomic` normally raises). Without it the tool aborts and the two
    written files are orphaned.
    """
    payloads = three_distinct_payloads()
    harness.script(raw(payloads))
    publisher = FlakyPublisher(
        fail_on=frozenset({1}),
        error=lambda: errors.output_error("Output directory is full.", index=1),
    )
    monkeypatch.setattr(server.images, "publish_atomic", publisher)

    meta = metadata_of(generate(prompt="three squares", n=3, output_dir=str(out_dir)))

    assert meta["status"] == "ok"
    assert publisher.calls == 3
    assert [entry["index"] for entry in meta["images"]] == [0, 2]
    assert files_in(out_dir) == ["image-2.png", "image.png"]
    assert [failure["index"] for failure in meta["failed_images"]] == [1]
    assert meta["failed_images"][0]["code"] == errors.OUTPUT_ERROR
    assert meta["failed_images"][0]["message"] == "Output directory is full."
    assert meta["complete"] is False


def test_publish_failing_for_every_image_raises_output_error(
    harness: Harness, out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MUTATION CAUGHT: deleting the `if not published` re-raise, which would
    return `"status": "ok"` with an empty `images` list — a success payload
    with no image anywhere.

    It also pins the code: an unguarded loop lets the raw `OSError` reach the
    tool handler and surface as `internal_error`, not `output_error`.
    """
    harness.script(raw(three_distinct_payloads()))
    publisher = FlakyPublisher(
        fail_on=frozenset({0, 1, 2}), error=lambda: OSError("disk full")
    )
    monkeypatch.setattr(server.images, "publish_atomic", publisher)

    with pytest.raises(ToolError) as excinfo:
        generate(prompt="three squares", n=3, output_dir=str(out_dir))

    payload = error_payload(excinfo.value)
    assert payload["status"] == "error"
    assert payload["code"] == errors.OUTPUT_ERROR
    assert payload["code"] in errors.ERROR_CODES
    # The failure names the first image that could not be written.
    assert payload["details"]["image_index"] == 0
    assert "disk full" not in payload["message"]
    # Every image was attempted, and nothing survived.
    assert publisher.calls == 3
    assert files_in(out_dir) == []


# ===========================================================================
# The caller's basename actually reaches the disk
# ===========================================================================


def test_generate_writes_the_caller_basename(harness: Harness, out_dir: Path) -> None:
    """MUTATION CAUGHT: passing `constants.DEFAULT_BASENAME` instead of
    `request.basename` at the `generate_image` publish call site. That mutation
    silently ignores the caller's name and writes `image.png`; nothing else in
    this suite notices.
    """
    harness.script(raw([b64_image()]))

    result = generate(
        prompt="a hero shot", basename="hero-shot", output_dir=str(out_dir)
    )

    meta = metadata_of(result)
    written = Path(meta["images"][0]["path"])
    assert written.name == "hero-shot.png"
    assert written.is_file()
    assert meta["images"][0]["path"].endswith("hero-shot.png")
    assert files_in(out_dir) == ["hero-shot.png"]


def test_edit_writes_the_caller_basename(
    harness: Harness, out_dir: Path, reference_png: Path
) -> None:
    """MUTATION CAUGHT: the same substitution at the `edit_image` call site.
    Both sites are pinned because they are independent lines.
    """
    harness.script(raw([b64_image()]))

    result = edit(
        prompt="repaint the sky",
        image_paths=[str(reference_png)],
        basename="hero-shot",
        output_dir=str(out_dir),
    )

    meta = metadata_of(result)
    written = Path(meta["images"][0]["path"])
    assert written.name == "hero-shot.png"
    assert written.is_file()
    assert meta["images"][0]["path"].endswith("hero-shot.png")
    assert files_in(out_dir) == ["hero-shot.png"]


def test_caller_basename_reaches_disk_for_every_image_of_a_multi_response(
    harness: Harness, out_dir: Path
) -> None:
    """The collision suffix is built from the caller's name, not the default."""
    harness.script(raw(three_distinct_payloads()))

    meta = metadata_of(
        generate(
            prompt="three hero shots",
            n=3,
            basename="hero-shot",
            output_dir=str(out_dir),
        )
    )

    assert [Path(entry["path"]).name for entry in meta["images"]] == [
        "hero-shot.png",
        "hero-shot-2.png",
        "hero-shot-3.png",
    ]
    assert files_in(out_dir) == [
        "hero-shot-2.png",
        "hero-shot-3.png",
        "hero-shot.png",
    ]


@pytest.mark.parametrize(
    "hostile",
    [
        pytest.param("../../pwned", id="posix-traversal"),
        pytest.param("..\\..\\pwned", id="windows-traversal"),
        pytest.param("/etc/pwned", id="absolute-posix"),
        pytest.param("subdir/pwned", id="subdirectory"),
    ],
)
def test_traversal_shaped_basename_stays_inside_the_output_dir(
    harness: Harness, out_dir: Path, tmp_path: Path, hostile: str
) -> None:
    """MUTATION CAUGHT: forwarding the caller's basename to `publish_atomic`
    without `sanitize_basename` in the path — which the previous test now
    demands actually happens, so containment has to be pinned right beside it.

    Driven through the SERVER, not `sanitize_basename` directly: the guarantee
    is about the file that ends up on disk.
    """
    harness.script(raw([b64_image()]))

    result = generate(prompt="a square", basename=hostile, output_dir=str(out_dir))

    written = Path(metadata_of(result)["images"][0]["path"])
    assert written.name == "pwned.png"
    assert written.is_file()
    assert written.parent.resolve() == out_dir.resolve()
    assert files_in(out_dir) == ["pwned.png"]
    # Nothing was created anywhere above the output directory.
    assert not (tmp_path / "pwned.png").exists()
    assert not (tmp_path / "subdir").exists()
    assert not (out_dir / "subdir").exists()


# ===========================================================================
# A short provider response is not a clean success
# ===========================================================================


def test_short_provider_response_is_reported_not_hidden(
    harness: Harness, out_dir: Path
) -> None:
    """MUTATION CAUGHT: removing `provider_returned` / `complete` from the
    metadata, or hardcoding `complete` to True.

    n=3 was asked for and paid for; one image came back. Before the shortfall
    signal existed this looked identical to a clean success: `"status": "ok"`,
    `"failed_images": []`, and a single path, with no field an agent could
    check to notice it had been shorted.
    """
    harness.script(raw([b64_image()]))

    meta = metadata_of(generate(prompt="three squares", n=3, output_dir=str(out_dir)))

    assert meta["requested"]["n"] == 3
    assert meta["provider_returned"] == 1
    assert meta["complete"] is False
    # The shortfall is not a per-image failure, so the old fields cannot carry it.
    assert meta["status"] == "ok"
    assert meta["failed_images"] == []
    assert len(meta["images"]) == 1
    assert Path(meta["images"][0]["path"]).is_file()


def test_a_full_single_image_response_reports_complete(
    harness: Harness, out_dir: Path
) -> None:
    """The other half of the signal: `complete` must be able to be True, or the
    field is a constant and tells an agent nothing.
    """
    harness.script(raw([b64_image()]))

    meta = metadata_of(generate(prompt="a square", output_dir=str(out_dir)))

    assert meta["requested"]["n"] == 1
    assert meta["provider_returned"] == 1
    assert meta["complete"] is True


def test_a_full_multi_image_response_reports_complete(
    harness: Harness, out_dir: Path
) -> None:
    harness.script(raw(three_distinct_payloads()))

    meta = metadata_of(generate(prompt="three squares", n=3, output_dir=str(out_dir)))

    assert meta["provider_returned"] == 3
    assert meta["complete"] is True
    assert len(meta["images"]) == 3


def test_a_decode_failure_also_clears_the_complete_flag(
    harness: Harness, out_dir: Path
) -> None:
    """Three payloads arrived, so `provider_returned` is 3 — but one was
    undecodable, so the call is not complete. The two fields report different
    facts and both are needed.
    """
    harness.script(raw([b64_image(), "@@@ not base64 @@@", b64_image()]))

    meta = metadata_of(generate(prompt="three squares", n=3, output_dir=str(out_dir)))

    assert meta["provider_returned"] == 3
    assert meta["complete"] is False
    assert len(meta["images"]) == 2
    assert [failure["index"] for failure in meta["failed_images"]] == [1]


def test_edit_reports_the_same_shortfall_fields(
    harness: Harness, out_dir: Path, reference_png: Path
) -> None:
    """MUTATION CAUGHT: adding the shortfall signal to generate only. Both tools
    share `_metadata`, and both callers pay per image.
    """
    harness.script(raw([b64_image()]))

    meta = metadata_of(
        edit(
            prompt="repaint the sky",
            image_paths=[str(reference_png)],
            n=2,
            output_dir=str(out_dir),
        )
    )

    assert meta["requested"]["n"] == 2
    assert meta["provider_returned"] == 1
    assert meta["complete"] is False


# ===========================================================================
# Where the files go
# ===========================================================================


def test_a_missing_output_dir_tree_is_created(harness: Harness, tmp_path: Path) -> None:
    """IMG-REQ-006: the server may create the requested directory and missing
    descendants. MUTATION CAUGHT: dropping `parents=True` from the `mkdir`, or
    making a non-existent `output_dir` a validation error.
    """
    nested = tmp_path / "a" / "b" / "c"
    assert not nested.exists()
    harness.script(raw([b64_image()]))

    meta = metadata_of(generate(prompt="a square", output_dir=str(nested)))

    written = Path(meta["images"][0]["path"])
    assert written.resolve() == (nested / "image.png").resolve()
    assert written.is_file()
    assert files_in(nested) == ["image.png"]


def test_the_default_output_dir_follows_the_callers_working_directory(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MUTATION CAUGHT: resolving the default output directory at import time
    (a module-level `Path.cwd() / DEFAULT_OUTPUT_SUBDIR`) instead of at call
    time. That reads as identical in every test that passes `output_dir`
    explicitly, and it silently writes the caller's images under whatever
    directory the MCP server process happened to start in.

    Driven through the real tool, so the whole `models` -> `images` ->
    `publish_atomic` chain has to honour it.
    """
    session = tmp_path / "session"
    session.mkdir()
    monkeypatch.chdir(session)
    harness.script(raw([b64_image()]))

    meta = metadata_of(generate(prompt="a square"))

    expected_dir = session / constants.DEFAULT_OUTPUT_SUBDIR
    written = Path(meta["images"][0]["path"])
    assert written.resolve() == (expected_dir / "image.png").resolve()
    assert written.is_file()
    assert files_in(expected_dir) == ["image.png"]
    assert constants.DEFAULT_OUTPUT_SUBDIR == "generated-images"


def test_the_default_output_dir_is_reread_per_call(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two calls, two working directories, two destinations. A cached default
    would put both files in the first one.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    harness.script(raw([b64_image()]))

    monkeypatch.chdir(first)
    one = Path(metadata_of(generate(prompt="a square"))["images"][0]["path"])
    monkeypatch.chdir(second)
    two = Path(metadata_of(generate(prompt="a square"))["images"][0]["path"])

    assert one.resolve().parent == (first / constants.DEFAULT_OUTPUT_SUBDIR).resolve()
    assert two.resolve().parent == (second / constants.DEFAULT_OUTPUT_SUBDIR).resolve()
    # Not a collision suffix in the first directory — a genuinely new location.
    assert one.name == "image.png"
    assert two.name == "image.png"


@pytest.mark.parametrize(
    "shape",
    [
        pytest.param("file", id="output_dir-is-a-file"),
        pytest.param("under-file", id="output_dir-under-a-file"),
    ],
)
def test_an_output_dir_that_is_a_file_is_rejected_before_the_credential(
    harness: Harness, tmp_path: Path, shape: str
) -> None:
    """MUTATION CAUGHT: removing the nearest-existing-ancestor walk from
    `resolve_output_dir`, leaving only the absoluteness check.

    A path naming a regular file is absolute, so it passes that check. Without
    the walk the failure surfaces from `publish_atomic` — after the credential
    was read, after the image was generated, and after it was billed. The two
    counter assertions are the whole point: this must cost nothing.
    """
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"not a directory")
    target = blocker if shape == "file" else blocker / "nested" / "deeper"

    with pytest.raises(ToolError) as excinfo:
        generate(prompt="a square", output_dir=str(target))

    payload = error_payload(excinfo.value)
    assert payload["status"] == "error"
    assert payload["code"] == errors.INVALID_REQUEST
    assert payload["details"]["field"] == "output_dir"
    assert harness.creds.calls == 0
    assert harness.client.call_count == 0
    # The blocking file was neither read into the message nor touched.
    assert blocker.read_bytes() == b"not a directory"


def test_an_output_dir_that_is_a_file_is_rejected_for_edit_too(
    harness: Harness, tmp_path: Path, reference_png: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"not a directory")

    with pytest.raises(ToolError) as excinfo:
        edit(
            prompt="repaint the sky",
            image_paths=[str(reference_png)],
            output_dir=str(blocker),
        )

    payload = error_payload(excinfo.value)
    assert payload["code"] == errors.INVALID_REQUEST
    assert harness.creds.calls == 0
    assert harness.client.call_count == 0
