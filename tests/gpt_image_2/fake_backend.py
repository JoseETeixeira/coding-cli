"""Test-only fake backend, imported *inside* the spawned stdio server process.

`mcp_smoke.py` launches the real launcher (`run_gpt_image_2_server.py`) as a
child process and asks it to `import fake_backend` first. This module then swaps
exactly two seams, and installs one tripwire:

* ``gpt_image_2.api.build_client`` — replaced by a client that returns a real,
  tiny PNG as base64 and never opens a socket.
* ``gpt_image_2.credentials.resolve_api_key`` — replaced by a constant fake
  ``Secret``, so the smoke needs no credential and can never read the
  operator's real key out of the process environment or the Windows user
  environment store.
* ``openai.AsyncOpenAI`` — replaced by a hard failure, mirroring the autouse
  `_block_real_network` guard in `conftest.py`. Nothing in this smoke may
  construct a real client, so if the `build_client` seam ever stops being the
  only route to one, the child dies loudly instead of quietly reaching the
  network with the operator's inherited credential.

The production package deliberately has **no** environment-variable "fake mode"
switch, and must never grow one. This module is the proof that the seam lives
entirely in the test tree: `gpt_image_2/` is untouched.

Note on the patch, and why `install()` asserts a shape:

`api._call_with_retry` used to capture `build_client` as a keyword-only
*default* (`client_factory: Callable = build_client`), and Python binds defaults
at definition time — so rebinding the module attribute alone was a **no-op** for
`server.py`, which calls `api.call_generate(...)` without a `client_factory`.
This module papered over that by also rewriting `__kwdefaults__`, which meant
the smoke passed while the seam every unit test relies on
(`monkeypatch.setattr(api, "build_client", ...)`) was silently dead.

`api` now defaults `client_factory` to `None` and resolves `build_client` inside
the call, so the attribute patch is sufficient and honest. The `__kwdefaults__`
rewrite is gone on purpose, and `_require_late_bound_factory()` fails the child
immediately if that eager default ever comes back.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import openai
from PIL import Image as PILImage

from gpt_image_2 import api, credentials

__all__ = ["FAKE_REQUEST_ID", "calls", "installed"]

#: Reported back through `x-request-id` so the smoke can prove the header path
#: is wired without a real provider.
FAKE_REQUEST_ID = "req_fake_stdio_smoke"

#: A syntactically plausible but obviously fake key. Never a real credential.
FAKE_KEY = "sk-fake-stdio-smoke-0000000000000000"

#: Every request the server would have sent, recorded in-process only.
calls: list[tuple[str, dict[str, Any]]] = []

_PIL_FORMAT = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}


def _encoded_image(output_format: str) -> str:
    """A real, decodable 64x64 image in the format the caller asked for."""
    buffer = BytesIO()
    PILImage.new("RGB", (64, 64), (12, 84, 160)).save(
        buffer, format=_PIL_FORMAT.get(output_format, "PNG")
    )
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _FakeEntry:
    def __init__(self, b64_json: str, revised_prompt: str | None) -> None:
        self.b64_json = b64_json
        self.revised_prompt = revised_prompt
        self.url = None


class _FakeUsage:
    input_tokens = 7
    output_tokens = 9
    total_tokens = 16


class _FakeParsed:
    def __init__(self, payloads: list[str], revised_prompt: str | None) -> None:
        self.data = [
            _FakeEntry(payload, revised_prompt if index == 0 else None)
            for index, payload in enumerate(payloads)
        ]
        self.usage = _FakeUsage()


class _FakeRaw:
    """Stands in for `openai._response.AsyncAPIResponse`.

    `parse()` is synchronous on purpose: `api._maybe_await` must tolerate a
    plain value as well as a coroutine.
    """

    def __init__(self, parsed: _FakeParsed) -> None:
        self._parsed = parsed
        self.headers = {"x-request-id": FAKE_REQUEST_ID}

    def parse(self) -> _FakeParsed:
        return self._parsed


class _FakeRawOps:
    async def generate(self, **kwargs: Any) -> _FakeRaw:
        return _respond("generate", kwargs)

    async def edit(self, **kwargs: Any) -> _FakeRaw:
        return _respond("edit", kwargs)


class _FakeImages:
    def __init__(self) -> None:
        self.with_raw_response = _FakeRawOps()


class FakeAsyncClient:
    """The whole surface `gpt_image_2.api` touches, and nothing more."""

    def __init__(self) -> None:
        self.images = _FakeImages()


def _respond(operation: str, kwargs: dict[str, Any]) -> _FakeRaw:
    calls.append((operation, dict(kwargs)))
    output_format = str(kwargs.get("output_format") or "png")
    count = int(kwargs.get("n") or 1)
    payloads = [_encoded_image(output_format) for _ in range(count)]
    return _FakeRaw(_FakeParsed(payloads, "a fake revised prompt"))


def fake_build_client(secret: Any) -> FakeAsyncClient:
    """`build_client` replacement. Reads the secret exactly like the real one."""
    secret.reveal()
    return FakeAsyncClient()


def fake_resolve_api_key(*_args: Any, **_kwargs: Any) -> credentials.Secret:
    return credentials.Secret(FAKE_KEY)


def _blocked_async_openai(*_args: Any, **_kwargs: Any):
    """Tripwire: constructing a real SDK client is a bug, not a fallback."""
    raise RuntimeError(
        "gpt_image_2 tried to construct a real openai.AsyncOpenAI inside the "
        "stdio smoke. The fake backend is the only client this process may "
        "build; something bypassed the api.build_client seam."
    )


def _require_late_bound_factory() -> None:
    """Fail loudly if `client_factory` goes back to an eager `build_client`.

    Regression guard for the seam this whole module stands on. If any of the
    three entry points binds a callable as its `client_factory` default again,
    `api.build_client = fake_build_client` below silently stops mattering — and
    so does every unit test that monkeypatches `api.build_client`. Catching it
    here turns a vacuously-green suite into an immediate, explicit failure.
    """
    for function in (api._call_with_retry, api.call_generate, api.call_edit):
        defaults = getattr(function, "__kwdefaults__", None) or {}
        if "client_factory" not in defaults:
            raise RuntimeError(
                f"gpt_image_2.api.{function.__name__} no longer accepts a "
                "keyword-only `client_factory`; the fake backend's seam is gone."
            )
        if defaults["client_factory"] is not None:
            raise RuntimeError(
                f"gpt_image_2.api.{function.__name__} binds `client_factory` "
                f"eagerly to {defaults['client_factory']!r}. It must default to "
                "None and resolve `build_client` inside the call, otherwise "
                "patching `api.build_client` is a no-op and the tests that do "
                "so pass without exercising anything."
            )


def install() -> None:
    """Idempotently replace both seams in the already-imported package."""
    global installed
    _require_late_bound_factory()
    api.build_client = fake_build_client
    credentials.resolve_api_key = fake_resolve_api_key
    openai.AsyncOpenAI = _blocked_async_openai
    installed = True


installed = False
install()
