# Miro Flowchart DSL Reference

## Graph Direction

```
graphdir TB   # Top-to-bottom
graphdir LR   # Left-to-right
graphdir BT   # Bottom-to-top
graphdir RL   # Right-to-left
```

## Palette

```
palette #fff6b6 #c6dcff #adf0c7 #c3faf5 #dedaff
```

Default palette: `#fff6b6` (general), `#c6dcff` (decisions), `#adf0c7` (start/end). Palette supports custom hex colors.

## Nodes

Format: `n<id> <label> <object> <color_index>`

**Objects:**
- `flowchart-process` — rectangle
- `flowchart-decision` — diamond
- `flowchart-terminator` — rounded (start/end)
- `flowchart-data` — parallelogram

**Color index**: 0-based index into palette (0 = first color).

## Connectors

Format: `c <source_id> <text> <target_id>`

- Use `-` for empty connector text.
- Connector text describes the transition, not a repeat of the node label.

## Clusters

Format: `cluster <cluster_id> "<label>" <node_id1> <node_id2> ...`

- Define clusters **after** all nodes and connectors.
- A node belongs to at most one cluster.
- Cluster creates a container (dashed border) around its nodes.

## Example

```
graphdir TB
palette #fff6b6 #c6dcff #adf0c7

n1 Inbound comms flowchart-process 0
n2 Orchestrator flowchart-process 1
n3 Deep Agent flowchart-process 2
c n1 triggers n2
c n2 routes n3

cluster c1 "Signals" n1
cluster c2 "Run" n2 n3
```
