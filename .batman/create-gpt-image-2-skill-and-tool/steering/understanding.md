# Understanding: GPT Image 2 Skill And Tool

## User Goal

Create a canonical `gpt-image-2` skill and a callable tool so other agents can generate and edit images through OpenAI's `gpt-image-2` model, using the Windows user `OPENAI_API_KEY` without copying, logging, or committing the credential.

## Task Slug

`create-gpt-image-2-skill-and-tool`

## Current Behavior

### Workflow Summary

- `coding-cli` is the host-agnostic canonical customization source for Claude Code, Codex, and VS Code / Copilot. Reusable workflows live under `skills/`, while MCP-backed behavior is registered separately per host (`README.md:3-13`, `README.md:27-31`).
- No canonical `gpt-image-2`, `imagegen`, or image-generation skill/tool exists. The only image-generation references describe an optional host capability or disabled context-compaction profile behavior; they do not provide an API-backed tool (`skills/gamedev-workflow/SKILL.md:59`, `docs/context-compaction/compatibility.md:25`).
- The repository already demonstrates one cross-host local MCP service, `mnemo`: a Python stdio entrypoint delegates to a FastMCP server, and Claude Code, Codex, and Copilot each register it in their native configuration (`mnemo/run_server.py:1-18`, `.mcp.json:1-14`, `.codex/config.toml:1-4`, `.vscode/mcp.json:1-13`).
- The existing Python environment has the MCP SDK and OpenAI SDK installed. `mnemo/requirements.txt` already records `mcp>=1.2.0` and `openai>=1.40.0`; current local versions observed during discovery are `mcp 1.26.0` and `openai 2.8.1` (`mnemo/requirements.txt:1-3`).
- Both process and Windows user scopes expose `OPENAI_API_KEY`. Discovery checked presence only; no credential value was printed, stored, or sent to memory.
- OpenAI's current Image API directly supports `gpt-image-2` through `/v1/images/generations` and `/v1/images/edits`. The Image API is the documented choice for a single prompt-driven generate/edit operation; the Responses API is for conversational multi-turn editing.
- `gpt-image-2` returns base64 image data, supports `png`, `jpeg`, and `webp`, accepts `low`, `medium`, `high`, or `auto` quality, and accepts flexible dimensions within documented constraints. It does not currently support transparent backgrounds.

### Why This Evidence Answers The Question

- `skills/` and each skill's `SKILL.md` frontmatter are the canonical discovery and activation surface, so their absence proves other agents have no shared image workflow today.
- The three host MCP configuration files are the current source of truth for how local tools become callable across Claude Code, Codex, and Copilot on this machine.
- `mnemo/run_server.py` and `mnemo/mnemo/server.py` establish the repository's current local stdio/FastMCP implementation pattern, including the invariant that stdout is reserved for JSON-RPC.
- OpenAI's Image API guide and endpoint schemas are authoritative for model selection, request fields, output encoding, image-edit behavior, size constraints, and retry boundaries.
- Presence-only environment inspection proves the authorized credential source is available without exposing the secret.

### Process Distinctions And Terminology

- Skill vs tool: the skill tells an agent when and how to generate, edit, prompt, save, inspect, and iterate; the MCP tool performs the authenticated API request and returns the result.
- Generate vs edit: generation sends a text prompt to `/v1/images/generations`; editing sends one or more reference images, an optional mask, and a prompt to `/v1/images/edits`.
- Image API vs Responses API: Image API is the direct single-operation surface requested here; Responses API adds conversational state and mainline-model token cost, which is broader than the minimum capability.
- Host registration vs plugin packaging: host configuration makes a local MCP server available on this machine; plugin packaging makes the skill/server installable as one bundle. The repository currently has Claude-compatible plugin metadata but no `.codex-plugin/` manifest or local marketplace (`.claude-plugin/plugin.json:1-8`; `.codex-plugin/` and `.agents/` absent).
- Credential source vs credential value: configuration may name `OPENAI_API_KEY` or allow the server to read the Windows user environment, but repository files, MCP output, logs, tests, and memory must never contain the value.

### Components Likely To Change And Why They Exist

- `skills/gpt-image-2/SKILL.md`: new activation and workflow contract for generation, edits, masks, prompt quality, output inspection, and iteration.
- `skills/gpt-image-2/agents/openai.yaml`: skill-list metadata and a dependency pointer to the tool when the chosen packaging surface supports it.
- A new Python MCP package and stdio entrypoint: focused `generate_image` and `edit_image` tools, API authentication, input validation, output saving/attachment, safe errors, and request IDs.
- MCP server tests: deterministic mocked HTTP coverage for schemas, credential lookup, request construction, base64 decoding, output paths, moderation errors, transient errors, and secret redaction.
- `.mcp.json`, `.codex/config.toml`, and `.vscode/mcp.json`: possible host registration points, following the existing `mnemo` shape.
- `.claude-plugin/plugin.json` and possibly a new `.codex-plugin/plugin.json`: possible packaging/discovery updates if the approved design makes the capability installable as one plugin rather than host-config-only.
- `README.md`: capability, setup, credential, and cross-host availability notes.
- `docs/prd/create-gpt-image-2-skill-and-tool.md`: required PRD after Requirements approval.

### Execution Locations

- Skill selection and workflow reasoning execute in the consuming agent after it discovers `skills/gpt-image-2/` through the canonical skills root or a plugin.
- API calls execute inside a local MCP server process, never inside skill prose. The process reads `OPENAI_API_KEY` at call time and sends it only in the OpenAI Authorization header.
- Generated files should be written only to an explicit or safely resolved local output location. Exact path/default policy belongs to Requirements and Design, not Phase 1.
- Host registration executes in each host's MCP configuration layer. Source presence alone does not make a tool globally callable in unrelated workspaces.

## Likely Change Surface

### Files And Symbols

- `skills/gpt-image-2/SKILL.md` — new skill trigger and workflow.
- `skills/gpt-image-2/agents/openai.yaml` — new UI metadata and possible MCP dependency declaration.
- New MCP server package under a task-approved path — server initialization, `generate_image`, `edit_image`, credential resolution, validation, API client, result serialization, and entrypoint.
- New focused test module(s) beside the MCP package or under `tests/`.
- `.mcp.json`, `.codex/config.toml`, `.vscode/mcp.json` — candidate local host registrations.
- `.claude-plugin/plugin.json`, possible `.codex-plugin/plugin.json` — candidate bundle declarations.
- `README.md` — inventory and setup documentation.

### Tests

- No repository-native general skill validator was found. The installed `skill-creator` provides `quick_validate.py` for skill naming/frontmatter checks.
- MCP behavior needs unit tests with a fake HTTP transport so normal validation does not spend API credits or send images externally.
- One explicitly identified live smoke generation can verify real API compatibility after deterministic tests. `quality=low` and a standard square size minimize cost and latency; edits can be tested live only if an approved fixture is available.
- Cross-host validation must distinguish source/config checks from actual owner acceptance in Claude Code, Codex, and Copilot.

### Configuration And Infrastructure

- No remote service deployment is required for local agents; a stdio MCP server is sufficient.
- The tool needs outbound HTTPS access to `https://api.openai.com/v1/images/generations` and `/v1/images/edits`.
- The key must come from process environment or, on Windows, the current user's environment store. No `.env`, config literal, fixture, snapshot, log, or memory entry may contain it.
- A plugin-packaged stdio server must use an install-location-safe launcher; hard-coded worktree paths would break cached/plugin installs.

### Documentation

- Add the required PRD after Requirements approval.
- An ADR is likely warranted only if Design chooses a hard-to-reverse packaging/registration boundary with a real trade-off, such as separate MCP server vs coupling to `mnemo`, or host registration vs plugin bundle.
- `README.md` should document availability, registration/setup, supported generate/edit behavior, credential sourcing, and the difference between mocked tests and paid live smoke tests.

## Evidence

- `README.md:3-13`: repository owns shared agent assets and currently documents `skills/`, `mnemo`, and host-specific MCP configuration.
- `README.md:27-31`: supported hosts are Claude Code, Codex, and VS Code / Copilot.
- `README.md:61-66`: secrets must not enter memory; current OpenAI key handling already prefers environment lookup; unrelated MCP configuration remains outside the repository.
- `.mcp.json:1-14`: Claude-compatible stdio MCP registration shape.
- `.codex/config.toml:1-4`: project-scoped Codex stdio MCP registration shape.
- `.vscode/mcp.json:1-13`: VS Code / Copilot stdio MCP registration shape.
- `mnemo/run_server.py:1-18`: current cross-working-directory Python stdio entrypoint pattern.
- `mnemo/mnemo/server.py:1-25`: current FastMCP server pattern and stdout/JSON-RPC logging boundary.
- `mnemo/requirements.txt:1-3`: MCP and OpenAI SDK dependencies already exist in the repository's Python toolchain.
- `.claude-plugin/plugin.json:1-8`: current source-discovery plugin metadata does not declare skills or MCP servers explicitly.
- Absence queries: `rg -n -i "gpt-image|imagegen|image_gen|image generation|image tool" .` plus direct checks for `.codex-plugin/`, `.agents/`, and `tools/`.
- Git history: MCP host configuration files were introduced together in commits `9070fa0` and `e17249c`, supporting one shared server with host-native adapters.
- Environment inspection: `OPENAI_API_KEY` present in both Process and Windows User scope; value never printed.
- OpenAI Image API guide: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI create-image schema: https://api.openai.com/v1/images/generations
- OpenAI image-edit schema: https://api.openai.com/v1/images/edits
- OpenAI Codex image-generation documentation: https://learn.chatgpt.com/docs/image-generation
- OpenAI MCP documentation: https://learn.chatgpt.com/docs/extend/mcp
- OpenAI plugin architecture: https://developers.openai.com/plugins/concepts/plugins
- Memory preflight: mnemo reachable; returned older gamedev-skill records only. None governed this task, so no retrieved decision was used.

## Visual Recap

- Path: `.batman/create-gpt-image-2-skill-and-tool/steering/understanding.html`
- Notes: Shows the current gap, skill/tool separation, direct Image API boundary, credential flow, likely change surface, and unresolved distribution boundary.

## Open Questions

- Distribution boundary: should “other agents” mean the three locally configured hosts only, or should this also become an installable Codex/ChatGPT plugin bundle? Recommended: implement the canonical skill plus standalone local MCP server first, wire all three current host adapters, and add installable plugin metadata only if it can use a relocatable launcher without duplicating canonical content.

## Risks And Constraints

- Image generation is a paid external action. Mocked tests must be the default; live tests must be small, intentional, and reported separately.
- API calls may take up to about two minutes, so MCP and host tool timeouts must exceed the documented worst-case latency without hanging indefinitely.
- `gpt-image-2` does not support transparent backgrounds. The tool must reject or clearly report unsupported `background=transparent` rather than silently changing it.
- Flexible sizes still require both edges to be multiples of 16, each edge at most 3840, aspect ratio at most 3:1, and total pixels between 655,360 and 8,294,400.
- Mask and first input image must match format and dimensions, be under 50 MB, and the mask must have an alpha channel. Validation should fail before a paid request when possible.
- Moderation-blocked/user-correctable errors must not be blindly retried. Transient `429` and `5xx` errors may use bounded retry with request IDs preserved.
- Returning large base64 payloads directly through MCP can stress message limits. Design must choose a safe file-plus-content policy for 2K/4K and multi-image outputs.
- Source presence does not equal cross-host activation. Each target host needs registration or plugin installation plus a fresh session/restart as applicable.
- Never expose the API key in tool metadata, structured output, exception text, request logs, fixtures, memory, or generated files.

## Architecture Change Assessment

- Status: `required`
- Reason: the task adds a new external-service MCP contract, credential boundary, paid side effect, binary result path, reusable skill workflow, and cross-host registration/packaging behavior.
- Areas affected: canonical skills, Python MCP runtime, HTTP/API contract, credential lookup, file output, host MCP configurations, plugin metadata, tests, and repository docs.

## Initial Verification Ideas

- Run `quick_validate.py` on `skills/gpt-image-2` and confirm `agents/openai.yaml` matches the final `SKILL.md`.
- Unit-test generate/edit request construction, schema validation, output decoding, filenames, path containment, error mapping, retries, and secret redaction with a fake transport.
- Start the MCP server through an in-process or stdio client; verify initialize, tools/list, valid calls, and invalid calls without network access.
- Run one low-quality live generation using the authorized Windows user key; record only model, request ID, output metadata/path, and pass/fail.
- Inspect the generated image rather than treating HTTP 200 as visual acceptance.
- Validate the three host adapter files and, if selected, plugin manifest/package structure.
- Run `git diff --check`, focused tests, secret scans, and the canonical code-review instructions.
