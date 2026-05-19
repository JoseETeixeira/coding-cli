#!/usr/bin/env bash
# Auto-improvement nudge — fires once at Stop to prompt the LLM to scan
# the just-completed conversation for codification candidates per the
# auto-improvement skill (~/.claude/skills/auto-improvement/SKILL.md).
# Stays silent when no candidate is found.
#
# Loop guard: respects stop_hook_active so we only nudge once per task end.

set -euo pipefail

input=$(cat)

stop_hook_active=$(printf '%s' "$input" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('stop_hook_active', False))
except Exception:
    print(False)
" 2>/dev/null || echo "False")

if [ "$stop_hook_active" = "True" ]; then
    exit 0
fi

cat <<'JSON'
{"decision": "block", "reason": "auto-improvement scan: check this task for codification candidates per ~/.claude/skills/auto-improvement/SKILL.md (Q→A durable answer, PR-review behavior feedback, untracked/contradicting directive, memory > 40k chars). If candidate found and target NOT on protected list — apply edit directly (no approval), mirror to all host roots, surface 1-line summary. If candidate is protected — refuse + route. If none — reply 'auto-improvement: no candidate' and stop."}
JSON
