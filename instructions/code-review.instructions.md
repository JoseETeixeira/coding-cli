---
applyTo: "**"
---

# Code Review Instructions

Guidelines distilled from recurring code-review feedback. Apply only the sections matching the technology stack of the diff under review.

---

## 1. Repository & Data Access Patterns

- Never perform database operations directly in endpoint handlers. Always use a `Repository` namespace.
- Prefer `upsertOne` over read-then-insert/update patterns to avoid race conditions and reduce queries.
- Trust the data model: one-to-one relations return objects, not arrays — never check `Array.isArray()` on them.
- If a related record is guaranteed to exist at entity creation time, assume it exists — don't add defensive null/existence checks.
- Avoid N+1 queries inside loops. Use batch operations or retrieve data in bulk before iterating.

```ts
// Bad — inline DB call in handler
const details = await database.account_details.findOne({ where: { company_id } });
await database.account_details.updateOne({ data, where: { company_id } });

// Good — use a repository
await AccountRepository.updateDetails(companyId, data);

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
- Prefer simple `type` declarations over `interface`/`class` unless the framework requires it.
- For queue message types, export a client type alias: `export type StartTaskClient = StartTaskQueue['client']`.

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
- To disconnect a relationship in ORM/database operations, use `{ relation: { id: null } }` — but in application code prefer `undefined`.
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
const data = await AccountService.tryGetAccountData(id).catch(() => undefined);

// Good — try/catch
let data;
try {
  data = await AccountService.tryGetAccountData(id);
} catch (error) {
  Logger.warn('Failed to fetch account data', { error });
}
```

---

## 5. API Response Contracts

- Never expose internal or external IDs to the frontend. Use communication IDs or public identifiers.
- Only return properties the frontend actually needs — question every field.
- If a value can be absent, make the property optional in the response schema rather than returning `null`.
- Use `camelCase` for all non-webhook request/response properties.
- Third-party webhook endpoints must preserve the third party's property naming verbatim.

```ts
// Bad — coalescing to null
{ threadId: record.thread_id ?? null }

// Good — optional property
{ ...(record.thread_id && { threadId: record.thread_id }) }
// Or make it optional in the response type
```

---

## 6. Service Boundaries & Responsibility

- Delegate features to the correct service package. Channel/messaging data belongs in the communication package, not the admin/console package.
- Don't import common service definitions into packages that should be calling the API instead.
- If a function exists in a util or service (e.g. `formatName`, `createUniqueIdentity`, `getEmailDomains`), use it — don't reimplement the logic.
- Centralize shared transformations. If create and update parse the same way, consolidate into one function.
- Keep inbound-resolution paths isolated by channel. Channels with different invariants (one that knows the sender via an integration vs one that is blind and relies on contact/domain heuristics) have different matching logic; a change to one should not touch the other, and sensitive resolution paths risk altering routing and matching on incidental edits. If a fix appears to require both, split it into two PRs.

```ts
// Bad — reimplementing name formatting
const name = `${firstName} ${lastName}`.trim();

// Good — use existing utils
const name = formatName(firstName, lastName);
const id = createUniqueIdentity(companyId, externalId);
```

---

## 8. Code Hygiene

- Remove all `console.log` and debug statements before PR submission.
- Remove test/debug endpoints or protect them with feature flags before merging.
- Don't log sensitive data (URLs, tokens, signatures, secrets).
- Don't add comments that describe what the code obviously does — only use comments for non-obvious decisions. Do not add comments that merely restate relevance or reference a task/ticket (JIRA-XXX, PR number, "for the X feature") — they go stale when the work merges and the ticket archives, leaving noise. Keep code task-agnostic.
- Avoid redundant error handling where both branches produce the same result.
- Don't create helper functions for simple property access — every abstraction must justify its existence.
- **Handler JSDoc becomes the AWS Lambda function `description`, which is capped at 256 characters.** SST/CDK reads the leading `/** … */` block above each exported handler and sends it as the Lambda's `description` property. Exceeding 256 chars fails the deploy with `Value '<long text>' at 'description' failed to satisfy constraint: Member must have length less than or equal to 256`, and the failure cascades into "Dependency X linked to entry Y does not exist" errors on every downstream API Gateway / route / permission resource that depended on the Lambda. Keep the JSDoc one short line; put any longer rationale in a regular `//` comment below the function signature, or in a sibling design doc.
- When looking up N candidate values against the same indexed column (e.g. `external_id` from extracted tokens), prefer one query with `WHERE col IN [...]` over N point lookups. The bulk-IN form is bounded by the candidate set size, the query planner indexes it natively, and the resulting service code stays single-roundtrip.

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
- Function names should accurately describe behavior — `findChatContactsByThread` should only find contacts, not also format them.

---

## 12. Testing Expectations

- Ensure test assertions match actual implementation behavior (e.g., don't expect 404 when the implementation returns 200 with empty array).
- Test the actual behavior, not just that a value is passed through.
- Document new API fields via JSDoc or OpenAPI schema updates alongside the implementation.
- Add or update tests for new status/state combinations.

---

## 18. GitHub Actions / CI Workflow Gating (`.github/workflows/**`)

Review change-gated pipelines (jobs that skip when their change-gate is false) against these `needs:`/`if:` semantics. Getting them wrong lets a deploy run after an upstream failure, or blocks a deploy that should proceed.

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
- [ ] Queue messages carry all needed context
- [ ] No sensitive data logged
- [ ] Test/debug endpoints removed or feature-flagged
- [ ] API naming conventions respected (`camelCase` for standard, third-party naming preserved for webhooks)
- [ ] Return types only specified when strictly necessary
- [ ] YAML/frontmatter/config parsing validates mapping and field types
- [ ] Model output flags/classifications use closed vocabularies with drift checks
- [ ] Shadow logs and live routing decisions remain equivalent
- [ ] Persistence changes have real integration coverage when mocks cannot catch the failure class
- [ ] Prompt-touching changes have deterministic fixtures plus gated scenario coverage where available
- [ ] Production fixes add redacted replay or regression fixtures for the failure shape
- [ ] Missing/empty critical payload fields fail closed, same as unknown variants
- [ ] Tool config + prompt content aligned — no prompt instruction to call a tool the agent does not actually have
- [ ] CI change-gated deploy jobs guard EVERY transitive upstream stage's `result != 'failure'` (not just the immediate parent), symmetrically across envs (§18)
- [ ] `!cancelled()`/`always()` deploy jobs add explicit `needs.<gate>.result == 'success'` to block on a gate failure (§18)
- [ ] Secret-bearing workflow jobs restricted to `push` + `refs/heads/main`; per-env upload-artifact names distinct (§18)
- [ ] Caller-controlled paths validate slugs and resolved path containment
- [ ] Unknown variants, provider modes, and model routes fail fast with clear errors
