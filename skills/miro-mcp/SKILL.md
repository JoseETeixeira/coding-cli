---
name: miro-mcp
description: Create and edit Miro boards via MCP—flowcharts, docs, tables, images. Use when the user wants to create Miro diagrams, add content to a Miro board, or work with Miro board URLs.
---

# Miro MCP

## Board Access

- **Board ID**: Use full URL including `?share_link_id=...` when the board is shared by link.
- **Access denied**: Add the MCP's Miro account as collaborator with edit access. Share links alone may return empty data.
- **Empty results**: Share link may be view-only; grant edit access or add as collaborator.

---

## Creating Flowcharts

### Workflow

1. **Always call `diagram_get_dsl` first** for the diagram type (flowchart, uml_class, uml_sequence, entity_relationship).
2. Generate DSL text following the spec.
3. Call `diagram_create` with `diagram_dsl`, `diagram_type`, and `title`.

### Layout and overlap

- **Shorter labels** → smaller nodes → more padding between nodes and cluster borders.
- **Layout direction** affects connector routing:
  - `graphdir LR` (left-right): arrows may cross through other boxes.
  - `graphdir TB` (top-bottom): often cleaner when multiple outputs (e.g. Tools + Artifacts side by side under Deep Agent).
- Place sibling target nodes **side by side** so arrows branch without crossing.

### Flowchart DSL (minimal)

```
graphdir TB
palette #fff6b6 #c6dcff #adf0c7

n1 Label A flowchart-process 0
n2 Label B flowchart-process 1
c n1 - n2

cluster c1 "Container" n1 n2
```

- **Nodes**: `n<id> <label> flowchart-process|flowchart-decision|flowchart-terminator <color_index>`
- **Connectors**: `c <source_id> <text|-> <target_id>`
- **Clusters**: `cluster <id> "<label>" <node_ids...>` — define after all nodes/edges.

For full DSL spec (objects, colors, clusters), see [reference.md](reference.md).

---

## Other Board Content

| Tool | Use |
|------|-----|
| `doc_create` | Add markdown doc; supports # headings, **bold**, lists, [links](url) |
| `doc_get` / `doc_update` | Read or edit existing docs |
| `table_create` | Create table with text/select columns |
| `table_sync_rows` | Add or update rows; use `key_column` for updates |
| `image_get_url` / `image_get_data` | Retrieve image from board |
| `context_explore` | List frames, documents, prototypes on board |
| `context_get` | Get content from item (URL must include `moveToWidget` or `focusWidget`) |
| `board_list_items` | List items by type (document, card, frame, image, etc.) |

---

## Tool Reference

**No** `context_get_board_docs` — use `context_explore`, `context_get`, and `board_list_items` instead.

**Connector routing** is automatic; positions are algorithmic. If arrows or labels overlap, adjust layout (direction, clustering) or tweak manually in Miro.

---

## Checklist

- [ ] Board URL includes `share_link_id` if using link sharing
- [ ] Called `diagram_get_dsl` before `diagram_create`
- [ ] Shorter node labels for better padding
- [ ] TB layout when multiple outputs from one node (avoids arrow overlap)
- [ ] Clusters defined after all nodes and connectors
