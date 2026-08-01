# Requirements: Gamedev Skills Workflow

## Status

Approved on 2026-08-01. Phase 1 Understanding, the `3d-modeling` repair, the clean-room `game-designer` direction, Design, and Task Planning were approved before implementation. Final implementation and static verification evidence is recorded under `../evidence/`; project runtime and owner acceptance remain outside this repository-only task.

## Problem Statement

`coding-cli` has project specialists and a conditional BYOND skill, but no general game-development workflow. The seven requested skill names are absent. Literal imports would also create integrity, compatibility, licensing, and authority problems: `3d-modeling` has missing mandatory references, `game-designer` is marked restricted/unknown-license by its package metadata, some advice is engine/version-specific, and third-party defaults can conflict with current project evidence.

## Phase 2a Discovery Record

Discovery was read-only and ran before this draft.

- Query `rg -n --hidden --glob '!docs/**' --glob '!.git/**' "game-developer|3d-modeling|game-designer|godot-genre-shooter-fps|godot-particles|godot-performance-optimization|motion-design|gamedev-workflow|byond-projects" AGENTS.md README.md agents prompts skills .batman` found no requested skill or gamedev router; it found the conditional `byond-projects` precedent and the approved Understanding artifact.
- Exact directory checks for all eight proposed names under canonical `skills/`, `~/.codex/skills`, `~/.agents/skills`, and `~/.claude/skills` returned empty.
- Reads of `README.md`, `AGENTS.md`, `agents/batman.agent.md`, `skills/generic-entry/SKILL.md`, `skills/auto-improvement/SKILL.md`, `prompts/execute-task.prompt.md`, and `agents/godot-dev.agent.md` confirmed canonical-only ownership, approval gates, existing thin routing, and project-specialist precedence needs.
- `rg --files .batman docs` found no reusable Phase 2 steering/spec example. It found the repository conventions `docs/prd/` and `docs/architecture/adr/`, including ADRs through `0008`.
- `CONTEXT.md` and `CONTEXT-MAP.md` are absent. No unresolved domain-model term requires creating either file; the glossary below is sufficient.
- Current state check: branch `main`, HEAD `81862dc`, origin `JoseETeixeira/coding-cli`; `.batman/` and `docs/` are untracked. Existing unrelated `docs/` content must be preserved.
- Phase 1 already inspected all four upstream repositories at pinned commits and recorded package trees, license families, compatibility claims, and dangling references in `steering/understanding.md`.
- Phase 3a re-opened licensing evidence at the exact registry pin. `game-designer/metadata.json` reports `license: NOASSERTION`, `distribution: restricted`, and says not to treat the package as MIT. The original repository has no `LICENSE` file. The user selected a clean-room canonical replacement rather than copying that snapshot.
- The same pass confirmed `3d-modeling/metadata.json` identifies Apache-2.0 upstream content; its bytes match the identified original snapshot, whose repository carries the Apache-2.0 license. The integration must preserve this more specific origin/license evidence alongside registry provenance.

Outcome: discovery found an architecture addition, not an existing workflow to extend. Requirements therefore define one canonical router, six missing-only distributable snapshots, one missing-only clean-room skill, explicit precedence, and deterministic integration gates.

## Glossary

- **Gamedev workflow**: the new conditional router that chooses and sequences relevant game-development skills; not a replacement for `generic-entry`.
- **Discipline skill**: reusable design, implementation, art, VFX, performance, or motion guidance.
- **Specialist agent**: project-specific authority for an engine, repository, editor/tool bridge, build, and verification contract.
- **Pinned snapshot**: files fetched from an immutable upstream commit SHA.
- **Clean-room canonical skill**: locally authored content derived from approved capability requirements and general domain knowledge, without copying or closely paraphrasing the excluded snapshot.
- **Adaptation ledger**: a record of every local change from the pinned upstream files and why it exists.
- **Missing-only**: install a requested skill only when its destination directory does not already exist; never overwrite an existing skill as part of installation.
- **Routing scenario**: a read-only representative prompt used to inspect the workflow's declared skill selection and precedence behavior.

## Stakeholders

- **Primary**: user/maintainer of canonical `coding-cli` and developers running Batman in game repositories.
- **Secondary**: designers, technical artists, project specialists, reviewers, and maintainers performing future snapshot refreshes.
- **External**: upstream skill authors whose licenses and attribution must be retained.

## Goals

1. Add all seven explicitly requested skill names to canonical `coding-cli` only when absent: six as reviewed upstream snapshots and `game-designer` as clean-room canonical content.
2. Add one discoverable gamedev workflow that composes those skills with relevant existing skills and specialist agents.
3. Make project/source authority, engine compatibility, evidence gates, and accessibility explicit.
4. Preserve full usable upstream packages, licenses, provenance, local adaptation history, and the clean-room origin/exclusion boundary.
5. Verify the integration without mutating any active game project.

## Non-Goals

- Installing every sibling skill referenced by an upstream package.
- Configuring or launching Godot, Unreal, Roblox Studio, BYOND, Blender, or any game repository.
- Copying bundled example scripts/shaders into a live project.
- Copying or closely paraphrasing the restricted/unknown-license `game-designer` snapshot.
- Automatically tracking upstream branches or refreshing snapshots.
- Replacing project specialist agents, `generic-entry`, or project-local instructions.
- Proving runtime FPS, visuals, feel, accessibility, compatibility, or release readiness through repository-only checks.
- Editing generated/installed host copies under user configuration roots.
- Committing, pushing, or broadly staging the resulting changes unless separately requested.

## Functional Requirements

### GDS-REQ-001 — Missing-only canonical installation

When this feature is implemented, the system shall provide these canonical skill directories: `game-developer`, `3d-modeling`, `game-designer`, `godot-genre-shooter-fps`, `godot-particles`, `godot-performance-optimization`, and `motion-design`.

- If a destination exists before its install step, the installer shall leave it byte-for-byte unchanged and report the skip.
- If one of the six distributable upstream destinations is absent, the installer shall fetch its complete requested upstream subdirectory from its approved pinned commit.
- If `game-designer` is absent, the skill-creation workflow shall create independently authored canonical content; it shall not install the requested restricted snapshot.
- The implementation shall not create copied skill bodies in `~/.claude`, `~/.agents`, `~/.codex`, or workspace host folders.

### GDS-REQ-002 — Immutable source selection and clean-room boundary

The six vendored packages shall use the reviewed source snapshots below, unless a later approved Design explicitly replaces a pin after repeating source/license inspection:

- `game-developer`: `Jeffallan/claude-skills@e8be415bc94d8d6ebddc2fb50e5d03c6e27d4319`, path `skills/game-developer`.
- `3d-modeling`: `majiayu000/claude-skill-registry@ef926663574f5f7a0c19b0429b2540373279ed45`, path `skills/data/3d-modeling`.
- Three Godot skills: `thedivergentai/GD-Agentic-Skills@ebffc2b4f39b54dcf343b52dc9845a4ecc451cf2`, using their requested paths.
- `motion-design`: `lottiefiles/motion-design-skill@f9a8a041b85185ee4881b3471d3415e939aac772`, path `skills/motion-design`.

`game-designer` shall be authored from the approved capability/routing requirements and general game-design knowledge. It shall not copy or closely paraphrase the excluded registry snapshot. Its origin record shall identify the requested URL and pinned metadata as evaluated-but-not-vendored evidence, record the user's clean-room decision, and state that no upstream endorsement is implied.

After vendoring, normal use shall not require upstream network access. Updates shall be explicit reviewed snapshot changes, not automatic branch tracking.

### GDS-REQ-003 — Discoverable gamedev router

When a task materially concerns game mechanics, gameplay systems, game-engine code, assets, 3D production, VFX, performance, or game UI motion, Batman shall read and follow `skills/gamedev-workflow/SKILL.md` in addition to `generic-entry`.

The router shall:

- state its positive and negative trigger boundaries;
- select the smallest relevant set of discipline skills;
- support multiple routes when the task genuinely crosses disciplines;
- preserve the Batman phase, memory, approval, review, and documentation gates;
- avoid treating all game-related conversation as authorization to edit a game project.

### GDS-REQ-004 — Domain routing coverage

When a task matches a discipline, the router shall identify the corresponding primary guidance:

- mechanics, game loops, economy, onboarding, GDDs, and playtests → `game-designer`;
- general game implementation architecture, gameplay systems, Unity, or Unreal patterns → `game-developer`, qualified by the active project;
- mesh, topology, UV, LOD, baking, or 3D export pipelines → `3d-modeling`;
- Godot FPS controller/weapon work → `godot-genre-shooter-fps` only after engine/project compatibility checks;
- Godot particle/VFX work → `godot-particles` only after renderer/version checks;
- Godot profiling/optimization work → `godot-performance-optimization` only with an authored workload and measured baseline;
- UI animation, micro-interactions, transitions, or Lottie motion → `motion-design`, with reduced-motion/accessibility requirements.

The router shall also compose relevant existing authorities when triggered: project specialist agents, `byond-projects` for BYOND-family work, `visual-explainer` for complex flows/recaps, and safe testing/refactoring guidance for risky code changes. It shall not imply that optional upstream sibling skills are installed.

### GDS-REQ-005 — Authority and conflict resolution

If imported guidance conflicts with an explicit user decision, active project source, approved project specification/ADR, specialist agent contract, actual engine/version/renderer/platform, official engine documentation, or measured workload evidence, the higher-specificity current authority shall win and the conflict shall be stated.

The router shall treat generic FPS targets, pooling, LOD, architecture, naming, engine versions, and platform assumptions as candidates until the active project accepts them. It shall never use repository-only validation as proof of runtime, visual, performance, accessibility, or release acceptance.

### GDS-REQ-006 — Complete, usable packages and approved repair

Each of the six installed upstream skills shall include every bundled reference, script, shader, director module, pattern, and other file required by its `SKILL.md` at the pinned snapshot. The clean-room `game-designer` skill shall include every local reference it declares.

Because the approved `3d-modeling` snapshot mandates three files that do not exist upstream, its local integration shall preserve the useful upstream body, replace those impossible mandatory reads with a concise self-contained production checklist covering creation, sharp-edge diagnosis, and validation, and record the repair in its adaptation ledger.

Any unsupported frontmatter fields or broken local relative links introduced by upstream packaging shall be normalized without changing the skill's intended capability. Optional external related-skill links shall be labeled external/optional rather than rewritten as installed dependencies.

### GDS-REQ-007 — License, provenance, and modification traceability

For every one of the six third-party skills, the repository shall retain:

- source repository, subdirectory, and immutable commit SHA;
- upstream license identity and the notice/license text required for redistribution;
- an adaptation ledger identifying each locally modified file, the nature of the change, and the integration reason;
- a reproducible distinction between unchanged upstream files and local additions/changes.

MIT notices shall remain with applicable MIT-derived packages. Apache-2.0 license and modified-file notices shall remain with `3d-modeling`. LGPL-3.0 terms and modification visibility shall remain with the three Godot-derived packages. The clean-room `game-designer` shall carry a local origin/exclusion record rather than an upstream license claim. No local wording shall imply upstream endorsement.

### GDS-REQ-008 — Thin canonical integration

The workflow shall be reachable across entry and implementation phases using thin conditional pointers in the existing canonical routing surfaces. Those surfaces shall link to the workflow and shall not duplicate its routing matrix, precedence rules, or third-party content.

The README shall list the gamedev workflow and requested disciplines concisely. Canonical content shall remain under this checkout; installed host adapters remain outside the scope of mutation.

### GDS-REQ-009 — Safe reference use

Bundled scripts, shaders, project settings, and patterns shall be labeled as references or starting points. Before using one in a game, the acting agent shall validate the active project version, architecture, scene/resource layout, renderer, threading/multiplayer authority, save/replay contracts, platform targets, and project verification instructions.

No validation scenario for this feature shall copy or execute those assets inside an active game repository.

### GDS-REQ-010 — Deterministic validation and review

Before the feature is called complete, validation shall:

- run the selected skill validator successfully for all eight new skill directories;
- report zero unresolved required local paths and zero dangling relative Markdown links;
- verify every pinned source, license record, and adaptation ledger;
- compare vendored files with pinned upstream files and account for every difference;
- compare the clean-room `game-designer` against the excluded snapshot with deterministic exact and meaningful phrase-overlap checks, reporting any suspicious overlap for manual review;
- exercise representative read-only routing scenarios for all seven disciplines plus a cross-discipline case;
- verify the canonical entry pointers are thin and resolve;
- run `git diff --check` and a path-scoped diff review;
- prove pre-existing destination skills and unrelated working-tree content were not overwritten.

Any failed gate shall be reported as failed or blocked; focused success shall not be generalized into runtime or release acceptance.

### GDS-REQ-011 — Documentation lifecycle

After Requirements approval, the task shall produce `docs/prd/gamedev-skills-workflow.md`. Phase 3 shall offer an ADR because pinned third-party vendoring, local adaptations, and precedence are hard to reverse, surprising without context, and involve real trade-offs; if accepted, it shall use the repository's `docs/architecture/adr/` convention and next available number.

Documentation shall distinguish current source facts, approved decisions, external snapshot facts, verification evidence, and remaining project-specific acceptance.

## Non-Functional Requirements

### Context efficiency

- The router shall use progressive disclosure and shall not require loading every large skill body/reference for each game task.
- Detailed package content stays in its owning skill; entry pointers remain short.

### Compatibility

- Skill discovery metadata shall validate on the current Codex skill contract.
- Godot-specific routes shall fail closed or degrade to conceptual guidance when the active version/renderer is incompatible or unknown.
- Existing BYOND and project-specialist routing remains intact.

### Accessibility

- Motion guidance shall include reduced-motion behavior and shall not rely solely on animation to communicate state.
- Visual acceptance remains an owner/on-screen gate where applicable.

### Security and safety

- Third-party content is treated as untrusted data during import review.
- No secrets, credentials, wider tools, sandbox exceptions, or automatic code execution may be added.
- Paths used by installation/validation shall be resolved and constrained to the intended canonical destinations.

### Maintainability

- One source owns each rule: universal behavior in `generic-entry`, game composition in `gamedev-workflow`, discipline details in their skills, and project specifics in specialist agents/source.
- A future refresh must be reviewable by commit pin and adaptation ledger without reverse-engineering the initial import.

## Acceptance Criteria

- **GDS-AC-001**: Exactly eight new canonical skill directories exist: the seven requested names and `gamedev-workflow`; no same-name host mirror is created.
- **GDS-AC-002**: A simulated second installation skips all existing destinations and produces no content diff.
- **GDS-AC-003**: All eight `SKILL.md` files pass `quick_validate.py` (or the approved Design's equivalent validator) with supported frontmatter.
- **GDS-AC-004**: A deterministic link/path scan reports zero missing required package files and zero dangling local Markdown links.
- **GDS-AC-005**: Provenance/license/adaptation records cover all six upstream packages and list the exact reviewed SHAs; `game-designer` has a clean-room origin/exclusion record.
- **GDS-AC-006**: A source comparison across the six vendored packages reports every local difference as either metadata normalization, integration guardrail, license/provenance addition, or the approved `3d-modeling` repair; no unexplained drift remains.
- **GDS-AC-007**: Read-only routing cases select the correct primary skill for design, implementation, 3D, Godot FPS, Godot particles, Godot performance, and UI motion, plus all needed skills for one cross-discipline case.
- **GDS-AC-008**: A conflict case demonstrates that active project engine/version and specialist instructions override an incompatible upstream default.
- **GDS-AC-009**: `AGENTS.md`, `agents/batman.agent.md`, and `prompts/execute-task.prompt.md` contain resolving thin pointers; existing BYOND routing still resolves.
- **GDS-AC-010**: README, PRD, and accepted ADR accurately describe discovery, routing, pins, licenses, adaptations, and limitations without duplicating workflow bodies.
- **GDS-AC-011**: `git diff --check` passes, path-scoped review finds no secrets or unsafe execution, and pre-existing untracked `docs/` plus unrelated changes remain preserved.
- **GDS-AC-012**: Final reporting separates static integration success from unperformed project runtime, renderer, visual, performance, accessibility, and owner acceptance.
- **GDS-AC-013**: Exact-copy and meaningful phrase-overlap checks find no unexplained overlap between clean-room `game-designer` content and the excluded restricted snapshot; the comparison evidence records the source pin and method.

## Assumptions Proposed For Approval

- Pinned snapshots remain frozen until an explicit reviewed refresh; no automatic updater is part of this feature.
- The current four requested-repository commit SHAs remain the source inputs for the six distributable snapshots and excluded-source evidence; any pin change reopens integrity/license discovery.
- `game-designer` is locally authored from requirements and general knowledge, not from the requested snapshot's prose or structure.
- The three existing canonical routing surfaces are sufficient for discoverability; host-generated copies are intentionally untouched.
- Existing untracked `docs/` files are user-owned. New PRD/ADR files may be added at distinct paths after their phase approvals, but existing files may not be overwritten.

## Requirement Traceability Seed

| Concern | Requirements | Acceptance |
| --- | --- | --- |
| Missing-only install and clean-room boundary | GDS-REQ-001, GDS-REQ-002 | GDS-AC-001, GDS-AC-002, GDS-AC-013 |
| Routing/composition | GDS-REQ-003, GDS-REQ-004 | GDS-AC-007, GDS-AC-009 |
| Authority/version safety | GDS-REQ-005, GDS-REQ-009 | GDS-AC-008, GDS-AC-012 |
| Package integrity/repair | GDS-REQ-006 | GDS-AC-003, GDS-AC-004, GDS-AC-006 |
| Licensing/provenance | GDS-REQ-007 | GDS-AC-005, GDS-AC-006 |
| Canonical integration/docs | GDS-REQ-008, GDS-REQ-011 | GDS-AC-009, GDS-AC-010 |
| Verification/safety | GDS-REQ-010 | GDS-AC-011, GDS-AC-012 |
