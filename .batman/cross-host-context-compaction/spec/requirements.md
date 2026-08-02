# Requirements: Cross-Host Context Compaction Pilot

## Document Information

- **Feature Name:** Cross-Host Context Compaction Pilot
- **Version:** 1.1
- **Status:** Approved 2026-08-01; Refresh 3 semantic-registry delta approved 2026-08-01
- **Date:** 2026-08-01
- **Author:** Batman Agent
- **Stakeholders:** Repository owner; Codex and Claude Code users; `coding-cli` and mnemo maintainers

## Introduction

Long coding-agent sessions repeatedly send stale conversation, old file reads, and large tool or memory payloads. This raises token cost and lets outdated context compete with current source, reducing coherence. Codex and Claude Code already compact history, but summaries alone cannot guarantee verbatim retention of complex cross-system relationships.

This pilot shall make conversation disposable while keeping task continuity safe. Exact truth remains in current source, tests, Git state, approved planning artifacts, and explicit decisions. Both hosts shall meet one preservation, security, measurement, and rollback contract through their documented native controls.

## Feature Summary

Provide an opt-in, measurable Codex and Claude Code compaction pilot that bounds hot-context ingress, restores minimal active task state, and requires current-source validation before material continuation.

## Business Value

- Lower repeated input-token cost during long tasks.
- Reduce stale-context contradictions and false confidence.
- Preserve safe continuity across large, intertwined repositories.
- Prevent Codex and Claude Code behavior from drifting into different semantic contracts.
- Make pilot activation, degradation, verification, and rollback auditable.

## Scope

### Included

- Manual and automatic compaction behavior on supported Codex and Claude Code versions.
- Bounded active-state continuation after compaction.
- Current-source, scoped-rule, test, Git, and approved-artifact revalidation.
- Bounded default mnemo task recall with deterministic access to full records.
- Host-specific activation, observability, version checks, off switches, and rollback.
- A representative large-codebase preservation and token benchmark.
- Canonical documentation, PRD/ADR artifacts, tests, and operator instructions.

### Excluded

- Replacing either host's native transcript or compaction engine.
- Arbitrary deletion of selected historical turns from a live host transcript.
- Treating summaries or semantic memory as authoritative source.
- Model fine-tuning, new model training, or a new vector database.
- Default rollout to every repository or every agent before pilot acceptance.
- Support for hosts beyond Codex and Claude Code in this pilot.
- Publishing raw transcripts, source bodies, or secret-bearing tool output as telemetry.

---

## Requirements

### Requirement 1: Preserve Critical Active Task State

**User Story:** As a developer working in a large intertwined codebase, I want critical active task state to survive compaction, so that the agent continues the same work without forgetting cross-system constraints.

**Acceptance Criteria (EARS)**

- **R1.1** WHEN manual or automatic compaction occurs during a repository task, THEN the pilot SHALL retain or deterministically reconstruct the task identity, user goal, current phase, approved artifact pointers, active plan step, open blockers, and completed verification status.
- **R1.2** WHEN active work has uncommitted changes, THEN the pilot SHALL retain or reconstruct the repository identity, branch, commit identity, and dirty path list without copying complete diffs into hot context.
- **R1.3** WHERE a user decision or cross-system invariant is marked critical, the pilot SHALL preserve its exact wording, provenance, and authoritative source pointer.
- **R1.4** IF a detail already exists in current source, an approved artifact, Git, or a deterministic memory record, THEN the pilot SHALL prefer a pointer and compact description over duplicating the full body.
- **R1.5** IF the active-state payload exceeds its approved budget, THEN the pilot SHALL preserve critical decisions, invariants, safety boundaries, and pending non-idempotent action state before lower-priority detail, and SHALL report every omitted category.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Approved Understanding; Requirements 2, 4, and 6
- **Assumptions:** Full evidence remains accessible from durable sources.

### Requirement 2: Revalidate Authoritative Source Before Material Continuation

**User Story:** As a repository owner, I want compacted agents to verify current source rather than trust remembered snippets, so that stale summaries cannot drive incorrect edits.

**Acceptance Criteria (EARS)**

- **R2.1** WHEN a compacted session resumes, THEN the agent SHALL treat the compact summary, hook context, and mnemo records as non-authoritative data.
- **R2.2** WHEN a post-compact decision depends on code, configuration, tests, Git state, or an approved artifact, THEN the agent SHALL reopen the exact current source before its first material write or external side effect.
- **R2.3** WHERE Claude Code path-scoped rules or nested instructions apply, the agent SHALL read a matching file and reload those rules before acting in that scope.
- **R2.4** IF current source conflicts with compacted or remembered state, THEN the agent SHALL follow current source and explicit user decisions, report the conflict, and refresh stale task state before continuing.
- **R2.5** IF required source or an approved artifact cannot be read, THEN the pilot SHALL enter visible degraded mode and SHALL NOT permit a material write based only on summary or memory.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** Requirement 1
- **Assumptions:** Read-only repository access remains available after compaction.

### Requirement 3: Provide Semantic Parity Across Codex and Claude Code

**User Story:** As a user of both Codex and Claude Code, I want the same safety and preservation outcomes on both hosts, so that switching agents does not change task guarantees.

**Acceptance Criteria (EARS)**

- **R3.1** WHERE the pilot runs on Codex or Claude Code, it SHALL enforce the same critical-state, source-authority, security, observability, degraded-mode, and rollback outcomes.
- **R3.2** WHEN either host performs manual compaction, THEN the pilot SHALL satisfy all approved preservation and revalidation requirements.
- **R3.3** WHEN either host performs automatic compaction, THEN the pilot SHALL satisfy the same approved requirements, including compaction that occurs during an active turn.
- **R3.4** IF host models or context windows expose different threshold semantics, THEN the pilot SHALL use host-native settings and SHALL NOT claim numeric threshold equivalence.
- **R3.5** IF a host version lacks a required documented lifecycle or configuration capability, THEN the pilot SHALL refuse activation on that host version and SHALL report the unsupported capability.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Current official host documentation; Requirements 1, 2, and 6
- **Assumptions:** Both hosts retain their documented native compaction APIs.

### Requirement 4: Bound Automatic Context Ingress

**User Story:** As a cost-conscious developer, I want automatic continuation, memory, and tool payloads to be bounded, so that compaction does not immediately refill context.

**Acceptance Criteria (EARS)**

- **R4.1** WHEN post-compact active state is injected automatically, THEN its serialized model-visible content SHALL NOT exceed 8,000 Unicode characters or 2,000 estimated tokens, whichever budget is reached first.
- **R4.2** WHEN default `task_context` recall returns memory, THEN the sum of returned memory `text` fields SHALL NOT exceed 4,000 Unicode characters, and the response SHALL report its budget, used amount, omitted result count, and truncation state.
- **R4.3** IF a memory body does not fit the default recall budget, THEN `task_context` SHALL return bounded preview metadata plus its `memory_id`, and explicit `memory_get(memory_id)` SHALL remain able to return the full authorized record.
- **R4.4** WHEN a tool result exceeds the host's stored-history budget, THEN the pilot SHALL retain a bounded preview and deterministic retrieval pointer rather than repeatedly carrying the complete result.
- **R4.5** WHILE automatic re-entry is assembled, the pilot SHALL exclude raw transcripts, complete diffs, source bodies, binary/base64 content, and unrelated namespaces.
- **R4.6** IF a bounded payload is truncated, THEN the pilot SHALL mark it explicitly and SHALL NOT present the preview as the complete record.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Mnemo response contract; host output limits
- **Assumptions:** Natural-language memory content is the expected default payload; dense data remains excluded.

### Requirement 5: Degrade Safely When Recovery State Is Missing or Invalid

**User Story:** As a repository owner, I want recovery failures to be visible and non-destructive, so that an incomplete compact summary cannot silently damage work.

**Acceptance Criteria (EARS)**

- **R5.1** IF active-state recovery is missing, malformed, stale, oversized, or internally contradictory, THEN the pilot SHALL enter degraded mode and display the specific reason.
- **R5.2** WHILE degraded mode is active, the agent SHALL limit itself to read-only reconstruction and SHALL NOT edit files, execute non-read-only tools, commit, push, message external systems, or claim task completion.
- **R5.3** WHEN authoritative state is successfully rebuilt and validated, THEN the pilot SHALL exit degraded mode and record the validation result.
- **R5.4** IF mnemo or Qdrant is unavailable, THEN the pilot SHALL continue reconstruction from current source, Git, and approved artifacts because memory is optional.
- **R5.5** IF reconstruction cannot succeed without user knowledge, THEN the pilot SHALL stop and request one targeted decision instead of guessing continuity.
- **R5.6** WHEN a host is at its hard context boundary, THEN pilot failure handling SHALL preserve the host's ability to compact and SHALL NOT convert an optional memory failure into avoidable context-limit loss.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Requirements 1, 2, and 6
- **Assumptions:** Host compaction itself remains available even when pilot context is unavailable.

### Requirement 6: Continue Mid-Turn Work Without Duplicate Side Effects

**User Story:** As a developer, I want automatic mid-turn compaction to continue exactly once, so that non-idempotent tools and edits are not repeated.

**Acceptance Criteria (EARS)**

- **R6.1** WHEN automatic compaction occurs in the middle of a turn, THEN the pilot SHALL preserve whether each pending operation is planned, started, completed, failed, or awaiting user approval.
- **R6.2** IF a non-idempotent operation completed before compaction, THEN the continued session SHALL NOT invoke it again unless current evidence proves a retry is required and permitted.
- **R6.3** IF operation completion is ambiguous after compaction, THEN the agent SHALL inspect current external or repository state before deciding whether to retry.
- **R6.4** WHERE an approval gate was pending before compaction, the continued session SHALL preserve the gate and SHALL NOT infer approval from the compact summary.
- **R6.5** WHEN continuation completes, THEN the pilot SHALL produce one observable lifecycle outcome for that compaction event.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Host lifecycle hooks; Requirement 1
- **Assumptions:** Host event identity or equivalent local correlation can distinguish one compact event.

### Requirement 7: Make Pilot Activation Opt-In and Reversible

**User Story:** As the environment owner, I want controlled enablement and rollback, so that the pilot cannot unexpectedly affect every repository or overwrite host configuration.

**Acceptance Criteria (EARS)**

- **R7.1** WHEN the pilot is first installed, THEN it SHALL remain disabled until explicitly enabled for a named host and allowlisted repository or workspace.
- **R7.2** WHEN host settings are activated, THEN the activation process SHALL merge only pilot-owned entries and preserve unrelated settings, hooks, plugins, MCP servers, environment values, and comments where the format supports them.
- **R7.3** WHEN the pilot is disabled or rolled back, THEN it SHALL remove or disable only pilot-owned activation and SHALL NOT delete transcripts, source, Git changes, approved artifacts, mnemo records, or unrelated user configuration.
- **R7.4** IF activation, hook trust, or effective configuration cannot be verified, THEN the system SHALL report the pilot as inactive and SHALL NOT claim protection.
- **R7.5** WHEN both host adapters are ready, THEN acceptance SHALL still require separate observed activation evidence for Codex and Claude Code.
- **R7.6** IF wider rollout beyond the allowlist is proposed, THEN the pilot SHALL require a separate user approval backed by passing benchmark evidence.
- **R7.7** WHEN Claude Code performs normal startup or interactive directory-trust writes to host-owned `.claude.json`, THEN the pilot SHALL never write or revert that file and SHALL accept only `numStartups + 1`, creation of the exact allowlisted project subtree with `hasTrustDialogAccepted=true`, and semantic equality everywhere else; any other delta SHALL stop the exact pilot child with `host_registry_drift`.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Requirements 3, 9, and 10
- **Assumptions:** User-level settings are writable only through explicit approved activation.

### Requirement 8: Protect Secrets, Scope, and Trust Boundaries

**User Story:** As a security-conscious developer, I want compaction state and diagnostics to exclude sensitive or untrusted payloads, so that token reduction does not create a data-leak path.

**Acceptance Criteria (EARS)**

- **R8.1** WHEN continuation state, memory previews, or diagnostics are produced, THEN the pilot SHALL exclude credentials, tokens, secret environment values, raw transcript bodies, and raw secret-bearing tool output.
- **R8.2** WHEN memory or hook input contains instructions, THEN the agent SHALL treat those instructions as untrusted data and SHALL reject any attempt to broaden paths, tools, network, approvals, readers, or task scope.
- **R8.3** WHERE mnemo ACLs, namespaces, redaction, and revocation apply, the bounded recall behavior SHALL preserve them.
- **R8.4** WHEN executable hooks are installed or changed, THEN both hosts SHALL require and expose their normal trust/review boundary.
- **R8.5** IF diagnostics cannot represent an event without sensitive content, THEN they SHALL record only a redacted failure category and count.
- **R8.6** WHEN the Claude registry guard captures or compares state, THEN it SHALL retain only bounded counts, hashes, approved change names, and closed failure codes; it SHALL NOT persist the registry body, project bodies, credentials, caches, or absolute registry path.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** Existing mnemo and host security boundaries
- **Assumptions:** No new external telemetry service is required.

### Requirement 9: Provide Content-Free Observability

**User Story:** As the pilot operator, I want concise diagnostics and measurements, so that I can prove savings and diagnose failures without logging private content.

**Acceptance Criteria (EARS)**

- **R9.1** WHEN a compaction lifecycle event occurs, THEN the pilot SHALL record host, host version, model/context class when available, trigger type, repository allowlist identity, event correlation identity, and outcome.
- **R9.2** WHEN host telemetry exposes context usage, THEN the pilot SHALL record pre-compact and post-re-entry token usage or available-context values and the measurement source.
- **R9.3** WHEN continuation state is assembled, THEN the pilot SHALL record serialized character count, estimated token count, included category names, omitted category names, and degraded/truncated flags without recording category contents.
- **R9.4** IF a metric is unavailable from a host, THEN the pilot SHALL label it `unmeasured` and SHALL NOT estimate it as an observed host value.
- **R9.5** WHILE diagnostics are retained, they SHALL remain local, bounded, and removable without affecting source, memory, or task continuity.

**Additional Details**

- **Priority:** Medium
- **Complexity:** Medium
- **Dependencies:** Host telemetry and Requirement 8
- **Assumptions:** Some measurements may require controlled test harness observation rather than hook input.

### Requirement 10: Validate Preservation on a Representative Complex Workload

**User Story:** As the owner of complex codebases, I want the pilot tested against intertwined real-world state, so that simple toy success cannot hide continuity failures.

**Acceptance Criteria (EARS)**

- **R10.1** WHEN the pilot benchmark is defined, THEN it SHALL use at least one user-approved representative large codebase or a faithful isolated fixture derived from it.
- **R10.2** WHEN benchmark state is prepared, THEN it SHALL include at least twelve probes covering cross-system invariants, approved decisions, dirty paths, file/symbol relationships, negative findings, exact error or command evidence, verification status, pending work, approval boundaries, and one non-idempotent-operation scenario.
- **R10.3** WHEN manual and automatic compaction are tested on each host, THEN the pilot SHALL retain and source-validate 100% of probes marked critical and at least 90% of all probes.
- **R10.4** WHEN a compacted run is compared with its uncompacted baseline, THEN it SHALL match or exceed baseline task-state accuracy and SHALL produce no additional source-contradicting or fabricated exact-code claims.
- **R10.5** WHEN functional benchmark checks pass, THEN the pilot SHALL still require one real-session review by the repository owner before broader rollout.
- **R10.6** IF the benchmark codebase has unrelated dirty work, THEN testing SHALL use an isolated worktree, copy, or reversible harness and SHALL NOT reset, stash, or alter that work.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Requirements 1 through 9
- **Assumptions:** User selects the representative workload before Test phase acceptance.

### Requirement 11: Demonstrate Token and Coherence Improvement Without Thrashing

**User Story:** As a user paying for long sessions, I want measured token reduction without repeated compaction, so that the pilot produces practical savings and stable answers.

**Acceptance Criteria (EARS)**

- **R11.1** WHEN the benchmark compacts eligible conversation history and adds bounded re-entry state, THEN it SHALL free at least 50% of the tokens occupied by the pre-compact conversation body where the host exposes a credible measurement.
- **R11.2** WHEN a host does not expose credible conversation-body measurement, THEN acceptance SHALL use a documented proxy and SHALL label the result qualified rather than confirmed.
- **R11.3** WHILE ten standard benchmark continuation turns execute after compaction, the pilot SHALL NOT trigger another compaction unless a declared oversized input or host-specific hard boundary explains it.
- **R11.4** WHEN compacted answers are scored, THEN they SHALL meet Requirement 10 accuracy and SHALL contain fewer stale-state contradictions than the pre-pilot long-context workload.
- **R11.5** WHEN automatic lifecycle processing runs, THEN its local bounded-state assembly SHALL complete within 2 seconds at the 95th percentile in the benchmark environment, excluding host-native summarization time and unavailable external services.

**Additional Details**

- **Priority:** High
- **Complexity:** High
- **Dependencies:** Requirements 4, 9, and 10
- **Assumptions:** Benchmark records idle-host conditions and separates host-native compaction latency.

### Requirement 12: Preserve Existing Workflows and Fresh-Session Escape Hatch

**User Story:** As an existing `coding-cli` user, I want compaction to coexist with Batman, mnemo, handoff, and host safety controls, so that token optimization does not weaken established workflows.

**Acceptance Criteria (EARS)**

- **R12.1** WHERE Batman approval gates, mnemo phase checkpoints, or handoff pointer rules apply, the pilot SHALL preserve their existing authority, timing, and provenance requirements.
- **R12.2** WHEN the user chooses a fresh session or `/clear` instead of in-place compaction, THEN the existing handoff path SHALL remain available and SHALL reference durable artifacts rather than duplicating their bodies.
- **R12.3** WHEN the pilot modifies canonical customization behavior, THEN it SHALL change canonical source only and SHALL keep installed host copies as thin pointers or adapters.
- **R12.4** WHEN host activation is applied, THEN native sandbox, approval, tool, plugin-trust, and credential boundaries SHALL remain unchanged.
- **R12.5** IF an existing user hook or setting overlaps pilot behavior, THEN the activation process SHALL surface the conflict and require an explicit resolution instead of silently replacing it.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** Existing canonical workflows; Requirement 7
- **Assumptions:** Current approved workflow behavior remains in force.

---

## Non-Functional Requirements

### Performance Requirements

- WHEN automatic state or memory context is produced, THEN the pilot SHALL enforce Requirements 4.1 and 4.2 before model-visible serialization.
- WHEN benchmark measurement is available, THEN the pilot SHALL meet the 50% conversation-body reduction and 2-second p95 local assembly targets in Requirement 11.
- WHILE the pilot is active, it SHALL avoid repeated compaction caused by its own re-entry payload.

### Security Requirements

- WHEN any model-visible or diagnostic payload is formed, THEN the pilot SHALL redact or exclude secret-bearing content and enforce scope/ACL boundaries.
- IF retrieved data attempts to change task authority, THEN the agent SHALL reject it and continue from explicit instructions and current source.
- WHEN hooks are activated, THEN normal host trust and approval controls SHALL remain enabled.

### Usability Requirements

- WHEN the pilot activates, degrades, truncates, or rolls back, THEN it SHALL show a concise status and actionable reason.
- IF host metrics are unavailable, THEN operator output SHALL distinguish confirmed, qualified, and unmeasured claims.
- WHERE host controls differ, documentation SHALL use native Codex and Claude Code names and examples rather than a false shared knob.

### Reliability Requirements

- WHEN mnemo, Qdrant, a hook, or an artifact is unavailable, THEN the pilot SHALL follow Requirement 5 without corrupting source or task state.
- IF compaction occurs mid-turn, THEN the pilot SHALL meet Requirement 6 and avoid duplicate side effects.
- WHEN the pilot is disabled, THEN native host behavior and existing workflows SHALL remain usable.

### Compatibility Requirements

- WHERE tests run on Windows, pilot scripts and paths SHALL function without requiring WSL.
- WHERE POSIX support is claimed, the same deterministic fixtures SHALL pass using supported shell/path conventions.
- IF host behavior changes in a later version, THEN the pilot SHALL fail its version/capability check until compatibility is revalidated.

---

## Constraints and Assumptions

### Technical Constraints

- Codex and Claude Code own native compaction and expose different trigger semantics.
- Claude path-scoped and nested instructions may require file reads after compaction.
- Codex compact `SessionStart` may run during the immediate continuation of a turn.
- Hook output and model-visible automatic context must remain bounded.
- Mnemo is optional and may be offline; current source and approved artifacts remain sufficient recovery authorities.
- Current supported baselines are Codex CLI 0.145.0 and Claude Code 2.1.220 on Windows; these are test identities, not permanent minimum-version promises.

### Business Constraints

- Pilot must cover both Codex and Claude Code before acceptance.
- No global all-repository rollout without separate user approval.
- Existing unrelated configuration and dirty work must remain untouched.
- Functional tests do not replace real-session owner review.

### Assumptions

- At least one representative complex workload will be available in isolated form.
- Host-native manual and automatic compaction remain supported.
- Approved Batman artifacts and Git state remain readable after compaction.
- The environment owner can explicitly trust reviewed hooks and enable thin host adapters.

---

## Success Criteria

### Definition of Done

- All twelve requirement groups pass on supported Codex and Claude Code versions.
- Mnemo default recall budget and deterministic full-record retrieval are tested.
- Manual, automatic, mid-turn, missing-state, stale-state, oversized-state, and rollback scenarios pass deterministic fixtures.
- Representative complex-workload benchmark meets critical retention, overall accuracy, token-reduction, no-thrash, and no-duplicate-side-effect gates.
- Existing host configuration and workflow regression checks pass.
- PRD, approved ADRs, activation/rollback documentation, exact commands, versions, and open limits are recorded.
- Repository owner completes real-session pilot review before wider rollout.

### Acceptance Metrics

- 100% critical benchmark probe retention and source validation.
- At least 90% overall benchmark probe accuracy.
- Zero additional fabricated exact-code/source claims versus uncompacted baseline.
- At least 50% measured eligible conversation-body token reduction, or explicitly qualified proxy evidence when the host cannot expose it.
- Automatic continuation payload no larger than 8,000 characters or 2,000 estimated tokens.
- Default task-context memory text no larger than 4,000 characters.
- No unexplained repeat compaction within ten standard continuation turns.
- Local bounded-state assembly p95 no slower than 2 seconds under recorded benchmark conditions.
- Zero secret leakage, unauthorized scope expansion, duplicate non-idempotent action, unrelated configuration overwrite, or destructive rollback.
- Observed activation and rollback evidence on both hosts.

---

## Glossary

| Term | Definition |
|---|---|
| Hot context | Model-visible conversation, tool output, and injected context processed on subsequent requests. |
| Durable state | Current source, tests, Git state, approved artifacts, and explicitly stored decisions that remain re-readable outside conversation history. |
| Compaction | Host-native replacement of older conversation history with a shorter summary. |
| Active task state | Minimal state needed to continue one task safely: goal, decisions, plan position, evidence pointers, dirty paths, checks, blockers, and pending operation state. |
| Critical invariant | User-approved constraint whose loss could cause unsafe or materially incorrect cross-system work. |
| Revalidation | Reading current authoritative sources after compaction before relying on remembered state. |
| Automatic ingress | Context added without an explicit per-record user request, including lifecycle context, default memory recall, and retained tool previews. |
| Degraded mode | Visible read-only recovery state entered when safe continuation cannot yet be proven. |
| Semantic parity | Same observable guarantees across hosts even when native controls and numeric thresholds differ. |
| Compaction thrashing | Repeated compaction soon after a previous compaction because summaries or re-entry payloads refill context. |
| Material action | File mutation, non-read-only tool use, external message, commit/push, or completion claim that depends on task state. |

---

## Phase 2a Discovery Record

- **Outcome:** Found approved Phase 1 boundary and current implementation gaps; no compaction-specific canonical asset or active host pilot exists. Current mnemo `task_context` remains unbounded by aggregate content size. Existing canonical state uses source-authoritative artifacts and pointers. Host compaction controls remain asymmetric.
- **Current-source queries:** `rg -n "compact|compaction|autoCompact|tool_output_token_limit|model_auto_compact" .`; `rg -n "task_context|PreCompact|PostCompact|SessionStart" skills agents mnemo .claude .codex hooks README.md CHANGELOG.md`; `rg --files mnemo`; focused reads of `mnemo/requirements.txt`, `mnemo/README.md`, current configs, hook files, approved Understanding, and every task steering file.
- **Official-host discovery reused and rechecked from Phase 1:** current Codex slash-command/config/hook documentation and current Claude Code context-window/cost/hook/settings/environment/plugin documentation, retrieved 2026-08-01.
- **Memory preflight:** mnemo healthy with 546 points. Focused top-three recall returned approved Phase 1 checkpoint `1a160139-c630-4f76-bf90-f194e9b35b23` plus two older workflow-checkpoint records by `claude-code` dated 2026-07-16. Memory informed continuity only; current source and approved artifact remained authoritative.
- **Phase 1 checkpoint written after approval:** `1a160139-c630-4f76-bf90-f194e9b35b23`.

---

## Requirements Review Checklist

### Completeness

- [x] Every requirement has a user story and EARS acceptance criteria.
- [x] Positive, failure, mid-turn, rollback, security, and compatibility scenarios are covered.
- [x] Non-functional requirements and measurable success criteria are present.
- [x] Codex and Claude Code are both in acceptance scope.

### Quality

- [x] Requirements state observable outcomes rather than a selected implementation design.
- [x] Numeric budgets and gates are explicit and testable.
- [x] Summary, memory, artifacts, and authoritative source use distinct terms.
- [x] Confirmed, qualified, and unmeasured evidence cannot be conflated.

### EARS Format Validation

- [x] Event requirements use `WHEN ... THEN ... SHALL`.
- [x] Conditional requirements use `IF ... THEN ... SHALL`.
- [x] Continuous requirements use `WHILE ... SHALL`.
- [x] Context requirements use `WHERE ... SHALL`.

### Traceability

- [x] Requirements trace to approved Understanding risks and change surfaces.
- [x] Requirement dependencies are named.
- [x] Success metrics trace to numbered requirements.
- [x] Phase 2a discovery and approved Phase 1 memory provenance are recorded.
