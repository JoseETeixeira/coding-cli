---
status: Active
approved: 2026-07-10
owner: FreightHero engineering
task: freighthero-agent-memory-and-repo-local-repowise
requirements_sha256: e9c95aa1ebfa81afaabbd98cf19b87e90e1d3681a35375452398f1a39430c7d6
design_sha256: c7bea2bf1482f37283fc7c4d89f27b70d5395aec685eb7d5eee613ebe8e5b96b
---

# PRD: native, source-only FreightHero agent platform

## Problem

FreightHero agent behavior is duplicated across Claude, Codex, local Copilot,
Batman, user directories, `coding-cli`, FreightHero MCP, CocoIndex, and
generated documentation. Installation and refresh scripts can overwrite local
configuration, retrieval has no shared snapshot identity, and broad
instructions load more skills and tools than a task needs.

## Outcome

`coding-cli` becomes the canonical source repository for prompts,
instructions, static specialist agents, and skills. It ships no task runtime or
model loop. Claude, Codex, and local VS Code/Copilot use their native model
loops and point at the checkout. The maintained FreightHero Repowise fork is
the only installed component and the only repository search, source,
explanation, decision, PRD, and managed-wiki service.

The entry agent classifies a request from compact skill metadata, loads the
smallest relevant skill set and its directly referenced material, checks a
fresh Repowise snapshot, and delegates only to fixed host-native specialists.
Each specialist performs its own scoped Repowise query before repository work.

## Required behavior

- One canonical source copy; no installer-generated prompt or skill bodies.
- Native Claude, Codex, and local Copilot loops; no Deep Agents.js, LangGraph
  controller, provider router, global Node task MCP, Go installer, or second
  task-model loop.
- Static research, planning, implementation, review, and documentation
  specialist roles with equivalent declared capabilities per supported host.
- Repowise freshness and scoped retrieval before repository analysis or
  mutation. Stale, unauthorized, malformed, or unavailable knowledge fails
  closed after one bounded retry.
- PRD plus accepted ADRs before behavior-changing implementation; source
  hashes and lifecycle state are indexed and verified.
- `allowed-tools` metadata is advisory across hosts. Actual security remains
  the native host's fixed tool, sandbox, network, path, approval, and secret
  boundary.
- Only Repowise may receive a scoped OpenAI credential. Task agents use native
  CLI/editor credits and never inherit the Repowise credential.
- Existing safety hooks and unrelated user settings remain intact.

## Acceptance

1. Source validation finds no duplicate canonical identities, broken direct
   references, hardcoded home paths, secrets, installable task runtime, or
   active FreightHero MCP/CocoIndex/OpenWiki dependency.
2. Claude, Codex, and local Copilot fixtures prove source-only activation,
   smallest-skill loading, fixed specialist boundaries, Repowise-first order,
   approvals, rollback, and clean unactivation.
3. Frozen dual-retrieval fixtures meet exact source/ranking/citation thresholds
   before the old retrieval and documentation automation are removed.
4. A clean developer installs only the maintained Repowise fork, adds one
   native source pointer, authenticates, runs a governed task, and removes the
   pointer without unrelated changes.

## Rollout and rollback

Roll out through local development, read-only shadow, dual retrieval, managed
wiki preview, merge-update canary, and full cutover. Each stage retains the
last known good Repowise snapshot and the byte-safe host-config rollback
record. Retirement is blocked until parity passes. Rollback restores the
captured host bytes/modes and reactivates the previous read-only clients; it
never deletes the external GitHub wiki.

## Out of scope

- GitHub cloud Copilot as a canonical asset target.
- Replacing valid AI Watchtower in-application Deep Agent terminology.
- Moving the external GitHub wiki or unrelated MCP servers and packages.
- Direct OpenAI calls from task agents.

## Completion record

Delivered on 2026-07-10. The canonical entry skill, six fixed native-host
agents, normalized prompts/instructions, source-only conformance CI, host
scenarios, activation pointers, and governance gates are implemented. The
frozen 15-case retrieval gate passed with rank-one exact retrieval, 100% top-3
recall, 100% citation identity, conceptual nDCG@5 improving from 0.307 to 0.631,
and lower measured p50/p95 retrieval latency.

Retired Go distribution, FreightHero MCP/CocoIndex, generated host copies,
refresh/patch hooks, and OpenWiki surfaces were removed. The maintained
Repowise fork is the only installed component. The external GitHub wiki remains
unchanged. The previously discovered VS Code bearer value was not copied and
still requires independent rotation by its owner.

## Superseding product amendment: repository-local knowledge and governed memory

Approved on 2026-07-10 under task
`freighthero-agent-memory-and-repo-local-repowise`. This amendment supersedes
the earlier product statements that kept the wiki external or treated a
shared Repowise service/database as team knowledge authority. The historical
completion record above remains evidence of the earlier delivery state.

The product now requires:

- `coding-cli` remains source-only. Claude, Codex, and local Copilot retain
  their native model loops and load only task-relevant canonical skills and
  host-native tools.
- Host configuration is changed only by an explicit, idempotent activation
  command. Install, init, update, and reindex never silently edit host/editor
  configuration or recommend another installation.
- Every Git repository owns one canonical Repowise store: ignored SQLite at
  `<repo>/.repowise/wiki.db` by default or an optional managed repository-local
  PostgreSQL instance. Workspace roots retain routing metadata only.
- One existing `RepoRegistry` resolves every repository context, and one
  atomic publisher keeps SQL, full-text, vector, wiki, ADR, and PRD views on
  the same active snapshot with last-known-good rollback.
- Working, procedural, semantic, episodic, and preference memory retain
  distinct trust/lifetime rules. If a host cannot isolate parent/specialist
  credentials or tools, no agent-facing memory mutation is exposed: parent
  and specialists remain read-only and only authenticated user CLI/UI may
  propose or promote memory. Ordinary file mutation remains governed by the
  independent review protocol.
- Team memory is exchanged only as immutable, reviewed episodic records in a
  repository ledger. Binary/generated database and vector state remains
  untracked. Activation requires trusted-target per-entry membership and
  attestation; invalid, untrusted, or conflicting entries remain inactive,
  with conflicts resolved only by a new immutable resolution.
- Existing wiki pages, ADRs, and PRDs move into each repository as the
  baseline. Covered topics update in place and new files are created only for
  genuinely uncovered behavior.
- Every durable mutation batch has one writer and one independent read-only
  reviewer who checks the full manifest until `PASS` or bounded `BLOCKED`.
  Replacement parity must pass before old retrieval, documentation, or host
  pointers are removed.
- Repowise alone may use its scoped OpenAI credential under ADR 0004's fixed
  `gpt-5.6-sol` primary and `gpt-5.5` fallback policy. Task agents never
  receive or use that credential.

The approved requirements hash is
`e9c95aa1ebfa81afaabbd98cf19b87e90e1d3681a35375452398f1a39430c7d6`;
the approved design hash is
`c7bea2bf1482f37283fc7c4d89f27b70d5395aec685eb7d5eee613ebe8e5b96b`;
the approved implementation-plan hash at authorization was
`d99978dac449458829f159203c2c6899d7a994efd47d025820c02636ecfee8ff`.

Repowise currently serves the `coding-cli` commit
`bf1587fa2cc127aeec400403245a08e951aa6aff` with zero pages; one bounded
index-only retry also returned zero. The approved bootstrap may implement only
the minimum active-snapshot slice needed to make source/search and ADR/PRD
evidence queryable. Work stops before later tasks unless a fresh non-empty
snapshot and these exact governance hashes are verified.

### Governed-memory implementation outcome

The canonical role matrix now makes `repowise-memory` mandatory for every
repository phase and requires shared status plus exact task context before the
normal source query. Repowise provides read-only agent MCP context,
authenticated local-user candidate lifecycle, per-repository ignored stores,
and immutable reviewed episodic interchange with protected-target attestation
and combined-tree CI. No Deep Agents runtime or API-key task-model loop was
added. Generated user-level FreightHero skill/hook/MCP duplicates were removed
so Claude and Codex resolve this source-only checkout.
