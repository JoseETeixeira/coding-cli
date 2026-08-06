# Project Structure

## Directory Organization

```text
coding-cli/
|-- mnemo/
|   |-- mnemo/
|   |   |-- code_index.py           # Git resolution, scope identity, index/search/status
|   |   |-- server.py               # FastMCP tools and per-call repository selection
|   |   |-- config.py               # Memory and code-index environment settings
|   |   |-- embedders.py            # Production/fake-compatible embedding boundary
|   |   `-- engine.py               # Durable memory; outside behavioral change
|   |-- tests/
|   |   |-- test_code_index.py      # Focused repository/index regressions
|   |   `-- mcp_smoke.py            # Real stdio/Qdrant/OpenAI contract smoke
|   |-- scripts/                    # Local Qdrant launcher
|   `-- README.md                   # Setup, tools, configuration, contracts
|-- docs/
|   |-- prd/                        # Product requirements
|   `-- architecture/adr/           # Accepted/proposed architecture decisions
|-- .batman/
|   `-- mnemo-worktree-index-identity/
|       |-- steering/               # Approved understanding + project foundations
|       `-- spec/                   # Requirements, design, and tasks
`-- CONTEXT.md                      # Canonical project glossary
```

## Naming Conventions

### Files

- **Python modules/tests**: snake_case; tests use `test_<subject>.py`.
- **Python package entry**: `mnemo/run_server.py`.
- **Batman artifacts**: lowercase kebab-case task directory with canonical `understanding.md`, `requirements.md`, `design.md`, and `tasks.md`.
- **PRDs**: task slug under `docs/prd/`.
- **ADRs**: sequential `NNNN-<decision-slug>.md` under `docs/architecture/adr/`.

### Code

- **Classes and dataclasses**: PascalCase.
- **Functions, fields, and variables**: snake_case.
- **Constants**: UPPER_SNAKE_CASE.
- **Public MCP field names**: descriptive snake_case; preserve existing names unless approved migration requires an additive distinction.

## Import Patterns

### Import Order

1. Python standard library.
2. Third-party dependencies.
3. Local mnemo modules.

### Module/Package Organization

- `mnemo/run_server.py` makes the package importable independent of caller cwd.
- `mnemo/mnemo/server.py` owns MCP argument/response and resolution order.
- `mnemo/mnemo/code_index.py` owns code-cache identity and storage behavior.
- `mnemo/mnemo/config.py` owns environment defaults and cache-root selection.
- `mnemo/mnemo/engine.py` remains the durable-memory boundary.

## Code Structure Patterns

### Module Organization

1. Contract/rationale docstring.
2. Imports and constants.
3. Repository-resolution models/helpers.
4. Discovery and chunking.
5. Manifest and index operations.
6. Locks and background orchestration.

### Function Organization

- Validate paths/repository identity before external writes.
- Keep identity derivation deterministic and separately testable.
- Use explicit scope identifiers at every cache boundary.
- Keep Git subprocess calls bounded and disconnected from MCP stdin.
- Return typed error/degradation state instead of guessing.

### File Organization Principles

- Do not mix durable-memory identity with code-cache identity.
- Keep Qdrant payload/schema changes inside code-index ownership.
- Keep host-specific repository selection in the MCP server boundary.
- Put worktree fixtures and behavioral proof in focused tests.

## Code Organization Principles

1. **Single Responsibility**: repository family, working-tree scope, manifest, query, and background lifecycle remain explicit concepts.
2. **Modularity**: identity helpers are testable without OpenAI.
3. **Testability**: real Git repositories/worktrees plus deterministic fake embeddings prove isolation.
4. **Consistency**: all manifests, locks, points, filters, progress, and debounce keys use the same approved scope.
5. **Reversibility**: code-index cache changes can be rolled back/rebuilt without touching source or memory events.

## Module Boundaries

- **Durable memory vs source cache**: memory is repository-family scoped; code index is working-tree scoped.
- **Repository resolution vs cache identity**: server selects the current root; code-index module derives and enforces scope.
- **Authoritative source vs semantic locator**: file reads decide; Qdrant chunks locate.
- **Local cache vs Qdrant projection**: manifest and vector points must bind to the same scope identity.
- **Same-scope concurrency vs cross-scope concurrency**: same scope deduplicates safely; different scopes proceed independently.

## Code Size Guidelines

- **Files**: no arbitrary line cap; split only if identity/lifecycle responsibilities cannot be reviewed independently.
- **Functions**: prefer small helpers for repository-family identity, working-tree identity, normalization, and compatibility checks.
- **Complexity**: avoid scattered string composition for scope IDs; use one model/helper contract.
- **Nesting depth**: use early validation returns for untrusted Git/path states.

## Monitoring Structure

```text
code_index_status
|-- repository family
|-- working-tree root + code-index scope
|-- manifest binding + last completed snapshot
|-- files/chunks
|-- live progress
`-- typed error or freshness note
```

Diagnostics may identify paths and cache scope but must not emit source bodies, secrets, or durable-memory text.

## Documentation Standards

- Public code-index tools document scope, asynchronous refresh, response identity, and failure behavior.
- Requirements use EARS and separate cross-scope contamination from same-scope refresh lag.
- PRD states product goals/non-goals and measurable acceptance.
- ADR records the later approved identity/migration trade-off only if Design passes the three-part ADR test.
- Validation reports separate deterministic tests, real Qdrant, real OpenAI, live MCP, and owner/release gates.
