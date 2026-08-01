# PRD: project-specialized subagents

Status: accepted · 2026-07-16

## Problem

After the generic role-based specialists were removed (ADR 0005), only the `batman` router remained on the generic hosts. The user works across ~11 unrelated projects with very different stacks, and a single generic agent has to rediscover each project's build/run/verify commands, conventions, and gotchas every session. There was also no representation of these specialists on the Codex host, and no audit that any agent's stated facts still matched the projects on disk.

## Goals

- One specialist per project (or tight family) carrying that stack's build/run/verify, conventions, gotchas, tool surfaces, and the shared operating-rules block.
- One canonical source (`coding-cli/agents/<name>.agent.md`) propagated to every installed host: Claude Code, the generic agent runtime, and Codex.
- Codex parity via native subagents (`~/.codex/agents/<name>.toml`) plus orchestrator-driven delegation routing in `~/.codex/AGENTS.md`.
- Factual accuracy: every definition verified against its real project before propagation; drift corrected.
- Family consistency: uniform frontmatter shape and a single canonical wording of the shared operating-rules bullets.

## Non-goals (deferred)

- Auto-dispatch/routing intelligence beyond description-match + the AGENTS.md table (Codex spawns are orchestrator-triggered by design).
- Per-specialist Codex model/reasoning overrides (they inherit the parent `gpt-5.6-sol` / `xhigh`).
- Fixing the upstream Codex Windows subagent-config bug (tracked externally; AGENTS.md routing is the fallback).

## Scope

- 11 canonical `agents/<name>.agent.md` + the `batman` router shim.
- Cross-host install: `~/.claude/agents/<name>.md` (byte-identical), `~/.agents/agents/<name>.agent.md` (byte-identical), `~/.codex/agents/<name>.toml` (body → `developer_instructions`), and a delegation table in `~/.codex/AGENTS.md`.
- Install the 4 referenced skills (`shared-memory`, `byond-projects`, `generic-entry`, `mnemo-setup`) into `~/.claude/skills/` and `~/.agents/skills/`.
- Fix the stale installed Claude `batman` shim (dead FreightHero routing + old `OneDrive/Desktop` fallback path → `source/coding-cli`).
- Docs: this PRD + ADR 0006.

## Acceptance criteria

- Each specialist's concrete claims (paths, entry points, build commands, versions, conventions, gotchas) were audited against its project on disk; all `wrong`/`drifted` claims were corrected with `path:line` evidence. (11/11 projects located; cpp-native was clean; the rest had 1–5 corrections each.)
- All 11 specialists carry the harmonized operating-rules block: full-form mnemo preflight, agentic-search bullet, 8-phase workflow + PRD/ADR bullet, no-attribution, and "apply on top of this file".
- Claude and generic-runtime copies are byte-identical to canonical; all 11 Codex TOMLs parse (`tomllib`) with `name`/`description`/`developer_instructions`.
- Shared codenames (Hollow Covenant ×3, epic_ai/epic-ai) are disambiguated in the descriptions and the AGENTS.md table.
- The 4 skills resolve under both host skill dirs.

## Verification

Audit workflow (one agent per specialist verifying against the project root, plus a cross-agent consistency pass); `grep` sweeps confirming zero residual short-form wordings and stale facts; `diff -q` canonical-vs-installed on both mirrors; `tomllib` parse of all 11 Codex TOMLs; skill-file presence checks on both hosts.
