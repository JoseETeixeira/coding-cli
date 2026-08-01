# 0007 — Batman phase checkpoints: the hook arms, the model writes

Status: accepted · 2026-07-16

## Context

`generic-entry` has asserted since 2026-07-16 that mnemo "also holds task/spec state (namespace `repo:<name>`)". Nothing ever wrote it. Every mnemo verb mandated anywhere in the tree was a read — `memory_status`, `task_context` (`generic-entry:10`, `batman.agent.md:17`, `batman-understanding:41`, `design.prompt.md:631`) — and `shared-memory`'s write section described only *mechanics*, with a discretionary trigger: "call `memory_write` whenever you judge something worth storing."

The gap was invisible because the store looked populated: 41 `type=spec` items existed. All 41 carry the `migrated-from-claude-md` tag — a frozen snapshot from the workspace `CLAUDE.md` deleted on 2026-07-16. State was migrated in and nothing ever appended. Write-once, then silence.

There is direct prior art on the failure mode. The mnemo *read* preflight was mandated in both `CLAUDE.md` and `batman.agent.md` prose and **silently never fired in either host** (recorded in `hooks/mnemo-preflight.py:3-8`). It only became real when it was made a `SessionStart` hook. The lesson recorded then: the harness executes hooks; prose only *asks* the model to comply, and for "before/after every X" behaviour that compliance degrades to zero.

"Store phase state after each planning phase" is exactly that shape.

## Options considered

1. **Prose-only.** Add the mandate to `generic-entry` and/or the four phase prompts. Cheapest. This is the option with a documented 0% hit rate on this machine.
2. **Hook writes to mnemo directly.** Fully deterministic, zero model discretion. Verified implementable — `MemoryEngine.write` is importable exactly as `mnemo-preflight.py` already imports `.status()`. Rejected on correctness, not feasibility:
   - `engine.py:231` is `embed_one(text)` — **one vector per item over the whole text**. An auto-dumped 22 KB `design.md` collapses to a single centroid and retrieves as noise. Every one of the 41 existing items is a terse summary; none is a pasted document.
   - `PostToolUse` fires on **every edit**, which during the `grill-me` pass is a draft the user is actively rejecting. It would persist exactly the state grilling exists to discard.
   - **The harness has no approval event.** A hook sees a file, not an approval. It physically cannot distinguish approved from rejected.
3. **Hook arms, model writes (chosen).** The hook detects the artifact, derives slug/phase/namespace, looks up the prior checkpoint, and injects a pre-filled `memory_write` into context. The model performs the curated write at the approval gate.

## Decision

A `PostToolUse` hook (`matcher: Write|Edit|MultiEdit|NotebookEdit`) at `.claude/hooks/batman-phase-checkpoint.py`, registered as a pointer in `~/.claude/settings.json`.

- **It arms; it never writes.** It emits `hookSpecificOutput.additionalContext` naming the exact parameters and, when a prior checkpoint exists, the `memory_forget` target. mnemo is touched only by one local read.
- **Envelope is uniform across all four phases**: `type="spec"`, `trust_class="summarized"`, `confidence=0.8`, `namespace="repo:<name>"`, `tags=["batman-spec","task-state","<task_slug>","phase-<n>","active"]`. This matches the existing `batman-spec` corpus byte-for-byte. `type` stays `spec` because `memory_search` filters only on `type` and `trust_class` (`engine.py:279`) — there is no tag filter, so `type` is the only coarse retrieval axis and phase is a facet, not an axis.
- **`trust_class=summarized`, not `observed`.** A checkpoint is a distillation; the artifact on disk stays authoritative. Writing checkpoints at `observed` would elevate memory toward authority, contradicting the core rule that memory is optional context, never authority.
- **`text` is a curated summary, never the artifact body** — forced by the one-vector-per-item geometry above.
- **Fires at the approval gate.** Not on creation (draft-1 is what grilling exists to change), not on every edit.
- **Phases accumulate; a phase supersedes only its own prior checkpoint** via `memory_forget` + fresh write. Invariant: exactly one live item per `(namespace, task_slug, phase)`.
- **Cost discipline**: the path gate runs *before* any import, so a miss costs one regex. The prior lookup uses `MemoryEngine.list` → `client.scroll` (`engine.py:315`) — payload filter only, local, no embedding, no network. Repo namespace is derived from the directory above `.batman/` by string search, deliberately avoiding a `git` subprocess (see the `_run_git` stdin-inheritance hang, fixed 2026-07-16).
- **Fail-soft absolute**: no `decision` field on any path; every exception returns silently; bare `except` at `__main__`. The hook cannot block an edit even with mnemo, Qdrant, or Python broken.

Ownership is split so nothing is stated twice: `generic-entry` step 2 owns the **trigger**, `shared-memory` → "Phase checkpoints" owns the **contract**, the hook owns **delivery**.

## Consequences

- The residual discretion is the write itself. This is unavoidable — approval is a user utterance, not a harness event — but it is categorically different from the failure that motivated this: there, the prose was never read. Here the obligation is JIT-injected, pre-filled, at the exact artifact, by the harness.
- The hook is **drift-immune**, which matters independently: a canonical-only prose edit reaches Codex and nothing else, because Claude Code loads its own installed copies. Registered in `settings.json`, the hook fires whichever copy loaded.
- Load-bearing rules (memory authority; the checkpoint envelope) live **inline in the hooks**, not behind a pointer, so they survive a missing or moved canonical checkout. Keep it that way.
- Precedent followed: `.claude/hooks/auto-improvement-nudge.sh` already injects an obligation rather than performing the action.

Verified: 12/12 offline cases (all four phases, both miss paths, garbage/empty stdin, relative-path join, `tool_response.filePath` fallback, supersede branch, slug isolation, phase isolation, revoked-item exclusion) plus a live in-session fire with no restart required.
