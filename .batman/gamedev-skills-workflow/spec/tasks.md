# Tasks: Gamedev Skills Workflow

## Phase 4a Discovery Record

Fresh read-only discovery ran after Design approval and before this plan:

- Re-read every file under `.batman/gamedev-skills-workflow/steering/`, plus approved `requirements.md`, `design.md`, the accepted PRD, `prompts/create-tasks.prompt.md`, and the repository ADR convention.
- Exact `Test-Path` checks reconfirmed all eight target skill directories are absent.
- Query `rg -n -C 3 "byond-projects|generic-entry|skills/" AGENTS.md agents/batman.agent.md prompts/execute-task.prompt.md README.md` reconfirmed the three thin-routing surfaces, existing BYOND precedent, and README discovery location.
- Search for task-plan precedents found no other implementation `tasks.md` body in the current `.batman/` tree.
- Search for a repository-native skill validator found none; implementation therefore uses the approved system `skill-creator` validator plus the router-owned standard-library validator.
- `docs/architecture/adr/0008-batman-delegation-handoffs.md` was the highest pre-existing ADR. Design approval created accepted ADR `0009-gamedev-skill-intake-and-routing.md` before this plan.
- Broad status remains `?? .batman/` and `?? docs/`; all pre-existing user-owned content remains outside broad staging/reset scope.

Outcome: approved Design remains implementable without changing its components, authority model, data schemas, or verification boundary.

## Implementation Plan

- [x] 1. Capture guarded baseline and prepare task-owned intake workspace
  - Record resolved canonical `skills/` root, all eight destination paths, their absent/existing state, and a path-containment assertion before mutation.
  - Record path-scoped Git status and hashes for every pre-existing tracked integration surface; inventory unrelated untracked `docs/` without modifying it.
  - Create task-scoped evidence locations only; keep fetched comparison material outside tracked canonical skill paths.
  - Define exact source package list, immutable commits, source subdirectories, and expected destination names from approved Design.
  - Add a deterministic missing-only install-plan check that marks any destination found at execution time as skipped and excludes it from all later mutation.
  - _Requirements: GDS-REQ-001, GDS-REQ-002, GDS-REQ-010 / GDS-AC-001, GDS-AC-002, GDS-AC-011_

- [x] 2. Scaffold the selective `gamedev-workflow` router and its contract fixtures
  - Initialize `skills/gamedev-workflow/` through the approved `skill-creator` workflow, retaining only needed scaffold files.
  - Author concise `SKILL.md` triggers, negative boundaries, authority precedence, engine/version compatibility gates, safe-reference rules, progressive disclosure, and static-versus-project acceptance boundary.
  - Encode representative routing cases for game design, general implementation, 3D, Godot FPS, Godot particles, Godot performance, UI motion, BYOND composition, a cross-discipline task, and a Godot version conflict.
  - Compose only applicable existing skills/specialists, including `byond-projects`, `visual-explainer`, refactoring/testing guidance, and optional `imagegen`; never imply optional upstream siblings are installed.
  - Add standard-library integration-validator structure with path-contained inputs, collected actionable failures, and nonzero failure exit.
  - _Requirements: GDS-REQ-003, GDS-REQ-004, GDS-REQ-005, GDS-REQ-009, GDS-REQ-010 / GDS-AC-007, GDS-AC-008, GDS-AC-012_

- [x] 3. Install six complete pinned upstream packages without overwriting destinations
  - Invoke the approved `skill-installer` separately for absent `game-developer`, `3d-modeling`, `godot-genre-shooter-fps`, `godot-particles`, `godot-performance-optimization`, and `motion-design` destinations using exact reviewed commits and source paths.
  - Stop or skip per destination if the guarded precondition changed; never merge into or replace an existing directory.
  - Verify each copied tree contains every file from its selected upstream package and no path escaped canonical `skills/`.
  - Preserve upstream filenames and bytes before any approved adaptation so source hashes remain reproducible.
  - _Requirements: GDS-REQ-001, GDS-REQ-002, GDS-REQ-006 / GDS-AC-001, GDS-AC-002, GDS-AC-004_

- [x] 4. Add license, provenance, and adaptation manifests for the six vendored packages
  - Add each package's exact `UPSTREAM.json` with schema version, skill name, repository, source path, 40-hex commit, original SHA-256 map, origin chain, license declarations, adaptation ledger, and local-only files.
  - Preserve applicable verbatim MIT, Apache-2.0, and LGPL-3.0 license/notice text; retain both original-source and requested-registry chain evidence for `3d-modeling` without implying endorsement.
  - Validate every upstream file hash before adaptation and ensure every local difference can later map to one approved adaptation or local-only record.
  - Keep manifests machine-readable and normal skill use independent from the network.
  - _Requirements: GDS-REQ-002, GDS-REQ-007 / GDS-AC-005, GDS-AC-006_

- [x] 5. Apply only approved package adaptations and make every package self-contained
  - Repair `3d-modeling` by replacing its three impossible mandatory reads with the approved concise creation, sharp-edge diagnosis, and validation checklist.
  - Rewrite dangling Godot sibling-skill links as pinned external/optional references; do not install or claim those siblings.
  - Normalize unsupported frontmatter only when the active validator requires it; otherwise preserve supported upstream metadata.
  - Label bundled scripts, shaders, project settings, patterns, and examples as reference starting points subject to project/version/renderer/authority checks.
  - Record every modified upstream file and reason in its package adaptation ledger; leave no unexplained delta or required dangling path.
  - _Requirements: GDS-REQ-005, GDS-REQ-006, GDS-REQ-007, GDS-REQ-009 / GDS-AC-003, GDS-AC-004, GDS-AC-006, GDS-AC-008_

- [x] 6. Author clean-room canonical `game-designer`
  - Initialize `skills/game-designer/` through `skill-creator` before retrieving excluded prose during this implementation pass.
  - Author from approved requirements and general knowledge only: player promise/audience/constraints, core loops, mechanics/state/invariants, progression/economy/balance, onboarding/accessibility, prototype/playtest/telemetry, and implementation handoff.
  - Keep examples, wording, and section structure independently authored; include reduced ambiguity, measurable design questions, and explicit project-source authority.
  - Add `ORIGIN.json` with clean-room basis, excluded repository/path/commit/hash metadata, decision date, reason, and comparison-evidence pointer; make no upstream license or endorsement claim.
  - Ensure every local reference declared by the skill exists before comparison.
  - _Requirements: GDS-REQ-002, GDS-REQ-004, GDS-REQ-006, GDS-REQ-007 / GDS-AC-003, GDS-AC-004, GDS-AC-005, GDS-AC-007, GDS-AC-013_

- [x] 7. Add thin canonical routing pointers and discovery documentation
  - Add one concise conditional pointer to `skills/gamedev-workflow/SKILL.md` in `AGENTS.md`, `agents/batman.agent.md`, and `prompts/execute-task.prompt.md` without duplicating routing/precedence bodies.
  - Keep `generic-entry` mandatory and preserve existing BYOND routing text and resolution.
  - Add a concise README discovery entry naming the router and covered disciplines.
  - Confirm project specialist definitions and all installed/generated host roots remain unchanged.
  - Keep accepted PRD and ADR aligned with implemented paths, pins, licensing model, adaptations, and stated limitations.
  - _Requirements: GDS-REQ-003, GDS-REQ-008, GDS-REQ-011 / GDS-AC-009, GDS-AC-010_

- [x] 8. Complete deterministic integration, source-delta, and clean-room checks
  - Finish `validate_integration.py` checks for eight expected directories, `SKILL.md` names/frontmatter, required paths, relative links, manifest/origin schemas, license files, routing fixtures, and thin pointer resolution.
  - Run the selected `quick_validate.py` against all eight skill directories and parse every new JSON file with Python's standard library.
  - Compare all six vendored trees against exact pinned upstream snapshots; write task evidence accounting for every unchanged, adapted, and local-only file.
  - Retrieve excluded `game-designer` snapshot only for post-authorship comparison; do not store its content in the repository.
  - Normalize Unicode/case/whitespace, remove frontmatter, assert whole-file hashes differ, fail on any contiguous 12-plus-word match, and report 8–11-word runs for manual classification.
  - Write overlap evidence containing only hashes, counts, run lengths, short diagnostic locations, source pin, method, and disposition; rewrite/retest any unexplained suspicious overlap.
  - _Requirements: GDS-REQ-002, GDS-REQ-006, GDS-REQ-007, GDS-REQ-010 / GDS-AC-003, GDS-AC-004, GDS-AC-005, GDS-AC-006, GDS-AC-013_

- [x] 9. Exercise routing, precedence, idempotence, and safety scenarios
  - Evaluate all representative read-only routing fixtures and confirm exact primary skills, conditional existing skills, specialists, and mandatory gates.
  - Prove a Godot 4.6/project-specialist case overrides incompatible 4.7+ imported assumptions and degrades examples to conceptual/reference guidance.
  - Simulate a second installation plan; verify all eight existing destinations are skipped and their hashes remain unchanged.
  - Scan for unresolved local links, unsafe automatic execution language, secrets, expanded tools/permissions, unpinned external dependencies, and duplicated workflow authority.
  - Confirm no active game repository, editor/runtime, generated host copy, or unrelated working-tree path was readied for mutation or changed.
  - _Requirements: GDS-REQ-001, GDS-REQ-004, GDS-REQ-005, GDS-REQ-009, GDS-REQ-010 / GDS-AC-002, GDS-AC-007, GDS-AC-008, GDS-AC-009, GDS-AC-011, GDS-AC-012_

- [x] 10. Perform path-scoped review and close documentation/evidence
  - Run `git diff --check`, the canonical code-review instructions, and a path-scoped diff/status review covering only approved task paths.
  - Revalidate constitution principles, requirement/acceptance traceability, source hashes, license obligations, adaptation completeness, pointer thinness, and worktree preservation.
  - Confirm PRD and accepted ADR match the final implementation; update only factual implementation/evidence details that do not alter accepted requirements or architecture.
  - Report every command/result and unresolved limit; separate static integration success from unperformed runtime, renderer, visual, performance, accessibility, owner, and release gates.
  - Leave all changes unstaged/uncommitted/unpushed unless the user separately requests publication.
  - _Requirements: GDS-REQ-007, GDS-REQ-008, GDS-REQ-010, GDS-REQ-011 / GDS-AC-005, GDS-AC-006, GDS-AC-009, GDS-AC-010, GDS-AC-011, GDS-AC-012, GDS-AC-013_
