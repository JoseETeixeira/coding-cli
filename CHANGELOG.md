# Changelog

## 2026-05-04

- Added the `freighthero` Cobra CLI for FreightHero onboarding, repository cloning, host setup, MCP config generation, and indexing bootstrap.
- Added internal Go packages and command-level integration tests covering `setup agent`, `setup mcp`, `setup full`, and rerun idempotence.
- Documented command usage, supported hosts, flags, and recovery guidance in the project README.
- Added `build.sh`, `install.sh`, and a GitHub Actions release workflow so published binaries install as `freighthero` without cloning the repo.
- Updated installer and docs to support private GitHub repositories via authenticated GitHub API and release downloads.
- Tightened the shipped Batman understanding prompt and skill so Phase 1 explanations answer source-of-truth, process-distinction, component-purpose, and execution-location questions instead of only listing change surfaces.
