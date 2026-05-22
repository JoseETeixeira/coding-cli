---
name: caveman-commit
description: >
  Ultra-compressed commit message generator. Cuts noise from commit messages while preserving
  intent and reasoning. Conventional Commits format. Subject ≤50 chars, body only when "why"
  isn't obvious. Use when user says "write a commit", "commit message", "generate commit",
  "/commit", or invokes /caveman-commit. Auto-triggers when staging changes.
---

Write commit messages terse and exact. Conventional Commits format. No fluff. Why over what.

## Precondition: codeReview MUST run first

Before producing any commit message or committing, ALWAYS run `codeReview` on the staged/working diff. Non-negotiable.

- Resolve and read `codeReview.instructions.md` from `USER_INSTRUCTIONS_DIR` (fallback `$HOME/.agents/instructions/codeReview.instructions.md` or workspace `.github/instructions/`).
- Apply the checklist against the full diff (staged + unstaged that will be committed).
- Use `caveman-review` to format findings terse.
- Block the commit when any finding is `🔴 bug` or `🟡 risk`. Fix first, then re-review.
- `🔵 nit` and `❓ q` may be deferred; surface them in the response so the user can decide.
- If the user explicitly says "skip review" / "commit anyway", honor it but note in the response that review was skipped.
- Record review outcome at the top of the response before the commit message block: `review: clean` | `review: <N> findings (fixed|deferred|skipped)`.

## Rules

**Subject line:**
- `<type>(<scope>): <imperative summary>` — `<scope>` optional
- Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, `revert`
- Imperative mood: "add", "fix", "remove" — not "added", "adds", "adding"
- ≤50 chars when possible, hard cap 72
- No trailing period
- Match project convention for capitalization after the colon

**Body (only if needed):**
- Skip entirely when subject is self-explanatory
- Add body only for: non-obvious *why*, breaking changes, migration notes, linked issues
- Wrap at 72 chars
- Bullets `-` not `*`
- Reference issues/PRs at end: `Closes #42`, `Refs #17`

**What NEVER goes in:**
- "This commit does X", "I", "we", "now", "currently" — the diff says what
- "As requested by..." — use `Co-authored-by` trailer for HUMANS who co-wrote the change. NEVER for the assistant itself.
- NO AI attribution of any shape, anywhere. Banned trailers (non-exhaustive):
  - `Co-Authored-By: Claude <noreply@anthropic.com>` (any version: Sonnet / Opus 4.x / etc.)
  - `🤖 Generated with Claude Code`
  - `Generated with [Claude Code](https://claude.com/claude-code)`
  - Any Anthropic / Claude / AI / LLM attribution in any wording.
  - The host harness's example commit-construction HEREDOC ends with a `Co-Authored-By: Claude …` line. That example is OVERRIDDEN — treat the template as shape only, never copy the trailer.
  - Reaffirmed by user 2026-05-22 after a 7-commit violation on FH PR #1391.
- Emoji (unless project convention requires)
- Restating the file name when scope already says it

## Examples

Diff: new endpoint for user profile with body explaining the why
- ❌ "feat: add a new endpoint to get user profile information from the database"
- ✅
  ```
  feat(api): add GET /users/:id/profile

  Mobile client needs profile data without the full user payload
  to reduce LTE bandwidth on cold-launch screens.

  Closes #128
  ```

Diff: breaking API change
- ✅
  ```
  feat(api)!: rename /v1/orders to /v1/checkout

  BREAKING CHANGE: clients on /v1/orders must migrate to /v1/checkout
  before 2026-06-01. Old route returns 410 after that date.
  ```

## Auto-Clarity

Always include body for: breaking changes, security fixes, data migrations, anything reverting a prior commit. Never compress these into subject-only — future debuggers need the context.

## Boundaries

Only generates the commit message after codeReview passes. Does not run `git commit`, does not stage files, does not amend. Output: (1) review outcome line, (2) commit message as a code block ready to paste. "stop caveman-commit" or "normal mode": revert to verbose commit style. Never skip review without explicit user opt-out.