#!/usr/bin/env bash
# SessionStart hook: refresh the FreightHero CocoIndex codebase index in the
# background so the session can start immediately. Path-agnostic — derives
# locations from the script's own path so it works for any developer who
# clones the FreightHero workspace.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODING_CLI_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
FREIGHTHERO_ROOT="$(cd "$CODING_CLI_DIR/.." && pwd)"
MCP_DIR="$CODING_CLI_DIR/freighthero-mcp"
VENV_ACTIVATE="$MCP_DIR/.venv/bin/activate"
LOG_FILE="${COCOINDEX_REFRESH_LOG:-/tmp/cocoindex-update.log}"
LOCK_FILE="${COCOINDEX_REFRESH_LOCK:-/tmp/cocoindex-update.lock}"

# Only refresh when the session is opened inside the FreightHero workspace.
# Lets the hook live in a global Claude Code settings file without firing for
# unrelated projects.
case "$PWD/" in
  "$FREIGHTHERO_ROOT"/*) ;;
  *)
    exit 0
    ;;
esac

if [ ! -f "$VENV_ACTIVATE" ]; then
  echo "[cocoindex] venv missing at $VENV_ACTIVATE; run 'freighthero setup full' to bootstrap" >&2
  exit 0
fi

# Skip if a refresh is already running.
if [ -f "$LOCK_FILE" ]; then
  pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "[cocoindex] refresh already running (pid $pid), skipping"
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi

echo "[cocoindex] refreshing FreightHero codebase index in background (log: $LOG_FILE)"

(
  echo "$$" > "$LOCK_FILE"
  cd "$MCP_DIR" || exit 0
  # shellcheck disable=SC1090
  source "$VENV_ACTIVATE"
  {
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') cocoindex update start ($MCP_DIR) ==="
    cocoindex update codebase_index.py:FreightHeroCodebase
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') cocoindex update done (exit $?) ==="
  } >> "$LOG_FILE" 2>&1
  rm -f "$LOCK_FILE"
) &

disown 2>/dev/null || true
exit 0
