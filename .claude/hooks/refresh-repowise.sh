#!/usr/bin/env bash
# SessionStart hook: refresh the FreightHero repowise workspace index in the
# background so the session starts with a current dependency graph + git +
# code-health view. Runs --index-only (no LLM, no cost, no MCP re-registration);
# docs/RAG are refreshed on demand via `repowise update --workspace` after a
# significant code change. Path-agnostic — derives locations from the script's
# own path so it works for any developer who clones the FreightHero workspace.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODING_CLI_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
FREIGHTHERO_ROOT="$(cd "$CODING_CLI_DIR/.." && pwd)"
LOG_FILE="${REPOWISE_REFRESH_LOG:-/tmp/repowise-update.log}"
LOCK_FILE="${REPOWISE_REFRESH_LOCK:-/tmp/repowise-update.lock}"

# Only refresh when the session is opened inside the FreightHero workspace, so
# this hook can live in a global Claude Code settings file without firing for
# unrelated projects.
case "$PWD/" in
  "$FREIGHTHERO_ROOT"/*) ;;
  *)
    exit 0
    ;;
esac

# Resolve the repowise CLI (uv tool install puts it on PATH; fall back to the
# conventional uv/local bin locations).
REPOWISE_BIN="$(command -v repowise 2>/dev/null || true)"
if [ -z "$REPOWISE_BIN" ]; then
  for cand in "$HOME/.local/bin/repowise" "$HOME/.local/share/uv/tools/repowise/bin/repowise"; do
    [ -x "$cand" ] && REPOWISE_BIN="$cand" && break
  done
fi
if [ -z "$REPOWISE_BIN" ]; then
  echo "[repowise] CLI not found; install with 'uv tool install repowise'" >&2
  exit 0
fi

# Skip if a refresh is already running.
if [ -f "$LOCK_FILE" ]; then
  pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "[repowise] refresh already running (pid $pid), skipping"
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi

echo "[repowise] refreshing FreightHero workspace index in background (log: $LOG_FILE)"

(
  echo "$$" > "$LOCK_FILE"
  cd "$FREIGHTHERO_ROOT" || exit 0
  {
    # Re-apply the Markdown-eligibility patch to the installed repowise tool.
    # `uv tool upgrade repowise` overwrites package source, so this keeps the
    # patch live every session. Idempotent + fail-soft (never aborts the run).
    PATCH_PY="$SCRIPT_DIR/patch-repowise-markdown.py"
    PYTHON_BIN="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
    if [ -n "$PYTHON_BIN" ] && [ -f "$PATCH_PY" ]; then
      echo "=== $(date '+%Y-%m-%d %H:%M:%S') repowise-md-patch start ==="
      "$PYTHON_BIN" "$PATCH_PY" || true
    fi
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') repowise update --workspace --index-only start ($FREIGHTHERO_ROOT) ==="
    "$REPOWISE_BIN" update --workspace --index-only
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') repowise update done (exit $?) ==="
  } >> "$LOG_FILE" 2>&1
  rm -f "$LOCK_FILE"
) &

disown 2>/dev/null || true
exit 0
