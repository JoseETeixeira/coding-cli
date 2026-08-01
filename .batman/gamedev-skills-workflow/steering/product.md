# Product Overview

## Product Purpose

`coding-cli` is the canonical, host-agnostic customization source for Batman agents, prompts, instructions, skills, and shared-memory behavior. This task extends it with a game-development workflow that can select specialized design, art, engine, VFX, performance, and UI-motion guidance without weakening the existing source-first Batman workflow.

## Target Users

- Developers using Batman across Godot, Unreal, custom-engine, Roblox, BYOND, and other game projects.
- Designers and technical artists who need reusable mechanics, 3D-pipeline, VFX, performance, or motion guidance.
- Maintainers who need third-party skills to remain attributable, reviewable, and consistent across supported hosts.

Their main pain points are fragmented game-development guidance, generic recommendations overriding project facts, incomplete upstream skill packages, and host copies drifting from the canonical checkout.

## Key Features

1. **Gamedev routing**: One conditional workflow selects only the game-development skills relevant to the current task.
2. **Curated skill set**: Six distributable upstream packages are installed when absent, while `game-designer` is independently authored because its requested snapshot has restricted/unknown distribution metadata.
3. **Safe composition**: Current project source, approved specifications, specialist agents, engine versions, platform constraints, and measured evidence override generic defaults.
4. **Traceable vendoring**: Licenses, source commits, bundled assets, and local adaptations remain visible and verifiable.

## Business Objectives

- Reduce repeated discovery and prompting for common game-development disciplines.
- Make game-project execution more consistent across agent hosts without duplicating canonical content.
- Preserve confidence by preventing stale or universal upstream advice from being treated as project truth.
- Keep future upstream refreshes auditable and intentional.

## Success Metrics

- **Requested coverage**: all seven requested skill names plus one local workflow are discoverable in canonical `skills/`; six are pinned upstream snapshots and `game-designer` is clean-room canonical content.
- **Package validity**: all eight new skill folders pass the selected skill validator and have zero dangling internal references.
- **Routing coverage**: representative design, implementation, 3D, Godot FPS, Godot particles, Godot performance, and UI-motion prompts select the intended route without mutating a game project.
- **Source integrity**: every third-party package records its pinned source, license, and adaptations.
- **Isolation**: no pre-existing destination or unrelated working-tree path is overwritten.

## Product Principles

1. **Current project wins**: live source, project documentation, specialist contracts, and measurements outrank generic skill defaults.
2. **Compose selectively**: load the smallest relevant skill set instead of preloading every game-development discipline.
3. **Canonical once**: shared bodies live only in `coding-cli`; host layers remain pointers or adapters.
4. **Evidence before claims**: engine compatibility, performance, visual quality, and release readiness require project-specific verification.
5. **Attribution survives adaptation**: vendored content stays traceable even when integration fixes are necessary.

## Monitoring & Visibility

- **Dashboard Type**: repository artifacts and command-line validation; no runtime dashboard.
- **Real-time Updates**: not applicable.
- **Key Metrics Displayed**: installed/missing status, validation results, link integrity, source hashes, routing cases, and changed paths.
- **Sharing Capabilities**: tracked skills, PRD/ADR records, validation logs, and reviewable Git diffs.

## Future Vision

### Potential Enhancements

- **Snapshot refresh command**: explicitly review and update pinned upstream revisions.
- **Additional engines/disciplines**: add routes only after a concrete project need and duplicate-authority review.
- **Automated contract tests**: run package and routing validation in CI after the local workflow proves stable.
