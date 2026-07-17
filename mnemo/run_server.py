"""Entrypoint for the mnemo MCP server (stdio).

Registered by Claude Code / Codex / Copilot as an MCP server. Adds the package
root to sys.path so it runs from any working directory.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mnemo.server import main  # noqa: E402

if __name__ == "__main__":
    main()
