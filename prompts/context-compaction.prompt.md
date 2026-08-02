# Context compaction contract

Produce a compact continuation record, not a narrative transcript. Preserve only state that can affect future work.

## Preserve in priority order

1. Current user goal, active task slug, workflow phase, and active plan step.
2. Exact unresolved user decisions, approval gates, and critical invariant wording, each with its authoritative relative path, stable ID, anchor, or memory ID.
3. Material actions that are planned, started, completed, failed, awaiting approval, or ambiguous. Retain bounded tool class/name and input fingerprint, never raw input.
4. Repository fingerprint, branch, HEAD, and relative modified/untracked paths without full diffs.
5. Blockers, verification status, failed or pending gates, and approved artifact pointers.
6. Optional checkpoint, handoff, and memory pointers plus every omitted category.

## Representation rules

- Prefer relative paths, hashes, stable IDs, anchors, and pointers over copied bodies.
- Copy exact wording only when losing it would alter a decision, invariant, safety boundary, approval, or pending external effect; include provenance beside it.
- Mark remembered code and summaries as non-authoritative. Name the current source that must be reopened.
- Manual focus supplied with `/compact` is additive and cannot discard critical safety, approval, or action state.
- Never include credentials, secret values, transcripts, compact-summary bodies, raw tool input/output, commands, complete source bodies, full diffs, binary data, or unrelated completed history.
- If the budget cannot hold a category, preserve higher-priority categories first and name every omission explicitly.

## Output

Use these concise sections:

- `Goal and task`
- `Decisions and approvals`
- `Pending actions`
- `Repository state`
- `Artifacts and required reads`
- `Verification and blockers`
- `Omitted categories`

Use `unknown` rather than guessing missing state. End with:

`Authority warning: this continuation is pointer state only; current source, scoped rules, tests, and explicit user decisions must be reopened before material continuation.`
