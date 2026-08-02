"""Credential resolution: process environment first, Windows user store second.

Requirements IMG-REQ-005. Two properties matter more than the lookup itself:

* The value never arrives as a tool argument, so no caller can inject one.
* The value cannot be *rendered*. `Secret` returns `<Secret ***>` from
  `__repr__`, `__str__`, and `__format__`, which covers f-strings, `%`
  formatting, `logging`'s lazy `%s`, and the frame reprs a traceback prints.
  Reaching the real value takes a deliberate `.reveal()`.

Resolution is called inside the tool, after validation, immediately before the
client is built — so `tools/list` and every rejected request touch no
credential at all.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Mapping

from . import constants, errors

__all__ = ["Secret", "resolve_api_key", "read_windows_user_env"]


class Secret:
    """A string that refuses to render itself."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "<Secret ***>"

    def __str__(self) -> str:
        return "<Secret ***>"

    def __format__(self, format_spec: str) -> str:
        return "<Secret ***>"

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        # Deliberately not the real length: even a length leaks a little.
        return len("<Secret ***>")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Secret):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:  # pragma: no cover - completeness
        return hash(("Secret", self._value))


def read_windows_user_env(name: str) -> str | None:
    """Read `name` from HKEY_CURRENT_USER\\Environment.

    This is the *persistent* user environment, which is what the user set with
    `setx` or the System Properties dialog. It is deliberately different from
    `os.environ`: a host process started before the variable was set has a
    stale environment, and this fallback is what makes the tool work anyway
    without asking the user to restart everything.

    Returns None on any failure — a missing key, a missing value, a wrong type,
    or a non-Windows platform. Never raises, never logs the value.
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg  # noqa: PLC0415 - Windows-only, imported lazily on purpose
    except ImportError:  # pragma: no cover - defensive
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, constants.WINDOWS_ENV_REGISTRY_KEY
        ) as key:
            value, kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None

    if not isinstance(value, str):
        return None
    if kind == winreg.REG_EXPAND_SZ:
        value = os.path.expandvars(value)
    return value


def resolve_api_key(
    env: Mapping[str, str] | None = None,
    windows_lookup: Callable[[str], str | None] | None = None,
) -> Secret:
    """Return the API key, or raise `missing_credential`.

    Both seams are injectable so the precedence, the Windows fallback, and the
    missing case are all testable on any platform.
    """
    environment = os.environ if env is None else env
    lookup = read_windows_user_env if windows_lookup is None else windows_lookup

    from_process = environment.get(constants.CREDENTIAL_ENV_VAR)
    if from_process and from_process.strip():
        return Secret(from_process.strip())

    from_user_store = lookup(constants.CREDENTIAL_ENV_VAR)
    if from_user_store and from_user_store.strip():
        return Secret(from_user_store.strip())

    raise errors.missing_credential()
