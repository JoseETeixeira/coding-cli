"""PostToolUse hook: arm the Batman delegation-handoff write.

Sibling to batman-phase-checkpoint.py. Same principle (ADR 0007, ADR 0008):
the hook ARMS, the model writes. It fires when a subagent writes a handoff
artifact under `.batman/<slug>/handoffs/<stem>.md`, and injects a pre-filled
mnemo `memory_write` (plus the `memory_forget` target when a prior live
handoff exists for the same stem). The FILE is the source of truth for the
body -- MemoryEngine.write embeds `text` as one vector (engine.py:231), so a
pasted body retrieves as noise. mnemo carries only the curated summary + the
artifact path + the pointer the next link consumes via memory_get.

Unlike the phase checkpoint there is no approval gate: durable memory writes
carry standing approval (user directive 2026-07-16), so the arm says "write
now, before you return your pointer", not "write after the gate".

Cost + safety identical to the sibling: path gate before any import (one regex
on a miss), local client.scroll for the prior lookup (no embed, no network),
never a `decision` field, every failure exits silent. The hook cannot block an
edit.
"""

import json
import os
import re
import sys
from pathlib import PurePosixPath

MNEMO = os.path.join(os.path.expanduser("~"), "source", "coding-cli", "mnemo")

WATCHED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# .batman/<slug>/handoffs/<stem>.md  -- stem is the unique discriminator, e.g.
# "task-3.gather" or "task-3.exec". Convention lives in shared-memory ->
# Delegation handoffs; the hook only needs the stem as a tag facet.
ARTIFACT_RE = re.compile(
    r"(?:^|/)\.batman/(?P<slug>[^/]+)/handoffs/(?P<stem>[^/]+)\.md$",
    re.IGNORECASE,
)


def resolve_target(payload):
    if payload.get("tool_name") not in WATCHED_TOOLS:
        return None

    raw = (payload.get("tool_input") or {}).get("file_path") or \
          (payload.get("tool_response") or {}).get("filePath")
    if not raw:
        return None

    base = payload.get("cwd") or os.getcwd()
    posix = os.path.abspath(os.path.join(base, raw)).replace("\\", "/")

    match = ARTIFACT_RE.search(posix)
    if not match:
        return None

    idx = posix.lower().rfind("/.batman/")
    if idx <= 0:
        return None
    repo = PurePosixPath(posix[:idx]).name
    if not repo:
        return None

    return {
        "slug": match.group("slug"),
        "stem": match.group("stem"),
        "namespace": "repo:{0}".format(repo),
        "artifact": posix,
    }


def find_prior(namespace, slug, stem):
    """Newest live handoff for this slug+stem, or None. Local scroll only."""
    sys.path.insert(0, MNEMO)
    from mnemo.config import Config
    from mnemo.engine import MemoryEngine

    os.environ.setdefault("MNEMO_AGENT_ID", "claude-code")

    items = MemoryEngine(Config()).list(namespace=namespace, limit=200, type="handoff")
    wanted = {"batman-handoff", slug, "handoff:{0}".format(stem)}
    for item in items:
        if wanted.issubset(set(item.get("tags") or [])):
            return item
    return None


def build_context(target, prior):
    tags = [
        "batman-handoff",
        target["slug"],
        "handoff:{0}".format(target["stem"]),
        "active",
    ]
    call = json.dumps(
        {
            "text": "<curated findings distillation -- see rule 2; NOT the file body>",
            "namespace": target["namespace"],
            "type": "handoff",
            "trust_class": "summarized",
            "confidence": 0.8,
            "tags": tags,
        },
        indent=2,
    )

    lines = [
        "Batman delegation handoff ARMED (PostToolUse hook) -- "
        "stem={0}, task_slug={1}, namespace={2}.".format(
            target["stem"], target["slug"], target["namespace"]
        ),
        "You just wrote the handoff artifact {0}.".format(target["artifact"]),
        "",
        "This hook wrote NOTHING to mnemo. The FILE is the source of truth for "
        "the full findings body; mnemo carries only a curated summary + this "
        "artifact path + the pointer the next link consumes. There is no "
        "approval gate -- durable writes carry standing approval -- so:",
        "",
        "1. Write it NOW, before you return, with exactly these parameters "
        "(this envelope matches the batman-handoff corpus -- do not vary it):",
        call,
        "",
        "2. `text` is a curated distillation, not the file body: what was found "
        "with a cited path:span for each claim, key decisions, and unresolved "
        "items. Include the artifact path {0} so the next link reads the full "
        "body from disk (mnemo stores one vector per item; a pasted body "
        "retrieves as noise). Never store secrets or tokens.".format(
            target["artifact"]
        ),
        "",
        "3. Return your control-plane summary with pointer set to the "
        "memory_id this write returns (task_id, status, pointer, key_decisions, "
        "checks, unresolved, confidence). The payload stays out of your return.",
    ]

    if prior:
        lines += [
            "",
            "4. SUPERSEDE FIRST -- a live handoff already exists for this stem. "
            "Before the write, call:",
            '     memory_forget(memory_id="{0}", reason="superseded by re-run of '
            'handoff {1}")'.format(prior.get("memory_id"), target["stem"]),
            "   Prior item: writer={0} timestamp={1}".format(
                prior.get("writer"), prior.get("timestamp")
            ),
            "   Never leave two `active` items for the same slug and stem.",
        ]
    else:
        lines += [
            "",
            "4. No prior handoff exists for this stem -- no memory_forget "
            "needed. This is the first write.",
        ]

    lines += [
        "",
        "Contract: shared-memory skill, 'Delegation handoffs'. This hook never "
        "blocks an edit; a missed arm costs one memory item, never your work.",
    ]
    return "\n".join(lines)


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        return
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    try:
        target = resolve_target(payload)
    except Exception:
        return
    if not target:
        return

    try:
        prior = find_prior(target["namespace"], target["slug"], target["stem"])
    except Exception:
        prior = None

    try:
        context = build_context(target, prior)
    except Exception:
        return

    print(json.dumps({
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        },
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
