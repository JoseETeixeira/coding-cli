# Generic agent assets

`coding-cli` is the user's generic customization layer for coding agents — reusable prompts, instructions, the Batman entry agent, skills, and the self-hosted `mnemo` shared-memory engine. It is host-agnostic and works across Claude Code, Codex, and VS Code / Copilot.

## Repository layout

- `agents/batman.agent.md`: the generic Batman entry agent (routes every project through `generic-entry`)
- `skills/`: generic skills — `generic-entry`, `shared-memory`, `mnemo-setup`, `batman-understanding`, `byond-projects`, `gamedev-workflow`, `caveman*`, `visual-explainer`, `grill-me`, Robot Framework helpers, refactoring guides, etc. `gamedev-workflow` selectively composes game design/implementation, 3D, Godot FPS/particles/performance, and UI-motion disciplines with project specialists.
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

## Opt-in context compaction pilot

The repository now contains a disabled-by-default Codex + Claude Code pilot that
lets each host keep ownership of native compaction while rebuilding a bounded,
source-backed continuation envelope. It does not delete transcripts or memory,
does not replace fresh-session handoff, and does not edit either host's primary
configuration.

Claude's host-owned `.claude.json` is never a pilot write or rollback target.
During the approved first-trust cycle, a content-free semantic guard permits only
the normal startup counter increment and exact allowlisted project trust entry;
all unrelated semantic drift stops the exact Claude child without reverting the
file. Rejected protected drift is compared with process-private field
fingerprints; persisted diagnostics contain only sorted categories from a closed
seven-value vocabulary, never raw names, values, or per-field hashes. This
diagnosis does not widen accepted startup behavior.

- Canonical policy: `skills/context-compaction/SKILL.md` and
  `prompts/context-compaction.prompt.md`
- Operator commands: `py -3.12 -m context_compaction --help`
- Runbook and rollback: `docs/context-compaction/README.md`
- Compatibility and evidence: `docs/context-compaction/compatibility.md` and
  `.batman/cross-host-context-compaction/spec/evidence/index.md`

Only Codex `0.145.0` and Claude Code `2.1.220` are currently admitted by the
experimental adapter. Real user-level activation remains approval-gated; source
presence is not activation.

## Security and operations

- Do not store secrets/tokens in memory; a redactor runs on every write.
- The `mnemo` OpenAI key resolves from `OPENAI_API_KEY` or `~/.mnemo/openai_api_key` (for hosts that do not pass the env through).
- `AGENTS.md` and `agents/batman.agent.md` are versioned normally. The `--skip-worktree` guard they used to carry was lifted 2026-07-16 once `origin` became this repo's own remote.
- Existing unrelated MCP servers, safety hooks, and RTK settings stay outside this repository.
