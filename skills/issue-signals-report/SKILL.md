---
name: issue-signals-report
description: Generate and explain the AI Watchtower issue-signals report — read the persisted findings (or CloudWatch), group by task instruction type, and for each affected load explain what the flow does, which business rule conflicted, how to fix it, and the signal_id. Use when the user says "issue signals report", "generate the issue signals digest", "explain the issue signals", "why is Robin stopped on load X", "what issue signals fired", "why did SIG-... fire", or wants the issue-signals findings turned into an actionable, Slack-formatted summary. Read-only. FreightHero-aware.
---

# Issue Signals Report

Turn `issue_signals` findings into a grouped, actionable, explained report: per
load — `load_id` + external id, **why** (the business rule that conflicted),
**how to fix**, and the `signal_id`. Read-only; the deliverable is *explained
findings*, not raw events.

Discipline: **scope → fetch → group → explain → report**. The service that
produces these findings is `ai_watchtower/app/services/issue_signals` (WT-1031).

---

## Phase 0 — Prerequisites

- AWS access: profile `freighthero`, region `us-east-1` (`AWS_PROFILE=freighthero`).
- Two sources for findings (prefer the store):
  1. **Findings store (DynamoDB)** — `prd-ai-watchtower-issue-signal-findings`,
     GSI `gsi_by_seen_date` (PK `last_seen_date` = `YYYY-MM-DD` UTC). Deduped by
     `dedupe_key`; carries `signal_id, severity, load_id, external_load_id,
     task_instruction_type, summary, triage_hint, priority_score, actionable_now,
     evidence_json, first_detected_at, last_seen_at, occurrence_count`.
  2. **CloudWatch** — log group `/ecs/prd-issue-signals`, `event_type =
     "issue_signals_finding"` (the historical/raw source; use when you need a
     window the store has TTL'd away — store TTL ≈ 48h).
- rtk gotcha: `aws ... json` is value-elided to schema shape; for real values run
  `AWS_PROFILE=freighthero rtk proxy aws ...` (`rtk proxy` before the `aws` binary).

---

## Phase 1 — Scope

Pin down: which **day** (default today UTC), **actionable-only** (default yes —
exclude the noise signals below), and optionally a single `load_id` or `signal_id`.

---

## Phase 2 — Fetch

Store (preferred), one day:
```bash
AWS_PROFILE=freighthero rtk proxy aws dynamodb query \
  --table-name prd-ai-watchtower-issue-signal-findings \
  --index-name gsi_by_seen_date \
  --key-condition-expression "last_seen_date = :d" \
  --expression-attribute-values '{":d":{"S":"2026-06-25"}}' \
  --scan-index-forward false
```
CloudWatch fallback (Logs Insights on `/ecs/prd-issue-signals`):
```
fields @timestamp, @message
| parse @message 'Event: *' as raw
| filter @message like /issue_signals_finding/
| fields jsonParse(raw) as ev
| filter ev.event_type = "issue_signals_finding"
| filter ev.details.evidence.actionable_now = 1 or ev.details.evidence.actionable_now = true
| stats count(*) as n by ev.details.signal_id as signal_id, ev.details.task_instruction_type as tit, ev.details.severity as severity
| sort n desc
```

Drop the **noise signals** from the actionable report (kept in the store for
history): `SIG-WF-004` (recovered), `SIG-WF-005` (postmortem), `SIG-WF-006`
(ambiguous).

---

## Phase 3 — Group

Group by `task_instruction_type` (null → "load-level"). Within each group sort by
`priority_score` desc. Cap loads-per-group (top ~15) with a "+N more" line — the
automated Slack digest (`app/workers/issue_signals_digest.py`) does the same to
stay under Slack's 50-block / 3000-char-per-section limits.

---

## Phase 4 — Explain (what the flow does + which rule conflicted)

For each finding, state: (a) what the underlying flow is supposed to do, (b) the
business rule the finding asserts was violated, (c) the fix (`triage_hint` is the
starting point; enrich from the catalog). Cite the evaluator.

Signal catalog (`base_by_signal` in `app/services/issue_signals/models.py`;
evaluators in `app/services/issue_signals/evaluators/`):

| signal_id | flow / rule that conflicted | fix direction | evaluator |
|---|---|---|---|
| SIG-ETA-001 | An open ETA-checkpoint task must have its `tracking-checkpoint-{p\|d}-{load}` + `eta-note-{p\|d}-{load}` EventBridge schedules | recreate the missing schedule(s); the on-route→delivery transition may not have scheduled the task | `eta_missing_schedules.py` |
| SIG-ETA-002 | Tracking pings entered disambiguation but never found an active task / stored metadata | investigate tracking disambiguation routing for the load | `eta_disambiguation_starvation.py` |
| SIG-ETA-003 | An open ETA task is receiving tracking processing but no metadata is being stored | check why tracking isn't routed to the task | `eta_open_task_starvation.py` |
| SIG-ETA-004 | A scheduled routine (tracking-checkpoint / hourly eta-note) hasn't run within its heartbeat window | check EventBridge schedule state + the routine worker | `eta_heartbeat_gap.py` |
| SIG-ETA-005 | A soft-reset replacement ETA task was interrupted while PENDING with no recovery (rare) | recreate the replacement monitoring | `eta_interrupt_replacement_loss.py` |
| SIG-RME-001 | Expected morning-ETA `rme-{load}-{yyyymmdd}` schedules are missing for an eligible load | reconcile/recreate; confirm the load is still morning-ETA eligible (signal went quiet 2026-06-12 when scheduling became reliable) | `morning_eta_missing_schedules.py` |
| SIG-WF-001 | Milestone advanced but no active expected task exists ("Robin stopped") | create/dispatch the expected task for the milestone | `workflow_task_milestone_drift.py` |
| SIG-WF-002 | Milestone facts/floor disagree with transition history (regression/conflict) | reconcile milestone state vs facts | `workflow_task_milestone_drift.py` |
| SIG-WF-003 | Task-state desync after a recovery pause failure (rare) | inspect the pause-failure + recovery path | `workflow_task_milestone_drift.py` |
| SIG-REC-001 | Backend authoritative state (read-details) disagrees with the agentic task state: missing expected task / agent behind / orphan task after completion / snapshot divergence | create the missing task (or file a backend ticket for the transition-creation gap); close orphan tasks; check milestone-sync | `backend_task_reconciliation.py` |

For root-causing a specific load, cross-reference the finding's `evidence_json`
(e.g. `missing_schedules`, `backend_milestone_state` vs `snapshot_milestone_state`)
and `mcp__freighthero-codebase__search_codebase`/`explain_code` on the cited evaluator.

### Known false-positive classes (validity audit 2026-07-01: 8/13 findings FP)

Caveat findings matching these patterns before reporting them as actionable:

1. **SIG-WF-001 successor-blindness** (worst offender): workflow legitimately runs
   AHEAD of a lagging milestone — arrival handoff completes `*_eta_checkpoint` and
   activates `confirm_pickup`/`confirm_delivery` while `milestone_state` still reads
   the prior leg. The finding's own `evidence_json.open_tasks_snapshot` shows the
   ACTIVE successor → not a stall. Check `open_tasks_snapshot` for an active
   later-context task first; distrust `no_active_*` timestamps older than the latest
   task handoff.
2. **SIG-WF-002 multi-stop blindness**: floor logic assumes a linear 2-stop ladder;
   a legit TMS multi-stop cycle (at-delivery → at-pickup for stop 2 of a 4-stop
   load) reads as regression. Check the load's stop count first.
3. **SIG-ETA-004 fire-race**: suppression covers only strictly-future triggers and
   the breach threshold equals the cadence, so a detector run seconds after an
   `at()` schedule fires flags normal EventBridge delivery latency. Confirm the
   routine actually ran near the trigger (`routine_tracking_checkpoint_received`
   in `/ecs/prd-ai-watchtower`) before reporting.

True-positive signature for SIG-WF-001: backend dispatch logs
(`prd-console-start-load-task-queue-process-message`, message
`load_task_dispatch_outcome`) show `skipped_competing_active_task` /
`roundtrip_human_task` at the milestone transition and no later `submitted` —
the human-close path never re-dispatches (WT-1171 family). Also verified real:
SIG-ETA-001 after a backend re-dispatch replaces the ETA task and the recreated
`eta-note-d-*` schedule fires into `hourly_eta_tms_note_no_metadata`
(`should_reschedule=False` consumes the schedule; hourly TMS notes die).

---

## Phase 5 — Report

Slack-formatted (mrkdwn), grouped by task instruction type. Per load:
`` `load_id` (external_id) — <why> _<signal_id>_ `` then `↳ fix: <how>`. Header
with total actionable count + a per-signal counts footer. For 4+ groups or large
output, prefer the `visual-explainer` skill for a browser-rendered table.

---

## Guardrails

- **Read-only.** No mutation. Recreating schedules / replaying dead schedulers is
  a separate, explicit ops action (`scripts/ops/replay_scheduler_ingress_failures.py`,
  `scripts/ops/issue_signals_task_deploy.py run-once`) — propose, don't auto-run.
- **No invented findings.** Every line traces to a stored finding or a
  CloudWatch `issue_signals_finding` event. A zero-finding day is a valid result
  (check `issue_signals_morning_eta_coverage` / actionable counts to confirm
  healthy-zero vs no-data).
- **Exclude noise** (SIG-WF-004/005/006) from the actionable report.
- PII: load identifiers only.
