---
name: excalidraw-mcp-diagrams
description: Create architecture and flow diagrams using the Excalidraw MCP. Use when drawing diagrams for presentations, documenting system architecture, or when the user asks for Excalidraw diagrams, MCP diagrams, or diagram drafting.
---

# Excalidraw MCP Diagrams

## Before You Begin

1. **Read the design guide**: Call `mcp_excalidraw_read_diagram_guide` to get colors, sizing, and layout rules.
2. **Clear canvas if needed**: Call `mcp_excalidraw_clear_canvas` if starting a new diagram.

---

## Critical: Text and Z-Order

### Text-in-boxes behavior

**Do NOT** use `text` on rectangles in `mcp_excalidraw_batch_create_elements`. The MCP creates a `label` that renders **outside or offset from the box**, so labels appear disconnected.

**Instead:**
1. Create rectangles as **empty shapes** (no `text` property).
2. Create **separate text elements** positioned inside each rectangle.
3. Use an **8px inset** from the rectangle edges (e.g., rect at `x,y` → text at `x+8, y+8`).

### Element creation order (z-order)

In Excalidraw, elements created later are drawn on top. **Always create in this order:**

1. **Rectangles** (background layer)
2. **Arrows**
3. **Text elements** (foreground layer)

If text is created before rectangles (e.g., after recreating boxes), text will appear **behind** the boxes. Fix by deleting and recreating the text elements so they are created last.

---

## Workflow

### 1. Create rectangles

Use `mcp_excalidraw_batch_create_elements` with `type: "rectangle"`, assign stable `id`s (e.g. `signals`, `orchestrator`). Do **not** pass `text`.

```json
{"id": "signals", "type": "rectangle", "x": 100, "y": 80, "width": 160, "height": 80, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2"}
```

### 2. Create arrows with binding

Use `startElementId` and `endElementId` so arrows auto-route to shape edges.

```json
{"id": "arr1", "type": "arrow", "startElementId": "signals", "endElementId": "orchestrator", "strokeColor": "#1e1e1e", "endArrowhead": "arrow"}
```

Use `strokeStyle: "dashed"` for optional/feedback flows; `strokeStyle: "dotted"` for weak dependencies.

### 3. Create text elements (last)

Position text at `rect.x + 8`, `rect.y + 8` with `width: rect.width - 16`, `height: rect.height - 16`. Use `fontSize: 14` or `16`.

```json
{"id": "t_signals", "type": "text", "x": 108, "y": 88, "width": 144, "height": 64, "text": "Signals / Triggers\n• Item 1\n• Item 2", "fontSize": 14, "fontFamily": "Virgil"}
```

---

## Color palette (from guide)

| Use case           | Fill       | Stroke   |
|--------------------|------------|----------|
| Inputs / signals   | #a5d8ff    | #1971c2  |
| Orchestration/eval| #eebefa    | #9c36b5  |
| Primary / agent    | #b2f2bb    | #2f9e44  |
| Async / tools      | #ffd8a8    | #e8590c  |
| Data / persistence | #99e9f2    | #0c8599  |
| Human / feedback   | #ffc9c9    | #e03131  |
| Annotations        | #e9ecef    | #868e96  |

---

## Sizing and layout

- **Shapes**: min 120×60; typical 160×80
- **Gaps**: 40–80px between adjacent shapes
- **Grid snap**: align to 20px
- **Flow**: left-to-right = temporal order; top-to-bottom = hierarchy

### Multiple sources converging on one target

When several shapes (e.g. signal types) each have an arrow to the same target:

1. **Space sources generously** — use at least 100–120px horizontal and 80–100px vertical gap between source shapes so arrows do not overlap.
2. **Avoid arrow overlap** — if arrows converge on the same target from sources that are too close, they will run on top of each other and be hard to read.
3. **Layout options**: use a 2×2 grid with wider spacing, or a vertical stack with ~80px between items, so each arrow has a distinct path.

---

## Checklist

- [ ] Called `read_diagram_guide` first
- [ ] Rectangles created without `text`
- [ ] Arrows use `startElementId` / `endElementId`
- [ ] Text elements created **after** rectangles and arrows
- [ ] Text inset 8px from rectangle edges
- [ ] Colors from palette
- [ ] Multiple sources → one target: 100–120px horizontal, 80–100px vertical gaps between sources
- [ ] Call `set_viewport(scrollToContent: true)` when done

---

## Troubleshooting

| Problem              | Fix                                                  |
|----------------------|------------------------------------------------------|
| Text outside boxes   | Remove `text` from rectangles; add separate text elements |
| Text behind boxes    | Delete text elements; recreate them last             |
| Arrows not connecting| Use `startElementId` and `endElementId` on arrows    |
| Cramped layout       | Increase gaps to 60–80px; enlarge shapes             |
| Arrows overlapping   | Space source shapes 100–120px apart; avoid converging arrows from nearby sources |
| Sources too close    | Use 80–100px vertical and 100–120px horizontal gaps between multiple sources → one target |
