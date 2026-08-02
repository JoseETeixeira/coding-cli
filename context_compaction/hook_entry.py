"""Stable hook entry point that works outside the coding-cli checkout."""

from __future__ import annotations

import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from context_compaction.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
