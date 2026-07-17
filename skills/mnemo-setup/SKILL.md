---
name: mnemo-setup
description: How to stand up and register the mnemo self-hosted shared-memory backend (Qdrant on port 1337 + OpenAI embeddings + stdio MCP server). Use when memory_status fails, when setting up a new host, or when the mnemo MCP is missing.
disable-model-invocation: true
---

# mnemo setup

mnemo is the self-hosted shared-memory engine that backs the `shared-memory` skill. Code lives in `<coding-cli>/mnemo/`; data lives in `~/.mnemo/`; vectors live in a Qdrant container on host port **1337**.

## 1. Start Qdrant (port 1337)

```
<coding-cli>\mnemo\scripts\mnemo-qdrant.cmd
```
Creates/starts container `mnemo-qdrant` (host 1337 → container 6333, volume `mnemo_qdrant_storage`). Verify: `curl http://127.0.0.1:1337/readyz`.

## 2. Dependencies + key

```
py -3.12 -m pip install -r <coding-cli>\mnemo\requirements.txt
```
`OPENAI_API_KEY` must be set — mnemo uses OpenAI `text-embedding-3-small` with no local fallback.

## 3. Register the MCP server

**Claude Code (user scope):**
```
claude mcp add mnemo -s user \
  -e QDRANT_URL=http://127.0.0.1:1337 -e MNEMO_AGENT_ID=claude-code -e MNEMO_DATA_DIR=%USERPROFILE%\.mnemo \
  -- py -3.12 <coding-cli>\mnemo\run_server.py
```

**Codex (`~/.codex/config.toml`):**
```toml
[mcp_servers.mnemo]
command = "py"
args = ["-3.12", "<coding-cli>/mnemo/run_server.py"]
env = { QDRANT_URL = "http://127.0.0.1:1337", MNEMO_AGENT_ID = "codex", MNEMO_DATA_DIR = "C:/Users/<you>/.mnemo" }
```

Set a distinct `MNEMO_AGENT_ID` per host so writes record which agent produced them — that is what makes memory sharing observable across agents.

## 4. Verify

```
py -3.12 -m pytest <coding-cli>/mnemo/tests -q     # engine (no network)
py -3.12 <coding-cli>/mnemo/tests/mcp_smoke.py     # full stdio + OpenAI + Qdrant
```
In an agent session, call `memory_status` — a healthy result shows `qdrant_url`, `embed_model`, and a point count.

## Troubleshooting

- `memory_status` **returns, but takes ~30s** (and `code_search` is always empty) → a git call is
  hanging, not Qdrant. Check Qdrant first to rule it out (`curl http://127.0.0.1:1337/readyz` → 200,
  and `memory_stats` returns instantly because it skips the code-index preflight). Only
  `memory_status` / `task_context` pay the cost — they call `_autoindex` → `resolve_repo` →
  `git rev-parse`. Confirm with `MNEMO_CODE_AUTO_INDEX=0`: if the stall vanishes, it is this.
  Root cause fixed 2026-07-16: `_run_git` spawned git without `stdin=subprocess.DEVNULL`, so under
  stdio MCP git inherited the server's JSON-RPC pipe — on which the server's own reader holds a
  blocking read — and blocked at startup until the subprocess timeout fired. Symptoms to recognise
  it by: `git.exe` alive with 0 CPU parented to the server's `python.exe`, orphans surviving long
  after the call, and no `GIT_TRACE` file even when `GIT_TRACE` is set (git blocks before tracing
  initialises). If it ever returns, check that spawn site first, and never let a git failure be
  reported as a negative answer (see `GitUnavailable`).
- `memory_status` errors on connection → Qdrant not up; run the cmd in step 1.
- `code_index_status` → `repo_unresolved: Tried: cwd=<your home>` → the server resolves the repo from
  MCP roots, then falls back to its cwd. A user-scope registration inherits the cwd of whatever
  launched the host, which is `$HOME` on a terminal launch — and `$HOME` is refused on purpose
  (indexing there would poison the shared index). Memory tools are unaffected; only the code index
  needs a repo. Fix by launching the host from the repo, or set `MNEMO_REPO` on a project-scoped
  registration. Treat a message naming a directory that *is* a git repo as a bug, not a diagnosis —
  that string is also what a broken git used to produce.
- Dimension-mismatch error → the collection was created with a different embedder; set `MNEMO_COLLECTION` to a fresh name or delete `mnemo_memory` and let it recreate.
- Empty results everywhere → check `MNEMO_DATA_DIR` and namespace; both agents must share the same Qdrant URL and data dir to share memory.
