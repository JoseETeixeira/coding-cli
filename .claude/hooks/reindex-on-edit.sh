#!/usr/bin/env bash
# PostToolUse hook (Write|Edit|MultiEdit|NotebookEdit): keep the CocoIndex index
# fresh DURING a session by reindexing the current project after file edits.
#
# Debounced so a burst of edits triggers at most one incremental reindex per
# window, and serialized against the SessionStart refresh via the shared lock so
# two cocoindex runs never hit the same db at once. Runs in the background and
# stays silent (logs to file) so it never adds noise after an edit.
#
# Path-agnostic: every location is derived from the script's own path. Scopes to
# the current project only; a session opened at the workspace root (where a
# reindex would crawl every project) is left to the SessionStart hook.

set -u

DEBOUNCE_SECS="${COCOINDEX_REINDEX_DEBOUNCE:-90}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CODING_CLI_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
WORKSPACE_ROOT="$(cd "$CODING_CLI_DIR/.." && pwd -P)"
MCP_DIR="$CODING_CLI_DIR/query-code-mcp"
VENV_ACTIVATE="$MCP_DIR/.venv/bin/activate"
[ -f "$VENV_ACTIVATE" ] || VENV_ACTIVATE="$MCP_DIR/.venv/Scripts/activate"
INDEX_DIR="${CODEBASE_INDEX_DIR:-$MCP_DIR/.cocoindex/codebase-index}"
LOG_FILE="${COCOINDEX_REFRESH_LOG:-/tmp/cocoindex-update.log}"
LOCK_FILE="${COCOINDEX_REFRESH_LOCK:-/tmp/cocoindex-update.lock}"
STAMP_FILE="${COCOINDEX_REINDEX_STAMP:-/tmp/cocoindex-reindex.stamp}"

CWD="$(pwd -P)"
HOME_DIR="$(cd "$HOME" 2>/dev/null && pwd -P || echo "$HOME")"

is_under() { case "$2/" in "$1"/*) return 0 ;; *) return 1 ;; esac }

# --- Scope to the current project (same rules as the SessionStart hook) ------
PROJECT_KEY=""
CODEBASE_PROJECTS_ENV=""
CODEBASE_PROJECT_PATHS_ENV=""

if [ "$CWD" = "$WORKSPACE_ROOT" ]; then
  # Whole-workspace reindex is too heavy to run after every edit; leave it to
  # the SessionStart hook.
  exit 0
elif is_under "$WORKSPACE_ROOT" "$CWD"; then
  rel="${CWD#"$WORKSPACE_ROOT"/}"
  PROJECT_KEY="${rel%%/*}"
  [ "$PROJECT_KEY" = "coding-cli" ] && exit 0
  CODEBASE_PROJECTS_ENV="$PROJECT_KEY"
else
  [ "$CWD" = "$HOME_DIR" ] || [ "$CWD" = "/" ] && exit 0
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
  CODEBASE_PROJECT_PATHS_ENV="${PROJECT_KEY}=${CWD}"
fi

# --- Debounce: at most one reindex per window --------------------------------
now="$(date +%s 2>/dev/null || echo 0)"
if [ -f "$STAMP_FILE" ]; then
  last="$(cat "$STAMP_FILE" 2>/dev/null || echo 0)"
  case "$last" in (*[!0-9]*|"") last=0 ;; esac
  if [ "$now" -ne 0 ] && [ $((now - last)) -lt "$DEBOUNCE_SECS" ]; then
    exit 0
  fi
fi

# --- Serialize against any in-flight cocoindex run ---------------------------
if [ -f "$LOCK_FILE" ]; then
  pid="$(cat "$LOCK_FILE" 2>/dev/null || echo "")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi

# Resolve the coding-cli binary; fall back to the venv pipeline.
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

if [ -z "$CLI_BIN" ] && [ ! -f "$VENV_ACTIVATE" ]; then
  exit 0
fi

# Stamp now so concurrent edits in this window do not re-trigger.
echo "$now" > "$STAMP_FILE"

(
  {
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') cocoindex reindex-on-edit start (project '$PROJECT_KEY') ==="
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
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') cocoindex reindex-on-edit done (exit $status) ==="
  } >> "$LOG_FILE" 2>&1
  rm -f "$LOCK_FILE"
) &
echo "$!" > "$LOCK_FILE"

disown 2>/dev/null || true
exit 0
