# Product Overview

## Product Purpose

`coding-cli` is the canonical, host-agnostic customization source for Batman agents, skills, prompts, instructions, and shared-memory workflows. This feature strengthens its game-development guidance so visible 3D and animation work is judged from source-aligned, multi-frame evidence before completion is claimed.

## Target Users

- Game developers using Batman across Godot, Unreal, Roblox, BYOND, custom engines, and other game projects.
- 3D artists, technical artists, riggers, and animators who need reliable review criteria.
- Product owners and reviewers who need comparable evidence rather than a favorable screenshot.
- `coding-cli` maintainers who need one canonical skill and deterministic routing tests.

## Key Features

1. **Source-backed comparison**: Reopen supplied reference material and compare it with aligned game output.
2. **3D integrity review**: Inspect transform spaces, skeletons, poses, silhouette, anatomy, skinning, deformation, and occlusion.
3. **Temporal evidence**: Capture an approved minimum frame schedule plus every critical animation frame and verify each capture.
4. **Fail-closed completion**: Separate static, DCC, import, runtime, reference, per-frame, and owner acceptance states.
5. **Selective routing**: Compose with existing game disciplines and project specialists without replacing them.

## Business Objectives

- Reduce false completion claims for visually incorrect 3D models and animations.
- Catch deformation, clipping, pose, transform, and motion defects before owner review or release.
- Make game-development evidence consistent across supported agent hosts and project engines.
- Preserve canonical-once maintenance and avoid host-specific skill drift.

## Success Metrics

- **Reference evidence**: 100% of tasks with supplied source material record a comparable source/output review or an explicit blocked state.
- **Animation evidence**: 100% of visible animation completion claims include more than one frame and satisfy the approved sampling rule.
- **Frame accountability**: 100% of captured frames receive an individual result.
- **Completion honesty**: 0 completion claims promote repository-only checks into game/reference/owner acceptance.
- **Integration health**: Canonical skill validation, route fixtures, host-mirror checks, and `git diff --check` pass.

## Product Principles

1. **Current evidence wins**: Current user decisions, project source, project specialists, engine output, supplied references, and owner feedback outrank generic advice.
2. **Comparable before critical**: Align camera, projection, timing, and transform assumptions before judging visible differences.
3. **Temporal work needs temporal proof**: A single still cannot validate animation.
4. **One failed critical frame matters**: Hidden defects are not averaged away by favorable samples.
5. **State what remains open**: Use `blocked`, `failed`, `not applicable`, and `ready for owner review` instead of premature completion.

## Monitoring & Visibility

- **Dashboard Type**: Task-local evidence ledger and durable artifact paths; no new service or dashboard.
- **Real-time Updates**: Not applicable.
- **Key Metrics Displayed**: Required sample count, captured frames, critical-frame additions, per-frame status, reference alignment, and remaining owner acceptance.
- **Sharing Capabilities**: Source/output captures and evidence summaries stored at project-authorized durable paths.

## Future Vision

The skill can later gain engine-specific capture helpers or landmark/difference tooling, but only after each integration preserves project authority, reference privacy, and honest acceptance boundaries.

### Potential Enhancements

- Engine-specific frame-capture adapters.
- Optional pose-landmark overlays after camera alignment.
- Evidence-ledger templates consumable by project review tooling.
- Automated loop-seam and contact diagnostics that remain subordinate to visual review.
