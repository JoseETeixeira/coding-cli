"""Shared fixtures for the gpt-image-2 suite.

Every fixture here is offline. Nothing in this package may make a network call:
the OpenAI boundary is replaced by `FakeOpenAI`, which records exactly what
would have been sent so tests can assert the request shape instead of trusting
it.

The fake errors are *real* `openai` exception instances so that `isinstance`
dispatch in `gpt_image_2.api.map_exception` is exercised for real rather than
being simulated by duck typing.
"""

from __future__ import annotations

import base64
import logging
import sys
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator

import httpx
import openai
import pytest
from PIL import Image as PILImage

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gpt_image_2 import api, constants  # noqa: E402
from gpt_image_2.credentials import Secret  # noqa: E402

#: A distinctive value that must never appear in a log, result, or error.
CANARY_SECRET = "sk-canary-DEADBEEF-must-never-be-emitted-0123456789"

ENDPOINT = "https://api.openai.com/v1/images/generations"

#: Root of this package's logger tree. `server._configure_logging()` owns its
#: level, its handler, and its `propagate` flag.
PACKAGE_LOGGER_NAME = "gpt_image_2"


# ---------------------------------------------------------------------------
# Image fixture factories
# ---------------------------------------------------------------------------


def make_image_bytes(
    fmt: str = "png",
    size: tuple[int, int] = (64, 64),
    mode: str = "RGB",
    color: tuple[int, ...] | int = (200, 30, 30),
    alpha: int | None = None,
) -> bytes:
    """Build a real encoded image in memory.

    `alpha` fills the alpha channel with a constant when `mode` carries one —
    255 produces the fully-opaque mask the validator must reject, anything
    lower produces a usable mask.
    """
    image = PILImage.new(mode, size, color if mode != "L" else 128)
    if alpha is not None and "A" in image.getbands():
        image.putalpha(alpha)
    buffer = BytesIO()
    pil_format = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[fmt]
    image.save(buffer, format=pil_format)
    return buffer.getvalue()


def write_image(
    directory: Path,
    name: str,
    fmt: str = "png",
    size: tuple[int, int] = (64, 64),
    mode: str = "RGB",
    alpha: int | None = None,
) -> Path:
    path = directory / name
    path.write_bytes(make_image_bytes(fmt=fmt, size=size, mode=mode, alpha=alpha))
    return path


def b64_image(**kwargs: Any) -> str:
    return base64.b64encode(make_image_bytes(**kwargs)).decode("ascii")


@pytest.fixture
def png_bytes() -> bytes:
    return make_image_bytes("png")


@pytest.fixture
def reference_png(tmp_path: Path) -> Path:
    return write_image(tmp_path, "reference.png", fmt="png", mode="RGBA", alpha=255)


@pytest.fixture
def mask_png(tmp_path: Path) -> Path:
    """Same size and format as `reference_png`, with usable (non-opaque) alpha."""
    return write_image(tmp_path, "mask.png", fmt="png", mode="RGBA", alpha=0)


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "out"


# ---------------------------------------------------------------------------
# Fake OpenAI transport
# ---------------------------------------------------------------------------


@dataclass
class RecordedCall:
    operation: str
    kwargs: dict[str, Any]


class FakeParsedImage:
    def __init__(self, b64_json: str | None, revised_prompt: str | None = None) -> None:
        self.b64_json = b64_json
        self.revised_prompt = revised_prompt
        self.url = None


class FakeUsage:
    def __init__(self, input_tokens: int = 11, output_tokens: int = 22) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens + output_tokens


class FakeParsedResponse:
    def __init__(
        self,
        payloads: list[str],
        *,
        usage: FakeUsage | None = None,
        revised_prompt: str | None = None,
    ) -> None:
        self.data = [
            FakeParsedImage(payload, revised_prompt if i == 0 else None)
            for i, payload in enumerate(payloads)
        ]
        self.usage = usage


class FakeRawResponse:
    """Stands in for `openai._response.AsyncAPIResponse`.

    `parse()` is intentionally synchronous: `api._maybe_await` must tolerate
    both a coroutine and a plain value, and this is the half that proves the
    non-awaitable branch.
    """

    def __init__(self, parsed: Any, headers: dict[str, str] | None = None) -> None:
        self._parsed = parsed
        self.headers = httpx.Headers(headers or {"x-request-id": "req_fake_001"})

    def parse(self) -> Any:
        return self._parsed


class _FakeRawOps:
    def __init__(self, owner: "FakeOpenAI") -> None:
        self._owner = owner

    async def generate(self, **kwargs: Any) -> Any:
        return self._owner._dispatch("generate", kwargs)

    async def edit(self, **kwargs: Any) -> Any:
        return self._owner._dispatch("edit", kwargs)


class _FakeImages:
    def __init__(self, owner: "FakeOpenAI") -> None:
        self.with_raw_response = _FakeRawOps(owner)


class FakeOpenAI:
    """Scripted stand-in for `openai.AsyncOpenAI`.

    `script` entries are consumed in order. An entry that is an exception is
    raised; anything else is returned. When the script runs out the last entry
    repeats, so a single-entry script models a stable service.
    """

    def __init__(self, script: list[Any] | None = None) -> None:
        self.calls: list[RecordedCall] = []
        self.script: list[Any] = list(script or [])
        self._index = 0
        self.images = _FakeImages(self)

    # -- inspection helpers -------------------------------------------------
    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_kwargs(self) -> dict[str, Any]:
        return self.calls[-1].kwargs

    def _dispatch(self, operation: str, kwargs: dict[str, Any]) -> Any:
        self.calls.append(RecordedCall(operation, dict(kwargs)))
        if not self.script:
            return FakeRawResponse(FakeParsedResponse([b64_image()]))
        entry = self.script[min(self._index, len(self.script) - 1)]
        self._index += 1
        if isinstance(entry, BaseException):
            raise entry
        return entry


@dataclass
class FakeClientFactory:
    """A `build_client` replacement that records how it was called."""

    client: FakeOpenAI = field(default_factory=FakeOpenAI)
    secrets_seen: list[Secret] = field(default_factory=list)

    def __call__(self, secret: Secret) -> FakeOpenAI:
        self.secrets_seen.append(secret)
        return self.client

    @property
    def call_count(self) -> int:
        return self.client.call_count


# ---------------------------------------------------------------------------
# Real openai exceptions, cheaply constructed
# ---------------------------------------------------------------------------


def http_response(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
    request = httpx.Request("POST", ENDPOINT)
    return httpx.Response(status_code=status, headers=headers or {}, request=request)


def status_error(
    status: int,
    message: str = "provider said something",
    *,
    code: str | None = None,
    headers: dict[str, str] | None = None,
) -> openai.APIStatusError:
    """Build the real SDK exception the SDK would raise for `status`."""
    body: dict[str, Any] = {"message": message}
    if code:
        body["code"] = code
    response = http_response(status, headers)
    cls = {
        400: openai.BadRequestError,
        401: openai.AuthenticationError,
        403: openai.PermissionDeniedError,
        404: openai.NotFoundError,
        409: openai.ConflictError,
        422: openai.UnprocessableEntityError,
        429: openai.RateLimitError,
    }.get(status)
    if cls is None:
        cls = openai.InternalServerError if status >= 500 else openai.APIStatusError
    return cls(message, response=response, body=body)


def timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx.Request("POST", ENDPOINT))


def connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx.Request("POST", ENDPOINT))


# ---------------------------------------------------------------------------
# Budget / timing seams
# ---------------------------------------------------------------------------


class FakeClock:
    """A monotonic clock the test advances by hand. No test ever sleeps."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class RecordingSleep:
    """An `anyio.sleep` replacement that records and optionally advances time."""

    clock: FakeClock | None = None
    delays: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
        if self.clock is not None:
            self.clock.advance(seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def sleeper(clock: FakeClock) -> RecordingSleep:
    return RecordingSleep(clock=clock)


@pytest.fixture
def budget(clock: FakeClock) -> api.Budget:
    return api.Budget(constants.OPERATION_DEADLINE_S, monotonic=clock)


@pytest.fixture
def secret() -> Secret:
    return Secret(CANARY_SECRET)


@pytest.fixture
def fake_factory() -> FakeClientFactory:
    return FakeClientFactory()


@pytest.fixture
def no_jitter():
    return lambda: 0.0


# ---------------------------------------------------------------------------
# Package log capture (the fixture `caplog` can no longer be)
# ---------------------------------------------------------------------------

#: Byte-for-byte the format `caplog.text` uses, so migrating an assertion from
#: `caplog.text` to `package_logs.text` really is a one-word change and cannot
#: change what a substring check finds.
_CAPLOG_FORMAT = "%(levelname)-8s %(name)s:%(filename)s:%(lineno)d %(message)s"


class PackageLogCapture(logging.Handler):
    """A `caplog`-shaped handler that lives on the `gpt_image_2` logger itself.

    Formatting happens at emit time, exactly as `caplog` does it: a handler in
    production formats the record while its arguments are still the objects the
    call site passed, and that is precisely the moment a `Secret` gets its one
    chance to refuse to render.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []
        self._formatted: list[str] = []
        self.setFormatter(logging.Formatter(_CAPLOG_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        try:
            self._formatted.append(self.format(record))
        except Exception:  # pragma: no cover - a broken record is still evidence
            self._formatted.append(record.getMessage())

    @property
    def text(self) -> str:
        """The formatted log text — the `caplog.text` equivalent."""
        return "".join(f"{line}\n" for line in self._formatted)

    @property
    def messages(self) -> list[str]:
        """Interpolated messages only — the `caplog.messages` equivalent."""
        return [record.getMessage() for record in self.records]

    def clear(self) -> None:
        self.records.clear()
        self._formatted.clear()


@pytest.fixture
def package_logs() -> Iterator[PackageLogCapture]:
    """Capture this package's log records. Use this, never `caplog`.

    Read this before "simplifying" it back to `caplog`, because the failure mode
    is silent and it is the worst kind:

    `server._configure_logging()` sets `propagate = False` on the `gpt_image_2`
    logger. That is deliberate and load-bearing — stdout is the JSON-RPC channel
    and a host may have installed a root handler that writes there, so our
    records must not climb to root (constitution principle 6). `caplog` installs
    its handler on the ROOT logger, so it now sees NOTHING this package logs.

    An empty `caplog` does not fail. It makes the leak suite's dominant
    assertion shape, `assert CANARY_SECRET not in caplog.text`, pass
    **vacuously**: green, and testing nothing at all. Delete the redaction from
    `errors.redact` and those assertions still pass. That is why capture is
    attached directly to the `gpt_image_2` logger here, below the propagation
    cut, where the records actually are.

    The fixture forces DEBUG for the duration so a record cannot be filtered out
    by whatever `GPT_IMAGE_2_LOG_LEVEL` resolved to at import, coexists with the
    stderr handler `_configure_logging()` already installed, and restores the
    logger's level, handler list, and `propagate` flag exactly on the way out —
    including when the test under it re-ran `_configure_logging()`.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    previous_level = logger.level
    previous_propagate = logger.propagate
    previous_handlers = list(logger.handlers)

    capture = PackageLogCapture()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(capture)
    try:
        yield capture
    finally:
        # Assign into the live list so any reference held elsewhere still sees
        # the restored state, and restore `propagate` even though this fixture
        # never changes it: the code under test may have.
        logger.handlers[:] = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard stop: a test that reaches for a real client fails loudly.

    This is the safety net behind constitution principle 7 — the default suite
    must not be able to spend money even by accident.
    """

    def _explode(*_args: Any, **_kwargs: Any):
        raise AssertionError(
            "A test attempted to construct a real OpenAI client. The default "
            "suite must stay offline; inject a FakeClientFactory instead."
        )

    monkeypatch.setattr(openai, "AsyncOpenAI", _explode)
