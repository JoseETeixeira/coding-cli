# Implementation Plan: Verify 3D Models And Animation

Status: Completed for repository integration · 2026-08-06. The user authorized implementation of all tasks. No concrete game visual, runtime, owner, or release gate was exercised.

## Phase 4a Discovery Record

Discovery was read-only and ran after Design approval, before this plan.

- Re-read the complete approved `requirements.md`, approved `design.md`, and every file under `.batman/verify-3d-animation/steering/`: `understanding.md`, `product.md`, `tech.md`, `structure.md`, and `constitution.md`.
- Query `rg -n "^SKILL_NAMES|^VENDORED_NAMES|^EXPECTED_ROUTES|^POINTER_FILES|^POINTER_TEXT|^def [a-z_]+" skills/gamedev-workflow/scripts/validate_integration.py` confirmed the exact inventory, route, pointer, link, provenance, idempotence, and host-mirror extension points.
- Read current `skills/gamedev-workflow/SKILL.md`, `references/routing-cases.json`, and `agents/openai.yaml`; the router has eight rows and ten fixtures but no model/reference, rig/pose, or multi-frame verifier route.
- Query `rg -n -C 2 "Gamedev|gamedev-workflow|3D production|UI motion" AGENTS.md agents/batman.agent.md prompts/execute-task.prompt.md README.md` confirmed the three existing thin pointers and one README discovery sentence to update.
- Read system Skill Creator scripts and interface rules. `init_skill.py` accepts an absent canonical destination, optional interface overrides, and no required resource directory; `generate_openai_yaml.py` regenerates metadata from the finalized skill; `quick_validate.py` accepts exactly one skill-directory argument and validates frontmatter. It has no `--help` mode, so its source was inspected after the attempted flag was treated as a path.
- Query `rg --files -g 'pyproject.toml' -g 'package.json' -g 'pytest.ini' -g 'tox.ini' -g 'Makefile' -g 'requirements*.txt' -g '*test*.py' -g 'validate*.py'` found no repository-wide test runner governing this customization. The gamedev integration validator is the focused/full owner for this change; unrelated mnemo, compaction, image, and optical test suites are outside the changed dependency graph.
- Ran `python skills/gamedev-workflow/scripts/validate_integration.py --repo-root .`; baseline remains `PASS: gamedev integration (868 checks)`.
- Checked `git status --short`; only `.batman/verify-3d-animation/` and `docs/prd/verify-3d-animation.md` are untracked. `skills/verify-3d-animation/` remains absent and no customization file has changed.
- Revalidated native and mnemo memory against current files. Prior gamedev evidence remains context only: one canonical router, six provenance-checked vendored packages, thin entry pointers, and static acceptance that cannot prove a live game.

Outcome: implement the approved exact diff test-first inside the existing router. Preserve the six vendored packages, specialist bodies, host roots, hooks, MCP configuration, and active games byte-for-byte/out of scope.

## Tasks

- [x] 1. Establish a guarded implementation baseline
  - Re-read current `git status --short`, branch/HEAD, and the approved Requirements/Design immediately before mutation; stop if the target path or approved files have unexpected concurrent changes.
  - Resolve `skills/verify-3d-animation/` and confirm it is absent and contained by canonical `skills/`; if it exists, do not overwrite it and return to the user with the exact conflict.
  - Confirm no same-name body exists under non-canonical `~/.codex/skills`, `~/.agents/skills`, or `~/.claude/skills`.
  - Record the baseline validator result and path-scoped status in `.batman/verify-3d-animation/evidence/validation-summary.md` without copying secrets or proprietary assets.
  - Record protected/out-of-scope paths for later diff comparison: `skills/3d-modeling/`, `skills/motion-design/`, all specialist agent bodies, `hooks/`, `.mcp.json`, and non-canonical host roots.
  - Preserve all unrelated dirty/untracked work; do not reset, stash, broadly stage, commit, push, or clean the workspace.
  - _Requirements: V3A-REQ-013.5, V3A-REQ-013.6, V3A-REQ-014.3, V3A-REQ-014.4, V3A-REQ-014.5_

- [x] 2. Encode the verifier routing and content contract before implementation
  - Update `skills/gamedev-workflow/references/routing-cases.json` with explicit positive, composed, and negative fixtures: static source-driven 3D matching, source-backed first-person pose/occlusion, skeletal loop sampling, visible FPS weapon/camera animation, VFX animation, game UI motion, BYOND visible animation, non-visual gameplay, and non-game animation.
  - Compose `3d-modeling` + `verify-3d-animation` for the 3D model/export route; compose VFX and UI disciplines with the verifier; add verifier-only rig/visible-animation routes; add FPS-animation and BYOND-animation composed routes; keep non-visual gameplay unchanged and make non-game animation expect an empty primary-skill tuple.
  - Preserve existing engine-version, renderer, performance, reduced-effects, reduced-motion, semantic-state, BYOND-RAG, Dream Maker, project-source, and owner-acceptance gates while adding source-inspection, comparable-capture, gameplay-view, transform/skeleton, first-person-occlusion, deformation, 30-FPS-schedule, endpoints, critical-frames, per-frame-results, temporal-continuity, loop-seam, fail-closed, and ready-for-owner-review gates where applicable.
  - Add `verify-3d-animation` to `SKILL_NAMES`; introduce an explicit locally owned set containing `gamedev-workflow`, `game-designer`, and `verify-3d-animation`; derive `VENDORED_NAMES` so only the existing six upstream packages retain provenance/license validation.
  - Extend `EXPECTED_ROUTES` with the exact fixture tuples and change routing validation from truthiness to `expected is not None` so an empty non-game route is asserted rather than skipped.
  - Add stable required-case/gate subsets and `validate_verifier_content()` checks for frontmatter, finalized `agents/openai.yaml`, a less-than-500-line skill, the approved sampling formula, source/comparison/transform/skeleton/pose/deformation/first-person/per-frame/temporal/evidence/completion markers, and explicit thin-pointer trigger markers.
  - Run the integration validator and record a controlled red result. It may fail only because the new skill, router text, and pointer triggers are not implemented yet; any unrelated provenance, link, origin, containment, or baseline regression stops the task.
  - _Requirements: V3A-REQ-001.3, V3A-REQ-001.4, V3A-REQ-002.1, V3A-REQ-002.2, V3A-REQ-002.3, V3A-REQ-002.4, V3A-REQ-008.1, V3A-REQ-008.2, V3A-REQ-008.4, V3A-REQ-009.1, V3A-REQ-009.5, V3A-REQ-012.2, V3A-REQ-012.5, V3A-REQ-013.2, V3A-REQ-013.3, V3A-REQ-013.4_

- [x] 3. Scaffold and author the canonical `verify-3d-animation` skill
  - Use the approved Skill Creator `init_skill.py` workflow only after the missing/contained destination check, with no `scripts`, `references`, `assets`, examples, dependencies, or host copies.
  - Set exact interface values: display name `Verify 3D Animation`, 46-character short description `Verify source fidelity across animation frames`, and the approved one-sentence default prompt containing `$verify-3d-animation`.
  - Replace generated placeholders through `apply_patch` with trigger-rich frontmatter for game 3D models, transforms, rigs, skeletons, poses, skinning/deformation, retargeting, source matching, first-person limbs/weapons, and visible skeletal/procedural/weapon/camera/VFX/UI animation.
  - Define authority and scope: inspect current project/source/specialist contracts; apply checks only when relevant; keep non-game animation out unless explicitly routed; never treat generated imagery as authoritative without a user decision.
  - Define source intake: open supplied/project-authoritative material, record identifier/path/frame/time/view/authority/ambiguity, expose conflicts, block inaccessible source matches, and label absent-reference checks separately.
  - Define comparable capture: record gameplay and source camera position/orientation, projection, FOV/focal length, aspect, crop, resolution, subject transform, clip time/frame, lighting/renderer differences, uncertainty, and diagnostic views without replacing gameplay evidence.
  - Define transform/skeleton checks across object/local/world/import/skeleton-rest/bone-pose/root-motion/camera spaces, including units, axes/handedness, pivot, applied transforms, hierarchy, bind/rest state, bone roll/orientation, root placement, scale, retarget assumptions, import settings, and ambiguous-layer handling.
  - Define pose/silhouette/readability checks, including source landmarks/proportions/position/orientation/balance/contacts/negative space and first-person hand chirality, grip, wrist, forearm, elbow, biceps, shoulder chain, weapon/body clipping, screen edge, camera/FOV, and rejected-axis correction while preserving accepted landmarks.
  - Define skinning/deformation checks for joint volume, edge-flow response, weights, twist, normals/tangents, collapse, candy-wrapper artifacts, stretching, clipping, self-intersection, discontinuities, stressed joints, and evidence-bounded root-cause language.
  - Define full-motion discovery at authored speed plus repeated/slow/scrub review, then the exact endpoint-inclusive `max(2, ceil(source_frame_count / 30))` schedule and additive contact/extreme/passing/transition/blend/IK-FK/retarget/loop/occlusion/deformation/fast-motion/clipping/known-risk frames without a convenience cap.
  - Define individual frame and temporal checks for pose, contacts, sliding, arcs, spacing, timing, velocity, root motion/drift, clipping, deformation continuity, popping, interpolation, blends, transitions, secondary motion, and loop seams; isolated stills cannot pass temporal properties.
  - Define the evidence ledger fields and closed states: authorized evidence location, clip/asset, source/output frame/time/artifacts, normalized position, capture reasons, camera/view settings, checks, observations, observation method, `pass`, `fail`, `blocked`, `not applicable`, `pending`, and `ready for owner review`.
  - Define aggregation: one failed/missing/blocked required frame prevents clip pass; repository/DCC/export/import/runtime/reference/per-frame/temporal/accessibility/owner/release gates remain separate; completion requires all applicable objective gates and explicit required owner acceptance.
  - Regenerate `agents/openai.yaml` from the finalized skill with the exact approved interface overrides, then run `quick_validate.py` on the canonical skill.
  - _Requirements: V3A-REQ-001.1, V3A-REQ-001.2, V3A-REQ-003.1, V3A-REQ-003.2, V3A-REQ-003.3, V3A-REQ-003.4, V3A-REQ-003.5, V3A-REQ-003.6, V3A-REQ-004.1, V3A-REQ-004.2, V3A-REQ-004.3, V3A-REQ-004.4, V3A-REQ-004.5, V3A-REQ-005.1, V3A-REQ-005.2, V3A-REQ-005.3, V3A-REQ-005.4, V3A-REQ-005.5, V3A-REQ-006.1, V3A-REQ-006.2, V3A-REQ-006.3, V3A-REQ-006.4, V3A-REQ-006.5, V3A-REQ-007.1, V3A-REQ-007.2, V3A-REQ-007.3, V3A-REQ-007.4, V3A-REQ-008.1, V3A-REQ-008.2, V3A-REQ-008.3, V3A-REQ-008.4, V3A-REQ-008.5, V3A-REQ-008.6, V3A-REQ-009.1, V3A-REQ-009.2, V3A-REQ-009.3, V3A-REQ-009.4, V3A-REQ-009.5, V3A-REQ-009.6, V3A-REQ-010.1, V3A-REQ-010.2, V3A-REQ-010.3, V3A-REQ-010.4, V3A-REQ-010.5, V3A-REQ-011.1, V3A-REQ-011.2, V3A-REQ-011.3, V3A-REQ-011.4, V3A-REQ-011.5, V3A-REQ-011.6, V3A-REQ-011.7, V3A-REQ-014.1, V3A-REQ-014.2, V3A-REQ-014.3_

- [x] 4. Compose the verifier through `gamedev-workflow`
  - Expand router frontmatter and boundaries with explicit 3D model/transform/rig/skeleton/pose/skinning/deformation/retarget and visible game-animation triggers while preserving exclusions for casual game mentions and unrequested non-game animation.
  - Update the route table so 3D model/export work composes `3d-modeling` + verifier; rig/pose/deformation and visible animation select the verifier; FPS weapon/camera animation adds the matching FPS discipline; VFX and game UI motion retain their disciplines plus the verifier; BYOND visible animation retains `byond-projects` and the BYOND specialist.
  - Add only a concise verifier gate summary: inspect provided source, establish comparable gameplay evidence, use more than one animation frame, verify every scheduled/critical frame and temporal transition, and leave owner acceptance separate.
  - Preserve the authority stack, smallest-union rule, exact engine/version/renderer checks, reduced-motion/reduced-effects requirements, performance boundaries, reference safety, and repository-versus-live acceptance statement.
  - Confirm the router contains selection/gate summaries only and does not duplicate the verifier's detailed formula, evidence schema, anatomy checklist, or engine-specific capture commands.
  - Run the integration validator; after this task, remaining expected failures may concern only the still-unmodified thin entry triggers/README discovery if those checks are already active.
  - _Requirements: V3A-REQ-001.3, V3A-REQ-001.4, V3A-REQ-002.1, V3A-REQ-002.2, V3A-REQ-002.3, V3A-REQ-002.4, V3A-REQ-002.5, V3A-REQ-011.1, V3A-REQ-011.4, V3A-REQ-012.1, V3A-REQ-012.5_

- [x] 5. Wire thin entry discovery and repository documentation
  - In only the existing gamedev sentence in `AGENTS.md`, replace broad `3D production` wording with explicit `3D models/transforms/rigs/poses, visible game animation` triggers while retaining exactly one pointer to `skills/gamedev-workflow/SKILL.md`.
  - Apply the same trigger expansion to the existing single sentences in `agents/batman.agent.md` and `prompts/execute-task.prompt.md`; keep their distinct composition wording and do not name or duplicate the verifier procedure directly.
  - Update the existing README skill summary to name source-aligned model/animation verification inside `gamedev-workflow` without copying its rules.
  - Confirm all three entries still compose with `generic-entry`/execution and the matching specialist, and no host copy or registry edit was introduced.
  - Run exact pointer-count and trigger-marker checks through the integration validator.
  - _Requirements: V3A-REQ-001.3, V3A-REQ-012.1, V3A-REQ-012.3, V3A-REQ-012.4, V3A-REQ-014.4_

- [x] 6. Run focused deterministic validation and fix only in-scope failures
  - Run `quick_validate.py skills/verify-3d-animation` and verify the finalized interface metadata, trigger description, skill name, and fewer-than-500-line contract.
  - Compile-check `validate_integration.py` with Python bytecode redirected to an exact temporary directory outside the workspace; verify and remove only that task-owned temporary path afterward.
  - Parse the changed routing JSON and all integration-owned JSON manifests with current Python tooling; report exact files on failure.
  - Run `python skills/gamedev-workflow/scripts/validate_integration.py --repo-root .` twice; require both passes and stable read-only idempotence behavior.
  - Confirm every required positive/composed/negative case and semantic gate assertion runs, including the empty non-game route and the non-visual gameplay omission.
  - If a check fails, correct only approved paths, rerun the smallest failing check first, then rerun the full integration validator; do not weaken a gate merely to turn it green.
  - _Requirements: V3A-REQ-001.1, V3A-REQ-001.2, V3A-REQ-012.2, V3A-REQ-013.1, V3A-REQ-013.2, V3A-REQ-013.3, V3A-REQ-013.4, V3A-REQ-013.6_

- [x] 7. Verify containment, regressions, and honest acceptance boundaries
  - Run `git diff --check` for tracked changes and an explicit trailing-whitespace/placeholder scan for new untracked task-owned files.
  - Review `git status --short`, `git diff --stat`, and the complete path-scoped diff; verify every change is listed in the approved Design preview or task artifacts.
  - Prove `skills/3d-modeling/`, `skills/motion-design/`, specialist bodies, `hooks/`, `.mcp.json`, and unrelated user paths have no task diff; verify the six existing `UPSTREAM.json`/license checks still pass.
  - Recheck non-canonical host roots for a same-name skill and confirm no MCP server, hook, credential, service, dependency, environment setting, sandbox exception, host reload, or active game mutation occurred.
  - Scan task-owned text for secrets, proprietary source bytes, unsafe upload/network instructions, unsupported engine-specific facts, and accidental generated-image authority.
  - Record exact repository validation results and remaining unrun DCC/import/runtime/reference/per-frame/accessibility/owner/release gates in the task evidence summary; never promote repository green to a live-game pass.
  - _Requirements: V3A-REQ-002.5, V3A-REQ-010.4, V3A-REQ-010.5, V3A-REQ-011.1, V3A-REQ-011.2, V3A-REQ-011.3, V3A-REQ-011.4, V3A-REQ-013.5, V3A-REQ-013.6, V3A-REQ-013.7, V3A-REQ-014.1, V3A-REQ-014.2, V3A-REQ-014.3, V3A-REQ-014.4, V3A-REQ-014.5_

- [x] 8. Perform code review, documentation audit, and final handoff
  - Review the complete implementation against all fourteen requirements, the approved Design, the seven constitution principles, accepted ADR 0009, current code-review instructions, and the exact customization diff preview.
  - Check Python responsibility boundaries, actionable validator failures, closed route vocabularies, empty-route handling, path containment, stable content markers, and alignment between fixtures and implementation.
  - Check skill clarity and progressive disclosure: one canonical owner, no duplicated procedure in router/entry/README, relevant checks may be `not applicable`, and concrete engine/DCC commands remain with specialists.
  - Resolve every review finding within approved scope, rerun focused validation after each material fix, then rerun the full validator and whitespace/diff checks.
  - Finalize `.batman/verify-3d-animation/evidence/validation-summary.md` with commands, exact results, changed paths, preserved paths, limitations, and separated acceptance states; update this task checklist truthfully.
  - Report the canonical skill and wiring as repository-integrated only. State explicitly that no concrete model, source match, animation frames, runtime, owner acceptance, or release gate was exercised in this repository task.
  - Do not commit, push, open a PR, broadly stage, or claim host reload/discovery unless the user separately requests it.
  - _Requirements: V3A-REQ-002.5, V3A-REQ-010.1, V3A-REQ-010.2, V3A-REQ-010.3, V3A-REQ-010.4, V3A-REQ-010.5, V3A-REQ-011.1, V3A-REQ-011.2, V3A-REQ-011.3, V3A-REQ-011.4, V3A-REQ-011.5, V3A-REQ-011.6, V3A-REQ-011.7, V3A-REQ-012.4, V3A-REQ-013.6, V3A-REQ-013.7, V3A-REQ-014.3, V3A-REQ-014.5_
