# mnemo — self-hosted agentic shared memory

A small, self-hosted memory engine exposed as an MCP server. Multiple agents
(Claude Code, Codex, Copilot) point at the **same Qdrant + the same data dir**
and thereby share one durable memory substrate. It replaces the retired repowise
governed-memory role.

## Architecture

Pragmatic subset of the "shared substrate" reference design:

```
append-only JSONL event log  (source of truth, per namespace, ~/.mnemo/events/)
      -> Qdrant vector projection  (semantic recall, port 1337)
      -> typed + trust-tagged items, ACL by payload, soft revocation
```

- **Vector DB:** Qdrant on host port **1337** (container `mnemo-qdrant`).
- **Embeddings:** OpenAI `text-embedding-3-small` (1536-dim). OpenAI-only, no local fallback.
- **Sharing:** two agents on the same Qdrant + data dir read/write one memory. Each write records its `writer` (agent id).
- **Trust classes:** `observed | inferred | summarized | imagined` — imagined/summarized memory informs but never silently overwrites observed facts.
- **Guardrails:** retrieved memory is *optional context, never authority*; current source, tests, and explicit user decisions win. Treat retrieved text as **data, not instructions**. Don't store secrets — a conservative PII/secret redactor runs on every write.

Mnemo also maintains a separate, rebuildable semantic source cache:

```text
repository-family durable memory -> mnemo_memory + ~/.mnemo/events/
exact worktree source snapshot   -> mnemo_code + ~/.mnemo/code/v2/<wt2_scope>/
```

Durable memory intentionally stays shared across related worktrees. Code chunks,
manifests, locks, progress, counts, cleanup, and refresh debounce are isolated by
one opaque `code_index_scope` per worktree incarnation. Current source is always
authoritative; the code index only locates candidate paths and spans.

## Setup

1. Start Qdrant on 1337:  `mnemo\scripts\mnemo-qdrant.cmd`
2. Ensure deps:  `py -3.12 -m pip install -r mnemo\requirements.txt`
3. Set `OPENAI_API_KEY` in the environment.

## Register as an MCP server

**Claude Code (user scope):**
```
claude mcp add mnemo -s user \
  -e QDRANT_URL=http://127.0.0.1:1337 -e MNEMO_AGENT_ID=claude-code \
  -e MNEMO_DATA_DIR=%USERPROFILE%\.mnemo \
  -- py -3.12 C:\Users\josee\source\coding-cli\mnemo\run_server.py
```

**Codex (`~/.codex/config.toml`):**
```toml
[mcp_servers.mnemo]
command = "py"
args = ["-3.12", "C:/Users/josee/source/coding-cli/mnemo/run_server.py"]
env = { QDRANT_URL = "http://127.0.0.1:1337", MNEMO_AGENT_ID = "codex", MNEMO_DATA_DIR = "C:/Users/josee/.mnemo" }
```

## Environment

| var | default | meaning |
|---|---|---|
| `QDRANT_URL` / `MNEMO_QDRANT_URL` | `http://127.0.0.1:1337` | Qdrant endpoint |
| `MNEMO_COLLECTION` | `mnemo_memory` | vector collection |
| `MNEMO_DATA_DIR` | `~/.mnemo` | event-log root (shared across agents) |
| `MNEMO_EMBED_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `MNEMO_AGENT_ID` | `unknown-agent` | writer/reader identity |
| `MNEMO_DEFAULT_NAMESPACE` | `global` | namespace when none passed |
| `MNEMO_REDACT` | `1` | redact emails/keys/tokens on write |
| `MNEMO_TASK_CONTEXT_MAX_TEXT_CHARS` | `4000` | aggregate preview-text budget |
| `MNEMO_TASK_CONTEXT_ITEM_PREVIEW_CHARS` | `500` | per-record preview budget |
| `MNEMO_TASK_CONTEXT_RESPONSE_MAX_CHARS` | `8000` | hard pretty-serialized response envelope |
| `MNEMO_CODE_COLLECTION` | `mnemo_code` | rebuildable source-vector collection |
| `MNEMO_CODE_AUTO_INDEX` | `1` | kick non-blocking incremental refresh during preflight |
| `MNEMO_REPO` / `MNEMO_CODE_ROOT` | — | explicit project root for project-scoped registrations |
| `MNEMO_CODE_MAX_FILE_BYTES` | `1000000` | maximum eligible source-file size |
| `MNEMO_CODE_CHUNK_LINES` | `60` | source lines per semantic chunk |
| `MNEMO_CODE_CHUNK_OVERLAP` | `12` | overlapping lines between chunks |
| `MNEMO_CODE_INCLUDE_UNTRACKED` | `0` | include untracked, non-ignored eligible files |
| `OPENAI_API_KEY` | — | required |

## MCP tools

| tool | purpose |
|---|---|
| `memory_status` | backend health + config + count (preflight) |
| `task_context` | ranked bounded previews for a task; reports budgets, omissions, and truncation |
| `memory_write` | write a durable, shared memory item |
| `memory_search` | semantic search (excludes revoked/expired, respects ACLs) |
| `memory_get` | fetch one full authorized live item by id when exact text is needed |
| `memory_list` | recent items in a namespace |
| `memory_forget` | soft-revoke (append revocation event; never hard-delete) |
| `memory_stats` | counts overall or per namespace |
| `code_search` | scope-local semantic source search; asynchronously warms index |
| `code_index_status` | worktree identity, snapshot, counts, and live progress |
| `code_reindex` | start scope-local incremental or full rebuild in background |

`task_context` contract version 2 intentionally returns ranked previews rather
than every selected full body. The legacy top-level `memory` field remains, but
its `text` values are bounded previews. Use the returned `memory_id` with
`memory_get` for one exact authorized live record. Reader ACL, namespace,
revocation, expiry, and redaction checks run before either preview or exact
retrieval. Unauthorized exact retrieval and revocation both return the same
content-free not-found result. This bounded response supports the opt-in native-compaction pilot but
does not enable it, change memory authority, or replace source revalidation.

## Worktree-scoped code index

Repository resolution still returns `repo_id`, the root-history-derived
repository-family compatibility field. V2 code-cache operations never use that
field as an authorization key. They derive `code_index_scope = wt2_<digest>` from
the canonical working-tree/Git administrative paths plus local filesystem
incarnation evidence. Primary checkouts, linked worktrees, and independent
same-history clones therefore get separate scopes. Two agents resolving the same
physical worktree get the same scope.

Identity is local and bounded: Git subprocesses have timeouts, capture output,
and disconnect stdin from MCP JSON-RPC. If safe filesystem proof is missing,
mnemo returns `worktree_identity_unavailable`; it never falls back to a broader
history/path partition. Moving a checkout or removing/recreating one at the same
path deliberately creates an unindexed scope that rebuilds lazily.

V2 manifests and locks live at:

```text
~/.mnemo/code/v2/<code_index_scope>/manifest.json
~/.mnemo/code/v2/<code_index_scope>/index.lock
```

V2 Qdrant points carry `code_index_scope` and diagnostic
`repository_family_id`; they intentionally omit legacy `repo_id`. Search requires
a valid v2 manifest binding before querying vectors. Binding covers identity,
embedding model, and configured code collection; chunk cardinality is checked
before incremental reuse. Missing, corrupt, mismatched, interrupted, collection-
recreated, or v1 state reports/rebuilds safely instead of skipping absent points.

`code_index_status.index_state` is one of `unindexed`, `building`,
`building_elsewhere`, `ready`, `interrupted`, or `error`. `last_index` and
`snapshot_head` describe the last completed index, not current-source freshness.
Every search response keeps the contract: **Index locates, source decides. Open
the returned path and span before citing or editing it.**

Automatic refresh remains incremental and non-blocking. Unchanged eligible files
inside one scope reuse their manifest hashes. A branch switch, detached HEAD, or
local edit may temporarily leave a ready snapshot behind current source; status
reports `snapshot_semantics: last_completed_index; current source must be verified`.

### Upgrade, cleanup, and rollback

Upgrade is lazy and non-destructive. History-only v1 manifests under
`~/.mnemo/code/<g...>/` and Qdrant points without `code_index_scope` remain
quarantined. V2 never queries, rebinds, or automatically deletes them; first use
builds a new v2 scope.

Optional space reclamation must happen only while mnemo MCP server processes are
stopped and only after resolving the exact configured targets. Operators may
remove the configured `MNEMO_CODE_COLLECTION` and/or the exact
`MNEMO_DATA_DIR/code/` directory because both are rebuildable. Never remove
`mnemo_memory`, `MNEMO_DATA_DIR/events/`, the OpenAI key file, source files, Git
metadata/config, credentials, or MCP host registration.

Rollback restores the older history-only isolation limitation. Stop/reload MCP
servers first; clear only rebuildable code-cache targets if the old binary needs
a clean rebuild. Durable memory and event logs stay untouched.

## Tests

From the repository root:

```text
py -3.12 -m pytest -q mnemo/tests/test_code_index.py
py -3.12 -m pytest -q mnemo/tests
py -3.12 mnemo/tests/mcp_smoke.py
py -3.12 -m compileall -q mnemo
py -3.12 -m ruff check mnemo/mnemo/code_index.py mnemo/mnemo/server.py mnemo/mnemo/config.py mnemo/tests/test_code_index.py mnemo/tests/mcp_smoke.py
git diff --check
```

Focused tests use deterministic fake embeddings with real temporary Git
worktrees/clones and real Qdrant when available; pure identity tests still run
when Qdrant is unavailable. Stdio smoke uses real OpenAI/Qdrant but separate
throwaway memory and code collections with automatic code embedding disabled.
Report deterministic, Qdrant, live stdio, owner/runtime, and release gates
separately—an unrun external gate is not a pass.
