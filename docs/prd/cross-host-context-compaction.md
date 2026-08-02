# PRD: Cross-Host Context Compaction Pilot

- **Status:** Implementation in progress
- **Date:** 2026-08-01
- **Owner:** Repository owner
- **Requirements:** `.batman/cross-host-context-compaction/spec/requirements.md`
- **Design:** `.batman/cross-host-context-compaction/spec/design.md` 1.2.0
- **Task plan:** `.batman/cross-host-context-compaction/spec/tasks.md`
- **Approved current state:** `.batman/cross-host-context-compaction/steering/understanding.md`

## Problem

Long Codex and Claude Code sessions repeatedly process stale conversation, previous file reads, and oversized tool or memory payloads. This increases token use and lets old state compete with current source. Native compaction reduces history, but a summary alone cannot guarantee exact retention of intertwined codebase invariants, dirty-worktree state, approval gates, or pending side effects.

Current `coding-cli` already keeps durable source, approved artifacts, mnemo checkpoints, and handoff pointers outside the hot conversation. Missing pieces are bounded continuation, bounded default memory recall, current-source revalidation after compaction, cross-host activation, measurable acceptance, and safe rollback.

## Goals

- Reduce eligible conversation-history tokens by at least 50% after bounded re-entry.
- Preserve and source-validate 100% of critical benchmark invariants.
- Keep post-compact continuation and default memory recall within explicit budgets.
- Prevent material action from missing, stale, or contradictory continuation state.
- Demonstrate the same semantic guarantees on Codex and Claude Code.
- Make pilot enablement opt-in, observable, version-aware, and reversible.

## Non-Goals

- Replace host-native compaction or transcript storage.
- Delete arbitrary historical turns from live sessions.
- Make memory or summaries authoritative.
- Roll out globally before allowlisted real-session acceptance.
- Add other agent hosts, a new database, or model training.

## Users

- Primary: repository owner operating long tasks across large, multi-language, intertwined codebases.
- Secondary: Codex/Claude Code agents and future `coding-cli` maintainers who need safe, explainable task continuity.

## Product Contract

Conversation is a cache. Current source, tests, Git state, approved artifacts, and explicit user decisions remain authoritative. Compaction may remove verbatim conversation and tool output. The continued agent receives only bounded active state and pointers, then reopens authoritative evidence before material action.

Both hosts must satisfy one outcome contract. Their native threshold and hook syntax may differ and must remain host-specific.

## Scope

### Pilot Includes

- Manual and automatic compaction, including mid-turn continuation.
- Bounded active-state recovery and memory previews.
- Source/scoped-rule/Git/artifact revalidation.
- Degraded read-only reconstruction on recovery failure.
- Host-specific activation, version/capability detection, trust, diagnostics, disable, and rollback.
- Deterministic fixtures plus one user-approved representative complex workload.
- Canonical tests, documentation, PRD, and approved ADRs.

### Pilot Excludes

- Global activation across all repositories.
- Raw transcript/source content telemetry.
- Destructive transcript, source, memory, or Git operations.
- Claims of threshold equivalence between Codex and Claude Code.

## Requirement Summary

- **R1-R2:** preserve critical active state; revalidate current authority before material action.
- **R3:** semantic parity on Codex and Claude Code.
- **R4:** bound continuation, memory, and oversized tool ingress.
- **R5-R6:** visible degraded mode and exactly-once mid-turn continuation.
- **R7:** opt-in activation and non-destructive rollback, including a fail-closed semantic guard around Claude's normal first-start registry write.
- **R8-R9:** preserve security/trust boundaries and log content-free measurements; never persist `.claude.json` bodies, values, or absolute project paths.
- **R10-R11:** complex-workload preservation, token, coherence, latency, and no-thrash gates.
- **R12:** preserve Batman, mnemo, handoff, sandbox, approval, and host configuration behavior.

## Acceptance Metrics

- 100% critical and at least 90% overall benchmark probe accuracy.
- No new fabricated exact-code claims versus uncompacted baseline.
- At least 50% measured eligible conversation-body token reduction, or explicitly qualified proxy evidence.
- Automatic continuation at most 8,000 characters or 2,000 estimated tokens.
- Default `task_context` memory text at most 4,000 characters with explicit truncation/pointer metadata.
- No unexplained repeat compaction within ten normal continuation turns.
- Local bounded-state assembly no slower than 2 seconds p95 under recorded benchmark conditions.
- Zero secret leak, duplicate non-idempotent action, unauthorized scope expansion, unrelated config overwrite, or destructive rollback.
- Claude first-start acceptance permits only `numStartups + 1` plus creation of the exact canonical allowlisted project entry with `hasTrustDialogAccepted=true`; every other semantic change stops the exact child and reports `host_registry_drift` without rewriting `.claude.json`.
- Observed activation, failure handling, and rollback on supported Codex and Claude Code versions.
- Repository-owner review of at least one real allowlisted session.

## Rollout

1. Implement deterministic bounded-state and memory-contract tests without host activation.
2. Validate host adapters and settings merge/rollback in isolated fixtures.
3. Enable one allowlisted repository on one host, then the second host.
4. Run matched uncompacted/compacted benchmark and real-session owner review.
5. Keep wider rollout blocked until separate approval.

## Key Risks

- Compaction omits a critical cross-system invariant.
- Re-entry payload or memory recall causes immediate compaction thrashing.
- Mid-turn continuation repeats a non-idempotent operation.
- Claude scoped rules do not reload before an edit.
- Plugin/hook files exist but are not active or trusted.
- Host/version changes invalidate assumed lifecycle behavior.
- Activation overwrites unrelated user configuration.
- Claude startup mutates unrelated host registry state or creates a noncanonical/pretrusted project entry.

Each risk maps to explicit requirements and must receive Design- and Test-phase traceability.

## Approved Design Decisions

- Use an isolated worktree/copy of `C:\Users\josee\source\educode` at the recorded clean commit as the representative complex workload; concrete source-backed probes are frozen during Task Planning.
- Activate through a standalone Codex profile and Claude `--settings` overlay/launcher, with independently measured host-native trigger seeds and no primary user-config rewrite.
- Guard Claude's host-owned `.claude.json` semantically during first-cycle startup: capture a content-free manifest before child launch, allow only the exact startup counter increment plus normal trust entry creation for the canonical allowlisted repository, fail closed on all drift, and never copy, restore, or rewrite the registry. Accepted ADR 0013.
- Diagnose rejected protected-state drift with process-private per-field hashes, but persist only sorted categories from a closed content-free vocabulary; unknown fields collapse to `protected_top_level`. Raw field names, values, and per-field hashes never persist. This adds diagnosis only and does not broaden accepted startup semantics. Accepted ADR 0014.
- Use an owner-created terminal or a separately approved dedicated classic console for live Claude trust; never close Windows Terminal top-level windows as pilot cleanup.
- Initial activation decisions were approved with Design 1.0.0; Refresh 3 guard decisions were approved with Design 1.1.0; Refresh 4 diagnostic decisions were approved with Design 1.2.0 on 2026-08-01.

## Evidence

- Official Codex and Claude Code documentation retrieved 2026-08-01.
- Approved Phase 1 current-state research and visual recap.
- Live mnemo measurement: default top-eight task recall returned 35,610 text characters before envelope overhead.
- Active baseline: Codex CLI 0.145.0 and Claude Code 2.1.220 on Windows; no current compaction pilot active.
- Real-host status: Codex manual recovery/validation/rollback passed; Claude's
  Refresh 3 semantic guard rejected protected registry drift before trust,
  then exact disable/purge passed. One owner-approved unchanged retry reproduced
  the rejection and rollback. One exact owner-approved Refresh 4 diagnostic cell
  then localized protected drift to closed category `feature_state` at 1.051
  seconds, before trust or counter increment; exact rollback passed. Claude
  lifecycle and owner acceptance remain red/open. Category evidence does not
  authorize a compatibility exception or retry.
