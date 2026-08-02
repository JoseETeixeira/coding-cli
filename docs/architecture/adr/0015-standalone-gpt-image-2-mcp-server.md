# 0015 — Isolate GPT Image 2 in a standalone local MCP server

Status: accepted · 2026-08-02

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
