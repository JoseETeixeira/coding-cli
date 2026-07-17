#!/bin/bash

# block-dangerous-git.sh
#
# Claude Code PreToolUse hook that blocks destructive git commands before
# they execute. Reads the tool input as JSON on stdin and exits non-zero
# when the command matches a dangerous pattern.
#
# See: coding-cli/skills/git-guardrails-claude-code/SKILL.md

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

DANGEROUS_PATTERNS=(
  "git push"
  "git reset --hard"
  "git clean -fd"
  "git clean -f"
  "git branch -D"
  "git checkout \."
  "git restore \."
  "push --force"
  "reset --hard"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    echo "BLOCKED: '$COMMAND' matches dangerous pattern '$pattern'. The user has prevented you from doing this." >&2
    exit 2
  fi
done

exit 0
