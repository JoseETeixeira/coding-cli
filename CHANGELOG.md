# Changelog

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
