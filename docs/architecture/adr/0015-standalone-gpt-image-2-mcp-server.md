# 0015 — Isolate GPT Image 2 in a standalone local MCP server

Status: accepted · 2026-08-02 · amended 2026-08-04

## Context

`coding-cli` needs one reusable image-generation/editing capability across Claude Code, Codex, and VS Code / Copilot. The capability combines a paid external API action, a user credential, large base64 responses, local binary writes, moderation/error policy, and host-specific registrations. The repository's existing local MCP process, `mnemo`, owns shared memory and source indexing; coupling image behavior into it would make unrelated preflight availability depend on image dependencies and would mix sharply different confidentiality, latency, and side-effect contracts.

Source presence alone also does not activate tools in unrelated sessions. The integration needs a durable answer for canonical ownership, host adapters, and whether first-release distribution should be a local server or a plugin/remote service.

## Options considered

1. **Add image tools to `mnemo`.** Rejected: couples shared-memory preflight to paid binary generation, broadens its credential/content surface, and makes failures or dependency changes cross subsystem boundaries.
2. **Create separate host-specific scripts or copied skill bodies.** Rejected: duplicates security-critical code and agent guidance, inviting drift between Claude Code, Codex, and Copilot.
3. **Create one canonical standalone stdio MCP server plus one canonical skill and thin adapters (chosen).** Isolates dependencies/side effects while reusing the repository's proven local FastMCP pattern and current user registries.
4. **Package a marketplace plugin or deploy a remote MCP service immediately.** Rejected for the first release: relocatable launch, installation lifecycle, remote secret custody, authentication, storage, and operations add scope before the local contract is proven.

## Decision

- Add canonical skill `skills/gpt-image-2/` and standalone Python subsystem `gpt_image_2/`; do not modify `mnemo` runtime behavior.
- Expose exactly `generate_image` and `edit_image` over stdio FastMCP. Fix the model to `gpt-image-2` and use OpenAI's direct Image API through the async Python SDK.
- Read credentials per call from process `OPENAI_API_KEY`, falling back on Windows to the current-user environment store. Never accept or persist the value through MCP/configuration.
- Save every valid image locally with atomic no-overwrite publication. Return stable structured metadata and at most one inline preview bounded to 5 MiB decoded.
- Keep SDK retries disabled. Permit one retry only after an explicit retryable `429`/`5xx` response and only inside the remaining 180-second operation budget; never retry connection/read timeouts.
- Register the canonical launcher through thin repository and user adapters. Target the canonical checkout, not a task worktree; report activation pending until merge/sync and host reload.
- Defer plugin marketplace packaging, remote MCP deployment, Responses API conversations, and duplicated installed bodies.

## Consequences

- Image failures, latency, dependencies, and credentials cannot make mnemo unavailable.
- Each host may launch an independent stateless process, but all execute the same canonical implementation and defaults.
- The MCP process working directory remains user-selected output context; default files land under `generated-images/` there.
- Local source/config checks can complete before merge, while unrelated-session activation remains explicitly pending until the canonical path contains the server.
- Future plugin or remote distribution must solve relocatable startup and secret custody without copying the skill/server body and should supersede this ADR if it changes the ownership boundary.

## Rollout and rollback

Implement the canonical skill/server and fake-backed tests first. Add repository adapters, then guarded user registrations that preserve existing entries. Run one live low-quality generation only after deterministic gates pass. After merge/sync, reload each host and verify tool discovery separately.

If rollback is explicitly requested, remove only the `gpt-image-2` registrations and task-owned source/docs after resolving exact targets. Never reset, stash, or rewrite unrelated configuration; retain this ADR and supersede it if the decision changes.

## Implementation notes (2026-08-02, at acceptance)

Two details were sharpened while implementing, neither changing the decision:

- **Preview reporting.** The bound is unchanged — one inline image, at most 5 MiB decoded. The reported reason vocabulary became `null` / `too_large` / `first_of_n`. When several images are produced the first is still attached, so `first_of_n` describes what happened more honestly than a flat "omitted" would.
- **Codex tool timeout is load-bearing.** The documented Codex default `tool_timeout_sec` is **60 s**, well below this server's 180 s operation deadline. Without the explicit `tool_timeout_sec = 240` in the Codex registrations, the host would abort a normal high-quality generation before the server could return either an image or its structured error. Claude Code's equivalent is the client-side `MCP_TOOL_TIMEOUT` environment variable, which a `.mcp.json` entry cannot set, so it is documented for the operator rather than claimed in configuration. VS Code exposes no timeout field and is covered by a runtime gate instead.

## Amendment (2026-08-04, latency budgets raised)

The decision stands; its numbers moved and one of its claims turned out to be wrong.

Generations were failing often enough for the operator to notice. The cause was the server's own per-attempt bound, not a host: a `quality=high` call that runs past 150 s raises `APITimeoutError`, which this design deliberately never retries because the request may already have been billed. A too-short attempt timeout therefore does not merely fail, it fails after paying. The per-attempt timeout is now **480 s** and the operation deadline **540 s**, with Codex's `tool_timeout_sec` raised to **600 s** to stay above them. Read the "remaining 180-second operation budget" in the Decision and the `tool_timeout_sec = 240` in the implementation notes as the values accepted on 2026-08-02, superseded by these.

`RETRY_MIN_REMAINING_S` rose from 20 s to 240 s in the same pass. It reads like an admission gate but is really the floor on the second attempt's timeout — `_call_with_retry` admits the retry and then clamps it to `min(API_ATTEMPT_TIMEOUT_S, remaining)`. At 20 s it could admit a retry with a 20-second ceiling against a multi-minute generation, so that retry could only end in `api_timeout`: a second billed request with no chance of finishing, which also destroyed the actionable `service_error` it replaced.

**Correction to the 2026-08-02 implementation note.** That note stated Claude Code's tool timeout can only be set through the client-side `MCP_TOOL_TIMEOUT` environment variable and that "a `.mcp.json` entry cannot set it". That is no longer true, and the variable was the wrong instrument anyway. Claude Code v2.1.203+ accepts a per-server `timeout` in milliseconds on the registry entry itself, which overrides the variable for that server alone; `.mcp.json` and the user-scope `~/.claude.json` now both carry `"timeout": 600000`. It also becomes that server's effective idle window, which is harmless here — 600 s of silence still exceeds the 540 s the server is permitted to take, and an image generation is silent for its whole duration. `MCP_TOOL_TIMEOUT` was rejected deliberately: it is global and defaults to roughly 28 hours, so setting it to 600000 for this server's benefit would have *shortened* every other MCP server's ceiling to ten minutes — a regression bought to fix a problem Claude Code never had. Codex's 60 s default is real and its explicit `tool_timeout_sec` remains load-bearing.

The trade-off is unchanged in kind: a longer budget means a stuck paid call holds a host tool slot longer, which is why the deadline stays finite. The ordering the design depends on is also unchanged — attempt timeout < operation deadline < host tool timeout — and `tests/gpt_image_2/test_contract_gates.py` still enforces the Codex half of it.
