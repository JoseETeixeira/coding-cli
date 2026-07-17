---
applyTo: '**'
---

# Code Patterns & Conventions

These patterns are derived from recurring code-review feedback and represent preferred coding style. Apply the ones matching the language and stack of the file under review.

## Best-Effort Side-Effects Must Not Live in Functional Transactions

Side-effects whose failure should not block the critical path (UX reactions, notifications, logging, analytics) must be isolated from the functional dispatch they accompany. The fastest way to silently break a system is to put a best-effort call and a load-bearing call inside the same DB / queue transaction:

```ts
// ANTI-PATTERN
await db.transaction(async (transaction) => {
  await Repository.createRow(transaction, { ... });        // functional: persists the inbound row
  await Repository.createEvent(transaction, { ... });      // functional: domain event
  await externalApi.reactWithEyes({ messageId });          // BEST-EFFORT: UX reaction to Slack
  await downstreamQueue.sendMessage({ ... });              // CRITICAL: dispatches to the agent
});
```

When `externalApi.reactWithEyes` throws, the transaction rolls back. Every line above AND below rolls with it — including the queue send. The downstream agent never receives the message, retries replay the same failure, and the message dead-letters with zero functional record. The symptom in production looks like "the agent didn't answer and didn't react", which masks the upstream side-effect failure as a downstream agent bug.

Apply ONE of these (in preference order):

1. **Move the best-effort call outside the transaction.** If the reaction / notification doesn't need transactional consistency with the DB writes, fire it after the transaction commits.
2. **Wrap the best-effort call in `try / catch`** that logs the failure and continues. Critical path still runs.
3. **Use an outbox-style queue** for the best-effort call: write a row inside the transaction, dispatch the side-effect from a separate worker that can fail in isolation.

Detection: when a downstream agent / worker shows zero traces for a request that definitely entered the system (webhook delivered, BE log shows the inbound), and the upstream service has retry events that all fail identically, suspect a transaction-wrapped side-effect blocking the dispatch. The Sentry trail will show the side-effect's error N times (once per SQS retry) while the downstream trail is silent.

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
const details = Array.isArray(account_details) ? account_details[0] : account_details;
if (existingDetails) { update() } else { create() }

// Do this (trust the relation)
const { account_details } = company;
await db.account_details.updateOne({ ... });
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
- For a closed set of domain values, prefer a `const enum` over a string-literal union type. Reference enum members in maps/comparisons (`status === TaskStatus.Scheduled`), not raw string literals. The enum's string values still match the wire payload, so the API contract is unchanged.

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
- Don't add comments that describe what the code obviously does — only use comments for non-obvious decisions.
- Keep comments as succinct as possible while still being informative. Prefer 1–3 lines capturing what + why over paragraphs narrating the call chain or every downstream consequence. Reserve longer comments for genuinely non-obvious tradeoffs that won't fit in three lines.
- When implementing code that extracts fields from a structured store (Terraform state, JSON-RPC results, k8s manifests, AWS API responses), verify each field's actual storage location against a live instance before shipping — don't infer location by analogy to sibling fields. Storage rules can be orthogonal to naming (Terraform workspaces partition some resources but not data sources; k8s cluster-scoped resources ignore namespace selectors). One live read of a real instance catches these silently divergent layouts before they ship as empty strings to downstream consumers.
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
- Function names should accurately describe behavior — `findChatContactsByThread` should only find contacts, not also format them.

---

## 12. Testing Expectations

- Ensure test assertions match actual implementation behavior (e.g., don't expect 404 when the implementation returns 200 with empty array).
- Test the actual behavior, not just that a value is passed through.
- Document new API fields via JSDoc or OpenAPI schema updates alongside the implementation.
- Add or update tests for new status/state combinations.

---
