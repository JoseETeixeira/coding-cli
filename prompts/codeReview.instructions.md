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

## 13. AI Watchtower Python Security & Input Boundaries

- Treat caller-controlled identifiers used in paths as untrusted. Validate slugs with a strict allowlist before path construction, then verify the resolved path stays inside the intended root.
- When raw business names are accepted, reject traversal tokens before normalization, then normalize through the project helper or explicit alias/lowercase/kebab-case flow.
- Parse YAML/frontmatter defensively. Validate the parsed value is a mapping before reading fields, and validate required text fields are strings before using them.
- Fail fast on unknown workflow variants, model route modes, provider types, skill mappings, or sub-agent mappings. Raise a clear `ValueError` instead of silently falling back or allowing a later `FileNotFoundError`.
- Prefer explicit default profiles only where the product contract supports a default, such as a default broker profile. Do not use broad fallback behavior to hide invalid configuration.
- For cross-load or cross-context data, scope reads and writes by the current load/task/message identifiers only. Never let cached or historical context from another load influence the current workflow.

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

---

## 15. AI Watchtower Testing Expectations

- Pick the regression layer that matches the bug. Use LocalStack-backed integration tests for DynamoDB/persistence behavior; use deterministic unit tests for pure routing and graph-node logic; use gated real-LLM scenario tests for prompt behavior.
- Test behavior, not implementation details. Persistence tests should assert stored rows and branch outcomes, not only mocked expression strings. Refactor tests should assert public behavior, not module paths.
- For prompt-touching changes, treat the scenario suite as the behavioral contract. Run the gated scenario suite with retries/repetition when available, and treat repeated failures as real regressions rather than flakiness.
- Include positive and negative fixtures for operational guardrails: stale vs fresh tracking, wrong-leg geography, bare attachments, broker questions, load cancellation, trusted-system events, and direction scoping.
- Add production-case replay fixtures when a change fixes a production failure. Redact sensitive details, but preserve the semantic shape that caused the bug.
- For rollout or gate changes, add non-regression matrices covering every existing transition source and assert unchanged paths remain unchanged.
- When an integration path failed in dev/prd, add at least one runtime integration test that exercises the real path, not only isolated helper logic.

---

## 16. AI Watchtower Observability & Operations

- Keep existing log event names stable where dashboards or manual runbooks depend on them.
- Add structured log payloads for routing decisions, overrides, shadow/live mode, classification outputs, and failure fallbacks. Avoid sensitive data in logs.
- When adding fallback/retry behavior, bound retries, prevent fallback loops, and emit observable events for the fallback trigger and selected provider/model.
- Document operational validation for high-risk changes: deploy target, log query, expected event shape, rollback toggle, and manual checks against affected state.

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

For changes touching `app/services/skills_service.py`, `app/utils/skill_tools.py`, `SkillToolOutputMiddleware`, or `PostRunContextEditingMiddleware`, verify the runtime invariants in §1.4 are preserved (composition order, context clearing between invocations, raw-markdown tool output, auto-generated reference catalog).

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
