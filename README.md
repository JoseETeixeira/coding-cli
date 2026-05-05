# FreightHero Onboarding CLI

`coding-cli` now contains the `freighthero` Go CLI used to bootstrap a local FreightHero workspace.

The CLI handles five main jobs:

- clone missing FreightHero repositories
- install user-level prompts, instructions, agents, and skills
- verify or install local MCP-related dependencies
- write host-native MCP configuration
- build and refresh local indexing support

## Install From Downloaded Release Binary

This repository is private. Release binaries must be downloaded from an authenticated GitHub session, either in the browser or with GitHub CLI.

Published assets:

- `freighthero_darwin_arm64.tar.gz`
- `freighthero_darwin_amd64.tar.gz`
- `freighthero_linux_arm64.tar.gz`
- `freighthero_linux_amd64.tar.gz`

Option 1: sign in to GitHub in the browser, open the private Releases page for `Freight-Hero/coding-cli`, and download the matching archive.

Option 2: use GitHub CLI after authenticating:

```bash
gh auth login
gh release download v0.1.3 -R Freight-Hero/coding-cli -p 'freighthero_darwin_arm64.tar.gz'
```

Install the extracted binary into your local bin directory:

```bash
tar -xzf freighthero_darwin_arm64.tar.gz
mkdir -p "$HOME/.local/bin"
install -m 0755 freighthero "$HOME/.local/bin/freighthero"
freighthero help
```

If `$HOME/.local/bin` is not already on `PATH`, add it in your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Install From Built Binary

If you already have a checkout of this private repository, you can build and install the binary locally instead of downloading a release archive.

Build the current platform binary:

```bash
bash ./build.sh
./dist/freighthero help
```

`build.sh` always writes the current-platform binary to `dist/freighthero`.

Install that built binary into your local bin directory:

```bash
mkdir -p "$HOME/.local/bin"
install -m 0755 ./dist/freighthero "$HOME/.local/bin/freighthero"
freighthero help
```

If `$HOME/.local/bin` is not already on `PATH`, add it in your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Build

```bash
bash ./build.sh
go run . help
```

`build.sh` always writes the binary as `dist/freighthero`.

## Supported Hosts

- `--vscode`
- `--batman`
- `--claude-code`
- `--codex`

`setup agent` requires exactly one explicit host flag.

`setup mcp` auto-detects the host when exactly one supported host is present. Otherwise pass one of the flags above.

`setup full` can auto-detect a host only when exactly one supported host is present. Otherwise pass one of the flags above.

## Commands

```bash
freighthero repositories clone
freighthero setup agent --vscode
freighthero setup mcp --codex
freighthero run indexing
freighthero setup full --batman
freighthero help
```

## Common Flags

- `--freighthero-root`: explicit FreightHero workspace root
- `--force`: allow FreightHero-managed files to be rewritten
- `--verbose`: print extra setup diagnostics

## Expected Workspace Layout

The CLI expects a FreightHero root that contains:

```text
freighthero/
	coding-cli/
	frontend/
	backend/
	ai_watchtower/
```

`freighthero repositories clone` creates that root under the current working directory by default.

## Examples

Clone the sibling repositories into a fresh workspace:

```bash
freighthero repositories clone
```

Install user-level Batman assets from an existing workspace:

```bash
freighthero setup agent --batman --freighthero-root ~/src/freighthero
```

Configure Codex MCP entries and build the local codebase server:

```bash
freighthero setup mcp --codex --freighthero-root ~/src/freighthero
```

Run the full onboarding flow from an existing `coding-cli` checkout:

```bash
freighthero setup full --vscode --freighthero-root ~/src/freighthero
```

Build a local binary named `freighthero`:

```bash
bash ./build.sh
./dist/freighthero help
```

## Dependency Behavior

`freighthero setup mcp` verifies the MCP setup prerequisites: `node`, `npm`, `python3`, `pip`, `mempalace`, and `rtk`.

`freighthero run indexing` adds the indexing-only requirements on top of the local build: a newer `python3`, `pip`, and `cocoindex`.

`freighthero setup full` performs the setup work first, then runs the indexing dependency check and indexing refresh as the final phase.

When `python3` is missing or too old, the CLI first tries to expose an existing versioned interpreter such as `python3.11`. If no suitable interpreter is available, it uses `uv` to create a FreightHero-managed Python environment, exposes its `python3` on your PATH automatically, and installs `mempalace` and `cocoindex` into that managed environment.

If your interactive shell still resolves an older `python3` immediately after setup, start a new shell or run `rehash` before retrying.

If a dependency already satisfies the minimum version, the CLI reports it as reused and skips reinstalling it.

`rtk` is installed from the official `rtk-ai/rtk` GitHub release assets for macOS, Linux, and Windows when it is missing.

Generated MCP config always includes:

- `freighthero-codebase` for the local FreightHero codebase MCP server
- `mempalace` for project memory
- `github` as the remote GitHub MCP endpoint at `https://api.githubcopilot.com/mcp/`

`freighthero run indexing` and the indexing phase inside `freighthero setup full` run `mempalace wake-up` first, then `cocoindex update`, and log every step including skipped build/config steps.

If `setup full` reaches the final indexing phase and your machine does not yet satisfy the CocoIndex Python requirement, the MCP config and user-level assets are still installed first.

## Recovery Notes

- If workspace discovery fails, rerun the command with `--freighthero-root`.
- If MCP config parsing fails, inspect the host config file and rerun after fixing the invalid JSON or TOML.
- If indexing fails, rerun `freighthero run indexing` after confirming `frontend`, `backend`, and `ai_watchtower` exist beside `coding-cli`.
- If the release asset you need does not exist yet, push a new `v*` tag so the GitHub release workflow can publish the `freighthero_<os>_<arch>.tar.gz` archives.
- If you want to inspect the exact command surface, run `freighthero help` or `freighthero <command> --help`.
