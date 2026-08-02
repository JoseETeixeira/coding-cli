# Task 10 exact real user-level activation preview

Date: 2026-08-01

Status: **Refresh 2 completed the Codex manual lifecycle; Refresh 3 safely
rejected two real Claude startups at the semantic preservation gate; Refresh 4
diagnosis rejected one exact approved live cell with `feature_state`, then exact
rollback passed**. The four proposed targets are absent. See
`task-10-activation-attempt.md` for all Claude red gates, exact owned-target
rollback, and Refresh 4 deterministic evidence.

Post-Refresh-4 pre-commit review advanced the source generator to `0.1.1` and
changed per-event hook commands. The embedded `0.1.0` contents and hashes below
remain historical evidence for the consumed live cells; they are not a current
or reusable activation plan. Any future launch requires a fresh read-only plan,
superseding approved strategy where required, and explicit approval.

## Frozen scope

- Allowlisted repository only:
  `C:\Users\josee\source\educode.context-pilot`
- Frozen commit: `0db30624dd32d814b937aa88b5ec84e18d4b130d`
- Repository fingerprint:
  `74ab18671983692d54b0bfabf8e7ac4f7c133bdf466c80a8680a57c0534e4c43`
- Current task slug: `agentic-development-workbench` (Refresh 2 correction)
- The isolated checkout and active `C:\Users\josee\source\educode` checkout are
  both clean at the frozen commit.
- No other repository, user, host version, OS, or default rollout is included.

## Preserved primary configuration

These files are outside the owned mutation set and must remain byte-identical
through enable, lifecycle exercise, disable, and purge:

| File | Bytes | SHA-256 |
|---|---:|---|
| `C:\Users\josee\.codex\config.toml` | 4,130 | `7f0ee4673abfe45c36cad051f7f77fbd1e63300f1776b097f0d5d7f58ee8178c` |
| `C:\Users\josee\.claude\settings.json` | 22,282 | `fc4451db75e7f13562a1ef043424bcd8d417848878f11a74eb53c5cb7dd9fdaa` |
| `C:\Users\josee\.claude.json` | 63,381 | `6e843e98e3b666214da8676ded7ad573de75c15f8f4461055238244b3debfc6d` |

The Codex primary config has no inline hook table and no exact target-project
entry. Its existing feature, MCP, memory, plugin, project, and Windows sections
are preserved. Claude's primary settings keep all top-level entries and the
existing `PreToolUse` (one handler), `SessionStart` (one handler), and
`PostToolUse` (two handlers) groups. Their command SHA-256 values are,
respectively:

- `3127028ecb4bdcc32f13306c030844b116fc7cf87972aee66b17d8a7718aaa5a`
- `4d5b83eee345c84d0ff2fd543cfa769b057ce9f787d8a99173a6596f52b155b6`
- `0bbb268f7923bd5d3474fcb6390dab7f4d4473743d457c5d24cf61f79477203c`
- `20bae6b3cb5eefaeb420980298af45847a6990aa36a9856f272a69197391dba1`

The Claude registry has no exact isolated-target mention. Its duplicate
case-variant project keys prevent a safe generic JSON merge, which is why the
pilot will not edit it and must use Claude's normal interactive directory-trust
flow.

## Codex 0.145.0

- Resolved executable:
  `C:\Users\josee\.codex\packages\standalone\releases\0.145.0-x86_64-pc-windows-msvc\bin\codex.exe`
- Executable SHA-256:
  `83751f15cb6a0a7b97df67752c001e3fe1c20e18ffbfec3ff63567296205eb6c`
- Current read-only plan SHA-256:
  `5122e7952525be1016bb7ef8376654bf25470af86987f0d6b7278832dd7386e0`
- Current plan state: `inactive`, reason `inactive_or_untrusted_hook` only.
- The ordinary runtime parser accepted the generated profile with zero stderr.
  Codex has no strict-config mode for this surface.

### Target 1: create Codex profile

Path: `C:\Users\josee\.codex\context-pilot.config.toml`

Whole-file SHA-256:
`41c663081c84b333117a6310e3856370ab3e8293a90992582203191cfd92283d`

Owned payload SHA-256:
`6c89bb904300f4a44705d707ab9ddc471a1072d3e3d4af7ba49c42bcef84760a`

Exact generated content:

```toml
# context-pilot-owner: coding-cli-context-compaction-pilot
# context-pilot-schema: 1
# context-pilot-generator: 0.1.0
# context-pilot-content-sha256: 6c89bb904300f4a44705d707ab9ddc471a1072d3e3d4af7ba49c42bcef84760a

experimental_compact_prompt_file = "C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\prompts\\context-compaction.prompt.md"
model_auto_compact_token_limit = 64000
model_auto_compact_token_limit_scope = "body_after_prefix"
tool_output_token_limit = 12000
web_search = "disabled"

[features]
hooks = true
apps = false

browser_use = false
browser_use_external = false
browser_use_full_cdp_access = false
computer_use = false
image_generation = false
in_app_browser = false
skill_mcp_dependency_install = false

[[hooks.PreCompact]]
matcher = "^(manual|auto)$"
[[hooks.PreCompact.hooks]]
type = "command"
command = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
command_windows = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
timeout = 2

[[hooks.PostCompact]]
matcher = "^(manual|auto)$"
[[hooks.PostCompact.hooks]]
type = "command"
command = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
command_windows = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
timeout = 2

[[hooks.SessionStart]]
matcher = "^compact$"
[[hooks.SessionStart.hooks]]
type = "command"
command = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
command_windows = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
timeout = 2
additionalContextLimit = 8000

[[hooks.PreToolUse]]
matcher = ".*"
[[hooks.PreToolUse.hooks]]
type = "command"
command = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
command_windows = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
timeout = 2

[[hooks.PostToolUse]]
matcher = ".*"
[[hooks.PostToolUse.hooks]]
type = "command"
command = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
command_windows = "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host codex --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\codex.allowlist.json --host-version 0.145.0"
timeout = 2

```

### Target 2: create Codex allowlist

Path:
`C:\Users\josee\AppData\Local\coding-cli\context-compaction\codex.allowlist.json`

Whole-file SHA-256:
`3cef8141bbf8b00ce5fbfa40c3e08bb9a2fe8e6b7bf7516b999a50628754313c`

Owned payload SHA-256:
`e5d34973f025ec95340b2a76c3f927c99187d64945e41f0c4e789139247b0e25`

Exact generated content:

```json
{
  "_context_pilot": {
    "content_sha256": "e5d34973f025ec95340b2a76c3f927c99187d64945e41f0c4e789139247b0e25",
    "generator_version": "0.1.0",
    "owner": "coding-cli-context-compaction-pilot",
    "schema_version": 1
  },
  "budgets": {
    "memory_envelope_chars": 8000,
    "memory_item_chars": 500,
    "memory_text_chars": 4000,
    "reentry_chars": 8000,
    "reentry_estimated_tokens": 2000
  },
  "contract_relative_path": "prompts/context-compaction.prompt.md",
  "contract_sha256": "0132ab9ce6381c58c8596565d68c8b567376f3dc930b9c0be680f97bdec5c0fa",
  "host": "codex",
  "host_executable": "C:\\Users\\josee\\.codex\\packages\\standalone\\releases\\0.145.0-x86_64-pc-windows-msvc\\bin\\codex.exe",
  "host_executable_sha256": "83751f15cb6a0a7b97df67752c001e3fe1c20e18ffbfec3ff63567296205eb6c",
  "host_version": "0.145.0",
  "observable_tools": [
    "Bash",
    "apply_patch",
    "mcp__mnemo__code_index_status",
    "mcp__mnemo__code_reindex",
    "mcp__mnemo__code_search",
    "mcp__mnemo__memory_forget",
    "mcp__mnemo__memory_get",
    "mcp__mnemo__memory_list",
    "mcp__mnemo__memory_search",
    "mcp__mnemo__memory_stats",
    "mcp__mnemo__memory_status",
    "mcp__mnemo__memory_write",
    "mcp__mnemo__task_context",
    "request_user_input",
    "update_plan"
  ],
  "python_executable": "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "repository_fingerprint": "74ab18671983692d54b0bfabf8e7ac4f7c133bdf466c80a8680a57c0534e4c43",
  "repository_root": "C:\\Users\\josee\\source\\educode.context-pilot",
  "source_root": "C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a",
  "state_fallback_root": "C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\state",
  "task_slug": "cross-host-context-compaction"
}
```

### Codex launch and restrictions

Exact launch:

```text
C:\Users\josee\.codex\packages\standalone\releases\0.145.0-x86_64-pc-windows-msvc\bin\codex.exe --profile context-pilot --cd C:\Users\josee\source\educode.context-pilot
```

No process-local environment additions. Only the profile disables hosted web
search, connector apps, image generation, browser/computer use, in-app browser,
and skill dependency installation because local hooks cannot observe those
surfaces. Unknown runtime tool names are denied before use. The approved
inventory is the 15-name list embedded in the allowlist.

## Claude Code 2.1.220

- Executable: `C:\Users\josee\.local\bin\claude.exe`
- Executable SHA-256:
  `af5bf1f1b2aadffc768eccd787084c6fdf9ba81624cbe96c1c6d9ac1a1550231`
- Current read-only plan SHA-256:
  `ebc15e34796ce41a7da6266a1681b1938c2b81e7a96bc1128020971ed10bfaa9`
- Current plan state: `inactive`, reason `inactive_or_untrusted_hook` only.
- Claude accepted the generated overlay with `--settings`; `--version` exited 0
  with expected `2.1.220 (Claude Code)` output and empty stderr.

### Target 3: create Claude settings overlay

Path:
`C:\Users\josee\AppData\Local\coding-cli\context-compaction\claude-context-pilot.settings.json`

Whole-file SHA-256:
`4c0699b0d7318f262a26f8a60bdf56937419a14c9144ba0f9aec40a7f8bb047d`

Owned payload SHA-256:
`9a4ba3baa370e54faa04a0579e28b40a1773f55de21e84d875c09c6572680ac6`

Exact generated content:

```json
{
  "_context_pilot": {
    "content_sha256": "9a4ba3baa370e54faa04a0579e28b40a1773f55de21e84d875c09c6572680ac6",
    "generator_version": "0.1.0",
    "owner": "coding-cli-context-compaction-pilot",
    "schema_version": 1
  },
  "autoCompactEnabled": true,
  "hooks": {
    "PostCompact": [
      {
        "hooks": [
          {
            "command": "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host claude --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\claude.allowlist.json --host-version 2.1.220",
            "timeout": 2,
            "type": "command"
          }
        ],
        "matcher": "manual|auto"
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host claude --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\claude.allowlist.json --host-version 2.1.220",
            "timeout": 2,
            "type": "command"
          }
        ],
        "matcher": ".*"
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "command": "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host claude --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\claude.allowlist.json --host-version 2.1.220",
            "timeout": 2,
            "type": "command"
          }
        ],
        "matcher": "manual|auto"
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "command": "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host claude --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\claude.allowlist.json --host-version 2.1.220",
            "timeout": 2,
            "type": "command"
          }
        ],
        "matcher": ".*"
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "command": "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a\\context_compaction\\hook_entry.py hook --host claude --pilot-config C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\claude.allowlist.json --host-version 2.1.220",
            "timeout": 2,
            "type": "command"
          }
        ],
        "matcher": "compact"
      }
    ]
  },
  "permissions": {
    "deny": [
      "WebFetch",
      "WebSearch"
    ]
  }
}
```

### Target 4: create Claude allowlist

Path:
`C:\Users\josee\AppData\Local\coding-cli\context-compaction\claude.allowlist.json`

Whole-file SHA-256:
`b6fde5cc05ef1f18b47491060bcf499d52a1eebe784a2c4a6e47a58f7803232f`

Owned payload SHA-256:
`08385d2d360f7a692098b98e34f23bbac449124f8d9a9f1f931fac43c2f557d1`

Exact generated content:

```json
{
  "_context_pilot": {
    "content_sha256": "08385d2d360f7a692098b98e34f23bbac449124f8d9a9f1f931fac43c2f557d1",
    "generator_version": "0.1.0",
    "owner": "coding-cli-context-compaction-pilot",
    "schema_version": 1
  },
  "budgets": {
    "memory_envelope_chars": 8000,
    "memory_item_chars": 500,
    "memory_text_chars": 4000,
    "reentry_chars": 8000,
    "reentry_estimated_tokens": 2000
  },
  "contract_relative_path": "prompts/context-compaction.prompt.md",
  "contract_sha256": "0132ab9ce6381c58c8596565d68c8b567376f3dc930b9c0be680f97bdec5c0fa",
  "host": "claude",
  "host_executable": "C:\\Users\\josee\\.local\\bin\\claude.exe",
  "host_executable_sha256": "af5bf1f1b2aadffc768eccd787084c6fdf9ba81624cbe96c1c6d9ac1a1550231",
  "host_version": "2.1.220",
  "observable_tools": [
    "AskUserQuestion",
    "Bash",
    "Edit",
    "Glob",
    "Grep",
    "NotebookEdit",
    "Read",
    "Skill",
    "Task",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskUpdate",
    "TodoWrite",
    "Write",
    "mcp__mnemo__code_index_status",
    "mcp__mnemo__code_reindex",
    "mcp__mnemo__code_search",
    "mcp__mnemo__memory_forget",
    "mcp__mnemo__memory_get",
    "mcp__mnemo__memory_list",
    "mcp__mnemo__memory_search",
    "mcp__mnemo__memory_stats",
    "mcp__mnemo__memory_status",
    "mcp__mnemo__memory_write",
    "mcp__mnemo__task_context"
  ],
  "python_executable": "C:\\Users\\josee\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "repository_fingerprint": "74ab18671983692d54b0bfabf8e7ac4f7c133bdf466c80a8680a57c0534e4c43",
  "repository_root": "C:\\Users\\josee\\source\\educode.context-pilot",
  "source_root": "C:\\Users\\josee\\source\\coding-cli.worktrees\\i-want-you-to-research-if-theres-a",
  "state_fallback_root": "C:\\Users\\josee\\AppData\\Local\\coding-cli\\context-compaction\\state",
  "task_slug": "cross-host-context-compaction"
}
```

### Claude launch and restrictions

Exact launch:

```text
C:\Users\josee\.local\bin\claude.exe --settings C:\Users\josee\AppData\Local\coding-cli\context-compaction\claude-context-pilot.settings.json --append-system-prompt-file C:\Users\josee\source\coding-cli.worktrees\i-want-you-to-research-if-theres-a\prompts\context-compaction.prompt.md --disallowedTools WebFetch,WebSearch
```

Process-local environment only:

```text
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80
CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000
```

`WebFetch` and `WebSearch` are denied only for the pilot process. Unknown runtime
tool names are denied before use. The approved inventory is the 26-name list
embedded in the allowlist.

## Trust, enable order, verification, and rollback

Approval of this preview authorizes only the following guarded sequence:

1. Re-run the Codex plan with `--hook-trusted`. The ready plan hash will differ
   because trust/state are hash inputs; all four previewed Codex target paths and
   contents must remain byte-identical to the hashes above or activation stops.
2. Create only the two Codex-owned files with the ready plan's exact SHA-256,
   launch the isolated profile, and use Codex's normal hook trust UI to review and
   trust the exact hook hash. Do not report active until a real lifecycle event
   and the tool inventory are observed.
3. Disable Codex, then separately purge its pilot state. Confirm the two owned
   files are gone and all three primary hashes above remain identical.
4. Repeat the same plan-hash, create, normal directory/hook trust, lifecycle,
   disable, purge, and primary-hash checks for Claude Code.

The owned rollback set is exactly the four targets above plus pilot metadata state
under
`C:\Users\josee\AppData\Local\coding-cli\context-compaction\state` or the
repository-local self-owned state selected by the storage resolver. `disable`
removes only self-verifying host activation files; drift causes refusal.
`purge-state` is a separate command and removes only self-verifying pilot state.
The isolated Git worktree is persistent benchmark infrastructure, not activation
state, and is not deleted by either command.

Approval does **not** authorize edits to the three primary configurations,
credentials, MCP server definitions, sandbox/approval policy, other repositories,
later host versions, wider rollout, or automatic replay of ambiguous actions.

## Refresh 1 after guarded Codex attempt

The original approval became stale during execution for two reasons:

1. Codex 0.145.0 could find neither packaged Windows sandbox helper from the
   approved standalone launch. A read-only diagnostic proved that using the
   package-resolved binary plus a process-local prepend of its own
   `codex-resources` directory lets Codex find both helpers without changing the
   sandbox or approval policy.
2. The non-target `C:\Users\josee\.claude.json` changed concurrently at
   `2026-08-01T19:21:39.7508369Z`, from 63,381 bytes / original SHA-256
   `6e843e98e3b666214da8676ded7ad573de75c15f8f4461055238244b3debfc6d`
   to 63,730 bytes / current SHA-256
   `631bc992e42fa8e6fe6c8b68b1a77d0511fe711e333f80eb929c111426a1820c`.
   It contains no exact isolated-repository or source-worktree mention. The pilot
   did not overwrite or restore it.

Current preserved baselines are therefore:

| File | Bytes | SHA-256 |
|---|---:|---|
| `C:\Users\josee\.codex\config.toml` | 4,130 | `7f0ee4673abfe45c36cad051f7f77fbd1e63300f1776b097f0d5d7f58ee8178c` |
| `C:\Users\josee\.claude\settings.json` | 22,282 | `fc4451db75e7f13562a1ef043424bcd8d417848878f11a74eb53c5cb7dd9fdaa` |
| `C:\Users\josee\.claude.json` | 63,730 | `631bc992e42fa8e6fe6c8b68b1a77d0511fe711e333f80eb929c111426a1820c` |

All four generated file bodies, paths, whole-file hashes, ownership hashes,
arguments, repository fingerprint, executable hashes, and Claude environment
values remain byte-for-byte as previewed above. The only proposed launch delta is:

```text
Codex path_prepend = C:\Users\josee\.codex\packages\standalone\releases\0.145.0-x86_64-pc-windows-msvc\codex-resources
Codex environment = {}
Claude path_prepend = []
Claude environment = {CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80, CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000}
```

The inherited PATH remains host-owned and is not copied into the plan; the exact
approved prepend directive is hashed. Environment values, not only names, are now
part of the plan hash. Refreshed ready-plan hashes are:

- Codex: `cc64a33b2fc0eedf4fa4677317900ae8a2270152f7e372aa7b662c325fe041ec`
- Claude: `894e645e6552fa4f0b7da36e7b51e9bf52f6331f81375765c7bbbc0afe6326be`

Approval of Refresh 1 authorizes the same one-host-at-a-time sequence and four
owned files, with only the Codex PATH-prepend directive and new preserved
`.claude.json` baseline above. Normal hook/directory trust remains interactive;
no hook-trust bypass is authorized.

## Refresh 2: repository-native task identity

The approved Refresh 1 cycle proved real Codex manual lifecycle but degraded
because `task_slug=cross-host-context-compaction` exists in this implementation
checkout, not in the allowlisted `educode.context-pilot` repository. Current
source in that repository contains the intended frozen preservation task at
`.batman/agentic-development-workbench`. Refresh 2 changes only the allowlisted
task slug to `agentic-development-workbench` and the self-hashes/plan hashes that
necessarily cover that field.

No primary configuration changed. All four activation targets are absent. The
three preserved primary hashes remain exactly those listed in Refresh 1. Codex
normal trust may append its reviewed `[hooks.state]` section after enable; the
generator does not synthesize it, and the manager accepts only the exact five
expected host keys and hash-only values.

The user-level Codex wrapper is now 0.146.0 and is intentionally unsupported.
Refresh 2 does not widen compatibility: it pins the still-installed, unchanged
0.145.0 package binary with SHA-256
`83751f15cb6a0a7b97df67752c001e3fe1c20e18ffbfec3ff63567296205eb6c`.
The 0.146.0 read-only plan returned `unsupported_host_version`; no files were
created. Claude remains 2.1.220 with executable SHA-256
`af5bf1f1b2aadffc768eccd787084c6fdf9ba81624cbe96c1c6d9ac1a1550231`.

Corrected ready plans:

| Host | Plan SHA-256 | Primary generated SHA-256 | Allowlist SHA-256 | Allowlist owned-payload SHA-256 |
|---|---|---|---|---|
| Codex 0.145.0 | `2379e98a8d541d992fdf719be4164e7e6d4897af5965aa384b750a32529e2132` | `41c663081c84b333117a6310e3856370ab3e8293a90992582203191cfd92283d` | `5dae46d2ce2dbb2a5faedbe6436fbe9ed28fa0603bdf3f2f81fea8abe8dbb816` | `9229cfeeac1f48610bf58537ce69beb9bc151b4d67940463d6032dd1456870f8` |
| Claude 2.1.220 | `46381b248d97ebbe657ca1f94878e80a1f19962b46daffdf4cb8b0338cef2864` | `4c0699b0d7318f262a26f8a60bdf56937419a14c9144ba0f9aec40a7f8bb047d` | `a1034fd250b63f1c7db0bd9faf98906d01c1a91ee339ff72cc99097e92f5829e` | `5383785cc09e47b37d23043041f0b53f162ef4aabe5214effb1987745c229319` |

Unchanged Codex path prepend:
`C:\Users\josee\.codex\packages\standalone\releases\0.145.0-x86_64-pc-windows-msvc\codex-resources`.
Codex environment remains empty. Claude environment remains exactly
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` and
`CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000`; Claude path prepend remains empty.

Approval of Refresh 2 authorizes only the prior one-host-at-a-time guarded
sequence with this single task-slug correction and the exact hashes above. It
does not authorize Codex 0.146.0, new repositories, new users, primary config
edits, trust bypass, sandbox/approval/network changes, or wider rollout.

## Refresh 3: Claude host-owned registry preservation

Refresh 2 completed the valid Codex manual lifecycle and exact rollback. The
approved Claude plan then enabled exactly its overlay and allowlist. Before any
trust input or lifecycle event, ordinary Claude 2.1.220 startup rewrote
host-owned `C:\Users\josee\.claude.json`:

| State | Bytes | SHA-256 |
|---|---:|---|
| Approved Refresh 2 baseline | 63,730 | `631bc992e42fa8e6fe6c8b68b1a77d0511fe711e333f80eb929c111426a1820c` |
| Preserved post-startup state | 63,729 | `2391a9a9333b3c290b468e2b31a63a11bc1058032b36d57ddac3602b4edfe35f` |

No isolated-project entry exists in the resulting registry. Because no full body
snapshot was retained, the exact semantic delta is intentionally not claimed.
Local binary/current-state inspection confirms the relevant host schema contains
integer `numStartups`, per-project `hasTrustDialogAccepted`, and
`autoCompactWindowsCache` surfaces. The changed file was never reverted.

Current read-only revalidation shows:

- Both Claude targets are absent; all four pilot activation targets are absent.
- Isolated repository is clean at
  `0db30624dd32d814b937aa88b5ec84e18d4b130d`.
- Codex `config.toml` remains
  `7f0ee4673abfe45c36cad051f7f77fbd1e63300f1776b097f0d5d7f58ee8178c`.
- Claude `settings.json` remains
  `fc4451db75e7f13562a1ef043424bcd8d417848878f11a74eb53c5cb7dd9fdaa`.
- Claude plan remains `ready`, with no degraded reasons, at the already reviewed
  plan hash `46381b248d97ebbe657ca1f94878e80a1f19962b46daffdf4cb8b0338cef2864`;
  its two generated file hashes, launcher arguments, environment, repository,
  task slug, tool inventory, and rollback set are unchanged.

Refresh 3 proposes one semantic contract delta only: stop requiring byte identity
for host-owned `.claude.json` while the exact Claude pilot PID is running. Before
launch, capture a content-free semantic manifest. After startup/trust/exit, accept
only:

1. `numStartups` increasing by exactly one;
2. creation of only the canonical
   `C:\Users\josee\source\educode.context-pilot` project subtree by Claude's
   normal interactive trust flow, with `hasTrustDialogAccepted=true`; and
3. serialization-only byte changes with semantic equivalence everywhere else.

Any deletion or change to an existing project, any other top-level semantic
change, a missing/manual-trust mismatch, or a write outside the exact Claude PID
window stops the pilot without revert. The pilot still never writes
`.claude.json`; `~/.claude/settings.json` remains byte-identical; normal trust
must be user-reviewed; primary credentials, network, sandbox, approvals, and MCP
permissions remain untouched.

Refresh 3 was explicitly approved by the owner. Implementation must pass focused
semantic-guard, activation, security, and rollback tests before another Claude
launch. That launch must use an owner-created terminal or separately approved
dedicated console; Windows Terminal top-level windows will not be closed
programmatically. Approval does not reopen the already completed Codex manual
lifecycle or authorize any wider rollout.

## Refresh 4 exact read-only diagnostic preview

After ADR 0014 implementation and full deterministic verification, the read-only
Claude plan remains `ready` with no degraded reasons. No file was created and no
Claude process was launched.

- Plan SHA-256:
  `46381b248d97ebbe657ca1f94878e80a1f19962b46daffdf4cb8b0338cef2864`
- Overlay content SHA-256:
  `4c0699b0d7318f262a26f8a60bdf56937419a14c9144ba0f9aec40a7f8bb047d`
- Allowlist content SHA-256:
  `a1034fd250b63f1c7db0bd9faf98906d01c1a91ee339ff72cc99097e92f5829e`
- Claude 2.1.220 executable SHA-256:
  `af5bf1f1b2aadffc768eccd787084c6fdf9ba81624cbe96c1c6d9ac1a1550231`
- Repository fingerprint:
  `74ab18671983692d54b0bfabf8e7ac4f7c133bdf466c80a8680a57c0534e4c43`
- Task slug: `agentic-development-workbench`.
- Generated mutations remain exactly two creates: the process-local settings
  overlay and allowlist already shown above. Disable removes only matching owned
  targets; purge-state remains separate.
- Launch arguments and process-local environment remain byte-for-byte unchanged
  from the approved Refresh 3 plan. ADR 0014 changes guard diagnosis in source,
  not the host command, accepted semantics, or rollback set.

Before and after planning, both Claude activation targets and pilot state were
absent; no exact Claude/pilot-manager process existed. Primary Codex config
remained `7f0ee467...`, primary Claude settings `fc4451db...`, and host-owned
registry `33a35b780...` at 63,786 bytes. The version probe therefore caused no
host-state change.

This preview does not authorize `enable` or `run`. One diagnostic-only live cell
requires the owner to approve this exact Refresh 4 plan. Any category-based
registry exception remains out of scope and needs a later Design/ADR decision.

The owner later supplied that exact one-cell approval. It was consumed by the
`feature_state` rejection recorded in `task-10-activation-attempt.md` and is not
reusable for another launch.
