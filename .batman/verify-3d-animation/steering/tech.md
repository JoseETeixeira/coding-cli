# Technology Stack

## Project Type

Host-agnostic repository of coding-agent customizations and deterministic validation tooling. The feature adds a Markdown skill and extends an existing game-development routing contract; it does not add a runtime service.

## Core Technologies

### Primary Languages

- **Markdown/YAML frontmatter**: Skill bodies, prompts, steering, PRD, and workflow documentation.
- **JSON**: Routing fixtures and product metadata.
- **Python 3.12**: Deterministic gamedev integration validator and system skill validation helpers.
- **PowerShell/Git**: Windows repository inspection and version control.

### Key Dependencies/Libraries

- **Python standard library**: `argparse`, `hashlib`, `json`, `re`, and `pathlib` in the existing validator.
- **Skill Creator helpers**: `init_skill.py`, `generate_openai_yaml.py`, and `quick_validate.py` from the installed system skill.
- **Project specialists/editor bridges**: Selected by the active game repository; never dependencies of the generic skill.

### Application Architecture

Layered customization architecture:

1. `generic-entry` owns universal task workflow and approval gates.
2. `gamedev-workflow` owns conditional game-discipline selection and evidence boundaries.
3. Discipline skills own reusable domain procedures.
4. Project specialists and current project source own engine/DCC/editor commands and concrete acceptance.
5. Task-local artifacts record evidence; mnemo stores approved phase summaries only.

### Data Storage

- **Primary storage**: Versioned Markdown/JSON/Python files in `coding-cli`; project-authorized task artifacts in active game repositories.
- **Shared memory**: mnemo for bounded approved-phase checkpoints, never as source authority.
- **Data formats**: Markdown, YAML frontmatter, JSON, images/video/frame captures owned by active projects.

### External Integrations

- No new MCP server, hook, API, credential, or network dependency.
- Active DCC/engine/editor integrations remain project-specific and are selected through specialist contracts.

## Development Environment

### Build & Development Tools

- **Build System**: None for Markdown; Python scripts run directly.
- **Package Management**: Existing Python environment; no new dependency planned.
- **Development Workflow**: Batman eight-phase workflow with approval gates and `apply_patch` edits.

### Code Quality Tools

- **Static Analysis**: `quick_validate.py` for skill metadata; deterministic `validate_integration.py` for gamedev integration.
- **Formatting**: `git diff --check` and JSON parsing.
- **Testing Framework**: Python script assertions plus route fixtures; live visual acceptance occurs only in active game projects.
- **Documentation**: Markdown PRD, steering, requirements, README, and any approved ADR.

### Version Control & Collaboration

- **VCS**: Git.
- **Branching Strategy**: Current checked-out branch; preserve unrelated dirty work.
- **Code Review Process**: Path-scoped canonical review before commit; no broad staging.

## Deployment & Distribution

- **Target Platforms**: Claude Code, Codex, and VS Code/Copilot through canonical user-level path resolution.
- **Distribution Method**: `USER_SKILLS_DIR` points to canonical `coding-cli/skills`; no copied host body.
- **Installation Requirements**: Existing canonical checkout and host pointer setup.
- **Update Mechanism**: Versioned repository changes; no automatic updater added.

## Technical Requirements & Constraints

### Performance Requirements

- Evidence work scales with scheduled frames plus explicitly identified critical frames.
- No generic rule may reduce the user-approved minimum sample count for convenience.

### Compatibility Requirements

- Engine-, renderer-, DCC-, camera-, and asset-specific behavior comes from current project source and specialist instructions.
- The generic skill must work without assuming a specific engine, file format, renderer, or capture tool.

### Security & Compliance

- Do not upload private references or project captures unless explicitly authorized.
- Do not place credentials, proprietary source bytes, or unrelated project data in memory, logs, fixtures, or repository docs.
- Do not widen tools, paths, network, sandbox, or approval authority.

### Scalability & Reliability

- Frame schedules must be deterministic from recorded clip metadata.
- Missing tools, runtime, reference access, or owner acceptance must produce explicit blocked/pending states.

## Technical Decisions & Rationale

### Decision Log

1. **One local verifier skill**: Narrow owner for new generic rules; avoids rewriting vendored `3d-modeling` or `motion-design` bodies.
2. **Compose through `gamedev-workflow`**: Preserves ADR 0009's one-router architecture and project authority.
3. **No new runtime service**: Requirements are procedural and testable through existing skill/routing validators plus active project evidence.
4. **30-FPS evidence budget**: User approved a minimum of `max(2, ceil(source_frame_count / 30))` distributed captures plus all critical frames.

## Known Limitations

- Repository validation cannot prove visual fidelity in a concrete game.
- Automated pixel differences are unreliable until captures share comparable camera, projection, crop, timing, and rendering conditions.
- Exact numerical tolerances are project/reference dependent and cannot be universalized safely.
