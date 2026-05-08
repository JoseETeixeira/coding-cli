---
name: karpathy-guidelines
description: Behavioral guardrails for Codex coding work. Use when writing, reviewing, refactoring, debugging, or planning code changes where hidden assumptions, overcomplication, broad diffs, or weak verification criteria could cause mistakes.
---

# Karpathy Guidelines

Use these as lightweight coding behavior guardrails. They bias toward caution and verification on non-trivial work; for obvious one-line changes, apply judgment and keep momentum.

## Operating Loop

1. Clarify the goal before editing.
   - State assumptions when they matter.
   - Ask for clarification when ambiguity changes the implementation, data model, user experience, security, cost, or migration path.
   - When a request has multiple plausible meanings, briefly name the interpretations and the implementation consequence of each.
   - Push back when a simpler or lower-risk approach clearly satisfies the goal.

2. Choose the smallest sufficient implementation.
   - Do not add features beyond the request.
   - Do not add an abstraction for a single use unless the local codebase already requires it.
   - Do not add speculative configurability, extension points, frameworks, or generic managers.
   - Do not add defensive handling for impossible states unless the code path or external boundary makes them realistic.
   - If the solution has grown large, pause and look for the simpler version before continuing.

3. Keep edits surgical.
   - Touch only files and lines that directly support the requested change.
   - Match the surrounding style, naming, patterns, and test conventions.
   - Do not reformat, rename, rewrite comments, or clean adjacent code as a drive-by change.
   - Remove dead imports, variables, helpers, and files introduced by the current change.
   - Mention unrelated pre-existing cleanup opportunities instead of silently changing them.

4. Work from verifiable success criteria.
   - Convert vague instructions into concrete expected behavior before implementation.
   - For bugs, reproduce the failure first when feasible, then make the narrow fix.
   - For refactors, identify preservation checks before changing structure.
   - For multi-step work, keep a short plan where each step has a matching check.
   - Run the most relevant tests or commands before finishing; if a check cannot run, state the reason and residual risk.

## Review Checklist

Before finalizing code changes, verify:

- Every changed line traces back to the user's request or to cleanup caused by the current edit.
- The implementation does not introduce unused flexibility or premature abstractions.
- Existing behavior outside the requested scope is preserved.
- Tests, lint, type checks, smoke checks, or manual verification match the risk of the change.
- The final response reports what changed, what was verified, and any remaining uncertainty.
