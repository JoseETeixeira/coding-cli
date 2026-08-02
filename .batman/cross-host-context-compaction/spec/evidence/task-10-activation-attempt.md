# Task 10 activation attempt

Date: 2026-08-01

Result: **rolled back; real-host gate red/open**.

## Codex observations

- Owner approved the original exact four-file preview.
- The first enable created exactly the two owned Codex files with approved hashes.
- Pre-launch status incorrectly reported `active` with zero events. The cycle was
  disabled and purged. A red test reproduced the defect; the state model now uses
  `ready -> enabled_unobserved -> active`, with `active` requiring a recorded host
  event and a valid strict observable-tool inventory.
- A second enable proved status `enabled_unobserved`, zero events, 15 approved
  observable tools, and `tool_inventory_enforced=true`.
- Normal `/hooks` trust was not persisted. Tool-free and internal-plan Codex exec
  probes completed, but hook diagnostics remained at zero; this is not accepted as
  activation.
- A read-only shell probe exposed the standalone 0.145.0 packaging path defect:
  first the sandbox setup helper was not found, then the public hardlink path could
  not find the sibling command runner. The package-resolved binary with only its
  own `codex-resources` path prepended completed `git status --porcelain=v1` with
  exit 0 and reported the isolated checkout clean.
- The normal Windows sandbox setup applied its standard ACL preparation to the
  isolated checkout and read access for `.claude.json`; no file body or Git state
  changed. No ACL rollback was attempted because there was no safe pre-run ACL
  snapshot and the standard sandbox owns those entries.
- Codex was disabled again and pilot state separately purged. Both owned Codex
  targets are absent.

## Preservation and conflict

- `C:\Users\josee\.codex\config.toml` stayed at SHA-256
  `7f0ee4673abfe45c36cad051f7f77fbd1e63300f1776b097f0d5d7f58ee8178c`.
- `C:\Users\josee\.claude\settings.json` stayed at SHA-256
  `fc4451db75e7f13562a1ef043424bcd8d417848878f11a74eb53c5cb7dd9fdaa`.
- `.claude.json` changed concurrently from the approved
  `6e843e98e3b666214da8676ded7ad573de75c15f8f4461055238244b3debfc6d`
  baseline to
  `631bc992e42fa8e6fe6c8b68b1a77d0511fe711e333f80eb929c111426a1820c`.
  It contains no exact pilot target mention. The cause is not established, so the
  pilot preserved it and invalidated the remaining approval instead of reverting.
- Both the active `educode` checkout and isolated `educode.context-pilot` checkout
  remain clean at `0db30624dd32d814b937aa88b5ec84e18d4b130d`.
- Claude activation was not started. All four proposed user-level targets are
  absent while Refresh 1 awaits approval.

## Classification

- Deterministic state/inventory correction: focused green.
- Codex package-path diagnostic: real executable, read-only command, qualified
  diagnostic only.
- Codex normal trust, lifecycle, manual/automatic compaction: red/open.
- Claude activation and lifecycle: unmeasured/open.
- Owner coherence and token-reduction acceptance: open.

## Refresh 1 approved live Codex cycle

Refresh 1 was approved and enabled against the isolated checkout. Normal
interactive `/hooks` trust appended Codex-owned `[hooks.state]` entries to the
standalone profile. Primary `config.toml` did not change. The original exact-file
validator reported this expected host write as `owned_file_drift`, so the exact
pilot process was stopped without rollback. A red characterization test was
added, then ownership was narrowed to accept only an unchanged generated prefix
plus all five expected hook-state keys, each containing only one lowercase
`sha256:<64 hex>` value. The generator still emits no trust hashes. Activation
and security regressions passed 22/22; focused Ruff passed.

The trusted profile then reported two owned targets, zero drift, strict 15-tool
inventory, and `enabled_unobserved`. One synthetic no-tool turn followed by
manual `/compact` produced real host events:

- `PreCompact/manual`: event `e009dc08-11e5-4485-8330-fa1f5e081f52`, 189 ms,
  degraded with `artifact_missing`.
- `PostCompact/manual`: event `51850196-1b76-4835-9cc6-34c1298f579b`, 10 ms,
  recorded.
- The next model request produced `SessionStart/compact`: event
  `2d39ecf2-f2d7-43b5-ac0b-9fbed499b948`, 182 ms, 528 re-entry characters,
  132 estimated tokens, all six bounded categories included, no truncation.

This proves normal Codex trust and manual lifecycle wiring, but not valid
recovery. The approved allowlist used `cross-host-context-compaction`, a task in
the implementation repository, while the allowlisted target repository contains
`agentic-development-workbench`. The resolver therefore correctly retained
`artifact_missing`. Three real Bash launch attempts were denied before execution
while the recovery gate was degraded. The retry loop was interrupted; no target
repository file changed.

Disable removed exactly the two Codex pilot files, including disposable normal
trust state. Separate purge removed seven metadata-only diagnostic events. All
four activation targets are absent, the isolated checkout is clean, and primary
hashes are exactly:

- Codex `config.toml`: `7f0ee4673abfe45c36cad051f7f77fbd1e63300f1776b097f0d5d7f58ee8178c`.
- Claude `settings.json`: `fc4451db75e7f13562a1ef043424bcd8d417848878f11a74eb53c5cb7dd9fdaa`.
- Claude `.claude.json`: `631bc992e42fa8e6fe6c8b68b1a77d0511fe711e333f80eb929c111426a1820c`.

During cleanup, the user-level Codex wrapper changed concurrently to 0.146.0.
Planning correctly returns `unsupported_host_version`; no 0.146 activation was
attempted. The previously approved package binary remains present and unchanged
at version 0.145.0 / SHA-256
`83751f15cb6a0a7b97df67752c001e3fe1c20e18ffbfec3ff63567296205eb6c`.

Updated classification:

- Codex 0.145.0 normal trust, manual Pre/PostCompact, compact SessionStart, and
  user-level rollback: real-host observed.
- Valid recovery and source validation: red/open because the approved task slug
  named the wrong repository.
- Fail-closed material-tool gate: real-host observed; validated read/write tool
  continuation remains open.
- Codex automatic/mid-turn and every Claude real-host cell: open/unmeasured.

## Refresh 2 approved valid Codex cycle

Refresh 2 changed only the allowlisted task slug to the repository-native
`agentic-development-workbench` and pinned the unchanged Codex 0.145.0 package
binary. The approved plan hash was
`2379e98a8d541d992fdf719be4164e7e6d4897af5965aa384b750a32529e2132`.
Enable created exactly two files, status reported `enabled_unobserved`, and the
normal interactive `/hooks` flow supplied all five trust identities.

One host entry also contained `enabled = true`. The strict validator stopped the
exact process on that previously uncharacterized shape. A red test was added,
then ownership was narrowed to require `trusted_hash`, permit only optional
literal `enabled=true`, and reject `false`, extra fields, malformed hashes, or
changed identities. The generator still synthesizes no trust state.

A synthetic no-tool turn followed by native manual `/compact` produced:

- `PreCompact/manual`: `f0161fa7-bca1-4d43-a401-eedf3fab0744`, 235 ms,
  `captured`, no degradation.
- `PostCompact/manual`: `18f160fc-5be8-4774-ba59-116857949ac2`, 3 ms,
  `recorded`, no degradation.
- Next-request `SessionStart/compact`:
  `b4d6dd27-3ba5-45fc-9f2c-ea9d974f43d2`, 199 ms, 3,556 re-entry
  characters, 889 estimated tokens, all six categories included, no omission,
  truncation, or degradation, gate `validation_required`.

The recovered envelope named exactly five current-source pointers: the isolated
task's understanding, requirements, design, and tasks files plus root
`AGENTS.md`. Codex 0.145.0 exposes these reads through `shell_command`, not a
direct `Read` tool. A red characterization test therefore added evidence capture
only for strict two-token `cat <path>` or `Get-Content <path>` commands. Compound,
flagged, globbed, multi-path, search, and outside-root commands remain ineligible.

All five exact files were then reopened in the real Codex session and their
current-epoch hashes recorded. Validation returned `validated` with no degraded
reasons (`17fb2abb-7ed7-4f1b-9943-9cdd37201ea0`). A subsequent
`git status --short` ran under validated Pre/PostToolUse events
`59a52180-15b2-49c2-8721-546473a13e3c` and
`835ee985-2c13-4910-bb77-a2e212da0a36`; it reported the isolated checkout clean.

`/exit` ended only pinned Codex PID 130084. Disable removed exactly the two owned
Codex files, separate purge removed only pilot state, and the encoded pilot shell
was closed by exact PID/command identity. All four activation targets were absent,
the isolated repository remained clean at
`0db30624dd32d814b937aa88b5ec84e18d4b130d`, and primary hashes remained:

- Codex `config.toml`: `7f0ee4673abfe45c36cad051f7f77fbd1e63300f1776b097f0d5d7f58ee8178c`.
- Claude `settings.json`: `fc4451db75e7f13562a1ef043424bcd8d417848878f11a74eb53c5cb7dd9fdaa`.
- Claude `.claude.json`: `631bc992e42fa8e6fe6c8b68b1a77d0511fe711e333f80eb929c111426a1820c`.

The full deterministic suite passed 125 tests in 68.38 seconds after both
real-host discoveries.

## Refresh 2 Claude preservation stop

Claude 2.1.220 revalidated exact plan
`46381b248d97ebbe657ca1f94878e80a1f19962b46daffdf4cb8b0338cef2864`,
binary SHA-256
`af5bf1f1b2aadffc768eccd787084c6fdf9ba81624cbe96c1c6d9ac1a1550231`,
26 observable tools, two absent targets, exact primary hashes, and a clean frozen
repository. Enable created only the approved overlay and allowlist and reported
`enabled_unobserved`.

Ordinary Claude startup changed host-owned `C:\Users\josee\.claude.json`
before any trust input or lifecycle hook. It changed from 63,730 bytes / SHA-256
`631bc992e42fa8e6fe6c8b68b1a77d0511fe711e333f80eb929c111426a1820c`
to 63,729 bytes / SHA-256
`2391a9a9333b3c290b468e2b31a63a11bc1058032b36d57ddac3602b4edfe35f`.
The resulting registry contains no `educode.context-pilot` project entry. No
pilot event was recorded and no synthetic prompt or trust keystroke was sent.

Exact Claude, manager, and encoded shell PIDs were stopped after command-line
identity checks; the shared Windows Terminal parent was untouched. The changed
registry was preserved, not reverted. Disable removed exactly the two Claude
owned files and separate purge removed only owned pilot state. The isolated
checkout stayed clean; Codex `config.toml` and Claude `settings.json` retained
their hashes above. A fresh read-only plan remains `ready` at the unchanged
Claude plan hash and both Claude targets remain absent.

Classification: Claude lifecycle remains red/open. Normal startup makes an
exact-byte invariant for `.claude.json` infeasible; any narrower semantic
preservation rule is a contract change and requires a refreshed exact preview and
explicit approval before another launch.

## Terminal cleanup incident

After the exact Codex and Claude child processes had ended, accessibility
inspection proved handle 19925134 contained only the exited Codex 0.145.0 pilot.
Posting `WM_CLOSE` to that exact stale window unexpectedly terminated Windows
Terminal's singleton PID 41532. A separate top-level `✳ Batman Agent` window on
the same singleton also closed. Both handles and the terminal process are gone;
no automatic relaunch was attempted and its conversation/process state cannot be
recovered by this pilot.

The activation targets remained absent, pilot state remained purged, no pilot
process remained, the isolated repository stayed clean, and primary file hashes
did not change during this cleanup incident. This is nevertheless a red operator
safety failure: exact window-handle identity is insufficient when Windows
Terminal multiplexes unrelated windows in one singleton process. Future live
testing must not close a Windows Terminal top-level window programmatically.
Use an owner-created terminal or a separately approved dedicated console process,
exit only the exact host/manager/shell children, and leave terminal-window cleanup
to the owner.

## Refresh 3 approved semantic-guard cycle

Refresh 3 implemented ADR 0013 before any new live launch. Focused guard and
activation tests ultimately passed 32/32, selected
security/storage/documentation/workflow tests passed 28/28, Ruff was clean, and
the final deterministic `tests/context_compaction` suite passed 137 tests in
57.52 seconds. The final increment covers removal of a duplicate pre-guard
Claude plan/version probe from `run`.

Fresh content-free preflight proved:

- all four activation targets and pilot state were absent;
- the isolated repository was clean at
  `0db30624dd32d814b937aa88b5ec84e18d4b130d`;
- Claude 2.1.220 binary SHA-256 remained
  `af5bf1f1b2aadffc768eccd787084c6fdf9ba81624cbe96c1c6d9ac1a1550231`;
- the ready plan remained exactly
  `46381b248d97ebbe657ca1f94878e80a1f19962b46daffdf4cb8b0338cef2864`,
  with overlay `4c0699b0d7318f262a26f8a60bdf56937419a14c9144ba0f9aec40a7f8bb047d`
  and allowlist `a1034fd250b63f1c7db0bd9faf98906d01c1a91ee339ff72cc99097e92f5829e`;
- the registry baseline was 63,729 bytes / SHA-256
  `2391a9a9333b3c290b468e2b31a63a11bc1058032b36d57ddac3602b4edfe35f`,
  semantic SHA-256
  `219e33f69ceb85418c5c83583d59025750e18c67578ef59b3160f2af4a3a0f89`,
  `numStartups=30`, and target absent. Content-free manifest SHA-256 was
  `44bec628fa08b9ce3adbf882649c1039d3f77bdd0aecc60e1076793d0fec7c0b`.

Enable created exactly the two approved Claude files and reported
`enabled_unobserved`, zero lifecycle events, 26 observable tools, and enforced
inventory. Launch used a separately approved classic `conhost.exe` console, not
Windows Terminal. No trust input or synthetic prompt was sent.

The guard captured event
`814fd2f3-1177-47a1-ac8e-131d4e18594d` in 2 ms. About 1.055 seconds after child
start, ordinary Claude bootstrap rewrote protected registry semantics. The guard
emitted rejected event `40789995-c38c-4aa7-abca-93fa18ba150f` with
`registry_semantic_drift` / `host_registry_drift`, terminated only the exact
Claude child, and did not revert the file. The resulting registry was 63,786
bytes / SHA-256
`e58920c51ec71a5787d0d07825b2e69436c0c00d12164bb2a95d2c84cbe37f2c`,
semantic SHA-256
`7ad0451aedccebbc9a0f5a749be968fd49e914e17355030b26eb24e722f538b2`,
still `numStartups=30`, with the target still absent.

Read-only string inspection of the exact installed binary showed that its
bootstrap can persist `clientDataCacheSlots` and model/cache fields before the
later `numStartups + 1` write. The content-free baseline intentionally retained
no registry body or per-field values, so the exact changed field is not claimed.
That ordering explains why Refresh 3's approved monitor rejected before either
the counter increment or interactive trust.

Disable removed exactly the two owned Claude targets. Separate purge removed
only the two content-free guard events. All four activation targets and pilot
state are absent; no Claude/pilot-manager child remains; the isolated checkout
is clean. Codex `config.toml` remains
`7f0ee4673abfe45c36cad051f7f77fbd1e63300f1776b097f0d5d7f58ee8178c`
and Claude `settings.json` remains
`fc4451db75e7f13562a1ef043424bcd8d417848878f11a74eb53c5cb7dd9fdaa`.
The changed `.claude.json` remains preserved at `e58920c...`. Dedicated console
PIDs 138096 (`conhost.exe`) and 11140 (`powershell.exe`) were deliberately left
for owner cleanup; no top-level window was closed programmatically.

Classification: semantic-guard implementation and exact owned-target rollback
are green; registry preservation and Claude lifecycle remain red/open. Repeating
the same launch would reproduce a
known rejected shape. Permitting selected host-cache changes, deferring semantic
validation, or redirecting `CLAUDE_CONFIG_DIR` changes the approved contract and
requires a new Design/ADR decision plus explicit owner approval.

## Owner-approved unchanged retry

The owner explicitly replied `retry approved`, authorizing exactly one guarded
retry against the preserved warmed registry baseline without changing ADR 0013,
the plan, allowlist, tools, environment, trust flow, or rollback set. Current
source and this explicit decision overrode the earlier no-retry checkpoint for
this one attempt.

Preflight again proved all four activation targets and pilot state absent, no
pilot process, a clean isolated repository at
`0db30624dd32d814b937aa88b5ec84e18d4b130d`, unchanged primary Codex/Claude
settings hashes, and unchanged plan
`46381b248d97ebbe657ca1f94878e80a1f19962b46daffdf4cb8b0338cef2864`.
The plan's single `claude --version` probe left the registry byte-identical.
Retry baseline was 63,786 bytes / SHA-256
`e58920c51ec71a5787d0d07825b2e69436c0c00d12164bb2a95d2c84cbe37f2c`,
semantic SHA-256
`7ad0451aedccebbc9a0f5a749be968fd49e914e17355030b26eb24e722f538b2`,
`numStartups=30`, target absent, with content-free manifest SHA-256
`c0b20a2ef9affc773cbe1c2711432be583420cad313381e02faf2cfa1d1fe062`.

Enable again created only the exact overlay and allowlist. A new dedicated
classic `conhost.exe` console launched the manager. The guard captured event
`eacc8705-3417-4474-98b9-9eb289bd936b` in 1 ms. At 1.054 seconds, before trust,
counter increment, or lifecycle evidence, Claude again changed protected
semantics. Rejected event `5cf07b5b-162e-48ce-baa5-86e3ce692876` reported
`registry_semantic_drift` / `host_registry_drift` and stopped only the exact
Claude child.

Post-retry registry remained 63,786 bytes but changed to SHA-256
`33a35b780c651b05f02e028cd81beb3657a837f98b10fc515b1b67adde45bed4`
and semantic SHA-256
`1d5e68140a782cff40d44daa0a3832ba7f570866df93b04b537c98ef59e27ec5`.
`numStartups` remained 30 and the target remained absent. Content-free
fingerprints for `clientDataCacheSlots`, `additionalModelOptionsCache`,
`additionalModelCostsCache`, `modelAccessCache`, `orgModelDefaultCache`,
`autoCompactWindowsCache`, and `oauthAccount` were unchanged from the prior
post-startup inspection. The exact protected field therefore remains
unidentified; no registry body or values were retained to infer it.

Disable removed exactly two owned targets and separate purge removed exactly the
two bounded guard events. All activation targets and state are absent, isolated
Git remains clean, primary Codex config and Claude settings retain their hashes,
and no exact Claude/manager child remains. The changed registry was preserved,
not reverted. Dedicated console PIDs 102936 (`conhost.exe`) and 109412
(`powershell.exe`) were left for owner cleanup; no terminal window or unrelated
process was closed.

Classification: unchanged retry is red and confirms the blocker is repeatable,
not a one-time cache warm-up. No third launch is authorized. Any next attempt
requires source changes for narrower content-free field diagnosis and a
superseding Design/ADR decision about permitted host state or configuration
isolation, followed by explicit owner approval.

## Refresh 4 deterministic diagnostic implementation

The owner explicitly approved `Refresh 4 diagnostic design`. Design 1.2.0 and
accepted ADR 0014 authorize source, tests, and documentation only. They do not
authorize a Claude launch, registry exception, or isolated configuration.

Characterization first kept the existing guard/activation surface green: 32
tests passed in 2.17 seconds. New tests then failed as expected because
`ClaudeRegistryError` had no `changed_field_categories`. The minimal
implementation now:

- removes approved `numStartups` and the exact target subtree before computing
  one canonical SHA-256 per protected top-level field;
- retains that field-to-hash map only inside the live guard object;
- converts changed field names in process to a sorted unique subset of the seven
  ADR 0014 categories, with unknown/unsafe names becoming
  `protected_top_level`;
- persists only `changed_field_categories`, never raw field names, values, or
  per-field hashes; and
- leaves ADR 0013 acceptance, exact-child termination, and no-revert behavior
  unchanged.

Verification:

- guard, activation, and model tests: 46 passed in 2.45 seconds;
- selected privacy, fault, storage, and contract tests: 68 passed in 11.47
  seconds;
- documentation and contract tests: 10 passed in 0.07 seconds;
- full deterministic suite: 146 passed in 57.78 seconds;
- Ruff: clean; `git diff --check`: clean.

Security assertions cover known category families, multi-field sorting,
unknown-name collapse, empty categories for non-semantic capture rejection,
exact-child rejection, no registry revert, and absence of raw identity, value,
or per-field fingerprint from error, event state, and bounded status.

Phase 7 review found one diagnostic-completeness gap: if a child exited directly
after protected drift, final validation could report missing trust/counter state
before attaching changed-field categories. It also found that the generic
`DiagnosticEvent` dataclass typed category strings without runtime closure. New
RED regressions reproduced both. The fix preserves the original rejection code
while attaching any independently observed protected-drift categories, and adds
one shared closed enum plus sorted/unique validation to the generic model.

Final post-review verification supersedes the initial counts above:

- review regressions: 5 passed in 0.07 seconds;
- guard, activation, and model tests: 50 passed in 2.77 seconds;
- selected privacy, fault, storage, and contract tests: 72 passed in 13.15
  seconds;
- final documentation and contract tests: 10 passed in 0.09 seconds;
- full deterministic suite: 150 passed in 65.49 seconds;
- Ruff and `git diff --check`: clean.

No interactive/pilot Claude child was started, no activation target was enabled,
and no host-owned configuration or registry was modified during Refresh 4
implementation. The later exact read-only preview invoked only the verified
`claude --version` probe and re-proved byte-identical host state. At that point,
Task 10 remained red/open pending the separately approved cell recorded below.

## Refresh 4 owner-approved diagnostic live cell

The owner explicitly replied `Refresh 4 diagnostic launch approved`, authorizing
one cell against exact plan
`46381b248d97ebbe657ca1f94878e80a1f19962b46daffdf4cb8b0338cef2864`.
No category exception, isolated configuration, extra repository, or wider
rollout was included.

Fresh preflight proved:

- both Claude activation targets, both Codex targets, repository-private state,
  and fallback state absent;
- isolated `educode.context-pilot` clean at
  `0db30624dd32d814b937aa88b5ec84e18d4b130d`;
- Claude 2.1.220 executable SHA-256 `af5bf1f1...0231`;
- primary Codex config `7f0ee467...8178` and Claude settings
  `fc4451db...fdaa` unchanged;
- registry 63,786 bytes / SHA-256 `33a35b78...ed4`, semantic SHA-256
  `1d5e6814...7ec5`, `numStartups=30`, target absent, and content-free manifest
  SHA-256 `f562c8c5...06f6`; and
- exact plan still `ready`, no degraded reasons, two create mutations only,
  overlay `4c0699b0...047d`, allowlist `a1034fd2...829e`, and no pilot process.

Enable created exactly the two approved Claude targets. Status reported
`enabled_unobserved`, 2/2 owned, zero drift, and all 26 observable tools enforced.
Primary hashes and registry remained unchanged before launch.

A visible dedicated classic console launched the exact guarded manager. Capture
event `0f92b7ba-2a8a-4ba2-969d-6cb4a5f8de87` completed in 2 ms. At 1.051 seconds,
before trust or counter increment, event
`1aac688d-44f6-4f62-aa6a-abf0c7fb6423` rejected
`registry_semantic_drift` / `host_registry_drift` with exactly one persisted
category: `feature_state`. No raw field name, value, project path, or per-field
fingerprint entered the event or status. The guard stopped only the exact Claude
child; the manager also exited. No lifecycle event was observed.

The preserved registry remained 63,786 bytes and changed to SHA-256
`0d593dd7...4625`, semantic SHA-256 `a71757fe...decb`, still
`numStartups=30`, target absent, with post-state content-free manifest
`192adc34...b574`. The pilot did not write or revert it.

Disable removed exactly two owned targets. Separate purge removed exactly the
two content-free guard events. Final status is inactive; all four activation
targets and both state locations are absent; isolated Git remains clean at the
frozen commit; primary Codex/Claude settings retain their hashes; and no exact
Claude or pilot-manager process remains. Dedicated visible console PID 112388
and its idle PowerShell PID 127180 remain for owner cleanup; no Windows Terminal
top-level window was closed.

Classification: Refresh 4 diagnostic behavior, exact-child rejection, registry
preservation, and owned rollback are green. Claude lifecycle remains red/open.
The blocker is now localized to `feature_state`, but that category is evidence,
not an allowed mutation. Any retry, category/field exception, deferred validation,
or isolated-config strategy requires a superseding Design/ADR decision and
explicit approval.

## Post-Refresh-4 pre-commit source review (no host launch)

Mandatory final diff review found five source-only safety gaps: a hook-process
error could exit nonzero before PreCompact's fail-open response; Claude compact
events without turn/tool correlation reused one permanent dedupe identity;
historical or wrong-repository diagnostics could mark replacement activation
files active; exact mnemo retrieval could bypass ACL checks when its caller
omitted `reader`; and purge could leave an orphaned pilot process-lock when the
state directory was already absent. Review also closed permissive boolean/budget
coercion and kept safe pathless recovery tools available while material tools are
gated.

Generator `0.1.1` fixes those paths with an owned expected-event argument per
hook, fresh local sequence identity where the host supplies no correlation,
repository/version-bound event selection plus a content-free deactivation marker,
fail-closed ACL payload validation/default reader identity, strict config models,
and idempotent lock cleanup. No Codex or Claude process launched; all previous
`0.1.0` plan hashes remain consumed historical evidence and cannot authorize a
new cell.

Current checks:

- focused changed-path suite: 117 passed in 17.55 seconds;
- full deterministic compaction suite: 183 passed in 61.69 seconds;
- full mnemo suite: 48 passed in 30.83 seconds;
- stdio MCP write/search/task-context/get/forget: PASS;
- Ruff and Git whitespace checks: clean.

Task 10 remains red/open because generator `0.1.1` has no real-host lifecycle
evidence and Claude's last observed protected rewrite remains `feature_state`.
Tasks 11 and 12 remain open. No retry, exception, or wider activation is
authorized.
