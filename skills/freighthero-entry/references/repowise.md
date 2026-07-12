# Repowise evidence boundary

Call `get_index_status(repo)` before repository work. Require a non-empty authoritative snapshot, current freshness, and an expected served commit. Then use:

- `search_codebase`: fused exact, literal, full-text, and vector retrieval.
- `get_source`: bounded exact source bytes and line/byte spans.
- `get_answer`: one-call, source-cited explanation; accept degraded retrieval when citations remain exact.
- `get_context`, `get_symbol`, `get_overview`, `get_why`, `get_risk`: structural, symbol, architecture, decision, and change-risk evidence.

Every material claim retains repository alias, snapshot ID, served commit, path, span, hash, entity kind, retrieval methods, confidence, and freshness.

Fail closed after one bounded retry on stale, empty, unauthorized, malformed, inconsistent, partial, or unavailable responses. Do not replace Repowise with local grep for repository conclusions. Local reads may verify already-cited spans after preflight.

Refresh and re-query after a material branch, commit, worktree fingerprint, or task-scope change. Preview snapshots are owner-scoped and never canonical publication.
