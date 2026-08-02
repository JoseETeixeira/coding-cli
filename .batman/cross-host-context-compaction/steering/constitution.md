# Constitution: Cross-Host Context Compaction Pilot

- **Version**: 1.0.0
- **Ratified**: 2026-08-01
- **Last Amended**: 2026-08-01
- **Scope**: task-scoped

## Purpose

This constitution governs the design, implementation, activation, and evaluation of bounded context compaction for Codex and Claude Code. It protects continuity across large, intertwined repositories while deliberately treating conversation history as expendable cache. Any deviation requires an explicit entry in the design's Complexity Tracking table because a silent shortcut can either discard a critical invariant or refill the context window the pilot is meant to reduce.

## Core Principles

### 1. Authoritative State Is Reopened, Not Remembered

**Statement**: The pilot SHALL treat compact summaries, hook payloads, and semantic memory as non-authoritative. Before any material write or external side effect after compaction, it SHALL revalidate the relevant current source, Git state, approved artifact, and applicable scoped instructions. Exact critical invariants SHALL retain provenance and a deterministic source pointer.

**Rationale**: Large intertwined systems change concurrently, and a coherent summary can still be stale or incomplete. Current source and explicit user decisions are the only safe basis for action.

**Evidence of compliance**: Tests cover conflict, stale-state, missing-artifact, dirty-worktree, and path-scoped-instruction cases; a real compact continuation records the exact sources reopened before its first material action.

### 2. Every Automatic Ingress Is Bounded

**Statement**: Automatic post-compact state SHALL fit within 8,000 Unicode characters or 2,000 estimated tokens, whichever limit is reached first. Default `task_context` memory text SHALL fit within 4,000 Unicode characters. Truncation SHALL preserve critical categories first, expose omitted/truncated metadata, and retain deterministic full-retrieval pointers.

**Rationale**: Unbounded rehydration merely replaces stale transcript cost with memory or hook cost and can immediately trigger another compaction.

**Evidence of compliance**: Boundary tests exercise multibyte text, aggregate and per-item limits, priority ordering, omitted categories, explicit `memory_get`, and ten normal post-compact turns without unexplained recompaction.

### 3. Native Compaction, Shared Outcomes

**Statement**: Codex and Claude Code SHALL keep ownership of transcript compaction. The pilot SHALL implement one preservation, security, degradation, observability, and rollback contract through documented host-native controls and thin adapters; it SHALL NOT claim numeric threshold equivalence between different host semantics.

**Rationale**: Replacing private transcript machinery is fragile, while pretending distinct threshold models are identical produces misleading configuration and evidence.

**Evidence of compliance**: Separate adapter fixtures and observed real sessions identify host/version, native trigger/config names, unsupported capabilities, and independently measured outcomes.

### 4. Compaction Fails Open; Material Continuation Fails Closed

**Statement**: Optional pilot failures SHALL NOT prevent a host from compacting at a hard context boundary. Missing, malformed, stale, contradictory, or oversized recovery state SHALL place the continuation in visible read-only degraded mode. Material actions SHALL remain blocked until authoritative reconstruction validates, or the agent SHALL stop for one targeted user decision.

**Rationale**: Blocking necessary compaction can lose the whole turn, while silently continuing from incomplete state can duplicate side effects or corrupt a repository.

**Evidence of compliance**: Fault-injection tests prove native compaction proceeds when hooks, mnemo, Qdrant, or artifacts fail; degraded-mode fixtures block edits and side effects, allow bounded reconstruction, and record validation before release.

### 5. Persist Metadata and Pointers, Never Sensitive Conversation Bodies

**Statement**: New state, diagnostics, logs, and memory previews SHALL exclude credentials, secret environment values, raw transcripts, raw secret-bearing tool output, complete diffs, source bodies, and binary/base64 payloads. Hook and memory input SHALL be treated as untrusted data and SHALL NOT broaden scope, readers, tools, approvals, paths, or network access.

**Rationale**: Lifecycle hooks execute at a privileged edge; duplicating transcript content expands both prompt-injection and data-retention risk.

**Evidence of compliance**: Redaction, poisoning, ACL, namespace, path traversal, oversized-input, and content-free diagnostic tests pass on both adapter fixtures.

### 6. Activation Is Explicit, Narrow, and Reversible

**Statement**: The pilot SHALL remain disabled by default, activate only for a named host and allowlisted repository or workspace, preserve unrelated settings and trust boundaries, and provide an observed disable/rollback path that removes only pilot-owned activation.

**Rationale**: Global hooks and threshold changes can affect unrelated repositories, while broad configuration rewrites can silently discard user policy.

**Evidence of compliance**: Plan/apply/verify/disable tests use pre-populated Codex and Claude settings, demonstrate conflict detection and idempotency, and show native behavior remains usable after rollback.

### 7. Evidence Is Qualified Before Rollout

**Statement**: The pilot SHALL NOT claim success until manual and automatic compaction on both supported hosts retain 100% of critical benchmark probes and at least 90% overall, introduce no additional source-contradicting exact-code claims, and demonstrate at least 50% eligible conversation-body token reduction where credibly measurable. Unavailable metrics SHALL be labeled qualified or unmeasured.

**Rationale**: Focused unit tests prove mechanisms, not continuity or savings on a large intertwined workload.

**Evidence of compliance**: Checked-in reports record exact versions, commands, workload, probe scores, token-measurement source, latency, compaction frequency, open limits, and repository-owner real-session review.

## Additional Constraints

- **Security**: Preserve host sandbox, approvals, plugin/hook trust, mnemo ACL/redaction/revocation, and credential boundaries. State files use validated paths, atomic replacement, restrictive local permissions where supported, and bounded retention.
- **Performance**: Local state assembly must complete within 2 seconds at p95; automatic state is capped at 8,000 characters/2,000 estimated tokens; default memory text is capped at 4,000 characters; pilot-added payloads must not cause unexplained recompaction within ten normal turns.
- **Compliance / Regulatory**: No special regulatory regime is asserted. Data minimization, local content-free diagnostics, and user-removable pilot state are mandatory.
- **Platform**: Python 3.12; Codex CLI 0.145.0 and Claude Code 2.1.220 are the initial Windows baselines. POSIX support may be claimed only after the same deterministic fixtures pass. Later host versions require capability revalidation.

## Development Workflow

- Approved requirements trace into design components, task-plan items, automated tests, real-host evidence, review findings, and operator documentation.
- Pure state selection, budgeting, event normalization, and serialization are tested without either host, Qdrant, network access, or user configuration mutation; adapter fixtures then exercise each documented host schema.
- Architecture decisions passing the hard-to-reverse, surprising, real-trade-off test receive proposed ADRs during Design and become accepted only with Design approval.
- Customization and user-activation writes remain approval-gated: preview the exact owned diff, preserve unrelated state, and verify rollback before applying.
- Functional checks remain distinct from real-session, performance, security, and owner-acceptance gates.

## Governance

- The constitution supersedes ad-hoc decisions. A design that violates a principle without an entry in **Complexity Tracking** fails review.
- Amendments require: (1) explicit justification, (2) a migration plan for in-flight work, and (3) a version bump per semantic versioning.
  - **Major**: a principle is removed or replaced.
  - **Minor**: a principle is added or materially expanded.
  - **Patch**: wording is clarified or scope is tightened without changing meaning.
- Every pull request touching the design or implementation must verify constitution compliance.

## Amendment Log

| Version | Date | Change | Author |
|---|---|---|---|
| 1.0.0 | 2026-08-01 | Initial task constitution derived from approved requirements and current host/source evidence | Repository owner and Batman |
