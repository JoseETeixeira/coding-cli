---
applyTo: '**'
---

# Code Patterns & Conventions

These patterns are derived from team code reviews and represent our preferred coding style. Freight-Hero backend patterns are primarily TypeScript/EZ4; AI Watchtower patterns are Python/agent-workflow focused and include recurring guidance from closed `ai_watchtower` PRs reviewed or authored by `arthurmf`.

## AI Watchtower Path & Config Boundaries (input + payload validation)

Missing or empty critical payload fields fail closed (`ValueError` + ERROR log), same as unknown variants. Don't fall through to free-form classification when timer / classifier / route payloads are malformed.

## AI Watchtower Path & Config Boundaries

- Validate every caller-controlled path segment with a strict slug allowlist, then verify the resolved path stays inside the intended root.
- Reject traversal tokens before normalizing raw business names such as broker names; then normalize with alias resolution and kebab-case conversion.
- Parse YAML/frontmatter as untrusted input: require a mapping and validate required fields are strings before use.
- Unknown workflow variants, provider route modes, model names, skill mappings, and unmappable sub-agents should raise clear `ValueError`s.

```python
# Don't do this
path = skills_root / workflow / broker / f"{skill_id}.md"

# Do this
skill_slug = validate_slug(skill_id, "skill_id")
path = assert_within(skills_root / workflow / broker / f"{skill_slug}.md", skills_root, "skill")
```

## AI Watchtower Agent Guardrails

- Preserve source-of-truth boundaries: gates and agents should call the existing transition service/backend contract, not write TMS-owned milestone state directly.
- Ambiguous classifier output should route to inbound/broker handling, not direct driver outreach or milestone transitions.
- Use closed vocabularies for LLM outputs such as flags, tiers, signal types, and classifications. Keep hard-flag sets synchronized with type assertions.
- Shadow-mode telemetry must mirror live-equivalent decisions, including overrides and `would_have_transitioned` style fields.
- Trusted-system events need stable provenance metadata before they can drive live transitions.
- Tool config and prompt content stay aligned. Removing a tool from workflow yaml → scrub every prompt that instructs calling it (system prompts, skill bodies, factory wrappers).
- Skill body = complete system prompt. Factory wrappers that duplicate or contradict the skill body are anti-pattern; delete during SOP → Skills migration.
- Universally-required tools live in `_base.yaml::sub_workflows.<sub>.tools`. Broker overlays (`patterns/<broker>_<sub>.yaml`) carry deltas only.

## AI Watchtower Testing Layers

- Match the test layer to the failure class: LocalStack integration for DynamoDB/persistence, deterministic unit tests for routing, gated real-LLM scenarios for prompt behavior.
- Test behavior and persisted state, not only mocked expression strings or private module paths.
- Prompt-touching changes should keep the scenario suite green; repeated scenario failures are regressions unless proven otherwise.
- Production fixes should add redacted replay fixtures that preserve the semantic failure shape.
- Rollout/gate changes need non-regression matrices for existing transition sources and unchanged paths.
- Tool-only scenario suites are the primary behavioral merge gate. Live-LLM judge runners are deprecated (skip-shim pattern from `confirm_pickup` / `confirm_delivery` / `initiate_tracking`).
- Robot framework is not a validated merge gate; use as supplementary evidence only — regex on UI-rendered state-field artifacts is brittle.
- Shared-intent body restructures must prove 0pp delta on every neighboring workflow's tool-only suite (pre/post).

## AI Watchtower Observability

- Keep operational log event names stable when dashboards or runbooks depend on them.
- Log structured routing, classification, override, shadow/live, fallback, and error context without sensitive data.
- Bound provider/model retries and fallbacks; prevent fallback loops and emit events when fallback is triggered.

## Best-Effort Side-Effects Must Not Live in Functional Transactions

Side-effects whose failure should not block the critical path (UX reactions, notifications, logging, analytics) must be isolated from the functional dispatch they accompany. The fastest way to silently break a system is to put a best-effort call and a load-bearing call inside the same DB / queue transaction:

```ts
// ANTI-PATTERN — observed in chat-received.ts:106-198
await db.transaction(async (transaction) => {
  await Repository.createRow(transaction, { ... });        // functional: persists the inbound row
  await Repository.createEvent(transaction, { ... });      // functional: load event
  await externalApi.reactWithEyes({ messageId });          // BEST-EFFORT: UX reaction to Slack
  await downstreamQueue.sendMessage({ ... });              // CRITICAL: dispatches to the agent
});
```

When `externalApi.reactWithEyes` throws, the transaction rolls back. Every line above AND below rolls with it — including the queue send. The downstream agent never receives the message, retries replay the same failure, and the message dead-letters with zero functional record. The symptom in production looks like "the agent didn't answer and didn't react", which masks the upstream side-effect failure as a downstream agent bug.

Apply ONE of these (in preference order):

1. **Move the best-effort call outside the transaction.** If the reaction / notification doesn't need transactional consistency with the DB writes, fire it after the transaction commits.
2. **Wrap the best-effort call in `try / catch`** that logs the failure and continues. Critical path still runs.
3. **Use an outbox-style queue** for the best-effort call: write a row inside the transaction, dispatch the side-effect from a separate worker that can fail in isolation.

Production case (Freight-Hero/backend#628, 2026-05-19): the `:eyes:` Robin-processing reaction in `chat-received.ts:161-170` lived inside `consoleDb.transaction` alongside `agentInboundQueue.sendMessage`. When Slack returned `message_not_found` on the reaction (race condition / bot membership), the transaction rolled back, the queue send never fired, ai_watchtower never received the message, robin-gpt never computed an answer. Symptom: "Robin didn't react and didn't answer" for hours, even though the user-facing analytical path on robin-gpt was fully functional. Fix: try/catch around the reaction call.

Detection: when a downstream agent / worker shows zero traces for a request that definitely entered the system (webhook delivered, BE log shows the inbound), and the upstream service has retry events that all fail identically, suspect a transaction-wrapped side-effect blocking the dispatch. The Sentry trail will show the side-effect's error N times (once per SQS retry) while the downstream trail is silent.

## AI Watchtower Robin GPT Bridge Timeout Diagnosis

When a user reports a chat message went unanswered (Robin posted nothing in Slack, not even an error), trace the bridge call in this order — most failures cluster around the bridge timeout, not the agent itself.

- **Robin-gpt service usually computes an answer.** The deployed `robin_gpt_bridge` in `ai_watchtower/app/services/robin_gpt_bridge.py` calls `POST /system/loads/{load_id}/chat-messages` on the robin-gpt service with `httpx.Timeout(self._settings.ROBIN_GPT_CHAT_TIMEOUT_SECONDS)`. The setting defaults to 25 s — too short for analytical questions that touch many tools (`get_tracking_history`, `get_state_transitions`, multi-stop ETA inference) or hit cold caches.
- **The diagnostic trail lives in `/ecs/<stage>-ai-watchtower`** under three event names: `robin_chat_message_received`, `robin_chat_message_timeout`, `robin_chat_message_exception`, `robin_chat_message_completed`. Filter on the load UUID or `trace_id` to follow a single conversation. A pair of `_received → _timeout → _exception(504)` followed by a second `_received` with the SAME `idempotency_key` ~10–30 s later is the canonical bridge-timeout signature.
- **Robin-gpt's own idempotency layer keeps working past the timeout.** When the bridge gives up at 25 s, the in-flight claim on robin-gpt continues; the BE's retry on the same idempotency key joins the existing run and returns the cached response in seconds. The 200 OK on the retry is the answer the agent always intended — but the user-facing chat path has already 504'd, so Slack never relays it.
- **CloudWatch query template** (substitute stage, load_uuid, time window):

  ```
  AWS_PROFILE=freighthero aws logs filter-log-events \
    --log-group-name /ecs/<stage>-ai-watchtower \
    --start-time <epoch_ms> \
    --filter-pattern '"robin_chat_message"' \
    --query 'events[].[timestamp,message]' --output text
  ```

  Pair with `/ecs/<stage>-robin-gpt` filtered on `"chat-messages"` to see the matching robin-gpt-side 200/5xx response.

- **Fix paths** (apply in order):
  1. Bump `ROBIN_GPT_CHAT_TIMEOUT_SECONDS` in Doppler for the affected stage (recommended 45–60 s for analytical surfaces). No code deploy.

     ```bash
     # FreightHero Doppler project for ai_watchtower + robin-gpt services.
     # Stages: local / dev / prd (no stg in this project).
     doppler secrets set ROBIN_GPT_CHAT_TIMEOUT_SECONDS=60 \
       --project freight-hero-agents --config <stage> --no-interactive

     # Force ECS rolling restart so new tasks pick up the new env at start.
     # The API service runs the bridge; workers do not need to restart for
     # this setting.
     AWS_PROFILE=freighthero aws ecs update-service \
       --cluster prd-ai-watchtower-cluster \
       --service prd-ai-watchtower-green-service \
       --force-new-deployment
     ```

  2. If robin-gpt itself is the bottleneck (look for slow LLM calls or unbudgeted tool payloads), bump the per-tool token budgets (e.g. `agent_tracking_history_tool_budget_tokens`) or downsample tool payloads (see "AI Watchtower Agent Tool Payload Compaction" below).
  3. Move the chat path to async / queue-based delivery so a slow Robin response cannot time out the user-facing call. Larger change, defer until #1 + #2 stop helping.

- **Deploy verification** (before assuming a recent build is live): the API service runs `prd-ai-watchtower-api-ecr:green`, but the `green` tag does NOT auto-update on every push — it is moved explicitly by the deploy pipeline. Check the actual taskdef + deployment timestamp before concluding code is live.

  ```bash
  AWS_PROFILE=freighthero aws ecs describe-services \
    --cluster prd-ai-watchtower-cluster \
    --services prd-ai-watchtower-green-service \
    --query 'services[0].deployments[].[status,createdAt,taskDefinition,rolloutState]' --output text

  AWS_PROFILE=freighthero aws ecs describe-services \
    --cluster prd-robin-gpt-cluster \
    --services prd-robin-gpt-chat-service \
    --query 'services[0].deployments[].[status,createdAt,taskDefinition,rolloutState]' --output text
  ```

  Robin-gpt uses timestamp image tags (e.g. `20260519173427`), so the image push time in ECR maps directly to "what is live". Cross-reference the push time against the failure timestamp to confirm whether the failure hit the pre-deploy image (most common cause of "I deployed but the failure shape persists").

- **Common false-positive: thinking the message never reached robin-gpt.** Check `/ecs/<stage>-robin-gpt` with the SAME load UUID. If you see a 200 OK in robin-gpt right after the ai-watchtower `_timeout`, the agent computed an answer; the failure is in the bridge layer, not robin-gpt. Conversely, zero robin-gpt traffic for that load UUID means the BE never forwarded the message — check the BE's `agent-chat` flow (`backend/packages/console/src/communications/services/agent-chat.ts`).

## AI Watchtower Agent Tool Payload Compaction

When an LLM agent tool envelope (Robin GPT, deep agents, any tool that returns a list of rows the model has to reason over) might exceed its token budget, compact the payload by preserving information density, not by random or strided dropping:

1. **Field strip first** — drop per-row bookkeeping the model never references (IDs, providers, sources), rename to short keys (`t`/`lat`/`lon`). Every row survives.
2. **Round / coarsen second** — round floats to the lowest meaningful precision (e.g. lat/lon to 3 dp ≈ 110 m), truncate timestamps to minute precision when sub-minute resolution is not needed. Every row survives.
3. **Cluster / segment third** — collapse consecutive rows that share a semantic group (same city, same status, same dwell location) into one row carrying `from_t`/`to_t`/`count`/`dwell_minutes`. Every row is accounted for; the agent reads the answer directly off the cluster instead of inferring it from a sample.
4. **Only THEN drop rows** — and when you do, surface an explicit `partial` envelope with a marker (`omitted_due_to_context_budget`) and a warning. Never silently return `status: "ok"` while having dropped data.

Avoid uniform-stride or random sampling as the first response to a budget overflow: it discards rows the agent might need without warning and breaks analytical queries (dwell, idle, ordering, gap detection). Information-preserving compaction is almost always cheaper than the LLM tokens you save by dropping rows.

## AI Watchtower Planner Intent Routing

When the orchestrator's keyword / intent planner routes a request to a deterministic handler, each semantically distinct intent must map to its own focus — even when the focuses look similar at first glance.

- Distinct user questions need distinct focuses. `GFOTD` ("good for on-time delivery") and `GFOTP` ("good for on-time pickup") answer different operator questions and can disagree on the same load (e.g. pickup already complete while delivery is at risk). Sharing `focus="eta"` lets the wrong leg's appointment / ETA fields leak into the answer.
- Each focus needs its own deterministic handler that reads only the relevant slice of the payload. Filter `load_summary.locations` by stop type (`pickup` / `delivery`) at the handler entry — do not surface every stop's facts and trust phrasing to disambiguate.
- Each handler must short-circuit on milestone progression. GFOTP after pickup completion → "pickup is already complete; GFOTP no longer applies". GFOTD before pickup completion → "pickup is not yet complete; delivery on-time outlook depends on pickup finishing first." Returning the raw delivery ETA when pickup is still pending mis-implies the load is ahead of schedule.
- Add a `_OPERATOR_KEYWORD_PLANS` distinct-focus regression test so a future refactor cannot silently collapse the two focuses back into one.

## AI Watchtower Multi-Shape Payload Normalization

WT BE timeline-style endpoints emit data in two shapes — flat (`timeline_items`, each item is an event row) and grouped (`load_events`, each item is a scope container whose actual events live under nested `events`). Any code that searches the timeline must normalize through a single flattener before matching.

- Use `_iter_timeline_items(timeline_payload)` (in `robin-gpt/app/retrieval.py`) as the entry point for any new milestone / event search. It walks both shapes and emits a uniform row layout with `event_type`, `event_at`, `payload`, `scope`, etc.
- Never read `timeline_data.get("timeline_items") or timeline_data.get("load_events")` and iterate the result directly. The grouped shape returns scope containers, your match condition reads `event_type` from a container that has none, and no row ever matches — terminal-only behavior silently regresses to "no data available".
- Coordinates / payload fields land in the grouped shape's nested `event.payload` dict. Fall back to `chosen.get("payload", {}).get(field)` so the matched event still surfaces lat / lon / timestamps after the flatten.
- Add a regression test that builds the grouped shape verbatim (`load_events: [{ events: [{ type, payload, date }] }]`) and asserts the search code still finds the milestone. The flat shape passing alone is not enough — that path doesn't exercise the flattener.

## AI Watchtower Agent Multi-Party Thread Response Gating

When an LLM agent participates in a multi-party chat (Slack thread, Teams channel, etc.) where teammates and the agent post in the same room, an upstream deterministic "directed at the agent" flag is not enough. Once the agent is engaged, upstream may forward every subsequent reply — including side conversations that tag a different teammate — and the agent will try to answer them.

- Add an LLM-based secondary gate at the chat-service layer. The classifier reads the prior thread context plus the latest message and returns one of `directed | not_directed | unclear`.
- Keep the upstream deterministic flag as a cheap fast-path for the obvious cases (no LLM call when upstream already says "definitely not the agent"). The LLM gate only runs when upstream says "directed".
- On `not_directed`, return an explicit ignore envelope (`status="ignored"`, `should_reply=False`, `answer_text=""`). Record the idempotent response so retries are stable. Never let the orchestrator (LLM or deterministic) run — both paths can hallucinate a generic load-summary answer for an unrelated message.
- Treat `unclear` as `directed` (safe default — never silence a real question).
- Any classifier failure (transport error, unparseable response, missing API key) must also fall back to `directed`. Infrastructure problems must never silence the agent.
- Reuse the main agent's model factory so the classifier inherits the workspace's existing provider routing (OpenRouter / OpenAI / Bedrock). Do not introduce a second provider config surface.
- **Flatten provider-shaped responses before parsing.** LangChain `AIMessage.content` is a `str` on most providers but a list of content blocks (`[{"type": "text", "text": "..."}, ...]`) on others — Anthropic via langchain-anthropic, OpenAI responses API, certain Bedrock configurations. A parser that treats non-string content as the safe default silently disables the gate on those providers. Coerce content to text first: handle plain `str`, list-of-blocks (extract `block["text"]`, skip non-text blocks like `tool_use` / `image`), list-of-strings, then fall through to default only if the result is genuinely empty.
- **Persist ignored turns in session history.** When the gate decides `not_directed`, append BOTH the incoming user turn AND an internal-only marker (e.g. `"[not_directed] Robin observed this thread message as addressed to a different teammate and did not reply."`) before returning the sleep response. The marker never reaches the user-visible channel (`should_reply=False`, `answer_text=""`), but the classifier reads session history on the next turn and needs the ignored turn as context — otherwise a follow-up like "yes" / "ok" / "thanks" in the same human side conversation arrives with no record of the prior off-topic turn and gets re-classified as directed at the agent. Keep this marker distinct from any user-facing "I'll stay quiet" sleep reply so independent gate paths stay literally distinguishable.

## AI Watchtower Agent User-Facing String Discipline

Internal slugs (kebab-case milestone states, snake_case transition types, enum string values) are bookkeeping identifiers, not display text. They must not appear verbatim in any user-facing LLM answer.

- Enrich tool payloads at the retrieval / normalization layer with companion `*_label` fields carrying the human-readable form (e.g. `milestone_state_label`, `from_state_label`, `to_state_label`). The slug stays for any caller that keys off it; the label is what the agent quotes.
- Source the canonical label map from a single place — typically mirror the frontend display map (e.g. `loadStatusLabel` in `frontend/packages/console/src/types/loads.ts`) so the agent and the console UI never disagree on what a state is called.
- For unknown slugs, fall back to Title Case English (`brand-new-state` → "Brand New State", `snake_case_state` → "Snake Case State") so even uncovered cases never emit a raw slug.
- In the system prompt, explicitly forbid echoing raw kebab-case / snake_case slug values and point the model at the `*_label` companion fields. A passive "use plain language" instruction is not enough — the model will copy whatever slug it sees in the tool payload if nothing tells it not to.
- Inverse rule: when matching state in code, key off the canonical slug value (from the source enum), never the display label string. `LoadMilestoneState.PodReceived = 'pod-received'` is the canonical value; `"POD Collected"` is the label only — code that does `if active in {"delivered", "pod-collected"}:` is dead matching because the backend never emits `pod-collected` on `milestone_state`. Anchor any new state-matching set on the source-of-truth enum (mirror it in a constant if needed) and add a regression test that asserts the canonical slug is in the set and the display label is not.

## Repository Pattern

- All database operations must go through repository namespaces, never inline in handlers
- Use `upsertOne` instead of check-then-insert/update patterns

```typescript
// Don't do this
const existing = await db.table.findOne({ where: { id } });
if (existing) {
  await db.table.updateOne({ data, where: { id } });
} else {
  await db.table.insertOne({ data });
}

// Do this
await db.table.upsertOne({
  insert: { ...data },
  update: { ...data },
  where: { id }
});
```

## Type Definitions

- Shared types belong in common locations, not duplicated locally
- Don't create local type extensions when you can extend the shared type

```typescript
// Don't do this (in each endpoint file)
type CreateFooRequest = FooRequest & { extra_field?: string };
type UpdateFooRequest = FooRequest & { extra_field?: string };

// Do this (in the shared types file)
export type FooRequest = {
  field: string;
  extra_field?: string;  // Add it once to the shared type
};
```

## Trust the Framework

- Undefined values are skipped by default in insert/update operations
- Don't add conditional spreads for optional fields

```typescript
// Don't do this
data: {
  ...(field !== undefined && { field }),
  ...(otherField !== undefined && { otherField })
}

// Do this
data: {
  field,
  otherField
}
```

## Trust the Data Model

- Don't add defensive checks for impossible states based on schema relations
- One-to-one relations return objects, not arrays - don't check `Array.isArray()`
- If a related record is created on entity creation, assume it exists

```typescript
// Don't do this
const details = Array.isArray(broker_details) ? broker_details[0] : broker_details;
if (existingDetails) { update() } else { create() }

// Do this (trust the relation)
const { broker_details } = company;
await db.broker_details.updateOne({ ... });
```

## Avoid Unnecessary Abstractions

- Don't create helper functions for simple property access
- Every abstraction must justify its existence

```typescript
// Don't do this
const getThreadId = (recipient: Recipient) => recipient.threadId;
const threadId = getThreadId(recipient);

// Do this
const threadId = recipient.threadId;
```

## DRY Principle

- If two functions do the same mapping/transformation, consolidate them
- Parsing functions for create vs update can often be the same

```typescript
// Don't do this
export const parseCreateRequest = (req: Request) => ({ field: req.field });
export const parseUpdateRequest = (req: Partial<Request>) => {
  const entity = {};
  if (req.field !== undefined) entity.field = req.field;
  return entity;
};

// Do this (same logic works for both)
export const parseRequest = (req: Partial<Request>) => ({
  field: req.field
});
```



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

---

## 8. Code Hygiene

- Remove all `console.log` and debug statements before PR submission.
- Remove test/debug endpoints or protect them with feature flags before merging.
- Don't log sensitive data (URLs, tokens, signatures, secrets).
- Don't add comments that describe what the code obviously does — only use comments for non-obvious decisions.
- Keep comments as succinct as possible while still being informative. Prefer 1–3 lines capturing what + why over paragraphs narrating the call chain or every downstream consequence. Reserve longer comments for genuinely non-obvious tradeoffs that won't fit in three lines.
- When implementing code that extracts fields from a structured store (Terraform state, ez4 ezstate, JSON-RPC results, k8s manifests, AWS API responses), verify each field's actual storage location against a live instance before shipping — don't infer location by analogy to sibling fields. Storage rules can be orthogonal to naming (ez4's `disableBranch:true` keeps Aurora in the shared stage state while siblings live in the per-branch file; Terraform workspaces partition some resources but not data sources; k8s cluster-scoped resources ignore namespace selectors). One live read of a real instance catches these silently divergent layouts before they ship as empty strings to downstream consumers.
- Avoid redundant error handling where both branches produce the same result.
- Don't create helper functions for simple property access — every abstraction must justify its existence.

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
