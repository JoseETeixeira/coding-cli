# 0010 — Native compaction with bounded deterministic rehydration

Status: accepted · 2026-08-01

## Context

Long Codex and Claude Code sessions repeatedly carry stale conversation and tool output, reducing coherence and increasing token cost. Both hosts already own supported manual and automatic compaction, but a default summary alone cannot prove that a large intertwined repository's exact current state, approval boundaries, dirty paths, and cross-system invariants survived. A custom transcript pruner would provide more apparent control at the cost of coupling to private formats, duplicating sensitive content, and risking replay corruption.

The durable state already used by this repository lives in current source, Git, approved Batman artifacts, and pointer-oriented mnemo records. Conversation history is therefore a cache, not the correct place to build a second source of truth.

## Options considered

1. **Use host defaults only.** Minimal implementation, but no deterministic re-entry, aggregate memory budget, degraded state, or cross-host evidence contract.
2. **Rewrite or externally store host transcripts.** Fine-grained turn selection, but private-format lock-in, secret-retention expansion, and high corruption risk.
3. **Use native compaction plus a shared bounded rehydration layer (chosen).** Host summaries retain transient intent; a metadata-and-pointer envelope reconstructs authoritative task state and requires current-source validation.

## Decision

Keep transcript compaction entirely inside Codex and Claude Code. Add one host-neutral, standard-library lifecycle core that:

- gives native summarizers a canonical compact contract;
- captures only bounded repository/task/action metadata and deterministic pointers before compaction;
- rebuilds and compares current Git/source/artifact state after compaction;
- injects at most 8,000 Unicode characters or 2,000 estimated tokens;
- keeps memory optional and requires explicit full retrieval by pointer;
- uses thin Codex and Claude adapters for their documented lifecycle/config syntax.

The pilot does not promise selective deletion of arbitrary turns and does not claim to shrink fixed system/developer instruction prefixes that hosts re-inject.

## Consequences

- The architecture stays compatible with supported host behavior rather than private transcript formats.
- Exact code and cross-system facts remain re-readable from their authoritative source instead of being duplicated into summaries.
- Two small host adapters remain necessary, and their numeric trigger settings must be measured independently.
- A compact summary can still be incomplete; material continuation depends on revalidation, not summary confidence.
- Plugin packaging can reuse the same core later, but plugin installation is not required to prove the initial pilot.

## Rollout and rollback

Ship the core disabled. Activate only through a named Codex profile or Claude settings overlay for an allowlisted repository. Rollback removes those isolated pilot layers and leaves native compaction, transcripts, source, artifacts, memory, and primary user configuration unchanged.
