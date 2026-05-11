---
name: freighthero-projects
description: Use for FreightHero project tasks across ai_watchtower, backend, frontend, and robin-error-dashboard. Enforces codebase search/explain workflow, evidence-backed responses with source identifiers, documentation-first optimization checks, and mandatory testing/review via codeReview.instructions.md. Keywords: FreightHero, ai_watchtower, backend, frontend, robin-error-dashboard, search_codebase, explain_code, code review, testing.
---

When working on a freight hero project (ai_watchtower, backend, frontend, robin-error-dashboard) follow the rules below:

0. At the start of every session, run `cocoindex update` in the freighthero project root to refresh the codebase index before any search operations.
1. Always call #freighthero-codebase/:search_codebase with a good query derived from the user prompt.
2. Use the returned passages as the primary evidence.
3. Include source identifiers from the tool output when you reference facts.
4. If there are multiple ways to do something, check the documentation for the most optimized way given the project's constraints.
5. If you need to understand how something works, use the #freighthero-codebase/:explain_code tool
6. Do a code review following the instructions in codeReview.instructions.md for any code you generate or modify.
7. Any command that requires environment variables must be prefixed with `doppler run -c <STAGE> --` where `<STAGE>` is the appropriate config stage (e.g. `dev`, `stg`, `prd`). Never run such commands without Doppler injection — do not assume env vars are already set in the shell.
8. When creating a PR, use the nearest repo-level `.github/PULL_REQUEST_TEMPLATE.md` for the body. If absent, use `coding-cli/.github/PULL_REQUEST_TEMPLATE.md` from the FreightHero workspace as the canonical fallback. Preserve headings, remove placeholder comments, and fill every section with concrete details.
9. When adding, renaming, or moving AI Watchtower Robot workflow suites under `ai_watchtower/tests/automated/workflows/`, update `ai_watchtower/scripts/ci/select_robot_tests.py` (`ROBOT_SUITES`, label mappings, changed-file mappings), `ai_watchtower/tests/unit/scripts/test_select_robot_tests.py`, `ai_watchtower/docs/wiki/Integration-Testing.md`, and `ai_watchtower/CHANGELOG.md` so GitHub Actions exposes the available Robot tests and reviewer-owned `robot:*` labels stay accurate.
10. New AI Watchtower workflow Robot suites must import `ai_watchtower/tests/automated/workflows/resources/workflow-common.resource` and use the shared `Accelerate Load Time` keyword instead of duplicating the default Tool Belt accelerate flow.

IMPORTANT: Always ensure that any code you generate or modify is tested and reviewed through the `codeReview.instructions.md` for best practices.
