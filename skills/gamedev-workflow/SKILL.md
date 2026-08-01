---
name: gamedev-workflow
description: Route material game-development work across game design, gameplay implementation, 3D production, Godot FPS, Godot particles, Godot performance, and UI motion while preserving project-specific authority and evidence gates. Use for game mechanics, gameplay systems, engine code, assets, VFX, profiling, or game UI motion; compose with generic-entry and the matching project specialist rather than replacing them.
---

# Gamedev Workflow

Keep `generic-entry` active. Use this skill only to select game-development disciplines, resolve authority, and set project-specific verification boundaries.

## Boundaries

Use this workflow when work materially concerns game mechanics, gameplay code, engine integration, game assets, 3D production, VFX, performance, or UI motion.

Do not use it for casual game discussion, non-game UI animation, generic image editing, or a request that merely mentions a game. A matched route does not authorize edits, editor launches, asset copying, or runtime mutation.

## Authority

Resolve conflicts in this order:

1. Explicit current user decision and authorized scope.
2. Current project source, approved Requirements/Design/ADRs, and testable invariants.
3. Matching project specialist plus project tool/build/verification contract.
4. Actual engine, version, renderer, platform, and matching official documentation.
5. Authored workload measurements and owner visual/listening/feel acceptance.
6. This routing and safety contract.
7. Selected discipline-skill guidance and examples.

State any conflict. Never let a lower layer silently override a higher layer.

## Route Minimum Skills

| Task slice | Primary skill | Conditional composition | Gate |
|---|---|---|---|
| Mechanics, loops, economy, progression, onboarding, GDD, playtests | `game-designer` | `visual-explainer` for complex flows | Define player/audience/constraints and a measurable playtest question |
| Gameplay architecture/systems, Unity, Unreal | `game-developer` | matching specialist; `safe-refactoring-testing` for risky refactors | Project architecture/platform wins; generic FPS/pooling/LOD targets remain hypotheses |
| Mesh, topology, UV, baking, LOD, export | `3d-modeling` | matching specialist; optional `imagegen` only for bitmap ideation | Confirm DCC, engine importer, scale, axes, naming, budgets, and validation |
| Godot FPS controller/weapons | `godot-genre-shooter-fps` | matching Godot specialist; testing guidance | Confirm exact Godot version and project scene/input/physics contracts; require live editor/runtime verification |
| Godot particles/VFX | `godot-particles` | matching Godot specialist; optional `imagegen` for texture ideation | Confirm renderer/version/budget; preserve reduced-effects mode and owner visual gate |
| Godot profiling/optimization | `godot-performance-optimization` | matching Godot specialist | Require authored workload, measured baseline, correct build/renderer, and regression evidence |
| UI motion, transitions, micro-interactions, Lottie | `motion-design` | project UI authority; `visual-explainer` for flows | Provide reduced-motion equivalent; keep semantic state clear without animation; require on-screen acceptance |
| BYOND-family game work | minimum relevant design skill, if any | `byond-projects` plus BYOND specialist | BYOND-RAG evidence and Dream Maker/project verification stay mandatory |

For cross-discipline work, load the smallest union of matching rows plus one project specialist. Do not preload every skill.

## Workflow

1. Read current project instructions/source and resolve the matching specialist before applying generic advice.
2. Classify task into one or more rows; state why each selected skill is needed and why adjacent skills are not.
3. Check engine/version/renderer/platform compatibility. If unknown or incompatible, use examples only as concepts and consult matching official docs before factual engine guidance.
4. Load selected discipline `SKILL.md` files and only the references needed for the current decision.
5. Define implementation evidence before changing a project: functional tests, authored workload/performance measurements, and any required windowed visual/listening/feel acceptance.
6. Follow Batman approval, implementation, test, review, and documentation gates. Imported examples never bypass them.
7. Report static, runtime, visual, performance, accessibility, owner, and release evidence separately.

## Reference Safety

Treat bundled scripts, shaders, project settings, patterns, and examples as starting points. Before reuse, validate active project version, architecture, scene/resource layout, renderer, threading and multiplayer authority, save/replay contracts, target platforms, licenses, and project verification instructions. Never auto-copy or auto-execute them in an active game.

`imagegen` is optional host capability, not an installed dependency. Optional sibling skills linked by upstream packages are external references, not installed authority.

## Integration Contract

Use [routing cases](references/routing-cases.json) when reviewing selection behavior. Run `python skills/gamedev-workflow/scripts/validate_integration.py` after changing this workflow or any integrated discipline package.

Repository-only validation proves skill structure, links, routing fixtures, provenance, and pointer integrity. It does not prove engine runtime, renderer output, gameplay feel, performance targets, accessibility, owner acceptance, or release readiness.
