"""IMG-AC-004: every locally-detectable bad request dies before it costs anything.

Two things are proved here, and the second one is the load-bearing one.

1. The rule tables. Prompt, quality, format, compression, background, moderation,
   count, size, output directory, basename, references, and mask each get their
   own matrix, asserted against the closed codes in `errors` — never against
   prose.

2. **Nothing invalid ever reaches a credential or a client.** An autouse fixture
   replaces `credentials.resolve_api_key` and `api.build_client` with tripwires
   that *count* the reach and then raise, and every rejection test calls
   `assert_nothing_reached_a_credential_or_a_client()`.

   That helper replaced ~25 `assert fake_factory.call_count == 0` lines, which
   were tautologies: `fake_factory` is a fresh `FakeClientFactory` that was never
   installed as anybody's `client_factory` on those paths, so its `call_count`
   read 0 whatever the production code did. Deleting every rule in `models.py`
   would not have moved it. The counters below are wired to the two seams that
   actually cost money, and the four `test_the_*` tests under "The tripwire
   itself" are the negative controls that prove a counter can move — without
   them this file would simply have swapped one vacuous assertion for another.

The request-shape half of IMG-AC-003 lives at the bottom: a validated request
becomes exactly the approved OpenAI body, with `model=gpt-image-2` and none of
the parameters the requirements forbid.
"""

from __future__ import annotations

import dataclasses
import json
from functools import partial
from pathlib import Path
from typing import Any, Callable

import anyio
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from conftest import CANARY_SECRET, FakeClientFactory, write_image

from gpt_image_2 import api, constants, credentials, errors, models, server

# ---------------------------------------------------------------------------
# Tripwires
# ---------------------------------------------------------------------------

_TRIPWIRE = "validation reached a credential or a client"


class CredentialTripwireTripped(AssertionError):
    """Raised when something under test read the API credential."""


class ClientTripwireTripped(AssertionError):
    """Raised when something under test built an OpenAI client."""


@dataclasses.dataclass
class TripwireRecord:
    """How many times each paid-path seam was actually reached."""

    credential_reads: int = 0
    clients_built: int = 0

    def reset(self) -> None:
        self.credential_reads = 0
        self.clients_built = 0


#: One instance, reset per test by the autouse fixture below, so a rejection test
#: keeps a one-line assertion instead of threading a fixture through a signature
#: it does not otherwise need. `tripwire` hands the same object to the tests that
#: want to read the counts directly.
_TRIPWIRE_RECORD = TripwireRecord()


@pytest.fixture(autouse=True)
def tripwire(monkeypatch: pytest.MonkeyPatch) -> TripwireRecord:
    """Count *and* refuse every credential read and client build in this module.

    Both seams are patched exactly where the production code looks them up:

    * `server.generate_image` calls `credentials.resolve_api_key()` through the
      module object at call time, so a module attribute swap intercepts it.
    * `api._call_with_retry` resolves `build_client` from the module *inside* the
      call (`factory = build_client if client_factory is None else ...`) rather
      than binding it as a keyword default. That is what makes
      `setattr(api, "build_client", ...)` actually take effect; with the default
      bound at def-time the patch was silently ignored and the real client got
      built.

    The two `AssertionError` subclasses are deliberate. They are not
    `ImageToolError`, so they escape every `pytest.raises(ImageToolError)` below
    and fail the test loudly instead of being mistaken for the rejection under
    test, and their distinct names make the MCP payload's
    `details.exception_type` say which wire was tripped.
    """
    _TRIPWIRE_RECORD.reset()

    def _resolve(*_args: Any, **_kwargs: Any):
        _TRIPWIRE_RECORD.credential_reads += 1
        raise CredentialTripwireTripped(_TRIPWIRE)

    def _build(*_args: Any, **_kwargs: Any):
        _TRIPWIRE_RECORD.clients_built += 1
        raise ClientTripwireTripped(_TRIPWIRE)

    monkeypatch.setattr(credentials, "resolve_api_key", _resolve)
    monkeypatch.setattr(api, "build_client", _build)
    return _TRIPWIRE_RECORD


def assert_nothing_reached_a_credential_or_a_client() -> None:
    """Constitution principle 3, as an assertion that can actually fail.

    This is the replacement for `assert fake_factory.call_count == 0`. That line
    could not fail: nothing on these paths ever received `fake_factory` as a
    `client_factory`, so its counter was pinned at 0 by construction. These two
    counters move the moment a rejected request touches `resolve_api_key` or
    `build_client`, which is the property the file claims to prove.
    """
    assert _TRIPWIRE_RECORD.credential_reads == 0, (
        f"a rejected request read the credential "
        f"{_TRIPWIRE_RECORD.credential_reads} time(s)"
    )
    assert _TRIPWIRE_RECORD.clients_built == 0, (
        f"a rejected request built an OpenAI client "
        f"{_TRIPWIRE_RECORD.clients_built} time(s)"
    )


def _tool_error_payload(exc: ToolError) -> dict[str, Any]:
    """The failure payload, however the MCP edge decorates it.

    `server._fail` prefixes the error code, and FastMCP's `Tool.run` prefixes
    "Error executing tool <name>:" on top of that, so `json.loads` on the whole
    message fails. The JSON object is the tail; parse from the first brace and
    the assertions below stay true whichever decoration is in force.
    """
    text = str(exc)
    start = text.find("{")
    assert start != -1, f"tool error carried no JSON payload: {text!r}"
    return json.loads(text[start:])


def _rejects(code: str, fn: Callable[..., Any], /, **kwargs: Any) -> errors.ImageToolError:
    with pytest.raises(errors.ImageToolError) as excinfo:
        fn(**kwargs)
    assert excinfo.value.code == code, f"expected {code}, got {excinfo.value.code}"
    return excinfo.value


def _generate(**overrides: Any) -> models.GenerateRequest:
    kwargs: dict[str, Any] = {"prompt": "a small red apple on a white table"}
    kwargs.update(overrides)
    return models.validate_generate(**kwargs)


def _edit(reference: Path, **overrides: Any) -> models.EditRequest:
    kwargs: dict[str, Any] = {
        "prompt": "make the apple green",
        "image_paths": [str(reference)],
    }
    kwargs.update(overrides)
    return models.validate_edit(**kwargs)


# ---------------------------------------------------------------------------
# The tripwire itself — the negative controls, without which everything above
# this line is decoration
# ---------------------------------------------------------------------------


def test_the_credential_tripwire_fires_on_the_valid_path(
    tripwire: TripwireRecord,
) -> None:
    """The *valid* request must reach `resolve_api_key`, so the counter must move.

    Catches: a `credentials.resolve_api_key` patch that no longer intercepts
    anything — because the server started importing the symbol directly
    (`from .credentials import resolve_api_key`) instead of calling it through
    the module, say. If that happened, `credential_reads` would stay at 0 here
    and every `assert_nothing_reached_a_credential_or_a_client()` in this file
    would silently become a no-op again.
    """
    with pytest.raises(ToolError) as tripped:
        anyio.run(partial(server.generate_image, prompt="a valid prompt"))

    payload = _tool_error_payload(tripped.value)
    assert payload["code"] == errors.INTERNAL_ERROR
    assert payload["details"]["exception_type"] == "CredentialTripwireTripped"
    assert tripwire.credential_reads == 1
    # The credential wire fires first, so no client is ever built on this path.
    assert tripwire.clients_built == 0


def test_the_client_tripwire_fires_when_a_request_gets_as_far_as_a_client(
    monkeypatch: pytest.MonkeyPatch, tripwire: TripwireRecord
) -> None:
    """The second negative control, and the regression for late-bound factories.

    Catches: restoring `client_factory: Callable[[Secret], Any] = build_client`
    as a keyword default in `api._call_with_retry`. A default is bound at `def`
    time, so `monkeypatch.setattr(api, "build_client", ...)` used to be ignored
    entirely and the SDK client got built for real — which means the client half
    of this module's tripwire proved precisely nothing.

    With the fix, `build_client` is resolved from the module inside the call, so
    the patch lands and `clients_built` reaches 1. Revert it and the real
    `build_client` runs instead: conftest's `_block_real_network` guard raises a
    plain `AssertionError`, `clients_built` stays 0, and both assertions below
    fail.
    """
    monkeypatch.setattr(
        credentials,
        "resolve_api_key",
        lambda *_a, **_k: credentials.Secret(CANARY_SECRET),
    )

    with pytest.raises(ToolError) as tripped:
        anyio.run(partial(server.generate_image, prompt="a valid prompt"))

    payload = _tool_error_payload(tripped.value)
    assert payload["code"] == errors.INTERNAL_ERROR
    assert payload["details"]["exception_type"] == "ClientTripwireTripped"
    assert tripwire.clients_built == 1
    assert CANARY_SECRET not in json.dumps(payload)


def test_the_invalid_path_never_gets_near_either_wire(
    tripwire: TripwireRecord,
) -> None:
    """The other half of the control: a rejected request moves neither counter."""
    with pytest.raises(ToolError) as stopped:
        anyio.run(partial(server.generate_image, prompt="   "))

    payload = _tool_error_payload(stopped.value)
    assert payload["code"] == errors.INVALID_REQUEST
    assert (tripwire.credential_reads, tripwire.clients_built) == (0, 0)
    assert_nothing_reached_a_credential_or_a_client()


def test_the_tripwire_helper_itself_can_fail() -> None:
    """Proof by construction that `assert_nothing_reached_a_credential_or_a_client`
    is not the tautology it replaced.

    The old `assert fake_factory.call_count == 0` could not be made to fail from
    inside a test at all — there was no way to reach that counter. This one is
    one attribute away, which is the whole difference.
    """
    _TRIPWIRE_RECORD.credential_reads = 1
    try:
        with pytest.raises(AssertionError, match="read the credential"):
            assert_nothing_reached_a_credential_or_a_client()

        _TRIPWIRE_RECORD.credential_reads = 0
        _TRIPWIRE_RECORD.clients_built = 1
        with pytest.raises(AssertionError, match="built an OpenAI client"):
            assert_nothing_reached_a_credential_or_a_client()
    finally:
        _TRIPWIRE_RECORD.reset()


@pytest.mark.parametrize(
    "operation, kwargs",
    [
        pytest.param("generate", {"prompt": ""}, id="generate-blank-prompt"),
        pytest.param("generate", {"prompt": "p", "size": "1000x1000"}, id="generate-size"),
        pytest.param("generate", {"prompt": "p", "quality": "ultra"}, id="generate-quality"),
        pytest.param(
            "generate",
            {"prompt": "p", "output_format": "png", "output_compression": 50},
            id="generate-png-compression",
        ),
        pytest.param("generate", {"prompt": "p", "n": 0}, id="generate-n"),
        pytest.param("generate", {"prompt": "p", "output_dir": "relative"}, id="generate-output-dir"),
        pytest.param("edit", {"prompt": "p", "image_paths": []}, id="edit-empty-paths"),
        pytest.param("edit", {"prompt": "", "image_paths": ["x.png"]}, id="edit-blank-prompt"),
    ],
)
def test_invalid_tool_calls_never_touch_credentials(
    operation: str, kwargs: dict[str, Any]
) -> None:
    """IMG-AC-004 through the real MCP edge, not just the validator."""
    tool = server.generate_image if operation == "generate" else server.edit_image
    with pytest.raises(ToolError) as excinfo:
        anyio.run(partial(tool, **kwargs))
    payload = _tool_error_payload(excinfo.value)
    assert payload["code"] in {errors.INVALID_REQUEST, errors.UNSUPPORTED_OPTION}
    assert_nothing_reached_a_credential_or_a_client()


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
        pytest.param("\t\n ", id="whitespace-control"),
        pytest.param(123, id="int"),
        pytest.param(["a prompt"], id="list"),
        pytest.param(b"bytes prompt", id="bytes"),
        pytest.param("a" * (constants.MAX_PROMPT_CHARS + 1), id="over-limit-32001"),
    ],
)
def test_prompt_rejected(prompt: Any) -> None:
    error = _rejects(errors.INVALID_REQUEST, models.validate_generate, prompt=prompt)
    assert error.details["field"] == "prompt"
    assert_nothing_reached_a_credential_or_a_client()


def test_prompt_at_exact_limit_is_accepted() -> None:
    prompt = "a" * constants.MAX_PROMPT_CHARS
    request = models.validate_generate(prompt=prompt)
    assert len(request.prompt) == constants.MAX_PROMPT_CHARS


def test_prompt_is_forwarded_verbatim() -> None:
    """Surrounding whitespace is not silently rewritten; only blankness fails."""
    assert _generate(prompt="  a red apple  ").prompt == "  a red apple  "


# ---------------------------------------------------------------------------
# quality
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param("auto", "auto", id="auto"),
        pytest.param("low", "low", id="low"),
        pytest.param("medium", "medium", id="medium"),
        pytest.param("high", "high", id="high"),
        pytest.param("HIGH", "high", id="uppercase"),
        pytest.param("  Medium ", "medium", id="padded-mixed-case"),
    ],
)
def test_quality_accepted(value: str, expected: str) -> None:
    assert _generate(quality=value).quality == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("ultra", id="ultra"),
        pytest.param("hd", id="hd"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
        pytest.param("standard", id="dall-e-vocabulary"),
        pytest.param(3, id="int"),
    ],
)
def test_quality_rejected(value: Any) -> None:
    error = _rejects(errors.INVALID_REQUEST, models.validate_generate, prompt="p", quality=value)
    assert error.details["field"] == "quality"
    assert_nothing_reached_a_credential_or_a_client()


def test_quality_defaults_to_high() -> None:
    assert _generate().quality == constants.DEFAULT_QUALITY == "high"


# ---------------------------------------------------------------------------
# output_format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected, extension, mime",
    [
        pytest.param("png", "png", ".png", "image/png", id="png"),
        pytest.param("jpeg", "jpeg", ".jpg", "image/jpeg", id="jpeg"),
        pytest.param("webp", "webp", ".webp", "image/webp", id="webp"),
        pytest.param("PNG", "png", ".png", "image/png", id="uppercase"),
        pytest.param(" WebP ", "webp", ".webp", "image/webp", id="padded-mixed-case"),
    ],
)
def test_output_format_accepted_with_matching_extension_and_mime(
    value: str, expected: str, extension: str, mime: str
) -> None:
    request = _generate(output_format=value)
    assert request.output_format == expected
    assert request.extension == extension
    assert request.mime_type == mime


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("gif", id="gif"),
        pytest.param("tiff", id="tiff"),
        pytest.param("jpg", id="jpg-is-the-extension-not-the-format"),
        pytest.param("bmp", id="bmp"),
        pytest.param("", id="empty"),
        pytest.param(0, id="int"),
    ],
)
def test_output_format_rejected(value: Any) -> None:
    error = _rejects(
        errors.INVALID_REQUEST, models.validate_generate, prompt="p", output_format=value
    )
    assert error.details["field"] == "output_format"
    assert_nothing_reached_a_credential_or_a_client()


def test_output_format_defaults_to_png() -> None:
    request = _generate()
    assert request.output_format == constants.DEFAULT_OUTPUT_FORMAT == "png"
    assert request.extension == ".png"
    assert request.mime_type == "image/png"


# ---------------------------------------------------------------------------
# output_compression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "output_format, value",
    [
        pytest.param("jpeg", 0, id="jpeg-0"),
        pytest.param("jpeg", 100, id="jpeg-100"),
        pytest.param("jpeg", 75, id="jpeg-mid"),
        pytest.param("webp", 0, id="webp-0"),
        pytest.param("webp", 100, id="webp-100"),
    ],
)
def test_output_compression_accepted(output_format: str, value: int) -> None:
    request = _generate(output_format=output_format, output_compression=value)
    assert request.output_compression == value


@pytest.mark.parametrize(
    "output_format, value",
    [
        pytest.param("png", 0, id="png-0"),
        pytest.param("png", 50, id="png-mid"),
        pytest.param("png", 100, id="png-100"),
        pytest.param("jpeg", -1, id="jpeg-below-range"),
        pytest.param("jpeg", 101, id="jpeg-above-range"),
        pytest.param("webp", -1, id="webp-below-range"),
        pytest.param("webp", 101, id="webp-above-range"),
        pytest.param("jpeg", True, id="bool-true"),
        pytest.param("jpeg", False, id="bool-false"),
        pytest.param("jpeg", 50.0, id="float"),
        pytest.param("jpeg", "50", id="numeric-string"),
    ],
)
def test_output_compression_rejected(
    output_format: str, value: Any) -> None:
    error = _rejects(
        errors.INVALID_REQUEST,
        models.validate_generate,
        prompt="p",
        output_format=output_format,
        output_compression=value,
    )
    assert error.details["field"] == "output_compression"
    assert_nothing_reached_a_credential_or_a_client()


def test_output_compression_defaults_to_none() -> None:
    assert _generate(output_format="jpeg").output_compression is None
    assert "output_compression" not in api.build_generate_kwargs(_generate(output_format="jpeg"))


# ---------------------------------------------------------------------------
# background
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param("auto", "auto", id="auto"),
        pytest.param("opaque", "opaque", id="opaque"),
        pytest.param("AUTO", "auto", id="uppercase"),
        pytest.param("  Opaque  ", "opaque", id="padded-mixed-case"),
    ],
)
def test_background_accepted(value: str, expected: str) -> None:
    assert _generate(background=value).background == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("transparent", id="lowercase"),
        pytest.param("TRANSPARENT", id="uppercase"),
        pytest.param("  transparent ", id="padded"),
    ],
)
def test_transparent_background_is_an_unsupported_option_naming_the_model(
    value: str) -> None:
    """Not INVALID_REQUEST: the option is real, this model just cannot do it."""
    error = _rejects(
        errors.UNSUPPORTED_OPTION, models.validate_generate, prompt="p", background=value
    )
    assert error.details["field"] == "background"
    assert constants.MODEL in error.message
    assert_nothing_reached_a_credential_or_a_client()


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("blue", id="colour"),
        pytest.param("", id="empty"),
        pytest.param("none", id="none-string"),
        pytest.param("alpha", id="alpha"),
        pytest.param(1, id="int"),
    ],
)
def test_background_rejected(value: Any) -> None:
    error = _rejects(
        errors.INVALID_REQUEST, models.validate_generate, prompt="p", background=value
    )
    assert error.details["field"] == "background"
    assert_nothing_reached_a_credential_or_a_client()


def test_background_defaults_to_auto() -> None:
    assert _generate().background == constants.DEFAULT_BACKGROUND == "auto"


# ---------------------------------------------------------------------------
# moderation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param("auto", "auto", id="auto"),
        pytest.param("low", "low", id="low"),
        pytest.param("LOW", "low", id="uppercase"),
    ],
)
def test_moderation_accepted_on_generate(value: str, expected: str) -> None:
    assert _generate(moderation=value).moderation == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("strict", id="strict"),
        pytest.param("off", id="off"),
        pytest.param("high", id="quality-vocabulary"),
        pytest.param("", id="empty"),
    ],
)
def test_moderation_rejected(value: Any) -> None:
    error = _rejects(
        errors.INVALID_REQUEST, models.validate_generate, prompt="p", moderation=value
    )
    assert error.details["field"] == "moderation"
    assert_nothing_reached_a_credential_or_a_client()


def test_moderation_defaults_to_auto() -> None:
    assert _generate().moderation == constants.DEFAULT_MODERATION == "auto"


def test_edit_request_has_no_moderation_at_all(reference_png: Path) -> None:
    """`POST /v1/images/edits` has no `moderation`, so neither does EditRequest."""
    request = _edit(reference_png)
    assert not hasattr(request, "moderation")
    assert "moderation" not in {f.name for f in dataclasses.fields(models.EditRequest)}
    with pytest.raises(TypeError):
        models.validate_edit(
            prompt="p", image_paths=[str(reference_png)], moderation="low"
        )


# ---------------------------------------------------------------------------
# n
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [pytest.param(1, id="min"), pytest.param(5, id="mid"), pytest.param(10, id="max")],
)
def test_n_accepted(value: int) -> None:
    assert _generate(n=value).n == value


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(0, id="zero"),
        pytest.param(11, id="above-max"),
        pytest.param(-1, id="negative"),
        pytest.param(1.5, id="float"),
        pytest.param(1.0, id="whole-float"),
        pytest.param(True, id="bool-true"),
        pytest.param(False, id="bool-false"),
        pytest.param("2", id="numeric-string"),
    ],
)
def test_n_rejected(value: Any) -> None:
    error = _rejects(errors.INVALID_REQUEST, models.validate_generate, prompt="p", n=value)
    assert error.details["field"] == "n"
    assert_nothing_reached_a_credential_or_a_client()


def test_n_defaults_to_one() -> None:
    assert _generate().n == constants.DEFAULT_N == 1


# ---------------------------------------------------------------------------
# size
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        # The sizes the guide documents. All of these must stay legal.
        pytest.param("1024x1024", "1024x1024", id="documented-square"),
        pytest.param("1536x1024", "1536x1024", id="documented-landscape"),
        pytest.param("1024x1536", "1024x1536", id="documented-portrait"),
        pytest.param("2048x2048", "2048x2048", id="documented-large-square"),
        pytest.param("2048x1152", "2048x1152", id="documented-widescreen"),
        pytest.param("3840x2160", "3840x2160", id="documented-4k-landscape"),
        pytest.param("2160x3840", "2160x3840", id="documented-4k-portrait"),
        # auto and normalisation.
        pytest.param("auto", "auto", id="auto"),
        pytest.param("AUTO", "auto", id="auto-uppercase"),
        pytest.param("  auto ", "auto", id="auto-padded"),
        pytest.param("1024X1024", "1024x1024", id="uppercase-separator"),
        pytest.param(" 1024x1024 ", "1024x1024", id="padded"),
        # Inclusive boundaries.
        pytest.param("1024x640", "1024x640", id="exactly-min-total-pixels"),
        pytest.param("3840x1280", "3840x1280", id="exactly-3-to-1-ratio"),
    ],
)
def test_parse_size_accepted(value: str, expected: str) -> None:
    assert models.parse_size(value) == expected
    assert _generate(size=value).size == expected


@pytest.mark.parametrize(
    "value",
    [
        # Each case violates exactly one rule, so the table maps rule -> failure.
        pytest.param("1000x1000", id="rule-not-a-multiple-of-16"),
        pytest.param("1024x1000", id="rule-height-not-a-multiple-of-16"),
        pytest.param("3856x1296", id="rule-edge-above-3840"),
        pytest.param("1296x3856", id="rule-edge-above-3840-portrait"),
        pytest.param("3840x1152", id="rule-aspect-above-3-to-1"),
        pytest.param("1152x3840", id="rule-aspect-above-3-to-1-portrait"),
        pytest.param("512x512", id="rule-total-pixels-below-655360"),
        pytest.param("1024x624", id="rule-just-below-min-total-pixels"),
        pytest.param("3840x2400", id="rule-total-pixels-above-8294400"),
        pytest.param("3840x3840", id="rule-total-pixels-far-above-max"),
        pytest.param("1024.5x1024", id="rule-non-integer-decimal"),
        pytest.param("1e3x1024", id="rule-non-integer-exponent"),
        pytest.param("abcxdef", id="rule-non-integer-letters"),
        pytest.param("1024x", id="rule-non-integer-missing-height"),
        pytest.param("-1024x1024", id="rule-negative-width"),
        pytest.param("1024x-1024", id="rule-negative-height"),
        pytest.param("0x0", id="rule-zero"),
        pytest.param("1024", id="rule-no-separator"),
        pytest.param("1024*1024", id="rule-wrong-separator"),
        pytest.param("1024x1024x1024", id="rule-too-many-separators"),
        pytest.param("", id="rule-empty"),
        pytest.param("   ", id="rule-whitespace"),
        pytest.param("square", id="rule-word"),
        pytest.param(1024, id="rule-not-a-string"),
    ],
)
def test_parse_size_rejected(value: Any) -> None:
    error = _rejects(errors.INVALID_REQUEST, models.parse_size, value=value)
    assert error.details["field"] == "size"
    through_validate = _rejects(
        errors.INVALID_REQUEST, models.validate_generate, prompt="p", size=value
    )
    assert through_validate.details["field"] == "size"
    assert_nothing_reached_a_credential_or_a_client()


def test_size_defaults_to_1024_square() -> None:
    assert models.parse_size(None) == constants.DEFAULT_SIZE == "1024x1024"
    assert _generate().size == "1024x1024"


# ---------------------------------------------------------------------------
# output_dir and basename
# ---------------------------------------------------------------------------


def test_output_dir_defaults_under_the_current_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Read at call time, so two sessions in two directories do not collide."""
    first = tmp_path / "session-a"
    second = tmp_path / "session-b"
    first.mkdir()
    second.mkdir()

    monkeypatch.chdir(first)
    from_first = _generate().output_dir
    assert from_first == Path.cwd() / constants.DEFAULT_OUTPUT_SUBDIR
    assert from_first.name == "generated-images"

    monkeypatch.chdir(second)
    from_second = _generate().output_dir
    assert from_second == Path.cwd() / constants.DEFAULT_OUTPUT_SUBDIR
    assert from_second != from_first


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("generated-images", id="bare-relative"),
        pytest.param("./out", id="dot-relative"),
        pytest.param("../out", id="parent-relative"),
        pytest.param("out/nested", id="nested-relative"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
    ],
)
def test_output_dir_rejected(value: str) -> None:
    error = _rejects(
        errors.INVALID_REQUEST, models.validate_generate, prompt="p", output_dir=value
    )
    assert error.details["field"] == "output_dir"
    assert_nothing_reached_a_credential_or_a_client()


def test_absolute_output_dir_is_accepted_unchanged_and_not_created(out_dir: Path) -> None:
    request = _generate(output_dir=str(out_dir))
    assert request.output_dir == out_dir
    assert not out_dir.exists(), "validation must not create anything on disk"


@pytest.mark.parametrize(
    "shape",
    [
        pytest.param("is-a-file", id="output_dir-is-an-existing-regular-file"),
        pytest.param("under-a-file", id="output_dir-lies-under-an-existing-file"),
    ],
)
def test_an_unusable_output_dir_is_rejected_before_the_request_costs_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """Constitution principle 3 for the one path check that used to be missing.

    Catches: reverting the nearest-existing-ancestor walk in
    `images.resolve_output_dir` (the `while True: if probe.exists() ...` loop).
    Absoluteness alone is satisfied by a path that *names an existing file*, so
    before the fix this request validated cleanly, read the credential,
    generated and paid for an image, and only then blew up inside
    `publish_atomic` — where `mkdir` hits FileExistsError / NotADirectoryError.
    The money was already spent on an output that could never land.

    The two counters are what make this a regression rather than a restatement.
    The credential stand-in returns a real `Secret` instead of exploding, and the
    fake factory is installed as `api.build_client`, so a revert produces
    *counted* work rather than an exception that could be mistaken for the
    rejection under test. Reverted, this test fails four ways at once: the code
    becomes `output_error`, there is no `field` detail, `credential_reads`
    becomes 1, and `factory.call_count` becomes 1.
    """
    occupied = tmp_path / "not-a-directory.txt"
    occupied.write_bytes(b"in the way")
    output_dir = occupied if shape == "is-a-file" else occupied / "sub" / "deeper"

    credential_reads: list[str] = []

    def _counting_resolve(*_args: Any, **_kwargs: Any) -> credentials.Secret:
        credential_reads.append("resolved")
        return credentials.Secret(CANARY_SECRET)

    factory = FakeClientFactory()
    monkeypatch.setattr(credentials, "resolve_api_key", _counting_resolve)
    monkeypatch.setattr(api, "build_client", factory)

    with pytest.raises(ToolError) as excinfo:
        anyio.run(
            partial(
                server.generate_image,
                prompt="a perfectly valid prompt",
                output_dir=str(output_dir),
            )
        )

    # The money assertions first, because they are the point of the fix.
    assert credential_reads == [], "the credential was read for a request that cannot land"
    assert factory.call_count == 0, "a paid API call was made for a request that cannot land"

    payload = _tool_error_payload(excinfo.value)
    assert payload["code"] == errors.INVALID_REQUEST
    assert payload["details"]["field"] == "output_dir"
    # And the file that was in the way is untouched.
    assert occupied.read_bytes() == b"in the way"
    assert not (tmp_path / "not-a-directory.txt").is_dir()


def test_basename_defaults_to_generic_image() -> None:
    assert _generate().basename == constants.DEFAULT_BASENAME == "image"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
        pytest.param("../../", id="traversal-only"),
        pytest.param("CON", id="windows-reserved"),
        pytest.param("nul.png", id="windows-reserved-with-extension"),
    ],
)
def test_basename_rejected(value: str) -> None:
    error = _rejects(
        errors.INVALID_REQUEST, models.validate_generate, prompt="p", basename=value
    )
    assert error.details["field"] == "basename"
    assert_nothing_reached_a_credential_or_a_client()


@pytest.mark.parametrize(
    "field_name, value",
    [
        pytest.param("output_dir", Path("C:/images"), id="output_dir-as-Path"),
        pytest.param("output_dir", 123, id="output_dir-as-int"),
        pytest.param("basename", Path("image"), id="basename-as-Path"),
        pytest.param("basename", 123, id="basename-as-int"),
    ],
)
def test_non_string_path_arguments_stay_inside_the_closed_taxonomy(
    field_name: str, value: Any) -> None:
    """A wrong type must be INVALID_REQUEST, not an escaping AttributeError.

    Regression guard: `resolve_output_dir` and `sanitize_basename` used to call
    `.strip()` unguarded, so a `Path` or an `int` escaped the closed taxonomy and
    surfaced at the MCP edge as `internal_error` for what is plainly a caller
    mistake. Every other validator in models.py guards its type; these two must
    keep doing so too.
    """
    error = _rejects(
        errors.INVALID_REQUEST, models.validate_generate, prompt="p", **{field_name: value}
    )
    assert error.details["field"] == field_name
    assert_nothing_reached_a_credential_or_a_client()


# ---------------------------------------------------------------------------
# validate_edit: references
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "image_paths",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty-string"),
        pytest.param("C:/images/reference.png", id="bare-string-path"),
        pytest.param(b"C:/images/reference.png", id="bytes"),
        pytest.param([], id="empty-list"),
        pytest.param((), id="empty-tuple"),
    ],
)
def test_edit_image_paths_rejected(image_paths: Any) -> None:
    error = _rejects(
        errors.INVALID_REQUEST,
        models.validate_edit,
        prompt="p",
        image_paths=image_paths,
    )
    assert error.details["field"] == "image_paths"
    assert_nothing_reached_a_credential_or_a_client()


def test_edit_rejects_more_references_than_the_local_limit() -> None:
    """The count is checked before any file is opened, so fake paths suffice."""
    too_many = [f"never-opened-{i}.png" for i in range(constants.MAX_EDIT_IMAGES + 1)]
    error = _rejects(
        errors.INVALID_REQUEST, models.validate_edit, prompt="p", image_paths=too_many
    )
    assert error.details["field"] == "image_paths"
    # The cap is ours, not OpenAI's, and the message has to say so.
    assert str(constants.MAX_EDIT_IMAGES) in error.message
    assert str(len(too_many)) in error.message
    assert "local" in error.message
    assert_nothing_reached_a_credential_or_a_client()


def test_edit_accepts_exactly_the_local_limit(tmp_path: Path) -> None:
    paths = [
        write_image(tmp_path, f"ref{i:02d}.png", size=(16, 16))
        for i in range(constants.MAX_EDIT_IMAGES)
    ]
    request = models.validate_edit(prompt="p", image_paths=[str(p) for p in paths])
    assert len(request.references) == constants.MAX_EDIT_IMAGES


def test_edit_preserves_reference_order_exactly(tmp_path: Path) -> None:
    first = write_image(tmp_path, "alpha.png", size=(16, 16))
    second = write_image(tmp_path, "bravo.png", size=(16, 16))
    third = write_image(tmp_path, "charlie.png", size=(16, 16))

    shuffled = [third, first, second]
    request = models.validate_edit(
        prompt="p", image_paths=[str(p) for p in shuffled]
    )
    assert [ref.path.name for ref in request.references] == [
        "charlie.png",
        "alpha.png",
        "bravo.png",
    ]
    assert [ref.path for ref in request.references] == [p.resolve() for p in shuffled]


@pytest.mark.parametrize(
    "path_value",
    [
        pytest.param("", id="blank"),
        pytest.param("   ", id="whitespace"),
    ],
)
def test_edit_blank_reference_path_rejected(
    path_value: str) -> None:
    error = _rejects(
        errors.INVALID_REQUEST,
        models.validate_edit,
        prompt="p",
        image_paths=[path_value],
    )
    assert error.details["field"] == "image_paths"
    assert_nothing_reached_a_credential_or_a_client()


def test_edit_missing_reference_file_rejected(
    tmp_path: Path) -> None:
    error = _rejects(
        errors.INVALID_INPUT_FILE,
        models.validate_edit,
        prompt="p",
        image_paths=[str(tmp_path / "nope.png")],
    )
    assert "path" in error.details
    assert_nothing_reached_a_credential_or_a_client()


# ---------------------------------------------------------------------------
# validate_edit: mask
# ---------------------------------------------------------------------------


def test_valid_mask_is_accepted(reference_png: Path, mask_png: Path) -> None:
    request = _edit(reference_png, mask_path=str(mask_png))
    assert request.mask is not None
    assert request.mask.path == mask_png.resolve()
    assert request.mask.has_alpha


@pytest.mark.parametrize(
    "mask_path",
    [pytest.param(None, id="omitted"), pytest.param("", id="blank"), pytest.param("  ", id="whitespace")],
)
def test_absent_mask_leaves_the_request_maskless(
    reference_png: Path, mask_path: Any
) -> None:
    assert _edit(reference_png, mask_path=mask_path).mask is None


def test_mask_with_different_dimensions_rejected(
    reference_png: Path, tmp_path: Path) -> None:
    wrong_size = write_image(
        tmp_path, "wrong-size-mask.png", mode="RGBA", alpha=0, size=(32, 32)
    )
    error = _rejects(
        errors.INVALID_MASK,
        models.validate_edit,
        prompt="p",
        image_paths=[str(reference_png)],
        mask_path=str(wrong_size),
    )
    assert error.details["path"] == str(wrong_size.resolve())
    assert_nothing_reached_a_credential_or_a_client()


def test_fully_opaque_mask_rejected(
    reference_png: Path, tmp_path: Path) -> None:
    """A mask with no transparency selects nothing, so the call would burn money."""
    opaque = write_image(
        tmp_path, "opaque-mask.png", mode="RGBA", alpha=255, size=(64, 64)
    )
    error = _rejects(
        errors.INVALID_MASK,
        models.validate_edit,
        prompt="p",
        image_paths=[str(reference_png)],
        mask_path=str(opaque),
    )
    assert error.details["path"] == str(opaque.resolve())
    assert_nothing_reached_a_credential_or_a_client()


def test_mask_without_alpha_channel_rejected(
    reference_png: Path, tmp_path: Path) -> None:
    flat = write_image(tmp_path, "no-alpha-mask.png", mode="RGB", size=(64, 64))
    _rejects(
        errors.INVALID_MASK,
        models.validate_edit,
        prompt="p",
        image_paths=[str(reference_png)],
        mask_path=str(flat),
    )
    assert_nothing_reached_a_credential_or_a_client()


def test_mask_format_mismatch_rejected(
    reference_png: Path, tmp_path: Path) -> None:
    webp_mask = write_image(
        tmp_path, "mask.webp", fmt="webp", mode="RGBA", alpha=0, size=(64, 64)
    )
    _rejects(
        errors.INVALID_MASK,
        models.validate_edit,
        prompt="p",
        image_paths=[str(reference_png)],
        mask_path=str(webp_mask),
    )
    assert_nothing_reached_a_credential_or_a_client()


def test_mask_is_checked_against_the_first_reference_only(
    reference_png: Path, mask_png: Path, tmp_path: Path
) -> None:
    other_size = write_image(tmp_path, "second.png", size=(128, 128))
    request = models.validate_edit(
        prompt="p",
        image_paths=[str(reference_png), str(other_size)],
        mask_path=str(mask_png),
    )
    assert request.mask is not None
    assert request.references[0].path == reference_png.resolve()


# ---------------------------------------------------------------------------
# IMG-AC-003, request-shape half: a validated request becomes the approved body
# ---------------------------------------------------------------------------

#: Every one of these is banned by a requirement, so none may ever appear in a
#: request body: model override / fallback (IMG-REQ-002), credential
#: (IMG-REQ-005), remote input or endpoint escape (IMG-REQ-002), overwrite
#: (IMG-REQ-006), and input_fidelity (not settable for this model).
FORBIDDEN_REQUEST_KEYS = (
    "api_key",
    "authorization",
    "headers",
    "endpoint",
    "base_url",
    "url",
    "image_url",
    "file_id",
    "overwrite",
    "output_dir",
    "basename",
    "input_fidelity",
)


def test_generate_body_uses_the_fixed_model_and_the_approved_defaults() -> None:
    kwargs = api.build_generate_kwargs(_generate(prompt="a red apple"))
    assert kwargs == {
        "model": "gpt-image-2",
        "prompt": "a red apple",
        "n": 1,
        "size": "1024x1024",
        "quality": "high",
        "output_format": "png",
        "background": "auto",
        "moderation": "auto",
    }
    assert kwargs["model"] == constants.MODEL


def test_generate_body_carries_every_explicit_control() -> None:
    request = _generate(
        prompt="a red apple",
        size="1536x1024",
        quality="low",
        output_format="jpeg",
        n=3,
        output_compression=80,
        background="opaque",
        moderation="low",
    )
    assert api.build_generate_kwargs(request) == {
        "model": "gpt-image-2",
        "prompt": "a red apple",
        "n": 3,
        "size": "1536x1024",
        "quality": "low",
        "output_format": "jpeg",
        "background": "opaque",
        "moderation": "low",
        "output_compression": 80,
    }


def test_edit_body_shape_preserves_order_and_omits_the_banned_parameters(
    reference_png: Path, mask_png: Path, tmp_path: Path
) -> None:
    second = write_image(tmp_path, "second.png", size=(16, 16))
    request = models.validate_edit(
        prompt="make the apple green",
        image_paths=[str(reference_png), str(second)],
        mask_path=str(mask_png),
        output_format="webp",
        output_compression=60,
    )
    kwargs = api.build_edit_kwargs(request)

    assert kwargs["model"] == constants.MODEL == "gpt-image-2"
    assert [entry[0] for entry in kwargs["image"]] == ["reference.png", "second.png"]
    assert [entry[2] for entry in kwargs["image"]] == ["image/png", "image/png"]
    assert kwargs["mask"][0] == "mask.png"
    assert kwargs["output_compression"] == 60
    assert "moderation" not in kwargs, "the edit endpoint has no moderation parameter"
    for banned in constants.OMITTED_EDIT_PARAMS:
        assert banned not in kwargs


@pytest.mark.parametrize("key", FORBIDDEN_REQUEST_KEYS)
def test_no_forbidden_key_reaches_either_request_body(
    key: str, reference_png: Path
) -> None:
    generate_kwargs = api.build_generate_kwargs(_generate(output_dir=None))
    edit_kwargs = api.build_edit_kwargs(_edit(reference_png))
    assert key not in generate_kwargs
    assert key not in edit_kwargs


def test_recorded_generate_call_matches_the_validated_request(
    fake_factory: FakeClientFactory,
    secret: credentials.Secret,
    budget: api.Budget,
    sleeper: Any,
    no_jitter: Callable[[], float],
) -> None:
    """The shape actually handed to the SDK, recorded rather than assumed."""
    request = _generate(prompt="a red apple", quality="low", size="1024x1024")
    anyio.run(
        partial(
            api.call_generate,
            request,
            secret=secret,
            budget=budget,
            client_factory=fake_factory,
            sleep=sleeper,
            jitter=no_jitter,
        )
    )

    assert fake_factory.call_count == 1
    assert fake_factory.secrets_seen == [secret]
    call = fake_factory.client.calls[0]
    assert call.operation == "generate"
    assert call.kwargs["model"] == constants.MODEL
    assert call.kwargs["prompt"] == "a red apple"
    assert call.kwargs["quality"] == "low"
    assert call.kwargs["size"] == "1024x1024"
    assert call.kwargs["timeout"] == constants.API_ATTEMPT_TIMEOUT_S
    assert sleeper.delays == []
    for banned in (*FORBIDDEN_REQUEST_KEYS, *constants.OMITTED_EDIT_PARAMS):
        assert banned not in call.kwargs


def test_recorded_edit_call_sends_ordered_references_and_the_mask(
    reference_png: Path,
    mask_png: Path,
    tmp_path: Path,
    fake_factory: FakeClientFactory,
    secret: credentials.Secret,
    budget: api.Budget,
    sleeper: Any,
    no_jitter: Callable[[], float],
) -> None:
    second = write_image(tmp_path, "second.png", size=(16, 16))
    request = models.validate_edit(
        prompt="make the apple green",
        image_paths=[str(reference_png), str(second)],
        mask_path=str(mask_png),
    )
    anyio.run(
        partial(
            api.call_edit,
            request,
            secret=secret,
            budget=budget,
            client_factory=fake_factory,
            sleep=sleeper,
            jitter=no_jitter,
        )
    )

    assert fake_factory.call_count == 1
    call = fake_factory.client.calls[0]
    assert call.operation == "edit"
    assert call.kwargs["model"] == constants.MODEL
    assert [entry[0] for entry in call.kwargs["image"]] == [
        "reference.png",
        "second.png",
    ]
    assert call.kwargs["mask"][0] == "mask.png"
    assert "moderation" not in call.kwargs
    for banned in (*FORBIDDEN_REQUEST_KEYS, *constants.OMITTED_EDIT_PARAMS):
        assert banned not in call.kwargs
