"""Credential resolution and secret opacity — IMG-AC-005 / IMG-REQ-005.

Three properties are under test, and each maps to a clause of the requirement:

* **Precedence.** A non-blank process-scope value wins outright, and the Windows
  user store is only consulted when process scope has nothing usable.
* **Failing closed.** Neither source available means a `missing_credential`
  error that names the variable and carries no value.
* **Opacity.** `Secret` cannot be rendered by any of the paths a real leak takes
  — `repr`, `str`, f-strings, `str.format`, `%`-formatting, container reprs,
  exception messages, and `logging`'s lazy `%s` interpolation.

Everything here is offline and platform-independent: both seams of
`resolve_api_key` are injected, and the one test that needs a platform decision
monkeypatches `sys.platform` rather than requiring a host.
"""

from __future__ import annotations

import logging
import sys
import traceback
from io import StringIO
from typing import Callable

import pytest

from gpt_image_2 import constants, credentials, errors
from gpt_image_2.credentials import Secret

from conftest import CANARY_SECRET  # noqa: E402 - pytest puts this dir on sys.path

KEY = constants.CREDENTIAL_ENV_VAR

PROCESS_VALUE = "sk-process-scope-0000000000000000"
WINDOWS_VALUE = "sk-windows-user-store-11111111111"

MASK = "<Secret ***>"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class RecordingLookup:
    """A `windows_lookup` stand-in that records whether it was consulted."""

    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.names: list[str] = []

    def __call__(self, name: str) -> str | None:
        self.names.append(name)
        return self.value

    @property
    def consulted(self) -> bool:
        return bool(self.names)


def _exploding_lookup(name: str) -> str | None:
    raise AssertionError(
        f"windows_lookup was consulted for {name!r} even though process scope "
        "supplied a usable value."
    )


# ---------------------------------------------------------------------------
# Precedence: process scope wins
# ---------------------------------------------------------------------------


def test_process_scope_wins_over_windows_store() -> None:
    lookup = RecordingLookup(WINDOWS_VALUE)

    secret = credentials.resolve_api_key(env={KEY: PROCESS_VALUE}, windows_lookup=lookup)

    assert isinstance(secret, Secret)
    assert secret.reveal() == PROCESS_VALUE
    assert lookup.consulted is False, "the Windows store must not be read at all"


def test_process_scope_short_circuits_before_the_lookup_runs() -> None:
    """The stronger form: the fallback is not merely ignored, it never runs."""
    secret = credentials.resolve_api_key(
        env={KEY: PROCESS_VALUE}, windows_lookup=_exploding_lookup
    )
    assert secret.reveal() == PROCESS_VALUE


def test_default_env_reads_the_real_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KEY, PROCESS_VALUE)
    lookup = RecordingLookup(WINDOWS_VALUE)

    secret = credentials.resolve_api_key(windows_lookup=lookup)

    assert secret.reveal() == PROCESS_VALUE
    assert lookup.consulted is False


def test_injected_env_is_authoritative_over_os_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An injected mapping must not be silently merged with `os.environ`."""
    monkeypatch.setenv(KEY, "sk-should-never-be-consulted-999999")
    lookup = RecordingLookup(WINDOWS_VALUE)

    secret = credentials.resolve_api_key(env={}, windows_lookup=lookup)

    assert secret.reveal() == WINDOWS_VALUE
    assert lookup.names == [KEY]


# ---------------------------------------------------------------------------
# Fallback: Windows user store
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("env", "case"),
    [
        ({}, "absent"),
        ({"UNRELATED": PROCESS_VALUE}, "other_keys_only"),
        ({KEY: ""}, "empty"),
        ({KEY: " "}, "single_space"),
        ({KEY: "\t"}, "tab"),
        ({KEY: "\n"}, "newline"),
        ({KEY: "  \t\r\n  "}, "whitespace_run"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_blank_or_absent_process_scope_falls_back_to_windows(
    env: dict[str, str], case: str
) -> None:
    lookup = RecordingLookup(WINDOWS_VALUE)

    secret = credentials.resolve_api_key(env=env, windows_lookup=lookup)

    assert secret.reveal() == WINDOWS_VALUE
    assert lookup.names == [KEY], "the fallback must be asked for exactly this name"


def test_default_lookup_is_used_when_none_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`windows_lookup=None` means `read_windows_user_env`, not "no fallback"."""
    calls: list[str] = []

    def fake_reader(name: str) -> str | None:
        calls.append(name)
        return WINDOWS_VALUE

    monkeypatch.setattr(credentials, "read_windows_user_env", fake_reader)

    secret = credentials.resolve_api_key(env={})

    assert secret.reveal() == WINDOWS_VALUE
    assert calls == [KEY]


# ---------------------------------------------------------------------------
# Failing closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("env", "store"),
    [
        ({}, None),
        ({}, ""),
        ({}, "   "),
        ({}, "\t\n"),
        ({KEY: ""}, None),
        ({KEY: "   "}, ""),
        ({KEY: "\n"}, "  \t "),
    ],
)
def test_both_sources_missing_raises_missing_credential(
    env: dict[str, str], store: str | None
) -> None:
    lookup = RecordingLookup(store)

    with pytest.raises(errors.ImageToolError) as excinfo:
        credentials.resolve_api_key(env=env, windows_lookup=lookup)

    assert excinfo.value.code == errors.MISSING_CREDENTIAL
    assert lookup.names == [KEY]


def test_missing_credential_error_names_the_variable_and_leaks_nothing() -> None:
    with pytest.raises(errors.ImageToolError) as excinfo:
        credentials.resolve_api_key(env={}, windows_lookup=RecordingLookup(None))

    error = excinfo.value
    payload = error.to_payload()
    surfaces = (error.message, str(error), repr(error), str(payload))

    assert KEY in error.message, "the message must say which variable to set"
    assert error.code == errors.MISSING_CREDENTIAL
    assert payload["code"] == errors.MISSING_CREDENTIAL
    assert payload["status"] == "error"

    for surface in surfaces:
        for leaked in (CANARY_SECRET, PROCESS_VALUE, WINDOWS_VALUE):
            assert leaked not in surface


def test_missing_credential_carries_no_value_from_either_source() -> None:
    """A blank-but-present value must not be echoed back as "what we found"."""
    with pytest.raises(errors.ImageToolError) as excinfo:
        credentials.resolve_api_key(
            env={KEY: "   "}, windows_lookup=RecordingLookup("  \t ")
        )

    error = excinfo.value
    assert error.details == {}
    assert "   " not in error.message.replace(KEY, "")


def test_missing_credential_is_not_retryable() -> None:
    with pytest.raises(errors.ImageToolError) as excinfo:
        credentials.resolve_api_key(env={}, windows_lookup=RecordingLookup(None))

    assert excinfo.value.retryable is False


# ---------------------------------------------------------------------------
# Whitespace stripping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["  {v}", "{v}  ", "\t{v}\n", "\r\n  {v}  \t"])
@pytest.mark.parametrize("source", ["process", "windows"])
def test_whitespace_is_stripped_from_the_winning_source(raw: str, source: str) -> None:
    padded_process = raw.format(v=PROCESS_VALUE)
    padded_windows = raw.format(v=WINDOWS_VALUE)

    if source == "process":
        env = {KEY: padded_process}
        lookup = RecordingLookup(padded_windows)
        expected = PROCESS_VALUE
    else:
        env = {}
        lookup = RecordingLookup(padded_windows)
        expected = WINDOWS_VALUE

    secret = credentials.resolve_api_key(env=env, windows_lookup=lookup)

    assert secret.reveal() == expected
    assert secret.reveal() == secret.reveal().strip()


def test_interior_whitespace_is_preserved() -> None:
    """Only the edges are trimmed; the value itself is never rewritten."""
    secret = credentials.resolve_api_key(
        env={KEY: "  sk-has interior-space  "}, windows_lookup=RecordingLookup(None)
    )
    assert secret.reveal() == "sk-has interior-space"


# ---------------------------------------------------------------------------
# Secret opacity
# ---------------------------------------------------------------------------

#: The renderings the requirement pins to the exact mask.
EXACT_RENDERERS: dict[str, Callable[[Secret], str]] = {
    "repr": repr,
    "str": str,
    "fstring": lambda s: f"{s}",
    "fstring_repr": lambda s: f"{s!r}",
    "fstring_str_conversion": lambda s: f"{s!s}",
    "format_method": lambda s: "{}".format(s),  # noqa: UP032 - the API under test
    "format_positional": lambda s: "{0}".format(s),  # noqa: UP030 - the API under test
    "format_repr_conversion": lambda s: "{!r}".format(s),  # noqa: UP032
    "format_builtin": lambda s: format(s),
    "percent_bare": lambda s: "%s" % s,
    "percent_tuple": lambda s: "%s" % (s,),
    "percent_repr": lambda s: "%r" % s,
    "percent_mapping": lambda s: "%(key)s" % {"key": s},
}


@pytest.mark.parametrize("name", sorted(EXACT_RENDERERS))
def test_secret_renders_only_the_mask(name: str) -> None:
    rendered = EXACT_RENDERERS[name](Secret(CANARY_SECRET))
    assert rendered == MASK
    assert CANARY_SECRET not in rendered


#: Renderings that must not leak, but whose exact text is not pinned.
LEAKY_SHAPED_RENDERERS: dict[str, Callable[[Secret], str]] = {
    "format_spec_align": lambda s: f"{s:>60}",
    "format_spec_fill": lambda s: f"{s:*^40}",
    "list_repr": lambda s: repr([s]),
    "tuple_repr": lambda s: repr((s,)),
    "dict_repr": lambda s: repr({"api_key": s}),
    "nested_container": lambda s: str({"outer": [{"inner": s}]}),
    "exception_str": lambda s: str(ValueError(s)),
    "exception_repr": lambda s: repr(ValueError(s)),
    "exception_args_repr": lambda s: repr(ValueError(s).args),
    "str_of_object": lambda s: "%s" % (s.__class__.__name__,) + str(s),
}


@pytest.mark.parametrize("name", sorted(LEAKY_SHAPED_RENDERERS))
def test_secret_never_leaks_through_indirect_renderings(name: str) -> None:
    rendered = LEAKY_SHAPED_RENDERERS[name](Secret(CANARY_SECRET))
    assert CANARY_SECRET not in rendered
    assert MASK in rendered


def test_secret_length_does_not_leak_the_real_length() -> None:
    secret = Secret(CANARY_SECRET)

    assert len(secret) == len(MASK)
    assert len(secret) != len(CANARY_SECRET)


@pytest.mark.parametrize(
    "value",
    ["a", "sk-short", CANARY_SECRET, "x" * 512],
    ids=["one_char", "short", "canary", "long"],
)
def test_secret_length_is_constant_across_values(value: str) -> None:
    assert len(Secret(value)) == len(MASK)


def test_reveal_returns_the_real_value() -> None:
    assert Secret(CANARY_SECRET).reveal() == CANARY_SECRET


def test_secrets_with_the_same_value_compare_equal() -> None:
    assert Secret(CANARY_SECRET) == Secret(CANARY_SECRET)
    assert not Secret(CANARY_SECRET) != Secret(CANARY_SECRET)
    assert Secret(CANARY_SECRET) != Secret(PROCESS_VALUE)


def test_equal_secrets_hash_together() -> None:
    assert len({Secret(CANARY_SECRET), Secret(CANARY_SECRET)}) == 1
    assert len({Secret(CANARY_SECRET), Secret(PROCESS_VALUE)}) == 2


@pytest.mark.parametrize("other", [CANARY_SECRET, None, 0, object()])
def test_secret_does_not_compare_equal_to_a_bare_value(other: object) -> None:
    """A plain-string comparison must not become an oracle for the value."""
    assert (Secret(CANARY_SECRET) == other) is False


@pytest.mark.parametrize(
    ("value", "expected"), [("", False), (" ", True), (CANARY_SECRET, True)]
)
def test_secret_truthiness_follows_the_value(value: str, expected: bool) -> None:
    assert bool(Secret(value)) is expected


def test_secret_has_no_instance_dict_to_dump() -> None:
    """`__slots__` is load-bearing: `vars()` is a common accidental leak."""
    with pytest.raises(TypeError):
        vars(Secret(CANARY_SECRET))


def test_resolved_secret_is_opaque_end_to_end() -> None:
    secret = credentials.resolve_api_key(
        env={KEY: CANARY_SECRET}, windows_lookup=RecordingLookup(None)
    )

    assert secret.reveal() == CANARY_SECRET
    for rendered in (repr(secret), str(secret), f"{secret}", "%s" % secret):
        assert rendered == MASK


def test_traceback_of_an_exception_holding_a_secret_stays_clean() -> None:
    secret = Secret(CANARY_SECRET)
    try:
        raise RuntimeError(secret)
    except RuntimeError:
        rendered = traceback.format_exc()

    assert CANARY_SECRET not in rendered
    assert MASK in rendered


# ---------------------------------------------------------------------------
# The realistic leak path: logging
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("msg", "arg_count"),
    [
        ("resolved credential %s", 1),
        ("resolved credential %r", 1),
        ("key=%s repr=%r", 2),
        ("%(api_key)s", 0),
    ],
)
def test_formatter_does_not_emit_the_secret(msg: str, arg_count: int) -> None:
    secret = Secret(CANARY_SECRET)
    # A sole mapping argument is passed as a one-tuple, exactly the way
    # `Logger.warning(msg, {...})` hands it to `LogRecord`.
    args: tuple[object, ...]
    if arg_count == 0:
        args = ({"api_key": secret},)
    else:
        args = tuple(secret for _ in range(arg_count))

    record = logging.LogRecord(
        name="gpt_image_2.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )
    rendered = logging.Formatter("%(levelname)s %(name)s %(message)s").format(record)

    assert CANARY_SECRET not in rendered
    assert MASK in rendered


def test_logger_handler_roundtrip_does_not_emit_the_secret() -> None:
    """A real logger, a real handler, a real stream — the leak path in the wild."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log = logging.getLogger("gpt_image_2.tests.credentials_leak")
    log.propagate = False
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)

    secret = credentials.resolve_api_key(
        env={KEY: CANARY_SECRET}, windows_lookup=RecordingLookup(None)
    )
    try:
        log.warning("using credential %s", secret)
        log.error("credential detail %r for %s", secret, secret)
        log.info("mapping form %(api_key)s", {"api_key": secret})
    finally:
        log.removeHandler(handler)
        handler.close()

    emitted = stream.getvalue()
    assert CANARY_SECRET not in emitted
    assert emitted.count(MASK) == 4


def test_logging_an_exception_holding_a_secret_does_not_emit_it() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log = logging.getLogger("gpt_image_2.tests.credentials_exc_leak")
    log.propagate = False
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)

    try:
        try:
            raise RuntimeError(Secret(CANARY_SECRET))
        except RuntimeError:
            log.exception("credential step failed")
    finally:
        log.removeHandler(handler)
        handler.close()

    emitted = stream.getvalue()
    assert CANARY_SECRET not in emitted
    assert MASK in emitted


# ---------------------------------------------------------------------------
# read_windows_user_env
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin", "cygwin", "emscripten"])
def test_read_windows_user_env_returns_none_off_windows(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setattr(sys, "platform", platform)

    assert credentials.read_windows_user_env(KEY) is None


def test_read_windows_user_env_never_raises_for_an_unset_name() -> None:
    """Read-only, and a miss is None on every platform — never an exception."""
    assert (
        credentials.read_windows_user_env(
            "GPT_IMAGE_2_ABSENT_VARIABLE_9F3C1A4E_DO_NOT_SET"
        )
        is None
    )


class _FakeRegistryKey:
    def __enter__(self) -> "_FakeRegistryKey":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


win32_only = pytest.mark.skipif(
    sys.platform != "win32", reason="winreg exists on Windows only"
)


@win32_only
def test_read_windows_user_env_opens_the_documented_registry_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import winreg

    opened: list[tuple[object, str]] = []

    def fake_open(root: object, path: str):
        opened.append((root, path))
        return _FakeRegistryKey()

    monkeypatch.setattr(winreg, "OpenKey", fake_open)
    monkeypatch.setattr(
        winreg, "QueryValueEx", lambda key, name: (WINDOWS_VALUE, winreg.REG_SZ)
    )

    assert credentials.read_windows_user_env(KEY) == WINDOWS_VALUE
    assert opened == [(winreg.HKEY_CURRENT_USER, constants.WINDOWS_ENV_REGISTRY_KEY)]


@win32_only
@pytest.mark.parametrize(
    "failure",
    [FileNotFoundError("missing key"), PermissionError("denied"), OSError("boom")],
    ids=["missing_key", "denied", "generic_oserror"],
)
def test_read_windows_user_env_swallows_registry_failures(
    monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    import winreg

    def fake_open(root: object, path: str):
        raise failure

    monkeypatch.setattr(winreg, "OpenKey", fake_open)

    assert credentials.read_windows_user_env(KEY) is None


@win32_only
@pytest.mark.parametrize("value", [1234, None, b"bytes", ["list"]])
def test_read_windows_user_env_rejects_non_string_values(
    monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    import winreg

    monkeypatch.setattr(winreg, "OpenKey", lambda root, path: _FakeRegistryKey())
    monkeypatch.setattr(winreg, "QueryValueEx", lambda key, name: (value, winreg.REG_SZ))

    assert credentials.read_windows_user_env(KEY) is None


@win32_only
def test_read_windows_user_env_expands_reg_expand_sz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import winreg

    monkeypatch.setenv("GPT_IMAGE_2_TEST_PREFIX", "sk-expanded")
    monkeypatch.setattr(winreg, "OpenKey", lambda root, path: _FakeRegistryKey())
    monkeypatch.setattr(
        winreg,
        "QueryValueEx",
        lambda key, name: ("%GPT_IMAGE_2_TEST_PREFIX%-tail", winreg.REG_EXPAND_SZ),
    )

    assert credentials.read_windows_user_env(KEY) == "sk-expanded-tail"


@win32_only
def test_read_windows_user_env_queries_the_requested_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import winreg

    queried: list[str] = []

    def fake_query(key: object, name: str):
        queried.append(name)
        return (WINDOWS_VALUE, winreg.REG_SZ)

    monkeypatch.setattr(winreg, "OpenKey", lambda root, path: _FakeRegistryKey())
    monkeypatch.setattr(winreg, "QueryValueEx", fake_query)

    credentials.read_windows_user_env(KEY)

    assert queried == [KEY]


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_public_surface_is_exactly_the_three_documented_names() -> None:
    assert set(credentials.__all__) == {
        "Secret",
        "resolve_api_key",
        "read_windows_user_env",
    }
