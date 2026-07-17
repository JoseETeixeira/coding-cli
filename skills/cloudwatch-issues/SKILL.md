---
name: cloudwatch-issues
description: Read CloudWatch Logs and derive a ranked list of issues (errors, exceptions, spikes, latency, anomalies) into a structured report. Use when the user says "check cloudwatch", "what's breaking in prod", "pull the logs", "find errors in <service>", "triage cloudwatch", asks why a Lambda/ECS service/API is failing, or wants log-derived issues turned into tickets. Works on any AWS account.
---

# CloudWatch Issues

Turn raw CloudWatch Logs into a ranked, deduplicated, root-caused issue list.
Read-only by default. The output is a structured report; filing tickets is an
explicit opt-in last step.

The discipline: **scope → fetch → cluster → rank → root-cause → report**. Never
hand back a wall of log lines — the deliverable is *issues*, not events.

---

## Phase 0 — Prerequisites

- AWS access. Use the project's AWS profile and region, e.g.
  `AWS_PROFILE=<profile> AWS_REGION=<region>`. Some ops scripts instead load
  creds from a project `.env`.
- `aws` CLI or `boto3`. CloudWatch **Logs Insights** is the primary tool;
  `filter_log_events` is the fallback when you need raw streamed lines.
- rtk gotcha: `aws ... json` output is value-elided to schema shape by the
  rtk filter. When you need real values, run `AWS_PROFILE=... rtk proxy aws ...`
  (`rtk proxy` BEFORE the `aws` binary, after env-var assignments).

---

## Phase 1 — Scope (always ask/confirm before pulling)

Pin down four things. Guess sensibly and state the guess if the user is terse.

1. **Log group(s).** Typical AWS conventions (`<stage>` ∈ `dev`, `prd`, or a branch env):
   - ECS app + workers: `/ecs/<stage>-<service>` (stream prefixes vary by service)
   - Lambda: `/aws/lambda/<stage>-<function>`
   - API Gateway: `/aws/apigateway/<stage>-<api>-http-api`
   - ElastiCache Redis: `/aws/elasticache/redis/<cluster>/{slow,engine}-log`
   - Discover what exists: `aws logs describe-log-groups --log-group-name-prefix /ecs/<stage>`
2. **Time window.** Default last 3h for "what's breaking now", last 24–72h for
   trend/triage. Express as epoch-ms for the SDK.
3. **Stage / environment.** `prd` unless told otherwise. Never assume branch envs.
4. **Signal of interest.** Errors+exceptions (default), latency, throttling,
   OOM/restarts, a specific string, or "anything anomalous".

---

## Phase 2 — Fetch

Prefer **Logs Insights** — it aggregates server-side, so you derive issues
without dragging every line back. Start broad, then drill.

Triage query (error signatures, most frequent first):

```bash
AWS_PROFILE=<profile> AWS_REGION=<region> aws logs start-query \
  --log-group-name "/ecs/<stage>-<service>" \
  --start-time $(($(date +%s) - 10800)) --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message
    | filter @message like /(?i)(error|exception|traceback|critical|fatal|timeout)/
    | stats count(*) as hits by errorClass
    | sort hits desc | limit 50'
# then: aws logs get-query-results --query-id <id>
```

Useful drill queries:
- **Spike detection**: `stats count(*) by bin(5m)` — find the time bucket where
  volume jumps, then re-query that window only.
- **Latency** (API GW / app): `filter status >= 500 | stats count(*), avg(latency), max(latency) by routeKey`.
- **Exact trace bodies**: once you know the signature, `filter @message like /<signature>/ | sort @timestamp asc | limit 100`.

Raw-line fallback (when Insights isn't enough): `boto3.client("logs")` +
`filter_log_events` with `interleaved=True`, paginating on `nextToken`.

Cost/courtesy: scope the time window tightly, `limit` every query, sleep ~0.2s
between paginated calls. Insights scans are billed by bytes — don't run a 30-day
scan to answer a "last hour" question.

---

## Phase 3 — Derive issues (the actual skill)

Raw events → issues. For each distinct problem:

1. **Cluster** by normalized signature, not literal text. Strip volatile tokens
   (UUIDs, entity ids, timestamps, request ids, hex addresses) so
   `job 7f3a… failed` and `job 9b21… failed` collapse to one issue.
2. **Count + window** each cluster: occurrences, first-seen, last-seen, whether
   it is ongoing or a closed burst, and rate (per min/hour).
3. **Classify severity**: ongoing 5xx / crash-loop / data-loss > intermittent
   error > warning/noise. A single ERROR that fires 4000×/h outranks a scary-
   looking one-off.
4. **Extract the smallest diagnostic core** per cluster: the exception type, the
   top app frame of the traceback, the failing route/task, the correlated
   stream prefix (which worker/color).
5. **Drop noise**: known-benign warnings, retries that later succeed, health-
   check chatter. Say what you filtered so nothing is silently dropped.

---

## Phase 4 — Root-cause against the codebase

For each ranked issue, before reporting, tie the log signature to code:

- Grep the codebase for the exception class, log-message literal, or failing
  function, then read the exact source for evidence.
- Note the suspected owning module and a one-line hypothesis. Mark confidence
  (confirmed-from-code vs inferred-from-message). Do not assert a root cause you
  could not trace to a file.

---

## Phase 5 — Report

Deliver a ranked table, highest-severity first. Per issue:

| Field | Content |
|---|---|
| Title | one line, the normalized signature |
| Severity | critical / high / medium / low + why |
| Count / window | `4,213 hits, 02:10–now (ongoing)` |
| Signature | exception type + top app frame |
| Source | log group + stream prefix |
| Suspected cause | file:line + one-line hypothesis + confidence |
| Sample | one representative (PII-redacted) line |

Lead with a 2–3 line summary: how many distinct issues, how many critical,
whether anything is actively ongoing. For 4+ issues, prefer the `visual-explainer`
skill to render the report instead of a raw markdown table.

**PII**: redact entity-specific PII, tokens, secrets, emails, phone numbers,
addresses in every sample line (`[entity_id]`, `[email]`, `[token]`).

---

## Phase 6 — File tickets (opt-in only)

Only when the user explicitly asks to file/track. Then, per the GitHub-first and
memory rules: use the `github` MCP tools (`create_issue`) or Notion
(`notion-create-pages`); title = the normalized signature; body = severity,
count/window, source, suspected file:line, redacted sample. Link back issues that
share a root cause instead of filing duplicates. Never auto-file without the ask.

---

## Guardrails

- **Read-only.** This skill reads logs and codebase; it never mutates AWS,
  deploys, or changes log config. Filing a ticket (Phase 6) is the only write,
  and only on explicit request.
- **No invented issues.** Every reported issue traces to actual log events you
  pulled; every root cause traces to a file or is marked inferred.
- **Scope the spend.** Tight windows, `limit` on every query, narrowest log
  group that answers the question.
- **Surface what you filtered.** Dropped noise and capped result sets are stated,
  never silent — a truncated scan reads as "complete" when it isn't.
- **Stage safety.** Default to `prd` only when the user means production; never
  assume a branch env. Confirm the stage when ambiguous.
