# Project Structure

## Directory Organization

```text
coding-cli/
|-- agents/                         # Canonical generic and specialist agent definitions
|-- skills/                         # Canonical workflows and reusable behavior
|-- prompts/                        # Approval-gated workflow and task prompts
|   `-- templates/steering/         # Foundation steering templates
|-- instructions/                   # Shared review and code-pattern guidance
|-- mnemo/
|   |-- mnemo/                      # Python memory engine, MCP server, and code index
|   |-- tests/                      # Engine, index, and MCP smoke tests
|   `-- scripts/                    # Local Qdrant helpers
|-- hooks/                          # Plugin-discoverable lifecycle hook configuration
|-- .claude/                        # Claude Code repository fixtures and hook helpers
|-- .claude-plugin/                 # Claude plugin metadata
|-- .codex/                         # Codex repository-scoped configuration
|-- .vscode/                        # Editor MCP configuration
|-- docs/                           # PRDs and architecture ADRs created by workflow
`-- .batman/
    `-- cross-host-context-compaction/
        |-- steering/               # Approved current-state and foundation context
        `-- spec/                   # Requirements, design, and tasks
```

## Naming Conventions

### Files

- **Skills and prompt directories**: lowercase kebab-case; skill entry is `SKILL.md`.
- **Agent definitions**: lowercase kebab-case with `.agent.md` suffix.
- **Python modules/tests**: snake_case; tests use `test_<subject>.py`.
- **Hook helpers**: descriptive lowercase kebab-case for shell scripts; snake_case or existing kebab convention for Python helpers based on neighboring files.
- **Batman task paths**: lowercase kebab-case task slug; canonical files are `understanding.md`, `requirements.md`, `design.md`, and `tasks.md`.
- **ADRs**: `NNNN-<decision-slug>.md` under this repository's `docs/architecture/adr/` convention.

### Code

- **Python classes**: PascalCase.
- **Python functions/variables**: snake_case.
- **Constants**: UPPER_SNAKE_CASE.
- **JSON/TOML keys**: match host-documented schema exactly; do not normalize host names.

## Import Patterns

### Import Order

1. Python standard library.
2. Third-party dependencies.
3. Local `mnemo` modules.

### Module/Package Organization

- `mnemo/run_server.py` is the stdio entry point.
- `mnemo/mnemo/server.py` exposes MCP contracts.
- `mnemo/mnemo/engine.py` owns memory behavior.
- `mnemo/mnemo/config.py` resolves environment configuration.
- Hook helpers should keep host-event parsing separate from canonical state selection so deterministic logic can be unit-tested without launching a host.

## Code Structure Patterns

### Python Module Organization

1. Module contract and rationale docstring.
2. Standard and third-party imports.
3. Constants and schemas.
4. Pure parsing/selection helpers.
5. External I/O or host entry point.
6. Fail-safe top-level boundary where lifecycle integration requires it.

### Function Organization

- Validate untrusted hook/MCP input first.
- Keep deterministic selection and budgeting pure where possible.
- Perform external reads after path/scope validation.
- Return explicit degradation/truncation metadata.
- Keep security filtering and output caps at the final serialization boundary too.

### File Organization Principles

- One clear policy or runtime responsibility per file.
- Shared semantic behavior belongs in canonical modules/skills.
- Host-specific syntax and activation remain thin adapters.
- Full artifacts remain on disk; hot-context returns carry summaries and pointers.

## Code Organization Principles

1. **Single Responsibility**: separate canonical state contract, host adapter, memory API, and deployment activation.
2. **Modularity**: deterministic logic must be callable from tests without Codex, Claude Code, Qdrant, or network access.
3. **Testability**: characterize current behavior before changing public memory or hook contracts.
4. **Consistency**: preserve existing source-of-truth, pointer, namespace, trust-class, and approval conventions.
5. **Reversibility**: pilot config and hooks need explicit off paths; no destructive transcript or memory mutation.

## Module Boundaries

- **Canonical policy vs host adapter**: skills/agents define outcomes; Codex/Claude files translate documented host lifecycle/config into that contract.
- **Authoritative state vs optional recall**: source/tests/Git/approved artifacts are truth; mnemo locates context but never testifies.
- **Summary vs payload**: hook/context output stays bounded; full records remain retrievable by deterministic path or memory ID.
- **Repository source vs user activation**: tracked canonical changes do not overwrite user settings; activation merges narrowly and remains separately verifiable.
- **Stable vs pilot**: pilot is allowlisted and disabled independently; wider default rollout requires separate evidence and approval.

## Code Size Guidelines

- **Files**: no arbitrary line cap; split when a file owns more than one lifecycle/policy responsibility or cannot be reviewed/tested independently.
- **Functions**: prefer small pure helpers; split parsing, selection, budgeting, serialization, and I/O when combined behavior obscures failure handling.
- **Complexity**: avoid host-condition matrices inside canonical policy; use explicit adapters and shared fixtures.
- **Nesting depth**: use early validation returns to keep untrusted input handling shallow.

## Monitoring Structure

```text
pilot event
|-- host + version + trigger
|-- before/after usage when host exposes it
|-- continuation payload size + truncation/degraded flags
|-- source-validation state
`-- outcome + rollback state
```

Diagnostics contain metadata only. They exclude transcript bodies, raw tool output, secrets, and full memory text.

## Documentation Standards

- Every public MCP or hook contract documents input, bounded output, failure semantics, and source-of-truth behavior.
- PRD captures problem/goals/scope/acceptance criteria.
- ADRs capture only hard-to-reverse, surprising trade-off decisions.
- Operator docs show host-specific enable, verification, disable, and rollback steps.
- Evidence reports record exact host versions, commands, workloads, counts, and known limits.
