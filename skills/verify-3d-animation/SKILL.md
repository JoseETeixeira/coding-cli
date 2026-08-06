---
name: verify-3d-animation
description: Verify game-development 3D models, transforms, rigs, skeletons, poses, skinning and deformation, retargeting, and visible animation against supplied or project-authoritative source and multi-frame evidence before completion. Use for source or reference matching, first-person arms or weapons, skeletal, procedural, weapon, camera, VFX, or game UI animation, import or bone-space discrepancies, pose readability, deformation, contacts, transitions, and loop seams; compose through gamedev-workflow and the matching project specialist.
---

# Verify 3D Models And Animation

Use this skill as an evidence and completion gate. Keep `generic-entry`, `gamedev-workflow`, current project instructions, and the matching project specialist active.

## Authority And Boundaries

Resolve conflicts in this order:

1. Explicit current user decisions and authorized scope.
2. Current project source, approved specifications/ADRs, and testable invariants.
3. Matching project specialist and its DCC/editor/build/runtime contract.
4. Exact DCC, engine, renderer, camera, platform, and matching official documentation.
5. Inspected source material, current rendered output, measured evidence, and owner feedback.
6. This generic verification procedure.

State conflicts instead of silently choosing a lower authority. Use project tools for concrete transforms, frames, captures, and runtime checks; do not invent engine-specific commands.

Apply only relevant checks. Mark anatomy or skeleton checks `not applicable` for rigid, VFX, camera, or UI work when they genuinely do not apply. Do not use this game-specific procedure for non-game animation unless the current user explicitly routes it through `gamedev-workflow`.

This skill does not authorize edits, editor launches, uploads, image generation, network transfer, asset copying, or wider filesystem/tool access. Keep private source and captures inside authorized project/tool boundaries.

## Verification Workflow

1. Define the exact asset, clip, pose, view, requested match, and completion claim.
2. Inspect source material and record its authority before making a match claim.
3. Establish comparable source and gameplay captures.
4. Inspect relevant transform, hierarchy, skeleton, pose, and deformation layers.
5. For visible animation, discover critical moments and build the deterministic capture schedule.
6. Capture and verify every scheduled and critical frame, then inspect temporal behavior between them.
7. Record an evidence ledger and aggregate gates without promoting unverified layers.
8. Request owner review when required; claim completion only after every applicable gate passes.

## Inspect Source Material

Open and inspect supplied or project-authoritative source material before claiming that pose, transform, position, orientation, scale, silhouette, deformation, or timing matches. Do not rely on memory, filenames, thumbnails, generated approximations, or an earlier agent's description.

Record:

- durable identifier or authorized path;
- whether authority is current user, project, or non-authoritative generated material;
- relevant still, view, source frame/time, frame rate, and intended use;
- ambiguity, occlusion, crop, missing metadata, or conflicting instructions.

If authoritative sources conflict, present the conflict and obtain a current user/project decision. If a supplied source is missing, corrupt, inaccessible, or cannot be viewed with authorized tools, set the reference-match gate to `blocked`; do not claim a match. If no source exists, record `not provided` or `not applicable` and continue only separately authorized technical/internal-consistency checks.

Never substitute generated imagery for supplied/project source unless the current user explicitly declares it authoritative.

## Establish A Comparable Capture

Before visual comparison, align or record as far as available:

- camera position and orientation;
- projection type and FOV or focal-length equivalent;
- aspect ratio, crop, resolution, and screen region;
- subject object/world transform and scale;
- clip, state, frame/time, playback rate, and source-to-output timing map;
- relevant lighting, renderer, material, and post-processing differences.

Always include the actual gameplay camera/FOV/aspect when the result is player-facing. Add front, side, back, orthographic, joint-focused, or wireframe diagnostic views when the gameplay view hides a cause, but never replace gameplay acceptance evidence with a DCC/editor beauty view.

Use overlays, blink comparisons, landmarks, or image differences only after alignment. If exact alignment is impossible, record the mismatch and uncertainty; avoid unsupported pixel-perfect claims.

## Inspect Transforms, Hierarchy, And Skeleton

Name every applicable transform layer before changing geometry blindly: object, local, world, import, skeleton-rest, bone-pose, root-motion, and camera spaces.

Check as applicable:

- units and target scale;
- axes, handedness, and conversion rules;
- origin/pivot and applied object transforms;
- parent hierarchy and inherited transforms;
- bind/rest state separately from authored bone-pose animation;
- bone orientation/roll and root placement;
- negative or non-uniform scale;
- retarget source/target assumptions and constraints;
- root-motion ownership, drift, and extraction;
- importer settings, sampling, and project-specific identity invariants.

If multiple layers could explain an offset, record or isolate each candidate before editing. Let the current project contract override generic bind/import examples.

## Match Pose, Silhouette, And Gameplay Readability

Match the requested pose as closely as the authoritative source, rig limits, anatomy/style, collision, and gameplay readability permit. Compare visible landmarks, proportions, position, orientation, balance, silhouette, contacts, and negative space—not only whether an end effector reaches a target.

Inspect the actual gameplay view plus enough diagnostic angles to expose hidden joints. For first-person arms and weapons, check:

- hand chirality, grip, finger/contact placement, and weapon alignment;
- wrist angle, forearm line, elbow and biceps visibility, and shoulder chain;
- plausible joint bends and preserved limb volume;
- body/weapon clipping, self-intersection, screen-edge loss, and camera/FOV occlusion.

Fail the pose when moving a hand closer to the body or target hides the elbow/biceps chain, collapses the limb, creates an implausible bend, or damages the intended silhouette—even if the hand reaches its target. If the source cannot be matched without violating the project rig, anatomy/style, collision, or readability, expose the trade-off and request an authoritative choice.

Treat current user visual feedback as authoritative for the reviewed output. Preserve accepted landmarks and dimensions while correcting only the rejected pose/transform axis unless the user broadens scope.

## Inspect Skinning And Deformation

Inspect skinning and deformation at neutral and stressed states:

- joint volume and edge-flow response;
- weight gradients and influence discontinuities;
- twist distribution and candy-wrapper artifacts;
- normals/tangents and shading continuity;
- collapse, stretching, clipping, and self-intersection;
- discontinuities across retargets, blends, constraints, or imports.

Add stressed frames/views for materially bending or twisting shoulders, elbows, wrists, hips, knees, ankles, neck, fingers, and project-specific risk areas. Any visible defect in a required gameplay or diagnostic capture fails that pose/frame gate.

Treat topology, weights, skeleton placement, animation, constraints, and import settings as possible cause layers. Do not claim a root cause until current evidence isolates it.

## Discover And Sample Visible Animation

Never accept visible animation from one favorable still. First inspect the complete source and output motion at authored speed, repeat or loop it when applicable, then scrub or use slow playback to discover contacts, extremes, passing positions, transitions, blends, seams, occlusion changes, deformation stresses, clipping, and reported risks.

Build the base schedule:

1. Express clip duration as `source_frame_count` at normalized 30 FPS. Also record authoritative source FPS/frame/time mappings when they differ.
2. Compute `capture_count = max(2, ceil(source_frame_count / 30))`.
3. Distribute those captures over the closed interval, including both endpoints:

   `t_i = clip_start + i * (clip_end - clip_start) / (capture_count - 1)`

4. Map each time to the exact source/project frame convention and record rounding; never silently shift an endpoint.
5. Add every contact, extreme, passing, transition, blend, loop-seam, and known-risk frame not already represented. Also add IK/FK or retarget switches, acceleration reversals, fast motion, occlusion changes, stressed deformation, and clipping risks.

Deduplicate one capture selected by multiple rules only when it represents the same exact time and view. Preserve every capture reason and never reduce the base minimum or impose a convenience cap.

If duration/frame metadata is unavailable, or fewer than two distinct animation times can be evaluated, set animation evidence to `blocked`; do not manufacture duplicate frames.

## Verify Every Captured Frame And Transition

Verify every captured frame individually. Record an observation and status for each scheduled and critical time. Check applicable:

- source pose/landmark/silhouette fidelity;
- contacts and foot/hand sliding;
- transform, root-motion, and camera/weapon drift;
- joint readability, skinning, deformation, penetration, and clipping;
- VFX/UI state, semantic readability, reduced-effects, and reduced-motion state.

Inspect playback and adjacent evidence for arcs, spacing, timing, acceleration, velocity, interpolation, popping, contact stability, blend continuity, root-motion continuity, secondary motion, and visible deformation continuity.

For a loop, compare last-to-first pose, transform, velocity, contacts, and deformation; two good endpoint stills do not prove a clean loop seam. For transitions/blends, inspect entry, blend interior, and exit frames. If isolated stills cannot establish a temporal property, leave that property unverified.

One failed, missing, or blocked required/critical frame prevents the affected pose, clip, and overall visual claim from passing. Never average it away with favorable frames.

## Maintain The Evidence Ledger

Choose an evidence location authorized by the active project/task before verification. For every frame/view, record:

- clip or asset;
- source and output frame/time plus normalized position;
- every capture reason;
- camera/view settings and comparable-capture uncertainty;
- source and game artifact paths, or the authorized observation method when retention is forbidden;
- checks performed, observations, status, and reason.

Use current source/tool evidence for load-bearing paths, frames, times, transforms, FOV, camera values, and exact numbers. Do not infer them from compressed memory or visually transcribed text.

Use the closed states `pass`, `fail`, `blocked`, `not applicable`, `pending`, and `ready for owner review`.

## Aggregate And Report Honestly

Report repository/static, DCC/export, engine import, runtime/windowed, reference-match, per-frame/temporal, accessibility, owner, and release gates separately. A pass in one layer never promotes another layer.

If any applicable gate is failed, blocked, pending, or unverified, do not mark overall work complete. If implementation evidence is assembled but required current-user/product-owner acceptance is absent, report `ready for owner review`, not `completed`.

Claim completion only when all applicable objective gates pass and required owner acceptance is explicit or explicitly delegated. Still name any unrun platform/release gate.

Repository skill lint, routing fixtures, source tests, or headless checks prove only their own layer. They cannot prove a concrete game's model, source match, pose, deformation, animation frames, runtime output, owner acceptance, or release readiness.
