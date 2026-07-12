# Agent platform modernization completion record

Date: 2026-07-10  
Task: `freighthero-agent-platform-modernization`  
Implementation state: locally implemented and activated; immutable release pin pending

## Delivered architecture

- Installed components: one, the editable FreightHero Repowise fork at version `0.30.0`.
- Task model loops: native Claude Code, Codex, and local VS Code/Copilot.
- Canonical agent assets: this `coding-cli` checkout only.
- Repository evidence: authenticated, snapshot-qualified Repowise REST/streamable MCP with mandatory scoped task context and read-only agent memory.
- Managed documentation: local Repowise wiki UI backed by ignored repository-local SQLite/Lance snapshots.
- Models: Repowise-only `gpt-5.6-sol` at `max`, one transient retry, then one `gpt-5.5` fallback at `xhigh`.

GitHub cloud Copilot remains unsupported. The external GitHub wiki remains intact and is no longer an automated publication target.

## Removed surfaces

- `coding-cli` Go CLI, installers, build/release artifacts, runtime tests, and distribution folders
- both FreightHero MCP runtimes and all ignored index, virtualenv, build, cache, and dependency state
- CocoIndex skills, commands, configuration, and session refresh consumers
- Repowise patch/refresh hooks superseded by the maintained fork
- active OpenWiki workflows, generated trees/state, instructions, publication script, and FreightHero-owned global package
- generated user-level Batman/prompt/skill copies and duplicate canonical identities

Unrelated MCP servers, RTK settings, Git safety hooks, archives, other Batman tasks, and unknown user files were preserved. Stale FreightHero-owned generated skills, MCP pointers, and auto-improvement hook registrations were removed so hosts resolve the canonical source-only checkout.

## Governed memory and concurrent developers

Each Git repository owns ignored local SQL/vector state and one tracked
credential-free ledger policy. Task agents can only read current-evidence-first
context and shared trust status. Authenticated local users manage candidates
through the Repowise CLI/REST/UI; preference promotion still requires approved
canonical auto-improvement. Reviewed episodic outcomes can be exported as
immutable RFC 8785 JSON. Protected-target Sigstore membership, combined-tree
CI, explicit conflicts/resolutions, active-snapshot evidence, and the shared
repository writer lock prevent binary-database merges and last-writer-wins
behavior across developer PRs.

## Verification

- Repowise Python: 7,541 tests passed and 26 opt-in tests skipped; the full suite includes server/MCP, publication, migration, governance, repository-routing, schema-lock, memory, and policy coverage.
- Repository-local persistence: SQLite/Lance and managed-PostgreSQL schemas through revision `0047`; atomic snapshot, governed memory, shared-ledger proof identity, managed-membership, ordered-link, active-only search, and rollback-reuse tests pass. Local no-ledger SQLite upgrades are cross-process serialized; stale Alembic ledgers fail closed.
- Live model policy: all four protected OpenAI evaluations passed for primary long context/citations, exact fallback, function tools, and reconciliation quality. The actual dated fallback snapshot is recorded while the requested alias remains fixed.
- Node: all workspace type checks passed; 36 types tests, 45 API-client tests, 587 shared UI tests, 9 web tests, and 4 VS Code extension tests passed (681 total). Build completed with only existing bundle-size, dynamic-import, asset-resolution, and local-storage warnings.
- Retrieval parity: 15 cases passed; exact rank-one `1.0`, top-three recall `1.0`, citation identity `1.0`, conceptual nDCG@5 `0.307 -> 0.631`, final local p50/p95 `1.46/3.58 ms` versus frozen retired-oracle `80.28/280.97 ms`.
- Source/governance: coding-cli source-only validation, 12 native-host scenarios, workspace approval, Repowise governance/provenance, AI Watchtower governance, workflow YAML, and real diff whitespace checks passed. A separate AI Watchtower model-selection subset remains red in four pre-existing expectations: its tests expect the Bedrock default while the current branch routes those agents through OpenRouter `z-ai/glm-5.2`; this modernization did not rewrite that unrelated product behavior.
- Live repository routing: six distinct ignored repository-local SQLite stores each expose one active snapshot; no workspace-root database exists. AI Watchtower serves snapshot `cd85035cb6a6455eac76f414de7710bd` as current with 2,936 captured sources and 22,533 search documents.
- Managed wiki: the active AI Watchtower snapshot contains exactly 40 topics, two aliases, one SVG asset, 270 ordered links, 40 managed search rows, zero duplicate raw search chunks for managed destinations, and one active full-text plus one active Lance projection.
- Loopback smoke: UI and wiki routes return HTTP 200; authenticated memory status/review/audit/search, shared-ledger status, and managed-page reads are snapshot-qualified; promote/hold/release completed against exact active-snapshot evidence; and streamable MCP initializes protocol `2025-06-18` with 22 tools.
- Protected user files remained byte-identical: `coding-cli/skills/create-scenario-tests/SKILL.md` SHA-256 `cce763d235d29cc965094f47dee3d3255a618c2540731114ff4efb658237340f`; `ai_watchtower/CHANGELOG.md` SHA-256 `6650e0d4046a2ee56a8ca6a10de636aee7847682441be94400d60016ba4d6978`.

## Rollout state and remaining operator actions

The local fork and host pointers are installed, and the loopback service is
running in the detached `freighthero-repowise` screen session. No shared binary
database or additional agent runtime is required. Each repository builds its
own ignored state; the workspace service discovers those stores. Shared team
memory travels as reviewed, immutable Git ledger objects, not a merge-prone SQL
file. Local service/auth/trust values were generated only in ignored mode-600
files; no cloud deployment values were invented or committed.

The previously discovered VS Code bearer credential was not copied. Its owner
must rotate it independently before production cutover. Local service values
were provisioned only in ignored files. The user token and policy carry the
exact memory actions plus session issue/revoke; scoped agents receive
short-lived, narrower tokens from the OS keyring. Provider credentials remain
outside agent assets and are used only by Repowise model operations.

The remaining release gate is intentional: all six caller repositories keep
their protected ledger-attestation workflows fail-closed until a reviewed,
immutable Repowise fork commit SHA exists. Pinning a mutable working-tree SHA or
fabricating a release would defeat the supply-chain control. After the fork is
committed and reviewed, replace each placeholder with that exact SHA and enable
the protected workflow/OIDC permissions.

After source changes, run a verified update for each affected repository and
record the resulting active snapshot, protocol version, and served commit.
Host preflight blocks repository work when the loopback service is unavailable
or the selected repository snapshot is stale.

## Rollback point

No commits or pushes were made. The pre-migration repository bases are:

- `coding-cli`: `bf1587fa2cc127aeec400403245a08e951aa6aff`
- `repowise-fork`: `3774409622d6d906874d1a6daf1e2179b5c5832b`
- `ai_watchtower`: `2cd51705b8eecfda3b998bd9dfdde66cfb7f2a46`

Use the byte-safe migration record for changed host configuration. Rollback restores only the captured FreightHero-owned bytes/modes and previous pointers; it does not touch unrelated user settings, credentials, or the external wiki.
