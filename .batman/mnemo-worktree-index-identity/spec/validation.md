# Validation: Mnemo Worktree-Aware Code Index Identity

Status: Complete with registered-host reload open · 2026-08-06

## Shipped Outcome

Mnemo now preserves root-history `repo_id` as repository-family diagnostics while deriving opaque `wt2_` code-index scope from each canonical Git worktree incarnation. V2 manifests, Qdrant payloads/filters/IDs, locks, progress, background threads/debounce, status, search, reindex, and cleanup use that scope. V1 cache is quarantined. Durable memory code, event semantics, namespaces, services, ports, credentials, and host registrations are unchanged.

## Validation Matrix

| Gate | Result | Evidence |
|---|---|---|
| Untouched focused baseline | PASS | `25 passed` in 17.46s; Qdrant reachable; zero skips. |
| Identity RED | EXPECTED FAIL | Four new worktree identity/lifecycle tests failed because `code_index_scope` did not exist. |
| Final focused code index | PASS | `61 passed` in 91.64s against real Qdrant with deterministic fake embeddings. |
| Pure identity without Qdrant | PASS | `7 passed, 54 deselected` with `MNEMO_QDRANT_URL=http://127.0.0.1:1`. |
| Full mnemo regression | PASS | `84 passed` in 103.04s. |
| Fresh stdio/live dependencies | PASS | All 11 memory/code tools discovered; isolated code status plus memory write/search/context/get/forget passed with real OpenAI/Qdrant. |
| Scoped Ruff | PASS | Changed Python files: `All checks passed!`. |
| Compile/import | PASS | `py -3.12 -m compileall -q mnemo`. |
| Markdown/placeholders/fences | PASS | Task artifacts, PRD, ADR, and README validated. |
| Diff whitespace | PASS | `git diff --check`; only Git LF-to-CRLF notices. |
| Installed MCP process | RELOAD OPEN | Registered process still returned legacy status without `code_index_scope`; it was not killed/reloaded while connected. Fresh stdio process loaded and passed updated code. |

Pytest emitted only the existing `pytest-asyncio` default-loop-scope deprecation warning.

## Real-Git and Recovery Evidence

- One primary checkout, two linked worktrees, and two same-history clones indexed conflicting content at one relative path with distinct scopes and zero cross-scope hits, counts, deletion, reset, manifest, progress, lock, or debounce interference.
- Same-tree root/subdirectory variants remained deterministic and incrementally skipped unchanged files.
- Move, linked-worktree removal/recreation, branch switch, detached HEAD, relative administrative paths, missing/zero/unreadable identity proof, and Git timeout/stdin behavior passed.
- Missing, corrupt, structurally malformed, mismatched, legacy, interrupted, collection-recreated, and collection-renamed state failed closed or rebuilt only the active v2 scope.
- Empty-file shrink, file/hash/Git failures, deterministic point recovery, stale deletion, full reset, failed-background retry, and mutable-progress races have regressions.
- Smoke uses throwaway memory/code collections and a throwaway data directory, then removes them; live durable-memory events/cache are not test targets.

## Requirement Disposition

- R1: satisfied by deterministic, fail-closed worktree-incarnation identity tests.
- R2: satisfied; memory engine/collection/events/namespaces were not changed, and stdio memory behavior passed.
- R3: satisfied by scope-only local/Qdrant/background boundaries and five-tree interference tests.
- R4: satisfied by manifest-gated search, explicit states, snapshot metadata, and source-verification wording.
- R5: satisfied by v2 quarantine, no legacy rebinding/deletion, collection recovery, and documented cleanup/rollback.
- R6: satisfied by move/recreate/branch/detached lifecycle tests.
- R7: satisfied by strict paths, protected roots, bounded Git, `stdin=DEVNULL`, and typed proof/Git failures.
- R8: satisfied in fresh server tests: tool names/arguments unchanged; identity/state fields additive; errors typed/content-safe. Installed host reload remains operationally open.
- R9: satisfied by same-scope incremental reuse, scope-parallel background state, success-only debounce, and interruption recovery.
- R10: satisfied by real-Git/Qdrant tests, isolated stdio smoke, README operations guidance, and separated gate reporting above.

## Phase 7 Findings Resolved

Review found and fixed mutable cross-thread progress references, false-ready interrupted runs, completion stamping after per-file/Git/hash failure, stale chunks after empty-file shrink, failure debounce, post-start reindex failure, missing typed search initialization, malformed manifest acceptance, and stale-manifest reuse after code-collection recreation/change. All affected gates were rerun.

## Production Concept Ledger

- `IDENTITY_VERSION`: public/persisted worktree identity contract version.
- `MANIFEST_SCHEMA_VERSION`: local v2 manifest compatibility boundary.
- `SNAPSHOT_SEMANTICS`: one canonical public freshness disclaimer.
- `WorktreeIdentityUnavailable`: typed refusal when safe scope proof cannot be established.
- `WorktreeIdentity`: immutable internal proof result; raw filesystem values never leave derivation.
- `RepoInfo.worktree` / `code_index_scope`: separates repository-family diagnostics from cache authorization.
- `_canonical_path` / `_canonical_git_path`: strict platform-aware root and Git-admin resolution.
- `_path_identity` / `_hash_identity_parts` / `compute_code_index_scope`: bounded incarnation proof and length-delimited opaque digest.
- `Manifest.matches` / `bind` / `chunk_count`: binding and vector-cardinality gate for safe incremental reuse.
- `indexing`: persisted incomplete-run marker used to distinguish interrupted snapshots.
- `code_collection`: persisted binding that prevents one configured collection from inheriting another's manifest.
- `ProgressRegistry`: synchronized, copy-on-read/write scope progress shared across foreground/background clients.
- `_scope_filter` / `_delete_scope_points` / `_count_scope_points`: single source for scope-only Qdrant operations.
- `_progress_registry`: process-level registry injected into all code-index clients.
- `_repo_error`: shared MCP mapping for repository, Git, and identity failures.
- `repository_family_id`, `identity_version`, `index_state`, `snapshot_head`, `snapshot_semantics`: additive public diagnostics; existing `repo_id` meaning remains compatible.

Test-only function names are scenario labels and introduce no production concepts.

## Upgrade and Rollback Warning

After host reload, each worktree lazily builds `~/.mnemo/code/v2/<scope>/`. Legacy history-only cache remains non-queryable and is not deleted automatically. Optional cleanup may remove only the exact configured `mnemo_code` collection and/or exact `MNEMO_DATA_DIR/code/` cache while MCP servers are stopped. Never remove `mnemo_memory`, `MNEMO_DATA_DIR/events/`, source, Git metadata/config, credentials, key files, or host registration. Rollback restores the old cross-worktree limitation.
