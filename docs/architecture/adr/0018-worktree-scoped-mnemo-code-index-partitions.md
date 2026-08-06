# 0018 — Worktree-scoped, versioned mnemo code-index partitions

Status: accepted · 2026-08-06

## Context

Mnemo's source index currently uses a repository root-commit ID for manifests, locks, deterministic vector IDs, Qdrant payload filters, progress, debounce, search, status, and stale deletion. That ID is useful as a repository-family diagnostic and survives a checkout move, but linked worktrees and independent same-history clones share it. One agent can therefore query or report another worktree's last indexed source before asynchronous refresh replaces the shared partition.

Durable `mnemo_memory` has the opposite boundary: repository facts, Batman checkpoints, and handoff pointers must remain shared across worktrees. The source cache is rebuildable; memory and source are not.

The persisted identity decision is hard to reverse, surprising without context, and has real reuse-versus-safety trade-offs, so it warrants an ADR.

## Options considered

1. **Keep root-history identity and add a freshness barrier.** Rejected. It still shares locks, progress, debounce, deletion, and partition ownership; a barrier must synchronously prove/rebuild current contents before every query to prevent stale cross-worktree results.
2. **Key by canonical working-directory path only.** Rejected. It isolates live paths but a removed/recreated working tree at the same path can inherit the old cache before refresh.
3. **Key by branch, HEAD, or content snapshot.** Rejected. Branch/HEAD are shared or change too often, dirty content is expensive to fingerprint, and snapshot keys create unbounded partitions while confusing working-tree identity with freshness.
4. **Write a random UUID into source or Git metadata.** Rejected. It gives strong incarnation identity but violates the no-repository-mutation boundary and adds cleanup/coordination state to user repositories.
5. **Use a versioned worktree-incarnation proof and quarantine legacy cache (chosen).** Derive an opaque scope from canonical root/per-worktree Git paths plus stable filesystem identity for the Git administrative directory and marker. Use that scope at every code-cache boundary; keep repository-family identity diagnostic-only; rebuild rather than rebind ambiguous data.

## Decision

- Preserve existing `repo_id` as the repository-family compatibility/diagnostic field. It does not key mutable v2 code-cache operations.
- Add `code_index_scope = wt2_<digest>` for one working-tree incarnation. The digest uses canonical working-tree/Git paths and non-zero filesystem object identity for Git's per-worktree administrative directory and stable marker, with birth time where available. Missing or ambiguous proof fails closed.
- A working-tree move produces a new scope and rebuilds. Removing/recreating at the same path produces a new incarnation proof and cannot query the old scope.
- Store v2 local state under `~/.mnemo/code/v2/<scope>/`.
- Add Qdrant payload/filter keys `code_index_scope` and `repository_family_id`. V2 points omit legacy `repo_id`; legacy points omit `code_index_scope`. V1 and v2 therefore cannot match each other's queries.
- Key deterministic point IDs, manifests, locks, progress, background threads, debounce, count, search, reindex, per-file sweep, and full-scope deletion by `code_index_scope`.
- Require a valid v2 manifest binding before querying a scope. Missing, corrupt, or mismatched binding reports unindexed/rebuild-required.
- Do not automatically delete or reuse legacy cache. First access rebuilds v2; optional operator cleanup may remove only rebuildable `mnemo_code` and `~/.mnemo/code/` data.
- Keep `mnemo_memory`, event logs, repository-scoped task namespaces, tool names/arguments, services, credentials, and host registrations unchanged.

## Consequences

**Benefits**

- Different worktrees and clones cannot read, overwrite, delete, lock, debounce, or report each other's code cache.
- Same-worktree agents still share deterministic incremental state.
- Legacy cache is non-queryable without a destructive migration.
- Old binaries do not see v2 points through their family `repo_id` filter.
- Identity remains local and bounded; no embedding/network call is needed.

**Costs**

- Every existing worktree performs one v2 rebuild after upgrade.
- Moves and conservative proof changes rebuild rather than reuse embeddings.
- Legacy cache consumes disk/Qdrant space until optional cleanup.
- Filesystems that cannot provide a safe Git-admin object identity receive a typed refusal instead of path-only indexing.

**Accepted risk**

- Same-worktree asynchronous snapshots may lag later edits. Responses must label this and require source verification.
- Platform filesystem identity has different primitives; the implementation must validate non-zero/stable evidence in real Windows/POSIX tests and fail closed when unavailable.

## Rollout and rollback

1. Ship v2 identity, payload indexes, manifest binding, tests, and additive diagnostics together.
2. Reload MCP server processes; let each worktree build its new scope lazily or through explicit reindex.
3. Leave legacy data quarantined by default. Document exact optional code-cache cleanup and prohibit memory/source/Git deletion.
4. Before rollback, stop/reload the server and clear rebuildable code cache if a clean old-version rebuild is desired. Never delete `mnemo_memory` or `~/.mnemo/events/`.
5. Rollback restores the old history-only limitation; it cannot preserve worktree isolation by itself.
