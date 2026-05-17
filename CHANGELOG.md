# Changelog

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
