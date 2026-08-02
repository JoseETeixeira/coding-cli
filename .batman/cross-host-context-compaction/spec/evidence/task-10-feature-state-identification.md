# Task 10 — identifying the `feature_state` protected rewrite

Date: 2026-08-02. Method: **read-only, no host launch, no activation, no registry write**.

ADR 0014's diagnostics localized three identical Claude 2.1.220 rejections to one closed
category, `feature_state`, but deliberately retained no field identity. This closes that gap
from the source side instead: the classifier and the installed binary, not the guard's state.

## 1. Which top-level fields the classifier calls `feature_state`

`context_compaction/claude_registry.py:296-325` `_field_category` matched against the **key
names only** of the live registry (61 top-level keys; no values, paths, or bodies read):

    cachedExperimentData
    cachedExperimentFeatures
    cachedGrowthBookFeatures
    cachedGrowthBookFeaturesAt

All four are `cached*`. They land in `feature_state` rather than `cache_state` purely because
the `"feature"`/`"growthbook"` test at `:304` runs before the `"cache"` test at `:306`. The
category is a diagnostic label, so this ordering does not affect guard correctness — but it
did make the family read as product feature state when it is a remote-fetch cache.

## 2. What writes them

Read-only inspection of the exact installed executable
(`C:\Users\josee\.local\bin\claude.exe`, 253.4 MB, not executed). One updater writes all four:

    function Rtu(){ ... hr((n)=>({...n,
      cachedGrowthBookFeatures:e,
      cachedExperimentFeatures:r,
      cachedExperimentData:t,
      cachedGrowthBookFeaturesAt:Date.now()}))}

`cachedGrowthBookFeaturesAt` is `Date.now()` — **unconditional with respect to whether the
flag payload changed**. Two call sites, both guarded on a successful remote evaluation:

    let t = await Itu(e); if (t) ktu(), Rtu(), Yer.emit()

So a fresh timestamp is written on every start whose GrowthBook fetch succeeds.

## 3. Why the guard is correct and R7.7 is unsatisfiable in practice

`_protected_value` (`claude_registry.py:273-282`) exempts exactly `numStartups` and the
matched target project subtree. ADR 0013:38-51 admits only `numStartups + 1`, one new trusted
project subtree, and canonical semantic identity for everything else. R7.7
(`requirements.md:184`) says the same.

A monotonically re-stamped `Date.now()` in a protected top-level field cannot satisfy
"canonically semantically identical". The three rejections at 1.055 s / 1.054 s / 1.051 s are
the contract working as approved, not a defect in the guard.

Honest scope: only the third cell recorded a category (`task-10-activation-attempt.md:433`).
The two earlier cells predate ADR 0014 and recorded none. Attributing all three to this family
is a well-supported inference from matching timing and shape — not an observation.

## 4. The lever, and what is *not* yet proven

The binary carries an env gate immediately after the updater:

    function die(){return !Z.DISABLE_GROWTHBOOK && uie()}

`DISABLE_GROWTHBOOK` appears 19 times, including in the host's own environment-variable list.
Setting it in the pilot child's process environment is the obvious way to stop the write at
source, keeping ADR 0013 and R7.7 completely untouched.

**Not proven, and it must be before anything is launched:** that `die()` actually gates the
path reaching those two `Rtu()` call sites, and that no *other* protected top-level field is
re-stamped on startup. The same classifier run shows `protected_top_level` (26 members)
already contains `changelogLastFetched`, `closedIssuesLastChecked`, `routineFiredWatermark`,
and `firstStartTime` — each with its own timestamped writer. Suppressing GrowthBook may simply
move the rejection to the next family.

The cheap, launch-free way to settle both is now implemented as
`context_compaction/registry_census.py`. It reuses the guard's own `_snapshot` /
`_protected_field_fingerprints` / `_field_category` helpers, so a clean census means the
guard would also have been clean. It writes nothing, launches nothing, and activates
nothing — the **owner** drives the host.

## Census runbook (owner-driven, nothing is activated)

Run each cell from this checkout. Nothing else needs to be enabled.

**Cell A — baseline, flags as they are.** In terminal 1:

    py -3.12 -m context_compaction.registry_census --duration 120 \
      --repo "C:/Users/josee/source/educode.context-pilot"

In terminal 2, within those 120 s: start Claude natively, let it reach the prompt, exit.

**Cell B — with the lever.** Same census command, but start Claude in terminal 2 with
`DISABLE_GROWTHBOOK=1` in its environment:

    $env:DISABLE_GROWTHBOOK=1; claude      # PowerShell
    set DISABLE_GROWTHBOOK=1 && claude     # cmd

Run each cell two or three times — the updater only fires when the remote fetch succeeds,
so a single clean run proves nothing.

Read the result as: `REJECT` lines list the exact protected fields that moved and would
have failed the guard. Exit status 0 means no protected drift at all. `numStartups` and
the target project subtree are exempted exactly as ADR 0013 exempts them, so anything the
census prints is real drift, not approved delta.

- Cell A rejecting on the four `cached*` fields and Cell B clean → the lever works, and
  Option "env lever + one supervised cell" becomes concrete and testable.
- Cell B still rejecting → the named field is the *next* blocker, and suppressing
  GrowthBook only moves the problem. That is the signal to stop and take the Codex-only
  path rather than open an exemption ratchet.

Self-verification for the tool itself: it re-read the live registry across a 4 s window
and left it byte-identical at
`e59e1a0faf893910017c458f5b0d7aabb9312c21388cd1938292efd6311dba53`, reporting the recorded
`numStartups=30` baseline. Offline coverage is in
`tests/context_compaction/test_registry_census.py` (5 tests: the GrowthBook timestamp the
guard rejects, the exempt startup counter, the exempt target subtree, torn reads, and
read-only behavior).

## 5. Decision status

Task 10 remains **red/open**. This artifact is evidence only. A category or field exemption,
an env lever in the generated activation, `CLAUDE_CONFIG_DIR` redirection, or any new live
cell each still require a superseding Design/ADR decision and explicit owner approval
(ADR 0013:84-87).
