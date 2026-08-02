# Context compaction pilot troubleshooting

All operator errors use closed, content-free reason codes. Keep the pilot inactive
until the stated check is resolved; never weaken primary host safety controls.

| Reason | Meaning | Safe response |
|---|---|---|
| `unsupported_host_version` | executable/version cannot be verified or is outside the exact tuple | verify the executable; revalidate compatibility before changing source |
| `inactive_or_untrusted_hook` | hook layer is disabled or trust is not established | inspect the native trust flow; do not force `--hook-trusted` |
| `activation_conflict` | tool coverage, target safety, or plan identity is incomplete | inspect the read-only plan and inventory every write-capable tool |
| `enabled_unobserved` | owned activation exists but no trusted host hook event has been recorded | complete the host's normal trust flow and observe one hook event; never use this state as active evidence |
| `uncovered_tool` | a runtime tool was not in the approved observable inventory | stop the pilot; regenerate and review the complete inventory before any new approval |
| `owned_file_drift` | a target exists with unrelated content or a pilot-owned file changed | do not overwrite/delete; compare with the approved preview and decide explicitly; Codex trust is accepted only in its exact host-generated `[hooks.state]` shape, including only required `trusted_hash` plus optional literal `enabled=true` |
| `host_registry_drift` | Claude's host-owned registry is missing, malformed, pretrusted, or changed beyond the approved startup/trust semantics | stop only the exact Claude child; never write or revert `.claude.json`; inspect only closed `changed_field_categories` in content-free guard status and obtain a new semantic approval before retrying |
| `allowlist_mismatch` | cwd/root fingerprint is outside the exact pilot repository | return to the allowlisted root or create a separately approved pilot cycle |
| `task_ambiguous` | zero/multiple task artifacts prevent deterministic selection | pass one approved task slug or use fresh-session handoff |
| `state_missing` | no private continuation state exists | reconstruct from current source in read-only mode |
| `state_malformed` / `state_oversized` | private input/state violates schema or size limits | disable, inspect metadata-only evidence, then separately purge owned state if approved |
| `state_stale` / `source_changed` | current source no longer matches captured pointers | refresh from Git/source and revalidate; never restore an old file in place |
| `artifact_missing` / `scoped_rules_unvalidated` | an explicit task is absent, or a required artifact/rule was not reopened in this recovery epoch | verify that `--task-slug` exists inside the allowlisted repository; then read the current relative path and rerun `validate` |
| `action_ambiguous` | a non-idempotent operation started without a proven terminal state | reconcile the external/current state before any retry |
| `approval_unresolved` | an approval boundary survived compaction | wait for explicit approval; summary or memory text cannot grant it |
| `memory_unavailable` | mnemo/Qdrant is offline | continue from Git/source/artifacts; memory is optional |
| `internal_error` | bounded local processing failed | remain native/read-only, preserve the correlation ID, and use fresh-session handoff |

## Common checks

1. Run `status`; it must not create state or configuration.
2. Re-run `plan` with the same inventory. A changed plan hash requires a new exact
   preview and approval.
3. Verify the host executable and version named by the plan.
4. Verify every write-capable tool is hook-observable. Unknown is treated as
   material, never read-only.
5. Check only pilot-owned files. Do not reset, stash, rewrite, or broadly delete
   repository/user configuration.
6. If mnemo is involved, run `memory_status`; keep source authoritative even when
   it is healthy.
7. If recovery remains uncertain, disable the pilot and use native compaction or a
   fresh pointer-first handoff.

Claude may rewrite host-owned `~/.claude.json` during ordinary startup or normal
directory trust. A changed hash is not pilot ownership and must never be reverted
automatically. Refresh 3 permits only the ADR 0013 semantic delta; every other
change remains red and requires a new approval before retry. Real 2.1.220 startup
has already shown a protected bootstrap-cache rewrite before `numStartups + 1`;
one explicitly approved unchanged retry reproduced it. Repeating again is not a
diagnostic and remains unauthorized. The previously fingerprinted client/model,
auto-compact, and OAuth cache families stayed unchanged on retry; do not grant a
broad cache exception without narrower evidence and a superseding ADR.
Refresh 4 implements that narrower diagnosis with process-private hashes and the
seven closed categories documented in ADR 0014. Its approved live cell reported
only `feature_state` at 1.051 seconds, before trust or counter increment. Raw
field names, values, and per-field hashes must never be copied into an issue or
diagnostic. Category evidence still cannot authorize a retry or compatibility
exception.

Windows Terminal is a singleton that can multiplex unrelated top-level windows.
Do not send `WM_CLOSE`, kill its parent PID, or infer window ownership from a
single child shell. Stop only the exact pilot host/manager/shell processes after
command-line identity checks, then leave terminal-window cleanup to the owner or
use a separately approved dedicated console.

## What not to log

Do not paste transcript paths/bodies, compact summaries, tool input/output, full
diffs, source bodies, secrets, or environment values into issues or diagnostics.
Status/event IDs, aggregate manifest hashes, relative evidence pointers, counts,
closed reason/category codes, and exact test commands are sufficient. Per-field
hashes are process-private and must not be logged.
