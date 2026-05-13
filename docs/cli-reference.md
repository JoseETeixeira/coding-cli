# CLI reference

`coding-cli` is a Cobra CLI. Every command accepts the global flags below, then narrows behavior via subcommands.

## Global flags

| Flag | Purpose |
| --- | --- |
| `--workspace-root <path>` | Absolute path to the workspace root (parent of `coding-cli/`). Defaults to the nearest ancestor of the current directory that contains `coding-cli/`. |
| `--force` | Allow coding-cli-managed files (existing prompts/agents/skills) to be rewritten. Without `--force`, conflicting files are reported and skipped. |
| `--verbose` | Print subprocess invocations and config-diff details. |

## Subcommands

### `coding-cli setup agent --<host>`

Installs user-level prompts, instructions, agents, and skills for one host. Requires an explicit `--<host>` flag — no auto-detection here.

- Reads everything under [`prompts/`](../prompts/) and [`skills/`](../skills/) of this repo.
- Renders host-specific transforms (e.g. Claude Code strips the `tools:` frontmatter list, swaps `#tool:vscode/askQuestions` for `AskUserQuestion`, injects the spec-sync block).
- Writes per-host destinations (see [host profiles](#host-profiles)).
- For Claude Code, also installs the SessionStart hook into `~/.claude/settings.json`.

### `coding-cli setup mcp [--<host>]`

Writes MCP configuration for one host. Auto-detects the host when exactly one supported host is configured on the machine; otherwise requires `--<host>`.

The generated configuration always includes three servers:

| Server | Purpose |
| --- | --- |
| `query-code` | Local workspace codebase search via CocoIndex. See [query-code-mcp.md](query-code-mcp.md). |
| `mempalace` | Project memory (the `mempalace` Python package, invoked as `python3 -m mempalace.mcp_server`). |
| `github` | Remote GitHub MCP at `https://api.githubcopilot.com/mcp/`. For Codex, includes `bearer_token_env_var: GITHUB_PAT_TOKEN`. |

`setup mcp` also runs the prerequisite checks ([dependencies](#dependencies)) and builds `query-code-mcp` (`npm install` + `npm run build`) before writing the config.

### `coding-cli setup full [--<host>]`

End-to-end onboarding: `setup mcp` + `setup agent` + initial indexing. Auto-detects the host when exactly one is configured.

Phases, in order:

1. Resolve workspace and validate the `coding-cli/` directory.
2. Resolve the host profile.
3. Verify dependencies (`SetupFullSpecs`: adds `git` on top of `SetupMCPSpecs`).
4. Sync assets (`setup agent`).
5. Build `query-code-mcp` (`npm install` + `npm run build`).
6. Write MCP config.
7. Install Claude Code SessionStart hook (Claude Code only).
8. Verify indexing dependencies (`IndexingSpecs`).
9. Run the indexing flow (build MCP if missing, create venv, run `mempalace wake-up`, run `cocoindex update`).

`setup full` is idempotent — rerunning skips work that's already complete and logs `skipped` rather than redoing it.

### `coding-cli run indexing`

Runs only the indexing phase: dependency check (`IndexingSpecs`), `mempalace wake-up`, then `cocoindex update`. Use this when you just want to refresh the index without touching MCP config or prompts.

## Host profiles

Each `--<host>` flag selects a profile with its own write destinations and rendering rules. Resolved at runtime by `internal/host` and `internal/paths`.

### `--vscode` (VS Code / GitHub Copilot)

| Asset | Destination |
| --- | --- |
| Prompts (`*.prompt.md`) | `$USER_PROMPTS_DIR` / `$VSCODE_USER_PROMPTS_FOLDER` / `<vscode-user>/prompts/` |
| Agents (`*.agent.md`) | Same folder as prompts (VS Code Batman extension) |
| Instructions (`*.instructions.md`) | Same folder as prompts |
| Skills (`<skill>/SKILL.md`) | `$USER_SKILLS_DIR` / `$HOME/.agents/skills/` |
| MCP config | `<vscode-user>/mcp.json` (`servers` key) |

`<vscode-user>` resolves to `~/Library/Application Support/Code/User` (macOS), `%APPDATA%\Code\User` (Windows), or `~/.config/Code/User` (Linux).

Harness for the rendered Batman agent: `codex`.

### `--batman`

Same destinations as `--vscode` (it's the VS Code Batman extension). Detected by the presence of `BATMAN`, `BATMAN_AGENT`, `BATMAN_HARNESS`, or `BATMAN_CONFIG_DIR` env vars.

### `--claude-code`

| Asset | Destination |
| --- | --- |
| Prompts (`*.prompt.md`) | `$CLAUDE_CONFIG_DIR/commands/` or `~/.claude/commands/` |
| Agents (`*.agent.md`) | `$CLAUDE_CONFIG_DIR/agents/` or `~/.claude/agents/` |
| Instructions (`*.instructions.md`) | Individual files at `~/.claude/`, plus a managed block appended to `~/.claude/CLAUDE.md` |
| Skills (`<skill>/SKILL.md`) | `$CLAUDE_CONFIG_DIR/skills/` or `~/.claude/skills/` |
| MCP config | `~/.claude.json` (`mcpServers` key) |
| SessionStart hook | Merged into `~/.claude/settings.json` |
| MemPalace `Stop`/`PreCompact` hooks | Merged into `~/.claude/settings.json` |

Batman agent transforms for this host:
- Frontmatter `tools:` list is removed so the agent inherits every session-available tool (including any claude.ai cloud connectors and future MCP servers).
- `#tool:vscode/askQuestions` → `AskUserQuestion`, `#tool:agent/runSubagent` → `Agent`.
- `model: "opus"` is injected.
- The Claude-Code-only "Spec-Driven CLAUDE.md Synchronization" block is appended (idempotent — re-renders replace it in place).

Harness for the rendered Batman agent: `claude-code`.

### `--codex`

| Asset | Destination |
| --- | --- |
| Prompts (`*.prompt.md`) | `$CODEX_HOME/prompts/` or `~/.codex/prompts/` |
| Instructions (`*.instructions.md`) | Managed block appended to `$CODEX_HOME/AGENTS.md` or `~/.codex/AGENTS.md` |
| Skills (`<skill>/SKILL.md`) | `$USER_SKILLS_DIR` / `~/.agents/skills/` |
| MCP config | `$CODEX_HOME/config.toml` (`mcp_servers` key) |

Harness for the rendered Batman agent: `codex`.

## Dependencies

The CLI verifies (and installs when possible) a tiered set of tools.

`SetupMCPSpecs` — used by `setup mcp` and as the base of `setup full`:

| Tool | Minimum | Install path |
| --- | --- | --- |
| `node` | 22.0.0 | `brew install node` (macOS only); otherwise reports recovery instructions. |
| `npm` | 10.0.0 | Same. |
| `python3` | 3.9.0 | Tries `python3.13`/`3.12`/`3.11`/`3.10`/`python` (or `py -3.X` on Windows). Falls back to `uv venv` in `~/.local/share/coding-cli/python/<ver>` and exposes a `python3` shim on PATH. |
| `pip` | any | `python3 -m ensurepip --upgrade`. |
| `mempalace` | any | `python3 -m pip install --user mempalace` (or into the managed venv). |
| `rtk` | any | Downloads from `rtk-ai/rtk` GitHub releases, installs into `~/.local/bin` (Unix) or `%LOCALAPPDATA%\Programs\coding-cli\bin` (Windows), persists PATH. |

`SetupFullSpecs` — adds `git` (≥2.0.0) on top of `SetupMCPSpecs`.

`IndexingSpecs` — used by `run indexing` and the indexing phase of `setup full`. Replaces `rtk` with `cocoindex`, and requires `python3 ≥ 3.11`:

| Tool | Minimum | Install path |
| --- | --- | --- |
| `node`, `npm`, `mempalace` | Same as above. |
| `python3` | 3.11.0 | Same auto-discovery + uv fallback. |
| `pip` | 23.0.0 | `ensurepip --upgrade`. |
| `cocoindex` | 1.0.0 | `pip install --user cocoindex` (or into the managed venv). |

Outcomes are logged per-dependency: `skipped installing <name>; using <version>` when already satisfied, `installed <name> <version>` when freshly installed, `skipped optional dependency <name>` when not required and install failed.

## Logging

Every phase emits a `step: <message>` line, followed by success/skip lines. With `--verbose`, subprocess invocations are also printed. Setup is idempotent — log lines like `skipped query-code-mcp npm dependencies; node_modules already present` are expected on reruns.

## Recovery notes

- Workspace discovery fails → rerun with `--workspace-root /absolute/path`.
- MCP config parsing fails → fix the invalid JSON/TOML in the host config and rerun. Existing config is backed up to `<path>.bak` before any write.
- Asset conflict reported (`skipped-conflict`) → rerun with `--force` to overwrite. The previous file is backed up to `<path>.bak`.
- Indexing fails on `cocoindex update` → confirm the workspace contains at least one project directory beside `coding-cli/`, then rerun `coding-cli run indexing`.
- Shell still resolves an older `python3` after the uv fallback installed a new one → start a new shell or run `rehash`.
