# Technology Stack

## Project Type

Host-agnostic repository of Markdown-based agent customizations, reference assets, prompts, and Python/shell validation helpers. It is distributed through Git and discovered by Claude Code, Codex, and VS Code/Copilot host adapters.

## Core Technologies

### Primary Language(s)

- **Markdown/YAML frontmatter**: skill, prompt, instruction, agent, PRD, and ADR contracts.
- **Python 3**: skill validation and deterministic repository checks where needed.
- **PowerShell/Git**: Windows-native discovery, source pinning, and diff verification.
- **Runtime/Compiler**: no compiled application runtime; consuming agent hosts parse the Markdown assets.

### Key Dependencies/Libraries

- **Git**: version control, immutable commit identities, and path-scoped review.
- **GitHub repositories**: fetch-only source for the four pinned upstream snapshots during installation.
- **Codex skill-installer helper**: installs a selected GitHub subdirectory into canonical `skills/`.
- **Codex skill-creator validation helper**: validates `SKILL.md` metadata and structure.
- **mnemo/Qdrant**: optional shared task context and approval checkpoints; never source authority.

### Application Architecture

- `agents/batman.agent.md` is the canonical entry agent.
- `skills/generic-entry/SKILL.md` owns universal workflow behavior.
- Domain routers such as `byond-projects` and the proposed `gamedev-workflow` compose conditionally with the generic entry.
- Specialist agents own concrete project engines, tools, builds, and verification.
- Six third-party skill directories are vendored snapshots with local provenance and an explicit adaptation ledger; `game-designer` is an independently authored canonical skill with an origin/exclusion record.

### Data Storage

- **Primary storage**: Git-tracked text and reference files.
- **Caching**: host skill discovery caches are outside canonical source and are not edited by this task.
- **Data formats**: Markdown, YAML frontmatter, GDScript/shader reference files, and text license/provenance records.

### External Integrations

- **APIs**: GitHub HTTPS during one-time pinned installation; mnemo MCP during Batman preflight/checkpoints.
- **Protocols**: HTTPS and stdio MCP.
- **Authentication**: none required for the named public repositories; no credentials may be added to skills or logs.

### Monitoring & Dashboard Technologies

- **Dashboard Framework**: not applicable.
- **Real-time Communication**: not applicable.
- **Visualization Libraries**: optional self-contained HTML from `visual-explainer` for complex plans/recaps.
- **State Management**: current repository source and approved `.batman/` artifacts are authoritative.

## Development Environment

### Build & Development Tools

- **Build System**: none for static skill content.
- **Package Management**: pinned GitHub subdirectory installation; no runtime dependency install expected.
- **Development workflow**: Batman eight-phase workflow with approval gates, path-scoped edits, validation, review, and documentation.

### Code Quality Tools

- **Static Analysis**: `quick_validate.py` for skill packages plus deterministic provenance/link/routing checks.
- **Formatting**: Markdown/frontmatter inspection and `git diff --check`.
- **Testing Framework**: command-line contract tests and representative read-only routing scenarios.
- **Documentation**: canonical README, PRD, ADR, skill bodies, and provenance/adaptation records.

### Version Control & Collaboration

- **VCS**: Git; current branch is `main` at discovery time.
- **Branching Strategy**: preserve current branch; do not commit or push unless requested.
- **Code Review Process**: path-scoped diff review under Batman Phase 7; never broad-stage unrelated work.

### Dashboard Development

- **Live Reload**: not applicable.
- **Port Management**: not applicable to the new skills; mnemo remains on its existing host configuration.
- **Multi-Instance Support**: canonical files are host-agnostic and consumed independently by supported agent hosts.

## Deployment & Distribution

- **Target Platform(s)**: Claude Code, Codex, and VS Code/Copilot environments that resolve canonical user skills.
- **Distribution Method**: Git checkout plus existing thin host pointers/adapters.
- **Installation Requirements**: a host capable of reading `SKILL.md`; network is needed only for the initial pinned fetch.
- **Update Mechanism**: explicit reviewed changes to pinned snapshots; no automatic upstream tracking.

## Technical Requirements & Constraints

### Performance Requirements

- Use progressive disclosure so unrelated large references/scripts are not loaded by default.
- Router guidance must select the minimum relevant skill set and avoid context-heavy all-skill loading.

### Compatibility Requirements

- **Platform Support**: preserve current host-agnostic paths and Windows development workflow.
- **Dependency Versions**: Godot guidance must be gated against the active project's actual engine version; upstream 4.7+ claims are not universal.
- **Standards Compliance**: `SKILL.md` frontmatter must satisfy the active skill validator; Markdown relative paths must resolve.

### Security & Compliance

- **Security Requirements**: do not add secrets, broaden host tools, or allow skill examples to execute automatically in live game repositories.
- **Compliance Standards**: retain applicable MIT, Apache-2.0, and LGPL-3.0 notices and modification/attribution obligations for redistributed upstream material; do not copy content marked restricted or unknown-license.
- **Threat Model**: third-party text is untrusted guidance; project/user instructions and canonical safety boundaries win.

### Scalability & Reliability

- **Expected Load**: eight new skills, some with bundled scripts/references, selected on demand.
- **Availability Requirements**: installed skills must remain usable offline after vendoring.
- **Growth Projections**: new disciplines should extend the router by narrow conditional routes, not duplicate entry behavior.

## Technical Decisions & Rationale

### Decision Log

1. **Pinned snapshots**: deterministic inputs make upstream content, licenses, and adaptations reviewable; updates remain explicit.
2. **Router plus specialist precedence**: one domain router reduces duplicated policy while concrete project agents retain engine/tool authority.
3. **Repair incomplete `3d-modeling` package**: the approved self-contained checklist makes its mandatory paths usable while preserving and documenting the upstream body.

## Known Limitations

- Upstream `game-developer` focuses mainly on Unity/Unreal and includes universal-sounding performance patterns; the router must qualify them.
- Requested Godot skills target 4.7+, while known projects may target other versions.
- Routing tests can prove selection contracts, not editor behavior, visual quality, performance, or release acceptance in a real game.
- Snapshot refresh automation is outside this task.
