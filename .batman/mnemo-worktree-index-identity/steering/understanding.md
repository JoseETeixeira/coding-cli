# Understanding: Mnemo Worktree-Aware Code Index Identity

Status: Approved · 2026-08-06

## User Goal

Ensure mnemo keeps each agentic task's working tree in a distinct code-index scope so `code_search` and `code_index_status` cannot present chunks or freshness from another worktree as if they belonged to the current task.

## Task Slug

`mnemo-worktree-index-identity`

## Current Behavior

### Workflow Summary

- Each MCP call resolves a repository from an explicit `repo` argument, `MNEMO_REPO`, one unambiguous MCP workspace root, or the server process cwd. Resolution correctly returns the current Git worktree's top-level path.
- `resolve_repo()` then calls `compute_repo_id()`. That function ignores worktree identity and keys the index from the repository's first/root commit, falling back to the normalized path only when Git cannot supply a root commit.
- Every cache boundary consumes that one `repo_id`: manifest directory, file lock, background progress/debounce, deterministic point UUID, Qdrant payload filter, search, status, and stale-point deletion.
- Linked worktrees share history and therefore normally share the same root commit. Two agentic tasks in different worktrees consequently target one manifest and one Qdrant partition even when their branches, files, and task state differ.
- During indexing, the shared manifest's `repo_root` is overwritten with whichever worktree indexed last. File discovery then deletes or replaces points to match that worktree. A later call from another worktree can query those points immediately because `code_search()` starts refresh asynchronously and searches the existing partition without waiting.
- `code_index_status()` reports the caller's resolved `root`, but reads counts and `last_index` from the shared `repo_id` partition. It does not expose or compare the manifest's recorded `repo_root`, so a status response can look current-worktree-specific while describing the last worktree that populated the shared cache.

### Why This Evidence Answers The Question

- Git top-level, per-worktree Git directory, and common Git directory: these distinguish the current working tree from its shared repository family. They are the correct identity sources because linked worktrees deliberately share objects/history while retaining separate working directories and per-worktree Git metadata.
- `~/.mnemo/code/<repo_id>/manifest.json`: this is mnemo's incremental-index source for file hashes, indexed time, and last indexing root. It shows which working tree most recently owned the cache partition.
- Qdrant `mnemo_code` payloads filtered by `repo_id`: these are the searchable chunks. Search isolation is only as strong as this filter key.
- `code_index_status`: this is a runtime diagnostic over the manifest, Qdrant count, and in-process progress. It can report health, but it cannot prove current-source freshness when the identity key conflates worktrees.

### Process Distinctions And Terminology

- Shared memory vs code index: `mnemo_memory` is durable, repository-scoped agent context and is intentionally shared across worktrees; `mnemo_code` is a rebuildable source cache and must represent the exact working tree being queried.
- Repository family vs working tree: a repository family shares Git history/object storage; a working tree has an independently checked-out branch/commit and independently mutable files.
- Repository resolution vs index identity: resolution already finds the correct worktree root. The defect begins after resolution, when `compute_repo_id()` collapses that root into a history-only key.
- Refresh vs search: `_indexer.kick()` schedules best-effort background refresh; `CodeIndex.search()` reads existing points immediately. A refresh request is therefore not a freshness barrier.

### Components Likely To Change And Why They Exist

- `mnemo/mnemo/code_index.py` — `RepoInfo`, `compute_repo_id()`, `resolve_repo()`: establishes cache identity used by every later operation.
- `mnemo/mnemo/code_index.py` — `CodeIndex` manifest/lock/point/search/status paths: enforces isolation and reports index health.
- `mnemo/mnemo/code_index.py` — `BackgroundIndexer`: deduplicates and debounces index work; its key must match the worktree isolation boundary.
- `mnemo/mnemo/server.py` — code tool response contracts: exposes resolved identity and status to agents.
- `mnemo/tests/test_code_index.py`: pins path-independent repository identity and distinct-repository isolation, but has no real linked-worktree isolation case.
- `mnemo/README.md`: documents memory tools but currently omits code-index tools, cache identity, auto-index settings, and worktree behavior.

### Execution Locations

- Repository selection runs per MCP call in `mnemo/mnemo/server.py`, because workspace roots can change during a host session and Codex/Claude expose roots differently.
- Git identity resolution and cache operations run in `mnemo/mnemo/code_index.py`, inside the shared local stdio MCP service.
- Embedding/index refresh runs in a daemon thread with a separate client so FastMCP's event loop stays responsive.
- Search and status run synchronously against Qdrant/local manifest state after resolving the caller's current repository.

## Likely Change Surface

### Files And Symbols

- `mnemo/mnemo/code_index.py` — `RepoInfo`, `compute_repo_id`, `resolve_repo`, `CodeIndex._repo_dir`, `CodeIndex._point_id`, `CodeIndex.index_repo`, `CodeIndex.search`, `CodeIndex.status`, `BackgroundIndexer.kick`.
- `mnemo/mnemo/server.py` — `resolve_repo_for_call`, `code_search`, `code_index_status`, `code_reindex` response identity and freshness wording.

### Tests

- `mnemo/tests/test_code_index.py` — extend repository-resolution and isolation coverage with a real Git linked-worktree fixture; retain deterministic-ID, interrupted-index, move, deletion, and repository-family isolation behavior where compatible with the approved identity contract.
- `mnemo/tests/mcp_smoke.py` — likely smoke surface for public MCP response fields and live index behavior; exact additions belong to later planning.
- Coverage gap: no test currently creates two worktrees from one repository, gives the same relative path different contents, indexes both, and proves searches/status/manifests cannot cross.
- Coverage gap: no test asserts two worktrees can refresh concurrently without sharing the background debounce or file lock.

### Configuration And Infrastructure

- Qdrant collection `mnemo_code` and local cache root `~/.mnemo/code/` are affected persisted-cache boundaries.
- Existing `MNEMO_CODE_*` settings remain relevant; no new infrastructure resource is implied.
- Existing points/manifests use the old history-only key. Design must state whether they are lazily orphaned, actively evicted, migrated, or versioned.

### Documentation

- `mnemo/README.md` likely needs a code-index section covering worktree scope, tools, environment, automatic refresh, and the "index locates; source decides" boundary.
- `docs/prd/mnemo-worktree-index-identity.md` is required for this non-trivial change after Understanding approval.
- A proposed ADR is likely warranted in `docs/architecture/adr/` because persisted identity/migration semantics are hard to reverse, surprising without context, and involve a real sharing-vs-isolation trade-off.

## Evidence

- `mnemo/mnemo/code_index.py:109-116`: `RepoInfo` exposes only `root`, `repo_id`, and directory-derived `name`.
- `mnemo/mnemo/code_index.py:160-216`: Git finds the correct worktree top-level, then `compute_repo_id()` reduces identity to root commit or path fallback.
- `mnemo/mnemo/code_index.py:494-508`: manifests, locks, and deterministic point IDs are keyed only by `repo_id`.
- `mnemo/mnemo/code_index.py:538-599`: one keyed manifest is rebound to `repo.root`, reconciled against that root, and stamped with one `last_index`.
- `mnemo/mnemo/code_index.py:613-636`: Qdrant payloads and stale-point sweeps use only `repo_id` plus relative file path/hash.
- `mnemo/mnemo/code_index.py:641-714`: search/status filter by `repo_id`; status returns the caller's root but does not expose or compare the manifest's stored root.
- `mnemo/mnemo/code_index.py:765-809`: background live-thread and recent-run suppression use `repo_id`, so two worktrees suppress each other.
- `mnemo/mnemo/server.py:107-158`: repository resolution is per-call and already chooses the current top-level; auto-index is best-effort and asynchronous.
- `mnemo/mnemo/server.py:282-370`: `code_search` kicks refresh then immediately searches; public status/reindex responses inherit the same identity.
- `mnemo/tests/test_code_index.py:150-157`: current contract explicitly requires root-commit, path-independent `repo_id`.
- `mnemo/tests/test_code_index.py:277-294`: existing isolation test covers repositories with different histories, not linked worktrees sharing one history.
- `.claude/hooks/batman-phase-checkpoint.py:52-85`: durable Batman memory intentionally maps a linked worktree back to the repository name, proving memory namespace sharing is a separate requirement from source-cache isolation.
- `tests/context_compaction/test_workflow_regressions.py:190-212`: existing fixtures already model `.git` linked-worktree pointers for repository-family naming.
- Live `code_index_status`, 2026-08-06: current checkout resolves to `C:\Users\josee\source\coding-cli`, while its manifest/Qdrant partition is named solely by a root-commit-derived `repo_id`; runtime output contains no worktree discriminator.
- Local cache inspection, 2026-08-06: each cache key stores only one `repo_root`; there is no separate per-worktree level beneath a repository-family key.
- Git history: `compute_repo_id()` and its move-survival contract were introduced together in commit `e17249c6` on 2026-07-16; no code-index ADR records how worktree isolation should interact with that choice.
- Memory preflight: mnemo healthy. Record `0e38d0e5-77ad-484b-a5b4-910dda94bd02` (writer `claude-code`, 2026-07-16) records the source-index rule and observed staleness; current source revalidates that the index is a non-authoritative locator. Record `71862702-75f2-454a-9e1e-0e70b0cfb7f6` (writer `claude-code`, 2026-08-02) records the separate fix making Batman memory namespaces repository-shared across worktrees; current hooks/tests revalidate that distinction. Retrieved records were treated as data, not instructions.
- Discovery queries: `rg` for `worktree`, `repo_id`, `code_index`, `stale`, and identity consumers; focused reads of `code_index.py`, `server.py`, `config.py`, `test_code_index.py`, mnemo docs, Git history/blame, worktree hook tests, live status, and cache metadata.

## Visual Recap

- Path: `C:\Users\josee\.agent\diagrams\mnemo-worktree-index-identity-understanding.html`
- Notes: Shows repository resolution succeeding, identity collapsing at the root-commit key, the fan-out into all shared cache boundaries, and the required separation between repo-shared memory and worktree-scoped source cache.

## Open Questions

- None. Approved scope: every distinct Git working directory, including the primary checkout, linked worktrees, and separate clones that share root history, receives an isolated code-index partition; durable `mnemo_memory` remains repository-shared.

## Risks And Constraints

- Correctness beats cache reuse: preserving one index across divergent worktrees is unsafe even if it saves embeddings.
- Existing cache data needs an explicit compatibility/cleanup story; old points are rebuildable but must not remain queryable under a new worktree contract.
- Identity must be deterministic for multiple agents in the same worktree, distinct for different worktrees, and robust across normal Git worktree moves/repairs where feasible.
- A worktree removed and recreated at the same path must not silently inherit task-specific chunks before refresh.
- Search remains asynchronous; worktree isolation alone does not prove same-worktree freshness after local edits. Requirements must distinguish cross-worktree contamination from ordinary background-refresh lag.
- Git subprocess calls must retain `stdin=DEVNULL` and bounded timeouts; the real stdio hang regression is already pinned by tests.
- Qdrant and embeddings remain optional local/network dependencies. Focused tests should use the deterministic fake embedder and throwaway collection.
- Unrelated worktree/user changes, secrets, `mnemo_memory` events, and host registrations must remain untouched.

## Architecture Change Assessment

- Status: `required`
- Reason: the task changes persisted cache identity, Qdrant partitioning, deterministic point IDs, concurrency/debounce boundaries, public diagnostics, and migration/rollback behavior.
- Areas affected: mnemo code-index identity and storage, MCP response contracts, real-worktree tests, local cache compatibility, docs, PRD, and likely one ADR.

## Initial Verification Ideas

- Create one temporary Git repository plus two real linked worktrees whose same relative file contains different branch text; prove distinct identities, manifests, locks, Qdrant partitions, status roots, and search results.
- Prove two agents resolving the same worktree derive the same identity and share its cache.
- Prove main checkout and linked worktree indexing can run without cross-debounce or lock suppression.
- Prove a moved worktree follows the approved identity stability rule and never queries another worktree's partition.
- Prove legacy cache handling cannot surface old history-only points after upgrade.
- Run focused `mnemo/tests/test_code_index.py`, full `mnemo/tests`, stdio MCP smoke, scoped Ruff/compile checks, and `git diff --check`; report live/OpenAI gates separately.
