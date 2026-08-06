# Requirements: Verify 3D Models And Animation

## Status

Implemented for repository integration · 2026-08-06. Understanding, Requirements, Design, and Task Plan were approved; the user then authorized all implementation tasks. Concrete game visual, runtime, owner, and release gates remain outside this repository task.

## Document Information

- **Feature Name:** Verify 3D Models And Animation
- **Version:** 1.0
- **Date:** 2026-08-06
- **Author:** Batman
- **Stakeholders:** `coding-cli` maintainer, game developers, 3D artists, riggers, animators, technical artists, project specialists, reviewers, and product owners

## Introduction

`coding-cli` already routes material game-development work through a conditional gamedev workflow and project specialists. Its current 3D discipline validates topology, export/import settings, transforms, and general rig/animation presence, while UI motion has separate accessibility guidance. Neither path defines a shared source-reference comparison, skeletal pose/deformation review, deterministic multi-frame evidence schedule, or fail-closed completion state.

This feature adds one locally owned canonical verifier beneath the existing gamedev router. It must make visual evidence comparable, temporal evidence representative, and completion claims honest without replacing project-specific DCC, engine, renderer, asset, accessibility, or owner authority.

## Feature Summary

Provide a canonical `verify-3d-animation` skill that verifies source fidelity, transforms, skeletons, poses, deformation, and visible game animation across multiple recorded frames before completion is claimed.

## Business Value

- Reduce false-positive completion and repeated owner-review cycles.
- Catch hidden anatomical, deformation, transform, occlusion, contact, timing, and loop defects.
- Produce durable, reviewable evidence across game engines and agent hosts.
- Preserve one canonical workflow and prevent host-specific drift.

## Scope

### Included

- 3D model, transform, pivot, hierarchy, rig, skeleton, retargeting, pose, skinning, and deformation review for game-development tasks.
- Every visible game-animation completion claim: skeletal, procedural, weapon, camera, VFX, and game UI motion. Each check applies only when relevant to that animation type.
- Supplied still-image, turnaround, video, animation-clip, pose-sheet, or other source-material comparison.
- Static-pose and multi-frame capture schedules, per-frame evidence, and completion-state reporting.
- Canonical skill, route, entry-trigger, fixture, validator, and README integration.

### Excluded

- Non-game animation unless explicitly routed through `gamedev-workflow` by the current user.
- Live edits to any game project during this repository-only implementation.
- Universal numerical visual tolerances or an engine/DCC-specific capture implementation.
- New MCP servers, hooks, credentials, runtime dependencies, host skill mirrors, or external uploads.
- Rewriting vendored discipline packages without a later explicit approval.

## Phase 2a Discovery Record

Discovery was read-only and ran after Phase 1 approval, before this draft.

- Query `rg -n --hidden -S "skeleton|skeletal|armature|rig|bone|pose|retarget|root motion|foot slid|deformation|first.person|reference image|source material|frame sampling|loop seam|owner visual" agents skills prompts instructions docs .batman -g '!**/.git/**' -g '!.batman/verify-3d-animation/**'` found project-specific animation facts and generic 3D import checks, but no shared source-match or multi-frame completion contract.
- Query `rg -n -S "3d-modeling|motion-design|gamedev-workflow|owner.*acceptance|static.*acceptance|visual.*acceptance|route" skills/gamedev-workflow skills/3d-modeling skills/motion-design AGENTS.md agents/batman.agent.md prompts/execute-task.prompt.md README.md docs/architecture/adr/0009-gamedev-skill-intake-and-routing.md docs/prd/gamedev-skills-workflow.md` confirmed one canonical router, broad owner-acceptance language, a static 3D route, and a distinct UI-motion route.
- Query `rg --files agents skills prompts instructions docs tests .batman | rg "(3d|anim|model|gamedev|visual|skeleton|rig|requirements|prd|adr)"` mapped likely skills, agents, tests, PRD, ADR, and Batman artifacts.
- Query `git log -12 --oneline --all -- skills/gamedev-workflow skills/3d-modeling agents AGENTS.md prompts/execute-task.prompt.md README.md` identified commit `55f46d6` as the current gamedev integration origin and confirmed later commits did not add the requested verifier.
- Exact search `rg -n --hidden -S "verify-3d-animation|source-reference|reference-match|frame_count / 30|source_frame_count|multi-frame animation" . -g '!**/.git/**'` found only this task's approved Understanding artifacts; no existing canonical implementation exists.
- Reads of `agents/godot-dev.agent.md:11-24`, `agents/unreal-dev.agent.md:11-19`, `agents/roblox-dev.agent.md:9-31`, and `agents/byond-dev.agent.md:11-38` confirmed that editor access, animation architecture, bone replication, DMI registries, documentation, and runtime verification differ materially by project. The new skill must defer to them.
- Reads of `hooks/hooks.json:1-26`, `.mcp.json:1-30`, and current `USER_SKILLS_DIR` resolution confirmed no hook/MCP registry change or installed host body is required.
- Mnemo Phase 1 checkpoint `4a075977-da07-4cb1-a17e-29b7fceb908d` (writer `copilot`, 2026-08-06) preserved the approved source-backed finding and sampling rule; current source above revalidated it.

Outcome: discovery found a missing shared verification discipline inside the existing one-router architecture. Requirements therefore add one local canonical skill, conditional composition across relevant visible game-animation routes, explicit evidence gates, and deterministic repository validation while leaving concrete project acceptance outside this repository.

## Glossary

- **Source material**: User-provided or project-authoritative still image, video, pose sheet, turnaround, animation clip, model, or specification used as comparison authority.
- **Reference match**: A supported claim that game output corresponds to source material under recorded comparable conditions; not a synonym for technical asset validity.
- **Comparable capture**: Game/source evidence aligned as far as practical in camera, projection, FOV, aspect, crop, timing, pose, and view purpose, with remaining uncertainty recorded.
- **Transform space**: Named coordinate context such as object, local, world, import, skeleton rest, bone pose, root-motion, or camera space.
- **Normalized source frame count**: Clip duration expressed at 30 FPS for the approved evidence schedule. When authoritative source frame numbering uses another FPS, record both source and normalized frame/time mappings.
- **Scheduled frame**: One of at least `max(2, ceil(source_frame_count / 30))` distributed captures including endpoints.
- **Critical frame**: Additional contact, extreme, passing, transition, blend, loop-seam, or known-risk frame that must be inspected even when not selected by the base schedule.
- **Evidence ledger**: Durable record mapping source/output artifacts, clip/frame/time, view/camera settings, observations, and gate status.
- **Ready for owner review**: Implementation evidence is assembled, but required current-user/product-owner visual acceptance is not yet explicit.

## Requirements

### V3A-REQ-001 — Canonical skill and triggering

**User Story:** As a game developer, I want one discoverable 3D/animation verification skill, so that relevant tasks consistently load the same completion rules.

**Acceptance Criteria (EARS)**

- WHEN the feature is implemented THEN `coding-cli` SHALL provide canonical `skills/verify-3d-animation/SKILL.md` with valid `name` and trigger-rich `description` frontmatter.
- WHEN the skill is finalized THEN the system SHALL provide matching `skills/verify-3d-animation/agents/openai.yaml` metadata generated from the skill.
- WHERE a game-development task concerns a 3D model, transform, rig, skeleton, pose, skinning, deformation, retarget, or visible animation THEN `gamedev-workflow` SHALL load `verify-3d-animation` as part of the smallest applicable skill union.
- IF a task is non-game animation and the current user has not routed it through `gamedev-workflow` THEN the system SHALL NOT implicitly broaden this game-specific skill's authority.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** Approved Understanding; existing `gamedev-workflow`
- **Assumptions:** Skill name remains `verify-3d-animation`.

### V3A-REQ-002 — Selective composition and authority

**User Story:** As a project specialist, I want generic verification to compose with project authority, so that it improves evidence without inventing engine-specific rules.

**Acceptance Criteria (EARS)**

- WHEN `verify-3d-animation` is selected THEN the router SHALL also select relevant existing disciplines and the matching project specialist without loading unrelated skills.
- WHERE mesh/topology/export work is present THEN the router SHALL compose `3d-modeling` with `verify-3d-animation`.
- WHERE game UI motion is present THEN the router SHALL compose `motion-design` with `verify-3d-animation` and preserve reduced-motion/accessibility gates.
- WHERE VFX animation is present THEN the router SHALL compose the applicable VFX discipline with `verify-3d-animation` and preserve renderer/effect-budget gates.
- IF a generic instruction conflicts with the current user decision, project source/specification, specialist contract, exact engine/DCC/renderer version, or project testable invariant THEN the higher authority SHALL win and the conflict SHALL be reported.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** V3A-REQ-001; ADR 0009
- **Assumptions:** Existing specialist descriptions remain project authority.

### V3A-REQ-003 — Source-material intake and provenance

**User Story:** As a reviewer, I want supplied source material inspected and identified, so that match claims are based on the actual reference rather than memory or assumption.

**Acceptance Criteria (EARS)**

- WHEN source material is supplied or already authorized in the active project THEN the verifier SHALL open or inspect it before making pose, transform, position, silhouette, deformation, timing, or match claims.
- WHEN source material is inspected THEN the verifier SHALL record its durable identifier/path, relevant frame/time/view, intended authority, and any ambiguity.
- IF multiple source materials conflict THEN the verifier SHALL present the conflict and SHALL NOT choose a winner without current user/project authority.
- IF supplied source material is missing, inaccessible, corrupt, or not viewable with authorized tools THEN the reference-match gate SHALL be `blocked` and the verifier SHALL NOT claim a match.
- IF no source material exists THEN the verifier SHALL label reference matching `not applicable` or `not provided` while continuing separately authorized technical and internal-consistency checks.
- IF generated imagery is available but the user has not declared it authoritative THEN the verifier SHALL NOT silently substitute it for supplied/project source material.

**Additional Details**

- **Priority:** Critical
- **Complexity:** Medium
- **Dependencies:** V3A-REQ-001
- **Assumptions:** Project authorization controls access to proprietary references.

### V3A-REQ-004 — Comparable source and game captures

**User Story:** As a technical artist, I want source and game captures made comparable before judgment, so that camera or projection differences are not misdiagnosed as model defects.

**Acceptance Criteria (EARS)**

- WHEN a reference comparison is required THEN the verifier SHALL record or align camera position/orientation, projection type, FOV or focal-length equivalent, aspect ratio, crop, resolution, subject transform, animation time/frame, and relevant lighting/renderer differences as far as the available source permits.
- WHERE the result is viewed during gameplay THEN the verifier SHALL include the actual gameplay camera/FOV/aspect and SHALL NOT rely solely on a DCC/editor beauty view.
- IF the gameplay view hides the cause of a defect THEN the verifier SHALL add diagnostic views without replacing the gameplay-view acceptance evidence.
- IF exact alignment is impossible THEN the verifier SHALL record the mismatch and uncertainty and SHALL avoid unsupported pixel-perfect claims.
- WHEN overlays, blinking comparisons, landmarks, or image differences are used THEN the verifier SHALL establish comparable alignment before treating the comparison as evidence.

**Additional Details**

- **Priority:** Critical
- **Complexity:** High
- **Dependencies:** V3A-REQ-003
- **Assumptions:** Exact source camera metadata may be unavailable.

### V3A-REQ-005 — Transform, hierarchy, and skeleton integrity

**User Story:** As a rigger, I want every relevant transform space and skeleton state named and checked, so that visible offsets are diagnosed at their true source.

**Acceptance Criteria (EARS)**

- WHEN work changes a 3D model, rig, pose, retarget, or animation THEN the verifier SHALL identify applicable object, local, world, import, skeleton-rest, bone-pose, root-motion, and camera-space transforms.
- WHEN transform integrity is reviewed THEN the verifier SHALL check units, axes/handedness, origin/pivot, applied transforms, parent hierarchy, bind/rest state, bone orientation/roll, root placement, negative/non-uniform scale, retarget assumptions, and import settings where applicable.
- IF an imported skinned mesh or project contract requires bind/rest identity THEN the verifier SHALL verify that invariant separately from authored bone/animation motion.
- IF a visible discrepancy could arise from more than one transform layer THEN the verifier SHALL isolate or report the ambiguous layers before changing geometry blindly.
- WHERE a project specialist defines a different transform/import contract THEN that contract SHALL override generic examples.

**Additional Details**

- **Priority:** Critical
- **Complexity:** High
- **Dependencies:** V3A-REQ-002, V3A-REQ-004
- **Assumptions:** Project tools expose enough transform state for the authorized review.

### V3A-REQ-006 — Pose, silhouette, anatomy, and gameplay readability

**User Story:** As a player-facing reviewer, I want requested poses to preserve anatomy and readable silhouettes, so that matching hand/weapon targets does not introduce hidden or implausible limbs.

**Acceptance Criteria (EARS)**

- WHEN a requested pose has source material THEN the verifier SHALL compare visible landmarks, proportions, position, orientation, balance, silhouette, contacts, and relevant negative space against the source.
- WHEN a pose is reviewed THEN the verifier SHALL inspect it from the actual gameplay view and from sufficient diagnostic angles to reveal occluded joints.
- WHERE a first-person view is involved THEN the verifier SHALL check grip/contact placement, hand chirality, wrist angle, forearm/elbow/biceps visibility, shoulder chain, weapon/body clipping, and screen-edge/camera occlusion.
- IF moving a hand closer to the body or target hides the elbow/biceps chain, collapses a limb, creates an implausible bend, or harms the intended silhouette THEN the pose gate SHALL fail even if the hand reaches its target.
- IF a requested reference pose cannot be matched without violating project anatomy, rig limits, gameplay readability, or collision constraints THEN the verifier SHALL report the conflict and request an authoritative trade-off rather than silently deforming the model.

**Additional Details**

- **Priority:** Critical
- **Complexity:** High
- **Dependencies:** V3A-REQ-004, V3A-REQ-005
- **Assumptions:** Stylized anatomy follows the supplied/project style rather than a universal human proportion model.

### V3A-REQ-007 — Skinning and deformation quality

**User Story:** As a technical artist, I want deformations inspected at stressed joints and transitions, so that the mesh remains consistent throughout the required motion.

**Acceptance Criteria (EARS)**

- WHEN a skinned or deforming model is reviewed THEN the verifier SHALL inspect joint volume, edge flow behavior, weight gradients, twist distribution, normals/tangents, mesh collapse, candy-wrapper artifacts, stretching, clipping, self-intersection, and discontinuities where applicable.
- WHERE shoulders, elbows, wrists, hips, knees, ankles, neck, fingers, or other high-risk joints materially bend or twist THEN the verifier SHALL include relevant stressed frames/views in the evidence.
- IF a deformation defect is visible in any required gameplay or diagnostic capture THEN the applicable pose/frame gate SHALL fail.
- IF topology, weights, skeleton placement, animation, or import settings could each cause the defect THEN the verifier SHALL record the likely layers and SHALL not claim a root cause without evidence.

**Additional Details**

- **Priority:** Critical
- **Complexity:** High
- **Dependencies:** V3A-REQ-005, V3A-REQ-006
- **Assumptions:** Static rigid assets may mark skinning checks not applicable.

### V3A-REQ-008 — Deterministic animation sampling

**User Story:** As an animation reviewer, I want a deterministic multi-frame schedule, so that clips are not approved from one favorable still.

**Acceptance Criteria (EARS)**

- WHEN visible animation is part of the task THEN the verifier SHALL capture more than one frame.
- WHEN clip duration/frame metadata is available THEN the verifier SHALL express the clip at 30 FPS, calculate at least `max(2, ceil(source_frame_count / 30))` scheduled captures, distribute them across the clip, and include both endpoints.
- WHERE authoritative source frame numbering uses a different FPS THEN the verifier SHALL record source-frame/time and normalized 30-FPS mappings.
- WHEN contacts, extremes, passing positions, transitions, blends, loop boundaries, or known-risk moments are not already scheduled THEN the verifier SHALL add them as critical frames.
- IF the same frame is selected by multiple rules THEN the verifier MAY deduplicate the capture but SHALL retain every reason it is critical and SHALL NOT reduce the base minimum.
- IF frame count or duration cannot be determined THEN the animation-evidence gate SHALL be `blocked` until an authoritative schedule can be established.

**Additional Details**

- **Priority:** Critical
- **Complexity:** Medium
- **Dependencies:** User-approved Phase 1 sampling decision
- **Assumptions:** “Length / 30” means a 30-FPS-normalized evidence budget, not permission to inspect fewer than two frames.

### V3A-REQ-009 — Per-frame and temporal verification

**User Story:** As an animator, I want every captured frame and the motion between them assessed, so that temporal defects cannot hide between representative poses.

**Acceptance Criteria (EARS)**

- WHEN a scheduled or critical frame is captured THEN the verifier SHALL assign that frame an individual result and observation.
- WHEN animation is reviewed THEN the verifier SHALL check applicable pose fidelity, silhouette, contacts, foot/hand sliding, arcs, spacing, timing, root motion/drift, penetrations, clipping, deformation continuity, popping, camera/weapon occlusion, and visual readability.
- WHERE a loop exists THEN the verifier SHALL compare the loop boundary and SHALL check seam continuity in pose, transform, velocity, contacts, and visible deformation.
- WHERE state transitions or blends exist THEN the verifier SHALL inspect transition entry, blend interior, and exit frames for discontinuity or invalid overlap.
- IF any required critical frame fails THEN the entire clip SHALL remain failed or pending regardless of favorable frames elsewhere.
- IF evidence only contains isolated stills and cannot establish an applicable temporal property THEN that property SHALL remain unverified rather than passed.

**Additional Details**

- **Priority:** Critical
- **Complexity:** High
- **Dependencies:** V3A-REQ-006, V3A-REQ-007, V3A-REQ-008
- **Assumptions:** The active project determines the capture/playback mechanism.

### V3A-REQ-010 — Evidence ledger and durable artifacts

**User Story:** As a reviewer, I want a traceable evidence ledger, so that each pass/fail claim can be checked against its source and game artifact.

**Acceptance Criteria (EARS)**

- WHEN verification begins THEN the verifier SHALL define an evidence location authorized by the active project or task.
- WHEN a frame/view is reviewed THEN the ledger SHALL record clip/asset, source frame/time, normalized position, capture reason, camera/view settings, source artifact, game artifact, observation, and status.
- WHEN a gate is not applicable, blocked, failed, pending, or passed THEN the ledger SHALL record that state and its reason.
- IF a source/output artifact cannot be retained due to privacy, size, format, or project policy THEN the ledger SHALL record the authorized observation method without embedding restricted content.
- IF an exact number, path, frame, or transform value is load-bearing THEN the verifier SHALL obtain it from current source/tool evidence rather than infer it from a compressed or visually transcribed representation.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** V3A-REQ-003 through V3A-REQ-009
- **Assumptions:** Exact evidence-file layout is selected during Design or by the active project.

### V3A-REQ-011 — Fail-closed completion and owner acceptance

**User Story:** As a product owner, I want incomplete visual gates reported honestly, so that “done” means the requested result was actually reviewed.

**Acceptance Criteria (EARS)**

- WHEN reporting 3D/animation work THEN the verifier SHALL separate repository/static, DCC/export, engine import, runtime/windowed, reference-match, per-frame animation, accessibility, owner, and release status.
- IF any applicable gate is failed, blocked, unverified, or pending THEN the verifier SHALL NOT mark overall work complete.
- IF the runtime/editor/capture surface is unavailable THEN runtime and visual gates SHALL remain blocked even when source tests pass.
- WHEN visible output has implementation evidence but current-user/product-owner acceptance is required and absent THEN the verifier SHALL report `ready for owner review`, not `completed`.
- WHEN the current user provides visual feedback THEN the verifier SHALL treat it as authoritative for the reviewed output, preserve accepted landmarks, and iterate only the rejected dimensions unless the user broadens scope.
- IF one required critical frame fails THEN the clip and overall visual completion SHALL remain failed or pending until corrected and reverified.
- WHEN all applicable objective gates pass and required current-user/product-owner acceptance is explicit THEN the verifier MAY report completion while still separating any unrun release/platform gates.

**Additional Details**

- **Priority:** Critical
- **Complexity:** Medium
- **Dependencies:** All evidence requirements
- **Assumptions:** Owner acceptance may be delegated only by an explicit current user/project decision.

### V3A-REQ-012 — Workflow and documentation wiring

**User Story:** As a Batman user, I want plain-language 3D and animation requests routed reliably, so that the verifier is not missed outside direct skill invocation.

**Acceptance Criteria (EARS)**

- WHEN the feature is implemented THEN `skills/gamedev-workflow/SKILL.md` SHALL describe explicit 3D model/rig/pose/animation routes and completion gates without duplicating the verifier body.
- WHEN routing fixtures are updated THEN they SHALL cover at least static source-driven 3D matching, first-person skeletal posing/occlusion, multi-frame skeletal/procedural animation, visible VFX animation, and game UI motion.
- WHEN thin entry surfaces are updated THEN `AGENTS.md`, `agents/batman.agent.md`, and `prompts/execute-task.prompt.md` SHALL explicitly include 3D models, rigs/poses, and visible game animation while retaining exactly one pointer to `skills/gamedev-workflow/SKILL.md` per file.
- WHEN repository discovery documentation is updated THEN `README.md` SHALL name the verifier discipline without copying its procedure.
- IF BYOND or another project-specific route is selected THEN its existing documentation, compile/runtime, asset-registry, and verification requirements SHALL continue to apply.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** V3A-REQ-001, V3A-REQ-002
- **Assumptions:** Existing three thin entry surfaces remain sufficient for host discovery.

### V3A-REQ-013 — Deterministic integration validation

**User Story:** As a `coding-cli` maintainer, I want deterministic integration checks, so that the new skill remains canonical, routed, and resistant to regression.

**Acceptance Criteria (EARS)**

- WHEN implementation finishes THEN `quick_validate.py` SHALL pass for `skills/verify-3d-animation`.
- WHEN `validate_integration.py` runs THEN it SHALL recognize `verify-3d-animation` as a locally owned canonical skill and SHALL NOT treat it as a vendored package requiring `UPSTREAM.json`.
- WHEN route fixtures run THEN expected routes and gate sets SHALL match the representative 3D/animation cases.
- WHEN verifier-content checks run THEN they SHALL prove presence of source inspection, comparable-capture, transform/skeleton, pose/deformation, first-person occlusion, approved sampling, critical-frame, per-frame, fail-closed, and separated-status contracts without relying only on prose review.
- WHEN host duplicate checks run THEN no same-name skill body SHALL exist under `~/.codex/skills`, `~/.agents/skills`, or `~/.claude/skills` outside canonical resolution.
- WHEN the full repository validation runs THEN JSON parsing, Markdown links, pointer integrity, idempotence, existing vendored provenance/license checks, BYOND route resolution, and `git diff --check` SHALL pass.
- IF a repository test passes without live game evidence THEN final reporting SHALL label only repository integration green.

**Additional Details**

- **Priority:** High
- **Complexity:** Medium
- **Dependencies:** V3A-REQ-001, V3A-REQ-012
- **Assumptions:** Existing validator remains the integration owner.

### V3A-REQ-014 — Privacy, safety, and scope containment

**User Story:** As a project owner, I want references and captures handled safely, so that verification does not leak assets or broaden agent authority.

**Acceptance Criteria (EARS)**

- WHEN source material or captures are private THEN the verifier SHALL keep them within current authorized project/tool boundaries.
- IF external upload, image generation, or network transfer would be useful but is not explicitly authorized THEN the verifier SHALL not perform it.
- WHEN recording evidence or memory THEN the verifier SHALL exclude credentials, secrets, unrelated project data, and proprietary source bytes not authorized for storage.
- WHEN implementing this repository feature THEN the system SHALL NOT add a new MCP server, hook, credential, sandbox exception, runtime service, or copied host skill body.
- WHILE unrelated user changes exist THEN implementation and validation SHALL preserve them and SHALL avoid reset, stash, broad stage, or destructive cleanup.

**Additional Details**

- **Priority:** High
- **Complexity:** Low
- **Dependencies:** Existing generic-entry and repository safety rules
- **Assumptions:** Current tool authorization is sufficient for repository work.

## Non-Functional Requirements

### Reliability

- WHEN the same clip metadata and critical-frame set are supplied THEN the verifier SHALL produce the same minimum sampling schedule.
- IF evidence is missing or contradictory THEN the verifier SHALL fail closed rather than infer a pass.
- WHEN a correction changes a sampled or adjacent risk region THEN the verifier SHALL recapture and reverify affected scheduled/critical frames.

### Compatibility

- WHERE an active project uses Godot, Unreal, Roblox, BYOND, a custom engine, or another DCC/engine stack THEN the generic verifier SHALL defer concrete commands and runtime contracts to that project's source and specialist.
- IF no compatible capture/view tool is available THEN the verifier SHALL report the limitation without fabricating evidence.

### Performance

- WHEN determining evidence workload THEN the verifier SHALL scale the base schedule from the approved formula and SHALL add all critical frames without silently imposing a smaller convenience cap.
- IF the evidence workload is impractical THEN the verifier SHALL request an explicit scope/sampling decision and SHALL keep completion pending.

### Usability and accessibility

- WHEN presenting evidence THEN the verifier SHALL use stable frame/view labels and concise pass/fail reasons that a reviewer can trace.
- WHERE UI motion or accessibility-sensitive VFX is involved THEN existing reduced-motion/reduced-effects and semantic-state requirements SHALL remain active.

### Maintainability

- WHEN a rule is updated THEN one canonical owner SHALL contain its detailed body: universal workflow in `generic-entry`, game composition in `gamedev-workflow`, verification procedure in `verify-3d-animation`, and project specifics in specialists/source.
- IF Design finds no new hard-to-reverse, surprising trade-off beyond accepted ADR 0009 THEN the feature SHALL NOT create an unnecessary ADR.

## Constraints And Assumptions

### Technical Constraints

- The skill must remain engine/DCC neutral.
- Camera/reference metadata may be incomplete; uncertainty must be explicit.
- Repository tests cannot prove concrete visual fidelity or owner acceptance.
- Vendored discipline bodies and their license/provenance records remain unchanged unless separately approved.

### Business Constraints

- Evidence quality takes priority over premature completion speed.
- Current user visual feedback is authoritative for the reviewed result.
- No commit, push, PR, or broad staging occurs without a separate user request.

### Assumptions Proposed For Approval

- “Animation” includes every visible game-animation completion claim—skeletal, procedural, weapon/camera, VFX, and game UI motion—while irrelevant anatomy/skeleton checks are marked not applicable.
- `source_frame_count` means clip duration expressed at 30 FPS for the evidence budget; authoritative source frame numbers at another FPS are recorded alongside normalized mappings.
- Visible work remains `ready for owner review` until the current user/product owner explicitly accepts it, unless the user explicitly delegates acceptance to an objective project gate.
- The new skill is locally authored and needs no upstream provenance manifest.
- Existing ADR 0009 covers the one-router/canonical-only architecture unless Phase 3 exposes a genuinely new ADR-worthy trade-off.

## Success Criteria

### Definition Of Done

- V3A-REQ-001 through V3A-REQ-014 are implemented and traced to Design and Tasks.
- Skill, route, fixture, pointer, validator, and documentation changes pass repository checks.
- No host mirror, MCP/hook change, provenance regression, secret, or unrelated-work mutation exists.
- Final report explicitly states that repository integration does not validate any concrete game's visuals.

### Acceptance Metrics

- 100% of supplied-reference cases require source inspection or block match claims.
- 100% of animation cases schedule more than one frame and satisfy the approved minimum plus critical frames.
- 100% of captured frames have individual evidence results.
- 100% of failing/blocked/pending applicable gates prevent overall completion.
- Representative routing covers static 3D, first-person pose, skeletal/procedural animation, VFX, UI motion, and specialist-conflict cases.
- All deterministic structural/integration checks pass with zero host mirrors and zero unexplained vendored drift.

## Requirement Traceability Seed

| Concern | Requirements | Evidence Target |
| --- | --- | --- |
| Canonical skill and routing | V3A-REQ-001, V3A-REQ-002, V3A-REQ-012 | Skill metadata, router, thin pointers, fixtures |
| Source and comparable captures | V3A-REQ-003, V3A-REQ-004 | Source/output ledger and alignment record |
| Transforms, pose, and deformation | V3A-REQ-005, V3A-REQ-006, V3A-REQ-007 | Gameplay plus diagnostic captures |
| Sampling and temporal quality | V3A-REQ-008, V3A-REQ-009 | Deterministic schedule and per-frame results |
| Honest completion | V3A-REQ-010, V3A-REQ-011 | Separated gate/status report and owner decision |
| Integration and safety | V3A-REQ-013, V3A-REQ-014 | Validators, no mirrors, diff review, no infra change |

## Requirements Review Checklist

### Completeness

- All user stories name roles, desired capability, and benefit.
- Source-present, source-absent, conflicting-source, missing-runtime, short-clip, transition, loop, first-person, UI/VFX, and failed-frame cases are covered.
- Repository integration and active-game acceptance remain separate.

### Quality

- Acceptance criteria use EARS keywords and `SHALL`.
- Requirements define observable outcomes without choosing engine-specific implementation commands.
- Terms are defined in the feature glossary.

### Traceability

- Stable `V3A-REQ-*` identifiers seed Design and Task Planning.
- Existing ADR 0009 and approved Understanding constrain later architecture.
- Phase 2a discovery queries and memory provenance are recorded.
