# 0009 — Gamedev skill intake and routing

Status: accepted · 2026-08-01

## Context

`coding-cli` needs reusable game-design, implementation, 3D, Godot FPS, Godot particles, Godot performance, and UI-motion guidance without creating a second universal workflow or weakening project-specific authority. The requested sources are not uniform: six packages have distributable pinned inputs worth preserving, `3d-modeling` has three impossible mandatory reads, and the requested `game-designer` package is marked `NOASSERTION` / restricted by its package metadata. Literal copying would therefore be incomplete or unsafe, while rewriting every package would discard useful maintained assets and create unnecessary local ownership.

The integration also needs a durable answer to two boundary questions: where generic game guidance sits beneath `generic-entry`, and how future maintainers distinguish upstream bytes from reviewed local adaptations.

## Options considered

1. **Copy all seven requested snapshots literally.** Rejected: it would redistribute restricted/unknown-license `game-designer` content and retain a broken `3d-modeling` workflow.
2. **Rewrite all seven skills locally.** Rejected: it would lose useful upstream references/scripts, expand maintenance ownership, and obscure which guidance came from reviewed sources.
3. **Vendor six pinned, minimally adapted snapshots; independently author `game-designer`; add one selective router and per-package manifests (chosen).** Preserves usable upstream value, respects package-specific distribution constraints, and makes authority plus drift reviewable.
4. **Install separate bodies into each host.** Rejected: it violates canonical-once and recreates cross-host drift.

## Decision

- Keep `generic-entry` as universal workflow owner. Add `skills/gamedev-workflow/` beneath it as conditional owner of game-development discipline selection, authority precedence, compatibility gates, and acceptance boundaries.
- Vendor `game-developer`, `3d-modeling`, `godot-genre-shooter-fps`, `godot-particles`, `godot-performance-optimization`, and `motion-design` from immutable reviewed commits. Preserve complete package trees and applicable license text.
- Record each vendored package in `UPSTREAM.json`: repository, source path, commit, upstream file hashes, license chain, local-only files, and every adaptation. Apply only validator compatibility fixes, safety/optional-link qualification, and the approved self-contained `3d-modeling` repair.
- Author `skills/game-designer/` independently from approved requirements and general game-design knowledge. Do not copy or closely paraphrase the excluded snapshot. Record the exclusion and comparison evidence in `ORIGIN.json`; unexplained exact or meaningful phrase overlap blocks completion.
- Route the smallest applicable skill set. Explicit user decisions, current project source/specifications, matching specialists, actual engine/version/renderer/platform, official documentation, measured workloads, and owner acceptance outrank generic imported guidance.
- Keep canonical entry integration thin. No host mirrors, automatic snapshot updates, imported-example execution, or live game mutation belong to this change.

## Consequences

- Normal skill use works offline and remains deterministic at the reviewed pins.
- Future refreshes must repeat license/tree discovery and account for every delta against the recorded manifests.
- The repository locally owns the clean-room `game-designer` content and router contract, while retaining modification responsibility for the six adapted packages.
- Static validation can prove package, routing, provenance, and pointer integrity. It cannot prove gameplay, renderer, visual, performance, accessibility, owner, or release acceptance for a concrete game.
- Godot guidance degrades to conceptual/reference use when active project compatibility is unknown or conflicts with the imported baseline.

## Rollout and rollback

Create only absent canonical skill destinations, then add three thin entry pointers, one README discovery note, provenance/license records, and task-scoped evidence. Validate before any optional commit.

If rollback is explicitly requested, resolve and remove only task-owned new paths and pointer/note additions after confirming no later user edits. Never reset or stash the workspace, remove pre-existing `docs/` content, or delete this accepted record; supersede it with a later ADR when the decision changes.
