# Project Structure

## Directory Organization

```text
coding-cli/
├── AGENTS.md                         # Generic host entry and thin domain pointers
├── agents/
│   ├── batman.agent.md               # Canonical Batman entry
│   └── *-dev.agent.md                # Project specialists
├── skills/
│   ├── generic-entry/                # Universal Batman workflow owner
│   ├── gamedev-workflow/             # New game-development router
│   ├── game-developer/               # Vendored implementation guidance
│   ├── 3d-modeling/                   # Vendored/adapted 3D guidance
│   ├── game-designer/                 # Clean-room canonical design guidance
│   ├── godot-genre-shooter-fps/       # Vendored Godot FPS guidance/assets
│   ├── godot-particles/               # Vendored Godot VFX guidance/assets
│   ├── godot-performance-optimization/# Vendored Godot performance guidance/assets
│   └── motion-design/                 # Vendored UI-motion guidance/modules
├── prompts/
│   └── execute-task.prompt.md         # Thin implementation-phase pointer
├── docs/
│   ├── prd/                           # Product requirements documents
│   └── architecture/adr/              # Repository ADR convention
└── .batman/gamedev-skills-workflow/
    ├── steering/                      # Task understanding and foundations
    ├── spec/                          # Requirements, design, and tasks
    └── evidence/                      # Visual/verification evidence
```

## Naming Conventions

### Files

- **Skills**: lowercase kebab-case directory; required entry file is uppercase `SKILL.md`.
- **Agents**: lowercase kebab-case with `.agent.md` suffix.
- **Prompts**: lowercase kebab-case with `.prompt.md` suffix unless preserving an existing host-facing name.
- **PRDs/ADRs**: lowercase kebab-case; ADRs use the next four-digit repository sequence.
- **Third-party records**: consistent uppercase license/provenance filenames chosen in Design and applied to every package.
- **Tests/scripts**: lowercase snake_case Python names when new helpers are required.

### Code

- **Python functions/variables**: `snake_case`; constants: `UPPER_SNAKE_CASE`.
- **Markdown requirement IDs**: `GDS-REQ-###`; acceptance criteria: `GDS-AC-###`.
- **Upstream code assets**: retain upstream filenames unless an approved compatibility adaptation requires a rename.

## Import Patterns

### Import Order

Not generally applicable to Markdown skills. Any new Python validator follows standard-library imports first, then third-party packages, then repository-local imports.

### Module/Package Organization

```text
SKILL.md                     # Trigger and concise workflow; progressive-disclosure entry
references/ or upstream dirs # Detailed content loaded only when the route needs it
scripts/                     # Reference/helper scripts; never auto-copied into a game
LICENSE* / provenance record # Redistribution and adaptation evidence
```

## Code Structure Patterns

### Module/Class Organization

1. Frontmatter with supported discovery fields.
2. Purpose, trigger boundaries, and authority/precedence.
3. Workflow and routing decisions.
4. Verification/acceptance gates.
5. Progressive links to references, scripts, license, and provenance.

### Function/Method Organization

Any validation helper performs input/path validation first, deterministic checks second, collects all failures, and exits nonzero with actionable messages.

### File Organization Principles

- One skill directory owns one reusable capability.
- The gamedev router links to skills; it does not copy their bodies.
- Third-party content and local integration notes remain visibly distinguishable.
- Host directories receive no copied canonical bodies.

## Code Organization Principles

1. **Single Responsibility**: router, discipline skill, specialist agent, and universal entry each retain separate authority.
2. **Modularity**: routes compose only the capabilities required by the task.
3. **Testability**: source pins, links, frontmatter, and routing promises are machine-checkable.
4. **Consistency**: follow current conditional-domain and documentation conventions.

## Module Boundaries

- **Universal vs domain**: `generic-entry` owns all-project behavior; `gamedev-workflow` owns game-development composition only.
- **Domain vs project**: gamedev skills provide reusable guidance; specialist agents and current game repositories own concrete facts and tools.
- **Router vs content**: the router selects skills; each skill owns its detailed guidance and bundled assets.
- **Canonical vs host**: `coding-cli` owns bodies; host roots contain pointers/adapters only.
- **Vendored vs adapted**: upstream snapshot identity is recorded; every local content change appears in an adaptation ledger. Independently authored replacements carry an origin/exclusion record instead of false upstream attribution.

## Code Size Guidelines

- **Router entry**: concise enough to load routinely; push detailed domain material into linked packages.
- **Skill entry**: avoid duplicating bundled reference bodies.
- **Validation helpers**: one clear concern per function and actionable failures; no arbitrary line cap overrides clarity.
- **Nesting depth**: keep Markdown headings and code branches shallow enough to scan without hidden authority.

## Dashboard/Monitoring Structure

No dashboard subsystem applies. Validation output and Git diffs provide operational visibility.

### Separation of Concerns

- Validation reads canonical skills and test fixtures only.
- Representative routing scenarios do not edit active game projects.
- Documentation records decisions without becoming a second workflow implementation.

## Documentation Standards

- Every skill has discoverable frontmatter and clear trigger boundaries.
- Third-party skills record immutable source URLs, commit SHAs, licenses, and adaptations.
- Complex routing/precedence decisions are captured in the task PRD and accepted ADR.
- Relative links must resolve; external optional sibling skills must be labeled optional and not installed.
- Claims about compatibility, performance, or visual acceptance name the required project-specific evidence.
