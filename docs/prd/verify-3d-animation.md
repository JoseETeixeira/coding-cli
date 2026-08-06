# PRD: Verify 3D models and animation before completion

Status: implemented for repository integration · 2026-08-06. Concrete game, source-match, runtime, owner, and release gates were not exercised.

## Problem

Batman can currently route game work through 3D modeling, UI motion, and engine specialists, but the shared workflow does not require source-aligned pose/transform comparison or multi-frame animation evidence. A technically valid import or one favorable screenshot can therefore hide incorrect pose, transform, anatomy, skin deformation, clipping, occlusion, foot sliding, root drift, popping, or loop seams and lead to a premature completion claim.

## Goals

- Add one canonical `verify-3d-animation` skill for game-development 3D and visible animation verification.
- Require inspection of supplied source material before any reference-match claim.
- Compare source and game output under recorded, comparable camera/projection/timing conditions.
- Validate transform spaces, skeleton/rest/pose state, visible pose, anatomy, deformation, contacts, and gameplay readability.
- Require the user-approved minimum animation-frame schedule plus every critical frame, with an individual result for each capture.
- Fail closed when evidence, runtime access, source access, a critical frame, or required owner acceptance is missing.
- Route the skill through existing canonical gamedev and specialist workflows without creating host mirrors or new infrastructure.

## Non-goals

- Replacing project specialists, DCC/engine documentation, asset specifications, or current user decisions.
- Editing a live game asset, model, rig, animation, or engine as part of this repository-only feature.
- Creating a universal camera, pose, pixel-difference, anatomy, or deformation tolerance.
- Treating generated imagery as authoritative source material unless the user explicitly chooses it.
- Rewriting vendored `3d-modeling` or `motion-design` bodies and provenance.
- Adding an MCP server, hook, credential, runtime dependency, or copied host skill body.
- Claiming any concrete game visual, renderer, animation, owner, or release acceptance from repository tests.

## Scope

- New canonical skill at `skills/verify-3d-animation/` with UI metadata.
- Conditional composition for 3D models, transforms, rigs, skeletons, poses, and all visible game-animation completion claims, including skeletal/procedural motion, weapon/camera animation, VFX, and game UI motion; irrelevant checks remain not applicable.
- Updated game routing, representative fixtures, deterministic integration validation, and thin entry trigger wording.
- README discovery, Batman requirements/design/task artifacts, and this PRD.
- Evidence rules for source intake, aligned captures, frame scheduling, per-frame review, status classification, and owner review.

## Acceptance Criteria

- Supplied source material is opened and recorded before pose, transform, position, silhouette, or animation-match claims.
- Static 3D comparison uses the actual gameplay view plus diagnostic views where needed; camera/FOV/projection/aspect/crop and transform-space assumptions are recorded.
- Animation captures include at least `max(2, ceil(source_frame_count / 30))` distributed frames including endpoints, plus all contact, extreme, transition, loop-seam, and known-risk frames.
- Every captured frame has an individual source/output comparison and status.
- Pose/deformation checks include silhouette, proportions, joint volume, twist, skinning, clipping, self-intersection, contacts, and first-person occlusion; hands may not hide or collapse the elbow/biceps chain merely to reach a target.
- One failed critical frame fails the clip; inaccessible evidence or runtime stays blocked; visual work remains `ready for owner review` until required acceptance is explicit.
- Router fixtures cover static reference matching, first-person skeletal posing, multi-frame animation, and visible UI/VFX animation.
- Skill metadata, routing, content invariants, JSON, links, idempotence, host-mirror protection, thin pointers, and `git diff --check` pass.
- Final reporting separates repository/static, DCC/export, engine import, runtime/windowed, reference-match, animation-frame, accessibility, owner, and release status.

## References

- Approved Understanding: `.batman/verify-3d-animation/steering/understanding.md`
- Requirements draft: `.batman/verify-3d-animation/spec/requirements.md`
- Existing router decision: `docs/architecture/adr/0009-gamedev-skill-intake-and-routing.md`
