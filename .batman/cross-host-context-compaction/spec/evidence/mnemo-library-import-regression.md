# mnemo library-import regression (Task 2 defect, found while opening Task 10)

Date: 2026-08-02. Status: **fixed, deterministic-green**.

## Defect

`mnemo/mnemo/engine.py` gained a bare `from context_compaction.budget import truncate_text`
when Task 2 adopted the canonical shared budgeter. `context_compaction/` lives at the
repository ROOT, one level above the `mnemo` package, so that import resolves only when the
root is on `sys.path`. Only `mnemo/run_server.py:10-13` injects it.

Every importer that embeds mnemo as a **library** therefore raised
`ModuleNotFoundError: No module named 'context_compaction'`. CPython prepends the *script's*
directory to `sys.path`, never the cwd, so the failure was independent of working directory —
including inside the coding-cli checkout itself.

Three host surfaces, all registered in `C:\Users\josee\.claude\settings.json`, were down:

- `SessionStart` mnemo preflight (`~/.claude/hooks/mnemo-preflight.py`) — reported
  `UNAVAILABLE` and degraded to the shared-memory skill's no-memory fallback. Visible.
- `PostToolUse` `.claude/hooks/batman-phase-checkpoint.py` — **silent**.
- `PostToolUse` `.claude/hooks/batman-handoff-checkpoint.py` — **silent**.

The mnemo MCP server was never affected (`run_server.py` injects the root), and Codex was
never affected (it reaches mnemo only through that entrypoint). The blast radius is exactly
"every hook-driven mnemo entrypoint", not "mnemo".

## Why the silent half is worse than the visible half

Both checkpoint hooks put the mnemo import inside `find_prior()` and wrap the call in
`except Exception: prior = None` (`batman-phase-checkpoint.py:213-218`,
`batman-handoff-checkpoint.py`). That fallback exists for "mnemo down/unreachable". An
`ImportError` took the same branch, so the hook then emitted:

> 4. No prior checkpoint exists for this slug and phase -- no memory_forget needed.
> This is the first write.

The paired `memory_forget` was dropped, leaving two live `active` items per slug+phase —
the exact state the hook's own text forbids ("Never leave two `active` items for the same
slug and phase"). This is durable-memory corruption, not a missing feature.

Reproduced read-only with one identical payload:

- as the host invokes it → `"No prior checkpoint exists ... This is the first write."`
- with the repository root on `PYTHONPATH` → `memory_forget(memory_id="f1dadd8a-82a3-4ba1-b28d-ab160703e3a8", ...)`

## Window

Introduced with the pilot (`git log -S "from context_compaction.budget"`), landed on `main`
as `9394462`, and went live on this machine when the main checkout fast-forwarded at
2026-08-02 07:19:20 -0300 (`git reflog show main`). Every Claude Code session on this box
after that time lost its memory preflight and both Batman checkpoints.

## Why the approved gates did not catch it

- `mnemo/tests` passes only because `py -3.12 -m pytest` prepends the cwd (the repository
  root) to `sys.path`. Run from a neutral cwd against absolute paths, the same suite died
  with **3 collection errors**, all on `engine.py`'s line 28.
- `tests/context_compaction/test_workflow_regressions.py` hardcoded
  `hook.build_context(target, None)`, so `find_prior()` — the only function holding the
  broken import — was never invoked. The gate that owned R12.1 excluded the defect by
  construction.
- Its sibling gate hashed protected assets with `read_bytes()`. The repository has no
  `.gitattributes` and this machine uses `core.autocrlf=true`, so the gate measured the
  checkout's line endings, not the asset: it was already failing in the main checkout on
  three files whose content was identical.

Approved requirement violated: **R12.1** (`requirements.md:277`) — "WHERE Batman approval
gates, mnemo phase checkpoints, or handoff pointer rules apply, the pilot SHALL preserve
their existing authority, timing, and provenance requirements." Task 9's verification bullet
(`tasks.md:149`) claimed these were "available and semantically unchanged"; they were not.

## Fix

`mnemo/mnemo/engine.py` resolves the repository root from `__file__` before importing the
budgeter, mirroring the pattern already used by `mnemo/run_server.py:10-13` and
`context_compaction/hook_entry.py:8-10`.

One deliberate deviation from those two: the root is **appended**, never inserted at
position 0. Entrypoints own their process and may shadow; a library imported into host hook
processes we do not own may not. The repository root also contains `tests/`, `hooks/`, and
`docs/`, any of which would shadow a same-named module for the host.

The canonical single budgeter required by ADR 0012 is preserved — the budgeter was neither
forked, vendored, nor relocated.

## Verification

- Red first: the new regression fails against the unfixed `engine.py`
  (`ModuleNotFoundError` at line 28) and passes after the fix.
- `tests/context_compaction` — **170 passed** (167 before, plus 3 new).
- `mnemo/tests` from the repository root — **48 passed**.
- `mnemo/tests` from a neutral cwd against absolute paths — **48 passed**
  (previously 3 collection errors). This is the assertion that matters.
- stdio MCP smoke (`status`/`write`/`search`/`task_context`/`get`/`forget`) — **PASS**.
- `ruff check` on changed paths — clean. `git diff --check` — clean.
- End-to-end: the real `find_prior()` against the worktree returns the live Phase 4
  checkpoint `f1dadd8a-82a3-4ba1-b28d-ab160703e3a8` again. The supersede target is back.

New coverage in `tests/context_compaction/test_workflow_regressions.py`:

- `test_mnemo_stays_importable_as_a_library_with_only_its_package_root_on_sys_path` —
  subprocess under `-P` (no script dir, no cwd on the path) with only `<repo>/mnemo`
  inserted, reproducing the hooks' real resolution environment.
- `test_phase_checkpoint_names_the_supersede_target_when_a_prior_checkpoint_is_live` and
  the handoff equivalent — the branch the swallowed `ImportError` skipped.
- The protected-asset gate now hashes newline-normalized text, so it measures the asset
  rather than the checkout, and agrees across the worktree and the main checkout.

## Deployment note

Every host registration pins the **main** checkout — `~/.claude/settings.json`,
`.mcp.json:6`, `.codex/config.toml:3`, `.vscode/mcp.json:6` all point at
`C:/Users/josee/source/coding-cli`. The fix has no runtime effect on this machine until it
lands there; until then the preflight and both checkpoint hooks stay degraded.
