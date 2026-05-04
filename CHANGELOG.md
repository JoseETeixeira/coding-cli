# Changelog

## 2026-05-04

- Added the `freighthero` Cobra CLI for FreightHero onboarding, repository cloning, host setup, MCP config generation, and indexing bootstrap.
- Added internal Go packages and command-level integration tests covering `setup agent`, `setup mcp`, `setup full`, and rerun idempotence.
- Documented command usage, supported hosts, flags, and recovery guidance in the project README.
- Added `build.sh`, `install.sh`, and a GitHub Actions release workflow so published binaries install as `freighthero` without cloning the repo.