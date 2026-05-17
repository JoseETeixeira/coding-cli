---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me". Also runs as the mandatory pre-approval pass for every Batman planning phase.
---

# Grill-Me Protocol

Stress-test a draft artifact (understanding, requirements, design, tasks) against a 9-category ambiguity taxonomy before requesting user approval. Walk every branch of the decision tree, resolve dependencies one at a time, ask questions only when the codebase cannot answer them.

## Operating Loop

1. **Load the draft** — read the artifact file (`understanding.md` / `requirements.md` / `design.md` / `tasks.md`) plus any prior approvals in the same `.batman/<task_slug>/` folder.
2. **Scan against the taxonomy** below — flag every gap, ambiguity, or unverified assumption per category.
3. **Resolve via codebase first** — for each flag, try `query-code/:search_codebase`, `:explain_code`, `Read`, or `Grep` before forming a question. If the codebase answers it, record the answer in the artifact and move on. No question fired.
4. **Rank remaining flags** by impact: architecture > testing > UX > operations > compliance. Drop low-impact items.
5. **Ask up to 5 questions per pass**, one at a time, each with a recommended answer. Pass = one round of grilling before a single approval request.
6. **Atomic append** — after every answer, write it under a `## Clarifications` section at the bottom of the artifact, timestamped (ISO `YYYY-MM-DD`). Never rewrite the body silently; preserve original wording above the Clarifications block.
7. **Stop conditions**: user says "done"/"stop"/"skip grilling"/"no questions", or 5-Q cap reached, or all CRITICAL/HIGH flags resolved. Then request explicit approval using the phase's approval phrase.

## 9-Category Ambiguity Taxonomy

Flag any draft element that fits one of these:

1. **Scope** — what's in/out, MVP boundaries, deferred work, success/exit criteria.
2. **Data model** — entities, relationships, identifiers, persistence layer, retention, ownership boundaries.
3. **UX / interface** — actor roles, surface (CLI/HTTP/UI/queue), error surfaces, observable behavior.
4. **Non-functional** — performance budgets, scale, latency, concurrency, cost, availability targets.
5. **Integrations** — upstream/downstream systems, contracts, auth boundaries, third-party deps, version pins.
6. **Edge cases** — empty/null/duplicate input, timeouts, partial failure, retries, race conditions, ordering.
7. **Constraints** — security, compliance, regulatory, platform, license, host-OS constraints.
8. **Terminology** — overloaded names, distinct-but-similar concepts (e.g., "user" vs "actor" vs "account"), source-of-truth conflicts.
9. **Completion signals** — what proves done, who verifies, what tests/metrics/logs confirm behavior.

## Question Format

- One question per turn. No batches.
- Include a **recommended answer** every time. If the recommendation is grounded in codebase evidence, cite the file/symbol.
- Prefer multiple-choice (2–5 options) when the answer space is bounded; short-phrase otherwise.
- Avoid implementation-detail questions if the answer doesn't change architecture, testing, UX, ops, or compliance.

## Clarifications Block Format

Append (never overwrite) after every answer:

```markdown
## Clarifications

### 2026-05-16 — <pass label, e.g. "Design grill pass 1">

- **[scope]** Q: Should bulk import handle CSV and JSON? → A: CSV only for v1, JSON deferred.
- **[edge]** Q: What happens on duplicate row in CSV? → A: Reject batch, return row index.
- **[nfr]** Q: Latency budget per row? → A: 5ms p95.
```

Bracket tag uses the taxonomy category. One bullet per resolved question. Keep the answer verbatim if the user gave one; otherwise quote the codebase evidence.

## Coverage Report (end of pass)

After the user answers (or stops), emit a short coverage report before the approval phrase:

```
Grill coverage:
- Resolved: scope, data-model, terminology
- Deferred: edge-cases (low impact)
- Outstanding: none
- Skipped (codebase-answered): nfr, integrations
```

Then request approval using the phase's exact approval phrase.

## Skip Path

If the user says "skip grilling" or "no questions" for the current phase, log the skip in the coverage report (`Skipped (user-directed): all`) and proceed directly to the approval request. Do not silently bypass — the skip must be visible.
