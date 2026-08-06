# Project Structure

## Directory Organization

```text
coding-cli/
├── AGENTS.md
├── README.md
├── agents/
│   └── batman.agent.md
├── prompts/
│   └── execute-task.prompt.md
├── skills/
│   ├── generic-entry/
│   ├── gamedev-workflow/
│   │   ├── SKILL.md
│   │   ├── agents/openai.yaml
│   │   ├── references/routing-cases.json
│   │   └── scripts/validate_integration.py
│   ├── 3d-modeling/
│   ├── motion-design/
│   └── verify-3d-animation/          # New locally owned skill
│       ├── SKILL.md
│       └── agents/openai.yaml
├── docs/
│   ├── prd/verify-3d-animation.md
│   └── architecture/adr/             # Only if Design proves a new ADR is warranted
└── .batman/verify-3d-animation/
    ├── steering/
    └── spec/
```

## Naming Conventions

### Files

- **Skills/directories**: lowercase kebab-case; exact skill name `verify-3d-animation`.
- **Skill entrypoint**: uppercase `SKILL.md` with `name` and `description` frontmatter only.
- **Skill UI metadata**: `agents/openai.yaml` generated from finalized skill content.
- **Python**: snake_case files, functions, and variables; uppercase constants.
- **JSON fixtures**: kebab-case case IDs and stable string gate names.
- **Batman artifacts/PRDs**: kebab-case task slug.

### Code

- **Classes/types**: existing Python conventions.
- **Functions/methods**: snake_case.
- **Constants**: `UPPER_SNAKE_CASE`.
- **Variables**: snake_case.

## Import Patterns

Python validator imports standard-library modules first. The new skill should not add Python dependencies unless an approved Design demonstrates deterministic value that Markdown/fixtures cannot provide.

## Code Structure Patterns

### Skill Organization

1. Authority and evidence boundary.
2. Source/reference intake.
3. Comparable capture setup.
4. Transform/skeleton and pose/deformation checks.
5. Animation sampling and per-frame checks.
6. Completion gate and reporting contract.

### Validator Organization

1. Canonical skill inventory.
2. Vendored/local ownership separation.
3. Route expectations and representative cases.
4. Skill/link/content invariants.
5. Idempotence, host-mirror, and thin-pointer checks.

## Code Organization Principles

1. **Single Responsibility**: New verifier owns generic visual verification; router owns selection; specialists own project execution.
2. **Modularity**: Compose the smallest applicable skill union.
3. **Testability**: Encode representative routes and required gate invariants deterministically.
4. **Consistency**: Preserve current canonical-only and thin-pointer patterns.

## Module Boundaries

- `generic-entry` must not duplicate game-specific verification details.
- `gamedev-workflow` may route and summarize gates, but detailed procedure belongs in `verify-3d-animation`.
- Vendored `3d-modeling` and `motion-design` bodies/provenance remain unchanged unless later explicitly approved.
- Project specialists override generic engine/DCC/tool instructions.
- MCP and hook registries are outside this feature.

## Code Size Guidelines

- Keep `SKILL.md` concise and under the Skill Creator's 500-line ceiling.
- Add references only when core instructions would otherwise become bloated; avoid auxiliary README/changelog files inside the skill.
- Keep validator changes focused and reuse existing validation helpers.

## Documentation Standards

- Use EARS requirements with stable `V3A-REQ-*` identifiers.
- Trace design and tasks to requirement IDs.
- Record Phase 2a/3a/4a discovery queries and outcomes.
- Separate repository validation from active-game evidence in every report.
- Keep accepted ADR core sections immutable; supersede rather than rewrite if a new architecture decision is required.
