#!/usr/bin/env bash

set -euo pipefail

input=$(cat)
state=$(printf '%s' "$input" | python3 -c '
import json
import sys

try:
    value = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError):
    raise SystemExit(0)

if (
    isinstance(value, dict)
    and type(value.get("stop_hook_active")) is bool
    and value["stop_hook_active"] is False
):
    print("emit")
' 2>/dev/null || true)

if [[ "$state" != "emit" ]]; then
    exit 0
fi

python3 - <<'PY'
import json

print(
    json.dumps(
        {
            "decision": "block",
            "reason": (
                "Evaluate the auto-improvement skill bundled with the active "
                "FreightHero plugin now as the parent entry agent. If no candidate "
                "exists, produce no user-facing message and "
                "allow the next Stop. Specialists only report candidates; they never "
                "edit canonical customization. For a candidate, identify its source "
                "and any tracked-source conflict, refuse protected targets, show the "
                "proposed canonical diff, and wait for explicit user approval before "
                "any write. Edit only the canonical checkout; "
                "never mirror installed host copies."
            ),
        },
        separators=(",", ":"),
    )
)
PY
