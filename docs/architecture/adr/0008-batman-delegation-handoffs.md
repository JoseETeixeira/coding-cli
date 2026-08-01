# 0008 — Batman delegation handoffs: file body, mnemo pointer, hook arms

Status: accepted · 2026-07-24

## Context

The orchestrator/subagent context-passing contract (`shared-memory` → "Delegation handoffs", added 2026-07-24) routes gathered findings between subagents so they never occupy the orchestrator's window: the subagent returns a compact control-plane summary and the payload travels out of band. Two questions were left: WHERE the payload lives, and HOW the write is made reliable.

The first draft said "the full findings body goes to mnemo." ADR 0007 already recorded why that is wrong for any non-trivial body: `MemoryEngine.write` embeds `text` as a single vector (`engine.py:231`), so a document collapses to one centroid and retrieves as noise. Phase checkpoints resolved the same tension by keeping the artifact on disk and storing only a curated distillation. Handoffs share the geometry.

Separately, prose that only asks the model to "write a handoff before returning" has the documented failure mode from 0007: before/after-every-X compliance degrades to zero without a harness hook.

## Options considered

1. **Body in mnemo `text`.** Rejected — one-vector geometry (0007); non-trivial bodies retrieve as noise.
2. **Body in the subagent return, orchestrator forwards it.** Rejected — that is the pass-through tax the whole contract exists to remove; the payload lands in the orchestrator's window and is paid for again on the way out.
3. **Body in a `.batman/<slug>/handoffs/<stem>.md` artifact; mnemo carries a curated summary + artifact path + the `memory_id` pointer; a PostToolUse hook arms the mnemo write off the artifact (chosen).** Reuses the proven `batman-phase-checkpoint` machinery byte-for-byte.

## Decision

- **Full body → `.batman/<slug>/handoffs/<stem>.md`**, disk is source of truth. `<stem>` encodes task and role, e.g. `task-3.gather`, `task-3.exec`.
- **mnemo `batman-handoff` item = curated summary + artifact path + pointer.** Envelope: `type="handoff"`, `trust_class="summarized"`, `confidence=0.8`, `namespace="repo:<name>"`, `tags=["batman-handoff","<slug>","handoff:<stem>","active"]`. `trust_class=summarized` for 0007's reason — the distillation is not authority; the artifact and current source are.
- **Deterministic retrieval.** The orchestrator forwards the `memory_id`; the next link calls `memory_get` for summary + path, then reads the artifact for the body. Semantic search only for cross-cutting discovery the gatherer did not hand over.
- **A PostToolUse hook** (matcher `Write|Edit|MultiEdit|NotebookEdit`) at `.claude/hooks/batman-handoff-checkpoint.py` arms the write off the artifact and names the `memory_forget` target when a live item exists for the stem. It arms; it never writes. No approval gate — durable writes carry standing approval (2026-07-16) — so the arm says "write now, before you return your pointer".
- **Invariant: exactly one live item per `(namespace, slug, stem)`.** Re-run supersedes via `memory_forget` + fresh write.
- **Ownership split mirrors 0007**: `batman.agent.md` owns the delegation trigger, `shared-memory` → "Delegation handoffs" owns the contract, the hook owns delivery.
- **Fail-soft absolute**: path gate before any import, local scroll for the prior (no embed, no network), no `decision` field on any path, every exception silent. The hook cannot block an edit.

## Consequences

- The residual discretion is the write itself, JIT-injected pre-filled at the artifact — categorically different from the 0007 failure where prose was never read.
- **Drift-immune**: registered in `settings.json`, the hook fires whichever installed copy loaded.
- Runs alongside `batman-phase-checkpoint` on the same PostToolUse matcher; the two never collide (disjoint path patterns — `spec|steering` vs `handoffs`), each path-gates and exits silent on a miss, so the cost of the second hook on an unrelated edit is one regex.
- **Net-token gate preserved**: for a one-shot executor where a compact summary suffices, inline it in the return and skip both the artifact and the mnemo item.
- No `batman-handoff` hook can know it is the gatherer vs the executor writing — the `<stem>` filename convention carries that, and the hook treats it as an opaque discriminator. Keep the role in the filename.

Verified: offline cases (fire, both miss paths, supersede branch, garbage/empty stdin, relative-path join, `tool_response.filePath` fallback, slug/stem isolation) plus a live in-session fire.
