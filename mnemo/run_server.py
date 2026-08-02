"""Entrypoint for the mnemo MCP server (stdio).

Registered by Claude Code / Codex / Copilot as an MCP server. Adds the package
root to sys.path so it runs from any working directory.
"""

import os
import sys

MNEMO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPOSITORY_ROOT = os.path.dirname(MNEMO_ROOT)
sys.path.insert(0, REPOSITORY_ROOT)
sys.path.insert(0, MNEMO_ROOT)

from mnemo.server import main  # noqa: E402

if __name__ == "__main__":
    main()
