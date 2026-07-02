# FreightHero Onboarding CLI

`coding-cli` ships the `freighthero` Go CLI that bootstraps a local FreightHero
workspace. It handles five jobs:

- clone the sibling FreightHero repositories
- install user-level assistant assets (prompts, instructions, agents, skills)
- verify or install local MCP dependencies
- write host-native MCP configuration
- build and refresh the local codebase index

## Requirements

- macOS or Linux
- `curl` and `tar` (used by the install script)
- `git`, plus a GitHub account with access to the private `Freight-Hero/coding-cli` repo
- Go 1.22+ only if you build from source

## Install (macOS / Linux)

The repository and its releases are private, so every install path needs an
authenticated GitHub session. Export a token once — a fine-grained or classic PAT
with read access, or the `gh` CLI token:

```bash
export GH_TOKEN="$(gh auth token)"   # or: export GITHUB_PAT_TOKEN=ghp_xxxxx
```

### Option 1 — install script (recommended)

From a checkout of this repo:

```bash
bash ./install.sh
freighthero help
```

`install.sh` detects your OS and CPU architecture, resolves the latest published
release, downloads the matching `freighthero_<os>_<arch>.tar.gz`, installs the
binary to `~/.local/bin`, and appends that directory to your shell profile's
`PATH` when it is missing.

Optional overrides (environment variables):

| Variable | Default | Purpose |
| --- | --- | --- |
| `VERSION` | latest release | Install a specific tag, e.g. `VERSION=v1.0.0` |
| `INSTALL_DIR` | `~/.local/bin` | Destination directory for the binary |
| `PROFILE_FILE` | auto (`.zshrc` / `.bashrc` / `.profile`) | Shell profile the `PATH` export is appended to |
| `GH_TOKEN` / `GITHUB_PAT_TOKEN` / `GITHUB_TOKEN` | – | Auth token for the private repo and releases |
| `INSTALL_BASE_URL` | – | Fetch the archive from a custom base URL instead of the GitHub release |

Example — pin a version and install into a custom bin directory:

```bash
VERSION=v1.0.0 INSTALL_DIR="$HOME/bin" bash ./install.sh
```

### Option 2 — manual download with GitHub CLI

```bash
gh auth login
gh release download v1.0.0 -R Freight-Hero/coding-cli -p 'freighthero_darwin_arm64.tar.gz'
tar -xzf freighthero_darwin_arm64.tar.gz
mkdir -p "$HOME/.local/bin"
install -m 0755 freighthero "$HOME/.local/bin/freighthero"
freighthero help
```

Published assets per release:

- `freighthero_darwin_arm64.tar.gz` (Apple Silicon)
- `freighthero_darwin_amd64.tar.gz` (Intel Mac)
- `freighthero_linux_arm64.tar.gz`
- `freighthero_linux_amd64.tar.gz`

### Option 3 — build from source

```bash
bash ./build.sh
mkdir -p "$HOME/.local/bin"
install -m 0755 ./dist/freighthero "$HOME/.local/bin/freighthero"
freighthero help
```

`build.sh` always writes the current-platform binary to `dist/freighthero`.

If `~/.local/bin` is not already on your `PATH`, add it in your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Commands

Run `freighthero help` or `freighthero <command> --help` for the exact surface at
any time.

### Global flags

These persistent flags work on every command:

- `--freighthero-root <path>` — absolute path to the FreightHero workspace root (otherwise discovered from the current directory)
- `--force` — replace or rewrite FreightHero-managed files even when they differ from the source
- `--verbose` — print verbose subprocess and config diagnostics

### Host flags

`setup agent`, `setup mcp`, and `setup full` target one assistant host:

- `--vscode` — VS Code / Copilot user-level configuration
- `--batman` — Batman user-level configuration
- `--claude-code` — Claude Code user-level configuration
- `--codex` — Codex user-level configuration

`setup agent` requires exactly one host flag. `setup mcp` and `setup full`
auto-detect the host when exactly one supported host is present; otherwise pass a
flag explicitly.

### `freighthero setup full [--<host>]`

The full onboarding flow, end to end: resolve and validate the workspace, clone
the sibling repos, resolve the host, verify dependencies, sync user-level assets,
build the local `freighthero-mcp` server, write host MCP config, install the
Claude Code SessionStart hook (Claude Code only) and git guardrails, then run the
indexing dependency check and codebase index refresh. Persists the workspace root
so later `run indexing` calls work from anywhere.

```bash
freighthero setup full --batman
freighthero setup full --claude-code --freighthero-root ~/src/freighthero
```

Optional flags: host flag (auto-detected if omitted), `--freighthero-root`, `--force`, `--verbose`.

### `freighthero run indexing [--freighthero-root <path>]`

Refresh the local codebase index for the current working directory. Workspace
resolution order: `--freighthero-root` → nearest FreightHero-layout ancestor of
the cwd → the default workspace persisted by the last `setup` run. What gets
indexed depends on where you run it:

- cwd is the workspace root → every top-level project is indexed
- cwd is inside a project → just that project is indexed
- cwd is outside the workspace → the cwd itself is indexed as a standalone project

```bash
freighthero run indexing
freighthero run indexing --freighthero-root ~/src/freighthero
```

Optional flags: `--freighthero-root`, `--verbose`.

### `freighthero setup agent --<host>`

Install user-level assistant assets (prompts, instructions, agents, skills) for
one host, plus the Claude Code SessionStart hook (Claude Code only) and git
guardrails. Does not touch MCP config or indexing.

```bash
freighthero setup agent --batman
freighthero setup agent --vscode --freighthero-root ~/src/freighthero
```

Required flag: exactly one host flag. Optional flags: `--freighthero-root`, `--force`, `--verbose`.

### `freighthero setup mcp [--<host>]`

Verify MCP dependencies, build the local `freighthero-mcp` codebase server, and
write host-native MCP config. Persists the workspace root for later
`run indexing` calls.

```bash
freighthero setup mcp --codex
freighthero setup mcp --claude-code --verbose
```

Optional flags: host flag (auto-detected if omitted), `--freighthero-root`, `--verbose`.

### `freighthero repositories clone`

Clone the core FreightHero repositories (`frontend`, `backend`, `ai_watchtower`)
as siblings of `coding-cli`. With no `--freighthero-root`, the workspace is
created under the current directory.

```bash
freighthero repositories clone
freighthero repositories clone --freighthero-root ~/src/freighthero
```

Optional flags: `--freighthero-root`.

## Expected Workspace Layout

The CLI expects a FreightHero root that contains:

```text
freighthero/
	coding-cli/
	frontend/
	backend/
	ai_watchtower/
```

`freighthero repositories clone` creates that root under the current working
directory by default.

## Dependency Behavior

- `setup mcp` verifies the MCP prerequisites: `node`, `npm`, `python3`, `pip`, `mempalace`, and `rtk`.
- `run indexing` adds the indexing-only requirements on top: a newer `python3`, `pip`, and `cocoindex`.
- `setup full` runs the setup work first, then the indexing dependency check and index refresh as the final phase. If the machine does not yet satisfy the CocoIndex Python requirement, the MCP config and user-level assets are still installed first.
- When `python3` is missing or too old, the CLI first tries to expose an existing versioned interpreter (e.g. `python3.11`). If none is suitable, it uses `uv` to create a FreightHero-managed Python environment, exposes its `python3` on your PATH, and installs `mempalace` and `cocoindex` into it. If your shell still resolves an older `python3` right after setup, start a new shell or run `rehash`.
- A dependency that already meets the minimum version is reported as reused and skipped.
- `rtk` is installed from the official `rtk-ai/rtk` GitHub release assets when missing.

Generated MCP config always includes:

- `freighthero-codebase` — the local FreightHero codebase MCP server
- `mempalace` — project memory
- `github` — the remote GitHub MCP endpoint at `https://api.githubcopilot.com/mcp/`

`run indexing` (and the indexing phase inside `setup full`) runs `mempalace
wake-up` first, then `cocoindex update`, logging every step including skipped
build/config steps.

## Recovery Notes

- If workspace discovery fails, rerun the command with `--freighthero-root`.
- If MCP config parsing fails, inspect the host config file and rerun after fixing the invalid JSON or TOML.
- If indexing fails, rerun `freighthero run indexing` after confirming `frontend`, `backend`, and `ai_watchtower` exist beside `coding-cli`.
- If the release asset you need does not exist yet, push a new `v*` tag so the release workflow can publish the `freighthero_<os>_<arch>.tar.gz` archives.
- To inspect the exact command surface, run `freighthero help` or `freighthero <command> --help`.
