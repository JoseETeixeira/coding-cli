"""Entrypoint for the gpt-image-2 MCP server (stdio).

Registered by Claude Code / Codex / Copilot as an MCP server. Adds the
repository root to sys.path so it runs from any working directory — which
matters here because the tool's default output location is derived from the
*caller's* working directory, not from wherever the server was launched.

Mirrors mnemo/run_server.py deliberately: one proven launcher shape for every
stdio server in this repository.
"""

import os
import sys

REPOSITORY_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

from gpt_image_2.server import main  # noqa: E402

if __name__ == "__main__":
    main()
