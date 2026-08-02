# 0012 — Bounded previews for default mnemo task context

Status: accepted · 2026-08-01

## Context

`task_context` currently returns the complete `text` of each of eight ranked memory items. A live scoped call for this task returned 35,610 text characters before metadata, approximately 8,903 text tokens at the coarse four-characters-per-token rule. This can refill a compacted session immediately and gives long records more hot-context weight than their relevance warrants.

Mnemo's append-only event log and authorized memory records remain useful durable context, but current source and approved artifacts are authoritative. Exact full bodies already have a deterministic retrieval API: `memory_get(memory_id)`.

## Options considered

1. **Keep full bodies and lower `top_k`.** Reduces breadth and can hide an intertwined-system dependency while still allowing one very large result.
2. **Generate new summaries on every recall.** Adds latency, cost, non-determinism, and another lossy authority-like copy.
3. **Return ranked bounded previews plus IDs (chosen).** Preserves breadth, makes truncation explicit, and leaves exact retrieval intentional.

## Decision

Change the default `task_context` serialization contract to version 2:

- aggregate returned memory `text` is at most 4,000 Unicode characters;
- each ranked item receives at most a 500-character preview by default;
- ACL, namespace, trust, revocation, TTL, and ranking filters run before budgeting;
- existing order and metadata remain;
- additive response fields report budget, used characters, matched/returned/omitted counts, per-item and aggregate truncation, original text length, and whether `memory_get` is required;
- a default 8,000-character response-envelope ceiling may omit lower-ranked metadata records and reports that omission;
- `memory_get(memory_id)` remains unchanged and returns the full authorized record.

## Consequences

- Default recall falls from unbounded full bodies to a predictable token ingress while usually retaining all eight ranked pointers.
- Callers that assumed `task_context.items[].text` was complete must honor `text_truncated` and explicitly retrieve exact records.
- Phase checkpoints and handoffs remain discoverable by ID/path, matching their existing artifact-plus-pointer design.
- No Qdrant collection or event-log migration is required; only server serialization, configuration, guidance, and tests change.
- Operators can tune budgets by validated configuration, but acceptance is against the approved defaults.
- Sharing one canonical budgeter makes `mnemo.engine` depend on `context_compaction`,
  which lives a level above it at the repository root. `mnemo` must therefore resolve
  that root itself rather than relying on an entrypoint to inject it: it is embedded as
  a **library** by the SessionStart preflight and both Batman checkpoint hooks, not only
  by `run_server.py`. Regression evidence and the appended-not-inserted path rule are in
  `.batman/cross-host-context-compaction/spec/evidence/mnemo-library-import-regression.md`.

## Rollout and rollback

Add characterization and contract tests before changing serialization. Deploy the additive metadata and preview behavior together with updated shared-memory guidance. Rollback can restore full serialization without touching stored memory, though doing so reintroduces the measured context-ingress risk.
