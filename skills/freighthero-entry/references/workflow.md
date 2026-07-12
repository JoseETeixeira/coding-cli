# Governed task workflow

Classify the request as research, planning, implementation, verification, documentation, or a combination. Read-only questions do not authorize writes. Ambiguity that could change architecture, data, security, cost, rollout, or scope stays read-only until resolved.

For architecture, multi-module features, risky bugs, tracked work, or production surfaces, use the approved Batman phases:

1. Understand current behavior from Repowise and exact source.
2. Write requirements and obtain approval.
3. Write design and obtain approval.
4. Write concrete tasks and obtain approval.
5. Implement approved tasks only.
6. Test changed behavior and regressions.
7. Review the full diff using `instructions/code-review.instructions.md`.
8. Update PRD, ADR outcomes, managed wiki evidence, changelog, and operations docs.

Invalidate dependent approvals when their inputs or hashes change. Small, explicit, low-risk edits may run inline, but still require fresh Repowise evidence before repository work.
