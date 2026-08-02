# Generic agent assets

`coding-cli` is the user's generic customization layer for coding agents — reusable prompts, instructions, the Batman entry agent, skills, and the self-hosted `mnemo` shared-memory engine. It is host-agnostic and works across Claude Code, Codex, and VS Code / Copilot.

## Repository layout

- `agents/batman.agent.md`: the generic Batman entry agent (routes every project through `generic-entry`)
- `skills/`: generic skills — `generic-entry`, `shared-memory`, `mnemo-setup`, `batman-understanding`, `byond-projects`, `gamedev-workflow`, `caveman*`, `visual-explainer`, `grill-me`, Robot Framework helpers, refactoring guides, etc. `gamedev-workflow` selectively composes game design/implementation, 3D, Godot FPS/particles/performance, and UI-motion disciplines with project specialists.
- `instructions/`: shared code-pattern, review, and visual guidance
- `prompts/`: reusable task prompts
- `mnemo/`: the self-hosted shared-memory engine + MCP server (see `mnemo/README.md`)
- `gpt_image_2/`: the standalone GPT Image 2 MCP server (`run_gpt_image_2_server.py` launches it)
- `.claude-plugin/`: Claude Code source discovery manifest
- `.codex/`, `.vscode/`: repository-scoped `mnemo` and `gpt-image-2` MCP configuration

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

## Images: gpt-image-2

A standalone stdio MCP server exposing two tools, `generate_image` and
`edit_image`, backed by OpenAI's direct Image API with the model fixed to
`gpt-image-2`. It is deliberately separate from `mnemo` (ADR 0015) so a paid,
credential-bearing, large-binary capability cannot make the shared-memory
preflight unavailable.

- Agent-facing workflow: `skills/gpt-image-2/SKILL.md`
- Server: `gpt_image_2/`, launched by `run_gpt_image_2_server.py`
- Dependencies: `py -3.12 -m pip install -r gpt_image_2/requirements.txt`
  (`mcp`, `openai`, `pillow`)

**Cost and latency.** Every call is billed by OpenAI, is subject to OpenAI
moderation, and can take up to about two minutes. The server allows one
operation 180 seconds end to end, with a 150-second per-attempt timeout.

**Credentials.** `OPENAI_API_KEY` is read from the server process environment
first, then — on Windows — from the current user's persistent environment
(`HKCU\Environment`), which is what makes it work in a host that was started
before you ran `setx`. The value is never accepted as a tool argument and never
appears in configuration, logs, results, or errors. Starting the server and
listing its tools need no credential; only a generation does.

**Output.** Images land in `<working-directory>/generated-images/` unless you
pass an absolute `output_dir`. The basename is the generic `image` — never
derived from the prompt — and files are **never overwritten**: a collision
becomes `image-2.png`, then `image-3.png`. Results always carry every absolute
path; one image is attached inline when it is at most 5 MiB.

**Controls.** `quality` (default `high`), `size` (default `1024x1024`; `auto` or
edges that are multiples of 16, max edge 3840, aspect at most 3:1, 655,360 to
8,294,400 total pixels), `output_format` (`png`/`jpeg`/`webp`),
`output_compression` (JPEG/WebP only), `n` (1 to 10), `background`
(`auto`/`opaque`), and `moderation` (`generate_image` only).

**Known limitation:** `gpt-image-2` does not support transparent backgrounds.
`background="transparent"` fails with a clear unsupported-option error rather
than silently returning an opaque image. API limits can drift; every constant
lives in `gpt_image_2/constants.py` so a change is a one-file edit.

**Registration and reload.** Repository adapters are in `.mcp.json`,
`.codex/config.toml`, and `.vscode/mcp.json`; equivalent user-scope entries
point at the canonical checkout. A host must reload MCP before the tools appear,
and user-scope entries only resolve once this work is merged into
`~/source/coding-cli`.

Host timeouts are not uniform, and the difference matters:

- **Codex** defaults `tool_timeout_sec` to **60 s**, which is below this
  server's 180 s deadline, so the registrations set `tool_timeout_sec = 240`
  explicitly. Without it Codex aborts normal high-quality generations.
- **Claude Code** controls its MCP tool timeout with the client-side
  `MCP_TOOL_TIMEOUT` environment variable (milliseconds). A `.mcp.json` entry
  cannot set it — an `env` block there configures the *server* child, not the
  client. Set `MCP_TOOL_TIMEOUT=240000` in Claude's own environment if you see
  image calls time out.
- **VS Code / Copilot** exposes no documented per-server timeout field.

**Troubleshooting.** `GPT_IMAGE_2_LOG_LEVEL` (default `WARNING`) sets the level
for the `gpt_image_2` logger only, on stderr. It deliberately does **not** touch
the root logger or raise `openai`/`httpx` verbosity: at DEBUG the OpenAI client
logs full request options, which for an edit includes the raw reference-image
and mask bytes, and for any call includes the prompt. Those loggers stay pinned
at `WARNING` whatever you set here. The value is case-insensitive and an
unrecognised one falls back to `WARNING` rather than failing the server at
startup.

**Testing.** `py -3.12 -m pytest tests/gpt_image_2` is fully offline and spends
nothing — the suite fails loudly if anything tries to build a real client.
`py -3.12 tests/gpt_image_2/mcp_smoke.py` drives the real stdio server with a
test-only fake backend. `tests/gpt_image_2/live_smoke.py` is the only script
that spends money and refuses to run without
`--i-understand-this-costs-money`.

## Security and operations

- Do not store secrets/tokens in memory; a redactor runs on every write.
- The `mnemo` OpenAI key resolves from `OPENAI_API_KEY` or `~/.mnemo/openai_api_key` (for hosts that do not pass the env through).
- `AGENTS.md` and `agents/batman.agent.md` are versioned normally. The `--skip-worktree` guard they used to carry was lifted 2026-07-16 once `origin` became this repo's own remote.
- Existing unrelated MCP servers, safety hooks, and RTK settings stay outside this repository.
