# Implementation Plan: Mnemo Worktree-Aware Code Index Identity

Status: Completed · 2026-08-06

## Approved Inputs

- [Requirements](./requirements.md) — approved 2026-08-06
- [Technical Design](./design.md) — approved 2026-08-06
- [Task Constitution](../steering/constitution.md) — ratified 2026-08-06
- [ADR 0018](../../../docs/architecture/adr/0018-worktree-scoped-mnemo-code-index-partitions.md) — accepted 2026-08-06

## Phase 4 Discovery

- **Outcome**: Current production change surface remains concentrated in `mnemo/mnemo/code_index.py` and `mnemo/mnemo/server.py`, with configuration comments in `mnemo/mnemo/config.py`. Existing code uses repository-family `repo_id` at every manifest, lock, progress, UUID, payload/filter/count/delete, search, status, and debounce boundary. Background indexing constructs a fresh `CodeIndex` with private progress state, so status cannot reliably observe its own thread. Current tests have useful Git safety, deterministic-point, incremental, stale-deletion, and unrelated-repository characterization, but the module-wide Qdrant skip also suppresses pure identity tests. Stdio smoke discovers/tests memory tools only and uses no throwaway code collection.
- **Queries and reads**: all files under `.batman/mnemo-worktree-index-identity/steering/`; approved Requirements and Design; `rg` for `RepoInfo`, `compute_repo_id`, `repo_id`, `Manifest`, `IndexProgress`, `CodeIndex`, `BackgroundIndexer`, code MCP tools, Qdrant filters, lock/progress/debounce consumers, worktree/clone fixtures, and smoke cleanup; focused reads of `mnemo/mnemo/{code_index,server,config}.py`, `mnemo/tests/{test_code_index,mcp_smoke}.py`, `mnemo/README.md`, and accepted ADR 0018.
- **Memory preflight**: mnemo healthy. Approved Phase 1–3 checkpoints were optional summaries; current source and approved artifacts governed decomposition.

## Planning Guardrails

- Follow characterization → TDD RED → minimal GREEN → regression sequence for each new identity/cache abstraction.
- Record exact collected/pass/fail/skip counts at baseline, RED, GREEN, focused, full, and smoke gates; never invent expected counts.
- Keep Qdrant-dependent integration checks separable from pure Git/identity tests and from live OpenAI/stdin smoke.
- Never automatically delete legacy cache, mutate source/Git metadata, or touch `mnemo_memory`/events.
- Preserve unrelated dirty paths and make only path-scoped edits.

## Tasks

- [x] 1. Capture behavioral baseline and prepare test harness boundaries
  - Run the current focused code-index tests before production edits; record exact pass/skip/failure counts and whether Qdrant is reachable.
  - Preserve characterization coverage for repository-family `compute_repo_id`, candidate resolution, protected roots, opt-out behavior, deterministic point recovery, incremental skips, stale-file cleanup, and Git stdin/timeout failure semantics.
  - Refactor test gating so pure Git/identity/unit tests run without Qdrant while only Qdrant-backed integration tests skip when port 1337 is unavailable.
  - Add reusable real-Git fixture helpers for commits, branches, linked worktrees, same-history clones, moves, removal/recreation, and conflicting same-relative-path content.
  - Make test Git subprocesses capture output, disconnect stdin, and provide actionable failures without changing production behavior.
  - Record the baseline/fixture evidence in task comments or the final validation summary rather than a new persistent runtime surface.
  - _Requirements: 7.1, 7.3, 7.5, 9.2, 9.4, 10.1, 10.2_

- [x] 2. Define and implement worktree-incarnation identity with TDD
  - Write failing unit tests for deterministic same-tree scope resolution through subdirectories/path variants and distinct scopes for primary checkout, linked worktrees, and independent same-history clones.
  - Write failing lifecycle tests proving a supported move becomes a safe unindexed scope and remove/recreate at the same path cannot reuse the prior scope.
  - Write failing tests for absolute/relative Git administrative paths, Windows/POSIX normalization seams, missing/zero filesystem identity, unreadable stable marker, Git timeout/spawn failure, and content-safe typed refusal.
  - Add `WorktreeIdentityUnavailable`, immutable `WorktreeIdentity`, canonical path/Git-directory helpers, stable administrative-marker selection, bounded filesystem proof extraction, and `compute_code_index_scope` in `mnemo/mnemo/code_index.py`.
  - Extend `RepoInfo` with identity version/proof/scope while preserving existing `repo_id` repository-family semantics and `compute_repo_id` move-stable behavior.
  - Hash length-delimited proof material into the accepted `wt2_` scope; persist/expose only opaque digest/scope, never raw device/file IDs or Git pointer/config content.
  - Re-run identity tests GREEN, then re-run baseline repository/Git safety characterization.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5, 9.1, 10.2_

- [x] 3. Add v2 manifest binding and legacy-cache quarantine
  - Write failing tests for `~/.mnemo/code/v2/<scope>/` manifest/lock paths and schema/proof/family/root/embed-model binding validation.
  - Write failing tests that missing, malformed, v1, or mismatched bindings are non-queryable and reported as unindexed/rebuild-required even when orphan vectors exist.
  - Write failing tests proving history-only manifests/points are never rebound, queried, or deleted automatically and durable-memory paths/collections remain untouched.
  - Implement v2 manifest schema/binding helpers, strict match checks, atomic bound-empty initialization, and query gating in `mnemo/mnemo/code_index.py`.
  - Add scope-only reset behavior for new/mismatched/full/model-change rebuilds; abort reset on deletion failure instead of stamping completion.
  - Preserve upsert → same-scope stale sweep → manifest record ordering and atomic `os.replace` under interruption.
  - Re-run manifest/migration tests GREEN plus existing idempotence, incremental, model-change, deletion, and shrink regressions.
  - _Requirements: 3.1, 4.2, 4.4, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 9.2, 9.4, 10.2_

- [x] 4. Partition every Qdrant and deterministic-point operation by code-index scope
  - Write failing cross-scope tests for point IDs, payloads, keyword indexes, search/count filters, per-file sweeps, full-scope resets, and same-relative-path conflicts.
  - Add `code_index_scope` and `repository_family_id` keyword payload indexes while retaining harmless legacy indexes for collection compatibility.
  - Generate v2 point UUIDs from scope/path/chunk; emit v2 payloads with scope/family fields and intentionally omit legacy `repo_id`.
  - Replace every v2 search, count, delete, shrink, gone-file, and reset filter with exact `code_index_scope` matching.
  - Prove a change/delete/shrink in worktree A cannot replace or evict worktree B points and an unrelated legacy/family partition remains invisible.
  - Re-run existing language/path search and deterministic interruption/idempotence regressions.
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 5.1, 5.2, 5.4, 9.2, 9.4, 10.1, 10.2_

- [x] 5. Share scope-keyed progress and isolate background concurrency
  - Write failing tests showing foreground status and its background `CodeIndex` observe one shared progress registry inside an MCP process.
  - Write failing concurrency tests showing different scopes receive different thread, lock, progress, and recent-run debounce entries and can start concurrently.
  - Retain same-scope `already-running`/lock coalescing and deterministic recovery across multiple agents.
  - Introduce a thread-safe `ProgressRegistry`, inject it into foreground/background `CodeIndex` instances, and key all operations by `code_index_scope`.
  - Update `BackgroundIndexer` thread/done maps and details to scope semantics; preserve separate Qdrant/OpenAI clients and non-blocking daemon execution.
  - Report lock contention in the active scope as `building_elsewhere`/scoped detail without borrowing another scope's progress.
  - Re-run concurrent-scope, same-scope, responsiveness, and interruption tests GREEN.
  - _Requirements: 3.1, 3.4, 3.5, 4.3, 9.3, 9.4, 9.5, 10.2_

- [x] 6. Expose truthful scope and snapshot contracts through MCP tools
  - Write failing server-level tests for unchanged tool names/arguments and additive `repository_family_id`, `code_index_scope`, and `identity_version` fields.
  - Write failing status tests for unindexed, local building, external building, ready snapshot, interrupted, and error states with scope-local files/chunks/timestamps/progress.
  - Write failing search tests for manifest-gated zero hits, truthful building/rebuild hints, valid partial/ready scope-only hits, and the unchanged source-verification note.
  - Add snapshot metadata (`last_index`, optional indexed HEAD, explicit last-completed semantics) without claiming current-source freshness after branch/local edits.
  - Map repository, Git, worktree-identity, manifest, Qdrant, and indexing failures to typed content-safe responses; do not expose proof inputs, credentials, source bodies, or memory text.
  - Update `code_reindex` to target only the resolved scope and return additive scope/state fields while preserving `full` behavior and async polling note.
  - Re-run MCP response and resolution-order regressions GREEN.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.3, 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 7. Complete real-worktree, clone, lifecycle, migration, and recovery matrix
  - Build one temporary primary repo, at least two linked worktrees, and at least two same-history clones with unique conflicting content at one relative path.
  - Index/query/status every scope and assert zero cross-scope hits, counts, timestamps, manifests, point mutation, locks, progress, or debounce interference.
  - Verify two agents/path variants for one tree derive the same scope and preserve incremental embedding skips.
  - Verify move, remove/recreate, branch switch, detached HEAD, relative Git metadata, and never-indexed sibling behavior.
  - Inject legacy v1 manifest/points and interrupted v2 states; prove quarantine, safe rebuild, no duplicate queryable points, and no source/Git/memory mutation.
  - Exercise Qdrant/reset/manifest failure paths and confirm failures remain typed, scope-local, and non-destructive.
  - _Requirements: 1.2, 1.3, 1.4, 3.2, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 9.2, 9.4, 9.5, 10.1, 10.2_

- [x] 8. Extend stdio smoke without contaminating live code cache
  - Give smoke separate throwaway memory and code collection names and explicit repository resolution; clean both collections in `finally`.
  - Disable automatic code embedding for contract-only smoke unless the test explicitly exercises live indexing.
  - Require discovery of all eight memory tools plus `code_search`, `code_index_status`, and `code_reindex`.
  - Call `code_index_status` through the real stdio server and assert repository-family, worktree scope, identity version, state, and snapshot semantics.
  - Keep existing memory write/search/context/get/forget assertions intact to prove code-index changes do not alter durable memory.
  - Run live OpenAI/Qdrant smoke only with configured credentials/dependencies and report it separately from deterministic acceptance.
  - _Requirements: 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.5, 10.3_

- [x] 9. Update operator and architecture documentation to shipped behavior
  - Update `mnemo/README.md` with code tools, all relevant `MNEMO_CODE_*` settings, repository-family versus worktree scope, v2 cache layout, automatic refresh, snapshot/source-authority semantics, typed states/errors, and verification commands.
  - Document lazy v2 rebuild, legacy quarantine, optional exact code-cache cleanup, and rollback; explicitly prohibit deleting `mnemo_memory`, event logs, source, Git metadata, credentials, or host config.
  - Update stale code/config comments that call the cache merely “per-repo” or point to an unrelated ADR.
  - Reconcile PRD, accepted ADR 0018, Design, `CONTEXT.md`, and public MCP wording with final field names/behavior; amend approved core decisions only through an explicit re-approval if implementation evidence conflicts.
  - Confirm no host registration, service, port, credential, dependency, or default eligibility change is required.
  - _Requirements: 2.4, 5.3, 5.5, 8.3, 8.5, 10.4_

- [x] 10. Run focused, full, static, smoke, and live acceptance gates
  - Run focused pure identity and Qdrant-backed code-index tests; report exact pass/fail/skip counts and Qdrant availability.
  - Run full `mnemo/tests`; separate memory, deterministic/fake-embedder, and real-Qdrant evidence.
  - Run stdio smoke with real configured OpenAI/Qdrant and report credential/network/environment exclusions instead of treating them as passes.
  - Run scoped Ruff on changed Python, Python compile/import checks, Markdown/placeholder/fence validation, and `git diff --check`; separate pre-existing Ruff findings from regressions.
  - Reload/probe the actual MCP server from two real task worktrees if owner/runtime conditions permit; verify different scopes and zero cross-results, otherwise leave owner/live acceptance explicitly open.
  - Confirm Git status contains only intended task paths and preserved unrelated changes.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.5_

- [x] 11. Perform Phase 7 review and resolve all in-scope findings
  - Load canonical code-review and code-pattern instructions, review the complete diff against the approved Constitution/Design/ADR, and inspect every cache consumer for accidental repository-family keys.
  - Check correctness, security, lifecycle, concurrency, migration, interruption, response compatibility, documentation, and test isolation; fix all in-scope findings and rerun affected gates.
  - Verify no legacy `repo_id` filter/payload remains on v2 operations, no identity proof leaks, no automatic destructive cleanup exists, and durable memory code is behaviorally unchanged.
  - Record any unfixable external/owner/release gate as open; never mark an unrun gate green.
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 5.3, 7.4, 8.3, 8.4, 10.5_

- [x] 12. Finalize Phase 8 documentation and evidence handoff
  - Update task artifacts/statuses to match actual shipped behavior, test evidence, and remaining gates without rewriting accepted ADR core decisions silently.
  - Provide a concise change summary, exact validation matrix, cache upgrade/rollback warning, live-runtime qualification, and clickable source/doc references.
  - Confirm implementation satisfies every numbered acceptance criterion or name the exact unmet criterion/blocker before claiming completion.
  - _Requirements: 2.4, 5.5, 8.3, 10.4, 10.5_

## Phase 4 Grill-Me Review

- **Why tests first?** Production code silently returns wrong vectors on identity/filter mistakes. Characterization plus per-component RED/GREEN gates exposes regressions before the broad rewrite.
- **Why split pure and Qdrant tests?** Current module-wide skip can hide identity failures when Qdrant is down. Pure identity must always execute; Qdrant/live gates remain truthful and separate.
- **Why fixtures before implementation?** Real worktree/clone/recreation semantics drive the identity contract; synthetic `.git` paths alone are insufficient acceptance evidence.
- **Why no migration/cleanup task that reuses v1?** Accepted Design/ADR rejects rebinding and automatic deletion. Plan only quarantines and documents optional cache cleanup.
- **Why server contracts after storage?** Responses need final binding/state primitives; implementing them earlier would duplicate or guess lifecycle logic.
- **Why smoke late?** Stdio contract should validate the stabilized public fields and use throwaway collections, not drive architecture.
- **What can still remain open?** Real OpenAI/stdin, actual two-host reload, owner acceptance, and release gates may depend on external runtime state. Plan requires separate reporting, never inferred success.

## Completion Condition

Implementation is complete only when Tasks 1–12 are checked, every numbered requirement criterion is satisfied or explicitly blocked, deterministic and dependency-backed evidence is separated, Phase 7 has no unresolved in-scope finding, and Phase 8 documents any remaining owner/live/release gate.
