# Context compaction pilot rollback

Rollback is host activation removal plus an optional, separate private-state
purge. It is not conversation, memory, artifact, or source deletion.

## Owned activation set

The generator currently owns only these self-hashed files:

- Codex profile: `$CODEX_HOME/context-pilot.config.toml`
- Codex allowlist: the application-data
  `coding-cli/context-compaction/codex.allowlist.json`
- Claude overlay: the application-data
  `coding-cli/context-compaction/claude-context-pilot.settings.json`
- Claude allowlist: the application-data
  `coding-cli/context-compaction/claude.allowlist.json`

Git repositories keep private state at Git's resolved
`coding-cli-context-pilot` path. Non-Git fallback state is keyed by the canonical
repository-root hash beneath the pilot application-data state directory. A
sibling process-lock file is pilot-owned and removed by purge.

## Rehearsal

1. Capture byte hashes of primary Codex/Claude configuration and unrelated hooks.
2. Run content-free `status`.
3. Run `disable --host <host>`. If ownership/hash drift is reported, stop; do not
   manually delete the file.
4. Verify the primary configuration and unrelated hashes are byte-identical.
5. Start the host normally, without the pilot launcher/profile, and confirm native
   `/compact` and fresh-session behavior remain available.
6. If private pilot state should also be removed, run `purge-state --repo <exact
   repository>`. Unknown entries make purge refuse.
7. Verify source status, Batman artifacts, handoff files, transcripts, and mnemo
   records are unchanged.

`disable` is idempotent. If valid private state already exists, disable appends a
content-free marker so historical host events cannot mark replacement activation
files active. State purge is intentionally not implied, allowing an operator to
disable/review before disposal. Never use broad recursive deletion; the CLI
resolves and ownership-checks the exact target.

## Recovery from failed enable

Enable writes atomically. If a later target fails, files created by that attempt
are hash-checked and removed, and newly created empty pilot directories are
removed. Pre-existing or drifted content is never overwritten. Re-run a read-only
plan after resolving the external cause; its new hash needs approval.

## Current rollout state

Source, temporary-home, worktree, and deterministic rollback tests are green.
Codex 0.145.0 real user-level rollback removed exactly its two pilot targets,
separately purged state, and preserved all three recorded primary configuration
hashes on 2026-08-01. Claude 2.1.220 removal also deleted exactly its two owned
targets and separately purged state, but startup rewrote host-owned
`~/.claude.json` before any trust input. That file was preserved, not reverted;
Refresh 3 subsequently approved and implemented a content-free semantic guard.
Its real launch rejected a protected startup-cache semantic change before trust,
stopped only the exact Claude child, preserved the changed registry, removed the
two owned activation targets, and purged only pilot state. Owned-target rollback
is observed; registry preservation and Claude lifecycle activation remain
red/open.

One owner-approved unchanged retry reproduced the protected semantic drift at
1.054 seconds. Exact child termination, two-target disable, and separate state
purge passed again; the host-owned registry was preserved at its new hash. This
confirms rollback but does not make activation green.

Refresh 4's ADR 0014 implementation changes only rejected-event diagnosis:
process-private field fingerprints become closed content-free categories. It
does not change accepted registry semantics, exact-child termination, disable,
purge, or no-revert behavior. One owner-approved live cell reported
`feature_state` at 1.051 seconds, stopped the exact child, preserved the changed
registry, removed exactly two owned targets, and separately purged both guard
events. Primary Codex/Claude settings stayed byte-identical; activation remains
red/open.
