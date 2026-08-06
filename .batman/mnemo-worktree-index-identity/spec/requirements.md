# Requirements: Mnemo Worktree-Aware Code Index Identity

Status: Approved · 2026-08-06

## Document Information

- **Feature Name:** Mnemo Worktree-Aware Code Index Identity
- **Version:** 1.0
- **Date:** 2026-08-06
- **Author:** Repository owner
- **Stakeholders:** Repository owner; Codex, Claude Code, and Copilot users; mnemo maintainers

## Introduction

Mnemo currently resolves the caller's correct Git top-level directory but keys its entire semantic source-code cache from the repository's root commit. Primary checkouts, linked worktrees, and separate clones can share that history while containing different branches and local edits. They therefore collide in one manifest, Qdrant partition, point namespace, lock, progress/debounce entry, and status view.

This feature separates repository-family memory from working-tree source cache. Durable `mnemo_memory` facts, decisions, checkpoints, and handoff pointers remain shared across related tasks. Rebuildable `mnemo_code` chunks and diagnostics become isolated per concrete Git working directory, with truthful handling of legacy data and ordinary same-tree background-refresh lag.

## Feature Summary

Give every distinct Git working directory an isolated mnemo code-index scope while preserving repository-shared durable memory and existing source-authority rules.

## Business Value

- Prevent one agentic task from locating or reporting another task's source.
- Allow concurrent worktrees to index without overwriting or suppressing each other.
- Make empty/building/current-snapshot status trustworthy for the active working directory.
- Preserve cross-agent decisions and handoffs across all worktrees in the same repository family.
- Keep upgrades safe because code-index data is rebuildable and durable memory is untouched.

## Scope

### Included

- Primary Git checkout, linked Git worktrees, and separate clones that share repository history.
- Working-tree-aware identity for all code-index cache boundaries.
- Search, status, explicit reindex, automatic refresh, locking, progress, and debounce isolation.
- Legacy history-only cache compatibility and cleanup behavior.
- Additive public diagnostics distinguishing repository family from code-index scope.
- Deterministic, real-Git worktree tests; full mnemo regression and stdio contract coverage.
- Mnemo code-index documentation and operator verification/rollback guidance.

### Excluded

- Changing `mnemo_memory` namespace, ACL, redaction, event-log, revocation, or task-context semantics.
- Making semantic search authoritative over current source.
- Replacing Qdrant, OpenAI embeddings, FastMCP, or existing host registrations.
- Blocking every search until all same-working-tree local edits have been re-embedded.
- Indexing untracked files by default, binary assets, `.dmm` maps, protected directories, or opted-out repositories.
- New external service, port, credential, dashboard, file watcher, or source mutation.

## Phase 2 Discovery

- **Outcome:** current source confirms one root-commit-derived `repo_id` fans into manifest paths, Qdrant payload filters, point UUIDs, locks, progress, background debounce, search, status, and deletion. Existing isolation tests use unrelated repositories with different histories; no test constructs related worktrees. Stdio smoke covers memory tools only. Mnemo README omits code-index tools/settings/worktree behavior.
- **Queries:** `git status --short`; `git worktree list --porcelain`; `git rev-parse --show-toplevel --git-dir --git-common-dir`; `rg --files mnemo tests .github docs/prd docs/architecture/adr`; `rg` for `compute_repo_id`, `RepoInfo`, `repo_id`, `repo_root`, `last_index`, `BackgroundIndexer`, and code tool names; focused reads of current code-index/server/config/tests/docs/dependencies and existing project steering/PRD conventions.
- **Memory preflight:** mnemo healthy. Approved Phase 1 checkpoint `75342903-1713-484b-bcfa-cdc817c02d3e` (writer `copilot`, 2026-08-06) confirms the user-approved scope. Older records from `claude-code` dated 2026-07-16 and 2026-08-02 supplied historical context only; current source and tests revalidated relevant claims.

---

## Requirements

### Requirement 1: Deterministic Working-Tree Scope

**User Story:** As an agent using mnemo, I want the code index to identify my exact Git working directory, so that related repositories cannot share mutable source-cache state accidentally.

**Acceptance Criteria (EARS)**

- WHEN mnemo resolves a valid Git directory from an explicit argument, configured root, MCP workspace root, cwd, or subdirectory THEN mnemo SHALL derive a deterministic code-index scope for the exact working tree.
- IF two working directories share a root commit, object history, remote, branch name, or Git common directory THEN mnemo SHALL still derive distinct code-index scopes.
- IF two agents resolve the same physical working directory through normalized path variants or subdirectories THEN mnemo SHALL derive the same code-index scope.
- WHERE the working directory is a primary checkout, linked worktree, or separate clone THEN mnemo SHALL apply the same isolation contract.
- IF mnemo cannot establish a safe working-tree identity THEN mnemo SHALL return a typed repository-resolution error and SHALL NOT fall back to a repository-family cache partition.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Existing per-call repository resolution and Git subprocess safety
- **Assumptions:** Git is available for repositories accepted by the code index

### Requirement 2: Repository-Family Memory Remains Shared

**User Story:** As a repository owner, I want task memory to remain shared across related working trees, so that index isolation does not fragment decisions, checkpoints, or handoffs.

**Acceptance Criteria (EARS)**

- WHEN code-index scope identity changes THEN mnemo SHALL preserve existing `mnemo_memory` namespace, event-log, ACL, redaction, trust, revocation, and retrieval behavior.
- WHERE Batman tasks use `repo:<name>` memory namespaces THEN mnemo SHALL preserve the existing namespace-resolution behavior and SHALL NOT derive memory scope from the new code-index identity.
- IF code-index cache migration or cleanup runs THEN mnemo SHALL NOT delete or rewrite durable-memory events or `mnemo_memory` points.
- WHEN an agent receives memory or code-search context THEN documentation SHALL distinguish repository-family memory from working-tree-scoped source cache.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** Requirement 1; existing shared-memory contract
- **Assumptions:** Repository-family naming remains governed by existing memory workflow

### Requirement 3: Complete Cache-Boundary Isolation

**User Story:** As an agent working in one tree, I want every index operation confined to that tree's scope, so that another task cannot alter or surface my cache state.

**Acceptance Criteria (EARS)**

- WHEN mnemo creates or reads a manifest, lock, progress entry, background-debounce entry, deterministic point ID, Qdrant payload, filter, count, or stale-point deletion THEN it SHALL bind that operation to the active code-index scope.
- WHEN working tree A indexes a file THEN working tree B SHALL NOT receive A's chunks in search results even if both trees use the same relative path.
- WHEN working tree A deletes, shrinks, or changes a file THEN its stale-point sweep SHALL NOT delete or replace working tree B's points.
- WHILE working tree A is indexing, working tree B SHALL retain independent lock, progress, and debounce state.
- IF two agents index the same working tree concurrently THEN mnemo SHALL retain existing safe same-scope deduplication and idempotence.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Requirement 1
- **Assumptions:** Qdrant supports additive keyword payload indexes used by the approved design

### Requirement 4: Truthful Search and Status

**User Story:** As an agent diagnosing search results, I want status and search metadata tied to my active working tree, so that another task's completed index cannot appear current.

**Acceptance Criteria (EARS)**

- WHEN `code_index_status` is called THEN mnemo SHALL identify the resolved working-tree root and its code-index scope unambiguously.
- IF the active scope has never completed indexing THEN status SHALL report that scope as unindexed or building and SHALL NOT inherit files, chunks, timestamps, or progress from a related scope.
- WHILE the active scope is refreshing THEN status SHALL expose its own progress and SHALL retain only its own last completed snapshot metadata.
- WHEN `code_search` runs before a new scope has indexed THEN mnemo SHALL return no chunks from related scopes and SHALL provide a truthful unindexed/building hint.
- IF same-working-tree files may have changed after the last completed asynchronous refresh THEN mnemo SHALL describe the returned data as an index snapshot and SHALL NOT claim it is verified current source.
- WHEN search returns paths and spans THEN the existing “index locates; source decides” verification instruction SHALL remain present.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** Requirements 1 and 3
- **Assumptions:** Same-tree search remains non-blocking while refresh runs

### Requirement 5: Safe Legacy-Cache Transition

**User Story:** As a maintainer upgrading mnemo, I want history-only cache data handled safely, so that old cross-worktree points cannot leak into the new scope model.

**Acceptance Criteria (EARS)**

- WHEN a worktree-aware release first accesses an existing history-only manifest or Qdrant partition THEN mnemo SHALL NOT query it as current working-tree data without validating and rebinding it under the approved scope contract.
- IF legacy code-index data cannot be safely reused THEN mnemo SHALL leave it non-queryable and rebuild the active scope.
- WHEN legacy points or manifests are cleaned up THEN cleanup SHALL affect only rebuildable code-index data and SHALL preserve source, Git metadata, host configuration, and durable memory.
- IF upgrade or cleanup is interrupted THEN the next run SHALL resume or rebuild without duplicate queryable chunks.
- WHEN the feature is rolled back THEN operator guidance SHALL identify which code-index cache data may be removed/rebuilt and SHALL prohibit deleting durable-memory events.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Requirements 1 and 3
- **Assumptions:** Re-embedding cost is acceptable when correctness prevents safe reuse

### Requirement 6: Working-Tree Lifecycle Safety

**User Story:** As a repository owner who moves and recreates working trees, I want cache identity to fail safe across lifecycle changes, so that a reused path cannot inherit another task's source silently.

**Acceptance Criteria (EARS)**

- WHEN a working tree is moved or renamed through supported Git operations THEN mnemo SHALL either retain its identity safely or treat it as an unindexed scope requiring rebuild; it SHALL NOT collide with another live tree.
- IF a working directory is removed and later recreated at the same path THEN mnemo SHALL NOT return the removed tree's chunks as current before the recreated tree is safely identified and reconciled.
- IF a working tree changes branch, detached HEAD, or checked-out commit THEN mnemo SHALL preserve scope isolation and SHALL expose ordinary refresh lag truthfully until reconciliation completes.
- WHERE Git worktree metadata uses absolute or relative paths THEN mnemo SHALL resolve the same safe scope semantics.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Requirements 1, 4, and 5
- **Assumptions:** Design may choose rebuild over stable reuse when lifecycle identity is ambiguous

### Requirement 7: Git, Path, and Repository Safety

**User Story:** As a host operator, I want identity discovery to preserve current Git/path safeguards, so that fixing isolation does not reintroduce hangs or unsafe indexing.

**Acceptance Criteria (EARS)**

- WHEN mnemo invokes Git THEN it SHALL use bounded timeouts, capture output, and disconnect child stdin from the MCP JSON-RPC pipe.
- WHERE mnemo runs on Windows or POSIX THEN it SHALL normalize path syntax and case according to platform semantics before comparing identity.
- IF the candidate is home, a drive/filesystem root, an agent configuration directory, non-Git, missing, opted out with `.mnemo-noindex`, or otherwise protected THEN mnemo SHALL refuse indexing as it does today.
- WHEN mnemo derives or stores code-index identity THEN it SHALL NOT write into source files, Git config, Git administrative metadata, or host settings.
- IF Git is unavailable or times out THEN mnemo SHALL surface a typed failure and SHALL NOT misreport the repository as absent or evict its index.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** Existing `GitUnavailable`, `RepoUnresolved`, and protected-directory behavior
- **Assumptions:** No new privileged filesystem access is required

### Requirement 8: Public MCP Compatibility and Diagnostics

**User Story:** As a tool client, I want existing code-index calls to continue working with clearer identity metadata, so that hosts gain safety without registration churn.

**Acceptance Criteria (EARS)**

- WHEN the feature ships THEN mnemo SHALL retain the `code_search`, `code_index_status`, and `code_reindex` tool names and existing input arguments.
- WHEN a code tool succeeds THEN its top-level response SHALL expose repository-family and working-tree/code-index-scope identity without ambiguity.
- IF response fields are added or an existing identity field changes meaning THEN documentation and regression tests SHALL define the compatibility contract explicitly.
- IF repository or indexing resolution fails THEN code tools SHALL return typed content-safe errors rather than uncaught exceptions.
- WHEN existing MCP registrations launch the updated canonical server THEN they SHALL require no new credential, port, or external service.

**Additional Details**

- **Priority:** Medium
- **Complexity:** Medium
- **Dependencies:** Requirements 1 and 4
- **Assumptions:** Additive response fields are accepted by current hosts

### Requirement 9: Incremental Performance and Interruption Recovery

**User Story:** As an agent using semantic search frequently, I want isolation without unnecessary re-embedding or blocking, so that concurrent tasks remain responsive.

**Acceptance Criteria (EARS)**

- WHEN identity is derived THEN mnemo SHALL use local bounded Git/filesystem work and SHALL NOT call Qdrant or OpenAI solely to identify the working tree.
- WHEN an eligible file is unchanged inside the same scope and embedding model THEN incremental indexing SHALL skip re-embedding it.
- WHILE one scope refreshes in a background thread THEN unrelated memory and code-tool calls SHALL remain responsive.
- IF an indexer process is terminated at any point THEN the next same-scope refresh SHALL resume idempotently without accumulating duplicate queryable points.
- WHEN different scopes refresh concurrently THEN they SHALL NOT share a lock or recent-run debounce entry.

**Additional Details**

- **Priority:** Medium
- **Complexity:** Medium
- **Dependencies:** Requirements 1, 3, and existing deterministic point behavior
- **Assumptions:** Existing FastMCP/background-thread architecture remains

### Requirement 10: Documentation and Verification

**User Story:** As a maintainer, I want repeatable worktree tests and clear operator docs, so that the isolation contract remains visible and regression-proof.

**Acceptance Criteria (EARS)**

- WHEN focused tests run THEN they SHALL create real Git repositories, linked worktrees, and separate clones with conflicting same-path contents and SHALL prove zero cross-scope search/status/cache interference.
- WHEN regression tests run THEN they SHALL cover same-scope determinism, subdirectory/path normalization, move/recreate lifecycle, legacy-cache handling, concurrency/debounce, interruption idempotence, protected roots, and Git stdin/timeout safeguards.
- WHEN stdio smoke runs THEN it SHALL verify code-tool discovery and at least one public worktree-aware response contract separately from durable-memory behavior.
- WHEN documentation is updated THEN `mnemo/README.md` SHALL describe code tools, relevant `MNEMO_CODE_*` settings, working-tree scope, asynchronous refresh, source authority, upgrade, verification, and rollback.
- WHEN completion is reported THEN deterministic fake-embedder tests, real-Qdrant tests, live OpenAI/stdin smoke, and any unrun owner/release gate SHALL be reported separately.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** All prior requirements
- **Assumptions:** Qdrant remains available for the existing integration suite; live OpenAI smoke may require explicit credentials/network

---

## Non-Functional Requirements

### Performance Requirements

- WHEN multiple distinct working trees auto-index THEN mnemo SHALL isolate debounce/locks without serializing unrelated scopes.
- IF the active scope is unchanged THEN mnemo SHALL preserve incremental skip behavior and avoid unnecessary embedding calls.
- WHEN status is requested THEN mnemo SHALL return from local manifest/Qdrant/progress state without forcing a full source reindex.

### Security Requirements

- WHEN repository identity is derived THEN mnemo SHALL validate the candidate against existing protected-root and opt-out rules before cache access.
- IF identity metadata is logged or returned THEN mnemo SHALL exclude credentials, source bodies, memory text, and unrelated host configuration.
- WHEN migration/rollback occurs THEN mnemo SHALL confine mutation to rebuildable code-index cache data.

### Usability Requirements

- WHEN an agent inspects status THEN terminology SHALL distinguish repository family, working tree, code-index scope, and last completed index snapshot.
- IF a scope is empty or building THEN responses SHALL give an actionable hint without implying the query is genuinely absent from current source.

### Reliability Requirements

- WHEN Git, Qdrant, embeddings, locking, or manifest I/O fails THEN mnemo SHALL preserve source and durable memory and SHALL expose a typed/diagnosable code-index failure.
- IF old or conflicting identity state is detected THEN mnemo SHALL fail closed to unindexed/rebuild rather than query a broader partition.

---

## Constraints and Assumptions

### Technical Constraints

- Preserve Python 3.12 and current mnemo dependency minimums unless Design proves otherwise.
- Preserve Qdrant on the configured endpoint, existing collections, FastMCP stdio, and OpenAI-only production embeddings.
- Preserve automatic, non-blocking background refresh.
- Preserve deterministic point/recovery guarantees and `stdin=DEVNULL` Git hygiene.
- Code-index cache is rebuildable; durable memory is not part of cache migration.
- Current source and tests remain authoritative over index/memory output.

### Business Constraints

- No new service, credential, host registration, port, dashboard, or paid provider.
- No broad host/user configuration mutation.
- Preserve unrelated worktree changes and do not delete existing caches without an approved, scoped rollback/cleanup path.

### Assumptions

- Distinct working directories may contain conflicting content at identical relative paths.
- Separate clones with the same history require the same isolation as linked worktrees.
- Same-working-tree asynchronous index snapshots may lag local edits; the feature prevents cross-scope contamination and improves truthfulness rather than making search a synchronous source read.
- Rebuild cost is acceptable when legacy data cannot be reused safely.

---

## Success Criteria

### Definition of Done

- All EARS acceptance criteria are met.
- Code-index and memory boundaries remain separate.
- Legacy data cannot leak into worktree-aware queries.
- Focused/full tests and public stdio smoke pass or are truthfully qualified.
- Documentation, PRD, ADR (if approved), evidence, and rollback guidance match shipped behavior.

### Acceptance Metrics

- Zero cross-scope hits in a matrix covering primary checkout, two linked worktrees, and two same-history clones with conflicting same-path content.
- Zero cross-scope manifest, count, timestamp, lock, progress, debounce, or stale-deletion interference.
- One stable scope identity across two agents, repository subdirectories, and supported path normalization variants for the same working tree.
- Zero durable-memory event/point changes caused by code-index migration or cleanup.
- All existing mnemo tests plus new worktree regressions pass; stdio tool discovery includes all memory and code tools.

---

## Glossary

| Term | Definition |
|---|---|
| Repository Family | Git working trees mapped to one existing repository-scoped durable-memory namespace; this feature does not redefine how that namespace is selected. |
| Working Tree | One concrete Git working directory whose checked-out and locally modified source may differ from every other directory in the repository family. |
| Code-Index Scope | Isolated, rebuildable semantic source cache belonging to exactly one working tree. |
| Index Snapshot | Last successfully completed reconciliation of eligible files and searchable chunks for one code-index scope. |
| Cross-Scope Contamination | Any chunk or diagnostic state from one code-index scope returned, modified, deleted, locked, or attributed through another scope. |
| Legacy Partition | History-only manifest/Qdrant cache created before worktree-aware identity. |

---

## Requirements Review Checklist

### Completeness

- [x] Every requirement has a user story and EARS acceptance criteria.
- [x] Primary, linked-worktree, clone, move/recreate, concurrency, migration, failure, and rollback cases are covered.
- [x] Non-functional, security, reliability, and success metrics are present.
- [x] Durable memory and code-index cache are explicitly separated.

### Quality

- [x] Requirements state observable outcomes rather than selecting an identity algorithm.
- [x] Every acceptance criterion is testable.
- [x] Terminology matches `CONTEXT.md` and approved Understanding.
- [x] Same-scope refresh lag is separated from cross-scope contamination.

### EARS Format Validation

- [x] WHEN statements describe events/triggers.
- [x] IF statements describe conditions/states.
- [x] WHILE statements describe ongoing behavior.
- [x] WHERE statements describe contexts.
- [x] System responses use SHALL.

### Traceability

- [x] Requirements are numbered and dependency-linked.
- [x] Success metrics map to identity, isolation, diagnostics, migration, and verification.
- [x] Approved Phase 1 artifact/checkpoint and fresh Phase 2 discovery are recorded.
