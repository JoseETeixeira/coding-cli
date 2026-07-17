---
name: byond-projects
description: Guides BYOND DM project work through documentation-backed decisions, valid DM syntax, and Dream Maker compilation. Use when analyzing, creating, editing, reviewing, or testing BYOND projects, the BYONDOT engine fork, or the MYG ("Make Your Game") stack — .dme, .dm, .dmm, .dmf, .dmi, or .dms files, including Dragon Ball Universe.
---

# BYOND projects

1. Always call the `byond-rag` MCP tool `search_byond_docs` with a focused query derived from the user prompt before making BYOND-specific factual claims, suggesting an implementation, or changing code.
2. Use the returned passages as primary evidence and include their source identifiers whenever referencing facts.
3. If retrieval returns nothing useful or the documentation tool is unavailable, state that the knowledge base did not provide support, stop BYOND-specific implementation, and ask which source or location should be indexed or supplied. Do not invent documentation support.
4. When multiple implementations are valid, use the documentation to choose the best option for the project's constraints.
5. Keep every snippet and modification compatible with BYOND DM syntax, conventions, engine behavior, and runtime constraints.

## Compile with Dream Maker

Compile every generated or modified BYOND code change against the active project's `.dme` before reporting completion. For Dragon Ball Universe on this host, run:

```powershell
& "C:\Program Files (x86)\BYOND\bin\dm.exe" "$env:USERPROFILE\Ambiente de Trabalho\Dragonball_Universe\Dragon Ball Universe\Dragon Ball Universe.dme"
```

Report the command and compiler result. If the compiler or project path is unavailable, report the exact blocker and remaining compatibility risk; do not claim the change is compile-verified.

## Dragon Ball Universe

- When implementing melee skills, basic attacks, or new overlays, ensure the icon and icon state are present in `Game/code/mobs/abilities/agility_animations.dm`.
- When adding or deleting stats, items, or equipment, update the relevant save/load functions to prevent data loss or corruption.
- Keep UI changes consistent with existing Dragon Ball Universe UI/UX patterns and themes.
- Keep skill descriptions consistent with actual in-game behavior.
- Balance and test movement or combat mechanic changes for fair gameplay.
- Use tabs for indentation in DM files.
