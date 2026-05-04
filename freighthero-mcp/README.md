# FreightHero Codebase MCP Server

An MCP stdio server for searching the FreightHero codebase. CocoIndex builds and maintains a local JSON chunk index for `ai_watchtower`, `backend`, and `frontend`; the MCP server reads that local index directly.

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

The indexer scans these workspace folders by default:

- `../ai_watchtower`
- `../backend`
- `../frontend`

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `FREIGHTHERO_REPO_ROOT` | `..` | Workspace root containing the three projects. |
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
    "freighthero-codebase": {
      "command": "node",
      "args": ["/path/to/freighthero/freighthero-mcp/dist/index.js"],
      "env": {
        "CODEBASE_INDEX_DIR": "/path/to/freighthero/freighthero-mcp/.cocoindex/codebase-index"
      }
    }
  }
}
```

Docker config:

```json
{
  "mcpServers": {
    "freighthero-codebase": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e",
        "CODEBASE_INDEX_DIR=/index",
        "-v",
        "/path/to/freighthero/freighthero-mcp/.cocoindex/codebase-index:/index:ro",
        "freighthero-mcp"
      ]
    }
  }
}
```

Keep the local index fresh with `npm run index:coco` or `npm run index:coco:live` before using the MCP tools.