# 0013 — Semantically guard Claude's host-owned registry

Status: accepted · 2026-08-01

## Context

ADR 0010 requires isolated pilot activation without rewriting primary user
configuration. Real Claude Code 2.1.220 startup showed an important ownership
distinction: before trust input or a lifecycle event, Claude itself rewrote
`~/.claude.json`. Requiring byte identity makes observed Claude activation
impossible, while snapshotting, restoring, or synthesizing this registry would
make the pilot an owner of host state that can contain credentials, caches, and
unrelated project records.

The approved pilot still needs to prove that normal startup and directory trust
did not alter unrelated registry semantics. It also must not persist the
registry body merely to compare it later.

## Options considered

1. **Keep an exact-byte invariant.** Simple and strict, but every ordinary Claude
   startup can fail the pilot before trust is reviewed.
2. **Copy, rewrite, or restore the registry.** Could manufacture byte stability,
   but broadens pilot ownership into sensitive host state and can erase concurrent
   changes.
3. **Use a content-free semantic manifest and live guard (chosen).** Hash all
   protected semantics, permit only the reviewed host-owned startup/trust delta,
   monitor while the exact child runs, and never revert the file.

## Decision

The pilot never writes, copies, or restores `~/.claude.json`. Immediately before
launching the exact Claude child, it parses the current registry in memory using
duplicate-key and size checks and records only a bounded manifest of counts and
hashes. While the child runs, a file-change monitor validates every observed
rewrite and terminates only that child if protected semantics drift.

For the approved initial trust cycle, the only accepted final semantic changes
are:

- integer `numStartups` increases by exactly one;
- exactly one new project subtree uses the canonical allowlisted repository key
  and contains `hasTrustDialogAccepted=true`; and
- every other top-level value and pre-existing project remains canonically
  semantically identical, regardless of JSON serialization changes.

The target project may be temporarily absent between startup and interactive
trust. It must be present and trusted when the host exits. A pre-existing target,
case-variant duplicate, missing trust, malformed registry, counter mismatch, or
any protected semantic change fails with `host_registry_drift`. The changed file
is preserved for owner inspection; no rollback is attempted.

The launcher sets Claude's working directory to the allowlisted repository.
Content-free `captured`, `validated`, or `rejected` guard events share existing
bounded private-state retention and purge. They do not count as compaction
lifecycle activation evidence.

## Consequences

- ADR 0010's no-rewrite guarantee now distinguishes pilot writes from normal
  host-owned registry writes; its native-compaction and bounded-rehydration
  decisions remain unchanged.
- Existing settings, projects, credentials, and caches are covered by one
  semantic hash without being persisted in pilot state.
- First-cycle trust is deliberately one-shot: a pre-existing target requires a
  new reviewed rule rather than silently widening this exception.
- Live monitoring adds small local file-stat/hash work only after the registry
  changes; it adds no service or telemetry.
- Windows Terminal top-level windows are never closed programmatically. Live
  tests use an owner-created terminal or separately approved dedicated console
  and stop only exact host/manager/shell child processes.

## Observed rollout result

The first guarded real launch on Claude Code 2.1.220 rejected
`registry_semantic_drift` about 1.055 seconds after child start, before trust or a
startup-counter increment. The exact child stopped; the changed registry was
preserved; activation disable and state purge succeeded. Content-free evidence
showed unchanged `numStartups=30`, absent target trust, and a changed protected
semantic hash.

Read-only inspection of the exact installed executable shows its bootstrap may
persist model/client cache fields before a later `numStartups + 1` write. Because
the baseline body and per-field values were intentionally not retained, this
does not identify the exact changed field. Allowing any cache family, deferring
validation, or redirecting `CLAUDE_CONFIG_DIR` would change this decision and
requires a superseding Design/ADR approval before another launch.

The owner later approved one unchanged retry against the preserved warmed
baseline. It rejected `registry_semantic_drift` again after 1.054 seconds with
the same byte count, a changed protected semantic hash, `numStartups=30`, and no
target entry. Content-free fingerprints for the previously suspected client,
model, auto-compact, and OAuth cache families stayed unchanged. This rules out a
one-time warm-up and leaves the exact protected field unidentified. No third
launch is authorized under this ADR.

## Rollout and rollback

The guard exists only for the approved Claude pilot process. Disabling activation
still removes only the overlay and allowlist; purging state removes only bounded
guard/lifecycle diagnostics. `~/.claude.json` and `~/.claude/settings.json` are
never rollback targets.
