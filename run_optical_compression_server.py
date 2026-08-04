"""Entrypoint for the optical-compression MCP server (stdio).

Registered by Claude Code / Codex as an MCP server. Adds the repository root to
sys.path so it runs from any working directory.

Mirrors run_gpt_image_2_server.py and mnemo/run_server.py deliberately: one
proven launcher shape for every stdio server in this repository.
"""

import os
import sys
from pathlib import Path

REPOSITORY_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

# MCP hosts choose different working directories. Keep exact originals in one
# stable user-scoped store so a digest produced in one session remains
# retrievable after an editor/extension upgrade. An explicit operator override
# still wins.
os.environ.setdefault(
    "OPTICAL_COMPRESSION_DIR",
    str(Path.home() / ".optical-compression"),
)

from optical_compression.server import main  # noqa: E402

if __name__ == "__main__":
    main()
