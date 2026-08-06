# Generic agent assets

`coding-cli` is the user's generic customization layer for coding agents — reusable prompts, instructions, the Batman entry agent, skills, and the self-hosted `mnemo` shared-memory engine. It is host-agnostic and works across Claude Code, Codex, and VS Code / Copilot.

## Repository layout

- `agents/batman.agent.md`: the generic Batman entry agent (routes every project through `generic-entry`)
- `skills/`: generic skills — `generic-entry`, `shared-memory`, `mnemo-setup`, `batman-understanding`, `byond-projects`, `gamedev-workflow`, `caveman*`, `visual-explainer`, `grill-me`, Robot Framework helpers, refactoring guides, etc. `gamedev-workflow` selectively composes game design/implementation, 3D production and source-aligned model/animation verification, Godot FPS/particles/performance, and accessible UI-motion disciplines with project specialists.
- `instructions/`: shared code-pattern, review, and visual guidance
- `prompts/`: reusable task prompts
- `mnemo/`: the self-hosted shared-memory engine + MCP server (see `mnemo/README.md`)
- `gpt_image_2/`: the standalone GPT Image 2 MCP server (`run_gpt_image_2_server.py` launches it)
- `optical_compression/`: the offline optical-gist MCP server and Claude Code hook
- `.claude-plugin/`: Claude Code source discovery manifest
- `.codex/`, `.vscode/`: repository-scoped MCP configuration for all three local servers

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

## Token cost: optical-compression

A standalone stdio MCP server that renders large read-mostly text payloads as
images, which cost fewer tokens than the text they replace, and stores the exact
original for retrieval by digest. Fully offline: no network, no credentials.

- Agent-facing workflow: `skills/optical-compression/SKILL.md`
- Server: `optical_compression/`, launched by `run_optical_compression_server.py`
- Hook (Claude Code only): `run_optical_compression_hook.py`
- Installation and agent usage: `docs/optical-compression-installation.md`
- Replication: `docs/optical-compression-replication.md`
- Decisions: ADR 0016 (lossy gist + exact retrieval), ADR 0017 (host asymmetry)
- Dependencies: `py -3.12 -m pip install -r optical_compression/requirements.txt`
  (`mcp`, `pillow`)

Measured on this repository's own source: `context_compaction/activation.py`,
46,637 characters, 11,660 text tokens to 4,329 image tokens — **2.69x, a 62.9%
reduction** — with a byte-identical retrieval roundtrip.

**This is lossy for exact values by design.** Read the image for gist, then call
`optical_retrieve` before relying on any hash, UUID, key, path, or numeric
literal. At the aggressive density, trials scored 99.4% character accuracy while
losing 25% of identifiers: it flipped a digit in a UUID and mangled an
access-key. A guard refuses identifier-bearing payloads for automatic
compression, and payloads under 8,000 characters are declined outright because
rendering them would cost more than the text.

**Host asymmetry.** The MCP tools work on Claude Code and Codex alike. Automatic
hook interception is Claude-Code-only and cannot be added to Codex, which
rejects `updatedMCPToolOutput` upstream (PR #20703 closed unmerged). Call
`optical_stats` to see which profile is active. Kill switch:
`OPTICAL_COMPRESSION_HOOK=0`.

**Store and activation.** Both production launchers default to the same stable
user-scoped store, `~/.optical-compression`, so a digest created by Claude's
hook remains retrievable through the MCP server even when the host starts them
from different working directories. `OPTICAL_COMPRESSION_DIR` overrides it.
Repository adapters live in `.mcp.json`, `.codex/config.toml`, and
`.vscode/mcp.json`; user-scope adapters point at this canonical checkout so the
tools work from other repositories after host reload. Claude Code can activate
the `Read` hook through either `hooks/hooks.json` as an installed plugin or one
thin user-settings pointer—never both.

The canonical `generic-entry` workflow routes large read-mostly payloads to
`skills/optical-compression/SKILL.md`. Host skill copies remain thin pointers;
the skill body is never duplicated into host configuration.

Colour-encoding text as pixels does **not** work and the benchmark proves it
every run: additive mixing collapses 256 letter-pairs into 27 colours, and
vision encoders patchify at 28x28px so exact RGB never reaches the model.

**Testing.** `py -3.12 -m pytest tests/optical_compression` is fully offline.
`py -3.12 tests/optical_compression/mcp_smoke.py` drives the real stdio server;
`py -3.12 -m optical_compression benchmark --suite all` reproduces every
published performance and fidelity claim.

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
moderation, and is slow: a high-quality generation commonly runs for several
minutes. The server allows one operation 540 seconds end to end, with a
480-second per-attempt timeout. Those bounds were 180 and 150 until 2026-08-04,
which turned out to be under the real latency — and the resulting `api_timeout`
is never retried, because the request may already have been billed. Budget for
minutes, not seconds.

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
  server's 540 s deadline, so the registrations set `tool_timeout_sec = 600`
  explicitly. Without it Codex aborts normal high-quality generations.
- **Claude Code** takes a per-server `timeout` in milliseconds on the server's
  registry entry (`.mcp.json` and the user-scope `~/.claude.json`), so both are
  set to `600000`. Do not reach for the `MCP_TOOL_TIMEOUT` environment variable
  instead: it is global, and its default is roughly 28 hours, so setting it to
  600000 to help this server would *shorten* every other server's ceiling to
  ten minutes. The per-server field is scoped and overrides the variable for
  this server only. It also becomes this server's effective idle window, which
  is fine here: 600 s of silence is still more than the 540 s the server is
  allowed to take. Note the `env` block in a registry entry configures the
  *server child process*, not the client, and cannot set either. Requires
  Claude Code v2.1.203 or later.
- **VS Code / Copilot** exposes no documented per-server timeout field.

A tool call still running after two minutes is not stuck. Claude Code moves a
long MCP call to a background task at that point and delivers the result as a
notification; the wall-clock limit above still applies while it runs there.

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
