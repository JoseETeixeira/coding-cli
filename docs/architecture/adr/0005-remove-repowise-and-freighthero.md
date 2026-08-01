# 0005 — Remove repowise and FreightHero-only content from the generic hosts

Status: accepted · 2026-07-15 · supersedes 0001, 0002 (deleted)

## Context

This machine does no FreightHero work. The coding-cli checkout was repurposed as a generic-only customization layer and moved to `~/source/coding-cli`. repowise (codebase intelligence + governed memory) and all FreightHero-only assets were to be removed, keeping only generic counterparts, with the new `mnemo` shared memory (ADR 0004) replacing repowise's memory role.

## Decision

- **repowise removed entirely** from the generic hosts: binary (`~/.local/bin/repowise*.exe`), all `.repowise` stores, the MCP registrations (Claude/Codex/Copilot + coding-cli configs), and the `REPOWISE_*` environment variables. Codebase intelligence is now agentic (grep/glob/read).
- **FreightHero-only assets deleted**: `freighthero-entry` + 8 AI-Watchtower/scenario skills, the 5 fixed specialist agents + `role-contracts.json`, `base-system.instructions.md`, the FH `.github` governance/validation/CI + CODEOWNERS + repowise attestation workflow, and the FH ADRs/PRD/activation/completion docs.
- **batman.agent.md** no longer classifies repositories; it routes every project through `generic-entry`.
- **Generic skills that referenced repowise** (`generic-entry`, `batman-understanding`) were edited to agentic search + `mnemo`; `cloudwatch-issues` was scrubbed of FreightHero specifics.
- **Host instruction files** (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.agents/AGENTS.md`, Copilot) had repowise/FH stripped and memory repointed to `mnemo`.

## Consequences

- Kept: 33 generic skills, generic prompts/instructions, BYOND assets, the PR template, CHANGELOG (history).
- `AGENTS.md` and `agents/batman.agent.md` stay `git update-index --skip-worktree`; local generic edits never push to the FreightHero origin (origin HEAD stays the FreightHero-only canonical).
- FreightHero work, if ever needed, would require re-introducing repowise + the FH entry via a separate opt-in — not on this host.
- The old Desktop coding-cli copy is a partial leftover (a lock blocked the atomic move) for the user to delete.
