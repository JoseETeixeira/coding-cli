# 0011 — Fail open for compaction, fail closed for material continuation

Status: accepted · 2026-08-01

## Context

Compaction can occur at a host's hard context boundary and in the middle of a turn. Claude Code permits `PreCompact` hooks to block, and Codex supports a similar continue decision. Blocking because optional state, mnemo, Qdrant, or a helper failed can turn a recoverable context problem into a failed request. Letting the immediate continuation edit or repeat an external action from missing, stale, or contradictory state is the opposite failure: it can corrupt source or duplicate a non-idempotent effect.

These risks require different failure behavior on the two sides of the native compactor.

## Options considered

1. **Fail closed before compaction.** Protects capture completeness, but can prevent the only operation that lets the host continue at its context limit.
2. **Fail open throughout.** Maximizes availability, but permits writes and side effects from unvalidated summary state.
3. **Fail open before compaction and fail closed after it (chosen).** Preserve native recovery, then require authoritative reconstruction before material action.

## Decision

`PreCompact` never blocks native compaction. It attempts an atomic metadata capture and records only a content-free failure category when capture is unavailable.

Compact-sourced `SessionStart` rebuilds authoritative fingerprints. Valid state enters `validation_required` and permits only conservative read-only reconstruction until explicit validation. Missing, malformed, stale, oversized, contradictory, approval-ambiguous, or action-ambiguous state enters visible degraded mode. When safe read-only classification or reconstruction is impossible, the immediate continuation ends and the owner uses targeted recovery or the existing fresh-session handoff path.

Locally observable material tools are denied while the gate is active. Activation inventories the effective tool surface and disables write-capable hosted or specialized tools outside hook coverage only inside the pilot process/profile; if that cannot be done without changing the user's base configuration, activation refuses. The pilot still describes tool hooks as a guardrail rather than a complete host security boundary.

## Consequences

- Optional memory and hook failures cannot prevent necessary native compaction.
- Recovery may pause work and require source reads or one targeted user decision; that friction is deliberate.
- A metadata-only action journal is needed to distinguish completed, failed, pending-approval, and ambiguous material operations across a mid-turn compact.
- Successful current-epoch reads are recorded as path/hash evidence, without source bodies, so validation cannot be cleared by merely naming an unread file.
- The read-only classifier must be conservative, tested on Windows and claimed on POSIX only after equivalent fixtures pass.
- Real-host acceptance must demonstrate zero material actions before validation, not merely inspect unit-test output.

## Rollout and rollback

The gate exists only inside the opt-in pilot profile/overlay. Disabling the pilot removes its gate and restores native host behavior without deleting recovery state, source, memory, artifacts, or transcripts. Private pilot state can be purged separately.
