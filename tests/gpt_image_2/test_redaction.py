"""The canary suite: secrets and content must never leave this subsystem.

Traces IMG-AC-005 (tail: "a canary secret is absent from logs/results/
exceptions"), IMG-AC-014 (no secret disclosure), IMG-REQ-005, IMG-REQ-007
("results and logs SHALL not echo full prompts ... or base64 payloads"), and
constitution principle 1.

Two canaries are used throughout:

* ``CANARY_SECRET`` from conftest stands in for the resolved API key. It is
  deliberately ``sk-``-shaped so a test can tell the *exact-match* half of
  ``errors.redact`` from the *pattern* half.
* ``PROMPT_CANARY`` stands in for caller content. Prompts are content, not
  diagnostics, so a prompt must never reach a log record even though it is
  perfectly legal inside the outbound request body.

Everything here is offline: ``conftest._block_real_network`` is autouse and the
OpenAI boundary is driven by ``FakeOpenAI`` through an injected client factory.

**Log assertions use ``package_logs``, never ``caplog``.** ``caplog`` installs
its handler on the ROOT logger, and ``server._configure_logging()`` deliberately
sets ``propagate = False`` on the ``gpt_image_2`` logger (constitution
principle 6: stdout is the JSON-RPC channel and our records must not climb into
a host's root handler). So ``caplog.text`` is the empty string here, and every
``assert CANARY_SECRET not in caplog.text`` in this module used to pass
vacuously — it would have stayed green with ``errors.redact`` deleted outright.
``conftest.package_logs`` attaches below the propagation cut, where the records
actually are, and ``test_package_log_capture_sees_a_real_package_record`` is the
positive control that proves the capture is live rather than silently empty.
"""

from __future__ import annotations

import ast
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterator

import anyio
import pytest

import gpt_image_2
from gpt_image_2 import api, constants, credentials, errors, images, server

from conftest import (  # noqa: E402 - pytest puts this directory on sys.path
    CANARY_SECRET,
    FakeClientFactory,
    FakeParsedResponse,
    FakeRawResponse,
    FakeUsage,
    PackageLogCapture,
    RecordingSleep,
    b64_image,
    connection_error,
    status_error,
    timeout_error,
)

#: A distinctive prompt. Content, never a diagnostic.
PROMPT_CANARY = "PROMPTCANARY-a-neon-axolotl-riding-a-unicycle-7f3e"

#: A secret that is *not* key-shaped, so only the exact-match branch can catch it.
OPAQUE_SECRET = "hunter2-correct-horse-battery-staple"

LOG_ROOT = "gpt_image_2"

#: The third-party loggers `_configure_logging()` pins at WARNING no matter what
#: `GPT_IMAGE_2_LOG_LEVEL` says. `openai._base_client` logs the full request
#: options at DEBUG — the prompt, and for an edit the raw reference-image and
#: mask bytes.
NOISY_LOGGERS = ("openai", "httpx", "httpcore")


# ---------------------------------------------------------------------------
# errors.redact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "secret", "forbidden"),
    [
        pytest.param(
            f"the key is {CANARY_SECRET} ok",
            CANARY_SECRET,
            CANARY_SECRET,
            id="exact-supplied-secret",
        ),
        pytest.param(
            f"opaque token {OPAQUE_SECRET} here",
            OPAQUE_SECRET,
            OPAQUE_SECRET,
            id="exact-secret-that-no-pattern-matches",
        ),
        pytest.param(
            "proxy echoed sk-proj-UNTOLD1234567890abcdef back at us",
            None,
            "sk-proj-UNTOLD1234567890abcdef",
            id="pattern-catches-an-sk-token-we-were-never-told",
        ),
        pytest.param(
            "Authorization: Bearer abc123def456",
            None,
            "abc123def456",
            id="pattern-authorization-bearer-header",
        ),
        pytest.param(
            "Bearer abc123def456",
            None,
            "abc123def456",
            id="pattern-bare-bearer-token",
        ),
        pytest.param(
            "api_key=abc123def456",
            None,
            "abc123def456",
            id="pattern-api-key-assignment",
        ),
        pytest.param(
            "API-Key: abc123def456",
            None,
            "abc123def456",
            id="pattern-api-key-header",
        ),
        pytest.param(
            "authorization=abc123def456",
            None,
            "abc123def456",
            id="pattern-authorization-assignment",
        ),
    ],
)
def test_redact_removes_the_secret(text: str, secret: str | None, forbidden: str) -> None:
    result = errors.redact(text, secret)
    assert forbidden not in result
    assert errors.REDACTED in result


@pytest.mark.parametrize(
    "secret",
    [
        pytest.param("l", id="one-char"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank-whitespace"),
        pytest.param("hell", id="four-chars"),
        pytest.param("abc1234", id="seven-chars-just-below-the-floor"),
    ],
)
def test_redact_ignores_a_secret_shorter_than_eight_chars(secret: str) -> None:
    """A one-character "secret" would otherwise shred the whole string."""
    assert errors.redact("hello", secret=secret) == "hello"


def test_redact_uses_a_secret_at_the_eight_char_floor() -> None:
    assert errors.redact("xxabc1234yy", secret="abc1234") == "xxabc1234yy"
    assert errors.redact("xxabcd1234yy", secret="abcd1234") == "xx***yy"


def test_redact_strips_the_secret_before_matching() -> None:
    assert errors.redact(f"a {CANARY_SECRET} b", secret=f"  {CANARY_SECRET}  ") == "a *** b"


def test_redact_truncates_past_the_relayed_message_cap() -> None:
    long_text = "A" * (constants.MAX_RELAYED_MESSAGE_CHARS + 500)
    result = errors.redact(long_text)
    assert len(result) == constants.MAX_RELAYED_MESSAGE_CHARS + 3
    assert result.endswith("...")


def test_redact_truncation_runs_after_scrubbing() -> None:
    """Truncation is the last word, but it must not resurrect a secret."""
    result = errors.redact(f"{CANARY_SECRET} " + "B" * 900, secret=CANARY_SECRET)
    assert CANARY_SECRET not in result
    assert len(result) == constants.MAX_RELAYED_MESSAGE_CHARS + 3
    assert result.endswith("...")


def test_redact_leaves_a_short_message_untouched() -> None:
    assert errors.redact("all clear") == "all clear"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(12345, "12345", id="int"),
        pytest.param(None, "None", id="none"),
        pytest.param(2.5, "2.5", id="float"),
        pytest.param(["a", "b"], "['a', 'b']", id="list"),
    ],
)
def test_redact_stringifies_non_strings(value: object, expected: str) -> None:
    assert errors.redact(value) == expected


def test_redact_cannot_unwrap_a_secret_object() -> None:
    """`Secret` refuses to render, so even a raw redact() call sees nothing."""
    assert errors.redact(credentials.Secret(CANARY_SECRET)) == "<Secret ***>"


# ---------------------------------------------------------------------------
# ImageToolError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("secret_arg", "canary"),
    [
        pytest.param(CANARY_SECRET, CANARY_SECRET, id="told-the-secret"),
        pytest.param(None, CANARY_SECRET, id="never-told-pattern-half-saves-us"),
    ],
)
def test_payload_never_carries_the_canary(secret_arg: str | None, canary: str) -> None:
    exc = errors.ImageToolError(
        errors.USER_ERROR,
        f"Provider said: your key {canary} is wrong",
        request_id="req_1",
        status_code=400,
        details={"field": f"prompt {canary}"},
        secret=secret_arg,
    )
    dumped = json.dumps(exc.to_payload())
    assert canary not in dumped
    assert canary not in str(exc)
    assert canary not in repr(exc)
    assert exc.to_payload()["code"] == errors.USER_ERROR


def test_message_honours_a_secret_no_pattern_could_catch() -> None:
    exc = errors.ImageToolError(
        errors.USER_ERROR,
        f"Provider said: your key {OPAQUE_SECRET} is wrong",
        secret=OPAQUE_SECRET,
    )
    assert OPAQUE_SECRET not in json.dumps(exc.to_payload())


# Regression: _safe_detail dropped the supplied secret, so a key matching no
# pattern survived inside `details` and reached to_payload().
def test_details_honour_the_supplied_secret_too() -> None:
    exc = errors.ImageToolError(
        errors.USER_ERROR,
        "provider rejected the request",
        details={"field": f"prompt {OPAQUE_SECRET}"},
        secret=OPAQUE_SECRET,
    )
    assert OPAQUE_SECRET not in json.dumps(exc.to_payload())


def test_payload_shape_is_the_closed_contract() -> None:
    payload = errors.ImageToolError(
        errors.RATE_LIMITED, "slow down", request_id="req_2", status_code=429
    ).to_payload()
    assert payload == {
        "status": "error",
        "code": errors.RATE_LIMITED,
        "message": "slow down",
        "request_id": "req_2",
        "status_code": 429,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, None, id="none-stays-none"),
        pytest.param(True, True, id="bool-stays-bool"),
        pytest.param(7, 7, id="int-stays-int"),
        pytest.param(1.5, 1.5, id="float-stays-float"),
    ],
)
def test_scalar_details_pass_through_unchanged(value: Any, expected: Any) -> None:
    exc = errors.ImageToolError(errors.INVALID_REQUEST, "nope", details={"v": value})
    assert exc.details["v"] == expected
    assert type(exc.details["v"]) is type(expected)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({"key": CANARY_SECRET}, id="dict"),
        pytest.param([CANARY_SECRET, "x"], id="list"),
        pytest.param((CANARY_SECRET,), id="tuple"),
        pytest.param({CANARY_SECRET}, id="set"),
    ],
)
def test_collection_details_are_stringified_and_redacted(value: Any) -> None:
    exc = errors.ImageToolError(errors.INVALID_REQUEST, "nope", details={"v": value})
    assert isinstance(exc.details["v"], str)
    assert CANARY_SECRET not in exc.details["v"]
    assert CANARY_SECRET not in json.dumps(exc.to_payload())


def test_unknown_code_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        errors.ImageToolError("not_a_real_code", "whatever")


@pytest.mark.parametrize("code", sorted(errors.ERROR_CODES))
def test_every_closed_code_constructs_and_reports_its_retryability(code: str) -> None:
    exc = errors.ImageToolError(code, "message")
    assert exc.to_payload()["code"] == code
    assert exc.retryable is (code not in errors.NON_RETRYABLE_CODES)


def test_internal_error_relays_neither_the_canary_nor_the_exception_text() -> None:
    exc = errors.internal_error(ValueError(CANARY_SECRET))
    dumped = json.dumps(exc.to_payload())
    assert CANARY_SECRET not in dumped
    assert exc.details["exception_type"] == "ValueError"
    assert exc.code == errors.INTERNAL_ERROR


def test_internal_error_relays_no_exception_message_at_all() -> None:
    marker = "EXCTEXTCANARY-do-not-relay"
    exc = errors.internal_error(ValueError(f"{marker} {CANARY_SECRET}"))
    dumped = json.dumps(exc.to_payload())
    assert marker not in dumped
    assert CANARY_SECRET not in dumped
    assert exc.details["exception_type"] == "ValueError"


def test_missing_credential_names_the_variable_but_holds_no_value() -> None:
    exc = errors.missing_credential()
    dumped = json.dumps(exc.to_payload())
    assert constants.CREDENTIAL_ENV_VAR in dumped
    assert CANARY_SECRET not in dumped
    assert exc.code == errors.MISSING_CREDENTIAL


# ---------------------------------------------------------------------------
# Secret rendering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "render",
    [
        pytest.param(repr, id="repr"),
        pytest.param(str, id="str"),
        pytest.param(lambda s: f"{s}", id="f-string"),
        pytest.param(lambda s: f"{s!s}", id="f-string-str-conversion"),
        pytest.param(lambda s: "%s" % (s,), id="percent-format"),
        pytest.param(lambda s: format(s, ">40"), id="format-spec"),
        pytest.param(lambda s: "".join([str(s)]), id="join"),
    ],
)
def test_secret_refuses_to_render(render: Callable[[Any], str]) -> None:
    rendered = render(credentials.Secret(CANARY_SECRET))
    assert CANARY_SECRET not in rendered
    assert "<Secret ***>" in rendered


def test_secret_length_does_not_leak_the_real_length() -> None:
    assert len(credentials.Secret(CANARY_SECRET)) == len("<Secret ***>")


def test_logging_lazy_formatting_of_a_secret_stays_redacted(
    package_logs: PackageLogCapture,
) -> None:
    """`logging`'s lazy `%s` must reach `Secret.__str__`, not the raw value.

    Migrated from `caplog`, which saw nothing at all here: the assertion that
    the secret is absent was passing on an empty string. `package_logs` sits on
    the `gpt_image_2` logger itself, so the `<Secret ***>` half of this test is
    now real evidence that the record was captured and formatted.
    """
    logging.getLogger(f"{LOG_ROOT}.probe").warning(
        "resolved=%s", credentials.Secret(CANARY_SECRET)
    )
    assert package_logs.records, "the capture saw nothing; the assertion below is vacuous"
    assert CANARY_SECRET not in package_logs.text
    assert "<Secret ***>" in package_logs.text


# ---------------------------------------------------------------------------
# Positive control: the capture fixture is not silently empty
# ---------------------------------------------------------------------------


def test_package_log_capture_sees_a_real_package_record(
    package_logs: PackageLogCapture,
) -> None:
    """The control every negative log assertion in this module leans on.

    A capture that quietly records nothing is indistinguishable from a clean
    run: `assert SECRET not in package_logs.text` is green either way. This
    emits one record under the package logger and proves the fixture sees it,
    formats it, and exposes it through both `.text` and `.messages`.

    Catches: reverting `package_logs` to `caplog` (or otherwise moving the
    handler back above the `propagate = False` cut), which turns `.text` into
    the empty string and every leak assertion in this file into a no-op.
    """
    logging.getLogger(f"{LOG_ROOT}.control").warning("control-marker n=%d", 7)

    assert len(package_logs.records) == 1
    assert package_logs.messages == ["control-marker n=7"]
    assert "control-marker n=7" in package_logs.text
    assert "WARNING" in package_logs.text
    assert f"{LOG_ROOT}.control" in package_logs.text


def test_package_log_capture_starts_empty_and_clears(
    package_logs: PackageLogCapture,
) -> None:
    """`.clear()` really empties both views, so a capture cannot lie by staleness."""
    assert package_logs.records == []
    assert package_logs.text == ""

    logging.getLogger(f"{LOG_ROOT}.control").error("first")
    assert package_logs.messages == ["first"]

    package_logs.clear()
    assert package_logs.records == []
    assert package_logs.text == ""


# ---------------------------------------------------------------------------
# server._configure_logging()
#
# A verbosity knob is a security control here: DEBUG on the wrong logger makes
# `openai._base_client` dump the prompt and the raw reference-image bytes to
# stderr. Every test below restores the global logging state it touches, so the
# order tests run in cannot matter.
# ---------------------------------------------------------------------------


@pytest.fixture
def logging_state() -> Iterator[None]:
    """Snapshot and restore every logger `_configure_logging()` may mutate."""
    watched = [
        logging.getLogger(),
        logging.getLogger(LOG_ROOT),
        *(logging.getLogger(name) for name in NOISY_LOGGERS),
    ]
    saved = [(lg, lg.level, lg.propagate, list(lg.handlers)) for lg in watched]
    try:
        yield
    finally:
        for logger, level, propagate, handlers in saved:
            # Assign into the live list so any reference held elsewhere sees the
            # restored state.
            logger.handlers[:] = handlers
            logger.setLevel(level)
            logger.propagate = propagate


def test_configure_logging_pins_third_party_loggers_at_warning(
    monkeypatch: pytest.MonkeyPatch, logging_state: None
) -> None:
    """DEBUG for us is never DEBUG for the SDK.

    The loggers are pushed to DEBUG first, so passing requires
    `_configure_logging()` to actively pin them back — inheriting WARNING from
    an untouched root would not be enough.

    Catches: reverting to `logging.basicConfig(level=...)`, which sets the level
    on ROOT and leaves `openai`/`httpx` free to log at DEBUG, putting the user's
    prompt and raw reference-image bytes on stderr (constitution principle 1).
    """
    monkeypatch.setenv("GPT_IMAGE_2_LOG_LEVEL", "DEBUG")
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)

    server._configure_logging()

    assert logging.getLogger(LOG_ROOT).level == logging.DEBUG
    for name in NOISY_LOGGERS:
        logger = logging.getLogger(name)
        assert logger.level == logging.WARNING, f"{name} was not pinned"
        assert not logger.isEnabledFor(logging.DEBUG), f"{name} would log at DEBUG"


def test_configure_logging_leaves_the_root_logger_alone(
    monkeypatch: pytest.MonkeyPatch, logging_state: None
) -> None:
    """The knob is package-scoped. Root keeps whatever the host chose.

    Root's handlers are cleared first to reproduce a real server start, which is
    also the only condition under which `logging.basicConfig()` would do
    anything at all (it no-ops when root already has handlers, as it does under
    pytest). Without that, this test could not tell the fix from the bug.

    Catches: reverting to `logging.basicConfig(level=DEBUG)`, which sets ROOT to
    DEBUG and attaches a root StreamHandler — switching on DEBUG for every
    third-party library in the process.
    """
    monkeypatch.setenv("GPT_IMAGE_2_LOG_LEVEL", "DEBUG")
    root = logging.getLogger()
    root.handlers[:] = []
    root.setLevel(logging.WARNING)
    logging.getLogger(LOG_ROOT).setLevel(logging.NOTSET)

    server._configure_logging()

    assert logging.getLogger(LOG_ROOT).level == logging.DEBUG
    assert root.level == logging.WARNING
    assert root.handlers == [], "the handler belongs on the package logger, not root"
    assert not root.isEnabledFor(logging.DEBUG)


def test_configure_logging_keeps_package_records_off_the_root_logger(
    monkeypatch: pytest.MonkeyPatch, logging_state: None
) -> None:
    """`propagate = False` is load-bearing, not tidiness.

    A host may have installed a root handler that writes to stdout, which is the
    JSON-RPC channel (constitution principle 6). This is also the reason
    `caplog` cannot be used in this module.
    """
    monkeypatch.setenv("GPT_IMAGE_2_LOG_LEVEL", "DEBUG")
    package = logging.getLogger(LOG_ROOT)
    package.propagate = True  # the state the fix must undo
    root = logging.getLogger()
    root_sink = PackageLogCapture()
    root.handlers[:] = [root_sink]
    root.setLevel(logging.DEBUG)

    server._configure_logging()
    logging.getLogger(f"{LOG_ROOT}.probe").warning("must-not-climb-to-root")

    assert package.propagate is False
    assert root_sink.records == []
    assert "must-not-climb-to-root" not in root_sink.text


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        pytest.param("DEBUG", logging.DEBUG, id="canonical-uppercase"),
        pytest.param("info", logging.INFO, id="lowercase-is-normalised"),
        pytest.param("  WaRnInG  ", logging.WARNING, id="mixed-case-and-padding"),
        pytest.param("nonsense", logging.WARNING, id="garbage-falls-back-to-warning"),
        pytest.param("", logging.WARNING, id="empty-falls-back-to-warning"),
        pytest.param("15", logging.WARNING, id="numeric-string-falls-back-to-warning"),
    ],
)
def test_configure_logging_normalises_the_level_and_never_raises(
    monkeypatch: pytest.MonkeyPatch,
    logging_state: None,
    requested: str,
    expected: int,
) -> None:
    """An operator's typo must not kill the server at startup.

    Root's handlers are cleared for the same reason as the test above: this
    function runs at import, when root has none, and that is the only state in
    which `logging.basicConfig()` does anything. Leaving pytest's root handler
    in place would make `basicConfig` a silent no-op and the "must not raise"
    half of this test would prove nothing.

    Catches: reverting to `logging.basicConfig(level=os.environ.get(...))`,
    where `"info"`, `"nonsense"`, `"15"`, and `""` all raise `ValueError:
    Unknown level` — at import, so the MCP server dies with a traceback instead
    of serving.
    """
    monkeypatch.setenv("GPT_IMAGE_2_LOG_LEVEL", requested)
    root = logging.getLogger()
    root.handlers[:] = []
    root.setLevel(logging.WARNING)
    logging.getLogger(LOG_ROOT).setLevel(logging.NOTSET)

    server._configure_logging()  # must not raise

    assert logging.getLogger(LOG_ROOT).level == expected
    assert root.level == logging.WARNING


def test_configure_logging_is_idempotent_about_handlers(
    monkeypatch: pytest.MonkeyPatch, logging_state: None
) -> None:
    """Repeated configuration must not multiply handlers, and never uses stdout."""
    monkeypatch.setenv("GPT_IMAGE_2_LOG_LEVEL", "INFO")
    package = logging.getLogger(LOG_ROOT)
    package.handlers[:] = []

    server._configure_logging()
    after_first = list(package.handlers)
    server._configure_logging()

    assert len(after_first) == 1
    assert package.handlers == after_first
    handler = after_first[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is not sys.stdout, "stdout is the JSON-RPC channel"


# ---------------------------------------------------------------------------
# End-to-end leak hunt
# ---------------------------------------------------------------------------


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    factory: FakeClientFactory,
    sleeper: RecordingSleep,
) -> None:
    """Route the server's API calls through the fake client.

    `api.build_client` is late-bound now, so `monkeypatch.setattr(api,
    "build_client", ...)` would reach the transport — but only the transport.
    Wrapping `call_generate`/`call_edit` also injects the recording `sleep` and
    a zero `jitter`, which is what keeps the retrying failure cases (429, 5xx)
    from actually waiting two seconds each. Every real code path — retry,
    mapping, logging, publication — still runs.
    """
    real_generate = api.call_generate
    real_edit = api.call_edit

    async def generate(request: Any, *, secret: Any, budget: Any, **_ignored: Any) -> Any:
        return await real_generate(
            request,
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=lambda: 0.0,
        )

    async def edit(request: Any, *, secret: Any, budget: Any, **_ignored: Any) -> Any:
        return await real_edit(
            request,
            secret=secret,
            budget=budget,
            client_factory=factory,
            sleep=sleeper,
            jitter=lambda: 0.0,
        )

    monkeypatch.setattr(api, "call_generate", generate)
    monkeypatch.setattr(api, "call_edit", edit)


def _generate(**kwargs: Any) -> list:
    """Drive the async tool from a plain sync test (no pytest-asyncio here)."""

    async def main() -> list:
        return await server.generate_image(**kwargs)

    return anyio.run(main)


@pytest.fixture
def leak_harness(
    monkeypatch: pytest.MonkeyPatch,
    fake_factory: FakeClientFactory,
    sleeper: RecordingSleep,
    package_logs: PackageLogCapture,
) -> FakeClientFactory:
    """Credential in the environment, fake transport, live package log capture.

    `package_logs` is a dependency rather than a per-test opt-in so that the
    package logger is at DEBUG for every harness test — nothing this suite
    asserts about logs can be hidden by whatever `GPT_IMAGE_2_LOG_LEVEL`
    resolved to at import.
    """
    monkeypatch.setenv(constants.CREDENTIAL_ENV_VAR, CANARY_SECRET)
    _wire(monkeypatch, fake_factory, sleeper)
    return fake_factory


PROVIDER_FAILURES: list[Any] = [
    pytest.param(
        lambda: status_error(400, f"invalid parameter, key was {CANARY_SECRET}"),
        errors.USER_ERROR,
        id="user-error-400",
    ),
    pytest.param(
        lambda: status_error(
            400,
            "Your request was rejected as a result of our safety system. "
            f"Debug key {CANARY_SECRET}",
            code="content_policy_violation",
        ),
        errors.MODERATION_BLOCKED,
        id="moderation-block",
    ),
    pytest.param(
        lambda: status_error(401, f"Incorrect API key provided: {CANARY_SECRET}"),
        errors.AUTHENTICATION_ERROR,
        id="authentication-error",
    ),
    pytest.param(
        lambda: status_error(403, f"org not verified {CANARY_SECRET}"),
        errors.ACCESS_DENIED,
        id="access-denied",
    ),
    pytest.param(
        lambda: status_error(429, f"slow down {CANARY_SECRET}"),
        errors.RATE_LIMITED,
        id="rate-limited-after-retry",
    ),
    pytest.param(
        lambda: status_error(500, f"upstream exploded {CANARY_SECRET}"),
        errors.SERVICE_ERROR,
        id="service-error-after-retry",
    ),
    pytest.param(lambda: timeout_error(), errors.API_TIMEOUT, id="timeout"),
    pytest.param(lambda: connection_error(), errors.CONNECTION_ERROR, id="connection"),
    pytest.param(
        lambda: RuntimeError(f"kaboom {CANARY_SECRET}"),
        errors.INTERNAL_ERROR,
        id="unexpected-exception-from-the-transport",
    ),
]


@pytest.mark.parametrize(("make_failure", "expected_code"), PROVIDER_FAILURES)
def test_failing_generate_leaks_nothing(
    make_failure: Callable[[], BaseException],
    expected_code: str,
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    """The whole failure surface: raised ToolError plus every log record."""
    leak_harness.client.script = [make_failure()]

    with pytest.raises(Exception) as excinfo:
        _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))

    raised = str(excinfo.value)
    payload = json.loads(raised)

    assert payload["code"] == expected_code
    assert payload["status"] == "error"
    assert CANARY_SECRET not in raised
    assert PROMPT_CANARY not in raised
    # `api._call_with_retry` logs a warning on every failure path, so the log
    # assertions below have real text to inspect. Assert that first: without it
    # an empty capture would make them pass while proving nothing.
    assert package_logs.records, "no record captured; the leak assertions would be vacuous"
    assert CANARY_SECRET not in package_logs.text
    assert PROMPT_CANARY not in package_logs.text


@pytest.mark.parametrize(("make_failure", "expected_code"), PROVIDER_FAILURES)
def test_failing_generate_writes_no_file(
    make_failure: Callable[[], BaseException],
    expected_code: str,
    leak_harness: FakeClientFactory,
    out_dir: Path,
) -> None:
    leak_harness.client.script = [make_failure()]

    with pytest.raises(Exception):
        _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))

    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_moderation_block_is_not_retried_and_stays_redacted(
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    leak_harness.client.script = [
        status_error(
            400,
            f"rejected as a result of our safety system ({CANARY_SECRET})",
            code="moderation_blocked",
            headers={"x-request-id": "req_moderation"},
        )
    ]

    with pytest.raises(Exception) as excinfo:
        _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))

    payload = json.loads(str(excinfo.value))
    assert payload["code"] == errors.MODERATION_BLOCKED
    assert payload["request_id"] == "req_moderation"
    assert leak_harness.call_count == 1, "a moderation block must never be retried"
    assert CANARY_SECRET not in json.dumps(payload)
    assert PROMPT_CANARY not in json.dumps(payload)
    assert package_logs.records, "no record captured; the leak assertions would be vacuous"
    assert CANARY_SECRET not in package_logs.text
    assert PROMPT_CANARY not in package_logs.text
    # The safe diagnostic really is written: code and request id, nothing else.
    assert "req_moderation" in package_logs.text


def test_missing_credential_path_logs_nothing_sensitive(
    monkeypatch: pytest.MonkeyPatch,
    fake_factory: FakeClientFactory,
    sleeper: RecordingSleep,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    monkeypatch.delenv(constants.CREDENTIAL_ENV_VAR, raising=False)
    monkeypatch.setattr(credentials, "read_windows_user_env", lambda _name: None)
    _wire(monkeypatch, fake_factory, sleeper)

    with pytest.raises(Exception) as excinfo:
        _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))

    payload = json.loads(str(excinfo.value))
    assert payload["code"] == errors.MISSING_CREDENTIAL
    # A `missing_credential` is already an ImageToolError, so `server._fail`
    # logs nothing at all: this path is expected to be silent, and the strong
    # assertion is that it stays silent rather than that a record is clean.
    assert package_logs.records == []
    assert CANARY_SECRET not in package_logs.text
    assert PROMPT_CANARY not in package_logs.text
    assert fake_factory.call_count == 0
    assert fake_factory.secrets_seen == []


def test_successful_generate_logs_no_prompt_no_payload_no_secret(
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    payload_b64 = b64_image()
    leak_harness.client.script = [
        FakeRawResponse(
            FakeParsedResponse(
                [payload_b64],
                usage=FakeUsage(),
                revised_prompt="a redrawn description",
            )
        )
    ]

    result = _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))
    metadata = result[-1]

    assert metadata["status"] == "ok"
    saved = Path(metadata["images"][0]["path"])
    assert saved.is_file()

    # The outbound request legitimately carries the prompt...
    assert leak_harness.client.last_kwargs["prompt"] == PROMPT_CANARY
    # ...but nothing else may. The success path logs an INFO line, so there is
    # real captured text behind these three assertions.
    assert "generate ok" in package_logs.text
    assert PROMPT_CANARY not in package_logs.text
    assert CANARY_SECRET not in package_logs.text
    assert payload_b64[:48] not in package_logs.text
    dumped = json.dumps(metadata, default=str)
    assert PROMPT_CANARY not in dumped
    assert CANARY_SECRET not in dumped
    assert payload_b64[:48] not in dumped


# ---------------------------------------------------------------------------
# revised_prompt: provider-controlled text, treated like any other
# ---------------------------------------------------------------------------

#: A provider "revised prompt" doing both things a hostile or broken service
#: could do at once: echo a key back at us, and hand us 20 KB of text.
POISONED_REVISED_PROMPT = "sk-proj-" + "A" * 40 + "X" * 20_000

#: `errors.redact` appends "..." after truncating, so the bound is the cap plus
#: that ellipsis. The slack keeps the assertion about the *bound* rather than
#: about three characters.
_LENGTH_SLACK = 8


def test_revised_prompt_is_scrubbed_before_it_reaches_the_caller(
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    """`revised_prompt` is provider-controlled text, so it gets redacted.

    Catches: reverting `api._read_payloads` to `revised = str(candidate)`, which
    relayed the value verbatim — unbounded and unscrubbed — straight into the
    tool's metadata and therefore into the agent's context.
    """
    leak_harness.client.script = [
        FakeRawResponse(
            FakeParsedResponse(
                [b64_image()],
                usage=FakeUsage(),
                revised_prompt=POISONED_REVISED_PROMPT,
            )
        )
    ]

    metadata = _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))[-1]
    revised = metadata["revised_prompt"]

    assert revised is not None, "the field is still relayed, just safely"
    assert "sk-" not in revised
    assert errors.REDACTED in revised
    assert len(revised) <= constants.MAX_RELAYED_MESSAGE_CHARS + _LENGTH_SLACK
    # And nothing smuggled the blob in through another field.
    dumped = json.dumps(metadata, default=str)
    assert "sk-proj-" not in dumped
    assert POISONED_REVISED_PROMPT[:64] not in dumped


def test_revised_prompt_is_length_bounded_even_with_nothing_to_scrub(
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    """The cap is independent of the scrub.

    The poisoned case above collapses to `***` because the whole token matches
    the key pattern, so on its own it could not tell truncation from
    substitution. This one carries no secret at all: only the length bound can
    make it pass.

    Catches: reverting to `revised = str(candidate)`, or relaying with
    `max_chars=None`.
    """
    clean_but_huge = "R" * 20_000
    leak_harness.client.script = [
        FakeRawResponse(
            FakeParsedResponse([b64_image()], revised_prompt=clean_but_huge)
        )
    ]

    metadata = _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))[-1]
    revised = metadata["revised_prompt"]

    assert len(revised) == constants.MAX_RELAYED_MESSAGE_CHARS + 3
    assert revised.endswith("...")
    assert revised.startswith("R")


def test_a_short_revised_prompt_survives_intact(
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    """Redaction must not be a synonym for discarding the field (IMG-REQ-007)."""
    leak_harness.client.script = [
        FakeRawResponse(
            FakeParsedResponse([b64_image()], revised_prompt="a redrawn description")
        )
    ]

    metadata = _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))[-1]

    assert metadata["revised_prompt"] == "a redrawn description"


def test_output_failure_payload_carries_no_base64(
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    """A wrong-format response must be reported without echoing the payload."""
    payload_b64 = b64_image(fmt="jpeg")
    leak_harness.client.script = [
        FakeRawResponse(FakeParsedResponse([payload_b64]))
    ]

    with pytest.raises(Exception) as excinfo:
        _generate(prompt=PROMPT_CANARY, output_format="png", output_dir=str(out_dir))

    raised = str(excinfo.value)
    payload = json.loads(raised)
    assert payload["code"] == errors.OUTPUT_ERROR
    assert payload_b64[:48] not in raised
    assert PROMPT_CANARY not in raised
    # A decode failure is an ImageToolError, so this path is silent by design.
    assert package_logs.records == []
    assert payload_b64[:48] not in package_logs.text
    assert PROMPT_CANARY not in package_logs.text
    assert CANARY_SECRET not in package_logs.text


def test_local_validation_failure_never_touches_the_credential(
    monkeypatch: pytest.MonkeyPatch,
    fake_factory: FakeClientFactory,
    sleeper: RecordingSleep,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    monkeypatch.setenv(constants.CREDENTIAL_ENV_VAR, CANARY_SECRET)
    _wire(monkeypatch, fake_factory, sleeper)

    def _explode(*_a: Any, **_k: Any):  # pragma: no cover - must never run
        raise AssertionError("credential resolved before local validation finished")

    monkeypatch.setattr(credentials, "resolve_api_key", _explode)

    with pytest.raises(Exception) as excinfo:
        _generate(prompt=PROMPT_CANARY, background="transparent", output_dir=str(out_dir))

    payload = json.loads(str(excinfo.value))
    assert payload["code"] == errors.UNSUPPORTED_OPTION
    assert fake_factory.call_count == 0
    assert CANARY_SECRET not in package_logs.text
    assert PROMPT_CANARY not in package_logs.text


def _boom_publish(*_args: Any, **_kwargs: Any):
    raise RuntimeError(f"disk exploded while holding {CANARY_SECRET}")


def test_unexpected_failure_outside_the_api_returns_a_clean_payload(
    monkeypatch: pytest.MonkeyPatch,
    leak_harness: FakeClientFactory,
    out_dir: Path,
) -> None:
    leak_harness.client.script = [FakeRawResponse(FakeParsedResponse([b64_image()]))]
    monkeypatch.setattr(images, "publish_atomic", _boom_publish)

    with pytest.raises(Exception) as excinfo:
        _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))

    raised = str(excinfo.value)
    payload = json.loads(raised)
    assert payload["code"] == errors.INTERNAL_ERROR
    assert payload["details"]["exception_type"] == "RuntimeError"
    assert CANARY_SECRET not in raised
    assert PROMPT_CANARY not in raised


# Regression: server._fail used log.exception(), writing the raw traceback
# (including str(exc)) to stderr unscrubbed. It now redacts the formatted
# traceback instead.
def test_unexpected_failure_outside_the_api_logs_no_secret(
    monkeypatch: pytest.MonkeyPatch,
    leak_harness: FakeClientFactory,
    package_logs: PackageLogCapture,
    out_dir: Path,
) -> None:
    leak_harness.client.script = [FakeRawResponse(FakeParsedResponse([b64_image()]))]
    monkeypatch.setattr(images, "publish_atomic", _boom_publish)

    with pytest.raises(Exception):
        _generate(prompt=PROMPT_CANARY, output_dir=str(out_dir))

    # This is the one path that deliberately logs a whole traceback, so it is
    # also the only place the scrubbing can be observed doing work. Prove the
    # traceback was written *and* that the secret inside it was replaced —
    # under `caplog` both facts were invisible.
    assert package_logs.records, "the traceback was never logged"
    text = package_logs.text
    assert "RuntimeError" in text
    assert "disk exploded while holding" in text
    assert errors.REDACTED in text
    assert CANARY_SECRET not in text


# ---------------------------------------------------------------------------
# Source-level guard: stdout is the JSON-RPC channel
# ---------------------------------------------------------------------------

PACKAGE_DIR = Path(gpt_image_2.__file__).resolve().parent
SOURCE_FILES = sorted(PACKAGE_DIR.glob("*.py"))


def _parse(source: Path) -> ast.Module:
    return ast.parse(source.read_text(encoding="utf-8"), filename=str(source))


def test_the_package_has_source_files_to_scan() -> None:
    assert len(SOURCE_FILES) >= 6


@pytest.mark.parametrize("source", SOURCE_FILES, ids=lambda p: p.name)
def test_no_print_call_anywhere_in_the_package(source: Path) -> None:
    """`print(` in a docstring is fine; a real `print()` call is not.

    Matching the literal text would trip over `server.py`'s own "Never
    `print()`" warning, so the check walks the AST for a genuine call.
    """
    offenders = [
        node.lineno
        for node in ast.walk(_parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert offenders == [], f"{source.name} calls print() at lines {offenders}"


@pytest.mark.parametrize("source", SOURCE_FILES, ids=lambda p: p.name)
def test_nothing_in_the_package_reaches_for_stdout(source: Path) -> None:
    offenders = [
        node.lineno
        for node in ast.walk(_parse(source))
        if isinstance(node, ast.Attribute) and node.attr in {"stdout", "__stdout__"}
    ]
    assert offenders == [], f"{source.name} touches stdout at lines {offenders}"


#: The package's own key shape, reused so this guard cannot drift from it.
_KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


@pytest.mark.parametrize("source", SOURCE_FILES, ids=lambda p: p.name)
def test_no_module_embeds_a_key_shaped_literal(source: Path) -> None:
    """`errors.py` may describe the `sk-` shape; no file may contain one."""
    text = source.read_text(encoding="utf-8")
    found = _KEY_SHAPE.findall(text)
    assert found == [], f"{source.name} embeds key-shaped literals {found}"
    assert CANARY_SECRET not in text
