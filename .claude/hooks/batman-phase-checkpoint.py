"""PostToolUse hook: arm the Batman phase checkpoint at the approval gate.

Why a hook. `generic-entry` has claimed since 2026-07-16 that mnemo holds
task/spec state, and nothing ever wrote it -- every existing type=spec item
carries the `migrated-from-claude-md` tag, a frozen snapshot of the deleted
workspace CLAUDE.md. Prose that only *asks* the model to write silently does
not fire: the mnemo READ preflight was mandated in both CLAUDE.md and
batman.agent.md and never fired in either host until mnemo-preflight.py made it
a hook. The harness executes hooks, so the harness is what lands the obligation
in context at the moment it is actionable.

Why it does not write. A hook can see a file; it cannot see an approval.
Write/Edit fires on the *draft* -- the user may still reject or revise it during
the grill-me pass, so a hook write would store exactly the state grilling exists
to discard. And a hook can only store the artifact, while the value of a
checkpoint is the curated distillation of what was approved and why, which only
the model that just authored it knows. MemoryEngine.write embeds `text` as a
single vector (engine.py:231), so a pasted document retrieves as noise anyway.
This hook therefore ARMS and stops: it injects a pre-filled `memory_write` (and
the `memory_forget` target when a prior checkpoint exists) and instructs the
model to fire it AFTER the gate. The model does the write.

Cost. The path gate runs before any import -- for the Write/Edit calls that miss
`.batman/`, this is one regex and exit. On a hit, MemoryEngine.list() uses
client.scroll (engine.py:315): payload filter only, no embedding, no network
round-trip to OpenAI.

Never blocks an edit. There is no `decision` field on any path, and every
failure exits silently with no output. A missing checkpoint prompt costs one
memory item; it must never cost the user's work.
"""

import json
import os
import re
import sys
from pathlib import PurePosixPath

MNEMO = os.path.join(os.path.expanduser("~"), "source", "coding-cli", "mnemo")

# The settings.json matcher filters on tool NAME only, never path -- so the path
# gate has to live here.
WATCHED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

PHASES = {
    "understanding": (1, "Understanding"),
    "requirements": (2, "Requirements"),
    "design": (3, "Design"),
    "tasks": (4, "Task Planning"),
}

ARTIFACT_RE = re.compile(
    r"(?:^|/)\.batman/(?P<slug>[^/]+)/(?:steering|spec)/"
    r"(?P<stem>understanding|requirements|design|tasks)\.md$",
    re.IGNORECASE,
)


def resolve_target(payload):
    """Return checkpoint identity for a Batman phase artifact, else None."""
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

    # Repo root is whatever sits above `.batman/` -- no git call needed, which
    # also dodges the stdin-inheritance hang that cost mnemo 31s per call.
    idx = posix.lower().rfind("/.batman/")
    if idx <= 0:
        return None
    repo = PurePosixPath(posix[:idx]).name
    if not repo:
        return None

    phase, label = PHASES[match.group("stem").lower()]
    return {
        "slug": match.group("slug"),
        "phase": phase,
        "label": label,
        "namespace": "repo:{0}".format(repo),
        "artifact": posix,
    }


def find_prior(namespace, slug, phase):
    """Newest live checkpoint for this slug+phase, or None. Local scroll only."""
    sys.path.insert(0, MNEMO)
    from mnemo.config import Config
    from mnemo.engine import MemoryEngine

    # Match the host's MCP registration so the writer identity agrees with the
    # one the mnemo MCP server writes under.
    os.environ.setdefault("MNEMO_AGENT_ID", "claude-code")

    # list() -> _base_filter excludes revoked and expired items, and sorts
    # newest-first (engine.py:322).
    items = MemoryEngine(Config()).list(namespace=namespace, limit=200, type="spec")
    wanted = {"batman-spec", slug, "phase-{0}".format(phase)}
    for item in items:
        if wanted.issubset(set(item.get("tags") or [])):
            return item
    return None


def build_context(target, prior):
    tags = [
        "batman-spec",
        "task-state",
        target["slug"],
        "phase-{0}".format(target["phase"]),
        "active",
    ]
    call = json.dumps(
        {
            "text": "<curated distillation -- see rule 3 below; NOT the artifact body>",
            "namespace": target["namespace"],
            "type": "spec",
            "trust_class": "summarized",
            "confidence": 0.8,
            "tags": tags,
        },
        indent=2,
    )

    lines = [
        "Batman phase checkpoint ARMED (PostToolUse hook) -- phase {0} ({1}), "
        "task_slug={2}, namespace={3}.".format(
            target["phase"], target["label"], target["slug"], target["namespace"]
        ),
        "You just wrote {0}.".format(target["artifact"]),
        "",
        "This hook wrote NOTHING to mnemo. It cannot: it sees a file, not an "
        "approval, and this artifact is still a draft. The curated write is "
        "yours, and it fires AFTER the gate:",
        "",
        "1. Run the grill-me pass and request explicit user approval of {0}.".format(
            target["label"]
        ),
        "2. ONLY once the user approves, call mnemo memory_write with exactly "
        "these parameters (this envelope matches the existing batman-spec "
        "corpus -- do not vary it):",
        call,
        "",
        "3. `text` is a curated distillation, not a copy of the artifact: what "
        "was approved, the rationale, and what the next phase must honour. "
        "Verbatim for big decisions and technical rationale. Reference {0} for "
        "the full body -- the artifact stays the source of truth. Never store "
        "secrets or tokens.".format(target["artifact"]),
    ]

    if prior:
        lines += [
            "",
            "4. SUPERSEDE FIRST -- a live checkpoint already exists for this "
            "slug and phase. Before the write, call:",
            '     memory_forget(memory_id="{0}", reason="superseded by phase-{1} '
            're-approval")'.format(prior.get("memory_id"), target["phase"]),
            "   Prior item: writer={0} timestamp={1}".format(
                prior.get("writer"), prior.get("timestamp")
            ),
            "   Prior text (first 400 chars): {0}".format(
                (prior.get("text") or "")[:400]
            ),
            "   Never leave two `active` items for the same slug and phase.",
        ]
    else:
        lines += [
            "",
            "4. No prior checkpoint exists for this slug and phase -- no "
            "memory_forget needed. This is the first write.",
        ]

    lines += [
        "",
        "If the user rejects or revises the artifact, do NOT write. Re-arm "
        "happens on the next edit. Durable memory writes carry standing "
        "approval (user directive 2026-07-16), so the memory_write itself needs "
        "no separate permission -- only the phase approval gates it. Contract: "
        "shared-memory skill, 'Phase checkpoints'.",
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
        return  # not a Batman phase artifact -- stay silent, cost nothing

    try:
        prior = find_prior(target["namespace"], target["slug"], target["phase"])
    except Exception:
        # mnemo down/unreachable is the shared-memory skill's documented safe
        # fallback. Still arm the write; just cannot name a supersede target.
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
        # Absolute backstop: this hook never fails an edit.
        pass
