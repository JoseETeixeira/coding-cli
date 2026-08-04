"""Shared fixtures for the optical-compression suite.

Every test here is offline and deterministic: no network, no clock dependence,
no randomness. Rendering needs a real monospace font, so a suite run on a host
without one is skipped rather than failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


@pytest.fixture(scope="session", autouse=True)
def _require_font() -> None:
    from optical_compression.render import RenderError, load_font

    try:
        load_font(10)
    except RenderError as exc:  # pragma: no cover - host without a mono font
        pytest.skip(str(exc))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
