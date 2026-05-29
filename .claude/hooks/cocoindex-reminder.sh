#!/usr/bin/env bash
# UserPromptSubmit hook: nudge the agent to reach for the query-code semantic
# tools (search_codebase / explain_code / analyze_error) before falling back to
# blind grep/read, whenever the CURRENT project is in the CocoIndex index.
#
# UserPromptSubmit command hooks inject their stdout into the model's context,
# so a short reminder printed here lands in front of the agent on every prompt.
# Path-agnostic: every location is derived from the script's own path, so it
# works for any developer's clone. The nudge is scoped to the project the
# session opened in, so it never claims "indexed" when search_codebase would
# come back empty for the cwd.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CODING_CLI_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
WORKSPACE_ROOT="$(cd "$CODING_CLI_DIR/.." && pwd -P)"
MCP_DIR="$CODING_CLI_DIR/query-code-mcp"
INDEX_DIR="${CODEBASE_INDEX_DIR:-$MCP_DIR/.cocoindex/codebase-index}"

CWD="$(pwd -P)"

is_under() { case "$2/" in "$1"/*) return 0 ;; *) return 1 ;; esac }

# Derive the index subdirectory for the current project the same way the
# SessionStart refresh hook does. Empty PROJECT_KEY == whole workspace.
PROJECT_KEY=""
if [ "$CWD" = "$WORKSPACE_ROOT" ]; then
  PROJECT_KEY=""
elif is_under "$WORKSPACE_ROOT" "$CWD"; then
  rel="${CWD#"$WORKSPACE_ROOT"/}"
  PROJECT_KEY="${rel%%/*}"
  [ "$PROJECT_KEY" = "coding-cli" ] && PROJECT_KEY=""
else
  base="$(basename "$CWD")"
  if command -v shasum >/dev/null 2>&1; then
    hash="$(printf '%s' "$CWD" | shasum | cut -c1-6)"
  elif command -v sha1sum >/dev/null 2>&1; then
    hash="$(printf '%s' "$CWD" | sha1sum | cut -c1-6)"
  else
    hash="ext"
  fi
  PROJECT_KEY="${base}-${hash}"
fi

# Only nudge when the CURRENT project is actually in the index, so the tools
# have something to search for this cwd.
indexed="no"
if [ -n "$PROJECT_KEY" ]; then
  [ -d "$INDEX_DIR/$PROJECT_KEY" ] && [ -n "$(ls -A "$INDEX_DIR/$PROJECT_KEY" 2>/dev/null)" ] && indexed="yes"
else
  [ -d "$INDEX_DIR" ] && [ -n "$(ls -A "$INDEX_DIR" 2>/dev/null)" ] && indexed="yes"
fi

[ "$indexed" = "yes" ] || exit 0

cat <<'EOF'
[cocoindex] This project is indexed. Prefer the query-code MCP tools for
understanding existing code on this turn:
- Before grep/read to learn "how does X work", FIRST call search_codebase with
  a natural-language query and cite the returned source identifiers.
- Use explain_code for a specific file / function / class / symbol.
- Use analyze_error for an error or stack trace.
Treat Grep/Read as pinpoint follow-ups after the semantic search, not the first
move. If search_codebase returns nothing, check indexing_status and refresh.
EOF

exit 0
