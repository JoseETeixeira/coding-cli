# Constitution: GPT Image 2 Skill And Tool

- **Version**: 1.0.0
- **Ratified**: 2026-08-02
- **Last Amended**: 2026-08-02
- **Scope**: task-scoped

## Purpose

This constitution governs the design, implementation, registration, and verification of the canonical GPT Image 2 skill and MCP server. Any deviation must appear in the Design Complexity Tracking table with a concrete reason and mitigation.

## Core Principles

### 1. Secrets And Content Stay Bounded

**Statement**: Credential values, Authorization headers, raw request/response bodies, base64 payloads, prompts, reference images, and masks SHALL NOT enter repository files, logs, errors, MCP metadata, tests, evidence, or memory except that caller-requested output images SHALL be written to their approved local destination.

**Rationale**: The service crosses a credential boundary and transports user-provided/generated content; diagnostic convenience cannot silently expand retention.

**Evidence of compliance**: Credential lookup accepts no tool argument; fixed safe error mappings replace raw exception text; canary-secret tests and changed-file scans pass; logs contain only safe codes, attempts, timing, and request IDs.

### 2. Paid Actions Are Explicit And Bounded

**Statement**: Image API calls SHALL occur only for explicit user image intent or the one approved live smoke; model, defaults, count, retry policy, and deadlines SHALL remain closed and visible.

**Rationale**: Hidden model changes, variants, retries, or background work can multiply spend and create ambiguous duplicate results.

**Evidence of compliance**: Fixed `gpt-image-2`; default `high`/`1024x1024`/PNG/`n=1`; SDK retries disabled; one explicit-response retry maximum; no timeout retry; 180-second overall deadline.

### 3. Validate Before Network

**Statement**: Every locally knowable schema, cross-field, path, image, mask, size, format, count, and output constraint SHALL be checked before credential lookup and API invocation.

**Rationale**: Invalid paid requests waste time/credits and can turn malformed files or paths into security problems.

**Evidence of compliance**: Pure validators with fake-call counters; table-driven invalid cases prove zero credential and API calls; edit inputs cap at 16 local images under 50 MB each.

### 4. Never Overwrite; Publish Atomically

**Statement**: Successful outputs SHALL use generic/sanitized basenames, collision-safe numeric suffixes, validated bytes, and an atomic no-overwrite publication primitive; failures SHALL NOT expose invalid partial files.

**Rationale**: Generated output must not damage existing project assets or leave corrupt files that look complete.

**Evidence of compliance**: Default `generated-images/image.png`; concurrent collision tests; temporary-file flush/fsync; link-if-absent publication; cleanup tests; existing-file hashes remain unchanged.

### 5. Canonical Once, Thin Host Adapters

**Statement**: The skill and server implementation SHALL live only in canonical `coding-cli`; Claude Code, Codex, and VS Code / Copilot layers SHALL contain thin registrations without source bodies or credential values.

**Rationale**: Host copies drift, obscure ownership, and make security fixes inconsistent.

**Evidence of compliance**: One `skills/gpt-image-2/` package, one `gpt_image_2/` service, parsed adapter configs, and post-merge activation evidence that distinguishes source registration from live availability.

### 6. Protocol And Binary Results Stay Bounded

**Statement**: Stdout SHALL remain JSON-RPC-only, structured results SHALL remain stable, and inline image content SHALL be limited to the first output at no more than 5 MiB decoded.

**Rationale**: Unbounded base64 and accidental stdout logging can corrupt MCP transport or exhaust host context/message limits.

**Evidence of compliance**: stderr-only logging, stdio smoke parsing, small/large result tests, all-output path metadata, and no raw payload diagnostics.

### 7. Mock First; Report Gates Honestly

**Statement**: Default verification SHALL make no external call. Mocked, live API, visual, source-registration, per-host activation, owner, and release evidence SHALL remain distinct.

**Rationale**: Passing unit tests or HTTP 200 cannot prove organization access, tool discovery, visual quality, or every host runtime.

**Evidence of compliance**: fake-backed default suite, opt-in live marker, one low-cost generation, local visual inspection, per-host checklist, and explicit unrun/blocked gates.

## Additional Constraints

- **Security**: local edit inputs only; no URL fetches, arbitrary headers/endpoints, model overrides, overwrite flag, secret serialization, or raw-content logging.
- **Performance**: 150-second API attempt timeout, 180-second operation deadline, documented 240-second Claude/Codex host timeouts, schema-valid VS Code registration plus runtime gate, and one preview no larger than 5 MiB decoded.
- **Compliance / Regulatory**: OpenAI moderation remains in force; organization verification/billing failures are reported, not bypassed.
- **Platform**: Windows 11 and Python 3.12 are validated; process-environment credentials remain portable; Windows User fallback stays isolated.

## Development Workflow

- Requirements, Design/ADR, Task Planning, Implementation, Tests, Review, and Documentation approvals enforce these principles.
- `quick_validate.py`, pytest, fake-backed stdio smoke, config parsing, secret scans, `git diff --check`, one live smoke, and visual inspection provide evidence.
- Any live API call occurs only after deterministic gates pass; any user-wide adapter mutation is exact, thin, parsed before/after, and separately reported.

## Governance

- The constitution supersedes ad-hoc choices for this task. An untracked violation fails review.
- Amendments require explicit justification, a migration plan for in-flight work, and a semantic version bump.
- Every design revision and implementation/review pass rechecks compliance.

## Amendment Log

| Version | Date | Change | Author |
|---|---|---|---|
| 1.0.0 | 2026-08-02 | Initial task constitution | Codex/Batman |
