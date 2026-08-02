# Project Structure

## Directory Organization

```text
coding-cli/
├── skills/
│   └── gpt-image-2/
│       ├── SKILL.md                  # Trigger and agent workflow
│       ├── agents/openai.yaml        # Skill-list metadata
│       └── references/               # Focused prompting/editing guidance if needed
├── gpt_image_2/
│   ├── __init__.py
│   ├── server.py                     # FastMCP tools and presentation
│   ├── api.py                        # OpenAI request boundary
│   ├── credentials.py                # Process/Windows-user key resolution
│   ├── models.py                     # Validated input/output domain types
│   ├── images.py                     # Local image validation and safe writes
│   └── errors.py                     # Safe error taxonomy/redaction
├── run_gpt_image_2_server.py         # CWD-independent stdio entrypoint
├── tests/gpt_image_2/                # Mocked unit and MCP contract tests
├── .mcp.json                         # Claude-compatible project adapter
├── .codex/config.toml                # Codex project adapter
├── .vscode/mcp.json                  # Copilot project adapter
├── README.md                         # Capability/setup notes
└── .batman/create-gpt-image-2-skill-and-tool/
    ├── steering/                     # Understanding and foundations
    ├── spec/                         # Requirements, Design, Tasks
    └── evidence/                     # Test/live-smoke/review evidence
```

Exact Python module splits and test filenames remain Design decisions. This tree records the intended ownership boundaries, not authorization to implement before approval.

## Naming Conventions

### Files

- Skill directory: lowercase kebab-case `gpt-image-2`; required entry is uppercase `SKILL.md`.
- Python package, modules, and tests: lowercase snake_case.
- MCP server identifier: lowercase kebab-case where the host supports it.
- Generated files: `<working-directory>/generated-images/` by default, using generic basename `image` unless explicitly supplied, a format-matching extension, and numeric collision suffixes such as `image-2.png`.
- Requirements: `IMG-REQ-###`; acceptance criteria: `IMG-AC-###`.

### Code

- Python functions/variables: `snake_case`; classes: `PascalCase`; constants: `UPPER_SNAKE_CASE`.
- Public MCP tool names are stable verbs and distinct for generate vs edit.
- API/model strings live in one domain/config module rather than being repeated.

## Import Patterns

### Import Order

1. Python standard library.
2. Third-party MCP, OpenAI, and Pillow imports.
3. Repository-local `gpt_image_2` imports.

### Module/Package Organization

- MCP functions translate tool inputs/results only; they do not own HTTP, credential, or filesystem policy.
- API code depends on validated models and a replaceable client boundary.
- Image code validates/decodes/writes bytes without importing MCP.
- Credential code returns a secret to the API boundary only and never formats it into output.

## Code Structure Patterns

### Module/Class Organization

1. Constants and narrow domain types.
2. Pure validation helpers.
3. Side-effect adapters for registry, OpenAI, and filesystem access.
4. MCP composition and presentation at the outer boundary.

### Function/Method Organization

- Validate schema and cross-field constraints before credential lookup or network activity.
- Resolve credentials immediately before client creation.
- Decode all response images to memory, validate them, then write with temporary-file plus atomic rename behavior.
- Map external exceptions to a small safe result/error taxonomy at the MCP boundary.

### File Organization Principles

- One source owns each rule; server descriptions may summarize but do not duplicate implementation constants.
- Tests mirror module boundaries and use temporary directories.
- Live-smoke helpers are opt-in and unmistakably separate from default tests.
- Host adapters point to the canonical launcher; they do not embed Python source or credentials.

## Code Organization Principles

1. **Single Responsibility**: skill reasoning, MCP protocol, API calls, credentials, validation, and file persistence remain separable.
2. **Modularity**: core operations can be tested without starting stdio or calling OpenAI.
3. **Testability**: OpenAI client, clock/backoff, registry lookup, and filesystem roots are injectable where needed.
4. **Consistency**: follow the existing `mnemo` entrypoint/FastMCP convention while keeping image behavior independent.

## Module Boundaries

- **Skill vs tool**: skill decides when/how to call and inspect; tool performs authenticated generation/editing.
- **Protocol vs domain**: MCP types stay at the server edge; core code uses ordinary Python values/domain models.
- **API vs filesystem**: API response acquisition and image persistence are separate failure domains.
- **Canonical vs host**: the repository owns source; user/project configs contain thin registrations only.
- **Mocked vs live validation**: default tests never perform paid network calls; live evidence is opt-in and labeled.

## Code Size Guidelines

- Keep `SKILL.md` concise and move detailed prompt recipes into directly linked references only when needed.
- Keep MCP tool bodies thin; split a module when it accumulates a second independent policy concern.
- Prefer small pure validators over one large request handler.
- Avoid arbitrary line limits that would obscure the security or error-handling contract.

## Dashboard/Monitoring Structure

No dashboard subsystem applies. Structured MCP results, focused logs to stderr, saved files, tests, and evidence artifacts provide operational visibility.

### Separation of Concerns

- Operational logs contain event names and safe identifiers, never prompts, source image bytes, base64 output, or credentials.
- Returned metadata contains only data needed to locate and understand results.
- Evidence records exact validation scope and separates mocked, live API, visual, and host-activation acceptance.

## Documentation Standards

- `SKILL.md` names positive/negative triggers, external cost, supported operations, input constraints, and the inspect/iterate loop.
- README documents dependency installation, credential precedence, registrations, reload behavior, supported formats/limits, and troubleshooting.
- Official OpenAI documentation URLs support API/model claims.
- PRD/ADR and final evidence distinguish approved design from current API facts and unperformed owner acceptance.
