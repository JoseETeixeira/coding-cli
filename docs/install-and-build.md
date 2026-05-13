# Install and build

Four scripts ship at the repository root, two for each shell family. All four detect the host OS and target architecture automatically.

## install.sh / install.ps1 — fetch a published release

Both scripts download the latest GitHub release archive, extract the binary, drop it into a per-user bin directory, and add that directory to the user PATH.

### Bash (macOS / Linux / Git Bash / MSYS / Cygwin / WSL)

```bash
bash ./install.sh
```

OS detection:

| `uname -s` | Resolved OS | Archive | Default install dir |
| --- | --- | --- | --- |
| `Darwin` | `darwin` | `.tar.gz` | `$HOME/.local/bin` |
| `Linux` | `linux` | `.tar.gz` | `$HOME/.local/bin` |
| `MINGW*`/`MSYS*`/`CYGWIN*` | `windows` | `.zip` | `%LOCALAPPDATA%\Programs\coding-cli\bin` (via `cygpath -u` when available) |

Environment variables override behavior:

| Variable | Effect |
| --- | --- |
| `VERSION` | Install a specific tag (e.g. `v0.2.0`) instead of the latest release. |
| `INSTALL_DIR` | Override the bin directory. |
| `INSTALL_BASE_URL` | Skip GitHub and download `<BASE>/<asset>` directly (useful for testing local builds: `INSTALL_BASE_URL=file://$PWD/dist`). |
| `OWNER`, `REPO`, `BINARY_NAME` | Override the GitHub coordinates. Defaults: `JoseETeixeira` / `coding-cli` / `coding-cli`. |
| `GITHUB_PAT_TOKEN` / `GH_TOKEN` / `GITHUB_TOKEN` | Used as bearer auth for the GitHub API (required for private repos). |

PATH persistence:

- Unix: appends `export PATH=...` to `~/.zshrc`, `~/.bashrc`, `~/.bash_profile`, or `~/.profile` depending on `$SHELL`.
- Windows shells: invokes `powershell.exe` to `[Environment]::SetEnvironmentVariable('Path', ..., 'User')`.

### PowerShell (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Same defaults as the bash variant on Windows. Parameters:

| Parameter | Effect |
| --- | --- |
| `-Version v0.2.0` | Install a specific tag. |
| `-InstallDir <path>` | Override the bin directory (default `$env:LOCALAPPDATA\Programs\coding-cli\bin`). |
| `-InstallBaseUrl <url>` | Skip GitHub and pull from a custom URL. |
| `-Owner`, `-Repo`, `-BinaryName` | Override GitHub coordinates. |

Architecture detection: `$env:PROCESSOR_ARCHITECTURE`. `AMD64` → `amd64`, `ARM64` → `arm64`, `x86` is rejected.

## build.sh / build.ps1 — build from source

Both scripts wrap `go build` and write the binary into `dist/`. Pass `ARCHIVE=true` (bash) or `-Archive` (PowerShell) to also produce a release archive (`.tar.gz` on Unix targets, `.zip` on Windows targets).

### Bash

```bash
bash ./build.sh                              # native build
GOOS=linux GOARCH=amd64 bash ./build.sh      # cross-compile
ARCHIVE=true bash ./build.sh                 # also produce dist/coding-cli_<os>_<arch>.{tar.gz,zip}
```

Output naming:

| Scenario | File |
| --- | --- |
| Native build | `dist/coding-cli` (or `dist/coding-cli.exe` on Windows) |
| Cross-compile | `dist/coding-cli_<os>_<arch>` (or `…_<os>_<arch>.exe`) |
| Archive | `dist/coding-cli_<os>_<arch>.tar.gz` or `…_<os>_<arch>.zip` |

Host vs target detection runs `go env GOOS` / `go env GOARCH` in a subshell with `GOOS=` and `GOARCH=` unset, so an exported `GOOS=linux` is treated as a cross-compile request even when running on Windows.

On Windows under Git Bash, archive creation prefers `zip` when present and falls back to `powershell.exe Compress-Archive` otherwise.

### PowerShell

```powershell
.\build.ps1                                  # native build
.\build.ps1 -TargetOS linux -TargetArch amd64
.\build.ps1 -Archive                          # also produce dist/<binary>_<os>_<arch>.zip
```

Same output-naming rules. `Compress-Archive` is used for `.zip`; `.tar.gz` builds require `tar` (Windows 10 1803+ ships it; otherwise install via Git, MSYS, or run `build.sh` under a POSIX shell).

## GitHub release workflow

[`.github/workflows/release.yml`](../.github/workflows/release.yml) runs on `v*` tag pushes (and on manual dispatch). Matrix:

| GOOS | GOARCH | Archive |
| --- | --- | --- |
| `darwin` | `amd64` | `tar.gz` |
| `darwin` | `arm64` | `tar.gz` |
| `linux` | `amd64` | `tar.gz` |
| `linux` | `arm64` | `tar.gz` |
| `windows` | `amd64` | `zip` |
| `windows` | `arm64` | `zip` |

All jobs run on `ubuntu-latest`; Windows jobs install the `zip` package and rely on `build.sh` for cross-compilation. Published assets follow the `coding-cli_<os>_<arch>.<ext>` naming the install scripts expect.

## Verifying without installing globally

```bash
bash ./build.sh
./dist/coding-cli --help
./dist/coding-cli setup full --vscode --workspace-root /tmp/example
```

```powershell
.\build.ps1
.\dist\coding-cli.exe --help
.\dist\coding-cli.exe setup full --vscode --workspace-root C:\tmp\example
```

The binary is fully self-contained — no shared libraries, no runtime dependencies beyond what `setup full` itself installs.
