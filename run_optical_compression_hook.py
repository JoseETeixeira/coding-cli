"""Entrypoint for the optical-compression PostToolUse hook (Claude Code only).

Registered in hooks.json. Adds the repository root to sys.path so the package's
relative imports resolve no matter which working directory the host runs the
hook from.

Mirrors run_optical_compression_server.py: one proven launcher shape for every
entrypoint in this repository.

Fails open by construction. Any import or runtime problem exits 0 with no
stdout, which leaves the original tool result exactly as it was — a hook that
mangles tool output is far worse than a hook that does nothing.
"""

import os
import sys
from pathlib import Path

REPOSITORY_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

# Match the MCP launcher. Without one stable default, Claude's hook can store
# an original under the workspace while optical_retrieve looks under the MCP
# host's unrelated working directory.
os.environ.setdefault(
    "OPTICAL_COMPRESSION_DIR",
    str(Path.home() / ".optical-compression"),
)

if __name__ == "__main__":
    try:
        from optical_compression.hook import main
    except Exception:
        sys.exit(0)
    sys.exit(main())
