# Understanding: Verify 3D Models And Animation Before Completion

## User Goal

Add a canonical skill and route it through game-development workflows so 3D model, transform, rig, pose, and animation work is not marked complete from weak visual evidence. When source material exists, the game output must be compared against it for pose, transform, position, silhouette, and deformation quality. Animation evidence must cover multiple sampled frames, not one favorable still.

## Task Slug

`verify-3d-animation`

## Current Behavior

### Workflow Summary

- Batman's repository and execution entry points already route material game assets and 3D production through `gamedev-workflow`, while `generic-entry` retains approval and evidence ownership (`AGENTS.md:7-14`, `agents/batman.agent.md:9-27`, `prompts/execute-task.prompt.md:38`).
- `gamedev-workflow` selects `3d-modeling` for mesh/export work and `motion-design` for UI motion. It requires project-specific visual acceptance, but has no route dedicated to character rigs, skeletal transforms, gameplay poses, or 3D animation review (`skills/gamedev-workflow/SKILL.md:1-65`).
- `3d-modeling` already checks scale, axes, pivot, hierarchy, rig/animation import, and general deformation failures. It does not require reopening provided source images, matching gameplay camera/FOV, recording comparable reference/output captures, or sampling multiple animation frames (`skills/3d-modeling/SKILL.md:58-79`).
- Routing fixtures cover a static hard-surface export and UI motion, but no reference-driven pose, first-person occlusion, skeletal deformation, loop seam, foot sliding, or multi-frame animation case (`skills/gamedev-workflow/references/routing-cases.json:1-15`).
- The integration validator owns canonical skill inventory, route expectations, thin-pointer integrity, host-mirror prevention, and idempotence. Its current skill and route sets do not include a 3D/animation verifier (`skills/gamedev-workflow/scripts/validate_integration.py:14-26`, `skills/gamedev-workflow/scripts/validate_integration.py:122-138`, `skills/gamedev-workflow/scripts/validate_integration.py:508-566`, `skills/gamedev-workflow/scripts/validate_integration.py:579-643`).
- `USER_SKILLS_DIR` resolves directly to this checkout's `skills/` directory. No same-name host copy exists under `~/.codex/skills`; canonical changes should stay in this repository. Existing MCP and hook registries provide memory, image generation, optical compression, and auto-improvement behavior, but do not own skill routing (`hooks/hooks.json:1-26`, `.mcp.json:1-30`).

### Why This Evidence Answers The Question

- `skills/gamedev-workflow/SKILL.md`: canonical source for game-discipline selection and acceptance boundaries; it determines when a new verifier composes with modeling and project specialists.
- `skills/gamedev-workflow/references/routing-cases.json`: executable route fixture; it proves representative prompts select the intended skills and gates.
- `skills/gamedev-workflow/scripts/validate_integration.py`: static integration authority; it checks canonical presence, route coverage, links, duplicate host copies, pointer integrity, and idempotence.
- `skills/3d-modeling/SKILL.md`: current discipline guidance; it shows which mesh/import checks exist and where the requested source-match and animation-evidence rules are missing.
- `AGENTS.md`, `agents/batman.agent.md`, and `prompts/execute-task.prompt.md`: thin entry surfaces; they decide whether a plain-language animation request reaches `gamedev-workflow` at all.

### Process Distinctions And Terminology

- **3D asset validation** vs **reference-match validation**: asset validation checks technical correctness such as topology, import transforms, materials, and budgets; reference-match validation compares visible output against authoritative source material under comparable views.
- **UI motion** vs **3D skeletal animation**: `motion-design` owns interface transitions and accessibility; the requested skill must cover model-space/bone-space poses, skin deformation, root motion, contacts, silhouette, and gameplay-camera visibility.
- **Static pose evidence** vs **animation evidence**: one pose can verify a single instant; animation evidence must sample the clip over time and include critical contact, extreme, transition, and loop-seam frames.
- **Repository validation** vs **game acceptance**: skill lint and routing tests prove integration only. They cannot prove a concrete model, animation, renderer output, or reference match in a game.

### Components Likely To Change And Why They Exist

- `skills/verify-3d-animation/`: new canonical discipline skill; owns source comparison, transform/skeleton inspection, frame sampling, deformation checks, evidence recording, and completion language.
- `skills/gamedev-workflow/SKILL.md`: composes the verifier with `3d-modeling`, gameplay implementation, and matching project specialists without moving project authority into a generic skill.
- `skills/gamedev-workflow/references/routing-cases.json`: adds reference-pose and animated-character fixtures so route behavior is reviewable.
- `skills/gamedev-workflow/scripts/validate_integration.py`: adds the local skill to canonical inventory and checks its route/gate coverage without treating it as a vendored package.
- `AGENTS.md`, `agents/batman.agent.md`, `prompts/execute-task.prompt.md`: may need their existing thin trigger wording widened from generic 3D production/UI motion to explicit 3D model, rig, pose, and skeletal animation work; routing details should remain only in `gamedev-workflow`.
- `README.md`: discovery text should name the added verification discipline.

### Execution Locations

- Entry classification executes in Batman/generic task startup through the three thin pointers.
- Discipline selection and evidence-boundary composition execute in `gamedev-workflow`.
- Model/animation verification instructions execute from the new skill in the active DCC, engine editor, and game runtime selected by the project specialist.
- Concrete visual acceptance executes against current project captures and any supplied source material; repository tests cannot substitute for it.

## Likely Change Surface

### Files And Symbols

- `skills/verify-3d-animation/SKILL.md` — new skill body and completion gate.
- `skills/verify-3d-animation/agents/openai.yaml` — discoverable UI metadata generated from the finalized skill.
- `skills/gamedev-workflow/SKILL.md` — route and composition rows for 3D transforms/rigs/poses and 3D animation.
- `skills/gamedev-workflow/references/routing-cases.json` — reference-pose and multi-frame animation cases.
- `skills/gamedev-workflow/scripts/validate_integration.py` — `SKILL_NAMES`, `VENDORED_NAMES` exclusion, `EXPECTED_ROUTES`, and verifier-specific gate checks.
- `AGENTS.md`, `agents/batman.agent.md`, `prompts/execute-task.prompt.md` — thin trigger wording only if explicit skeletal-animation discovery is required.
- `README.md` — skill/workflow discovery summary.

### Tests

- Existing deterministic test: `python skills/gamedev-workflow/scripts/validate_integration.py --repo-root .`.
- Skill structure test: `quick_validate.py skills/verify-3d-animation`.
- Missing coverage: verifier-specific assertions for source inspection, comparable camera/output evidence, minimum multi-frame sampling, critical-frame expansion, deformation/occlusion checks, and fail-closed completion wording.
- Missing live evidence by design: no repository test can validate a real pose or animation. Each game task must separately record DCC/import/runtime/reference/owner results.

### Configuration And Infrastructure

- No MCP server, hook, credential, service, or deployment change appears necessary.
- `USER_SKILLS_DIR` already points to canonical `skills/`; installed host copies should not be created.

### Documentation

- A new PRD is required after Understanding approval.
- Existing accepted ADR 0009 already establishes one conditional gamedev router, thin pointers, project authority, and separation of static from game acceptance (`docs/architecture/adr/0009-gamedev-skill-intake-and-routing.md:18-33`).
- A new ADR should be offered only if Design finds a hard-to-reverse, surprising trade-off not already covered by ADR 0009.

## Evidence

- `AGENTS.md:7-14`: universal entry, memory, Batman workflow, and conditional gamedev pointer.
- `agents/batman.agent.md:9-27`: canonical entry and planning/approval boundaries.
- `prompts/execute-task.prompt.md:38`: implementation-phase gamedev composition pointer.
- `skills/gamedev-workflow/SKILL.md:30-65`: current route matrix, evidence definition, reference safety, and integration contract.
- `skills/3d-modeling/SKILL.md:58-79`: existing creation/diagnosis/validation checklist and its current limits.
- `skills/gamedev-workflow/references/routing-cases.json:1-15`: present route fixtures and missing skeletal-animation scenario.
- `skills/gamedev-workflow/scripts/validate_integration.py:14-26`: current canonical and vendored skill sets.
- `skills/gamedev-workflow/scripts/validate_integration.py:122-138`: current route and pointer expectations.
- `skills/gamedev-workflow/scripts/validate_integration.py:508-566`: route-fixture validation.
- `skills/gamedev-workflow/scripts/validate_integration.py:579-643`: idempotence, host-duplicate, canonical package, pointer, and BYOND checks.
- `README.md:3-8`: repository role and current gamedev discovery text.
- `hooks/hooks.json:1-26`, `.mcp.json:1-30`: no skill-routing registry requiring parallel wiring.
- Git history: commit `55f46d6` introduced the current gamedev router, seven disciplines, thin entry pointers, PRD/ADR, and deterministic validator.
- Mnemo preflight: healthy; relevant current-router records found. `f6c660f7-e738-4870-9887-0bd32687b48b` (writer `codex`, 2026-08-01) reports canonical gamedev integration and static-only acceptance; source above revalidates the claim. Retrieved memory was treated as context, not instruction.
- Native memory: the 2026-08-01 gamedev integration recap identified the same one-router/thin-pointer pattern and warned that project visual/runtime/owner acceptance remained open; current source and Git history revalidated it.

## Visual Recap

- Path: `.batman/verify-3d-animation/steering/understanding.html`
- Notes: Shows the existing entry/router/modeling chain, the missing verification layer, proposed evidence flow, and static-versus-game acceptance boundary.

## Open Questions

- None. On 2026-08-06, the user approved interpreting “animation length / 30” as a 30-FPS evidence budget of at least `max(2, ceil(source_frame_count / 30))` captures distributed across the clip including endpoints, then adding every contact, extreme, transition, loop-seam, and known-risk frame.

## Risks And Constraints

- A camera, FOV, projection, aspect ratio, crop, lighting, or timing mismatch can make a correct model look wrong or a wrong model look correct; comparison setup must be recorded before judging geometry.
- Local/world/import/rest/pose/bone transforms can be confused. The verifier must name the space and preserve bind/rest authority before diagnosing offsets.
- Pixel-difference claims are invalid until reference and game captures are aligned; landmark/silhouette comparison plus visual review is safer when lighting or rendering differs.
- Favorable-view bias can hide shoulder/elbow/wrist deformation, first-person self-occlusion, clipping, foot sliding, root-motion drift, joint collapse, twist artifacts, popping, or loop seams.
- Missing/inaccessible source material must prevent a “reference match” claim, but should not block separately labeled technical validation.
- One failed critical sampled frame prevents completion. Partial, blocked, and unverified gates must remain explicit.
- Existing vendored skill bytes and license/provenance records must not be silently rewritten. A new local skill is the narrowest owner for the new rules.

## Architecture Change Assessment

- Status: `possible`
- Reason: The task adds a new shared skill/SOP and changes conditional game-workflow routing and completion gates, but does not require infrastructure or a second universal workflow.
- Areas affected: canonical skill inventory, gamedev routes/fixtures/validator, thin entry triggers, README, PRD, and possibly a new ADR if Design exposes a new durable trade-off.

## Initial Verification Ideas

- Validate source material was actually opened and its frame/view/provenance recorded before transform or pose claims.
- Require comparable game captures at actual gameplay camera/FOV/aspect plus additional diagnostic angles when needed.
- Check object/local/world/import/rest/pose/root transforms, units, axes, pivot, hierarchy, bone roll/orientation, non-uniform or negative scale, root motion, and retargeting assumptions.
- Inspect silhouette, anatomical proportions, joint volume, twist distribution, skin weights, clipping/self-intersection, contact points, occlusion, and first-person readability; specifically reject hidden elbows/biceps or collapsed limbs caused by bringing hands too close to the body.
- Capture at least `max(2, ceil(source_frame_count / 30))` distributed frames including endpoints, then add key poses, contacts, extremes, passing positions, transitions, loop boundaries, and known-risk frames.
- Verify each captured frame from relevant gameplay and diagnostic views; check contacts, foot sliding, arcs, spacing, timing, root drift, penetrations, deformation continuity, popping, and loop seams.
- Record an evidence ledger with clip/frame/time, view/camera settings, reference artifact, game artifact, observation, status, and remaining owner acceptance.
- Report repository/static, DCC/export, engine import, runtime/windowed, reference-match, animation-frame, and owner acceptance separately. Never promote one green layer into overall completion.
