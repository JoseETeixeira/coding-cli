# Understanding: Gamedev Skills Workflow

## User Goal

Add the seven requested game-development, Godot, 3D, design, and motion-design capabilities to the canonical `coding-cli` skill source only when absent, then add one gamedev workflow that composes those skills with existing project-specific agents and relevant canonical workflow skills. Six skills may use reviewed upstream snapshots; `game-designer` must be independently authored because the requested snapshot's package-specific metadata restricts distribution.

## Task Slug

`gamedev-skills-workflow`

## Current Behavior

### Workflow Summary

- `coding-cli` is the canonical, host-agnostic customization source. Its `skills/` directory owns shared skills, while `agents/batman.agent.md` routes every task through `generic-entry` (`README.md:3-12`, `README.md:23-30`).
- `generic-entry` already owns request classification, the eight Batman phases, memory preflight, source-first evidence, PRD/ADR policy, skill resolution, and commit discipline (`skills/generic-entry/SKILL.md:8-15`). A gamedev workflow must compose with this entry rather than replace it.
- Conditional domain routing currently has one explicit precedent: Batman and the implementation prompt load `byond-projects` only for BYOND work (`agents/batman.agent.md:9-17`, `prompts/execute-task.prompt.md:32-34`). No equivalent general gamedev router exists.
- Existing specialist agents already own project-specific runtime/tool contracts, such as Godot 4.6 plus `godot-mcp-pro` verification for Hollow Covenant (`agents/godot-dev.agent.md:1-12`). A general workflow cannot override these project facts.
- None of `gamedev-workflow`, `game-developer`, `3d-modeling`, `game-designer`, `godot-genre-shooter-fps`, `godot-particles`, `godot-performance-optimization`, or `motion-design` exists under canonical `skills/` or the checked Claude/Codex host skill roots.
- All four upstream repositories were inspected at pinned `main` commits on 2026-07-31. The requested packages are present, but they are not uniformly ready for literal installation.

### Why This Evidence Answers The Question

- `skills/` plus each `SKILL.md` frontmatter: these are the canonical discovery and trigger sources, so directory presence and metadata answer whether a requested skill already exists and when it will load.
- `agents/batman.agent.md` and `prompts/execute-task.prompt.md`: these are current cross-phase routing boundaries, so they answer how a new gamedev workflow can be loaded for research, planning, implementation, and review without duplicating its body.
- Upstream Git trees pinned by commit SHA: these answer exactly which files would be vendored, expose missing relative dependencies, and provide immutable provenance for later review.
- Repository and package-specific licenses together determine redistribution obligations. Jeffallan and LottieFiles use MIT; GD-Agentic-Skills uses LGPL-3.0; the requested `3d-modeling` metadata identifies Apache-2.0 upstream content; and the requested `game-designer` metadata is `NOASSERTION` / restricted despite the registry root's MIT license.

### Process Distinctions And Terminology

- `gamedev-workflow` vs `game-developer`: the workflow is a router/orchestrator across design, asset, engine, VFX, performance, UI motion, verification, and docs; `game-developer` is one implementation-oriented knowledge pack whose upstream defaults are mainly Unity/Unreal.
- Generic skill vs specialist agent: a skill supplies reusable decision guidance and assets; a specialist agent owns a concrete project's engine, tools, build, verification, and local invariants.
- Vendoring vs host installation: this request targets canonical `coding-cli/skills`; `auto-improvement` forbids mirrored bodies in `~/.claude`, `~/.agents`, or `~/.codex` (`skills/auto-improvement/SKILL.md:8-10`, `skills/auto-improvement/SKILL.md:23-32`).
- Upstream snapshot vs local integration guardrail: upstream content should remain attributable and reviewable, while local precedence/version/provenance notes prevent generic or stale assumptions from overriding current project evidence.

### Components Likely To Change And Why They Exist

- `skills/gamedev-workflow/SKILL.md`: new conditional router for selecting requested and existing skills by task slice.
- `skills/game-developer/`: requested general implementation pack; includes five references.
- `skills/3d-modeling/`: requested art-pipeline pack; upstream has dangling mandatory references and needs an explicit repair decision.
- `skills/game-designer/`: clean-room canonical GDD, systems, economy, onboarding, and playtest skill; no restricted snapshot prose.
- `skills/godot-genre-shooter-fps/`: requested Godot FPS pack; includes sixteen scripts plus one reference.
- `skills/godot-particles/`: requested Godot VFX pack; includes thirteen scripts plus one reference.
- `skills/godot-performance-optimization/`: requested profiler-first Godot pack; includes twelve scripts plus one reference.
- `skills/motion-design/`: requested UI-motion pack at upstream path `skills/motion-design/`; includes director, pattern, and reference modules.
- `AGENTS.md`, `agents/batman.agent.md`, and `prompts/execute-task.prompt.md`: likely thin conditional pointers so the router is reachable outside automatic metadata matching, following the existing domain-routing shape.
- `README.md`: likely skill inventory/discovery note; current inventory names representative skills but no gamedev workflow.

### Execution Locations

- Canonical source edits execute in `C:\Users\josee\source\coding-cli`; host copies remain pointers/adapters only.
- Engine/project implementation remains in the active game repository under the matching specialist agent; imported skill scripts are reference patterns, not automatically copied into a game.
- Godot editor/runtime verification remains project-specific. For example, the current Hollow Covenant specialist requires live `godot-mcp-pro` observation and targets Godot 4.6, while the three requested Godot skill snapshots state a Godot 4.7+ baseline.
- Batman phase artifacts execute under `.batman/gamedev-skills-workflow/`; the visual recap uses the host adapter path under `~/.agent/diagrams/`.

## Likely Change Surface

### Files And Symbols

- `skills/gamedev-workflow/SKILL.md` — new trigger metadata, precedence rules, domain routing, and verification gates.
- `skills/{game-developer,3d-modeling,godot-genre-shooter-fps,godot-particles,godot-performance-optimization,motion-design}/**` — pinned/adapted upstream packages plus required license/provenance material.
- `skills/game-designer/**` — independently authored canonical content plus an origin/exclusion record and overlap verification evidence.
- `AGENTS.md` — likely one conditional gamedev pointer beside the BYOND pointer.
- `agents/batman.agent.md` — likely one conditional gamedev pointer at the canonical entry boundary.
- `prompts/execute-task.prompt.md` — likely one implementation-phase pointer so approved tasks load the same authority.
- `README.md` — likely inventory update.

### Tests

- No repository-native skill validator was found.
- The installed `skill-creator` supplies `quick_validate.py`; each new skill should pass it after frontmatter normalization.
- Add deterministic checks for required files, relative-link resolution, exact pinned source SHAs, license presence, pointer text, and absence of requested-name duplicates.
- Forward-test routing with representative prompts for generic design, Unity/Unreal implementation, 3D asset work, Godot FPS, Godot particles, Godot performance, and UI motion without mutating a live game project.

### Configuration And Infrastructure

- No runtime infrastructure change is expected.
- GitHub network access is needed only to fetch pinned public snapshots. Skill execution should not depend on live upstream availability after vendoring.
- Current worktree contains pre-existing untracked `docs/`; preserve it and avoid broad staging.

### Documentation

- A new PRD is required in `docs/prd/` after requirements approval.
- An ADR is likely warranted because vendored third-party snapshots plus local adapters, license retention, and precedence rules are hard to reverse, surprising without context, and involve real trade-offs.
- `README.md` likely needs a concise gamedev workflow entry.

## Evidence

- `README.md:3-12`: canonical repository owns shared agents, skills, prompts, and instructions across hosts.
- `README.md:23-30`: Batman is the entry and supported hosts resolve the shared customization layer.
- `AGENTS.md:7-12`: every task uses auto-improvement, mnemo, Batman workflow, and conditional BYOND routing.
- `agents/batman.agent.md:9-23`: generic-entry is mandatory; conditional domain routing and planning gates live at the entry boundary.
- `skills/generic-entry/SKILL.md:8-15`: cross-file feature work must use all planning phases; skill resolution and PRD/ADR policy are already owned here.
- `skills/auto-improvement/SKILL.md:8-10`: `coding-cli` is canonical; host bodies must not be mirrored.
- `skills/auto-improvement/SKILL.md:23-32`: customization writes require a preview and explicit approval.
- `agents/godot-dev.agent.md:1-12`: current project specialist targets Godot 4.6 and owns live editor verification, proving upstream 4.7 defaults cannot be globally authoritative.
- `https://github.com/Jeffallan/claude-skills/tree/e8be415bc94d8d6ebddc2fb50e5d03c6e27d4319/skills/game-developer`: requested `game-developer` snapshot; five bundled references; MIT repository license.
- `https://github.com/majiayu000/claude-skill-registry/tree/ef926663574f5f7a0c19b0429b2540373279ed45/skills/data/3d-modeling`: requested snapshot contains only `SKILL.md` and `metadata.json`, although `SKILL.md:56-64` mandates three absent reference files.
- `https://github.com/majiayu000/claude-skill-registry/tree/ef926663574f5f7a0c19b0429b2540373279ed45/skills/gaming/game-designer`: requested GDD/design snapshot. Its pinned `metadata.json` says `license: NOASSERTION`, `distribution: restricted`, and not to treat the package as MIT; user chose a clean-room canonical replacement on 2026-08-01.
- `https://github.com/thedivergentai/GD-Agentic-Skills/tree/ebffc2b4f39b54dcf343b52dc9845a4ecc451cf2/skills/godot-genre-shooter-fps`: requested Godot 4.7+ FPS snapshot with scripts/reference; LGPL-3.0 repository license.
- `https://github.com/thedivergentai/GD-Agentic-Skills/tree/ebffc2b4f39b54dcf343b52dc9845a4ecc451cf2/skills/godot-particles`: requested Godot 4.7+ particles snapshot with scripts/reference; LGPL-3.0 repository license.
- `https://github.com/thedivergentai/GD-Agentic-Skills/tree/ebffc2b4f39b54dcf343b52dc9845a4ecc451cf2/skills/godot-performance-optimization`: requested Godot 4.7+ performance snapshot with scripts/reference; LGPL-3.0 repository license.
- `https://github.com/lottiefiles/motion-design-skill/tree/f9a8a041b85185ee4881b3471d3415e939aac772/skills/motion-design`: requested motion-design snapshot actually lives under `skills/motion-design`; MIT repository license.
- Upstream inspection commands: `git ls-remote <repo> refs/heads/main`; GitHub Trees/Contents APIs at each SHA; raw `SKILL.md` and root `LICENSE` reads.
- Local absence query: `rg -n -i "game[- ]?dev|game developer|game designer|3d modeling|godot particles|performance optimization|motion design|lottie" skills agents prompts instructions docs .batman`; direct directory checks across canonical, `~/.claude/skills`, `~/.agents/skills`, and `~/.codex/skills`.
- Memory preflight: mnemo reachable; eight `repo:coding-cli` items returned. Used only for historical context about canonical-only pointers and source-first verification; current files and remotes independently confirm the relevant state.

## Visual Recap

- Path: `C:\Users\josee\.agent\diagrams\gamedev-skills-workflow-understanding.html`
- Notes: Shows current entry/routing boundary, seven requested package gaps, upstream integrity/license findings, likely canonical touchpoints, and precedence risks.

## Resolved Questions

- `3d-modeling`: vendor its useful body, replace the three impossible mandatory reads with a concise self-contained production checklist, and record the adaptation plus pinned source. Approved in Phase 1.
- `game-designer`: do not vendor the restricted/unknown-license snapshot. Create independently authored canonical content and retain exclusion/overlap evidence. Approved by the user on 2026-08-01 after Phase 3a licensing discovery.

## Risks And Constraints

- External skill prose contains universal-sounding rules that may be wrong for a project. Current source, project specialist, engine version, target platform, authored workload, and measured evidence must win.
- `game-developer` is mainly Unity/Unreal and hard-codes 60 FPS/object-pooling/LOD defaults; these are hypotheses unless the active project accepts them.
- Requested Godot packages target 4.7+, while at least one installed specialist targets 4.6. The workflow needs an engine-version gate and matching official docs before code reuse.
- Vendoring LGPL-3.0 scripts requires preserving the license and tracking modifications; MIT and Apache-2.0 packages also require their applicable notices. Restricted/unknown-license content must not be copied.
- Related-skill links in the Godot packs point to additional upstream skills not requested here. The workflow must not pretend those siblings are installed.
- Imported scripts are examples/patterns. Blindly copying them into active projects could violate scene structure, threading, multiplayer authority, renderer, save, or verification contracts.
- Existing untracked `docs/` belongs to the user; do not reset, delete, broadly stage, or overwrite it.

## Architecture Change Assessment

- Status: `required`
- Reason: this adds a conditional skill-orchestration layer, six third-party packages, one clean-room canonical skill, cross-phase entry pointers, provenance/license policy, and precedence rules between generic skills and project-specific specialists.
- Areas affected: canonical skills, Batman entry, implementation prompt, README, skill validation, third-party licensing/provenance, and future game-project routing.

## Initial Verification Ideas

- Run `quick_validate.py` on all eight new skill folders.
- Parse every new `SKILL.md`; assert only supported trigger frontmatter remains after normalization.
- Resolve every relative Markdown link and mandatory script/reference path.
- Compare vendored file hashes against the four pinned upstream SHAs; maintain an explicit adaptation ledger for changed files.
- Assert all requested skills are routed by `gamedev-workflow` and every route states project/source precedence.
- Assert `AGENTS.md`, Batman, and execute-task contain thin pointers only, never copied workflow bodies.
- Exercise representative routing prompts and inspect selected skills without editing live game projects.
- Run `git diff --check`, a path-scoped diff review, and a dirty-worktree preservation check.
