# Tasks 1–9 Implementation Evidence

Date: 2026-08-01

Scope: shared bounded contracts, mnemo preview retrieval, repository reconstruction,
private state, lifecycle recovery/validation, and Codex/Claude Code adapters. No
customization-layer asset or real host configuration was written.

## Characterization and TDD sequence

- Before mnemo production changes:
  `py -3.12 -m pytest mnemo/tests/test_task_context_characterization.py -q`
  → `2 passed`.
- Before core production modules existed, the new core tests failed with
  `ModuleNotFoundError: context_compaction`.
- Before bounded mnemo serialization existed, the preview tests failed because
  `build_task_context_response` was absent.
- Before Tasks 3–4 production modules existed, their suites failed collection for
  missing `context_compaction.repository`, `.storage`, and `.lifecycle`.
- Before Task 5 production code existed, its suite failed collection for missing
  `context_compaction.adapters`.

## Green evidence

- Focused initial core/mnemo slice:
  `py -3.12 -m pytest mnemo/tests/test_task_context_preview.py mnemo/tests/test_task_context_characterization.py tests/context_compaction/test_budget.py tests/context_compaction/test_models.py -q`
  → `26 passed in 0.57s`.
- Full mnemo suite after the bounded retrieval change:
  `py -3.12 -m pytest mnemo/tests -q`
  → `42 passed in 44.27s`.
- Repository/storage/lifecycle slice:
  `py -3.12 -m pytest tests/context_compaction/test_repository.py tests/context_compaction/test_storage.py tests/context_compaction/test_lifecycle.py -q`
  → `26 passed in 10.82s` before the later process-lock/fail-open additions.
- Adapter parity/security slice:
  `py -3.12 -m pytest tests/context_compaction/test_adapters.py -q`
  → `22 passed in 0.08s`.
- Combined Tasks 1–5 regression before the final hardening additions:
  `py -3.12 -m pytest tests/context_compaction mnemo/tests/test_task_context_preview.py mnemo/tests/test_task_context_characterization.py -q`
  → `74 passed in 12.21s`.
- Process-lock and fail-open hardening slice:
  `py -3.12 -m pytest tests/context_compaction/test_storage.py tests/context_compaction/test_lifecycle.py -q`
  → `20 passed in 12.53s`, including 20 independent writer processes.
- `py -3.12 -m compileall -q context_compaction mnemo\mnemo` → exit 0.
- `git diff --check` → exit 0; only existing Git line-ending notices were emitted.

The only recurring warning is pytest-asyncio's unrelated deprecation notice for an
unset `asyncio_default_fixture_loop_scope`; no feature test failed.

## Current host-contract sources

- Codex hooks: <https://developers.openai.com/codex/hooks>, fetched 2026-08-01.
  Confirmed common snake-case input, unstable `transcript_path`, manual/auto
  `PreCompact` and `PostCompact`, immediate compact-sourced `SessionStart`,
  `hookSpecificOutput.additionalContext`, and
  `hookSpecificOutput.permissionDecision="deny"` for `PreToolUse`. Codex documents
  top-level `continue` as unsupported for `PreToolUse`, so the adapter never emits it
  there.
- Claude Code hooks: <https://code.claude.com/docs/en/hooks>, fetched 2026-08-01
  against installed Claude Code `2.1.220`. Confirmed the same `PreToolUse` denial and
  SessionStart context shapes, manual/auto compact triggers, a 10,000-character hook
  output cap, and Claude-only `PostCompact.compact_summary`. The adapter hashes and
  measures that summary in process, then retains no body.
- Codex installed baseline remains `0.145.0`; Claude Code remains `2.1.220`.

## Boundaries still open

- Task 6 exact customization diff was approved and applied on 2026-08-01. Its
  eight source-asset/budget/pointer tests pass, and the canonical skill passes
  the skill-creator `quick_validate.py` validator. No installed copy was edited.
- Task 7 was completed only in isolated temporary homes. Its TDD red case was the
  missing `context_compaction.activation` module, followed by the intentional
  ownership/allowlist/status tests. Final evidence:
  `py -3.12 -m pytest tests/context_compaction -q`
  → `88 passed in 16.21s`; `py -3.12 -m compileall -q context_compaction` and
  `git diff --check` exited 0. The suite proves read-only planning/status/state
  reads, exact plan-hash approval, conflict/drift refusal, idempotent owned-file
  rollback, base-config preservation, supported-version and tool-coverage
  refusal, bounded metadata-only diagnostics, and separate state purge. Actual
  Codex/Claude homes were not touched.
- Task 8 was implemented test-first. Initial collection failed because
  `context_compaction.benchmark` did not exist. The completed harness validates
  P01–P14 against frozen commit
  `0db30624dd32d814b937aa88b5ec84e18d4b130d`, exact Git blob identities,
  bounded line spans/anchors, and P13's zero-match negative query. It defines the
  two-host, four-mode, eight-fault matrix; source-gated scoring; observed versus
  qualified savings; 30-sample p50/p95/max assembly; and ten-turn anti-thrashing
  gates. `py -3.12 -m pytest tests/context_compaction/test_benchmark.py -q`
  → `8 passed in 33.31s`. The two disposable-worktree tests created P14's only
  dirty paths (`CONTEXT.md` modified and
  `context-pilot-dirty/queued-change.ts` untracked), refused source drift, removed
  the worktrees, and re-proved the active `educode` checkout clean at the frozen
  commit. No reset or stash was used.
- Task 9 closed its deterministic gates with `113 passed` in the latest full context
  suite, `44 passed` against real Qdrant, a passing stdio MCP smoke test, `9
  passed` in the workflow/security/fault aggregate, and a passing 64-cell local
  gate report. The final review also added an absolute hook bootstrap, runtime
  approved-tool inventory enforcement, post-replace rollback coverage,
  pretty-serialized Mnemo envelope accounting, UUID-bounded exact lookup, ACL-safe
  forgetting, sensitive-value rejection, and content-free unexpected CLI errors.
- Tasks 10–12, real host activation, representative `educode` preservation runs,
  and owner acceptance remain open. Focused green tests are not rollout acceptance.
