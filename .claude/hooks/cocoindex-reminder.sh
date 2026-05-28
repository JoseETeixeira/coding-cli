#!/usr/bin/env bash
# UserPromptSubmit hook: nudge the agent to reach for the query-code semantic
# tools (search_codebase / explain_code / analyze_error) before falling back to
# blind grep/read, whenever the workspace CocoIndex index exists.
#
# UserPromptSubmit command hooks inject their stdout into the model's context,
# so a short reminder printed here lands in front of the agent on every prompt.
# Path-agnostic: every location is derived from the script's own path, so it
# works for any developer's clone. Gated on "index actually exists" so it stays
# silent when there is nothing to search.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CODING_CLI_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
MCP_DIR="$CODING_CLI_DIR/query-code-mcp"
INDEX_DIR="${CODEBASE_INDEX_DIR:-$MCP_DIR/.cocoindex/codebase-index}"

# Only nudge when an index actually exists (the tools have something to search).
[ -d "$INDEX_DIR" ] && [ -n "$(ls -A "$INDEX_DIR" 2>/dev/null)" ] || exit 0

cat <<'EOF'
[cocoindex] This workspace is indexed. Prefer the query-code MCP tools for
understanding existing code on this turn:
- Before grep/read to learn "how does X work", FIRST call search_codebase with
  a natural-language query and cite the returned source identifiers.
- Use explain_code for a specific file / function / class / symbol.
- Use analyze_error for an error or stack trace.
Treat Grep/Read as pinpoint follow-ups after the semantic search, not the first
move. If search_codebase returns nothing, check indexing_status and refresh.
EOF

exit 0
