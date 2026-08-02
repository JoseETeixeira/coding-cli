# Context compaction pilot compatibility

| Surface | Admitted version/state | Isolation mechanism | Current evidence |
|---|---|---|---|
| Codex CLI | exactly `0.145.0` | `$CODEX_HOME/context-pilot.config.toml`, selected with `--profile context-pilot` | focused/mock green; real manual trust, valid recovery, source validation, post-validation read, and rollback observed |
| Claude Code | exactly `2.1.220` | additional settings JSON plus launcher arguments/environment, ADR 0013 semantic registry guard, and ADR 0014 content-free drift categories | focused/mock guard green; two Refresh 3 starts rejected protected drift; one Refresh 4 real diagnostic cell rejected `feature_state` at 1.051 seconds before trust, then exact rollback passed; compaction lifecycle remains real host unmeasured/open |
| Windows | Python 3.12, Git worktree, Windows file lock | native PowerShell/Win32 paths; no WSL required | deterministic and frozen-worktree gates green |
| POSIX | standard-library `fcntl` path exists | same semantic core | unmeasured in this pilot cycle |
| mnemo | local Qdrant on `127.0.0.1:1337`, response contract v2 | bounded previews plus explicit `memory_get` | real Qdrant engine and stdio smoke green |
| Later host versions | unsupported | activation refusal | `0.146.0` observed and correctly kept inactive |

Current source generator is `0.1.1`. All real-host rows above came from consumed
historical `0.1.0` plans. The `0.1.1` safety hardening is deterministic-test green
but has no real-host launch evidence; future activation must start from a fresh
read-only plan and explicit approval.

## Native setting map

| Concern | Codex | Claude Code |
|---|---|---|
| Canonical compact policy | `experimental_compact_prompt_file` | `--append-system-prompt-file` |
| Automatic seed | `model_auto_compact_token_limit=64000` with `body_after_prefix` | process-local 100,000 window and 80-percent override |
| Tool-output seed | `tool_output_token_limit=12000` | no false equivalent asserted |
| Hook layer | profile `[hooks]` with hooks feature enabled | settings-overlay `hooks` |
| Pilot-local unobservable-tool restriction | profile disables web search, connector apps, image generation, browser/computer use, and skill dependency installation | overlay/launcher deny `WebFetch,WebSearch`; other tools remain hook-observable |
| Enabled state | `enabled_unobserved` until a trusted hook event is recorded; then `active` | `enabled_unobserved` until a trusted hook event is recorded; then `active` |
| Primary user configuration | not edited | not edited |

Claude's host-owned `~/.claude.json` is not a pilot activation target. Normal
Claude startup/trust writes are permitted only under ADR 0013's first-cycle
semantic guard and are never reverted by the pilot. ADR 0014 keeps per-field
fingerprints process-private and exposes only closed field-family categories; it
does not add an allowed mutation.

The restrictions above narrow only the pilot layer. They do not grant tools,
network, sandbox exceptions, approvals, credentials, or repository scope. Existing
host hooks/settings continue through native configuration precedence; overlap or
uncovered write capability is a visible activation conflict.

## Compatibility change rule

Host hook/config contracts are version-sensitive. A new version, operating system,
model/context class, plugin packaging path, or repository allowlist requires a new
read-only plan, source-backed compatibility review, affected deterministic tests,
real-host matrix cell, rollback rehearsal, and explicit approval. Do not widen the
version tuple to bypass an inactive result.

Current host contracts were checked on 2026-08-01 against the official Codex hooks
documentation and Claude Code hooks documentation. The operator evidence index
records what was observed versus mocked or unmeasured.
