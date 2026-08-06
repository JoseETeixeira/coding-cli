# Constitution: Verify 3D Models And Animation

- **Version**: 1.0.0
- **Ratified**: 2026-08-06
- **Last Amended**: 2026-08-06
- **Scope**: task-scoped

## Purpose

This constitution governs the design, integration, and use of the canonical 3D and visible-animation verification skill. It prevents favorable stills, uninspected references, ambiguous transform spaces, or repository-only checks from becoming unsupported completion claims. Any design deviation requires an explicit entry in the design's Complexity Tracking table.

## Core Principles

### 1. Source And Project Authority

**Statement**: The verifier SHALL inspect supplied or project-authoritative source material before making a source-match claim. Explicit current user decisions, current project source/specifications, matching specialists, actual engine/DCC versions, and current rendered feedback SHALL override generic guidance.

**Rationale**: A remembered pose, guessed reference, or generic engine assumption cannot establish fidelity in the active game.

**Evidence of compliance**: The design records source identity and inspection status, defines conflict and inaccessible-source behavior, and preserves the existing authority precedence.

### 2. Comparable Evidence Before Judgment

**Statement**: Source and game evidence SHALL be aligned as far as practical in view purpose, camera, projection, FOV/focal length, aspect, crop, subject transform, and time before visual differences are classified. Unresolved differences SHALL be recorded as uncertainty.

**Rationale**: Perspective, timing, and framing differences can masquerade as pose, scale, or deformation defects.

**Evidence of compliance**: Every reference comparison records comparable-capture settings and uses actual gameplay views plus diagnostic views when needed.

### 3. Temporal Proof Is Mandatory

**Statement**: Visible animation SHALL NOT be accepted from one frame. The verifier SHALL capture the deterministic minimum schedule, add every identified critical frame, and individually verify every captured frame and required transition.

**Rationale**: Contact, deformation, occlusion, popping, sliding, and loop defects often exist only between favorable stills.

**Evidence of compliance**: The sampling formula, endpoint distribution, critical-frame categories, per-frame ledger, and temporal checks are explicit and testable.

### 4. Pose, Transform, And Deformation Integrity

**Statement**: A target contact or approximate silhouette SHALL NOT excuse broken transform assumptions, hidden joint chains, implausible anatomy, collapsed volume, clipping, or inconsistent deformation. Relevant spaces, skeleton/rest state, root motion, and gameplay readability SHALL be checked separately.

**Rationale**: Moving a hand to the correct point can still hide the elbow/biceps, invert a wrist, break a bind pose, or deform the mesh.

**Evidence of compliance**: The design includes transform-space, skeleton, first-person occlusion, pose, skinning, and stressed-joint gates with diagnostic views.

### 5. Failed Critical Evidence Fails The Claim

**Statement**: One failed required or critical frame SHALL fail the affected pose, clip, or visual claim. Missing source access, runtime access, comparable capture, or required evidence SHALL yield `blocked` or pending status, never a pass.

**Rationale**: Averaging favorable frames hides defects and encourages premature completion.

**Evidence of compliance**: Closed gate vocabulary and aggregation rules prohibit passing a clip while any required frame fails, is missing, or is blocked.

### 6. Canonical, Selective Composition

**Statement**: Detailed generic verification SHALL have one canonical owner under `skills/verify-3d-animation/`; `gamedev-workflow` SHALL select it only for matching 3D or visible-animation work and SHALL compose it with the smallest relevant discipline set and project specialist. Vendored skill bodies and host mirrors SHALL remain untouched.

**Rationale**: A single owner prevents drift while selective composition limits context and preserves project authority.

**Evidence of compliance**: Thin entry pointers, one router, route fixtures, local/vendored ownership separation, and host-mirror checks remain intact.

### 7. Deterministic Validation And Honest Acceptance

**Statement**: Repository integration SHALL be validated by repeatable checks and reported separately from DCC, import, runtime, reference, per-frame, accessibility, owner, and release acceptance. Visible work SHALL remain `ready for owner review` until required owner acceptance is explicit unless that authority was explicitly delegated.

**Rationale**: Valid Markdown and routing fixtures cannot prove a model or animation matches the reference in a running game.

**Evidence of compliance**: The design defines deterministic content/routing checks and a separated evidence report with no gate promotion.

## Additional Constraints

- **Security**: Do not upload private source material or captures, store proprietary bytes in fixtures/memory, expose credentials, widen tool authority, or follow untrusted paths without explicit authorization.
- **Performance**: Evidence cost scales with the deterministic base schedule plus critical frames; no generic cap may reduce the approved minimum. Avoid duplicate captures only when they represent the same recorded time and view.
- **Compliance / Regulatory**: Preserve current repository licensing/provenance. The new skill is locally authored; no vendored body is rewritten.
- **Platform**: Remain engine-, DCC-, renderer-, camera-, and asset-format agnostic. Concrete commands come from the active project specialist and exact tool version.

## Development Workflow

- Approved Requirements, Design, Task Planning, Implementation, Tests, Review, and Documentation gates enforce these principles.
- `quick_validate.py`, `validate_integration.py`, routing fixtures, JSON parsing, marker checks, host-mirror checks, and `git diff --check` validate repository integration.
- Active game work must separately produce comparable captures, frame evidence, runtime results, and any required owner acceptance.
- Design and Task Plan approvals precede customization-layer mutation.

## Governance

- This constitution supersedes ad-hoc decisions for this task. A design that violates a principle without a Complexity Tracking entry fails review.
- Amendments require explicit justification, a migration plan for in-flight work, and a semantic version bump.
- Every implementation and review pass must verify constitution compliance.

## Amendment Log

| Version | Date | Change | Author |
|---|---|---|---|
| 1.0.0 | 2026-08-06 | Initial task constitution | Batman |
