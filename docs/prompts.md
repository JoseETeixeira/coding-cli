# Shipped prompts, instructions, and agents

Every file under [`prompts/`](../prompts/) is copied into the host's user-level customization folder by `coding-cli setup agent`. Naming convention determines the destination:

| Suffix | Destination | Used by |
| --- | --- | --- |
| `*.prompt.md` | User prompts folder (`commands/` on Claude Code) | Slash commands / chat templates |
| `*.instructions.md` | Instruction folder + merged into `CLAUDE.md` / `AGENTS.md` | Always-on global instructions |
| `*.agent.md` | Agents folder | Multi-phase agent definitions (Batman) |

Per-host rendering (e.g. Claude Code's strip-`tools:` + spec-sync transforms) is documented in [cli-reference.md → host profiles](cli-reference.md#host-profiles).

## Agent

| File | Purpose |
| --- | --- |
| [`batman.agent.md`](../prompts/batman.agent.md) | The Batman agent: eight-phase spec-driven workflow (Understanding → Requirements → Design → Task Planning → Implementation → Tests → Code Review → Documentation), with MemPalace lookups, codebase search via `query-code`, grill-me passes, visual recaps, and host-aware transforms. |

## Always-on instructions

| File | Purpose |
| --- | --- |
| [`BASE_SYSTEM_PROMPT.instructions.md`](../prompts/BASE_SYSTEM_PROMPT.instructions.md) | Base system rules: response style, MemPalace lookup mandate, user-level customization-file resolution, Batman workflow trigger set, `query-code` search mandate, PR template fallback. Applies to all turns. |
| [`code-patterns.md.instructions.md`](../prompts/code-patterns.md.instructions.md) | Project-agnostic code patterns: path/config boundary validation, agent guardrails, testing layers, observability. Apply the sections that match the stack of the diff under review. |
| [`codeReview.instructions.md`](../prompts/codeReview.instructions.md) | Review checklist distilled from recurring patterns: repository pattern, type safety, no debug code, no nullable where optional fits, framework conventions, sensitive-data hygiene. Used by `commit.prompt.md` Phase 0 and the prReview prompt. |
| [`visual-explainer.instructions.md`](../prompts/visual-explainer.instructions.md) | When to render an HTML artifact via the `visual-explainer` skill instead of an ASCII table. |

## Spec-driven workflow prompts

These prompts are read inline during each Batman planning phase.

| File | Phase | Purpose |
| --- | --- | --- |
| [`requirements.prompt.md`](../prompts/requirements.prompt.md) | 2 — Requirements | EARS-template walkthrough that turns the approved understanding into `.batman/<task_slug>/spec/requirements.md`. |
| [`design.prompt.md`](../prompts/design.prompt.md) | 3 — Design | Architecture decisions, component responsibilities, API contracts, data models, risks. |
| [`createTasks.prompt.md`](../prompts/createTasks.prompt.md) | 4 — Task Planning | Traceable task checklist linked to requirement/design IDs, with concrete file paths and acceptance criteria. |
| [`executeTask.prompt.md`](../prompts/executeTask.prompt.md) | 5 — Implementation | Per-task execution loop: read steering, edit, validate, mark in-progress/done. |

## Standalone prompts

Each runs as a slash command (`/<filename without .prompt.md>` on Claude Code, or the equivalent on the host).

| File | Description |
| --- | --- |
| [`commit.prompt.md`](../prompts/commit.prompt.md) | Code-review-first commit assistant. Phase 0 runs `codeReview.instructions.md` against the staged diff; Phase 1 stages and groups changes; Phase 3 writes a Conventional Commits message. |
| [`prReview.prompt.md`](../prompts/prReview.prompt.md) | Structured PR review against the approved understanding, requirements, design, and tasks. |
| [`diff-review.prompt.md`](../prompts/diff-review.prompt.md) | Generate a visual HTML diff review — before/after architecture comparison with code-review analysis. |
| [`plan-review.prompt.md`](../prompts/plan-review.prompt.md) | Generate a visual HTML plan review — current codebase state vs. proposed implementation plan. |
| [`project-recap.prompt.md`](../prompts/project-recap.prompt.md) | Generate a visual HTML project recap — current state, recent decisions, cognitive-debt hotspots. |
| [`generate-web-diagram.prompt.md`](../prompts/generate-web-diagram.prompt.md) | Generate a beautiful standalone HTML diagram and open it in the browser. |
| [`generate-visual-plan.prompt.md`](../prompts/generate-visual-plan.prompt.md) | Visual HTML implementation plan — detailed feature spec with state machines, code snippets, and edge cases. |
| [`generate-slides.prompt.md`](../prompts/generate-slides.prompt.md) | Magazine-quality slide deck as a self-contained HTML page. |
| [`fact-check.prompt.md`](../prompts/fact-check.prompt.md) | Verify the factual accuracy of a document against the actual codebase; correct inaccuracies in place. |
| [`share-page.prompt.md`](../prompts/share-page.prompt.md) | Deploy a generated visual-explainer HTML page to Vercel and return a live URL. |

## Templates

[`prompts/templates/steering/`](../prompts/templates/steering/) ships three steering templates (`product-template.md`, `tech-template.md`, `structure-template.md`) that Batman uses when first generating `.batman/<task_slug>/steering/*.md` artifacts.

## How rendering works

`internal/assets.RenderTemplate` runs on `batman.agent.md` only — every other file is copied verbatim. Renders are:

1. **MemPalace harness placeholder** — `{{MEMPALACE_HARNESS}}` is replaced with the host harness (`claude-code` / `codex` / etc.). The mempalace `Stop` / `PreCompact` hook commands inside the agent body are kept in sync this way.
2. **Claude Code transforms** (only when harness = `claude-code`):
   - Strips the frontmatter `tools:` list so the agent inherits every session tool.
   - Removes the YAML `hooks:` block (Claude Code agent files don't support in-file hooks; hooks live in `settings.json` instead).
   - Replaces `#tool:vscode/askQuestions` → `AskUserQuestion` and `#tool:agent/runSubagent` → `Agent`.
   - Injects `model: "opus"` into the frontmatter.
   - Appends the spec-sync block that keeps the workspace-root `CLAUDE.md` synchronized with the active Batman spec.

All other hosts (`--vscode`, `--batman`, `--codex`) get the file as-authored, with just the harness placeholder replaced.
