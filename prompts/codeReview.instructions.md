# Code Review Instructions

Guidelines distilled from recurring feedback patterns across **440+ closed pull requests** in the Freight-Hero backend repository plus closed `ai_watchtower` PR/issue/review history. Primary backend reviewer: **sbalmt**. AI Watchtower Python and agent-workflow patterns emphasize recurring guidance from **arthurmf** and related closed PR review notes.

---

## 1. Repository & Data Access Patterns

- Never perform database operations directly in endpoint handlers. Always use a `Repository` namespace.
- Prefer `upsertOne` over read-then-insert/update patterns to avoid race conditions and reduce queries.
- Trust the data model: one-to-one relations return objects, not arrays — never check `Array.isArray()` on them.
- If a related record (e.g. `broker_details`) is guaranteed to exist at entity creation time, assume it exists — don't add defensive null/existence checks.
- Avoid N+1 queries inside loops. Use batch operations or retrieve data in bulk before iterating.

```ts
// Bad — inline DB call in handler
const details = await database.broker_details.findOne({ where: { company_id } });
await database.broker_details.updateOne({ data, where: { company_id } });

// Good — use a repository
await BrokerRepository.updateDetails(companyId, data);

// Bad — read then conditionally insert/update
const existing = await database.table.findOne({ where: { id } });
if (existing) {
  await database.table.updateOne({ data, where: { id } });
} else {
  await database.table.insertOne({ data });
}

// Good — upsert
await database.table.upsertOne({
  insert: { ...data },
  update: { ...data },
  where: { id }
});
```

---

## 2. Type System Conventions

- Let TypeScript infer return types unless strictly necessary (recursive functions, `JSON.parse`, or API response contracts).
- Never use `any`. Pass proper types, use `Pick<>`, extend existing types, or use `unknown` with narrowing.
- Shared types belong in common locations — don't duplicate locally.
- Prefer simple `type` declarations over `interface`/`class` unless EZ4 requires it.
- For queue message types, export a client type alias: `export type StartLoadTaskClient = StartLoadTaskQueue['client']`.

```ts
// Bad — unnecessary return type
const getUser = (): UserType => {
  return { name: 'foo' };
};

// Good — let inference work
const getUser = () => {
  return { name: 'foo' };
};

// Bad — any usage
const processData = (data: any) => { ... };

// Good — proper types
const processData = (data: Pick<EmailStorageMessage, 'provider' | 'integrationId'>) => { ... };
```

---

## 3. Null vs Undefined

- The entire project relies on `undefined`, not `null`. Never coalesce to `null`.
- To disconnect a relationship in EZ4/database operations, use `{ relation: { id: null } }` — but in application code prefer `undefined`.
- If a property can be absent, make it optional (`property?: Type`) instead of allowing `null`.
- Undefined values are automatically skipped by insert/update operations — don't add conditional spreads for optional fields.

```ts
// Bad — unnecessary conditional spreads
data: {
  ...(field !== undefined && { field }),
  ...(otherField !== undefined && { otherField })
}

// Good — trust the framework
data: {
  field,
  otherField
}
```

---

## 4. Error Handling

- Always throw errors instead of logging them (except in queue handlers where retries are undesirable).
- Never use `console.log` — use `Logger` for any log output.
- For HTTP endpoints, throw `HttpError` or its subclasses. For internal services, map errors via `httpErrors` in route config.
- Never use `.catch()` on promises — use `try/catch` blocks.
- If a fire-and-forget async call can fail silently, explicitly handle its errors or document the decision.

```ts
// Bad — .catch() on promise
const data = await BrokerService.tryGetBrokerData(id).catch(() => undefined);

// Good — try/catch
let data;
try {
  data = await BrokerService.tryGetBrokerData(id);
} catch (error) {
  Logger.warn('Failed to fetch broker data', { error });
}
```

---

## 5. API Response Contracts

- Never expose internal or external IDs to the frontend. Use communication IDs or public identifiers.
- Only return properties the frontend actually needs — question every field.
- If a value can be absent, make the property optional in the response schema rather than returning `null`.
- Use `camelCase` for all non-webhook request/response properties (enforced via `NamingStyle.SnakeCase` API preference).
- Third-party webhook endpoints must use `NamingStyle.Preserve`.

```ts
// Bad — coalescing to null
{ threadId: record.thread_id ?? null }

// Good — optional property
{ ...(record.thread_id && { threadId: record.thread_id }) }
// Or make it optional in the response type
```

---

## 6. Service Boundaries & Responsibility

- Delegate features to the correct service package. Slack data management belongs in `communication`, not `console`.
- Don't import common service definitions into packages that should be calling the API instead.
- If a function exists in a util or service (e.g. `formatName`, `createUniqueIdentity`, `getEmailDomains`), use it — don't reimplement the logic.
- Centralize shared transformations. If create and update parse the same way, consolidate into one function.
- Keep inbound-resolution paths isolated by channel. `findMatchingByChat` (Slack) and `findFromMessage` (email/SMS) have different invariants — Slack always knows the broker via the integration, email/SMS is blind and relies on contact/domain heuristics. A change to one should not also touch the other; email/SMS resolution is sensitive enough that any incidental edit risks altering routing, matching, and Robin's downstream behavior. If a fix appears to require both, split it into two PRs (Freight-Hero/backend#627 sbalmt review).

```ts
// Bad — reimplementing name formatting
const name = `${firstName} ${lastName}`.trim();

// Good — use existing utils
const name = formatName(firstName, lastName);
const id = createUniqueIdentity(brokerCompanyId, externalId);
```

---

## 7. Framework Conventions (EZ4)

- Use `request.data` to access raw body data (not `request.body`).
- Use `Http.Incoming<RequestType>` to expand request properties.
- Specify only success status codes in response definitions — any other should be an HTTP exception.
- For webhook request types, use `Object.Extends<{ ...only properties in use }>` to keep types minimal.
- Don't cast database records manually — the ORM handles typing.
- When setting API preferences for naming style, trust `NamingStyle.SnakeCase` to handle the conversion.
- **Handler JSDoc becomes the AWS Lambda function `description`, which is capped at 256 characters.** SST/CDK reads the leading `/** … */` block above each exported handler (`apiXxxHandler`, `internalXxxHandler`, etc.) and sends it as the Lambda's `description` property. Exceeding 256 chars fails prd deploy with `Value '<long text>' at 'description' failed to satisfy constraint: Member must have length less than or equal to 256`, and the failure cascades into "Dependency X linked to entry Y does not exist" errors on every downstream API Gateway / route / permission resource that depended on the Lambda. Keep the JSDoc one short line; put any longer rationale in a regular `//` comment below the function signature, or in a sibling design doc (Freight-Hero/backend prd deploy 2026-05-19).

---

## 8. Code Hygiene

- Remove all `console.log` and debug statements before PR submission.
- Remove test/debug endpoints or protect them with feature flags before merging.
- Don't log sensitive data (URLs, tokens, signatures, secrets).
- Don't add comments that describe what the code obviously does — only use comments for non-obvious decisions. Do not add comments that merely restate relevance or reference a task/ticket (WT-XXX, JIRA-XXX, PR number, "for the X feature") — they go stale when the work merges and the ticket archives, leaving noise. Keep code task-agnostic (user direction 2026-06-15).
- Avoid redundant error handling where both branches produce the same result.
- Don't create helper functions for simple property access — every abstraction must justify its existence.
- The backend repo does not maintain a `CHANGELOG.md`. Do not add one or update one as part of a PR — the commit log is the source of truth (Freight-Hero/backend#627 sbalmt review).
- When looking up N candidate values against the same indexed column (e.g. `external_id` from extracted load tokens), prefer one query with `WHERE col IN [...]` over N point lookups. The bulk-IN form is bounded by the candidate set size, the query planner indexes it natively, and the resulting service code stays single-roundtrip (Freight-Hero/backend#627 sbalmt review).

---

## 9. Queue & Async Patterns

- When separating concerns into queues (e.g. stop, restart, start), pass all necessary context in the queue message so the handler is self-contained.
- For restart flows, ensure the agent/prerequisites are ready before triggering the task start.
- Send reason text in queue messages so downstream handlers can use it without re-fetching.
- Use `noSuppress: true` parameter patterns over boolean flags for clarity.

---

## 10. Redundant Query Prevention

- Don't fetch the same entity twice in the same handler. If it's loaded above, reuse it.
- If a relationship was loaded with the parent query, use the included data — don't re-query.
- When integration data is needed, fetch it once and pass it through.

```ts
// Bad — fetching integration twice
const integration = await IntegrationRepository.findOne({ where: { id } });
// ... 20 lines later ...
const sameIntegration = await IntegrationRepository.findOne({ where: { id } });

// Good — reuse the first fetch
const integration = await IntegrationRepository.findOne({ where: { id } });
// ... use `integration` throughout
```

---

## 11. Naming & File Conventions

- Use `kebab-case` for file names and folder names.
- Use `snake_case` for database schema properties and table names.
- Use `PascalCase` for namespaces, types, interfaces, enums.
- Use `camelCase` for functions, methods, and properties.
- Name queue files and classes descriptively: `email-files.ts` → `EmailFilesQueue`, not `file-database-email.ts`.
- Function names should accurately describe behavior — `findChatContactsByLoad` should only find contacts, not also format them.

---

## 12. Testing Expectations

- Ensure test assertions match actual implementation behavior (e.g., don't expect 404 when the implementation returns 200 with empty array).
- Test the actual behavior, not just that a value is passed through.
- Document new API fields via JSDoc or OpenAPI schema updates alongside the implementation.
- Add or update tests for new status/state combinations.

---

## 13. AI Watchtower Python Security & Input Boundaries

- Treat caller-controlled identifiers used in paths as untrusted. Validate slugs with a strict allowlist before path construction, then verify the resolved path stays inside the intended root.
- When raw business names are accepted, reject traversal tokens before normalization, then normalize through the project helper or explicit alias/lowercase/kebab-case flow.
- Parse YAML/frontmatter defensively. Validate the parsed value is a mapping before reading fields, and validate required text fields are strings before using them.
- Fail fast on unknown workflow variants, model route modes, provider types, skill mappings, or sub-agent mappings. Raise a clear `ValueError` instead of silently falling back or allowing a later `FileNotFoundError`.
- Prefer explicit default profiles only where the product contract supports a default, such as a default broker profile. Do not use broad fallback behavior to hide invalid configuration.
- For cross-load or cross-context data, scope reads and writes by the current load/task/message identifiers only. Never let cached or historical context from another load influence the current workflow.
- Treat missing or empty critical payload fields (e.g. timer `motivation`, classifier `selected_*`) as equivalent to unknown variants. Fail fast with `ValueError`, never silent-fallback to free-form classification — the model can pick arbitrary intents and fire outbound actions.

```py
# Bad: validated by convention only
path = SKILLS_ROOT / workflow / broker / f"{skill_id}.md"

# Good: validate input and resolved path
skill_slug = validate_slug(skill_id, "skill_id")
path = assert_within(SKILLS_ROOT / workflow / broker / f"{skill_slug}.md", SKILLS_ROOT, "skill")
```

---

## 14. AI Watchtower Agent & Workflow Guardrails

- Preserve source-of-truth boundaries. Agent gates should not write directly to TMS-owned milestone state; route through the existing transition service/backend contract.
- Keep milestone transitions forward-only unless an explicit rollback/reset workflow is being implemented and reviewed as architecture work.
- Ambiguous agent classifications should not trigger direct driver outreach or milestone transitions. Route ambiguity through the existing inbound/broker escalation path.
- Use closed vocabularies for model outputs such as flags, tiers, signal types, route modes, and classifications. Prefer `Literal`, enums, or constrained Pydantic fields over open strings.
- Keep hard-flag sets and model output vocabularies synchronized with type-level or import-time assertions so new labels cannot drift silently.
- Shadow-mode logs must reflect live-equivalent behavior. Fields such as `would_have_transitioned`, overrides, routing, and escalation decisions should match what live mode would have done.
- Rollout-mode changes need explicit guardrails: shadow/live parity, rollback path, log visibility, and a documented go/no-go decision.
- Trusted-system or tool-originated events are not automatically trusted. Require stable provenance metadata before allowing them to drive live transitions.
- Tool config and prompt content must stay aligned. Removing a tool from a workflow's tool list requires scrubbing every prompt that instructs the agent to call it (system prompts, skill bodies, factory wrappers). Mismatch produces invalid tool-call attempts instead of the intended behavior.
- **Broker-originated load events do not enter via the inbound-message channel.** They flow through the backend TMS notify-event path (`backend/packages/console/src/loads/endpoints/internal/notify-event.ts` → `LoadEventType` → realtime queues). The blanket "if sender type is broker, ignore the message" guardrail in inbound agents (`confirm_pickup`, `confirm_delivery`, `pickup_eta_checkpoint`, `delivery_eta_checkpoint`, `initiate_tracking` communication agents) is deliberate cross-agent policy backed by `inbound_broker_message_ignored` tool-only scenarios. Do not narrow or remove it from a single agent — if policy changes, file a separate ticket that touches all five agents together and co-decides the cancellation entry path with backend (PR #1358 codex-decline).
- **Tracking thread_ids must scope by task/stop UUID, not by `{load_id}_<direction>`.** The tracking data graph uses `task_uuid` (each lifecycle phase = unique task = isolated state); the tracking checkpoint routine uses `stop_uuid`. Direction-only scoping leaks geofence state (ping counts, timestamps) between stops on NPND multipick/multidrop loads. Skip graph execution entirely when no active task and log a warning (PR #1359, commit `4728309e`).
- **Cross-provider conversation history requires sanitization at the provider-translation layer.** When Bedrock falls back to OpenAI Responses or OpenRouter and later retries Bedrock, OpenAI-shaped `function_call` / `custom_tool_call` blocks can carry tool names outside Bedrock Converse's `[a-zA-Z0-9_-]+` regex (hallucinations such as `multi_tool_use.parallel`). The translator (`_normalize_openai_responses_content_block_for_bedrock` in `app/services/llm/providers/bedrock.py`) must sanitize `name` before emitting the `tool_use` envelope — replace invalid chars with `_`, truncate to 64, fall back to `invalid_tool_name`, and emit a `bedrock_tool_name_sanitized` WARNING. Tool-call ↔ tool-result matching is keyed on `id`/`toolUseId` not `name`, so substitution preserves call/result topology (Sentry AI-WATCHTOWER-Q, PR #1358 commit `309c85ba`).
- **Robin GPT retrieval methods must return `ToolEnvelope(status="partial", …)` on WT BE failures, not propagate exceptions.** Every method in `robin-gpt/app/retrieval.py` that calls the WT BE HTTP client (`get_live_tracking`, `get_tracking_history`, `get_state_transitions`, etc.) must wrap the call in `try/except` for `httpx.HTTPStatusError` (404 typical during staggered deploys before paired backend PRs ship; other status codes during transient failures) plus `httpx.RequestError` / `RuntimeError` (transport-level failures). Each branch returns a partial envelope with an explanatory `message`, a `wt_be.<source>` provenance entry, and `warnings=[…]`. Raw exceptions from `raise_for_status()` will kill the agent's response instead of degrading gracefully (Freight-Hero/ai_watchtower#1372 codex P1).
- **SYSTEM_PROMPT ↔ agent tool list must stay aligned in both directions.** The existing "removing a tool requires scrubbing the prompt" rule applies in reverse too: when a prompt clause instructs the agent to call `<tool_name>` for an analytical / retrieval path, the corresponding `RobinAgentRunner._build_agent` (or equivalent factory) must register a matching `@tool` and add it to the `tools` list. A prompt mention with no registered tool is dead text — the model reads the instruction and has nothing to invoke (Freight-Hero/ai_watchtower#1372 codex P1).
- **Use `force_refresh=True` when reading lifecycle-state from a cached snapshot inside a close-out-sensitive code path.** Helpers that read `load_summary.is_terminal_status` to gate fallback behavior (`_synthesize_tracking_from_timeline`, terminal-load 422 grace, etc.) must bypass the snapshot cache; otherwise a snapshot cached just before the load flipped to Concluded / Canceled stays for `ROBIN_GPT_SNAPSHOT_TTL_SECONDS` (default 120s) and masks the transition exactly when the fallback is needed most (Freight-Hero/ai_watchtower#1372 codex P2).
- **Deterministic-mode answer formatters that report load state must honor `is_terminal_status`.** When `orchestrator._render_answer` adds a new focus branch that reports driver location, trailer state, milestone, ETA, etc., the branch must check `load_summary.is_terminal_status` and emit past-tense wording for terminal loads (`"At the time the load reached its final status, the driver was on site at the shipper (OSS)"` not `"Driver is currently on site at the shipper (OSS)"`). The SYSTEM_PROMPT terminal-load clause sets the tone for the agent path; deterministic mode must match it (Freight-Hero/ai_watchtower#1372 codex P2).
- **Treat `ToolEnvelope.status="partial"` as untrustworthy for downstream signal extraction.** When a helper reads a time-sensitive field (e.g. `milestoneState`) from a tool envelope to gate behavior, it must check `envelope.status == "ok"` before preferring the envelope's value over a more authoritative source. `_resolve_active_milestone` originally always preferred `get_live_tracking.milestoneState`, but a stale ping (`at-pickup`) could override a progressed `load_summary.milestone_state` (`on-route-to-delivery`). The producer side already marks staleness via `status` — the consumer side must honor it before using the value (Freight-Hero/ai_watchtower#1372 codex P1 round 4).
- **Operator-shorthand planner routing must precede generic intent heuristics.** When SYSTEM_PROMPT defines a vocabulary the LLM is trained to recognize (`OSS` / `OSR` / `MT` / `GFOTD` / `GFOTP`, or any future operator shorthand), `_build_plan` must check that vocabulary BEFORE generic `summary_focus`-style token heuristics. Realistic broker phrasing pairs shorthand with common summary tokens (`"OSR status?"`, `"GFOTD?"`, `"MT now?"`) and the generic `status` / `origin` / `destination` tokens would otherwise steal the plan into a generic snapshot summary, defeating the keyword-specific handler. Stronger intents (reasoning, eta-context, tracking, transition, responsibility, communication) still take precedence — they return earlier in the plan-building flow (Freight-Hero/ai_watchtower#1372 codex P2 round 4).
- **EventBridge Scheduler listings must paginate — use `list_all_schedules_for_group`, never a raw first-page `list_schedules`.** AWS returns max 100 schedules per page; production groups exceed it. A consumer that derives state from the listing (e.g. Robin status `scheduled` vs `idle`) silently produces wrong answers for every schedule past page 1. The repo helper `app/services/aws/eventbridge_service.py::list_all_schedules_for_group` already wraps the paginator (ai_watchtower PR #1432 codex P1).
- **Terminal-site emits must cover EVERY early return, including pre-run guards.** When adding a "publish on completion" hook to a worker (status stream, metrics, callbacks), enumerate all `return` paths in the function — not just the post-execution branches. Pre-run guards (`take_over` before graph start, idempotency skips) are terminal outcomes too; missing them leaves downstream state stale exactly when an operator intervened (ai_watchtower PR #1432 codex P2).
- **Cross-service queue payloads: omit absent optional fields, never send explicit `null`.** ez4 queue consumers validate incoming messages against the declared schema (`@ez4/validator` via `getJsonMessage` → `MalformedMessageError` → message rejected). A TS-optional field (`taskId?: string`) is optional-NOT-nullable, so an explicit JSON `null` fails validation even though the field may be missing. When a WT publisher builds a payload for a backend ez4 queue, build the dict conditionally (`if value: payload["key"] = value`) for every `?:` field; keep explicit `null` only for fields the schema types as `| null` (e.g. `detail: RobinStatusDetail | null`, `locationContext?: RouteDirection | null`). Check the consumer's message type in `backend/packages/**/queues/*.ts` before settling the payload shape (WT-999 review, ai_watchtower PR #1432: emit payload sent `taskId: None` + `detail.type/fireAt: None`).

---

## 15. AI Watchtower Testing Expectations

- Pick the regression layer that matches the bug. Use LocalStack-backed integration tests for DynamoDB/persistence behavior; use deterministic unit tests for pure routing and graph-node logic; use gated real-LLM scenario tests for prompt behavior.
- Test behavior, not implementation details. Persistence tests should assert stored rows and branch outcomes, not only mocked expression strings. Refactor tests should assert public behavior, not module paths.
- For prompt-touching changes, treat the scenario suite as the behavioral contract. Run the gated scenario suite with retries/repetition when available, and treat repeated failures as real regressions rather than flakiness.
- Include positive and negative fixtures for operational guardrails: stale vs fresh tracking, wrong-leg geography, bare attachments, broker questions, load cancellation, trusted-system events, and direction scoping.
- Add production-case replay fixtures when a change fixes a production failure. Redact sensitive details, but preserve the semantic shape that caused the bug.
- For rollout or gate changes, add non-regression matrices covering every existing transition source and assert unchanged paths remain unchanged.
- When an integration path failed in dev/prd, add at least one runtime integration test that exercises the real path, not only isolated helper logic.
- Tool-only scenario suites are the primary behavioral merge gate. Live-LLM judge runners are deprecated (skip-shim pattern from `confirm_pickup` / `confirm_delivery` / `initiate_tracking`); new workflow migrations port behavioral tests to `tool_only/` registries with deterministic expectations.
- **Scenario suites are live-LLM tests — run them, don't just collect.** They call real models (secrets injected via Doppler, not a `.env`) and assert deterministic tool-call expectations. When a change touches a skill body (`app/skills/**`) OR a routine/agent factory or its middleware that executes skills (e.g. `app/graphs/routines/**`, `app/graphs/<workflow>/**_agent.py`), run ALL relevant tool-only scenario suites for the affected workflows via `doppler run -c dev -- env AWS_PROFILE=freighthero uv run pytest <suite>/tool_only/test_scenarios.py -n <N> -q` — not just unit + pyright. Unit-green is necessary but not sufficient for a skill/agent-behavior change (user direction 2026-06-15).
- Robot framework is NOT a validated merge gate. Robot regex on UI-rendered state-field artifacts is brittle and breaks on state-field renames even when agent behavior is unchanged (see PR #1357 — `selected_skill` state-field rename broke the `unresponsive` regex). Use Robot as supplementary evidence only.
- When restructuring a shared intent body across multiple workflows, prove "content moved, not added" with pre/post tool-only pass-rate delta = 0pp on every neighboring workflow that composes the intent.
- **Bump `pyproject.toml` + `uv.lock` version on every ai_watchtower agent change before the PR is ready.** Bump both together (e.g. `4.7.6` → `4.7.7`). For `uv.lock`, edit ONLY the `version = "..."` line under the `[[package]] name = "ai-watchtower"` block — do NOT run `uv lock` to regenerate: a newer local uv (0.11.x) rewrites `revision` (`2` → `3`) and reformats `requires-python` (`>=3.12.0, <3.13` → `==3.12.*`), producing churn unrelated to the bump. Project convention is a 1-line lock diff (see commit `fe3fc4c4`). If a prior session left a regenerated lock in the working tree, `git checkout uv.lock` then hand-edit the version line (user direction 2026-06-16).

---

## 16. AI Watchtower Observability & Operations

- Keep existing log event names stable where dashboards or manual runbooks depend on them.
- Add structured log payloads for routing decisions, overrides, shadow/live mode, classification outputs, and failure fallbacks. Avoid sensitive data in logs.
- When adding fallback/retry behavior, bound retries, prevent fallback loops, and emit observable events for the fallback trigger and selected provider/model.
- Document operational validation for high-risk changes: deploy target, log query, expected event shape, rollback toggle, and manual checks against affected state.
- **Do not apply prod Doppler / feature-flag / env-config changes yourself during feature or migration work — ship a safe code default and record the required prod change as a merge-time deploy action.** When a change needs a prod env/Doppler/rollout-flag flip to preserve or activate behavior (e.g. a rollout-mode default change), the agent ships the code with a behavior-preserving default and writes the exact Doppler/env action (project, config, key, value) into BOTH the PR body and the epic→main merge checklist for a human to apply at deploy time. Do not run the Doppler/env mutation. (This is narrower than the prod-diagnostics guidance, which still allows read-only `doppler secrets get`/injection checks and explicitly-requested `doppler secrets set` during live incident triage.) (user direction 2026-06-16, WT-907 WS7: "dont do any doppler changes (but record in the PR instructions they have to happen when merging the epic branch into main)").
- **When removing a config/env enum value (rollout mode, feature-flag string, variant) that a deployed environment may still hold, keep it as a transitional alias to the new value instead of deleting it outright.** A hard removal makes the validator reject the stale env value on the next deploy; if the resolver fails closed to a safe-but-inactive mode (e.g. `shadow`), the feature silently turns off until someone flips the env — a deploy-ordering hazard. Map the old value → its new equivalent in the alias table now, and delete the alias in a later cleanup once every env is confirmed reset (Codex PR #1455 P1; WT-907 WS7 kept `skills`/`skills-only`/`skills-variant` → `live`).
- **Paired in-flight / terminal status emissions must cover every exit path.** When a worker emits a "work started / in-flight" status to an outbound stream (e.g. the Robin status queue's `running` at graph-invoke), every terminal exit — the normal tail, early returns, AND the outer exception/recovery handler — must emit a settled status, or the consumer is left stuck on the in-flight state indefinitely. Verify the exception path re-derives and emits a terminal status (best-effort, before re-raising) (Freight-Hero/ai_watchtower#1433 codex P2).
- **Multi-message status streams on a standard (best-effort-ordered) SQS queue need a monotonic ordering key + last-writer-wins.** When more than one status message is emitted per entity over a non-FIFO queue (e.g. `running` then a terminal status), the contract must carry a monotonic key (millisecond `timestamp`, or a version/sequence) and require consumers to apply last-writer-wins per entity id, discarding stale deliveries — otherwise SQS reordering can regress the entity to an earlier state. Prefer documenting the timestamp-in-contract guarantee over switching to FIFO when the queue/consumer are owned by another service. A truncated-precision key (ms `timestamp`) is **not** strictly monotonic — rapid emits (a fast / immediate-failure path) can share a value, so pair LWW with a deterministic tie-break (e.g. a terminal status beats an in-flight one) or a strictly-increasing sequence; "discard if not newer" alone drops the later state on a tie (Freight-Hero/ai_watchtower#1433 codex P2).
- **When the queue/consumer owner will coordinate a FIFO flip, prefer FIFO over the timestamp-LWW interim for a multi-message status stream.** The timestamp-LWW guidance above is the fallback for when the other service will not switch. Once the owner declares the queue FIFO (e.g. ez4 `Queue.Ordered` + `fifoMode groupId:'<entityId>'` with content-based deduplication enabled), the publisher orders per entity by sending `MessageGroupId = <entityId>` on **every** send (FIFO rejects a send without it) and omits `MessageDeduplicationId` when content-based dedup is on. FIFO then guarantees in-order delivery + processing within a group, so the in-flight→terminal pair cannot reorder and the millisecond `timestamp` key is downgraded to display-only (kept so distinct bodies do not collide under content-based dedup). #1433 used the standard-queue timestamp-LWW interim; #1458 made the same Robin status stream FIFO once the backend owned the flip (Freight-Hero/ai_watchtower#1458). Deploy the owner's FIFO queue **before** the publisher repoints — a standard→`.fifo` rename is a *new* SQS resource (FIFO cannot be toggled in place), so a publisher that ships first targets a non-existent queue and best-effort-fails silently.
- **Capped + rotated scan windows: stride the pivot by the WINDOW WIDTH per tick, and treat rotated-out items as UNKNOWN, not empty.** Two invariants for any "too many candidates, scan a rotated cap-bounded slice per run" pattern: (1) a pivot that advances +1 per cadence tick under a `cap`-wide window shifts an almost-identical window each run — worst-case first coverage is ~`len-cap` ticks (~7.8 days at 1000/250 on a 15-min cadence), not the intended `ceil(len/cap)`; stride the pivot by the window width (`pivot = (offset * width) % len`) so consecutive windows tile the ring, and compute per-tier widths BEFORE rotating when a budget is split across tiers. (2) items rotated out this run have UNKNOWN (not empty) state — a consumer that reads a missing entry as `[]`/`None` can emit false positives (missing transition history made stale no-active evidence read as "after the current milestone" → false SIG-WF-001/005); track the unscanned set explicitly, skip evidence-timing decisions for those items, and give evidence-bearing items scan priority so they never lose the rotation race. Also check the coverage claim in tests: a rotation test that advances the offset by `cap` per run instead of one tick masks the stride bug. The same starvation hides in any fixed-prefix slice: `selected = priority[:cap]` of an over-cap set re-picks the same IDs every run (the tail never scans) even with no `% len` rotation in sight — an over-cap set must ALWAYS rotate before slicing. Shipped three times in one PR (transition scan, recon tiers, priority overflow) and caught by review each time — when touching one capped scan, grep for other `% len` rotations AND `[:cap]`-style prefix slices of unbounded sets (Codex PR #1509 P2 ×4; WT-1031).

---

## 17. AI Watchtower Skills Authoring (`ai_watchtower/app/skills/**`)

When the diff touches **any** file under `ai_watchtower/app/skills/` (including `SKILL.md`, `references/*.md`, `workflow-overrides/*.md`, `shipper-overrides/*.md`, or `_shared/escalation-models/**`), the canonical authoring guide is the source of truth for the review:

```
ai_watchtower/docs/architecture/skills/authoring-guide.md
```

Read it before reviewing. Apply the `ai-watchtower-skills-authoring` skill's review mode (§11 reviewer checklist plus §10 anti-pattern scan). For every blocking finding, cite the violated section number from the canonical guide (e.g., "§5.1 token budget", "§7.2 tool-table language", "§10.4 meta-mechanism leakage").

Non-negotiable rules to verify on every skills diff:

- **§1.1 / §5.1 token budget.** Combined `SKILL.md + workflow-overrides/*.md` ≤ 500 lines / ~5,000 tokens. Run `wc -l` on the affected files. Exceeding the budget blocks the merge until decomposed (§5.2 triggers, §5.4 routing-table pattern).
- **§5.5 no stub references.** Every file under `references/` must have real content. A `<!-- TODO -->` stub is a dead link the agent may follow.
- **§5.3 references one level deep.** No reference links to another reference. References must be self-contained — every required tool call listed in-file.
- **§6.2 / §6.3 frontmatter contract.** `name` is kebab-case and matches the directory. `description` is third person, states what + when, ≤1024 chars, no mechanism leakage. Intent skills declare `workflows:`.
- **§7.1 no invisible tool references.** Every tool mentioned in a broker profile (or in a skill that loads with it) must exist in that broker's routing config — even negations are forbidden.
- **§7.2 unambiguous tool-table language.** Escalation phrases must map unambiguously to broker profile tool-table rows: "urgent human handoff", "non-urgent human handoff", "broker visibility". Vague phrases ("escalation mechanism") are a blocker.
- **§7.3 default-in-intent, override-in-profile.** Broker-varying behavior must not be hardcoded in shared intents.
- **§7.5 no workflow logic inline in broker profile body.** Workflow-scoped content goes under `<broker>/workflow-overrides/` with frontmatter `workflows: [...]`.
- **§7.6.7a / §7.6.7b caller/callee contracts.** Named procedures own the `get_past_*` duplicate-check. Intents own `send_tms_notes`. Profiles must NOT include `send_tms_notes` in named procedures.
- **§8.3 single-invocation completeness.** A skill must not assume the agent remembers content from a prior invocation — `PostRunContextEditingMiddleware` clears skill tool output between turns. Durable state lives in `send_tms_notes`, load state fields, or timer payloads.
- **§8.4 boundary statements.** Intent skills declare what they do NOT handle and where to route instead.
- **§3.2 / §3.6 / §10.4 no meta-mechanism leakage and no engineering references.** Descriptions and bodies must not mention `load_skill`, auto-composition, file paths, PR numbers, load UUIDs, or "we observed in production" framing.
- **§3.5 / §10.11 default with escape hatch, not a menu.** State the default tool/path, then list at most one conditional alternative.
- **§4.3 no voodoo constants.** Every timer duration, threshold, or numeric value carries a stated reason.
- **§3.4 no time-sensitive content.** No absolute dates or "after <date>" branches in skill bodies.
- **Skill body is the complete system prompt.** When migrating a factory from a wrapper template (e.g. `*_SYSTEM_PROMPT.format(...)`) to `SkillsService.load_skill(...)`, delete the wrapper. Duplicated guardrails or hardcoded tool instructions in a factory wrapper contradict the skill body and break the workflow → tool → prompt contract (see PR #1360 / `RESUMPTION_SYSTEM_PROMPT`).
- **Universal-required tools belong in `_base.yaml`, not broker overlays.** If a shared intent's procedure under `<workflow>` requires a tool on every broker, expose it in `app/configs/workflows/<workflow>/_base.yaml::sub_workflows.<sub>.tools`. Broker overlays (`patterns/<broker>_<sub>.yaml`) carry deltas only (§7.3 clarification; see PR #1357 / `get_past_tasks`).
- **Regenerate `app/configs/workflow_manifest.yaml` whenever you edit `app/configs/workflows/**` (tool lists, broker patterns, sub-workflows).** The manifest is auto-generated (`# Do not edit directly`) and propagates each `_base.yaml` tool list into every broker variant — one removed/added tool line changes many manifest entries. Run `python -m scripts.dev_tools.workflow_manifest.generate` after the config edit; `tests/unit/test_workflow_manifest_validation.py` enforces manifest↔source freshness, so a stale manifest fails CI. Never hand-edit the manifest. **The same config edit also breaks the config-snapshot fixtures** `tests/unit/configs/snapshots/tool_resolutions.json` + `composition_migration_baseline.json` (compared per-combo against the loader by `tests/unit/configs/test_workflow_config_equivalence.py` and `test_config_system_characterization.py`) — update them too via `tests/unit/configs/generate_tool_snapshot.py` / `generate_composition_migration_baseline.py`, OR surgically drop the changed tool from only the affected combos (+ decrement `tool_count`) to avoid absorbing pre-existing snapshot drift into the PR (user direction 2026-06-16; WT-907 WS5 dropped `dynamic_sops_fetch` from the confirm `_base.yaml`; Codex PR #1453).
- **Delete dead SOP runtime in the same migration PR** when static evidence (`rg "skill_router|skills_loader|skill_agent_factory|skills_manifest"` returns zero hits in `app/` + `tests/`) proves zero callers. Do not defer to a later cleanup workstream.
- **Progressive-disclosure is the canonical pattern for every agent factory — including single-intent sub-agents.** Mirror the `inbound_communication_agent` shape: bootstrap `SKILLS_SYSTEM_PROMPT_TEMPLATE` with role + 3-step workflow, render the skill catalog via `SkillsService.get_skill_catalog(workflow=..., broker=...)`, wire `load_skill` + `load_skill_reference` into the tool list, attach `SkillToolOutputMiddleware` (outermost) + `PostRunContextEditingMiddleware` with `TOOLS_TO_CLEAR_FROM_CONTEXT`. The deterministic skill-as-system-prompt pattern (loading the skill body at construction and assigning to `system_prompt`) is removed — it forfeits the agent's ability to branch into another intent when the loaded procedure authorizes it (authoring-guide §1.4(f); PR #1358 commit `d6781a9d`).
- **Do not add a `runtime_facts` kwarg to simple single-intent agent factories.** Resumption-style factories load one skill and apply one procedure; they do not need runtime fact injection. Adding the kwarg "for parity" with `inbound_communication_agent` is reverted on review (PR #1358 commit `716806c8`).
- **Skill bodies must not enumerate broker-profile capabilities or notification channels.** Phrases like "broker visibility or internal slack" leak broker-profile detail into broker-agnostic content and create a reference dependency on profiles that may change. Tool resolution is governed by the auto-composed broker profile + workflow tool set — that is the only source of truth (§7.1, §7.2, §7.3, §3.6; PR #1358 commit `dfbec09f`).
- **Skill bodies must not instruct the agent to call tools the agent does not have access to.** Cross-check every imperative ("set status to IDLE", "call X", "fire Y") against the workflow tool list and the auto-composed broker profile. If the tool is not exposed, the instruction is dead text — rewrite as "take no action" or remove (PR #1358 commits `c3e560e8`, `5de779fe`).
- **FACTS keys must match the field names the migrated skill body references.** When a routine/agent loads a skill via progressive disclosure, every gate field or branch flag the skill body names (e.g. `stale_tracking_request_attempts`, `is_same_day_or_ambiguous`) must be emitted by the routine's FACTS builder under the *same* key. A renamed/abbreviated key — or a flag the FACTS dict never includes — makes the agent read the field as missing and take the wrong branch (extra driver SMS, leaked appointment time/location). Grep the new skill body for backticked field names and confirm each is a key in the FACTS dict the agent receives (PR #1442 / WT-907 WS3 Codex P2).
- **Banned engineering vocabulary in skill bodies and references** (§3.6 operational voice): `node`, `graph`, `sub-graph`, `sub-workflow`, `auto-composed`, `progressive-disclosure agent`, `directive at the top`, `deterministic .+ layer`, file paths, `class Name`, `def name(`, `tests/...`, GitHub issue/PR numbers. Run `find app/skills -name '*.md' ! -path '*/_template/*' | xargs grep -nE '<pattern>'` and verify zero hits before merge (PR #1358 commit `898819213493`).
- **Skill bodies must not narrate the composition mechanism.** Paragraphs like "the active workflow determines which overrides apply" or "an override defines the procedure for …" are meta-mechanism leakage. The runtime applies overrides automatically; the routing table alone is the agent-facing interface (§3.2, §3.6, §8.3, §10.4; PR #1358 commit `dfbec09f`).

For changes touching `app/services/skills_service.py`, `app/utils/skill_tools.py`, `SkillToolOutputMiddleware`, or `PostRunContextEditingMiddleware`, verify the runtime invariants in §1.4 are preserved (composition order, context clearing between invocations, raw-markdown tool output, auto-generated reference catalog).

---

## 18. GitHub Actions / CI Workflow Gating (`.github/workflows/**`)

Review change-gated pipelines (jobs that skip when their change-gate is false) against these `needs:`/`if:` semantics. Getting them wrong lets a deploy run after an upstream failure, or blocks a deploy that should proceed. (Source: ai_watchtower `ci-change-gates.yml`, PRs #1490/#1491; Codex P1 "Gate dev image on the dev plan result".)

- **Guard EVERY transitive upstream stage, not just the immediate parent.** In a chain `plan → apply → deploy`, when `plan` fails the intermediate `apply` AUTO-SKIPS (result `skipped`, not `failure`). A downstream job that only checks `needs.apply.result != 'failure'` therefore still runs after a failed `plan` (skipped ≠ failure). The deploy must also list `plan` in `needs` and check `needs.plan.result != 'failure'`. Mirror the gate across both environments (prd and dev) — an asymmetric gate is the common bug.
- **`!cancelled()` / `always()` defeats auto-skip — add an explicit success check.** A job whose `if:` contains `!cancelled()` or `always()` does NOT auto-skip when a needed job fails or is skipped. To BLOCK such a job on a gate failure you MUST add `needs.<gate>.result == 'success'`; listing the gate in `needs` alone is insufficient. (E.g. an image deploy that must run on skipped infra but block on failed unit-tests needs both `!cancelled()` and `needs.unit-tests.result == 'success'`.)
- **`skipped` ≠ `failure` — pick the operator deliberately.** Use `result != 'failure'` for "ran-or-skipped is OK, block only on a real failure" (lets a change-gated no-op proceed). Use `result == 'success'` for "must have actually succeeded." Mixing them up is how a skipped no-op merge silently blocks, or a real failure silently proceeds.
- **`needs.<job>.result` / `.outputs.*` is only populated when `<job>` is in that job's `needs:`.** A reference to a job absent from `needs` is always empty — a silent mis-gate. Cross-check every `needs.X.*` in an `if:` against the `needs:` list.
- **Secret-bearing jobs must not run on `pull_request`.** Any job with cloud creds / tokens in `env` (AWS keys, `DOPPLER_TOKEN*`) that checks out and executes repo code must restrict to `github.event_name == 'push' && github.ref == 'refs/heads/main'`, so PR-controlled code never sees the secrets. PR-time feedback belongs in a separate secret-less job (e.g. `terraform validate -backend=false`).
- **`actions/upload-artifact@v4` errors on duplicate artifact names in one run.** Per-environment artifacts (e.g. prd vs dev plan) need distinct names (`tfplan` vs `tfplan-dev`).
- **Validate the graph before merge:** parse the YAML, confirm every `needs` target exists, every `needs.X.*` reference is in that job's `needs`, and trace the no-change / upstream-failure / unit-failure / `pull_request` scenarios for each deploy job.

---

## Review Checklist

Before approving a PR, verify:

- [ ] No `any` types used
- [ ] No `console.log` or debug code left
- [ ] Database operations go through repositories
- [ ] No redundant queries (same entity fetched multiple times)
- [ ] `undefined` used instead of `null` (except ORM relation disconnects)
- [ ] Optional properties used instead of nullable ones in responses
- [ ] No internal/external IDs exposed to frontend
- [ ] Shared utils and services reused (not reimplemented)
- [ ] Error handling uses `try/catch`, not `.catch()` on promises
- [ ] Errors are thrown, not just logged (except queue handlers)
- [ ] Framework conventions followed (`request.data`, `Http.Incoming`, status codes)
- [ ] Queue messages carry all needed context
- [ ] No sensitive data logged
- [ ] Test/debug endpoints removed or feature-flagged
- [ ] API naming conventions respected (`camelCase` for standard, `Preserve` for webhooks)
- [ ] Return types only specified when strictly necessary
- [ ] AI Watchtower path/file inputs validate slugs and resolved path containment
- [ ] YAML/frontmatter/config parsing validates mapping and field types
- [ ] Unknown variants, provider modes, model routes, and unmappable sub-agents fail fast with clear errors
- [ ] Agent workflow changes preserve source-of-truth boundaries and do not bypass transition services
- [ ] Model output flags/classifications use closed vocabularies with drift checks
- [ ] Shadow logs and live routing decisions remain equivalent
- [ ] Persistence changes have real integration coverage when mocks cannot catch the failure class
- [ ] Prompt-touching changes have deterministic fixtures plus gated scenario coverage where available
- [ ] Production fixes add redacted replay or regression fixtures for the failure shape
- [ ] **Skills diffs (`ai_watchtower/app/skills/**`) reviewed against `ai_watchtower/docs/architecture/skills/authoring-guide.md`** — every blocking finding cites the violated section number
- [ ] Combined `SKILL.md + workflow-overrides/*.md` ≤ 500 lines / ~5,000 tokens (§5.1)
- [ ] No stub `<!-- TODO -->` files under `references/` (§5.5)
- [ ] References are one level deep and self-contained (§5.3)
- [ ] Frontmatter `name`/`description`/`workflows:` contract holds (§6.2, §6.3, §2.2)
- [ ] No invisible tool references; escalation uses tool-table language (§7.1, §7.2)
- [ ] Broker-varying behavior uses default-in-intent + profile override (§7.3)
- [ ] No workflow logic inlined in broker profile body (§7.5)
- [ ] Named-procedure caller/callee contracts respected — procedure owns `get_past_*`, intent owns `send_tms_notes` (§7.6.7a, §7.6.7b)
- [ ] Skill content is single-invocation complete; no reliance on cleared prior-turn state (§8.3)
- [ ] Boundary statements present in intent bodies (§8.4)
- [ ] No meta-mechanism leakage, no engineering references, no time-sensitive content, no menus (§3.2, §3.4, §3.5, §3.6, §10.4)
- [ ] Numeric constants justified (§4.3)
- [ ] Missing/empty critical payload fields fail closed, same as unknown variants
- [ ] Tool config + prompt content aligned — no prompt instruction to call a tool not in workflow yaml
- [ ] Behavioral tests use `tool_only/` pattern; Robot framework not relied on as merge gate
- [ ] Shared-intent body restructures show 0pp delta on neighboring workflows' tool-only suites
- [ ] Factory wrapper templates deleted when migrating to `SkillsService.load_skill` (no duplicate guardrails)
- [ ] Universal-required tools live in `_base.yaml`, not broker overlay (§7.3)
- [ ] Legacy SOP runtime deleted in same PR when `rg` proves zero callers
- [ ] Agent factories follow the progressive-disclosure shape (catalog + `load_skill`/`load_skill_reference` + `SkillToolOutputMiddleware` + `PostRunContextEditingMiddleware`) — including single-intent sub-agents (§1.4(f))
- [ ] No `runtime_facts` kwarg on simple single-intent factories
- [ ] FACTS keys emitted by the routine match the field names the migrated skill body references (no renamed/abbreviated/omitted gate fields or branch flags) (§17; PR #1442)
- [ ] Skill bodies do not enumerate broker-profile capabilities or notification channels
- [ ] Skill bodies only instruct tools the agent actually has (cross-check workflow yaml + composed broker profile)
- [ ] No banned engineering vocabulary in skill bodies (node/graph/sub-graph/sub-workflow/auto-composed/file paths/PR numbers/test paths)
- [ ] Skill bodies do not narrate composition/override mechanism — routing table is the only agent-facing interface
- [ ] Broker-originated load events still flow via backend TMS notify-event path (blanket broker-ignore guardrail intact across all 5 inbound agents)
- [ ] Tracking workflow thread_ids scope by `task_uuid` (data graph) / `stop_uuid` (checkpoint routine), never `{load_id}_<direction>`
- [ ] Provider-translation layer sanitizes tool-use `name` against Bedrock's `[a-zA-Z0-9_-]+` regex when crossing provider boundaries
- [ ] CI change-gated deploy jobs guard EVERY transitive upstream stage's `result != 'failure'` (not just the immediate parent), symmetrically across envs (§18)
- [ ] `!cancelled()`/`always()` deploy jobs add explicit `needs.<gate>.result == 'success'` to block on a gate failure (§18)
- [ ] Secret-bearing workflow jobs restricted to `push` + `refs/heads/main`; per-env upload-artifact names distinct (§18)
