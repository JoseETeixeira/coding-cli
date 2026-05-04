# FreightHero Onboarding CLI

`coding-cli` now contains the `freighthero` Go CLI used to bootstrap a local FreightHero workspace.

The CLI handles five main jobs:

- clone missing FreightHero repositories
- install user-level prompts, instructions, agents, and skills
- verify or install local MCP-related dependencies
- write host-native MCP configuration
- build and refresh local indexing support

## Build

```bash
bash ./build.sh
go run . help
```

`build.sh` always writes the binary as `dist/freighthero`.

## Install Without Cloning

```bash
curl -fsSL https://raw.githubusercontent.com/Freight-Hero/coding-cli/main/install.sh | bash
```

The installer downloads the latest GitHub Release archive for your OS and CPU, installs `freighthero` into `$HOME/.local/bin` by default, and adds that directory to `PATH` when needed.

Optional overrides:

- `INSTALL_DIR=/custom/bin` to choose a different install directory
- `VERSION=v0.1.0` to pin a specific release tag
- `PROFILE_FILE=~/.zshrc` to force a specific shell profile update target

## Supported Hosts

- `--vscode`
- `--batman`
- `--claude-code`
- `--codex`

`setup agent` and `setup mcp` require exactly one explicit host flag.

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

The CLI verifies `git`, `node`, `npm`, `python3`, `pip`, `mempalace`, `cocoindex`, and optional `rtk`.

If a dependency already satisfies the minimum version, the CLI reports it as reused and skips reinstalling it.

## Recovery Notes

- If workspace discovery fails, rerun the command with `--freighthero-root`.
- If MCP config parsing fails, inspect the host config file and rerun after fixing the invalid JSON or TOML.
- If indexing fails, rerun `freighthero run indexing` after confirming `frontend`, `backend`, and `ai_watchtower` exist beside `coding-cli`.
- If the installer cannot find a release asset yet, push a tag such as `v0.1.0` so the GitHub release workflow can publish the `freighthero_<os>_<arch>.tar.gz` archives.
- If you want to inspect the exact command surface, run `freighthero help` or `freighthero <command> --help`.
