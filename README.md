# coding-cli

A workspace bootstrapper for AI coding assistants. One command installs shared prompts, agents, and skills into your assistant of choice, wires up an MCP server that searches every project in your workspace, and keeps the codebase index fresh.

Supports VS Code (with GitHub Copilot), Claude Code, and Codex. The same skills/prompts library is rendered to whichever host you target.

## Quickstart

Clone this repo into a `coding-cli/` directory inside your workspace root, alongside the projects you want indexed:

```text
<workspace-root>/
  coding-cli/        # this repo
  <project-1>/       # your code
  <project-2>/
```

Build and install the binary:

```bash
# macOS / Linux / Git Bash on Windows
bash ./build.sh
mkdir -p "$HOME/.local/bin"
install -m 0755 ./dist/coding-cli "$HOME/.local/bin/coding-cli"
# add to PATH if missing: echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && exec $SHELL
```

```powershell
# Windows PowerShell
.\build.ps1
$bin = "$env:LOCALAPPDATA\Programs\coding-cli\bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null
Copy-Item .\dist\coding-cli.exe $bin -Force
$current = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not ($current -split ';' -contains $bin)) {
  [Environment]::SetEnvironmentVariable('Path', "$bin;$current", 'User')
}
# restart PowerShell so the new PATH takes effect
```

> Prefer a one-liner that handles directory + PATH for you? Use the install scripts: `bash ./install.sh` or `powershell -ExecutionPolicy Bypass -File .\install.ps1`. See [docs/install-and-build.md](docs/install-and-build.md).

Then run one of the following from inside the workspace.

### VS Code + Claude Code

```bash
coding-cli setup full --claude-code
```

Installs Batman agent + skills under `~/.claude/`, writes `~/.claude.json` MCP config, builds `query-code-mcp`, runs the SessionStart hook that refreshes the index, and runs the first `cocoindex update`.

### VS Code + GitHub Copilot

```bash
coding-cli setup full --vscode
```

Installs prompts/agents/skills into the VS Code user prompts folder (Copilot Chat picks them up), writes `mcp.json` so Copilot's MCP integration can call the `query-code` server, and indexes the workspace.

### VS Code + Codex

```bash
coding-cli setup full --codex
```

Installs assets under `~/.codex/`, writes the `mcp_servers` block into `~/.codex/config.toml`, and indexes the workspace.

### Common follow-ups

```bash
coding-cli run indexing      # refresh the codebase index manually
coding-cli setup agent --vscode --force   # re-sync prompts/skills, overwriting local edits
coding-cli help              # full command reference
```

## Docs

The detailed reference lives in [docs/](docs/README.md):

- [CLI reference](docs/cli-reference.md) — every command, flag, host, and recovery note.
- [Install and build](docs/install-and-build.md) — bash and PowerShell scripts, cross-compile, release workflow.
- [query-code MCP](docs/query-code-mcp.md) — CocoIndex pipeline, environment variables, MCP tools.
- [Shipped skills](docs/skills.md) — catalog of every skill installed by `setup agent`.
- [Shipped prompts](docs/prompts.md) — catalog of every prompt, instruction, and agent file.
