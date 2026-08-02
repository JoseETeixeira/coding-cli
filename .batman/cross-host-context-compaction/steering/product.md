# Product Overview

## Product Purpose

`coding-cli` is the canonical, host-agnostic customization layer for coding agents. It gives Codex, Claude Code, and compatible editor agents shared workflows, durable scoped memory, project specialists, prompts, and safety rules without copying canonical bodies into each host.

For this task, product purpose is narrower: reduce stale hot conversation context while preserving safe continuity across large, intertwined codebases on both Codex and Claude Code.

## Target Users

- Repository owner working across large multi-language game, engine, cloud, mobile, ML, and documentation codebases.
- Coding agents that need enough active task state to continue coherently after compaction.
- Future maintainers who must understand why a compacted agent made a decision and where exact evidence lives.

Primary pain points: repeated token cost, coherence loss in long sessions, stale snippets competing with current source, oversized tool/memory ingress, and host-specific behavior drift.

## Key Features

1. **Canonical agent workflow**: Batman routes repository work through source-backed discovery, approval-gated planning, tests, review, and documentation.
2. **Shared durable memory**: mnemo shares scoped facts, decisions, phase checkpoints, and handoff pointers across Codex and Claude Code while remaining subordinate to source.
3. **Cross-host adapters**: thin host configuration and hooks connect canonical behavior to each runtime without duplicating policy.
4. **Context lifecycle control**: the proposed pilot must compact expendable transcript state, bound re-entry payloads, and recover exact context from durable sources.

## Business Objectives

- Lower repeated input-token use in long agent sessions.
- Improve answer coherence by removing stale transcript noise.
- Preserve all critical cross-system invariants and active task state through compaction.
- Apply one semantic contract to Codex and Claude Code while respecting host-specific controls.
- Make activation, degradation, measurement, and rollback observable and safe.

## Success Metrics

- **Critical invariant retention**: 100% of benchmark critical invariants remain recoverable and source-validated after compaction.
- **Hot-context reduction**: at least 50% reduction in eligible conversation-history tokens after compaction and bounded re-entry.
- **Unsafe continuation**: zero material writes made from an unvalidated or silently degraded continuation.
- **Cross-host coverage**: same preservation, security, observability, and rollback guarantees demonstrated on supported Codex and Claude Code versions.
- **Memory ingress reduction**: default task recall stays within its approved aggregate budget while explicit pointer retrieval preserves access to full records.

## Product Principles

1. **Source is truth**: current source, tests, Git state, approved artifacts, and explicit user decisions outrank summaries and semantic memory.
2. **Conversation is cache**: old turns may be summarized or cleared; exact durable evidence must remain re-readable.
3. **Bound every automatic payload**: memory, hooks, tool output, and continuation state must not immediately refill the context window.
4. **Semantic parity, native controls**: Codex and Claude Code must meet the same outcomes without pretending their trigger settings are identical.
5. **Fail visibly and reversibly**: missing or stale continuation state cannot cause silent action; pilot activation must have a tested off switch.

## Monitoring & Visibility

- **Dashboard Type**: host CLI/status surfaces plus concise local pilot diagnostics; no new web dashboard is required.
- **Real-time Updates**: lifecycle event status emitted by each host hook without exposing transcript or secret contents.
- **Key Metrics Displayed**: host/version, trigger, before/after context usage when available, re-entry payload size, validation outcome, degraded-mode reason, and rollback state.
- **Sharing Capabilities**: checked-in benchmark reports and planning/test artifacts; no transcript publication.

## Future Vision

After a successful allowlisted pilot, the same bounded-context contract can support more repositories, models, and hosts. Wider rollout remains evidence-gated; it is not part of the initial pilot.

### Potential Enhancements

- **Adaptive thresholds**: choose host/model/repository thresholds from measured workload behavior.
- **Historical analytics**: compare token savings, compaction frequency, and preservation failures without retaining sensitive content.
- **Broader host support**: add other agent runtimes through thin adapters after semantic compatibility is proven.
