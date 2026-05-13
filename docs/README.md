# coding-cli wiki

Detailed reference for everything `coding-cli` ships and configures. The top-level [README](../README.md) covers the quickstart; pages here go deeper.

## Pages

- **[CLI reference](cli-reference.md)** — every subcommand, flag, host profile, dependency, and recovery note.
- **[Install and build](install-and-build.md)** — `install.sh` / `install.ps1` / `build.sh` / `build.ps1`, cross-compile, GitHub release workflow.
- **[query-code MCP](query-code-mcp.md)** — the workspace codebase MCP server: CocoIndex pipeline, environment variables, exposed MCP tools.
- **[Shipped skills](skills.md)** — every skill that `setup agent` copies into your assistant's skills folder.
- **[Shipped prompts](prompts.md)** — every prompt, instruction, and agent file in [prompts/](../prompts/).

## What gets installed where

When you run `coding-cli setup full --<host>`, three things happen:

1. **Assets** (prompts, instructions, agents, skills) are copied from this repo into the host's user-level customization folder. The exact destinations are listed in [cli-reference.md](cli-reference.md#host-profiles).
2. **MCP configuration** is written into the host's native config (`mcp.json`, `~/.claude.json`, or `~/.codex/config.toml`). The generated config always includes the `query-code`, `mempalace`, and `github` servers — see [query-code-mcp.md](query-code-mcp.md) for the `query-code` details.
3. **Indexing** runs: `query-code-mcp` is built, a Python venv is created with `cocoindex` installed, `mempalace wake-up` is called, and the workspace is indexed for the first time. After that, the SessionStart hook (Claude Code only) keeps it fresh.

## How the workspace is discovered

`coding-cli` resolves the workspace root by walking upward from the current directory until it finds a folder containing a `coding-cli/` child. Override it with `--workspace-root /absolute/path`. Every other top-level folder in that root (except `coding-cli/` itself) is treated as a project to index. Restrict the set with `CODEBASE_PROJECTS=projA,projB`.
