# query-code MCP Server

An MCP stdio server for searching a workspace codebase. CocoIndex builds and maintains a local JSON chunk index for every project directory it finds under the workspace root; the MCP server reads that local index directly.

No OpenAI API key, embedding model, or Qdrant instance is required. The MCP tools return relevant code context, and the calling agent LLM is responsible for explaining or analyzing it.

## Prerequisites

- Node.js 22+
- Python 3.11+
- Docker, only if you want to run the MCP server in a container

## Install

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Build the CocoIndex Index

Run the indexer from this directory:

```bash
source .venv/bin/activate
cocoindex update codebase_index.py
```

The default output directory is `./.cocoindex/codebase-index`. It contains one JSON file per indexed chunk and is safe to regenerate.

By default the indexer scans every top-level subdirectory of `WORKSPACE_ROOT` (the parent of `coding-cli`), skipping the `coding-cli` directory itself. Pass `CODEBASE_PROJECTS=projA,projB` to restrict the set explicitly.

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WORKSPACE_ROOT` | `..` | Workspace root that contains the projects to index. |
| `CODEBASE_PROJECTS` | (auto-detected) | Comma-separated allowlist of project directory names to index. |
| `CODEBASE_INDEX_DIR` | `./.cocoindex/codebase-index` | Local JSON chunk index directory. |
| `COCOINDEX_DB` | `./.cocoindex/cocoindex.db` | CocoIndex internal incremental state DB. |
| `COCOINDEX_MAX_INFLIGHT_COMPONENTS` | `8` | Max concurrent processing components. |
| `CODEBASE_CHUNK_SIZE` | `1600` | Target chunk size. |
| `CODEBASE_CHUNK_OVERLAP` | `250` | Character overlap between chunks. |

For continuous updates while editing files:

```bash
cocoindex update codebase_index.py -L
```

## Build the MCP Server

```bash
npm run build
```

## Tools

| Tool | Description |
| --- | --- |
| `search_codebase` | Search the local CocoIndex chunk index. Supports file path filtering. |
| `analyze_error` | Retrieve local code context for an error message or stack trace. |
| `explain_code` | Retrieve local code snippets for a function, class, or pattern. |
| `indexing_status` | Check local index path, chunk count, and per-project counts. |

## MCP Configuration

Native Node.js config:

```json
{
  "mcpServers": {
    "query-code": {
      "command": "node",
      "args": ["/path/to/workspace/coding-cli/query-code-mcp/dist/index.js"],
      "env": {
        "CODEBASE_INDEX_DIR": "/path/to/workspace/coding-cli/query-code-mcp/.cocoindex/codebase-index"
      }
    }
  }
}
```

Keep the local index fresh with `npm run index:coco` or `npm run index:coco:live` before using the MCP tools.
