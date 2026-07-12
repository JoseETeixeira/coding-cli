---
status: Accepted
date: 2026-07-10
scope: coding-cli
task: freighthero-agent-memory-and-repo-local-repowise
requirements_sha256: e9c95aa1ebfa81afaabbd98cf19b87e90e1d3681a35375452398f1a39430c7d6
design_sha256: c7bea2bf1482f37283fc7c4d89f27b70d5395aec685eb7d5eee613ebe8e5b96b
supersedes: []
superseded_by: []
---

# ADR 0002: govern native agents with repository-local knowledge and memory

## Status

Accepted on 2026-07-10. This decision extends ADR 0001; it does not replace
native host model loops or the source-only `coding-cli` boundary.

## Context

Native Claude, Codex, and local Copilot agents need task-relevant skills,
repository evidence, and durable learning without loading every tool or
sharing merge-prone databases. The prior platform delivery made Repowise the
retrieval service, but its shared PostgreSQL authority, external wiki
boundary, and ambient host setup do not satisfy repository ownership,
multi-developer PR safety, or scoped agent memory.

## Decision

`coding-cli` remains a repository of canonical prompts, instructions, static
agents, skills, validation fixtures, and governance only. Native hosts keep
their own model loops, sandboxes, approvals, tools, and credits. The entry
agent selects the smallest sufficient skill set, obtains current
snapshot-qualified Repowise evidence, and delegates only to fixed specialists.

Host setup is an explicit idempotent activation command. Ordinary Repowise
install, init, update, and reindex commands do not mutate Claude, Codex,
Copilot, or editor configuration.

Every durable file-mutation batch has exactly one writer and one independent
read-only reviewer. The same reviewer checks error closure, duplication,
architecture, security, compatibility, tests, documentation, and unrelated
artifacts through revision until `PASS` or bounded `BLOCKED`.

Repowise owns repository-local knowledge and governed memory under its ADR
0005. Agent memory is read-only wherever the host cannot isolate credentials
or tools: parent and specialists receive no proposal/promotion capability, and
only authenticated user CLI/UI may mutate memory. This restriction does not
replace the independent review protocol for ordinary repository files.

Repowise alone may use its scoped OpenAI credential under its fixed model
policy. Task agents never receive or invoke that credential.

## Alternatives

- A shared Deep Agents or LangGraph controller: rejected because it creates a
  second task-model loop and credential boundary.
- A workspace/global knowledge database: rejected because repositories lose
  ownership and developers must merge or coordinate mutable shared state.
- Prompt-only mutation review: rejected because review identity, scope, and
  results must be represented and tested as explicit host contracts.
- Automatic host configuration during install/indexing: rejected because it
  creates surprising, duplicate, and machine-specific artifacts.

## Consequences

Developers install only Repowise and point supported native hosts at the
source checkout explicitly. Repository evidence, wiki, ADRs, PRDs, and memory
remain repository-scoped. Capability isolation is honest about host limits,
and unsupported hosts degrade memory mutation to authenticated human actions.
The workflow depends on current Repowise evidence and stops when the active
snapshot is empty, stale, unauthorized, or hash-mismatched.

## Rollout and rollback

The approved bootstrap starts from Repowise commit
`bf1587fa2cc127aeec400403245a08e951aa6aff`, currently reporting zero pages
after one index-only retry. It may implement only the minimal active-snapshot
path, then must prove non-empty current source/search plus exact ADR/PRD hashes
before continuing. It does not claim that this decision is indexed yet.

Later rollout activates explicit host pointers and repository stores only
after parity. Rollback retains the last-known-good snapshot and restores
captured host configuration without touching unrelated settings.

## References

- Product record: `docs/product/agent-platform-modernization-prd.md`
- Repowise storage authority: `repowise-fork/docs/architecture/adr/0005-repository-local-stores-and-governed-memory.md`
- Approved Batman task: `freighthero-agent-memory-and-repo-local-repowise`

## Implementation outcome

Implemented locally. Every parent and fixed specialist now requires the
`repowise-memory` procedure, shared-ledger status, scoped task context, and a
fresh source query before repository work. Agent MCP remains read-only;
authenticated local users own candidate mutation. The same-writer/reviewer
loop, named `grill-me` and visual procedures, canonical auto-improvement, and
source-only host pointers are machine-validated. Seven Git repositories have
credential-free repository-local memory/ledger policy and combined-tree
attestation workflows; generated databases and vectors remain ignored.
