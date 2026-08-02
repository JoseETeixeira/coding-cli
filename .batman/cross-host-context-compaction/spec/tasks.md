# Tasks: Cross-Host Context Compaction Pilot

Status: Approved — Phase 4 approved 2026-08-01; Phase 5 implementation in progress.

Approved inputs:

- `requirements.md` 1.1, including Refresh 3 approval on 2026-08-01.
- `design.md` 1.2.0, including Refresh 4 diagnostic approval on 2026-08-01.
- Accepted ADRs 0010, 0011, 0012, 0013, and 0014.

This plan keeps the pilot disabled by default. Task 6 contains a separate approval gate before any durable customization-layer edit. Task 10 contains another exact-target approval gate before any user-level Codex or Claude Code activation. Wider rollout is not authorized by approval of this plan.

## Phase 4a Discovery Record

### Outcome

- No `context_compaction/` package exists. The new standard-library core and its tests therefore have a clean ownership boundary.
- `mnemo/mnemo/engine.py:294-304` currently returns every selected memory body under the public top-level `memory` field. `mnemo/mnemo/config.py` has no response-budget settings, and `memory_get` retrieves by ID without applying the reader, revocation, namespace, or expiry filters used by search/list.
- Backward compatibility therefore keeps `memory` as the `task_context` item field and adds contract/budget metadata around it. It does not duplicate bodies under a second `items` field. The unchanged `memory_get(memory_id)` call shape gains the authorization filtering assumed by the approved Design and R8.3.
- `mnemo/tests/test_engine.py` uses real Qdrant plus a deterministic fake embedder and skips when Qdrant is absent. `mnemo/tests/mcp_smoke.py` exercises the real stdio surface. Pure budget/serialization tests must be added separately so the safety contract is testable offline.
- `.claude/hooks/batman-phase-checkpoint.py` and `.claude/hooks/batman-handoff-checkpoint.py` establish fail-soft, metadata/pointer-first hook patterns, but no hook unit tests currently reference either script.
- Repository host layers are minimal: `.codex/config.toml` registers mnemo; `.claude/settings.json` is empty; `hooks/hooks.json` contains only the Stop auto-improvement hook. No compaction activation exists and no installer should rewrite these files.
- Current host baselines remain Codex CLI 0.145.0 and Claude Code 2.1.220.
- The approved representative checkout is still clean at `0db30624dd32d814b937aa88b5ec84e18d4b130d` on branch `fix/work-queue-session-navigation`. `rg --files` returns 16,722 files, of which 12,001 end in `.ts`.
- Current `educode` source confirms the probe authorities below. The active checkout was read only; benchmark dirties will be created only in an isolated worktree/copy.
- Architecture-risk check: empty. Discovery refined an additive MCP compatibility detail and found a missing read-authorization check already required by the approved Design; it did not change native-compaction ownership, authority, activation, or failure boundaries.

### Queries Used

- `rg --files` over `mnemo/`, `.claude/`, `hooks/`, `scripts/`, `.codex/`, `prompts/`, `skills/`, and `agents/`.
- Focused reads of `mnemo/mnemo/{config,engine,server}.py`, `mnemo/tests/{test_engine,mcp_smoke}.py`, `mnemo/run_server.py`, the two Batman checkpoint hooks, host config stubs, manifests, README, CHANGELOG, and handoff guidance.
- `rg` for `task_context`, `memory_get`, hook test coverage, compaction package presence, activation/config seams, and existing test commands.
- `codex --version` and `claude --version`.
- In read-only `C:\Users\josee\source\educode`: Git identity/status, file counts, focused `rg`/reads over execution targets, task intents, write claims, Write Broker, runtime command receipts, credential installation, Relay admission, Work Queue projection/navigation, review effects, and approved Batman task state.
- Negative dependency query: `rg -n "vs/sessions|sessions/" src/vs/platform/agenticRuntime src/vs/agenticRelay src/vs/oauthExchangeBroker` returned exit 1 with no matches.

## Frozen Preservation Probes

These fourteen probes and their critical labels are fixed before any uncompacted baseline. Implementation may machine-encode the manifest and refresh line spans only when the authoritative source hash changes; changing wording, expected outcomes, or criticality requires a recorded plan revision before rerunning baselines.

- **P01 — Active phase, verification, and pending work (critical).** Ask which phase the Agentic Development Workbench is in and what remains open. Expected: Phase 5 implementation is in progress; performance Task 20.5, full-suite Task 23.1, and owner-acceptance Task 23.6 remain unchecked; focused compile/test evidence does not close those gates. Authority: `.batman/agentic-development-workbench/spec/tasks.md:3,245,254,284,289`.
- **P02 — Approval boundary (critical).** Ask whether a newly discovered change to an authority boundary, credential location, write path, relay payload, dependency direction, or user-visible contract may proceed immediately. Expected: no; it requires a superseding ADR and renewed approval. Authority: `.batman/agentic-development-workbench/spec/tasks.md:300`.
- **P03 — Exact execution target (critical).** Ask what identifies an `AgentExecutionTarget` and what happens when the source/account/capability/model/mode is stale. Expected: the closed target carries provider, session type, provider mode, usage source, account, model selection, and capability revision; resolution returns explicit unresolved/blocked error codes rather than silently substituting a target. Authority: `src/vs/platform/agenticRuntime/common/executionTarget.ts:148-188,207-281`.
- **P04 — Cross-component capability binding (critical).** Ask what binds a provider request, tool call, broker apply, or external effect to runtime authority. Expected: the opaque capability binds runtime instance/boot, Agent Host authority, participant, attempt, exact target digest, credential revision, request kind/identity, sequence, issuance, and expiry; dispatch retains the target snapshot and credential revision. Authority: `src/vs/platform/agenticRuntime/common/executionTarget.ts:365-391`.
- **P05 — Duplicate and overlap coordination.** Ask how exact duplicates and potential overlaps differ. Expected: an exact duplicate returns the existing intent with `created=false`; a potential overlap creates `proposed` or unattended `needsInput` state and permits only Join Existing, Start Separately, or Cancel resolution. Authority: `src/vs/platform/agenticRuntime/node/taskIntentCoordinator.ts:88-178`.
- **P06 — Write-claim ordering and fencing (critical).** Ask how canonical write eligibility is ordered and how a stale claimant is rejected. Expected: requests receive repository-local enqueue sequence, eligible non-conflicting requests are granted in that order, each grant receives a new fence and nonce, and stale state raises `WRITE_CLAIM_STALE_FENCE`. Authority: `src/vs/platform/agenticRuntime/node/writeClaimCoordinator.ts:45-61,192-219,286-290`.
- **P07 — Write Broker replay and crash recovery (critical).** Ask whether a broker capability can be reused and what recovery does to prepared/applying journals. Expected: capabilities are one-use and bound to plan/fence/nonce/digest; replay raises `WRITE_BROKER_CAPABILITY_INVALID_OR_REPLAYED`; recovery rolls prepared/applying work back and quarantines rollback failure. Authority: `src/vs/platform/agenticRuntime/node/writeBroker.ts:59-95,141-195,243-265`.
- **P08 — Exact command-receipt evidence (critical).** Ask for the exact code and message when an idempotency key is reused with another digest. Expected: `RUNTIME_COMMAND_DIGEST_CONFLICT` and `Runtime idempotency key was reused with another digest`; committed repeats return the stored receipt, while an accepted crash marker is incomplete. Authority: `src/vs/platform/agenticRuntime/node/runtimeDatabase.ts:1291-1382`.
- **P09 — Credential boundary (critical).** Ask where reusable credentials live and what secure-storage failure permits. Expected: plaintext is opened only in memory, stored through the credential broker under an alias, buffers are zeroed, SQLite keeps alias/account digests rather than tokens, and degraded secure storage disables durable secret persistence and IDE-closed execution. Authority: `src/vs/platform/agenticRuntime/node/credentialInstallService.ts:82-110,137-212,262-277`.
- **P10 — Relay verification order.** Ask whether route lookup or JSON-derived routing occurs before provider verification. Expected: no; body bounds and provider verification occur before route resolution, and only verified evidence is admitted. Authority: `src/vs/agenticRelay/node/relayIngressService.ts:49-84`.
- **P11 — Work Queue relationship/navigation.** Ask how a projected item reaches a live agent session. Expected: the runtime projection joins source items, task intents, participants/runs, reviews, and terminal history; the UI resolves the stored session ID against current sessions, opens its resource when found, and returns false when absent. Authority: `src/vs/platform/agenticRuntime/node/runtimeWorkQueueHandlers.ts:121-210,225-348` and `src/vs/sessions/contrib/workQueue/common/workQueueSessionNavigation.ts:17-27`.
- **P12 — Non-idempotent external effect (critical).** Ask what happens after an ambiguous or recovered publish/merge dispatch. Expected: a committed outbox worker reconciles provider state before any repeat; unknown stops, found completes without resend, absent may resend, and transport/timeout-like failures become ambiguous rather than blind retries. Authority: `src/vs/platform/agenticRuntime/node/runtimeReviewEffectDispatchCoordinator.ts:270-274,324-425,428-483`.
- **P13 — Negative dependency finding.** Ask whether the platform authorities import `vs/sessions`. Expected: no matches at the frozen commit for `rg -n "vs/sessions|sessions/" src/vs/platform/agenticRuntime src/vs/agenticRelay src/vs/oauthExchangeBroker`; `vs/sessions` consumes platform authority, not the reverse.
- **P14 — Relative dirty paths (critical).** In the isolated benchmark only, append a marker to tracked `CONTEXT.md` and create untracked `context-pilot-dirty/queued-change.ts`. Ask for repository dirtiness. Expected: retain those two relative paths and their modified/untracked states without a full diff, file body, or absolute active-checkout path.

## Task Planning Grill-Me Coverage

- **Scope:** Settled. Initial support is exactly Codex 0.145.0 and Claude Code 2.1.220 on one explicit repository allowlist; no global/default/plugin-first rollout.
- **Data model:** Settled. Versioned disposable private state, bounded metadata/pointers, action journal, closed degradation codes, and additive mnemo preview metadata. Current-source discovery resolves the legacy top-level response name to `memory`.
- **Operator experience:** Settled. Explicit plan/enable/run/status/validate/disable/purge commands, visible gated/degraded reasons, one-host-at-a-time activation, and exact previews before external writes.
- **Non-functional requirements:** Settled. Character/token/memory envelopes, two-second p95 assembly, newest-200 retention, accuracy/savings/thrashing gates, and content-free diagnostics are exact.
- **Integrations:** Settled. Native compactors remain owners; mnemo, Batman checkpoints, handoff, scoped instructions, sandbox, approvals, credentials, and unrelated hooks/config remain intact.
- **Edge cases:** Settled. Missing/stale/malformed/oversized/contradictory state, offline memory, ambiguous task/action, source drift, unsupported host/trust, uncovered tools, ownership drift, and rollback failure all have planned tests and outcomes.
- **Constraints:** Settled. No transcript rewriting or bodies, no active-`educode` mutation, no reset/stash, no primary-host-config rewrite, no new network service, and no inferred metrics presented as observed.
- **Terminology:** Settled in `CONTEXT.md`; no new domain term emerged during Task Planning.
- **Completion signals:** Settled. Deterministic gates, four real compact cells, rollback on both hosts, frozen-probe thresholds, qualified savings, and owner acceptance remain distinct and mandatory.
- **Deferred decisions:** None block this plan. The exact customization diff in Task 6 and exact user-level activation diff in Task 10 are intentionally deferred approval gates because their concrete generated contents do not exist yet.

## Implementation Plan

- [x] 1. Establish characterization tests and the bounded core contracts.
  - Record a content-free baseline for the selected Git revision, clean/dirty state, host versions, current hook/config topology, current handoff behavior, and current `task_context` ordering before production changes.
  - Add `context_compaction/__init__.py`, `models.py`, and `budget.py` with strict versioned dataclasses/enums for pilot config, hook events/decisions, active state, actions, diagnostics, closed degradation codes, and measured-versus-unmeasured values.
  - Implement one deterministic priority allocator and conservative ASCII/non-ASCII token estimator enforcing both the 8,000-character and 2,000-estimated-token re-entry caps, explicit included/omitted categories, and truncation metadata.
  - Add offline tests for empty, exact-limit, one-over-limit, all-non-ASCII, poisoned strings, oversized fields, deterministic ordering, priority preservation, and serialization that never emits secret/raw-body categories.
  - Keep all fixtures synthetic or redacted and prove that this task neither reads transcripts nor changes real Codex/Claude configuration.
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 4.1, 4.5, 4.6, 5.1, 6.1, 9.3, 9.4, 12.3, 12.4_

- [x] 2. Make mnemo `task_context` bounded while preserving authorized exact retrieval.
  - Add validated configuration defaults for 4,000 aggregate text characters, 500 characters per preview, and an 8,000-character hard response envelope; reject invalid values deterministically.
  - Characterize ranking, metadata, namespace, reader ACL, expiry, and revocation behavior before altering serialization, including an offline allocator suite and real-Qdrant integration cases.
  - Budget ranked results after all authorization filters, preserve order and the existing top-level `memory` field, and add `contract_version=2`, original/returned lengths, `memory_get_required`, matched/returned/omitted counts, budget use, and explicit truncation fields.
  - Omit lower-ranked items only when metadata cannot fit; never split malformed Unicode or hide truncation, and keep the complete MCP response inside the hard envelope.
  - Preserve the public `memory_get(memory_id)` call shape while applying reader ACL, revocation, and expiry checks before returning the full authorized record; return a content-free not-found/unauthorized response otherwise.
  - Make `mnemo/run_server.py` able to import the canonical shared budgeter from any working directory without adding a network dependency, then extend engine and stdio smoke tests for preview/full-record behavior.
  - Update mnemo documentation and shared-memory examples to describe previews and explicit full retrieval without treating memory as authority.
  - _Requirements: 2.1, 2.4, 4.2, 4.3, 4.6, 5.4, 8.1, 8.3, 9.3, 12.1, 12.5_

- [x] 3. Implement safe repository reconstruction and private state storage.
  - Add `context_compaction/repository.py` to resolve canonical allowlisted roots, repository fingerprints, branch/HEAD, porcelain-v2 relative dirty paths, selected Batman task/artifact pointers, active plan state, scoped instruction pointers, verification state, blockers, approvals, and critical anchors without recursive source scans or full diffs.
  - Implement deterministic task selection in the approved order: explicit slug, exact branch slug, exactly one incomplete artifact set, otherwise `task_ambiguous`; never infer authority from modification time.
  - Add `context_compaction/storage.py` with worktree-private `git rev-parse --path-format=absolute --git-path coding-cli-context-pilot` storage, safe non-Git fallback keyed by canonical-root SHA-256, schema/owner markers, restrictive permissions where supported, atomic sibling replacement, deduplication, and current-plus-200 retention.
  - Persist only bounded metadata, relative pointers, hashes, counts, and status; exclude transcripts, compact-summary bodies, tool inputs/outputs, commands, diffs, source bodies, binary data, absolute diagnostic paths, and likely credentials.
  - Reject traversal, symlink/junction escape, UNC/device ambiguity, allowlist mismatch, unsafe roots, unknown schemas, stale fingerprints, oversized state, ownership drift, and contradictory sources with closed degraded reasons.
  - Add temporary-repository/worktree tests for zero/one/multiple tasks, nested instructions, dirty/untracked paths, detached HEAD, non-Git fallback, concurrency, atomicity, retention, permissions, and no source-worktree dirtiness.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 4.4, 4.5, 4.6, 5.1, 5.4, 5.5, 7.1, 7.3, 7.4, 8.1, 8.2, 8.4, 9.1, 9.2, 9.3, 9.4, 9.5, 12.4_

- [x] 4. Implement lifecycle recovery, action journaling, and the validation gate.
  - Add `context_compaction/lifecycle.py` with idempotent normalized transitions for `PreCompact`, `PostCompact`, compact-sourced `SessionStart`, `PreToolUse`, and `PostToolUse`.
  - Make `PreCompact` capture best-effort state atomically and always allow native compaction; make post-compact continuation require a current recovery epoch and enter visible `validation_required`, `degraded`, or stop state when reconstruction is missing, stale, malformed, oversized, contradictory, or ambiguous.
  - Journal material actions as planned/started/completed/failed/awaiting-approval/ambiguous using only bounded tool class/name and input fingerprint; retain incomplete/ambiguous records plus a bounded completed tail.
  - Suppress automatic replay of completed non-idempotent fingerprints, inspect current state before resolving ambiguity, and preserve every unresolved approval boundary across compaction.
  - Record successful current-epoch source reads as relative path plus current hash, then implement validation of allowlist identity, repository/artifact/rule fingerprints, required evidence reads, and action ambiguity without claiming semantic understanding.
  - On source conflict, refresh the envelope and remain read-only; on missing user knowledge, ask one targeted question; when mnemo is unavailable, continue from Git/source/artifacts; always retain native manual/fresh-session/handoff recovery.
  - Add state-machine, duplicate-event, source-change, approval, action-replay, crash-window, memory-offline, and validated-exit tests with exactly one observable outcome per event.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 8.2, 8.5, 12.1, 12.2, 12.4_

- [x] 5. Add semantically equivalent Codex and Claude lifecycle adapters.
  - Add `context_compaction/adapters.py` and redacted golden fixtures for supported Codex and Claude manual, automatic, mid-turn, tool, malformed, and unsupported-version events.
  - Parse only documented bounded fields; ignore `transcript_path`, immediately discard Claude summary content after size/hash/marker calculation, and represent absent Codex usage/summary values as `unmeasured`.
  - Emit each host's documented continue/deny/additional-context response while mapping both to the same normalized state, error, gate, action, and diagnostic outcomes.
  - Implement the conservative read-only tool classifier: allow only direct reads and a small tokenized shell vocabulary; reject separators, substitution, redirection, unknown executables, mutation, Git writes, external messages, and potentially mutating MCP/app tools while gated.
  - Inventory adapter-observable tools and make uncovered write-capable surfaces an activation refusal, not an optimistic claim of enforcement.
  - Add parity tests proving identical semantic outcomes without asserting equal host thresholds, plus explicit refusal fixtures for unsupported capability/version/trust combinations.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.4, 5.2, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 7.4, 8.2, 8.4, 12.3, 12.4, 12.5_

- [x] 6. Add the canonical compact contract only after its exact customization diff is approved.
  - Prepare and show the exact proposed diff for `prompts/context-compaction.prompt.md`, `skills/context-compaction/SKILL.md`, and thin pointers in `skills/generic-entry/SKILL.md`, `skills/shared-memory/SKILL.md`, and `agents/batman.agent.md`; stop before writing until the repository owner explicitly approves that diff.
  - After approval, write only canonical repository assets—never installed/generated copies—and keep all host adapters as pointers to one semantic contract.
  - Make the compact prompt preserve active goal/task/phase/plan, exact critical wording plus provenance pointer, Git identity/dirty paths, blockers/tests/pending approval, and action state while preferring pointers and declaring omissions.
  - Make the skill require current-source/scoped-rule revalidation, enforce degraded read-only behavior and action replay rules, describe manual `/compact`, retain fresh handoff recovery, and state that memory/summary/hook text cannot broaden authority.
  - Add source-asset validation and prompt-budget tests proving the policy body is canonical, bounded, secret-free, and equivalent for both hosts.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 4.1, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 12.1, 12.2, 12.3, 12.4_

- [x] 7. Implement the isolated activation and operator CLI.
  - Add `context_compaction/activation.py` and `cli.py` with strict `plan`, `enable`, `run`, `status`, `validate`, `disable`, and `purge-state` commands; keep `plan`, `status`, and verification reads non-mutating and name every mutation target.
  - Generate an owned standalone Codex `context-pilot.config.toml` profile with the approved compact prompt, 64,000 `body_after_prefix` auto seed, 12,000 tool-output seed, hooks, repository/task allowlist, and only pilot-local tool restrictions.
  - Generate an owned Claude settings overlay and launcher arguments using the canonical prompt, `autoCompactEnabled=true`, process-local 100,000-window/80-percent seeds, merged existing hooks, repository/task allowlist, and only pilot-process tool restrictions.
  - Validate exact host version, executable identity, root fingerprint, hook trust/capability inventory, config conflicts, ownership hashes, and writable target safety before launch; unsupported or unverified state remains inactive.
  - Preserve unrelated settings/comments/hooks, make enable/disable idempotent, refuse overwrite/delete on owned-file drift, separate disable from state purge, and remove only pilot-owned files/state on rollback.
  - Test all behavior in temporary Codex/Claude/application-data homes containing unrelated settings, hooks, comments, and conflicts; do not touch actual user homes in this task.
  - Emit bounded content-free status/diagnostics with host/version/model class/trigger/repository fingerprint/event/outcome, category and size counts, degradation/truncation, usage only when exposed, and `unmeasured` otherwise.
  - _Requirements: 3.2, 3.3, 3.4, 3.5, 7.1, 7.2, 7.3, 7.4, 7.6, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 12.4, 12.5_

- [x] 8. Build the isolated preservation and savings benchmark harness.
  - Machine-encode P01-P14, their expected facts, authority paths/anchors, critical flags, and the frozen `educode` commit in a versioned benchmark manifest; validate source hashes/spans and refuse silent probe drift.
  - Create a separate `educode` worktree or faithful copy at the frozen commit, assert the active checkout remains clean/unchanged, and create P14 dirtiness only inside the isolated target without reset or stash.
  - Add reproducible uncompacted, manual-compact, automatic-compact, and mid-turn scenario drivers for each host/model configuration, with valid/missing/stale/malformed/oversized/memory-offline/action-ambiguous/rollback cases.
  - Score source-validated retention, critical/overall accuracy, false exact-code claims, stale contradictions, dirty-path fidelity, approval retention, action replay, compaction count, eligible-body reduction, and local assembly latency without scoring PRD/ADR optimism as source truth.
  - Use host token evidence only when credible; otherwise emit a named qualified proxy. Measure fixed prefix separately, mark unavailable values `unmeasured`, and retain content-free bounded artifacts.
  - Add at least 30 local assembly samples per representative state and ten standard continuation turns per compact run, with explicit p50/p95/max and compaction-thrashing results.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.6, 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 9. Complete deterministic security, fault, regression, performance, and operator documentation gates.
  - Run the offline core/adapter/activation suites, real-Qdrant mnemo engine suite, stdio MCP smoke test, temporary Git/worktree integration suite, golden parity suite, and existing checkpoint/handoff regression scenarios with exact commands/results.
  - Fault-inject malformed/oversized events, source/artifact/rule drift, missing state, action ambiguity, unsupported versions, untrusted hooks, mnemo/Qdrant outage, concurrent events, partial writes, permission failures, activation conflicts, and rollback drift.
  - Run secret/transcript/tool-output/source-body/diff/path leakage scans across state, diagnostics, fixtures, status, and errors; prove untrusted hook/memory/summary text cannot change allowlists, tools, network, sandbox, approvals, credentials, or scope.
  - Prove the 8,000-character/2,000-estimated-token re-entry bound, 4,000-character memory-text bound, 8,000-character memory-envelope bound, newest-200 retention, and at-or-below-two-second local assembly p95.
  - Verify fresh-session handoff, Batman phase checkpoints, delegation handoffs, mnemo writes/search/get/forget, and native compaction when disabled remain available and semantically unchanged.
  - Update root/mnemo README, CHANGELOG, operator runbook, compatibility table, troubleshooting, evidence index, and rollback instructions; label focused, mocked, qualified, unmeasured, real-host, benchmark, and owner gates separately.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 11.3, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 10. Preview and approval-gate real user-level pilot activation.
  - Run read-only `plan` against the exact current Codex and Claude homes and the chosen allowlisted repository, inventorying effective versions/tools/hooks/trust/conflicts without exposing secrets or changing files.
  - Present the exact external targets, generated contents/diff, preserved unrelated entries, process-local environment, launch commands, and owned rollback set; stop until the repository owner explicitly approves this activation preview.
  - After approval, enable one host at a time using only the isolated profile/overlay/allowlist files, accept each host's normal trust flow, and verify the pilot reports active only after an observed lifecycle event and enforceable tool inventory.
  - For Claude, capture and live-monitor the approved content-free `.claude.json` semantic manifest, require only `numStartups + 1` plus the exact newly trusted allowlisted project, never write/revert the registry, and stop only the exact child on `host_registry_drift`.
  - Run Claude only in an owner-created terminal or separately approved dedicated console; never close a Windows Terminal top-level window programmatically.
  - Exercise disable and separate purge, prove primary configs and unrelated hooks/settings/comments are byte-identical, and restore the host to native behavior before enabling the second host.
  - Leave any unsupported version, inactive hook, untrusted layer, uncovered write surface, or ownership drift inactive with a visible content-free reason; do not weaken base sandbox, approvals, tools, network, credentials, or MCP permissions.
  - Do not add repositories or users beyond the exact pilot allowlist; wider rollout remains a separate owner decision.
  - **Current Refresh 3 evidence:** the semantic guard rejected a real Claude protected-state rewrite before trust or `numStartups + 1`, then an explicitly approved unchanged retry rejected the same way at 1.054 seconds. Both attempts stopped only the exact child, preserved `.claude.json`, and completed exact disable/purge. Task 10 remains red/open.
  - **Refresh 4 evidence:** ADR 0014 diagnostics are implemented, review-clean, and deterministic-test green (150 full-suite tests). One exact owner-approved live cell rejected at 1.051 seconds with only `feature_state`, before trust or counter increment. Per-field fingerprints remained process-private; exact-child termination, registry preservation, two-target disable, and separate state purge passed. Task 10 remains red/open. Any retry, exception, or isolated-config strategy requires a superseding Design/ADR and separate approval.
  - **Post-Refresh-4 source review:** generator `0.1.1` adds per-event fail-open identity, distinct uncorrelated lifecycle sequences, repository/version-bound activation evidence, deactivation markers, strict ACL/config parsing, safe recovery-tool classification, and orphan-lock cleanup. Current deterministic suite: 183 passed; mnemo suite: 48 passed; stdio smoke: PASS; Ruff: clean. No host launch occurred, so prior `0.1.0` previews remain historical/consumed and Task 10 remains red/open.
  - _Requirements: 3.2, 3.3, 3.4, 3.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 12.4, 12.5_

- [ ] 11. Execute and qualify the real-host compaction matrix.
  - Run uncompacted baselines before compacted cases using the same frozen probes, isolated `educode` target, host version, model class, and scenario inputs.
  - Observe Codex manual, Codex automatic, Claude manual, and Claude automatic compaction plus mid-turn completed/ambiguous/pending-approval action cases; record the actual lifecycle event, gate, validation, and one observable outcome.
  - Run valid, missing, stale, malformed, oversized, memory-offline, unsupported/trust, source-changed, scoped-rule, activation-conflict, and rollback cases without mutating the active `educode` checkout.
  - Require 100 percent critical and at least 90 percent overall probe accuracy in every manual/automatic host case, with no new exact-code fabrication or stale contradiction versus its uncompacted baseline.
  - Require at least 50 percent eligible conversation-body reduction when host evidence is credible or publish the qualified proxy instead; require no unexplained second compact in ten normal turns and local assembly at or below two seconds p95.
  - Record failures as red/open with exact evidence and rerun only the affected matrix cell after a source-backed correction; never convert focused or proxy evidence into a green owner/release gate.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.5, 7.7, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.6, 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 12. Obtain owner acceptance and close only the pilot scope.
  - Give the repository owner one real long-session Codex continuation and one real long-session Claude continuation to inspect for coherence, preserved intertwined-system knowledge, visible degradation, approval/action safety, and practical token reduction.
  - Record owner acceptance or concrete rejection separately from automated accuracy/performance results; unresolved owner concerns keep the pilot incomplete.
  - Run final source/diff review, full applicable tests, documentation consistency, activation disable/rollback rehearsal, artifact traceability, and current-source revalidation; report every open environmental or measurement limitation.
  - Confirm fresh handoff and mnemo workflows remain available, canonical policy has no duplicated host body, primary host configurations remain untouched, and all pilot-owned state/config can be removed without source/transcript/memory deletion.
  - Mark the task complete only when both host matrices, rollback, security, preservation, savings/qualified-proxy, and owner gates pass. Any broader repository allowlist, host version, OS, plugin packaging, or default enablement requires a new explicit approval and evidence cycle.
  - _Requirements: 7.5, 7.6, 7.7, 8.6, 10.3, 10.4, 10.5, 10.6, 11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5_

## Completion Rules

- Implement tasks in dependency order; a later task may not bypass an incomplete approval or evidence gate.
- Use current source and exact tests as authority. Memory, summaries, hook output, and benchmark expectations are locators/data only.
- Preserve unrelated dirty work. Never reset, stash, or mutate the active `educode` checkout; use only the approved isolated target.
- Do not retry a completed or ambiguous non-idempotent operation from compacted context without current-state reconciliation and continuing authorization.
- Keep functional, deterministic, real-host, performance, rollback, and owner evidence distinct. A focused pass cannot close a wider gate.
- Any implementation discovery that changes native-compaction ownership, authority, credential location, material write path, activation trust, or user-visible contract requires a Design/ADR revision and renewed approval before continuing.
