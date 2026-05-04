---
name: freighthero-projects
description: Use for FreightHero project tasks across ai_watchtower, backend, frontend, and robin-error-dashboard. Enforces codebase search/explain workflow, evidence-backed responses with source identifiers, documentation-first optimization checks, and mandatory testing/review via codeReview.instructions.md. Keywords: FreightHero, ai_watchtower, backend, frontend, robin-error-dashboard, search_codebase, explain_code, code review, testing.
---

When working on a freight hero project (ai_watchtower, backend, frontend, robin-error-dashboard) follow the rules below:

1. Always call #freighthero-codebase/:search_codebase with a good query derived from the user prompt.
2. Use the returned passages as the primary evidence.
3. Include source identifiers from the tool output when you reference facts.
4. If there are multiple ways to do something, check the documentation for the most optimized way given the project's constraints.
5. If you need to understand how something works, use the #freighthero-codebase/:explain_code tool
6. Do a code review following the instructions in codeReview.instructions.md for any code you generate or modify.

IMPORTANT: Always ensure that any code you generate or modify is tested and reviewed through the `codeReview.instructions.md` for best practices.
