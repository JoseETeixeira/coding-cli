# Requirements: GPT Image 2 Skill And Tool

## Status

Approved on 2026-08-02 after an eleven-question grill pass fixed output location/naming, local edit inputs, inline previews, live validation, and request defaults. No implementation is authorized until Design and Task Planning are each approved.

## Problem Statement

Agents using the canonical `coding-cli` customization layer do not share a callable image-generation/editing capability. A robust solution must combine agent-facing workflow guidance with a paid external API tool, local binary outputs, secret isolation, API-specific validation, and registrations for the user's active Claude Code, Codex, and VS Code / Copilot hosts.

## Phase 2a Discovery Record

Discovery was read-only and ran before this draft.

- `rg -n -i "gpt-image|imagegen|image_gen|image generation|image tool" .` plus direct directory checks found no existing canonical `gpt-image-2` skill or MCP service to extend.
- Reads of `README.md`, `.mcp.json`, `.codex/config.toml`, `.vscode/mcp.json`, `mnemo/run_server.py`, `mnemo/mnemo/server.py`, and `mnemo/requirements.txt` confirmed the current cross-host pattern: one CWD-independent Python stdio/FastMCP server with thin host-native registrations.
- A safe user-config inspection printed only server names and the existing `mnemo` launcher. `~/.codex/config.toml`, `~/.claude.json`, and `%APPDATA%/Code/User/mcp.json` exist and contain user-wide MCP registries; none contains an image server. No EduCode or Cursor `mcp.json` exists at the checked paths.
- Presence-only environment checks confirmed `OPENAI_API_KEY` in both the current process and Windows User scope. No value was printed, persisted, or sent to memory.
- The installed runtime is Python 3.12.10 with `mcp 1.26.0` and `openai 2.8.1`; exact dependency floors remain a Design decision and must be verified against `gpt-image-2` behavior.
- Official OpenAI Image API guide and endpoint schemas confirmed direct generation/edit endpoints, base64 outputs, supported output formats and quality values, multiple edit inputs plus masks, documented size rules, error/request-ID behavior, and the absence of transparent-background support in `gpt-image-2`.
- The skill-creator contract requires scaffolding through `init_skill.py`, complete `SKILL.md` frontmatter, generated/validated `agents/openai.yaml`, focused script tests, and `quick_validate.py`.
- The approved Phase 1 boundary is a standalone local MCP server plus canonical skill, wired to the three current host adapters. Installable marketplace/plugin packaging is deferred unless a later design proves a relocatable package without duplicating canonical bodies.
- `CONTEXT.md` is specific to the separate context-compaction domain. No unresolved image-domain term requires modifying it; the glossary below is sufficient.

Outcome: requirements cover a new architecture component, three live host registries, a paid external side effect, and local file writes. Source/config validation is not equivalent to post-merge host activation or visual acceptance.

## Official API Baseline

- Image generation guide: https://developers.openai.com/api/docs/guides/image-generation
- Generate endpoint: https://api.openai.com/v1/images/generations
- Edit endpoint: https://api.openai.com/v1/images/edits
- Codex image-generation guidance: https://learn.chatgpt.com/docs/image-generation

Documented behavior can drift. Implementation shall isolate API constants and fail clearly when the live service rejects a formerly valid request; it shall not silently reinterpret inputs.

## Glossary

- **Calling agent**: the Claude Code, Codex, or VS Code / Copilot agent invoking the MCP tool.
- **Generate operation**: prompt-only Image API request to create new image content.
- **Edit operation**: Image API request combining a prompt with one or more local reference images and an optional alpha mask.
- **Bounded inline content**: MCP image content included only when a Design-defined byte/count limit keeps the response safe.
- **User error**: invalid input, moderation block, or another documented `image_generation_user_error` that should not be retried unchanged.
- **Transient error**: retryable rate-limit or service failure such as HTTP `429` or selected `5xx` responses.
- **Canonical checkout**: `%USERPROFILE%/source/coding-cli`, the path used by existing user-level adapters after merge/sync.

## Stakeholders

- **Primary**: user requesting images and agents operating through the three configured hosts.
- **Secondary**: `coding-cli` maintainers, reviewers, and downstream projects receiving generated assets.
- **External**: OpenAI API/service and organization administrators responsible for access and billing.

## Goals

1. Give agents a discoverable, disciplined workflow for raster generation and editing.
2. Provide stable local MCP operations backed only by `gpt-image-2` and the direct Image API.
3. Save valid image files safely and return useful bounded results.
4. Use the authorized Windows user credential without exposing or persisting it.
5. Make the capability available through the current Claude Code, Codex, and VS Code / Copilot adapter surfaces.
6. Prove core behavior without paid calls, then separately prove one minimal live call and inspect its image.

## Non-Goals

- Conversational/multi-turn image editing through the Responses API.
- Partial-image streaming, background jobs, queues, web UI, or remote MCP deployment.
- Transparent-background output while `gpt-image-2` does not support it.
- Arbitrary model selection, model fallback, bulk batch generation, fine-tuning, or image uploads by URL/file ID.
- Automatic prompt moderation bypasses or retries of unchanged user-correctable requests.
- Overwriting existing output files or editing/deleting unrelated local files.
- Publishing to a marketplace or claiming ChatGPT plugin compatibility in the first release.
- Treating HTTP success or mocked tests as artistic, owner, or all-host runtime acceptance.
- Committing, pushing, merging, or broadly staging changes unless separately requested.

## Functional Requirements

### IMG-REQ-001 — Discoverable canonical skill

**User Story:** As an agent, I want a discoverable `gpt-image-2` skill so that I can choose generation or editing and follow a reliable image workflow.

- WHEN a user explicitly asks to create, generate, revise, transform, inpaint, or otherwise edit a raster image through OpenAI, THEN the skill SHALL activate and identify the appropriate MCP operation.
- WHEN the requested output is better implemented as existing SVG/vector/code-native UI, THEN the skill SHALL defer to the more appropriate code/vector workflow instead of calling the image API.
- WHEN the task is an image edit, THEN the skill SHALL inspect every available local reference before calling the tool and preserve user-identified invariants.
- AFTER a successful call, the skill SHALL inspect the saved result, compare it with the requested intent, and perform only targeted iterations that remain within the user's scope.
- The skill SHALL disclose that calls are external, paid, moderation-governed, and may take roughly two minutes.
- The package SHALL include validated `SKILL.md` frontmatter and `agents/openai.yaml` metadata without duplicating the workflow body.

### IMG-REQ-002 — Separate fixed-model operations

**User Story:** As a calling agent, I want separate generation and edit operations so that tool schemas remain clear and misuse is locally detectable.

- The MCP server SHALL expose distinct `generate_image` and `edit_image` tools under one `gpt-image-2` server.
- WHEN either tool sends an API request, THEN it SHALL use model `gpt-image-2`; no caller-supplied model or automatic fallback SHALL be accepted.
- `generate_image` SHALL require a nonblank prompt and MAY accept an absolute output directory override.
- `edit_image` SHALL require a nonblank prompt and at least one local reference-image path; it MAY accept one local mask path and an absolute output directory override.
- Neither operation SHALL accept remote URLs, OpenAI file IDs, API keys, arbitrary headers, or raw endpoint overrides.
- Tool metadata SHALL truthfully identify local file writes, paid external network use, and non-read-only behavior.

### IMG-REQ-003 — Documented request controls

**User Story:** As a creator, I want supported quality, size, format, and count controls so that I can trade detail, dimensions, latency, and cost intentionally.

- WHEN a prompt is supplied, THEN the tool SHALL enforce the documented nonblank maximum of 32,000 characters before network activity.
- The tool SHALL accept `quality` only from `auto`, `low`, `medium`, or `high`; WHEN omitted during normal use, THEN it SHALL default to `high`.
- The tool SHALL accept `output_format` only from `png`, `jpeg`, or `webp`, SHALL default to `png` when omitted, and SHALL write the matching extension/MIME type.
- The tool SHALL accept `n` only in the current documented range `1..10` for operations where the endpoint supports it; WHEN omitted, THEN it SHALL default to `1`.
- The tool SHALL accept `size=auto` or a `WIDTHxHEIGHT` value satisfying current `gpt-image-2` rules: integer edges, multiples of 16, edge limits, total-pixel limits, and maximum 3:1 aspect ratio. WHEN omitted, THEN size SHALL default to `1024x1024`. Exact boundary constants SHALL live in one validated source.
- The tool SHALL accept `output_compression` only from `0..100` and only for JPEG/WebP; an incompatible PNG/compression combination SHALL fail locally.
- The tool SHALL accept moderation only from `auto` or `low`.
- The tool SHALL accept background only as `auto` or `opaque`; `transparent` SHALL fail with a clear unsupported-model error instead of being silently changed.
- Unsupported or mutually incompatible controls SHALL fail before credential lookup and before a paid request.

### IMG-REQ-004 — Safe local edit inputs

**User Story:** As a user editing an image, I want bad references and masks rejected locally so that I do not pay for a request that cannot succeed.

- WHEN an edit input is provided, THEN the server SHALL resolve it as a local regular file and reject missing files, directories, unsupported image formats, malformed images, and files at or above the documented 50 MB limit.
- The server SHALL support the documented PNG, JPEG/JPG, and WebP edit inputs and SHALL not fetch remote resources.
- WHEN multiple reference images are supplied, THEN their order SHALL be preserved and the skill SHALL explain that the first image is the mask target.
- WHEN a mask is supplied, THEN it SHALL match the first reference image's dimensions and format and SHALL contain a meaningful alpha channel; otherwise the call SHALL fail locally.
- Input validation errors SHALL identify the offending path/field without returning image bytes or unrelated filesystem information.

### IMG-REQ-005 — Credential isolation and precedence

**User Story:** As the credential owner, I want the server to use my Windows user `OPENAI_API_KEY` without exposing it so that agents can call OpenAI safely.

- WHEN `OPENAI_API_KEY` exists in the server process environment, THEN the server SHALL use it.
- WHEN process scope is absent on Windows, THEN the server SHALL read `OPENAI_API_KEY` from the current user's environment store at call time.
- WHEN neither source is available, THEN the operation SHALL stop with an actionable missing-key error before any network request.
- The server SHALL NOT accept the key through tool arguments, command-line arguments, committed configuration, fixtures, generated metadata, logs, exceptions, MCP results, memory, or output files.
- Error serialization and diagnostic logging SHALL redact the resolved key and SHALL never include Authorization headers or complete raw request/response bodies.
- Host registrations SHALL name or forward the environment variable only where required; they SHALL never contain its value.

### IMG-REQ-006 — Collision-safe atomic outputs

**User Story:** As a user, I want generated images saved predictably without overwriting files so that results and existing assets remain safe.

- WHEN the caller omits `output_dir`, THEN the server SHALL use `<working-directory>/generated-images/`, resolving the working directory at call time.
- WHEN the caller supplies `output_dir`, THEN it SHALL be absolute; the server SHALL not reinterpret a relative override against an ambiguous host path.
- The server MAY create the derived or requested output directory and missing descendants, but SHALL not delete, move, or modify pre-existing files.
- WHEN the caller omits a basename, THEN the server SHALL use generic basename `image`; it SHALL NOT derive filenames from prompt content.
- An optional caller basename SHALL be reduced to a safe filename component; path separators, reserved Windows names, traversal segments, and control characters SHALL not escape the output directory.
- WHEN a target name already exists, THEN the server SHALL append the first available one-based collision suffix after the unsuffixed name, producing names such as `image.png`, `image-2.png`, and `image-3.png`; the first release SHALL expose no overwrite mode.
- The server SHALL base64-decode and validate every returned image before publishing any output.
- Each image SHALL be written to a temporary file in the destination directory, flushed, and atomically renamed to its final collision-safe path.
- WHEN a multi-image response is incomplete or invalid, THEN no invalid partial file SHALL be published; successfully validated files and failures SHALL be reported without overwriting anything.

### IMG-REQ-007 — Bounded useful MCP results

**User Story:** As a calling agent, I want structured result metadata and viewable bounded content so that I can locate, inspect, and report the output without flooding the MCP channel.

- EVERY successful result SHALL include operation, fixed model, absolute output path, output format/MIME type, byte count, decoded dimensions, and image index for each file.
- WHEN OpenAI supplies a request ID, usage data, or revised prompt, THEN the result SHALL include the safe available fields without inventing missing values.
- The server SHALL always make local file paths the durable result.
- WHEN one or more results fit within a Design-defined total byte/count threshold, THEN the server SHALL include bounded MCP image-content previews in output order; larger results SHALL still return every metadata/path entry without embedding unbounded base64.
- Results and logs SHALL not echo full prompts, input images, masks, base64 payloads, or credential-bearing API bodies.

### IMG-REQ-008 — Safe error and retry behavior

**User Story:** As an agent, I want actionable stable failures so that I can correct inputs or report service problems without accidental repeated spending.

- WHEN the API returns an image-generation user error or moderation block, THEN the server SHALL not retry the unchanged request.
- Moderation failures SHALL return a stable safe code, a useful coarse explanation when provided, and request ID when available; they SHALL not recommend evasion.
- WHEN the API returns a selected `429`, `5xx`, connection, or timeout failure, THEN the server MAY retry with Design-defined bounded attempts, backoff, and jitter.
- The total operation deadline SHALL be finite while accommodating documented image-generation latency.
- WHEN retries exhaust, THEN the result SHALL preserve the last safe status/error code and request ID where available.
- Unexpected exceptions SHALL become a stable internal-error result with stderr diagnostics that remain secret- and payload-safe.

### IMG-REQ-009 — Cross-host registration and canonical ownership

**User Story:** As the user of multiple agent hosts, I want the same canonical server available to Claude Code, Codex, and VS Code / Copilot so that image behavior does not drift by host.

- Repository `.mcp.json`, `.codex/config.toml`, and `.vscode/mcp.json` SHALL add thin registrations for the new CWD-independent launcher without altering existing servers.
- User-wide `~/.claude.json`, `~/.codex/config.toml`, and `%APPDATA%/Code/User/mcp.json` SHALL receive equivalent thin registrations without copying source or credentials and without changing unrelated entries.
- User-wide registrations SHALL target the canonical checkout, not the temporary task worktree.
- WHEN the canonical checkout does not yet contain the merged server, THEN implementation evidence SHALL report the registration as pending activation rather than claiming the tool works in unrelated sessions.
- Post-merge activation SHALL require a host MCP reload/restart and one tool-list or harmless validation check per available host; any unrun host gate remains unverified.
- Marketplace/plugin manifests and duplicated installed skill bodies are outside the first release.

### IMG-REQ-010 — Deterministic mocked verification

**User Story:** As a maintainer, I want comprehensive no-cost tests so that routine verification never sends prompts or images externally.

- Default tests SHALL replace the OpenAI boundary with a fake and SHALL make zero external API calls.
- Tests SHALL cover valid generation/edit construction; all cross-field validation; process/Windows credential precedence; missing-key behavior; ordered references and mask rules; base64/image validation; collision-safe atomic paths; bounded inline results; request IDs; moderation/user errors; transient retries; deadlines; and secret redaction.
- An MCP smoke test SHALL initialize the stdio server, list both tools, execute a fake-backed valid call, and exercise an invalid call without network access.
- The new skill SHALL be scaffolded with `init_skill.py`, its metadata generated/checked with `generate_openai_yaml.py`, and its final package SHALL pass `quick_validate.py`.
- A secret scan SHALL check changed repository/config/test/evidence files without printing the environment value.

### IMG-REQ-011 — Minimal live and visual validation

**User Story:** As a user, I want one real low-cost proof so that mocked compatibility is not mistaken for a working OpenAI integration.

- AFTER deterministic tests pass, one opt-in live generation SHALL use `gpt-image-2`, `quality=low`, `n=1`, and a standard 1024×1024 size unless the live API requires an approved adjustment.
- The live smoke SHALL use the authorized environment credential and SHALL record only safe model, request ID, timing, output metadata/path, and pass/fail evidence.
- The saved output SHALL be opened and visually inspected for decodability and prompt relevance; HTTP success alone SHALL not pass the visual smoke.
- Live edit testing SHALL remain optional unless a reviewed fixture is added; lack of a live edit SHALL be reported separately from mocked edit coverage.
- Organization verification, billing, moderation, or service access failures SHALL be reported as external blockers and SHALL not weaken or bypass safeguards.

### IMG-REQ-012 — Documentation and honest acceptance

**User Story:** As a future maintainer, I want source-backed setup and limitation documentation so that the capability can be used and diagnosed without rediscovery.

- README and skill documentation SHALL explain supported operations/controls, cost and latency, credential precedence, dependency setup, output behavior, host registration/reload, and common safe failures.
- Documentation SHALL state that `gpt-image-2` currently lacks transparent-background support and that current API limits can drift.
- The task SHALL produce a PRD after Requirements approval and SHALL offer an ADR in Design for the server/package/registration boundary.
- Final reporting SHALL distinguish mocked tests, live API smoke, visual inspection, source registrations, and actual per-host activation.
- No completion claim SHALL generalize an unrun visual, host, owner, organization-access, or release gate.

## Non-Functional Requirements

### Security and privacy

- Minimize prompt/image retention outside the caller-selected outputs and OpenAI request.
- Avoid logging content by default; diagnostics use event type, safe error code, and request ID.
- Resolve and validate all filesystem targets before writes, and keep temporary files within the destination directory.

### Reliability

- A malformed or partial API response cannot overwrite an existing asset.
- Retried calls remain bounded and visible in result metadata.
- Server startup and `tools/list` do not require an API key or network access.

### Performance and context efficiency

- Skill prose uses progressive disclosure and does not load API reference detail until needed.
- Image content embedded in MCP is bounded; file paths remain the scalable result channel.
- Validation avoids decoding an input repeatedly within one request.

### Compatibility and maintainability

- Windows user-environment lookup is isolated behind a portable credential interface.
- OpenAI-specific constants, error mapping, and request construction have one owner and focused tests.
- Existing MCP registrations and `mnemo` behavior remain intact.

## Acceptance Criteria

- **IMG-AC-001**: `skills/gpt-image-2/SKILL.md` and `agents/openai.yaml` exist, contain no unresolved placeholders, and pass `quick_validate.py` plus metadata consistency checks.
- **IMG-AC-002**: MCP `tools/list` exposes exactly the approved generate/edit operations with no credential, model override, URL input, or overwrite argument.
- **IMG-AC-003**: Mocked valid generation and multi-reference masked edit calls produce the approved OpenAI request shape with `model=gpt-image-2` and no real network traffic.
- **IMG-AC-004**: Table-driven invalid prompt, size, quality, count, format/compression, transparency, reference, mask, and path cases fail before credential lookup/API invocation.
- **IMG-AC-005**: Credential tests prove process scope wins, Windows User scope is the fallback, missing credentials fail clearly, and a canary secret is absent from logs/results/exceptions.
- **IMG-AC-006**: Output tests prove the default `<working-directory>/generated-images/` location, generic `image` basename, explicit absolute override behavior, matching formats/dimensions, atomic publication, collision-safe suffixes, basename containment, zero overwrite, and cleanup of temporary files after failures.
- **IMG-AC-007**: Small results include approved metadata and bounded viewable content; over-threshold/multi-image results retain all files and metadata without unbounded MCP base64.
- **IMG-AC-008**: User/moderation errors are attempted once; transient errors follow the approved bounded retry/deadline policy and preserve safe request IDs.
- **IMG-AC-009**: A fake-backed stdio test initializes, lists tools, runs one valid call, and rejects one invalid call while stdout remains valid JSON-RPC.
- **IMG-AC-010**: Repository adapters and the three approved user registries contain equivalent thin entries, preserve all prior servers, contain no secret value, and target only the canonical launcher.
- **IMG-AC-011**: Default focused tests, Python import/compile checks, skill validation, config parsing, secret scan, and `git diff --check` pass.
- **IMG-AC-012**: One low/1024×1024 live generation returns a valid saved image and safe request metadata, and visual inspection confirms the file opens and materially follows the smoke prompt.
- **IMG-AC-013**: README, PRD, accepted ADR if selected, skill, and evidence agree on supported controls, cost/latency, credential/output policy, reload requirements, and unperformed gates.
- **IMG-AC-014**: Final review finds no unrelated worktree edits, secret disclosure, remote input fetch, arbitrary model/endpoint escape, overwrite path, or coupling to mnemo.

## Confirmed Decisions And Approval Assumptions

- `output_dir` is optional. When absent, the tool uses `<working-directory>/generated-images/`; an explicit override must be absolute.
- The default basename is generic `image`; prompt content is never used in a filename.
- Normal calls default to `quality=high`; the single validation smoke explicitly uses `low` to minimize test cost.
- Normal calls default to `size=1024x1024`; callers select other valid dimensions explicitly.
- Normal calls default to lossless `output_format=png`.
- Normal calls default to `n=1`; additional variants require an explicit count.
- Generated names never overwrite and use numeric collision suffixes such as `image-2.png`. A separate filesystem action, not this paid tool, owns any deliberate replacement/removal.
- Local path inputs only are sufficient for initial edits; URL and OpenAI-file inputs remain excluded.
- All successful images are written to disk. The MCP result also includes inline previews when they fit within a threshold selected in Design; paths remain authoritative for every result.
- Initial cross-host activation uses the current user registries and canonical checkout path. The task does not copy the implementation into user configuration folders.
- Default verification is mocked. The approved implementation may make exactly one minimal live generation smoke after all deterministic gates pass.

## Requirement Traceability Seed

| Concern | Requirements | Acceptance |
| --- | --- | --- |
| Skill and operation contract | IMG-REQ-001, IMG-REQ-002 | IMG-AC-001, IMG-AC-002, IMG-AC-003 |
| API controls and edit inputs | IMG-REQ-003, IMG-REQ-004 | IMG-AC-003, IMG-AC-004 |
| Credentials and secrets | IMG-REQ-005 | IMG-AC-005, IMG-AC-010, IMG-AC-014 |
| Output and MCP response | IMG-REQ-006, IMG-REQ-007 | IMG-AC-006, IMG-AC-007 |
| Errors and retries | IMG-REQ-008 | IMG-AC-008, IMG-AC-009 |
| Host availability | IMG-REQ-009 | IMG-AC-010, IMG-AC-013 |
| Verification and docs | IMG-REQ-010, IMG-REQ-011, IMG-REQ-012 | IMG-AC-009, IMG-AC-011, IMG-AC-012, IMG-AC-013 |
