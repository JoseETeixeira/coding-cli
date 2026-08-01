# Constitution: Gamedev Skills Workflow

- **Version**: 1.0.0
- **Ratified**: 2026-08-01
- **Last Amended**: 2026-08-01
- **Scope**: task-scoped

## Purpose

This constitution governs the intake, adaptation, routing, and verification of game-development skills in canonical `coding-cli`. Any design deviation must appear in the design's Complexity Tracking table with a concrete reason and mitigation.

## Core Principles

### 1. Canonical Once

**Statement**: Shared skill, prompt, instruction, and agent bodies SHALL live only in canonical `coding-cli`; host layers SHALL remain pointers or adapters.

**Rationale**: Mirrored bodies drift and create competing authorities.

**Evidence of compliance**: New bodies exist only under canonical `skills/`; host roots are read-only during implementation; entry edits are thin pointers.

### 2. Current Project Authority

**Statement**: Explicit user decisions, current project source, approved project specifications, specialist-agent contracts, actual engine/platform versions, official documentation, and measured evidence SHALL override generic imported guidance.

**Rationale**: Upstream defaults are not reliable facts for every game, engine, renderer, workload, or release target.

**Evidence of compliance**: The router declares a precedence stack, Godot routes require compatibility checks, and validation includes a conflicting-version scenario.

### 3. Missing-Only, Path-Contained Mutation

**Statement**: Installation SHALL NOT overwrite an existing skill directory, escape the canonical `skills/` root, or mutate unrelated working-tree content.

**Rationale**: Existing skills and dirty work belong to the user unless explicitly placed in scope.

**Evidence of compliance**: Exact destination preflight, installer fail-closed behavior, resolved path checks, before/after status evidence, and a simulated second run.

### 4. License and Origin Integrity

**Statement**: Redistributed upstream material SHALL retain applicable license text, immutable provenance, original-file hashes, and modification notices. Restricted or unknown-license content SHALL NOT be copied or closely paraphrased.

**Rationale**: A repository-wide license cannot silently erase more specific package metadata or original-source obligations.

**Evidence of compliance**: Per-package `UPSTREAM.json` and license files, clean-room `ORIGIN.json`, adaptation entries, and overlap evidence.

### 5. Deterministic Verification, Honest Acceptance

**Statement**: Static integration claims SHALL be backed by repeatable checks, and SHALL NOT be presented as engine-runtime, visual, performance, accessibility, owner, or release acceptance.

**Rationale**: Valid Markdown and passing link checks cannot prove gameplay behavior or rendering quality.

**Evidence of compliance**: Validator output, source comparison, routing fixtures, path-scoped review, and explicit remaining-acceptance reporting.

### 6. Selective Composition

**Statement**: The workflow SHALL load the smallest relevant discipline set and SHALL keep detailed references behind progressive links.

**Rationale**: Loading every skill wastes context and increases conflicting advice.

**Evidence of compliance**: A routing matrix with positive/negative boundaries, cross-discipline composition rules, and no duplicated skill bodies in entry files.

### 7. Reference Assets Never Auto-Execute

**Statement**: Imported scripts, shaders, settings, and examples SHALL be treated as references and SHALL NOT be copied or executed in an active game without project-specific validation and authorization.

**Rationale**: Foreign examples can violate scene, renderer, threading, multiplayer, save/replay, or platform contracts.

**Evidence of compliance**: Router safety gate, no live-game paths in validation, and security review confirming no new tools, secrets, or automatic execution.

## Additional Constraints

- **Security**: no secrets, credential changes, tool expansion, sandbox exceptions, or uncontained paths.
- **Performance**: context efficiency through selective routing; game performance claims require an authored workload and measured project baseline.
- **Compliance / Regulatory**: applicable MIT, Apache-2.0, and LGPL-3.0 redistribution/modification obligations; restricted content excluded.
- **Platform**: canonical content remains host-agnostic; Godot examples are version/renderer gated.

## Development Workflow

- Batman Requirements, Design, Task Planning, Implementation, Tests, Review, and Documentation enforce the principles.
- `quick_validate.py`, the workflow integration validator, link scans, source manifests, overlap checks, and `git diff --check` provide automated evidence.
- User approval gates settle Requirements, Design/ADR, and Task Planning before canonical mutation.

## Governance

- The constitution supersedes ad-hoc design choices for this task. An untracked violation fails review.
- Amendments require explicit justification, a migration plan for in-flight work, and a semantic version bump.
- Every implementation/review pass verifies constitution compliance.

## Amendment Log

| Version | Date | Change | Author |
|---|---|---|---|
| 1.0.0 | 2026-08-01 | Initial task constitution | Codex/Batman |

