# FreightHero agent assets

`coding-cli` is the canonical source repository for FreightHero prompts, instructions, static specialist agents, and skills. It contains no task runtime, model router, indexer, installer, or generated user-level copies.

Repository intelligence comes from the maintained FreightHero Repowise fork. Claude, Codex, and local VS Code/Copilot keep their native model loops and credits. Only the Repowise process may receive an OpenAI API credential.

## Repository layout

- `skills/freighthero-entry/`: metadata-first entry workflow and one-level references
- `agents/`: Batman plus the fixed research, planning, implementation, verification, and documentation specialists
- `instructions/`: shared system, code-pattern, review, and visual guidance
- `prompts/`: reusable task prompts
- `.claude-plugin/`: Claude Code source discovery manifest
- `.codex/`: repository-scoped Repowise MCP configuration
- `.vscode/`: local Copilot discovery and Repowise MCP configuration
- `.github/validation/`: source-only, host-conformance, and governance checks

## Activation

Install the maintained Repowise fork, configure `REPOWISE_SERVICE_URL`, and
authenticate without printing a bearer value:

```sh
repowise service-auth login
repowise agents activate --coding-cli /path/to/coding-cli --dry-run
repowise agents activate --coding-cli /path/to/coding-cli --yes
```

Run `repowise agents unactivate --yes` for guarded restoration. Do not copy
these files into a user configuration directory.

See [Native host activation](docs/activation.md) for Claude Code, Codex, local VS Code/Copilot, and clean unactivation.

Every FreightHero task begins with `skills/freighthero-entry/SKILL.md`. It loads
the mandatory governed-memory preflight plus the smallest other skill set,
verifies snapshot and shared-ledger status, retrieves scoped task context and
source evidence, and enforces PRD/ADR gates before behavior-changing work.

## Validation

```sh
python3 .github/validation/validate_source_assets.py
python3 .github/validation/test_host_scenarios.py
python3 scripts/validate_governance.py
python3 scripts/benchmark_retrieval_parity.py
```

The checks reject installable task runtimes, duplicate canonical assets, broken direct references, machine-specific paths, literal credentials, retired retrieval/documentation dependencies, invalid governance state, and host-ordering regressions.

## Supported hosts

- Claude Code through the canonical plugin directory
- Codex through repository `AGENTS.md` plus `.codex/config.toml`
- local VS Code/Copilot through workspace discovery paths

GitHub cloud Copilot is intentionally unsupported because it cannot consume the same local canonical checkout and host boundaries.

## Security and operations

- Task agents never receive the Repowise OpenAI credential.
- MCP access uses authenticated HTTP with repository, tool, action, and preview-owner scopes.
- The browser UI binds to loopback only.
- Existing unrelated MCP servers, safety hooks, RTK settings, and user configuration stay outside this repository.
- The external GitHub wiki remains untouched; the local managed wiki is served from Repowise shared snapshots.
