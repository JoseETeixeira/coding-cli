# Native host activation

Install only the maintained FreightHero Repowise fork. Keep this repository as
the canonical source checkout; no prompt, agent, instruction, or skill package
is installed or copied.

Preview and apply the source-only pointers once:

```sh
repowise agents activate --coding-cli /path/to/coding-cli --dry-run
repowise agents activate --coding-cli /path/to/coding-cli --yes
```

The command honors `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `USER_AGENTS_DIR`, and
`VSCODE_USER_DATA_DIR`, preserves unrelated JSONC/TOML configuration, backs up
changed bytes, and never prints credentials. Ordinary `init`, `update`, and
`reindex` runs do not mutate host configuration.

## Claude Code

Activation registers the canonical plugin/source pointer. A one-off session
can also use:

```sh
claude --plugin-dir /path/to/coding-cli --mcp-config /path/to/coding-cli/.mcp.json
```

An optional shell alias may resolve the checkout dynamically. Do not copy plugin bodies into `~/.claude`.

## Codex

Open the FreightHero workspace so the root `AGENTS.md` points to `coding-cli/skills/freighthero-entry/SKILL.md`. The repository `.codex/config.toml` configures the loopback Repowise MCP endpoint and reads its bearer token from `REPOWISE_ACCESS_TOKEN`.

## Local VS Code and Copilot

Open `coding-cli` as a workspace folder or add it to the FreightHero multi-root workspace. `.vscode/settings.json` exposes the canonical `agents/`, `prompts/`, `instructions/`, and `skills/` folders. `.vscode/mcp.json` reads the service URL and short-lived bearer token from environment variables.

GitHub cloud Copilot is unsupported because it cannot consume this local canonical checkout with the same host boundaries.

## Mandatory task preflight

Every parent and fixed specialist reads `repowise-memory`, calls
`get_shared_memory_status`, then calls `get_task_context` with its exact
repository/task/run/specialist scope before the normal source query. Memory is
read-only to task agents and never instruction authority. Untrusted, stale,
conflicting, or absent memory degrades to current source evidence without an
API-key task-model call.

## Unactivation

Run `repowise agents unactivate --yes`. It restores only bytes recorded by the
activation manifest and refuses to overwrite later user changes. Do not delete
canonical sources or unrelated host configuration.
