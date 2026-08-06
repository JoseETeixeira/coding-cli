# Product Overview

## Product Purpose

`coding-cli` is the canonical, host-agnostic customization and local tooling layer for Codex, Claude Code, Copilot, and related coding-agent hosts. Its `mnemo` subsystem provides two distinct capabilities behind one MCP server: durable cross-agent memory and a rebuildable semantic source-code index.

This task makes the code index safe for concurrent agentic work. Each concrete Git working tree must receive an isolated source cache even when several worktrees or clones share repository history. Durable task memory keeps its existing repository-scoped behavior.

## Target Users

- Repository owner running multiple coding agents in primary checkouts, linked worktrees, and separate clones.
- Codex, Claude Code, and Copilot sessions that use mnemo to locate source before opening current files.
- Maintainers diagnosing whether an empty or stale-looking search result belongs to the active task.

Primary pain points are cross-worktree source contamination, misleading freshness/status, one task suppressing another task's refresh, and unnecessary doubt about whether semantic search reflects the active working directory.

## Key Features

1. **Shared durable memory**: repository-scoped facts, decisions, Batman checkpoints, and handoff pointers remain available across agentic tasks.
2. **Worktree-scoped code search**: semantic source chunks, manifests, status, locks, and refresh state belong to one concrete Git working tree.
3. **Truthful diagnostics**: tools expose enough repository-family, working-tree, and freshness state to distinguish an unindexed/building scope from a populated one.
4. **Safe rebuildability**: interrupted or legacy code-index caches can be rebuilt without changing current source or durable memory.

## Business Objectives

- Eliminate cross-worktree code-search results between concurrent agentic tasks.
- Prevent one working tree from overwriting, deleting, locking, or debouncing another tree's index.
- Preserve repository-wide memory continuity across worktrees.
- Keep mnemo's current MCP tools and deployment topology usable without new services or credentials.
- Make upgrade, rollback, and cache cleanup explicit and non-destructive.

## Success Metrics

- **Cross-scope contamination**: zero hits, counts, timestamps, progress, locks, or manifests attributed across distinct working trees in the acceptance matrix.
- **Same-scope agreement**: all agents and path variants resolving the same working tree derive one code-index scope.
- **Compatibility**: existing memory tests, code-index regressions, and stdio MCP smoke checks pass.
- **Recovery**: interrupted refresh resumes without duplicate chunks; legacy code-index data never becomes queryable as current-scope data.
- **Truthful status**: every tested unindexed, building, current-snapshot, and failed state reports the active working-tree scope without borrowing another scope's state.

## Product Principles

1. **Source decides**: semantic index results locate files; current source remains authoritative.
2. **Share memory, isolate source cache**: existing repository-scoped decisions cross worktrees as they do today; mutable source chunks do not.
3. **Correctness before cache reuse**: losing embeddings is acceptable; returning another task's source is not.
4. **Fail closed on identity**: unresolved working-tree identity cannot fall back to a broader shared partition.
5. **Rebuild, do not mutate repositories**: code indexing stores state in mnemo/Qdrant and does not write into source or Git metadata.
6. **Expose ordinary lag honestly**: same-working-tree asynchronous refresh may lag local edits, but tools must not present another tree's snapshot as current.

## Monitoring & Visibility

- **Dashboard Type**: MCP tool responses and local logs; no new dashboard.
- **Real-time Updates**: `code_index_status` polling for scope identity, state, progress, and last completed snapshot.
- **Key Metrics Displayed**: repository family, working-tree root/scope, indexed files/chunks, last completed index, auto-index state, live progress, and typed errors.
- **Sharing Capabilities**: none; diagnostics remain local and content-minimal.

## Future Vision

The identity model can later support bounded cache garbage collection and richer source-snapshot freshness checks without weakening the repository-family memory contract.

### Potential Enhancements

- **Garbage collection**: safely retire partitions for deleted working trees.
- **Snapshot diagnostics**: compare the last indexed Git/source snapshot with current state without forcing every search to block.
- **Cost visibility**: report rebuild/reuse counts without logging source content.
