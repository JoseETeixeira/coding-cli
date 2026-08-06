# Constitution: Mnemo Worktree-Aware Code Index Identity

- **Version**: 1.0.0
- **Ratified**: 2026-08-06
- **Last Amended**: 2026-08-06
- **Scope**: task-scoped

## Purpose

This constitution governs design and implementation of mnemo code-index identity. It protects the boundary between repository-shared durable memory and working-tree-scoped rebuildable source cache. Any deviation requires an explicit entry in the Design's Complexity Tracking table.

## Core Principles

### 1. Share Memory, Isolate Source Cache

**Statement**: Durable `mnemo_memory` behavior SHALL remain unchanged, while every manifest, vector point, query, lock, progress entry, debounce key, and cleanup operation in `mnemo_code` SHALL belong to exactly one working-tree scope.

**Rationale**: Agent decisions must cross related worktrees; mutable source chunks must not.

**Evidence of compliance**: Public identity fields distinguish repository family from code-index scope, and real-worktree tests prove zero cross-scope reads or mutations.

### 2. Fail Closed on Identity

**Statement**: Mnemo SHALL reject an unresolved or insufficiently proven working-tree identity and SHALL NOT fall back to a history-only, common-directory, branch, or path-only shared partition.

**Rationale**: A false cache match silently gives one agent another task's source.

**Evidence of compliance**: Identity helpers return typed failures; legacy and malformed bindings are non-queryable; protected-root and Git-failure tests remain green.

### 3. Source Authority and Truthful Snapshots

**Statement**: Current source SHALL remain authoritative. Search and status SHALL describe indexed data as a scope-bound snapshot and SHALL NOT claim it proves current working-tree contents.

**Rationale**: Background refresh is intentionally asynchronous, so same-tree lag can exist after local edits.

**Evidence of compliance**: Search retains the source-verification note; status exposes snapshot/refresh state; branch and never-indexed tests pin the wording and fields.

### 4. Deterministic, Interrupt-Safe Cache Mutation

**Statement**: Point identity and mutation order SHALL remain deterministic and resumable after ordinary host termination; manifests SHALL never overstate successfully written vectors.

**Rationale**: Hosts routinely terminate daemon index threads without cleanup.

**Evidence of compliance**: Scope-aware UUID inputs, upsert-before-sweep-before-record ordering, atomic manifests, OS-released locks, and interruption/idempotence tests.

### 5. Bounded and Non-Blocking Operation

**Statement**: Working-tree identity SHALL use bounded local Git/filesystem operations only. Different scopes SHALL refresh independently, and background indexing SHALL NOT block the MCP event loop.

**Rationale**: Isolation must not reintroduce stdio hangs, network identity calls, or global serialization.

**Evidence of compliance**: `stdin=DEVNULL` and timeout tests, scope-keyed background state, separate locks, and concurrent-scope tests.

### 6. Rebuildable Compatibility

**Statement**: Existing MCP tool names and arguments SHALL remain valid. Compatibility changes SHALL be additive, and upgrade/rollback SHALL mutate only rebuildable code-index data.

**Rationale**: Host registrations and durable memory are more valuable than embedding reuse.

**Evidence of compliance**: Stdio contract tests, versioned manifests/payloads, legacy quarantine tests, and operator rollback documentation.

### 7. Real-Git Evidence

**Statement**: Acceptance SHALL use real temporary Git primary checkouts, linked worktrees, and same-history clones, plus deterministic embeddings and scoped Qdrant collections.

**Rationale**: Synthetic path fixtures cannot prove Git worktree metadata or lifecycle behavior.

**Evidence of compliance**: Focused worktree/clone/recreation/concurrency tests, full mnemo regression, and separately reported live smoke gates.

## Additional Constraints

- **Security**: Never store or log source bodies beyond the existing vector payload, credentials, durable-memory text, or raw Git configuration. Never write source or Git metadata for identity.
- **Performance**: Identity resolution adds no Qdrant/OpenAI call; unchanged files remain incrementally reusable inside one scope; unrelated scopes do not share locks or debounce.
- **Compliance / Regulatory**: No additional regime applies; existing redaction and ACL behavior remains outside this cache change.
- **Platform**: Python 3.12; Windows-first with POSIX-compatible path and filesystem identity handling; existing dependency minimums unless separately approved.

## Development Workflow

- Approved Requirements constrain Design; approved Design constrains Task Planning and implementation.
- Focused identity tests precede or accompany cache-boundary edits; full mnemo and stdio smoke run after implementation.
- Phase 7 review checks every cache consumer for use of code-index scope rather than repository-family identity.
- Any unavoidable constitutional exception requires user-approved Complexity Tracking and, when the repository ADR test passes, an ADR.

## Governance

- This constitution supersedes ad-hoc implementation choices for this task. A design that violates a principle without a Complexity Tracking entry fails review.
- Amendments require explicit justification, an in-flight migration plan, and a semantic-version bump.
  - **Major**: principle removed or replaced.
  - **Minor**: principle added or materially expanded.
  - **Patch**: clarification or scope tightening without meaning change.
- Every change touching this task must verify constitution compliance.

## Amendment Log

| Version | Date | Change | Author |
|---|---|---|---|
| 1.0.0 | 2026-08-06 | Ratification | Repository owner |
