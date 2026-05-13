# query-code MCP

`query-code-mcp` is the workspace codebase search server. A Python CocoIndex pipeline keeps a JSON chunk index on disk; a Node MCP server reads that index and exposes four tools to the agent. No embedding model, no vector DB, no cloud calls — purely local files.

Source lives in [`query-code-mcp/`](../query-code-mcp/).

## How indexing works

The pipeline ([`codebase_index.py`](../query-code-mcp/codebase_index.py)) discovers projects, walks each one with a glob matcher, splits text files into overlapping chunks, and emits one JSON file per chunk into the output directory.

```text
WORKSPACE_ROOT/
  coding-cli/          # skipped automatically
  project-a/           # ┐
  project-b/           # ├── indexed
  project-c/           # ┘

.cocoindex/codebase-index/
  project-a/<flattened-path>__<sha1>.json
  project-b/...
```

Each chunk JSON carries the project name, source file path, line range, character offsets, and chunk text — enough for the MCP server to return useful context without further file reads.

### Project discovery

By default the pipeline scans every top-level subdirectory of `WORKSPACE_ROOT` whose name doesn't start with `.` and isn't `coding-cli`. Override with `CODEBASE_PROJECTS=projA,projB` to index a specific set.

### File matcher

Included globs (see `SOURCE_MATCHER`): `*.py`, `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.mjs`, `*.cjs`, `*.go`, `*.java`, `*.rs`, `*.rb`, `*.kt`, `*.json`, `*.md`, `*.mdx`, `*.yaml`, `*.yml`, `*.toml`, `*.tf`, `*.sql`, `*.html`, `*.css`, `*.scss`, `*.sh`, `*.tex`, `*.graphql`, `*.proto`, `Dockerfile`, `Makefile`.

Excluded: `.git/`, `.venv/`, `venv/`, `node_modules/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.next/`, `.turbo/`, `dist/`, `build/`, `coverage/`, `target/`, `*.env`, `*lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`, plus secrets/images/archives.

### Chunking

Defaults: 1600-character chunks with 250-character overlap, files larger than 350 kB are skipped. Tune via env vars (see below). Language is detected by extension so the recursive splitter can prefer syntactic boundaries.

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `WORKSPACE_ROOT` | `..` (parent of `query-code-mcp/`) | Where to look for project subdirectories. Set by `coding-cli` based on the resolved workspace root. |
| `CODEBASE_PROJECTS` | empty | Comma-separated allowlist of project directory names *relative to `WORKSPACE_ROOT`*. Used when `run indexing` scopes to a single sibling project. |
| `CODEBASE_PROJECT_PATHS` | empty | Comma-separated `name=/abs/path` entries pointing at projects *outside `WORKSPACE_ROOT`*. Used when `run indexing` is invoked from a cwd that isn't inside any workspace. Takes precedence over `CODEBASE_PROJECTS`. |
| `CODEBASE_INDEX_DIR` | `./.cocoindex/codebase-index` | Where chunk JSON files land. |
| `COCOINDEX_DB` | `./.cocoindex/cocoindex.db` | CocoIndex incremental-state DB. |
| `COCOINDEX_MAX_INFLIGHT_COMPONENTS` | `8` | Concurrency cap for the pipeline. |
| `CODEBASE_CHUNK_SIZE` | `1600` | Target chunk size in characters. |
| `CODEBASE_CHUNK_OVERLAP` | `250` | Overlap between consecutive chunks. |
| `CODEBASE_MAX_FILE_BYTES` | `350000` | Files larger than this are skipped entirely. |

When neither `CODEBASE_PROJECTS` nor `CODEBASE_PROJECT_PATHS` is set, the pipeline auto-discovers every non-hidden top-level directory under `WORKSPACE_ROOT` except `coding-cli`.

### Running the indexer

`coding-cli run indexing` is the supported entry point — it activates the venv, exports the env vars, and runs `cocoindex update codebase_index.py`. To run it directly:

```bash
cd <workspace>/coding-cli/query-code-mcp
source .venv/bin/activate
cocoindex update codebase_index.py            # one-shot
cocoindex update codebase_index.py -L         # live mode, re-indexes on file change
```

The Claude Code SessionStart hook (installed by `setup agent --claude-code`) does this for you on every new Claude Code session — see [`.claude/hooks/refresh-cocoindex.sh`](../.claude/hooks/refresh-cocoindex.sh).

## MCP tools

The Node MCP server is [`src/index.ts`](../query-code-mcp/src/index.ts). Built with `npm run build` (which `coding-cli setup mcp` runs automatically), it speaks the MCP stdio protocol and registers four tools.

### `search_codebase`

Generic search over the local index. Tokenizes the query, scores each chunk by literal match on file path + content plus per-token occurrences, and returns the top-N highest-scoring chunks.

| Argument | Type | Description |
| --- | --- | --- |
| `query` | string | Natural-language query, symbol name, error string, or code snippet. |
| `limit` | number (1–20, default 10) | Max results. |
| `file_filter` | string (optional) | Substring filter against the chunk's `filePath` (e.g. `"backend"`, `"src/utils"`). |

Returns blocks of the form:

```text
--- Result 1 (score: 92.0) ---
File: project-a/src/handlers/auth.ts (lines 42-78)

<chunk text>
```

### `analyze_error`

Convenience wrapper for stack-trace-driven lookup.

| Argument | Type | Description |
| --- | --- | --- |
| `error_message` | string | The error message or description. |
| `traceback` | string (optional) | Stack trace. |
| `context` | string (optional) | Free-form extra context. |

Concatenates the three fields and runs them through `search_codebase` with `limit=10`. The agent does the analysis — the tool just hands back the most relevant local code.

### `explain_code`

Quick lookup for a function, class, or pattern.

| Argument | Type | Description |
| --- | --- | --- |
| `query` | string | Symbol name or description. |
| `detail_level` | `"brief"` \| `"detailed"` (default `"detailed"`) | `brief` returns 3 chunks, `detailed` returns 8. |

### `indexing_status`

Returns the index directory, total chunk count, and per-project chunk counts. Useful as a health check before searching.

## Caching

The MCP server caches the entire chunk list in memory for `CODEBASE_INDEX_CACHE_TTL_MS` (default 60000 ms = 60 s). After the TTL, the next tool call re-reads the index from disk. This keeps repeated searches in a single turn fast while still picking up fresh `cocoindex update` output within a minute.

## Setup outside `coding-cli`

If you want to run `query-code-mcp` against a workspace without going through `coding-cli setup`:

```bash
cd <workspace>/coding-cli/query-code-mcp
npm install
npm run build
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cocoindex update codebase_index.py
```

Then point your MCP host at `dist/index.js`. Example for Claude Code's `~/.claude.json`:

```json
{
  "mcpServers": {
    "query-code": {
      "command": "node",
      "args": ["/abs/path/to/coding-cli/query-code-mcp/dist/index.js"],
      "cwd": "/abs/path/to/coding-cli/query-code-mcp",
      "env": {
        "WORKSPACE_ROOT": "/abs/path/to/workspace",
        "CODEBASE_INDEX_DIR": "/abs/path/to/coding-cli/query-code-mcp/.cocoindex/codebase-index"
      }
    }
  }
}
```

`coding-cli setup mcp` writes exactly this shape — see [cli-reference.md](cli-reference.md#coding-cli-setup-mcp---host) for the per-host config format.
