# PRD: Gamedev skills workflow

Status: accepted · 2026-08-01

## Problem

`coding-cli` has project-specific game specialists and conditional BYOND guidance, but no general workflow that composes game design, implementation, 3D, Godot FPS, particles, performance, and UI-motion skills. The seven requested names are absent. Literal copying is unsafe: one package has missing mandatory references, one is marked restricted/unknown-license, and several packages contain engine/version-specific or universal-sounding defaults that may conflict with active projects.

## Goals

- Add all seven requested skill names only when absent, plus one `gamedev-workflow` router.
- Install six complete upstream snapshots at immutable reviewed commits.
- Author `game-designer` independently from approved capabilities and general domain knowledge; do not copy the excluded restricted snapshot.
- Compose the smallest relevant skill set with current project specialists and existing skills.
- Make project/source/version/measurement authority explicit.
- Preserve licenses, provenance, original hashes, adaptation history, and clean-room evidence.
- Verify static integration without mutating or claiming acceptance for a live game.

## Non-goals

- Installing optional sibling skills referenced upstream.
- Editing generated host copies or configuring game editors/MCPs.
- Copying reference scripts or shaders into active games.
- Automatic upstream updates.
- Proving gameplay, visual, performance, accessibility, owner, or release acceptance.
- Committing, pushing, or broad staging without a separate request.

## Scope

- New canonical router: `skills/gamedev-workflow/`.
- Six vendored packages: `game-developer`, `3d-modeling`, three requested Godot skills, and `motion-design`.
- One clean-room canonical package: `game-designer`.
- Thin conditional pointers in `AGENTS.md`, `agents/batman.agent.md`, and `prompts/execute-task.prompt.md`.
- README discovery note, per-package provenance/license/origin records, validation tooling/evidence, and an accepted architecture record after Design approval.

## Acceptance Criteria

- Exactly eight new canonical skill directories exist; same-name pre-existing destinations are never overwritten.
- All eight skills pass metadata validation and have zero dangling required local paths/relative links.
- Six upstream packages account for every local difference from their pinned snapshots and retain applicable MIT, Apache-2.0, or LGPL-3.0 evidence.
- `game-designer` has an origin/exclusion record and no unexplained exact or meaningful phrase overlap with the excluded snapshot.
- Read-only routing cases cover seven disciplines, a cross-discipline task, and a project-version conflict.
- Entry pointers remain thin; BYOND routing remains intact; no host body mirror is created.
- Path-scoped review and `git diff --check` pass while pre-existing `docs/` and unrelated work remain preserved.
- Final reporting explicitly separates static integration success from unperformed project acceptance.

## References

- Approved requirements: `.batman/gamedev-skills-workflow/spec/requirements.md`
- Understanding: `.batman/gamedev-skills-workflow/steering/understanding.md`
- Constitution: `.batman/gamedev-skills-workflow/steering/constitution.md`
- Proposed architecture record: `docs/architecture/adr/0009-gamedev-skill-intake-and-routing.md`

