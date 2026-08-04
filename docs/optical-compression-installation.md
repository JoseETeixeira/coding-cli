# Install optical compression and use it with agents

Optical compression turns large, read-mostly text into rendered image pages so
an agent can understand the gist with fewer input tokens. The MCP server keeps
the exact original text in a local content-addressed store and returns a digest
that the agent can pass to `optical_retrieve` whenever precision matters.

This feature is fully offline and needs no API key. It is intentionally lossy
at the image layer: never trust a hash, UUID, path, line number, version, key, or
numeric literal read from a rendered page. Retrieve the exact text first.

## What gets installed

- `optical_compression/`: renderer, exact-text store, guard, CLI, and MCP server.
- `run_optical_compression_server.py`: stable stdio MCP launcher.
- `skills/optical-compression/SKILL.md`: agent policy and usage instructions.
- `run_optical_compression_hook.py`: optional Claude Code `Read` hook.
- One MCP registration for each host that should expose
  `optical_compress`, `optical_retrieve`, and `optical_stats`.

The MCP server works with Claude Code, Codex, and VS Code/Copilot. Automatic
tool-output replacement works only with Claude Code. Codex and Copilot agents
call `optical_compress` explicitly.

## 1. Clone and install dependencies

Python 3.12 is the supported repository runtime. On Windows PowerShell:

```powershell
git clone https://github.com/JoseETeixeira/coding-cli.git "$env:USERPROFILE\source\coding-cli"
Set-Location "$env:USERPROFILE\source\coding-cli"
py -3.12 -m pip install -r optical_compression/requirements.txt

$repo = (Get-Location).Path
$python = py -3.12 -c "import sys; print(sys.executable)"
```

If the repository is already cloned, update `$repo` to its absolute path. Use
the same Python interpreter for dependency installation and every MCP
registration; otherwise the host may start a Python environment that lacks
`mcp` or Pillow.

For an isolated environment, create a virtual environment first and use its
absolute Python executable in the registrations:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r optical_compression/requirements.txt
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
```

On macOS or Linux, use the equivalent `python3.12` and
`<repo>/.venv/bin/python` paths.

## 2. Register the MCP server

Choose user scope when agents in other repositories should see the tools.
Repository-scoped examples already live in `.mcp.json`, `.codex/config.toml`,
and `.vscode/mcp.json`; replace their absolute paths when the clone lives
somewhere else.

Before adding an entry, inspect the host's current MCP configuration. Update an
existing `optical-compression` entry instead of creating a duplicate. Never
paste unrelated configuration or credentials into setup logs.

### Claude Code

The current Claude CLI supports user-scoped stdio registration:

```powershell
claude mcp add --scope user --transport stdio optical-compression -e CLAUDECODE=1 -- "$python" "$repo\run_optical_compression_server.py"
```

The equivalent user configuration is an `optical-compression` entry under
`mcpServers` in `~/.claude.json`:

```json
{
  "mcpServers": {
    "optical-compression": {
      "type": "stdio",
      "command": "C:/absolute/path/to/python.exe",
      "args": ["C:/absolute/path/to/coding-cli/run_optical_compression_server.py"],
      "env": { "CLAUDECODE": "1" }
    }
  }
}
```

Merge this object into the existing file; do not replace the whole file.

### Codex

Codex writes MCP registrations to `~/.codex/config.toml`:

```powershell
codex mcp add --env CODEX_SESSION=1 optical-compression -- "$python" "$repo\run_optical_compression_server.py"
```

Equivalent TOML:

```toml
[mcp_servers.optical-compression]
command = "C:/absolute/path/to/python.exe"
args = ["C:/absolute/path/to/coding-cli/run_optical_compression_server.py"]
env = { CODEX_SESSION = "1" }
startup_timeout_sec = 30
```

Codex exposes all three MCP tools, but it cannot replace another tool's output
with an image. This is an upstream host limitation, not a missing setting. Have
the agent call `optical_compress` explicitly.

### VS Code / Copilot

Open the VS Code User `mcp.json` and merge this server into `servers`:

```json
{
  "servers": {
    "optical-compression": {
      "type": "stdio",
      "command": "C:/absolute/path/to/python.exe",
      "args": ["C:/absolute/path/to/coding-cli/run_optical_compression_server.py"]
    }
  }
}
```

Use User scope for availability across workspaces or copy the same entry into
this repository's `.vscode/mcp.json` for repository scope.

After any registration change, fully restart the host or reload its MCP
servers. Existing agent sessions usually keep the tool catalog captured at
session start.

## 3. Expose the skill to agents

MCP registration exposes tools. Skill installation teaches agents when and how
to use them. Keep `coding-cli` as the canonical skill body; use a directory
pointer or the customization-path environment variable rather than copying the
file into multiple host directories.

Batman/custom-host installations can point the complete skill catalog at the
checkout:

```powershell
[Environment]::SetEnvironmentVariable(
    "USER_SKILLS_DIR",
    (Join-Path $repo "skills"),
    "User"
)
```

For native host discovery, directory junctions keep one canonical copy. This
PowerShell snippet skips every target that already exists; inspect such targets
manually instead of overwriting them:

```powershell
$skillSource = Join-Path $repo "skills\optical-compression"
$skillTargets = @(
    "$env:USERPROFILE\.claude\skills\optical-compression",
    "$env:USERPROFILE\.codex\skills\optical-compression",
    "$env:USERPROFILE\.agents\skills\optical-compression"
)

foreach ($target in $skillTargets) {
    if (Test-Path -LiteralPath $target) {
        Write-Warning "Already exists; inspect manually: $target"
        continue
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    New-Item -ItemType Junction -Path $target -Target $skillSource | Out-Null
}
```

On macOS or Linux, create equivalent symbolic links beneath
`~/.claude/skills/`, `~/.codex/skills/`, and `~/.agents/skills/`.

Restart the host after changing skill discovery. In a fresh session, invoke the
skill by name (`$optical-compression`) or route every repository task through
`skills/generic-entry/SKILL.md`; `generic-entry` automatically selects optical
compression for qualifying large, read-mostly payloads.

If an agent does not support native skills, add a thin pointer to its root
instructions instead of copying the skill body:

```text
When a read-mostly log, transcript, agent history, or already-reviewed diff is
over roughly 8,000 characters, read
<coding-cli>/skills/optical-compression/SKILL.md and follow it. Use rendered
pages only for gist; call optical_retrieve before relying on any exact value.
```

## 4. Optional automatic Claude Code hook

Claude Code can automatically replace a qualifying oversized `Read` result.
The hook acts only when all safety conditions pass: at least 10,000 characters,
balanced density, and no identifier-shaped content. Any uncertainty leaves the
original text untouched.

Activate the hook through exactly one path:

1. Load this checkout as a Claude Code plugin so `hooks/hooks.json` supplies the
   `PostToolUse` hook; or
2. Add one thin `Read` hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          {
            "type": "command",
            "command": "py -3.12 \"C:/absolute/path/to/coding-cli/run_optical_compression_hook.py\"",
            "timeout": 30,
            "statusMessage": "Optical gist for oversized Read output"
          }
        ]
      }
    ]
  }
}
```

Merge this entry with existing hooks. Do not enable both paths simultaneously;
double execution wastes work and can produce confusing results.

Set `OPTICAL_COMPRESSION_HOOK=0` in the Claude Code environment to disable
automatic interception without removing configuration. Codex and Copilot have
no equivalent interception path; explicit MCP calls are expected there.

## 5. Use it from an agent

Start with a capability and cost check:

```text
Use $optical-compression. Call optical_stats with a representative preview and
tell me whether compression pays, which host profile is active, and whether the
automatic hook is available.
```

For an explicit compression request:

```text
Read build.log. If it is large and read-mostly, call optical_compress with the
content, density="balanced", and source="build.log". Use the images for the
summary. Before quoting any path, line number, version, hash, UUID, key, or
number, call optical_retrieve with the returned digest and verify it against the
exact text.
```

The normal tool sequence is:

1. `optical_stats(preview=...)` when value or host capability is uncertain.
2. `optical_compress(content=..., density="balanced", source=...)`.
3. Read the returned image pages for gist and navigation.
4. `optical_retrieve(digest=..., start=..., length=...)` for exact spans.

`balanced` is the default. `safe` uses larger text and fewer savings.
`aggressive` is unsuitable for identifier-bearing content and is automatically
downgraded when the guard detects it. Payloads under 8,000 characters or those
whose projected image cost exceeds text cost are declined; send the original
text instead.

Use optical compression for long logs, transcripts, histories, generated
output, and already-reviewed diffs. Do not use it for source you are about to
edit, security-sensitive material, or any task dominated by exact values. A
manual `optical_compress` call stores the complete input locally, so never pass
credentials, tokens, or secrets.

### Delegating to another agent

An agent or subagent may start with a stale skill catalog. Carry the obligation
in the task prompt when delegation matters:

```text
For large read-mostly payloads, load
<coding-cli>/skills/optical-compression/SKILL.md and use the
optical-compression MCP tools. Treat rendered pages as gist only. Retrieve and
verify exact identifiers, paths, line numbers, and numeric values before using
or returning them. If the skill or MCP tools are unavailable, continue from the
original text and report that optical compression was unavailable.
```

## 6. Verify the installation

Run offline tests with the same Python interpreter used by the MCP host:

```powershell
& $python -m pytest tests/optical_compression
& $python tests/optical_compression/mcp_smoke.py
& $python -m optical_compression benchmark --suite all
```

Then restart the host and ask a fresh agent to call `optical_stats`. Confirm:

- `status` is `ok`;
- `mcp_tools` is `true`;
- `detected_host` matches the registration marker; and
- `automatic_hook` is `true` only on Claude Code.

The stdio smoke test is the strongest setup check because it launches the same
server entrypoint and exercises the same JSON-RPC transport as the agents.

## Store, retention, and cleanup

Both production launchers default to `~/.optical-compression`. Keep the MCP
server and Claude hook on the same `OPTICAL_COMPRESSION_DIR`; otherwise a digest
created by one process cannot be retrieved by the other.

The store contains exact source text plus rendered segment images. Entries stay
until explicitly pruned. This command removes entries older than 14 days from
the production store:

```powershell
$env:OPTICAL_COMPRESSION_DIR = Join-Path $env:USERPROFILE ".optical-compression"
py -3.12 -m optical_compression prune --days 14
```

Review the resolved path before using `--days 0`, which removes every optical
store entry. Pruning does not touch files outside the optical-compression store.

## Troubleshooting

`optical_compress` is missing:

- Restart the host after MCP registration.
- Confirm the configured Python and launcher paths are absolute and exist.
- Run `tests/optical_compression/mcp_smoke.py` with that Python interpreter.

The server reports `ModuleNotFoundError` for `mcp` or `PIL`:

- Install `optical_compression/requirements.txt` with the exact Python
  executable used in the MCP entry.

`optical_retrieve` returns `not_found`:

- Confirm the hook and server use the same `OPTICAL_COMPRESSION_DIR`.
- Confirm the entry was not pruned and the host was not pointed at another
  checkout or user profile.

Claude Code does not compress a `Read` automatically:

- Call `optical_stats` and check `automatic_hook`.
- Confirm exactly one hook activation path is configured.
- Expected pass-through cases include payloads below 10,000 characters,
  identifier-bearing content, non-`Read` tools, and the kill switch.

Codex does not compress tool output automatically:

- Expected behavior. Call `optical_compress` explicitly.

Compression returns `declined`:

- Expected when the payload is too small or image tokens would not beat text
  tokens. Keep the original text.

For performance and fidelity evidence, see
`docs/optical-compression-replication.md`. For the governing safety and host
decisions, see ADR 0016 and ADR 0017 under `docs/architecture/adr/`.
