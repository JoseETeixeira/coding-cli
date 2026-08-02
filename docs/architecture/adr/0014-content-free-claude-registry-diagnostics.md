# 0014 — Diagnose Claude registry drift without persisting field identity

Status: accepted · 2026-08-01

## Context

ADR 0013 protects Claude Code's host-owned registry with one aggregate semantic
hash. Two real Claude 2.1.220 starts changed that hash before trust or
`numStartups + 1`; both were stopped and rolled back without reverting the
registry. The unchanged aggregate result says protected state moved but cannot
identify which field family moved. Persisting the registry body, raw field names,
or one stable hash per field would make diagnostics a new host-state index and
could expose sensitive schema or correlation signals.

Refresh 4 needs enough bounded evidence to choose a later compatibility rule
without weakening ADR 0013. It does not approve any new registry mutation or
another live launch.

## Options considered

1. **Keep only the aggregate hash.** Safest metadata surface, but repeated
   failures remain unlocatable and invite unsupported broad exceptions.
2. **Persist raw changed names, values, or per-field hashes.** Precise, but creates
   a durable index of host configuration and can leak arbitrary user-chosen keys
   or stable sensitive-state fingerprints.
3. **Compare per-field hashes only in process and persist closed categories
   (chosen).** Localizes the field family while keeping names, values, paths, and
   per-field hashes ephemeral.

## Decision

At capture, the guard canonicalizes each protected top-level value after removing
the approved `numStartups` field and exact target-project subtree. It retains one
field-to-SHA-256 map only inside the live guard object. This private map is never
included in a manifest, event, status response, exception string, log, or memory
record.

When the aggregate semantic hash changes, the guard compares current and baseline
maps and converts changed field names to a sorted unique set drawn only from:

- `existing_project_state`
- `cache_state`
- `authentication_metadata`
- `feature_state`
- `usage_state`
- `ui_state`
- `protected_top_level`

Known schema names and conservative name patterns select the first six
categories. Every unknown, malformed, or unsafe name collapses to
`protected_top_level`; raw names are never emitted. The category list is bounded
by the seven-value vocabulary.

The guard still raises `registry_semantic_drift`, the activation manager still
terminates only the exact Claude child, and `.claude.json` is still preserved
without revert. Categories diagnose rejection only. They cannot authorize,
ignore, or normalize a registry change.

## Consequences

- A later exact preview can distinguish existing-project, cache,
  authentication, feature, usage, UI, and unknown protected drift without
  retaining host values or identities.
- Persistent state gains one bounded `changed_field_categories` list; absence or
  an empty list remains valid for non-semantic rejection causes.
- Unit and security tests must prove raw field names, project paths, values, and
  per-field hashes never enter manifest, event, status, error text, or state.
- ADR 0013's allowed semantics, fail-closed behavior, exact-child termination,
  and no-revert rule remain unchanged.
- This ADR authorizes source, tests, and documentation only. Any live diagnostic
  run requires a separately approved exact activation preview.

## Rollout and rollback

The diagnostic map is process-local and disappears when the guard exits.
Disabling activation and purging state retain their ADR 0013 behavior. Removing
the additive category field later requires no host-state migration; older events
without it remain readable.
