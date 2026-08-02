# Technology Stack

## Project Type

Host-agnostic coding-agent customization repository plus a small Python MCP memory service. Most canonical behavior is Markdown policy/prompt content; runtime integration uses JSON/TOML configuration and hook scripts.

## Core Technologies

### Primary Languages

- **Markdown**: canonical agents, skills, prompts, instructions, planning artifacts, and documentation.
- **Python 3.12**: mnemo MCP service, Qdrant memory engine, code index, and hook helpers.
- **JSON and TOML**: Claude/plugin/MCP settings and Codex configuration.
- **PowerShell, command scripts, and Bash**: host setup and cross-platform hook/operations surfaces.

### Key Dependencies/Libraries

- **MCP 1.2 or newer**: stdio memory server interface.
- **qdrant-client 1.9 or newer**: semantic memory projection and filtering.
- **OpenAI 1.40 or newer**: embeddings client.
- **tiktoken 0.7 or newer**: token-accurate code-index truncation.
- **filelock 3.12 or newer**: process-safe index refresh locking.
- **pytest**: isolated engine and code-index tests; the MCP smoke test exercises real stdio/Qdrant/OpenAI integration.

### Application Architecture

- Canonical source in `agents/`, `skills/`, `prompts/`, and `instructions/`.
- Thin host surfaces in `.claude/`, `.codex/`, `.vscode/`, `hooks/`, manifests, and user-level pointer configuration.
- Batman task state in `.batman/<task_slug>/`; approved planning checkpoints also receive curated mnemo records.
- Mnemo append-only JSONL is durable memory source of truth; Qdrant is its semantic projection.
- Host-native compaction remains owned by Codex and Claude Code. This repository may constrain, observe, and rehydrate through supported host configuration/hooks, but must not invent a replacement transcript store.

### Data Storage

- **Current source and plans**: Git worktree and checked-in Markdown artifacts.
- **Shared memory**: append-only JSONL under `~/.mnemo/events/` plus Qdrant collection `mnemo_memory` on local port 1337.
- **Host transcript/config**: owned by each host; pilot must not delete or rewrite transcripts.
- **Data formats**: Markdown, JSON, JSONL, TOML, hook event JSON, and Qdrant payloads.

### External Integrations

- **Codex CLI**: native automatic/manual compaction, configuration, plugin, and lifecycle hook APIs.
- **Claude Code**: native automatic/manual compaction, settings/environment, plugin, and lifecycle hook APIs.
- **OpenAI embeddings API**: mnemo vector embeddings only; no compaction dependency may require sending additional repository content externally.
- **Qdrant**: local vector search over durable memory records.

## Development Environment

### Build & Development Tools

- **Build System**: none for Markdown assets; Python runs directly.
- **Package Management**: `pip` using `mnemo/requirements.txt`.
- **Development Workflow**: Git worktrees, path-scoped edits, native Codex/Claude sessions, local Qdrant, and approval-gated Batman artifacts.

### Code Quality Tools

- **Static Analysis**: Python import/compile checks and targeted source inspection; no repository-wide type checker is currently configured.
- **Formatting**: preserve established Markdown, JSON, TOML, and Python style; avoid broad formatting rewrites.
- **Testing Framework**: `pytest` for `mnemo/tests`; direct MCP smoke harness; future deterministic hook fixtures.
- **Documentation**: Markdown plus self-contained HTML visual artifacts.

### Version Control & Collaboration

- **VCS**: Git.
- **Branching Strategy**: task worktree branch; preserve unrelated changes; path-scoped staging only.
- **Code Review Process**: Batman Phase 7 plus canonical review instructions before commit/PR readiness.

## Deployment & Distribution

- **Target Platforms**: Windows primary host; hook/config behavior must also remain valid on supported POSIX environments where canonical assets are used.
- **Distribution Method**: canonical checkout plus user-level pointers, MCP registration, host settings, or trusted plugin installation.
- **Installation Requirements**: supported Codex/Claude Code versions, Python 3.12 for mnemo/hook helpers, local Qdrant for shared memory, and user review/trust for executable hooks.
- **Update Mechanism**: update canonical checkout, validate adapters, then update thin user-level activation without overwriting unrelated settings.

## Technical Requirements & Constraints

### Performance Requirements

- Automatic memory and re-entry payloads must have explicit aggregate budgets.
- Hook processing must be fast enough not to cause compaction thrashing or noticeable interactive stalls.
- Pilot must show at least 50% eligible conversation-history reduction after bounded re-entry.

### Compatibility Requirements

- **Platform Support**: current tested baselines are Codex CLI 0.145.0 and Claude Code 2.1.220 on Windows; design must version-gate unsupported semantics rather than assume them.
- **Dependency Versions**: preserve current mnemo minimums in `mnemo/requirements.txt` unless a later approved design proves a change necessary.
- **Standards Compliance**: use documented host hook schemas and EARS/PRD/ADR workflow conventions.

### Security & Compliance

- Never place credentials, raw secret-bearing tool output, or full transcripts in continuation manifests, logs, hook output, or new memory records.
- Treat semantic memory and host event input as untrusted data.
- Preserve host sandbox, approval, tool, reader ACL, redaction, and hook-trust boundaries.

### Scalability & Reliability

- Workloads range from this small customization repo to large intertwined game/engine/service monorepos.
- Missing memory, Qdrant, hooks, or artifacts must degrade visibly without corrupting task state.
- Automatic compaction may happen mid-turn; continuation must not duplicate non-idempotent actions.

## Technical Decisions & Rationale

### Decision Log

1. **Current source over memory**: prevents stale or poisoned summaries from becoming authority.
2. **Artifact plus pointer state**: keeps full planning/handoff detail outside hot context while retaining deterministic retrieval.
3. **Canonical source plus thin adapters**: avoids divergent policy copies across Codex and Claude Code.
4. **Host-native compaction**: preserves supported transcript semantics; exact trigger/config mapping remains a Design-phase decision.

## Known Limitations

- Current `task_context` returns full memory bodies with no aggregate output budget.
- Current canonical compaction behavior is not activated on either host.
- Canonical repository is not installed as a plugin in either host, so plugin hook files alone do not activate behavior.
- Codex and Claude Code expose different threshold semantics; one numeric cross-host setting is invalid.
- No current benchmark or hook test suite proves post-compaction invariant retention.
