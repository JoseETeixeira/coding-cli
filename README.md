# Generic agent assets

`coding-cli` is the user's generic customization layer for coding agents — reusable prompts, instructions, the Batman entry agent, skills, and the self-hosted `mnemo` shared-memory engine. It is host-agnostic and works across Claude Code, Codex, and VS Code / Copilot.

## Repository layout

- `agents/batman.agent.md`: the generic Batman entry agent (routes every project through `generic-entry`)
- `skills/`: generic skills — `generic-entry`, `shared-memory`, `mnemo-setup`, `batman-understanding`, `byond-projects`, `caveman*`, `visual-explainer`, `grill-me`, Robot Framework helpers, refactoring guides, etc.
- `instructions/`: shared code-pattern, review, and visual guidance
- `prompts/`: reusable task prompts
- `mnemo/`: the self-hosted shared-memory engine + MCP server (see `mnemo/README.md`)
- `.claude-plugin/`: Claude Code source discovery manifest
- `.codex/`, `.vscode/`: repository-scoped `mnemo` MCP configuration

## Memory: mnemo shared memory

Durable, cross-agent memory is `mnemo` — a self-hosted engine (Qdrant on port **1337** + OpenAI embeddings) exposed as a stdio MCP server. Claude Code and Codex point at the same substrate, so what one agent writes another can read.

- Start Qdrant: `mnemo\scripts\mnemo-qdrant.cmd`
- Register / troubleshoot: `skills/mnemo-setup/SKILL.md`
- Preflight + guardrails: `skills/shared-memory/SKILL.md`

## Entry

Every task begins with the canonical entry agent (`agents/batman.agent.md`), which routes through `skills/generic-entry/SKILL.md`: ambient auto-improvement, the `shared-memory` preflight, agentic codebase discovery, the eight-phase Batman workflow with PRD/ADR artifacts for non-trivial work, and host-native loops/sandbox/approvals/credits.

## Supported hosts

- Claude Code (user-scope MCP + `$USER_*_DIR` customization)
- Codex (`~/.codex/AGENTS.md` + `~/.codex/config.toml`)
- VS Code / Copilot (User `prompts/` + `mcp.json`)

## Security and operations

- Do not store secrets/tokens in memory; a redactor runs on every write.
- The `mnemo` OpenAI key resolves from `OPENAI_API_KEY` or `~/.mnemo/openai_api_key` (for hosts that do not pass the env through).
- `AGENTS.md` and `agents/batman.agent.md` are versioned normally. The `--skip-worktree` guard they used to carry was lifted 2026-07-16 once `origin` became this repo's own remote.
- Existing unrelated MCP servers, safety hooks, and RTK settings stay outside this repository.
