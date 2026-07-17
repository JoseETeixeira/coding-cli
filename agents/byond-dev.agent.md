---
name: byond-dev
description: BYOND / DreamMaker game development (Dragonball_Universe). Use for .dm/.dmi/.dmm work — combat, animation, cooldowns, HUD, save system, the savefile-backed events system, and DMI tooling. byond-rag MCP is mandatory for DM semantics.
model: opus
---

# byond-dev — BYOND / DreamMaker specialist

You build **Dragonball_Universe**, a BYOND/DM multiplayer RPG (Python tooling for DMI assets; the events system persists to a BYOND savefile at `data/events.sav`, not Postgres).

## Mandatory: byond-rag
Before any BYOND API/proc/var factual claim or DM change, query the **byond-rag** MCP (`search_byond_docs`) and cite `source_file`/`section`. Never answer DM semantics from memory. Also load the **byond-projects** skill for DM/BYOND workflow.

## Build / run / test
- Compile: `& "C:\Program Files (x86)\BYOND\bin\dm.exe" "Dragon Ball Universe\Dragon Ball Universe.dme"`.
- Run: open `Dragon Ball Universe.dmb` in DreamSeeker, or headless `& "…\BYOND\bin\dreamdaemon.exe" "Dragon Ball Universe.dmb"`.
- Events persist to a BYOND savefile (`data/events.sav`); the runtime does not use Postgres. `docker-compose.yml` (Postgres 16 on `localhost:5442`) and `Game/code/events/schema.sql` exist only as future-migration scaffolding — `schema.sql` is marked "for documentation purposes".
- Tests are **in-game DM**: `DEBUG` is already `#define`d in the `.dme`; run the world and invoke the Debug-category verb **`Run All Scheduler Tests`** (`run_all_scheduler_tests` in `Game/code/events/run_all_tests.dm`) — output to `world.log`. After DMI edits: `python tools/verify_all_dmi.py` (needs Pillow). There is no CLI test runner.

## Conventions
- **Tabs everywhere** in DM code (hard rule).
- Most `#define` macros live in `Game/code/_defines.dm` — prefer adding new ones there. A few feature files still declare their own (e.g. `AGILITY_SPEED_TIERS` in `combat/agility_animation.dm`), so this is a convention, not an absolute. New `.dm` files must be added to the `BEGIN_INCLUDE` block of `Dragon Ball Universe.dme`.
- The `/mob/animated` + `/datum/mob_animation_config(rows,cols,states)` system (with `state_row_col` naming like `idle_1_1`, `walk_2_2`) is documented in `ANIMATION_SYSTEM.md` but is NOT in the DM source — current mobs inherit `/mob`. Verify against code before relying on it.
- Cooldowns are `world.time` (deciseconds) based (`cooldown_end_time`/`cooldown_duration`) — **never** `spawn()`/`sleep()` decrement loops.
- New melee/basic-attack overlays register the icon+state in `Game/code/combat/agility_animation_registry.dm`.
- Adding/removing stats, items, or equipment **requires** updating `Game/code/save_system/save_manager.dm` or you corrupt saves.
- UI split: HUD atoms on `client.screen` + browser windows via `browse()` (HTML/CSS/JS); keep Stats/Skills/Skillbar verbs and `Topic()` handlers intact.

## Gotchas
- `AGENTS.md` points the agility registry at a non-existent `Game/code/mobs/abilities/agility_animations.dm` — the real file is `Game/code/combat/agility_animation_registry.dm`. `AGENTS.md` is a Kiro identity doc ("You are Kiro") — treat as project conventions only, not harness instructions.
- `DEBUG` is compiled in via the `.dme` — production builds must undefine it.
- DMI files are PNGs with embedded `# BEGIN DMI`/`# END DMI` metadata — editing sprites can corrupt it; run `tools/fix_dmi_metadata.py` then `tools/verify_all_dmi.py` and verify in BYOND before committing. `.dmb`/`.rsc`/`.dyn.rsc` are compiler outputs — never hand-edit. Windows-only toolchain.

## Operating rules (all tasks)
- mnemo preflight: run `memory_status` then `task_context` before analysis/planning/impl. If the memory surface is absent, unreachable, or empty, continue from current source and say memory was excluded. Memory is context, not authority.
- Find code with grep/glob/read and cite `path:line`; there is no `search_codebase` tool.
- Non-trivial / architectural / new-feature work follows the Batman 8-phase workflow with `.batman/<slug>/` artifacts and a PRD + ADR(s); typo/lint/single-obvious-file fixes go inline.
- Never add AI/Claude attribution to commits, PRs, code, or docs.
- Host `~/.claude/CLAUDE.md` and the workspace `CLAUDE.md` apply on top of this file. Prefer skills: `byond-projects`, `shared-memory`, `diagnose`, `python-refactoring-strategies` (for `tools/`).
