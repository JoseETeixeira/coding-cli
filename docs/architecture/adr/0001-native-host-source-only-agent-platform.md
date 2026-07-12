---
status: Accepted
date: 2026-07-10
scope: coding-cli
task: freighthero-agent-platform-modernization
requirements_sha256: b9dea9f43cc406f69aec3fe94d984aacc7d84c2826d6d91ef4d79c6b0fec08e1
design_sha256: 9a64134edd149a49bce5b79f2aad44f9449c511187d02cfe74728bb31a98e05e
supersedes: []
superseded_by: []
---

# ADR 0001: use native host loops and source-only agent assets

## Status

Accepted on 2026-07-10.

## Context

FreightHero currently distributes agent behavior through generated copies and
host-specific refresh code. A proposed shared Deep Agents.js controller would
centralize orchestration but would also introduce a second task-model loop,
another installed runtime, provider credentials, and an authorization layer
whose guarantees differ across Claude, Codex, and Copilot.

## Decision

`coding-cli` contains only canonical prompts, instructions, skills, static
specialist definitions, validation fixtures, and documentation. It does not
ship an executable task orchestrator or installer.

Claude, Codex, and local VS Code/Copilot retain native model-loop ownership.
Each host activates the canonical checkout through its smallest supported
pointer. A shared entry skill performs metadata-first selection and delegates
to fixed research, planning, implementation, verification, and documentation
specialists. Host adapters declare equivalent intent and capability
boundaries, while the host's native sandbox and approvals remain authoritative.

Repowise is the mandatory first repository evidence boundary for the entry
agent and every specialist. Instruction/evaluation conformance enforces order;
we do not claim middleware or cryptographic enforcement where a host exposes
only prompt-level control.

## Alternatives

- Deep Agents.js or LangGraph controller: rejected because it adds a second
  model loop, API-key routing, installation, and overlapping authorization.
- Generated per-host copies: rejected because identities drift and refresh
  code mutates user configuration.
- One unrestricted general agent: rejected because it loads unnecessary
  context and makes capability boundaries ambiguous.

## Consequences

Task calls use native CLI/editor credits, activation is inspectable, and one
source edit reaches all hosts. Capability parity requires fixtures because
host metadata is not a portable security boundary. Unsupported GitHub cloud
Copilot remains explicit. The Repowise service becomes a hard dependency for
repository work and must provide fresh, authenticated, snapshot-qualified data.

## Rollout and rollback

Activate pointers in shadow before deactivating old discovery paths. Preserve
byte-level configuration backups and unrelated settings. A failed host or
retrieval gate restores the previous pointer/config bytes and keeps the old
read-only oracle until parity is re-established.

## References

- Product record: `docs/product/agent-platform-modernization-prd.md`
- Batman task: `freighthero-agent-platform-modernization`

## Implementation outcome

Implemented in Tasks 15 through 21. `coding-cli` now contains only canonical
source assets, governance, fixtures, and documentation. The Go distribution,
local FreightHero MCP/CocoIndex runtime, installer/build/release surfaces,
refresh/patch hooks, generated user-level bodies, duplicate Batman identities,
and active OpenWiki dependencies were retired after the frozen retrieval gate
passed.

Claude uses the repository plugin directory, Codex uses the workspace entry
pointer, and local VS Code/Copilot uses canonical discovery paths. All three
retain native model-loop ownership and route repository evidence through the
authenticated Repowise service. Host scenarios verify freshness-first order,
smallest-skill loading, fixed specialists, native approvals, failure closure,
and clean unactivation. GitHub cloud Copilot remains unsupported as decided.
