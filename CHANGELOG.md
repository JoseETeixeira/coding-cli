# Changelog

## 2026-08-04

- Added `optical-compression`: a standalone offline MCP server that renders large
  read-mostly text payloads as 1-bit PNG pages costing fewer tokens than the text, and
  returns the exact original on demand by digest. Measured 2.69x (62.9% fewer tokens) on
  `context_compaction/activation.py`, with a byte-identical retrieval roundtrip. Three
  tools (`optical_compress`, `optical_retrieve`, `optical_stats`), a content-addressed
  segment cache, a CLI, a focused offline test suite, a six-suite replication benchmark,
  and a 16-gate stdio smoke test.
- Completed canonical and host wiring: `generic-entry` routes qualifying payloads to the
  skill; Claude Code, Codex, and VS Code/Copilot have repo and user-scope MCP adapters;
  Claude has one thin user-scope `Read` hook pointer; both launchers share the stable
  `~/.optical-compression` store; and a dedicated requirements file plus contract gates
  keep those promises from drifting. Installed skill bodies remain canonical pointers.
- Framed the feature as lossy optical gist with mandatory exact retrieval rather than as
  compression (ADR 0016). The reason is measured: at the aggressive density a
  transcription scored 99.4% character accuracy while corrupting 25% of the identifiers
  in the sample, flipping a hex digit in a UUID and mangling an access-key-shaped string.
  A character-accuracy headline hides exactly the errors that matter, so a guard refuses
  identifier-bearing payloads for automatic compression and the aggressive density
  auto-downgrades when identifiers are present.
- Declined payloads under 8,000 characters outright. Page padding does not amortise below
  that: a 428-character sample measured 0.95x, i.e. the image cost more than the text.
- Shipped automatic hook interception on Claude Code only, and made the gap visible
  through `optical_stats` rather than silent (ADR 0017). Codex parses
  `updatedMCPToolOutput` and then rejects it in `output_parser.rs`, and upstream PR
  #20703 was closed unmerged; there is no image-capable hook channel there at all. The
  hook targets `Read`, not `Bash`, because `Bash` declares a 30,000-character result
  ceiling that a full rendered page exceeds.
- Set `structured_output=False` on every optical-compression tool and pinned it with a
  test. Codex checks `structuredContent` before content blocks, so a populated value
  silently discards the image and the agent receives text with no error at all
  (openai/codex issue #10334, still open).
- Sized rendered pages to the token budget (1092px on the standard tier) rather than the
  1568px edge limit. Rendering to the edge costs 3,136 patches against a 1,568 ceiling,
  which forces a downscale that shrinks the glyphs and degrades decode accuracy precisely
  where it is tightest.
- Recorded the negative result on colour-encoding text as pixels as an executable
  benchmark suite. Additive mixing collapses 256 letter-pairs into 27 distinct colours
  with white alone the image of 46 pairs, so it is undecodable in principle; and vision
  encoders patchify at 28x28px, so exact per-pixel RGB never reaches the language model
  regardless. Even a repaired injective encoding would be a ~5x expansion, not a
  compression.

- Raised the `gpt-image-2` latency budgets: an attempt now gets 480 seconds and an
  operation 540, up from 150 and 180. Real high-quality generations were running past
  the old per-attempt bound, and the resulting `APITimeoutError` is the one failure this
  subsystem deliberately never retries — because the request may already have been
  billed. So the old numbers did not merely fail, they failed after paying.
- Raised `RETRY_MIN_REMAINING_S` from 20 to 240 seconds. It reads like an admission gate
  but is really the floor on the second attempt's timeout: `_call_with_retry` admits the
  retry, then clamps it to `min(API_ATTEMPT_TIMEOUT_S, remaining)`. At 20 it could admit
  a retry with a 20-second ceiling against a multi-minute generation — a second billed
  request that could only time out, replacing an actionable `service_error` with a
  useless one.
- Codex `tool_timeout_sec` 240 to 600 in both the repository and user `config.toml`, so
  the host still outlives the server's deadline. `tests/gpt_image_2/test_contract_gates.py`
  enforces this ordering and would have failed loudly otherwise.
- Claude Code now sets a per-server `"timeout": 600000` on the `gpt-image-2` registry
  entry in `.mcp.json` and `~/.claude.json`, which v2.1.203+ supports. The global
  `MCP_TOOL_TIMEOUT` environment variable was rejected on purpose: its default is
  roughly 28 hours, so setting it to 600000 for this server would have *shortened* every
  other MCP server's ceiling to ten minutes.
- Corrected a factual claim in ADR 0015 and `README.md` that a `.mcp.json` entry cannot
  set Claude Code's tool timeout. It can, per-server, and that is now the mechanism used.
  Claude Code was never the thing cutting these calls off.
- Closed three gaps an adversarial review of this very change found, each one a
  promise the change made without a gate to keep it. `test_contract_gates.py` now
  pins the Claude-side per-server `timeout` against `OPERATION_DEADLINE_S` (the Codex
  half was already gated, so one ordering rule had two halves and one guard), pins the
  operation deadline in `SKILL.md` (the change put a hard `540 seconds` into the one
  document an agent reads before spending money, where only the README was gated), and
  pins `RETRY_MIN_REMAINING_S` from both sides. That last one needed a policy gate
  rather than a unit test: `retried timeout >= floor` holds for *any* floor, so a unit
  test cannot tell 240 from 20. All three were verified by mutation — each fails when
  the value it guards is moved, which is the only evidence a new test is worth having.
- Re-stated the latency everywhere it is read, including the `generate_image` /
  `edit_image` tool descriptions themselves — the copy a calling model sees before it
  decides a running call has hung — plus `README.md` and `skills/gpt-image-2/SKILL.md`.
  ADR 0015 keeps its decision and gains a dated amendment.

## 2026-08-02

- Added the `gpt-image-2` capability: a canonical `skills/gpt-image-2/` workflow plus a
  standalone stdio MCP server (`gpt_image_2/`, launched by `run_gpt_image_2_server.py`)
  exposing `generate_image` and `edit_image` against OpenAI's direct Image API. Kept
  separate from `mnemo` on purpose (ADR 0015): a paid, credential-bearing, large-binary
  capability must not be able to take the shared-memory preflight down with it.
- The model is fixed to `gpt-image-2` and no tool argument can override it. Neither tool
  accepts a model, API key, header, endpoint, URL, file ID, overwrite flag, or
  `input_fidelity` — the absence is the enforcement, and a test asserts it as a set
  intersection so a future addition fails loudly.
- Spend control is explicit: the SDK's own retry is disabled (`max_retries=0`), at most one
  retry happens and only after an explicit `429`/`5xx` *response*, and a timeout or dropped
  connection is never retried because that request may already have been billed. One
  operation gets 180 seconds total, one attempt gets 150.
- Every locally knowable rule — prompt length, size geometry, quality, count, format and
  compression pairing, background, edit inputs, mask alpha, output paths — is checked before
  the credential is even read, so an invalid request costs nothing.
- Outputs are never overwritten. Images are decoded and validated in memory, written to a
  temporary file that is `fsync`ed, then published with a create-exclusive `os.link` so a
  collision becomes `image-2.png` rather than destroying an existing asset. The temporary
  file is removed in a `finally` on every path.
- `OPENAI_API_KEY` resolves from the process environment, then from the Windows per-user
  environment store, and is wrapped in a `Secret` whose `repr`/`str`/`format` all render
  `<Secret ***>` — so an f-string in a log line or a traceback frame cannot leak it.
- Registered for Claude Code, Codex, and VS Code / Copilot at both repository and user
  scope, with no credential value in any of the six files. Codex's registrations set
  `tool_timeout_sec = 240` because its documented default is 60 s, which would otherwise
  abort a normal high-quality generation before the server could answer.
- Known limitation, stated rather than worked around: `gpt-image-2` does not support
  transparent backgrounds, so `background="transparent"` fails with a clear
  unsupported-option error instead of quietly returning an opaque image.
- An adversarial review pass found and fixed thirteen defects in the first cut of this
  code before it shipped. The ones worth naming:
  - `GPT_IMAGE_2_LOG_LEVEL` went through `logging.basicConfig`, which sets the **root**
    logger — so asking this package for DEBUG also switched on DEBUG for `openai`, whose
    client logs full request options: the user's prompt, and for an edit the raw
    reference-image and mask bytes, straight to stderr. The level now applies to the
    `gpt_image_2` logger alone and `openai`/`httpx`/`httpcore` are pinned at `WARNING`
    regardless. A lowercase or unknown value used to raise `ValueError` at import and
    kill the server at startup; it now falls back to `WARNING`.
  - `revised_prompt` was the one provider-controlled string relayed to the caller
    without redaction or a length bound. It now goes through the same scrubber as every
    other provider string.
  - An `output_dir` that named an existing *file* passed validation, so the credential
    was read and the image was generated and billed before the write failed. Validation
    now walks to the nearest existing ancestor and rejects it before any spend.
  - A 68-byte PNG declaring 60000x60000 raised `DecompressionBombError` — which derives
    from plain `Exception` and escaped the closed error taxonomy as an `internal_error`
    with a traceback — after forcing a huge allocation during pre-credential validation.
    Header dimensions are now checked before decoding, and PIL failures are caught
    broadly.
  - A publish failure on the second of three images aborted the whole call, orphaning the
    file already on disk and returning an error that named none of the paths the caller
    had just paid for. Each publish is now guarded and partial success is reported.
  - A UNC path such as `//server/share/x.png` was treated as a local file, and
    `Path.resolve()` made Windows perform a real SMB/DNS lookup — caller-controlled
    network I/O that stalled a paid operation for seconds. URLs and UNC paths are now
    refused before the filesystem is touched.
  - A short provider response (fewer images than `n`) was reported as a clean success.
    Results now carry `provider_returned` and `complete`.
  - The decompression-bomb catch was widened on the input path but not on the response
    path, so a bomb in a provider payload still escaped the closed taxonomy and threw
    away the valid, already-paid-for images alongside it. Both sides now catch broadly.
- Fixed `mnemo.engine` resolving its canonical `context_compaction` budgeter only when the
  repository root happened to be on `sys.path`. Only `run_server.py` provided that, so every
  importer embedding mnemo as a library failed: the SessionStart preflight degraded visibly,
  and both Batman checkpoint hooks failed silently — they swallowed the `ImportError`, then
  claimed no prior checkpoint existed and dropped the paired `memory_forget`, leaving two live
  `active` items per slug and phase. The root is now resolved from `__file__`, and appended
  rather than inserted, so a library never shadows a host process's own modules.
- Added the regression that reproduces the hooks' real resolution environment (subprocess
  under `-P`, only `<repo>/mnemo` on the path) plus coverage for the supersede branch the
  swallowed error skipped. The protected-asset gate now hashes newline-normalized text, so it
  measures the asset instead of the checkout's line endings.
- Fixed both Batman checkpoint hooks deriving their mnemo namespace from the directory
  name, so any linked worktree wrote to `repo:<branch-dir>` and orphaned its checkpoints
  from the repository corpus the next session reads back. They now follow `.git` to the
  main checkout with pure file I/O, preserving the deliberate no-subprocess constraint,
  and fail soft to the directory name. The pilot's byte-identity gate for these assets is
  re-baselined with the reason recorded inline.
- Added `python -m context_compaction.registry_census`: a read-only drift census that
  reuses the ADR 0013 guard's own fingerprint helpers to report which protected registry
  fields move during a natively started Claude session. It writes nothing, launches
  nothing, and activates nothing.
- Identified the Claude 2.1.220 startup rewrite behind three `feature_state` rejections,
  read-only and without launching a host: one updater re-stamps four `cached*` GrowthBook and
  experiment fields with `Date.now()` on every successful remote flag fetch. The guard is
  behaving as approved. No exemption, env lever, or activation change was made — Task 10
  stays red/open pending an owner decision.

## 2026-08-01

- Added a disabled-by-default, cross-host native context-compaction pilot for
  Codex and Claude Code with one canonical policy, bounded source-backed
  re-entry, metadata-only action recovery, exact-version activation refusal,
  isolated profile/overlay generation, pilot-local disablement of hosted Codex
  surfaces outside hook coverage, and owned rollback.
- Changed mnemo `task_context` to a versioned, bounded preview envelope while
  retaining its legacy top-level field and adding ACL-aware `memory_get` for
  exact authorized retrieval and ACL-safe revocation.
- Added the frozen `educode` P01–P14 preservation manifest, disposable-worktree
  dirty-state fixture, qualified savings and anti-thrashing harness, security
  fault injection, and content-free deterministic gate reporting.
- Added ADR 0013's Claude host-registry guard: content-free semantic manifests,
  exact-child monitoring, allowlisted working directory, `host_registry_drift`,
  and no pilot write/revert of `.claude.json`.
- Added ADR 0014's content-free Claude registry diagnostics: per-protected-field
  fingerprints stay inside the live guard process, while rejected events/status
  expose only sorted closed field-family categories. An exact owner-approved
  live cell localized the protected startup rewrite to `feature_state`, stopped
  the exact child, preserved the registry, and completed exact disable/purge; no
  registry exception was added.
- Recorded a real Claude 2.1.220 guarded-startup rejection: bootstrap changed
  protected semantics before trust/counter increment, the exact child
  stopped, the registry was preserved, and owned activation/state rolled back.
- No real user Codex or Claude Code configuration is enabled by these source
  changes. Activation, real-host measurements, wider rollout, and owner
  acceptance remain separate explicit gates.
- Hardened the source-only pilot after final review: per-event hook commands
  guarantee PreCompact failure stays fail-open, uncorrelated Claude lifecycle
  invocations remain distinct, activation evidence is repository/version-bound,
  disable records a non-destructive deactivation marker, ACL defaults fail
  closed, and orphaned process locks are purged. Generator version is `0.1.1`;
  prior historical activation previews remain consumed evidence, not reusable
  launch approval.

## 2026-07-14

- Added shared `byond-projects` guidance plus thin Codex, Claude, and execution-prompt pointers, requiring BYOND documentation evidence, DM compatibility, Dream Maker compilation, and Dragon Ball Universe safeguards (user directive 2026-07-14).

## 2026-07-10

- Made governed Repowise task context and shared-ledger status mandatory for every parent/specialist repository preflight while keeping task-agent memory read-only.
- Made `repowise-memory` an explicit required skill in every role and phase, preserving named `grill-me`, `visual-explainer`, auto-improvement, and same-reviewer mutation loops.
- Added per-repository immutable shared-ledger policy and combined-tree attestation workflows; generated databases and vectors remain ignored and local per developer.
- Converted `coding-cli` into the canonical source-only repository for native Claude, Codex, and local Copilot agents, prompts, instructions, skills, governance, and conformance fixtures.
- Added the metadata-first FreightHero entry skill and six fixed native-host specialists with mandatory fresh, scoped Repowise evidence and PRD/ADR gates.
- Removed the Go distribution/installers, FreightHero MCP/CocoIndex runtime, refresh/patch hooks, duplicate generated host assets, and active OpenWiki dependencies after the frozen retrieval gate passed.
- Added protected Repowise HTTP pointers, host activation guidance, source/governance validation, host scenarios, retrieval parity regression, and the completion/rollback record.

## 2026-06-25

- Integrated [repowise](https://github.com/repowise-dev/repowise) as a second codebase-intelligence MCP server, complementary to `freighthero-codebase` (CocoIndex). `config.ManagedServers` now ships a `repowise` server (`repowise mcp <workspace-root>`, workspace mode federating every sub-repo) to all host configs; `deps` adds an optional `repowiseSpec` (installed via `uv tool install repowise`, non-required so a missing `uv` never breaks MCP setup); the VS Code Batman frontmatter tools whitelist gains `'repowise/*'` (Claude Code inherits it automatically).
- Attached complementary repowise guidance to the focused-set Batman assets: `batman.agent.md` (planning rules + a note that repowise does not satisfy the mandatory `freighthero-codebase` Discovery search), `skills/freighthero-projects/SKILL.md`, and `skills/batman-understanding/SKILL.md`. Guidance routes graph/git/code-health/decision/risk questions to repowise (`get_overview`, `get_context`, `get_why`, `get_risk`, `get_health`, `get_dead_code`, `get_symbol`) and keeps find/read-code on `freighthero-codebase` (`:search_codebase` / `:explain_code`).
- Added unit coverage: `ManagedServers` includes the repowise server with `repowise mcp <root>`; `SetupMCPSpecs`/`SetupFullSpecs` include an optional repowise spec that installs via `uv`.
- Added `.claude/hooks/refresh-repowise.sh` (SessionStart, mirrors `refresh-cocoindex.sh`): on session start it runs `repowise update --workspace --index-only` in the background (no LLM, no cost, workspace-guarded, lock-protected) so the graph/git/code-health stays current. `freighthero-projects` now instructs running `repowise update --workspace` (incl docs/RAG) after a significant code change, with `--index-only` for a fast no-LLM refresh.

## 2026-05-16

- Added a Constitution gate to the Batman Design phase. `design.prompt.md` now loads or seeds `.batman/<task_slug>/steering/constitution.md` from a new Constitution Template, requires pre- and post-design checks against every principle, and surfaces unavoidable violations through a Complexity Tracking table — no silent rule-breaking. `batman.agent.md` wires the gate into Phase 3 Design Capture and the Workflow Summary, and `requirements.prompt.md` references the constitution so Requirements stays aware of it without being blocked on it.
- Rewrote `skills/grill-me/SKILL.md` to follow a 9-category ambiguity taxonomy (scope, data model, UX, NFRs, integrations, edge cases, constraints, terminology, completion signals), cap at 5 questions per pass, resolve via codebase before asking, and append answers to a timestamped `## Clarifications` block on the artifact instead of rewriting it. Adds an end-of-pass coverage report covering resolved, deferred, outstanding, codebase-answered, and user-skipped categories.

## 2026-05-15

- Added `freighthero setup agent` and `setup full` provider-aware git guardrail installation. Claude Code gets a real PreToolUse hook (`block-dangerous-git.sh`) blocking `git push`, `reset --hard`, `clean -f`, `branch -D`, `checkout .`, `restore .`. VS Code / Batman get deny rules merged into `chat.tools.terminal.autoApprove` in user settings.json. Codex gets a managed guardrail block written to `~/.codex/AGENTS.md` (advisory — Codex has no shell PreToolUse hook).
- Bundled `coding-cli/.claude/hooks/block-dangerous-git.sh` as the canonical source of the Claude Code hook script. The CLI copies it into `~/.claude/hooks/` and merges the hook entry into the existing PreToolUse Bash matcher without disturbing other hooks.
- Added new shipped skills mirrored under `coding-cli/skills/`: `diagnose` (disciplined bug-diagnosis loop), `handoff` (compact session into handoff doc), `git-guardrails-claude-code` (skill that installs the Claude Code hook directly).
- Added `paths.VSCodeSettingsPath()` resolver and `SettingsPath` field on the VS Code and Batman host profile roots so the guardrail installer can locate `Code/User/settings.json` cross-platform.

## 2026-05-13

- Added the shipped `grill-me` skill and wired the Batman workflow (`batman.agent.md`, `BASE_SYSTEM_PROMPT.instructions.md`) to run a Grill-Me Pass before requesting user approval at the end of each planning phase (Understanding, Requirements, Design, Task Planning).

## 2026-05-11

- Added a canonical PR template and updated shipped FreightHero PR guidance to use it when creating pull requests.
- Updated shipped FreightHero skill guidance so new AI Watchtower Robot workflow suites update the CI selector inventory and reuse the shared workflow resource.

## 2026-05-05

- Added explicit step-by-step logging across `repositories clone`, `setup agent`, `setup mcp`, `run indexing`, and `setup full`, including skipped steps.
- Changed `setup mcp` to auto-detect a single supported host instead of failing silently when no host flag is passed.
- Switched generated GitHub MCP configuration to the remote GitHub MCP endpoint for all supported hosts, while preserving Codex bearer-token wiring.
- Added native cross-platform `rtk` installation from official GitHub release assets for macOS, Linux, and Windows.
- Added automatic `python3` exposure and installation so the CLI can put a suitable Python interpreter on PATH without depending on Homebrew, using a FreightHero-managed uv-backed Python environment when no suitable interpreter already exists.
- Exposed indexing progress as named steps so `setup full` logs the embedded indexing flow, with `mempalace` running before `cocoindex`.
- Fixed generated MemPalace hook harness values so Batman and VS Code assets use the supported `codex` harness, while Claude Code uses `claude-code`.

## 2026-05-04

- Added the `freighthero` Cobra CLI for FreightHero onboarding, repository cloning, host setup, MCP config generation, and indexing bootstrap.
- Added internal Go packages and command-level integration tests covering `setup agent`, `setup mcp`, `setup full`, and rerun idempotence.
- Documented command usage, supported hosts, flags, and recovery guidance in the project README.
- Added `build.sh`, `install.sh`, and a GitHub Actions release workflow so published binaries install as `freighthero` without cloning the repo.
- Updated installer and docs to support private GitHub repositories via authenticated GitHub API and release downloads.
- Tightened the shipped Batman understanding prompt and skill so Phase 1 explanations answer source-of-truth, process-distinction, component-purpose, and execution-location questions instead of only listing change surfaces.
