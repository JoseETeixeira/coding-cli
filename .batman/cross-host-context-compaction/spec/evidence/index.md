# Context compaction evidence index

Date: 2026-08-01

## Evidence labels

- Focused/local and mocked evidence proves deterministic implementation behavior.
- Qualified evidence is a named proxy, never observed host token usage.
- Real-host, representative answer accuracy, and owner acceptance remain separate.

## Implemented deterministic evidence

| Gate | Command/evidence | Result | Label |
|---|---|---|---|
| Core, repository, lifecycle, adapters, contract, activation | `py -3.12 -m pytest -q tests/context_compaction mnemo/tests/test_task_context_characterization.py mnemo/tests/test_task_context_preview.py` | 183 passed in 61.69s | focused/mock |
| Refresh 3 registry guard, activation, security, storage, docs, and workflow | focused guard/activation suite; selected security/docs gate; Ruff | 32 passed in 2.17s; 28 passed in 10.03s; Ruff clean | focused/mock |
| Refresh 4 content-free registry diagnosis | deterministic gates plus one exact approved Claude 2.1.220 cell | 150 full-suite tests green; live guard rejected `feature_state` at 1.051s before trust/counter; exact child stop, registry preservation, two-target disable, and two-event purge passed | focused/mock plus real diagnostic; lifecycle red |
| Frozen preservation harness | `python -m pytest -q tests/context_compaction/test_benchmark.py` | 8 passed in 34.86s; P01-P14, 12 Git objects, 28 spans, P13 zero matches; active `educode` clean | benchmark/focused |
| Workflow/security/fault aggregate | `python -m pytest -q tests/context_compaction/test_workflow_regressions.py tests/context_compaction/test_security_faults.py tests/context_compaction/test_gates.py` | 9 passed in 3.04s | focused/mock |
| Pre-commit safety review | focused regressions plus Ruff | 117 passed in 17.55s; Ruff clean | focused/mock; no host launch |
| Real-Qdrant mnemo suite | `py -3.12 -m pytest -q mnemo/tests` | 48 passed in 30.83s | real service/fake embedder plus focused API |
| Stdio MCP | `py -3.12 mnemo/tests/mcp_smoke.py` | write/search/task_context/get/forget passed through real stdio, OpenAI embedding, and Qdrant | real integration |
| Local gate report | `python -m context_compaction.gates --source-root . --manifest benchmarks/context_compaction/educode-probes.v1.json --educode-repo C:\Users\josee\source\educode` | 64 cells encoded; 30 samples for each of 8 states; worst p95 0.3790 ms; no ten-turn recompact; proxy reduction 70%; manifest `cad1b4497d781010294a060552c8ae67093378ca4ccce52cf7a99a9e1f39a06f` | focused + qualified proxy |

The local performance measurement excludes host-native summarization and real model
answer generation. It is far below the 2,000 ms p95 gate, but it is not a real-host
latency claim.

## Bounds proved

- Re-entry: at most 8,000 Unicode characters and 2,000 deterministic estimated
  tokens; canonical compact prompt is 2,117 characters / 530 estimated tokens.
- Mnemo: 4,000 preview-text characters, 500 per item, and 8,000
  pretty-serialized response characters.
- Diagnostics: newest 200 metadata-only events; no transcript/summary/tool/source
  body persistence. Claude registry per-field fingerprints are process-private;
  persisted drift diagnosis is bounded to seven closed categories.
- Benchmark artifact: at most 32,768 serialized bytes and no answer/source bodies.

## Regression and rollback evidence

- Primary `.codex/config.toml`, `.claude/settings.json`, `hooks/hooks.json`, phase
  checkpoint hook, handoff checkpoint hook, and pointer-first handoff skill match
  their pre-implementation SHA-256 hashes.
- Native behavior with `enabled=false` is non-blocking.
- Partial activation/permission failure removes only newly created files/directories;
  atomic state replacement retains the last good record.
- Generated hooks run from unrelated repository working directories, and any
  runtime tool absent from the approved observable inventory is denied before use.
- Generator `0.1.1` binds every hook command to its expected event, keeps all
  PreCompact failures fail-open, distinguishes uncorrelated Claude compact cycles,
  binds active evidence to repository/version and the latest disable marker, and
  keeps safe pathless reconstruction tools available while material tools remain
  gated. No real host launch used this post-review generator.
- Conflict/drift refusal, concurrent writers, missing/stale/oversized/malformed
  state, memory offline, pending approval, action ambiguity, and replay suppression
  have focused tests.

## Open gates

- Task 10 exact real user-level activation preview reached a green Codex 0.145.0
  manual compact, valid pointer recovery, five-path current-source validation,
  post-validation read, and exact rollback. Refresh 3's real Claude 2.1.220
  semantic guard then rejected `registry_semantic_drift` before trust: the host
  changed protected semantics while `numStartups` and target trust stayed
  unchanged. The exact child stopped, `.claude.json` was preserved, two owned
  targets were disabled, and state was purged. A broader cache exception or
  isolated-config approach requires a new Design/ADR decision and approval.
  An explicitly approved unchanged retry rejected the same way at 1.054 seconds,
  proving the blocker repeatable rather than a one-time cache warm-up. Its exact
  child stopped and owned rollback again passed. Refresh 4's exact approved live
  cell then rejected `registry_semantic_drift` at 1.051 seconds with only closed
  category `feature_state`; `numStartups=30` and target trust stayed absent. The
  exact child stopped, registry was preserved, exactly two targets were disabled,
  and exactly two guard events were purged. Any retry or compatibility exception
  requires a superseding Design/ADR decision and approval.
  `task-10-activation-attempt.md` records all live outcomes.
- Task 11 Codex/Claude manual/automatic/mid-turn real-host matrix: unmeasured.
- Credible host token/body telemetry: unmeasured; only the named 70% character proxy
  exists.
- POSIX and later host versions: unmeasured/inactive.
- Owner review of one long Codex and one long Claude continuation: open.

Nothing in this index authorizes activation or wider rollout.
