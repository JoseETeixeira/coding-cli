# Technology Stack

## Project Type

Host-agnostic agent customization repository with a new Python stdio MCP service, Markdown skill package, host-native MCP adapters, tests, and documentation.

## Core Technologies

### Primary Language(s)

- **Python 3.12**: MCP server, OpenAI client integration, validation, file handling, and tests.
- **Markdown/YAML**: skill contract, agent-facing metadata, PRD/ADR, and setup documentation.
- **JSON/TOML**: Claude Code, VS Code / Copilot, and Codex MCP registration.
- **Runtime/Compiler**: CPython; no compiled application component.

### Key Dependencies/Libraries

- **OpenAI Python SDK**: authenticated Image API calls to `images.generate` and `images.edit` with model `gpt-image-2`.
- **MCP Python SDK / FastMCP**: local stdio server and structured tool/content results.
- **Pillow**: local image format, dimensions, mask-alpha validation, and output verification.
- **pytest**: deterministic unit and integration-style tests with a fake OpenAI client/transport.
- **Codex skill-creator helpers**: `init_skill.py`, `generate_openai_yaml.py`, and `quick_validate.py` for scaffolding and validation.

### Application Architecture

- `skills/gpt-image-2/` owns agent activation, workflow, prompt guidance, inspection, and iteration.
- A standalone `gpt_image_2/` Python package owns credential lookup, request validation, API calls, safe decoding/writes, error mapping, and MCP presentation.
- A root entrypoint starts only the image MCP server and works from any current working directory.
- Thin repository and user-level adapters register that entrypoint for Claude Code, Codex, and VS Code / Copilot.
- The image service remains separate from `mnemo`; shared memory and paid binary-generation responsibilities do not share a process.

### Data Storage

- **Primary storage**: `<working-directory>/generated-images/` by default, an optional caller-selected absolute output directory, and Git-tracked text source.
- **Caching**: no API response cache in the first release.
- **Data formats**: PNG, JPEG, WebP, JSON-RPC, Markdown, YAML, JSON, and TOML.
- **Retention**: generated files remain until the user removes them; prompts and images are not copied into repository logs or mnemo.

### External Integrations

- **APIs**: OpenAI `POST /v1/images/generations` and `POST /v1/images/edits`.
- **Protocols**: outbound HTTPS and local stdio MCP.
- **Authentication**: `OPENAI_API_KEY` from process environment first, then Windows current-user environment lookup; never from an MCP argument or committed file.
- **Host integration**: Claude Code `mcpServers`, Codex `mcp_servers`, and VS Code / Copilot `servers` registrations.

### Monitoring & Dashboard Technologies

- **Dashboard Framework**: not applicable.
- **Real-time Communication**: MCP request/response over stdio; no first-release streaming.
- **Visualization Libraries**: MCP image content for bounded results and host-native image viewers for saved files.
- **State Management**: stateless server operations plus filesystem outputs.

## Development Environment

### Build & Development Tools

- **Build System**: none; Python source executes directly.
- **Package Management**: a focused requirements file for the image server; dependency installation is explicit.
- **Development workflow**: Batman eight-phase flow, `skill-creator` scaffolding/validation, mocked tests by default, and one separately reported paid smoke.

### Code Quality Tools

- **Static Analysis**: Python compilation/import checks plus skill metadata validation.
- **Formatting**: repository conventions and `git diff --check`.
- **Testing Framework**: pytest, fake OpenAI responses, and MCP stdio smoke tests.
- **Documentation**: `SKILL.md`, README setup, PRD, architecture decision, and validation evidence.

### Version Control & Collaboration

- **VCS**: Git; implementation stays on the current task worktree and preserves unrelated changes.
- **Branching Strategy**: no commit, push, merge, or broad staging unless separately requested.
- **Code Review Process**: focused Phase 7 review of source, adapters, tests, documentation, secret boundaries, and binary-output behavior.

### Dashboard Development

- **Live Reload**: not applicable.
- **Port Management**: no TCP port; stdio only.
- **Multi-Instance Support**: each host may launch an independent stateless server process against the same user credential.

## Deployment & Distribution

- **Target Platform(s)**: Windows 11 is the validated host; process-environment authentication remains portable to other platforms.
- **Distribution Method**: canonical Git checkout plus thin source/user MCP registrations. Plugin marketplace distribution is outside the first release.
- **Installation Requirements**: Python 3.12-compatible runtime, declared Python dependencies, outbound OpenAI HTTPS access, an authorized API key, and any required OpenAI organization verification.
- **Update Mechanism**: reviewed changes in `coding-cli`, followed by sync/merge and host restart or MCP reload.

## Technical Requirements & Constraints

### Performance Requirements

- Host tool timeouts must accommodate documented generation latency of up to roughly two minutes while retaining a finite upper bound.
- Large and multi-image outputs must not be forced through JSON-RPC as unbounded base64 content.
- Retry delays and counts must be bounded.

### Compatibility Requirements

- **Platform Support**: Windows user-environment fallback; ordinary process environment on all platforms.
- **Dependency Versions**: minimum versions must expose required Image API and MCP behavior and remain explicit in Design.
- **Standards Compliance**: MCP stdio reserves stdout for JSON-RPC; skill frontmatter and `agents/openai.yaml` pass the current skill validator/schema.

### Security & Compliance

- **Security Requirements**: no credential tool argument, no raw Authorization/header logging, no path traversal through file names, no default overwrite, no remote input URL fetching, and no secret-bearing exception serialization.
- **Compliance Standards**: rely on OpenAI's API moderation and accurately report moderation blocks without attempting bypasses.
- **Threat Model**: untrusted prompts, local input files, filenames, API error bodies, oversized base64 results, malformed images, and agent-supplied output paths.

### Scalability & Reliability

- **Expected Load**: interactive calls, usually one image; generation supports the documented bounded count without becoming a bulk-job system.
- **Availability Requirements**: actionable missing-key, dependency, organization-verification, moderation, timeout, and transient-service errors.
- **Growth Projections**: new image models or Responses API behavior require explicit contract changes rather than a hidden model override.

## Technical Decisions & Rationale

### Decision Log

1. **Direct Image API**: generation/editing are single operations; Responses API conversation state is unnecessary initial scope.
2. **Separate MCP server**: isolates paid image side effects, large binary output, dependencies, and credentials from mnemo.
3. **Fixed model**: callers cannot silently select a more expensive or behaviorally different model.
4. **Working-directory-derived output**: the tool defaults to `<working-directory>/generated-images/`; callers may override it with an absolute directory.
5. **Mock-first verification**: routine tests spend no credits and transmit no images; one small live smoke proves actual compatibility.
6. **Conservative paid retries**: disable OpenAI SDK automatic retries; retry at most once after an explicit retryable `429`/`5xx` response, never after a connection or read timeout whose remote completion is ambiguous.
7. **Bounded preview**: attach only the first successful image and only when its decoded size is at most 5 MiB; durable paths and metadata cover every output.
8. **Finite latency budget**: each operation has a 180-second total deadline and each API attempt has a 150-second timeout. Claude and Codex use their documented 240-second per-server settings; VS Code receives no undocumented timeout field and must pass a real 180-second runtime gate.

## Known Limitations

- `gpt-image-2` does not support transparent backgrounds.
- The first release does not stream partial images or maintain conversational edit state.
- User-level registrations that target the canonical checkout become usable only after this branch is merged/synced there and the host reloads MCP configuration.
- Automated tests can prove transport and file contracts, not artistic quality; a human/agent image inspection remains required.
