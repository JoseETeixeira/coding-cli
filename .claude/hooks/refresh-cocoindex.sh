#!/usr/bin/env bash
# SessionStart hook: keep the workspace CocoIndex codebase index fresh and make
# sure the folder the session opened in actually gets indexed.
#
# Wired into Claude Code SessionStart for startup/resume/clear, so it runs
# "whenever a session is started". It also handles the "current folder is not
# yet indexed" case by indexing the cwd, even when that folder lives outside the
# workspace:
#   - cwd == workspace root      -> every top-level project under it
#   - cwd under the workspace    -> just that top-level project
#   - cwd is a standalone repo   -> that repo, indexed on its own
#
# Work runs in the background so the session starts immediately. Path-agnostic:
# every location is derived from the script's own path, so it works for any
# developer's clone.

set -u

# Resolve every path physically (pwd -P) so symlinked roots (e.g. macOS
# /tmp -> /private/tmp) compare equal to the physical cwd below.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CODING_CLI_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
WORKSPACE_ROOT="$(cd "$CODING_CLI_DIR/.." && pwd -P)"
MCP_DIR="$CODING_CLI_DIR/query-code-mcp"
VENV_ACTIVATE="$MCP_DIR/.venv/bin/activate"
INDEX_DIR="${CODEBASE_INDEX_DIR:-$MCP_DIR/.cocoindex/codebase-index}"
LOG_FILE="${COCOINDEX_REFRESH_LOG:-/tmp/cocoindex-update.log}"
LOCK_FILE="${COCOINDEX_REFRESH_LOCK:-/tmp/cocoindex-update.lock}"

CWD="$(pwd -P)"
HOME_DIR="$(cd "$HOME" 2>/dev/null && pwd -P || echo "$HOME")"

is_under() { # is_under <parent> <child>  -> true when child is inside parent
  case "$2/" in "$1"/*) return 0 ;; *) return 1 ;; esac
}

# --- Decide what to index based on where the session opened -----------------
# PROJECT_KEY is the index subdirectory to probe for "already indexed?".
# The *_ENV vars scope the fallback pipeline run; an empty PROJECT_KEY means
# "whole workspace" (every top-level project).
PROJECT_KEY=""
SCOPE_LABEL=""
CODEBASE_PROJECTS_ENV=""
CODEBASE_PROJECT_PATHS_ENV=""

if [ "$CWD" = "$WORKSPACE_ROOT" ]; then
  SCOPE_LABEL="all top-level projects in $WORKSPACE_ROOT"
elif is_under "$WORKSPACE_ROOT" "$CWD"; then
  rel="${CWD#"$WORKSPACE_ROOT"/}"
  PROJECT_KEY="${rel%%/*}"
  if [ "$PROJECT_KEY" = "coding-cli" ]; then
    # coding-cli is never indexed on its own; refresh the whole workspace.
    PROJECT_KEY=""
    SCOPE_LABEL="all top-level projects in $WORKSPACE_ROOT"
  else
    SCOPE_LABEL="project '$PROJECT_KEY'"
    CODEBASE_PROJECTS_ENV="$PROJECT_KEY"
  fi
else
  # cwd is outside the workspace. Only auto-index real project folders so that
  # opening a session in $HOME (or another huge non-project dir) never kicks off
  # a massive crawl.
  if [ "$CWD" = "$HOME_DIR" ] || [ "$CWD" = "/" ]; then
    exit 0
  fi
  if [ ! -d "$CWD/.git" ] && [ "$(git -C "$CWD" rev-parse --show-toplevel 2>/dev/null)" != "$CWD" ]; then
    exit 0
  fi
  base="$(basename "$CWD")"
  if command -v shasum >/dev/null 2>&1; then
    hash="$(printf '%s' "$CWD" | shasum | cut -c1-6)"
  elif command -v sha1sum >/dev/null 2>&1; then
    hash="$(printf '%s' "$CWD" | sha1sum | cut -c1-6)"
  else
    hash="ext"
  fi
  PROJECT_KEY="${base}-${hash}"
  SCOPE_LABEL="standalone project '$PROJECT_KEY' ($CWD)"
  CODEBASE_PROJECT_PATHS_ENV="${PROJECT_KEY}=${CWD}"
fi

if [ ! -f "$VENV_ACTIVATE" ]; then
  echo "[cocoindex] venv missing at $VENV_ACTIVATE; run 'coding-cli setup full' to bootstrap" >&2
  exit 0
fi

# Skip if a refresh is already running (lock holds the worker's pid).
if [ -f "$LOCK_FILE" ]; then
  pid="$(cat "$LOCK_FILE" 2>/dev/null || echo "")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "[cocoindex] refresh already running (pid $pid), skipping"
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi

# Is this folder already in the index? Drives the log message; the refresh runs
# either way (incremental when present, full build when missing).
indexed="no"
if [ -n "$PROJECT_KEY" ]; then
  [ -d "$INDEX_DIR/$PROJECT_KEY" ] && [ -n "$(ls -A "$INDEX_DIR/$PROJECT_KEY" 2>/dev/null)" ] && indexed="yes"
else
  [ -d "$INDEX_DIR" ] && [ -n "$(ls -A "$INDEX_DIR" 2>/dev/null)" ] && indexed="yes"
fi

if [ "$indexed" = "yes" ]; then
  echo "[cocoindex] refreshing $SCOPE_LABEL in background (log: $LOG_FILE)"
else
  echo "[cocoindex] $SCOPE_LABEL not indexed yet; building index in background (log: $LOG_FILE)"
fi

# Prefer the coding-cli binary (cwd-aware target resolution, ensures the venv
# and MCP build exist); fall back to the venv pipeline with explicit scoping
# when it isn't on PATH.
CLI_BIN=""
for cand in \
  "$(command -v coding-cli 2>/dev/null || true)" \
  "$HOME/.local/bin/coding-cli" \
  "/usr/local/bin/coding-cli" \
  "$CODING_CLI_DIR/dist/coding-cli"; do
  if [ -n "$cand" ] && [ -x "$cand" ]; then
    CLI_BIN="$cand"
    break
  fi
done

# Launch the refresh in the background. The lock holds the worker's pid (written
# by the parent via $!, since macOS bash 3.2 has no BASHPID); the worker clears
# it on exit. A stale lock from a crashed run is detected by the kill -0 check
# above and removed.
(
  {
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') cocoindex update start ($SCOPE_LABEL) ==="
    if [ -n "$CLI_BIN" ]; then
      ( cd "$CWD" && "$CLI_BIN" run indexing )
      status=$?
    else
      cd "$MCP_DIR" || { rm -f "$LOCK_FILE"; exit 0; }
      # shellcheck disable=SC1090
      source "$VENV_ACTIVATE"
      export WORKSPACE_ROOT
      export CODEBASE_INDEX_DIR="$INDEX_DIR"
      [ -n "$CODEBASE_PROJECTS_ENV" ] && export CODEBASE_PROJECTS="$CODEBASE_PROJECTS_ENV"
      [ -n "$CODEBASE_PROJECT_PATHS_ENV" ] && export CODEBASE_PROJECT_PATHS="$CODEBASE_PROJECT_PATHS_ENV"
      cocoindex update codebase_index.py
      status=$?
    fi
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') cocoindex update done (exit $status) ==="
  } >> "$LOG_FILE" 2>&1
  rm -f "$LOCK_FILE"
) &
echo "$!" > "$LOCK_FILE"

disown 2>/dev/null || true
exit 0
