# PRD: mnemo worktree-aware code index identity

Status: Implemented · 2026-08-06

## Problem

Mnemo resolves the correct Git worktree root but keys its semantic code index only by repository root history. Related primary checkouts, linked worktrees, and clones can therefore overwrite and query one manifest/Qdrant partition even when their source differs. Background refresh is asynchronous, so another task's cached chunks and status may be observed before the active tree rebuilds.

Durable mnemo memory has the opposite requirement: repository facts, approved Batman checkpoints, and handoff pointers must remain shared across worktrees.

## Goals

- Give every distinct Git working directory an isolated code-index scope.
- Bind manifests, points, filters, IDs, locks, progress, debounce, search, status, reindex, and stale cleanup to that scope.
- Keep `mnemo_memory` repository-family scoped and behaviorally unchanged.
- Report unindexed/building/index-snapshot state truthfully without claiming semantic results are current-source proof.
- Transition legacy history-only cache data without cross-scope leakage or durable-memory mutation.
- Preserve current MCP tools, dependencies, registrations, non-blocking refresh, interruption recovery, and Git safety.

## Non-goals

- Synchronously re-index before every search.
- Make semantic search authoritative.
- Change durable-memory namespaces, ACLs, redaction, revocation, events, or task-context behavior.
- Add a service, port, credential, provider, dashboard, watcher, or host registration.
- Change default untracked/binary/map indexing.
- Mutate source or Git metadata to store index identity.

## Scope

- `mnemo/mnemo/code_index.py`: repository/working-tree identity and every code-cache boundary.
- `mnemo/mnemo/server.py`: additive public identity/freshness diagnostics and typed errors.
- `mnemo/tests/test_code_index.py`: real primary/linked/clone isolation, lifecycle, concurrency, migration, and regression proof.
- `mnemo/tests/mcp_smoke.py`: code-tool discovery/public-contract smoke.
- `mnemo/README.md`: code-index setup, settings, scope, refresh, upgrade, verification, rollback.
- `CONTEXT.md`, Batman artifacts, and one Design-phase ADR if the final identity/migration trade-off passes the repository's ADR test.

## Acceptance Criteria

- Primary checkout, linked worktrees, and same-history clones derive distinct code-index scopes; two agents/path variants resolving one physical tree derive the same scope.
- Search/status/reindex/manifest/lock/progress/debounce/stale deletion cannot cross scopes.
- A never-indexed scope does not inherit related-scope chunks, counts, timestamps, or progress.
- Legacy history-only partitions are non-queryable as current scope unless safely validated/rebound; rebuild/cleanup never touches durable memory.
- Move/recreate/branch lifecycle fails to unindexed/rebuild rather than silently inheriting another task's chunks.
- Existing tool names/arguments remain; responses distinguish repository family, working tree, and code-index scope.
- Focused/full mnemo tests and stdio smoke pass; real-Qdrant/OpenAI gates are reported separately when unavailable.

## Verification

- Deterministic fake-embedder tests over real temporary Git repositories, linked worktrees, and clones.
- Qdrant-backed focused and full `mnemo/tests` runs.
- Updated stdio MCP smoke covering memory and code tools.
- Scoped Ruff/compile checks plus `git diff --check`.
- Live status/search probes from two real task worktrees after merge/reload, reported separately from local test acceptance.
