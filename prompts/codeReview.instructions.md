# Code Review Instructions

Guidelines distilled from recurring code-review patterns. Apply only the sections that match the technology stack of the diff under review; treat unmatched sections as inapplicable.

---

> **Sections 1–12** (Repository, Types, Null/Undefined, Errors, API Response, Service Boundaries, Framework, Hygiene, Queue, Redundant Query, Naming, Testing) live in [`code-patterns.md.instructions.md`](./code-patterns.md.instructions.md). Apply those rules in addition to sections 13–16 below.

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
- [ ] Caller-controlled paths validate slugs and resolved path containment
- [ ] YAML/frontmatter/config parsing validates mapping and field types
- [ ] Unknown variants, provider modes, and model routes fail fast with clear errors
- [ ] Persistence changes have real integration coverage when mocks cannot catch the failure class
- [ ] Production fixes add redacted replay or regression fixtures for the failure shape
