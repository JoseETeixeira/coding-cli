# 0006 — Project-specialized subagents replacing generic role-based specialists

Status: accepted · 2026-07-16

## Context

ADR 0005 removed the five fixed role-based specialists (planning / implementation / verification / documentation / repository-researcher) and `role-contracts.json`, leaving only the `batman` entry router on the generic hosts. This machine drives ~11 distinct personal projects across very different stacks — BYOND/DM, a Godot C++ engine fork, native C++/Vulkan, PyTorch/diffusers, Flutter + AWS Lambda, a Next.js/Lambda SaaS monorepo, Roblox/Luau, a TypeScript WhatsApp bot, and a FastAPI + React finance terminal. A single generic agent reloads each project's build/run/verify commands, conventions, and gotchas from scratch every session, and role-based specialists never carried project knowledge at all.

## Decision

Author one project-specialized subagent per project (or tight project family), each carrying its stack's build/run/verify commands, conventions, gotchas, tool surfaces (MCPs), and the shared operating-rules block. `batman` stays the thin entry router; specialists are spawned by stack / file-type match.

- **Roster (11):** `byond-dev` (Dragonball_Universe), `byondot-engine` (BYONDOT), `cpp-native` (EGE-2D / HC / edu), `diffusion-ml` (OF_Generator / 3D-Gen), `fellow-software` (Fellow Software monorepo), `flutter-mobile` (standalone epic_ai), `godot-dev` (Hollow Covenant / Godot 4.6), `llm-fullstack` (finance), `roblox-dev` (lifeverse), `ts-cloud` (bot), `unreal-dev` (HollowCovenant / Unreal 5.7).
- **Canonical source:** `coding-cli/agents/<name>.agent.md` (frontmatter `name` + `description`, `model: opus`, then a markdown body). `batman.agent.md` is the router shim.
- **Cross-host install:** Claude Code `~/.claude/agents/<name>.md`; generic runtime `~/.agents/agents/<name>.agent.md`; Codex `~/.codex/agents/<name>.toml` (body → `developer_instructions`, inheriting the parent model) plus a delegation table in `~/.codex/AGENTS.md` because Codex routing is orchestrator-driven, not description-auto-dispatched.
- **Shared operating-rules block, harmonized across all 11:** mnemo preflight (`memory_status` + `task_context`) with the safe no-memory fallback; agentic search (grep/glob/read, no `search_codebase`); the Batman 8-phase workflow with `.batman/<slug>/` + PRD/ADR for non-trivial work; no AI/Claude attribution; host `CLAUDE.md`/`AGENTS.md` apply on top.
- **Audited against reality:** every definition was verified against its project on disk before propagation (see the PRD's acceptance criteria); factual drift was corrected.

## Consequences

- Each specialist is authoritative for its project; the router picks by stack/file-type. Context is pre-loaded, not rediscovered each session.
- Shared codenames are disambiguated by engine/scope in the descriptions: "Hollow Covenant" resolves to `godot-dev` (Godot 4.6), `unreal-dev` (Unreal 5.7), or `cpp-native` (EGE-2D content); `epic_ai` (standalone Flutter, `flutter-mobile`) is distinct from the monorepo `epic-ai` (`fellow-software`).
- Codex subagent-config is reportedly buggy on Windows (openai/codex #19399, #26868, #15250) — a spawned agent may ignore its TOML. The `AGENTS.md` delegation table is the fallback: read `~/.codex/agents/<name>.toml` inline and follow it.
- The four skills the specialists reference (`shared-memory`, `byond-projects`, `generic-entry`, `mnemo-setup`) were installed into `~/.claude/skills/` and `~/.agents/skills/` so references resolve at runtime.
- `AGENTS.md` and `agents/batman.agent.md` stay `git update-index --skip-worktree` (generic-only, never pushed to the FreightHero origin). The 11 specialist files are new canonical assets in the checkout.

## Rollout and rollback

Propagate corrected definitions to all three hosts and keep them byte-synced (Claude/generic mirrors are identical to canonical; Codex is the TOML-transformed equivalent). Rollback removes the specialist files, the Codex TOMLs, and the `AGENTS.md` delegation section, and records a superseding ADR rather than rewriting this one.

## References

- Product record: `docs/prd/specialized-project-agents.md`
- Canonical agents: `agents/<name>.agent.md`
- Prior decisions: ADR 0005 (removed the old specialists), ADR 0004 (mnemo shared memory), ADR 0003 (BYOND project guidance skill)
