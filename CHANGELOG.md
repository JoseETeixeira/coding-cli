# Changelog

## 2026-05-20

- Added a `git-guardrails-claude-code` skill plus a `.claude/hooks/block-dangerous-git.sh` PreToolUse hook that blocks `git push`, `git reset --hard`, `git clean -f[d]`, `git branch -D`, and `git checkout/restore .` before Claude Code can execute them. `coding-cli setup agent` / `setup full` now run `config.InstallGitGuardrails` for every host: Claude Code copies the hook + merges a PreToolUse Bash entry into `~/.claude/settings.json`, VS Code / Batman merge deny rules into `chat.tools.terminal.autoApprove` in user `settings.json`, and Codex maintains a managed `<!-- coding-cli:git-guardrails:* -->` block inside `AGENTS.md`. Installer is idempotent across all three host paths.
- Added `paths.Resolver.VSCodeSettingsPath()` and populated `HostVSCode` / `HostBatman` `Roots.SettingsPath` so the VS Code guardrail merge has a target file.
- Added new generic skills `diagnose` (reproduce → minimise → hypothesise → instrument → fix → regression-test loop with an `hitl-loop.template.sh` helper) and `handoff` (compact-conversation summary for picking up work in a fresh session).

## 2026-05-16

- Added a Constitution gate to the Batman Design phase. `design.prompt.md` now loads or seeds `.batman/<task_slug>/steering/constitution.md` from a new Constitution Template, requires pre- and post-design checks against every principle, and surfaces unavoidable violations through a Complexity Tracking table — no silent rule-breaking. `batman.agent.md` wires the gate into Phase 3 Design Capture and the Workflow Summary, and `requirements.prompt.md` references the constitution so Requirements stays aware of it without being blocked on it.
- Rewrote `skills/grill-me/SKILL.md` to follow a 9-category ambiguity taxonomy (scope, data model, UX, NFRs, integrations, edge cases, constraints, terminology, completion signals), cap at 5 questions per pass, resolve via codebase before asking, and append answers to a timestamped `## Clarifications` block on the artifact instead of rewriting it. Adds an end-of-pass coverage report covering resolved, deferred, outstanding, codebase-answered, and user-skipped categories.

## 2026-05-14

- Switched the `mempalace` dependency install target to the maintained fork at `git+https://github.com/JoseETeixeira/mempalace-fix.git`. `setup full` now force-reinstalls mempalace from the fork after the regular dependency check, so existing PyPI installs are swapped over automatically. Other commands (`setup mcp`, `run indexing`) still keep an existing install in place and only fetch the fork when mempalace is missing.
- Dedup'd `code-patterns.md.instructions.md` and `codeReview.instructions.md` so the synced `CLAUDE.md` no longer carries two copies of sections 1-12.

## 2026-05-13

- Renamed the CLI from `freighthero` to `coding-cli` and dropped FreightHero-specific repository, skill, and prompt content so the tool can bootstrap any workspace.
- Renamed `freighthero-mcp` to `query-code-mcp` and made its CocoIndex pipeline scan every project directory under the workspace root by default (with `CODEBASE_PROJECTS` as an optional allowlist).
- Replaced the `--freighthero-root` flag with `--workspace-root` and removed the `repositories clone` command.
- Removed FreightHero/AI-Watchtower-specific shipped skills (`freighthero-projects`, `console-testing-scenarios`, `ai-watchtower-wiki`, `ai-watchtower-skills-authoring`) and genericized the remaining prompts and instructions.

## 2026-05-05

- Added explicit step-by-step logging across setup and indexing flows, including skipped steps.
- Changed `setup mcp` to auto-detect a single supported host instead of failing silently when no host flag is passed.
- Switched generated GitHub MCP configuration to the remote GitHub MCP endpoint for all supported hosts, while preserving Codex bearer-token wiring.
- Added native cross-platform `rtk` installation from official GitHub release assets for macOS, Linux, and Windows.
- Added automatic `python3` exposure and installation so the CLI can put a suitable Python interpreter on PATH without depending on Homebrew, using a coding-cli-managed uv-backed Python environment when no suitable interpreter already exists.
- Exposed indexing progress as named steps so `setup full` logs the embedded indexing flow, with `mempalace` running before `cocoindex`.
- Fixed generated MemPalace hook harness values so Batman and VS Code assets use the supported `codex` harness, while Claude Code uses `claude-code`.

## 2026-05-04

- Added the Cobra CLI for workspace onboarding, host setup, MCP config generation, and indexing bootstrap.
- Added internal Go packages and command-level integration tests covering `setup agent`, `setup mcp`, `setup full`, and rerun idempotence.
- Documented command usage, supported hosts, flags, and recovery guidance in the project README.
- Added `build.sh`, `install.sh`, and a GitHub Actions release workflow so published binaries install as `coding-cli` without cloning the repo.
- Tightened the shipped Batman understanding prompt and skill so Phase 1 explanations answer source-of-truth, process-distinction, component-purpose, and execution-location questions instead of only listing change surfaces.
