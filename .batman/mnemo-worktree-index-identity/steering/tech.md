# Technology Stack

## Project Type

Host-agnostic coding-agent customization repository with a Python 3.12 FastMCP service. The affected subsystem is mnemo's rebuildable semantic source-code index, not its append-only durable-memory engine.

## Core Technologies

### Primary Languages

- **Python 3.12**: mnemo repository resolution, indexing, Qdrant operations, background refresh, and tests.
- **Markdown**: skills, planning artifacts, PRDs, ADRs, operator documentation, and module README.
- **JSON and TOML**: existing MCP/host registrations; no registration change is expected.
- **PowerShell, command scripts, and Git CLI**: Windows-first development and repository/worktree inspection.

### Key Dependencies/Libraries

- **MCP 1.2 or newer**: FastMCP stdio tool server.
- **qdrant-client 1.9 or newer**: vector collection, filters, payload indexes, upsert, count, and deletion.
- **OpenAI 1.40 or newer**: production embeddings client.
- **tiktoken 0.7 or newer**: token-accurate source-chunk truncation.
- **filelock 3.12 or newer**: OS-released cross-process code-index locks.
- **pytest**: deterministic fake-embedder/Qdrant tests and public-contract regressions.

### Application Architecture

- `mnemo/mnemo/server.py` resolves the active repository per MCP call and exposes memory/code tools.
- `mnemo/mnemo/code_index.py` owns Git repository resolution, eligible-file discovery, chunking, cache identity, manifest/lock paths, Qdrant point identity, search, status, and background refresh.
- `mnemo/mnemo/engine.py` owns durable memory; this task must preserve its repository-scoped behavior.
- Each MCP host launches the same canonical stdio entry point against shared Qdrant and `~/.mnemo`.

### Data Storage

- **Durable memory truth**: append-only JSONL events under `~/.mnemo/events/`.
- **Durable memory projection**: Qdrant collection `mnemo_memory`.
- **Code search cache**: Qdrant collection `mnemo_code`.
- **Incremental code cache metadata**: manifests and file locks under `~/.mnemo/code/`.
- **Authoritative source**: current Git working directory and its eligible files.
- **Data formats**: Python objects, JSON manifests, Qdrant payloads, Markdown, JSONL, and MCP JSON-RPC.

### External Integrations

- **Git CLI**: top-level, repository, and working-tree metadata; calls require bounded timeouts and `stdin=DEVNULL`.
- **Qdrant**: local vector storage on the existing configured endpoint.
- **OpenAI embeddings API**: production code embeddings only; identity resolution must not add an API call.
- **Codex/Claude/Copilot MCP clients**: invoke the same code tools with different workspace-root capabilities.

## Development Environment

### Build & Development Tools

- **Build System**: none; Python modules run directly.
- **Package Management**: `pip` via `mnemo/requirements.txt`.
- **Development Workflow**: Git worktrees, path-scoped edits, local Qdrant, fake embeddings for focused tests, real stdio smoke only where explicitly run.

### Code Quality Tools

- **Static Analysis**: scoped Ruff when available plus Python compile/import checks.
- **Formatting**: preserve current Python/Markdown style; no broad rewrite.
- **Testing Framework**: `pytest` for `mnemo/tests`; real stdio smoke at `mnemo/tests/mcp_smoke.py`.
- **Documentation**: Markdown source plus Batman planning/evidence artifacts.

### Version Control & Collaboration

- **VCS**: Git with primary checkouts, linked worktrees, and independent clones.
- **Branching Strategy**: task-specific worktrees/branches; preserve unrelated dirty changes.
- **Code Review Process**: Batman Phase 7 and canonical repository review instructions before commit readiness.

## Deployment & Distribution

- **Target Platforms**: Windows primary; path and Git metadata behavior must remain valid on supported POSIX systems.
- **Distribution Method**: canonical checkout referenced by existing host MCP configurations.
- **Installation Requirements**: Python 3.12, current mnemo dependencies, local Qdrant, OpenAI key for live embeddings.
- **Update Mechanism**: update canonical checkout, rebuild affected cache scopes lazily or explicitly, reload hosts only if their running stdio server must pick up source changes.

## Technical Requirements & Constraints

### Performance Requirements

- Working-tree identity resolution uses bounded local Git/filesystem operations and no embedding/network request.
- Unchanged eligible files remain incrementally reusable inside the same code-index scope.
- Different working-tree scopes must not suppress each other's background refresh.
- Search remains responsive while background refresh runs; any returned snapshot state must be truthful.

### Compatibility Requirements

- **Platform Support**: normalized Windows drive/case paths, POSIX paths, main `.git` directories, linked-worktree `.git` files, absolute/relative Git paths, and repository subdirectories.
- **Dependency Versions**: preserve current minimums unless approved Design proves a new dependency necessary.
- **Public Contract**: retain `code_search`, `code_index_status`, and `code_reindex` tool names and arguments; additive response metadata is permitted.

### Security & Compliance

- Repository/worktree identity input is untrusted; reject unresolved/protected roots rather than guessing.
- Do not write source files, Git config, Git metadata, host settings, credentials, or durable-memory events while indexing.
- Do not log or store credentials; source content remains limited to the existing code-index embedding/Qdrant boundary.

### Scalability & Reliability

- Multiple hosts/processes may index the same or different working trees concurrently.
- Host termination is routine; deterministic points and OS-released locks must keep recovery idempotent.
- Qdrant, embeddings, Git, or manifest failures must not corrupt source or durable memory.
- Cache migration/cleanup must remain bounded to code-index data.

## Technical Decisions & Rationale

### Decision Log

1. **Repository-family memory remains shared**: user-approved Phase 1 boundary; task decisions and handoffs must cross worktrees.
2. **Code-index cache is working-tree scoped**: user-approved Phase 1 boundary; mutable source cannot safely share a history-only partition.
3. **Current source remains authority**: semantic results never replace file reads.
4. **Exact identity and legacy-cache mechanism deferred to Design**: requirements define observable behavior without preselecting implementation.

## Baseline Limitations (Before Implementation)

- Current `repo_id` uses root history and conflates related working trees.
- Current status does not expose/compare the manifest's recorded root.
- Current refresh is asynchronous, so same-working-tree local edits may precede the next completed index snapshot.
- Current stdio smoke verifies memory tools but does not exercise the code-index tool contracts.
- Current module documentation omits code-index environment variables and worktree semantics.
