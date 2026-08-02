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

`task_context` contract version 2 intentionally returns ranked previews rather
than every selected full body. The legacy top-level `memory` field remains, but
its `text` values are bounded previews. Use the returned `memory_id` with
`memory_get` for one exact authorized live record. Reader ACL, namespace,
revocation, expiry, and redaction checks run before either preview or exact
retrieval. Unauthorized exact retrieval and revocation both return the same
content-free not-found result. This bounded response supports the opt-in native-compaction pilot but
does not enable it, change memory authority, or replace source revalidation.

## Tests

```
py -3.12 -m pytest mnemo/tests -q      # engine (fake embedder, no network)
py -3.12 mnemo/tests/mcp_smoke.py      # full stdio + real OpenAI + Qdrant
```
