# Context compaction pilot runbook

## What this pilot does

The pilot keeps native Codex or Claude Code compaction as the owner of conversation
summarization. Around that lifecycle it captures a small metadata-and-pointer
envelope, then reconstructs from current Git/source/Batman artifacts after
compaction. The model must reopen current source before material continuation.

It never removes selected conversation turns itself. It never stores raw
transcripts, compact-summary bodies, tool inputs/outputs, source bodies, full
diffs, credentials, or secret environment values. Mnemo and handoff remain
optional locator/recovery paths; neither can broaden authority.

The source implementation is disabled by default. Real user-level activation is
Task 10 and requires a read-only exact target/content/rollback preview followed by
explicit owner approval. Codex manual recovery and rollback have real-host
evidence. Claude's guarded real startup safely rejected protected registry drift
before trust, so Claude activation, the wider matrix, and owner acceptance remain
open.

## Supported pilot seeds

- Codex `0.145.0`: standalone `context-pilot` profile, 64,000-token
  `body_after_prefix` auto-compaction seed, 12,000-token tool-output seed.
  Hosted web, image-generation, browser/computer-use, connector-app, and
  skill-dependency-install surfaces are disabled only in this profile because
  Codex local hooks cannot observe them.
- Claude Code `2.1.220`: additional settings overlay,
  `autoCompactEnabled=true`, process-local 100,000 context-window and 80-percent
  auto-compaction seeds.
- Both: canonical prompt, Pre/PostCompact and SessionStart hooks, observable tool
  journal, repository/task allowlist, 8,000-character/2,000-estimated-token
  re-entry, and local newest-200 diagnostic retention.

Seeds are experimental, not cross-host equivalence claims. Any other host version
stays inactive until compatibility is revalidated.

## Read-only planning

Create a content-free tool inventory outside the repository. Every write-capable
tool must be hook-observable; otherwise planning returns inactive.

```json
[
  {"name":"Read","write_capable":false,"hook_observable":true},
  {"name":"apply_patch","write_capable":true,"hook_observable":true}
]
```

Then run `plan` with the exact host executable and allowlisted repository:

```powershell
py -3.12 -m context_compaction plan `
  --host codex `
  --repo <repository> `
  --task-slug <task-slug> `
  --tool-inventory <inventory.json> `
  --host-executable <codex.exe> `
  --hook-trusted
```

Use `--host claude` and the Claude executable for the Claude plan. Set
`--hook-trusted` only after the host's normal trust surface has been reviewed.
`plan` is read-only and emits every target, mutation, self-hash, generated body,
launcher argument, and process-local environment value. Treat that preview as
local configuration evidence because it contains local allowlist paths.

`--task-slug` names a Batman task directory inside the allowlisted repository,
not the implementation repository running this CLI. A missing explicit slug is
preserved as `artifact_missing`; the pilot will compact but recovery stays
degraded and material tools remain blocked.

## Approval, enable, and run

After the owner approves the exact preview, pass that unchanged plan's SHA-256:

```powershell
py -3.12 -m context_compaction enable <same planning arguments> `
  --approved-plan-hash <plan_sha256>
```

The command refuses a stale plan hash, unsupported version, changed executable,
untrusted hook layer, uncovered write surface, unowned conflict, or owned-file
drift. It writes only the standalone pilot profile/overlay and host-specific
allowlist. It does not merge or rewrite primary host configuration.

Launch through the active isolated layer:

```powershell
py -3.12 -m context_compaction run <same planning arguments>
```

The launcher re-plans before execution, verifies owned contents and executable
identity, and applies Claude thresholds only to that process. Normal sandbox,
approval, credential, MCP, plugin-trust, and network boundaries still apply.
The generated hook uses an absolute bootstrap path, so it remains importable from
the allowlisted project's working directory. Any runtime tool name absent from the
approved observable inventory is denied as `uncovered_tool` before use.

Codex's normal `/hooks` trust flow appends a `[hooks.state]` section to the
standalone profile. The generator never synthesizes those trust hashes. After
the user reviews the hooks, ownership accepts only the exact five configured
hook identities, a required lowercase `trusted_hash = "sha256:<64 hex>"`, an
optional host-generated `enabled = true`, and an otherwise byte-identical
generated profile. `enabled = false`, missing/extra fields, malformed hashes, or
modified trust state remains `owned_file_drift`.

## Lifecycle and validation

Native manual `/compact` stays available on both hosts. Automatic compaction uses
the host-specific seed only while launched through the pilot layer.

After compact-sourced SessionStart, the pilot returns bounded pointer context and
requires current-source evidence before local writes or external side effects.
Codex runs this SessionStart hook before the next model request after compaction,
so an idle `/compact` may show Pre/PostCompact first and SessionStart only when
the next turn begins.
Record those relative evidence paths with:

```powershell
py -3.12 -m context_compaction validate `
  --pilot-config <host.allowlist.json> `
  --event <recovery_event_id> `
  --evidence <relative/source/path>
```

Direct host `Read` calls record evidence. Codex 0.145.0 exposes source reads
through its shell surface, so the adapter also accepts only a single-file
`cat <path>` or `Get-Content <path>` command with no flags, wrappers, globs,
pipelines, or second path. General searches and compound shell reads never count
as validation evidence.

Missing, stale, contradictory, or ambiguous state stays read-only. A completed
non-idempotent action fingerprint is never replayed automatically. An action that
was merely started becomes ambiguous and requires current-state reconciliation.

## Claude host-registry guard

Claude Code owns `~/.claude.json` and may rewrite it during ordinary startup and
interactive directory trust. The pilot never writes, copies, or reverts this
file. Immediately before Claude launch it captures only a bounded semantic
manifest of counts and hashes, then monitors registry changes while the exact
child runs.

The approved first-trust cycle permits only integer `numStartups + 1`, creation
of the exact allowlisted project subtree with
`hasTrustDialogAccepted=true`, and semantic equality everywhere else. JSON
formatting may change. Any malformed/pretrusted state, existing-project or
top-level semantic drift, noncanonical target, missing trust, or counter mismatch
terminates only the exact child and reports `host_registry_drift`; the changed
registry remains untouched for owner inspection. Guard events are content-free
and do not count as observed compaction activation.

ADR 0014 adds rejection diagnosis without adding an exception. The live guard
keeps canonical per-protected-top-level-field hashes only in process, compares
them after aggregate semantic drift, then persists only a sorted unique subset
of `existing_project_state`, `cache_state`, `authentication_metadata`,
`feature_state`, `usage_state`, `ui_state`, and `protected_top_level`. Unknown or
unsafe names collapse to `protected_top_level`; raw names, values, project paths,
and per-field hashes never enter manifests, events, status, errors, or memory.

Real Claude 2.1.220 evidence shows its bootstrap can persist protected semantics
before the later startup-counter increment. ADR 0013 intentionally rejects that
shape. Do not retry unchanged: a narrow compatibility allowance or isolated
`CLAUDE_CONFIG_DIR` strategy changes the approved contract and requires a new
Design/ADR decision plus owner approval.

One explicitly approved unchanged retry was attempted and rejected identically
before trust. Current evidence also shows the previously fingerprinted
client/model/auto-compact cache families did not change on retry. Refresh 4
approved and implemented narrower content-free field-family diagnosis. Its one
exact approved live cell rejected at 1.051 seconds with only `feature_state`,
before trust or counter increment. The exact child stopped, registry stayed
untouched by the pilot, two owned targets were disabled, and state was separately
purged. This evidence authorizes neither a retry nor a feature-state exception.

## Content-free status

```powershell
py -3.12 -m context_compaction status --host codex --repo <repository>
```

Status reports `enabled_unobserved` after owned files exist and reports `active`
only after a real host event is recorded for the exact repository fingerprint and
host version against a strict observable-tool inventory. A disable marker makes
older events ineligible to activate replacement files. Status also reports
activation/inventory evidence, counts, and the latest
metadata-only lifecycle event: host/version/model class, trigger, correlation ID,
outcome/gate, category names, size counts, truncation/degradation, and host usage
only when exposed. Unavailable values say `unmeasured`. `status` and state reads do
not create files. When present, `registry_guard` reports only the latest bounded
Claude `captured`, `validated`, or `rejected` semantic-manifest outcome. Rejected
semantic drift also reports `changed_field_categories`; non-semantic rejection
causes report an empty list.

## Disable, purge, and fresh-session recovery

Disable host activation first:

```powershell
py -3.12 -m context_compaction disable --host codex
py -3.12 -m context_compaction disable --host claude
```

State deletion is intentionally separate:

```powershell
py -3.12 -m context_compaction purge-state --repo <repository>
```

`disable` refuses drift and removes only self-verifying activation files. When
valid private state already exists, it appends one content-free deactivation
marker; it does not create state solely for disable and does not purge prior
diagnostics.
`purge-state` refuses unknown/unowned entries and never deletes source, Git work,
transcripts, Batman artifacts, handoffs, or mnemo records. For exact owned targets
and recovery, see [rollback.md](rollback.md). When immediate reconstruction is not
safe, use a fresh session or the existing pointer-first handoff skill.

## Verification labels

- `focused`: deterministic local code/fixture gate.
- `mocked`: synthetic host executable/home or injected failure.
- `qualified`: named proxy where host telemetry is unavailable.
- `unmeasured`: no credible value exists.
- `real-host`: observed native host lifecycle.
- `benchmark`: frozen representative workload result.
- `owner`: human coherence/token-reduction acceptance.

Never promote one label into another. Current evidence is indexed under the task's
`spec/evidence/` directory.
