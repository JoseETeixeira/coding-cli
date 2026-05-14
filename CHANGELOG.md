# Changelog

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
