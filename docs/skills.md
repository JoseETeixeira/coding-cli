# Shipped skills

Every skill directory under [`skills/`](../skills/) is copied into the host's user-level skills folder by `coding-cli setup agent`. The frontmatter `description:` is what each host's skill loader uses to decide whether the skill is relevant to the current task.

Each entry below links to the underlying `SKILL.md` for the full body.

## Spec-driven workflow

| Skill | Description |
| --- | --- |
| [`batman-understanding`](../skills/batman-understanding/SKILL.md) | Use when starting a new Batman task, creating or updating `.batman/<task_slug>/steering/understanding.md`, validating current codebase behavior before requirements, mapping likely files/symbols/tests/docs, detecting architecture-change risk during Phase 1 Understanding, or generating a visual current-state recap with `visual-explainer`. |
| [`grill-me`](../skills/grill-me/SKILL.md) | Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when the user wants to stress-test a plan, get grilled on their design, or mentions "grill me". |
| [`karpathy-guidelines`](../skills/karpathy-guidelines/SKILL.md) | Behavioral guardrails for coding work. Use when writing, reviewing, refactoring, debugging, or planning code changes where hidden assumptions, overcomplication, broad diffs, or weak verification criteria could cause mistakes. |
| [`sop-vs-agent-behavior`](../skills/sop-vs-agent-behavior/SKILL.md) | Compare agent execution (tool calls, reasoning) to the SOP the agent had in context to find why the agent did not follow the SOP. Use when classifying AGENT_OR_SETUP vs JUDGE_MISMATCH or finding the needle-in-the-haystack root cause. |

## Refactoring

| Skill | Description |
| --- | --- |
| [`domain-entity-refactoring`](../skills/domain-entity-refactoring/SKILL.md) | Identify scattered knowledge patterns and refactor them into Domain Entities (Value Objects). Use when string patterns are duplicated across 3+ files, when implicit contracts exist between creators and consumers, when bugs arise from pattern divergence, or when significant research is needed to understand how something works. |
| [`python-refactoring-strategies`](../skills/python-refactoring-strategies/SKILL.md) | Python refactoring patterns using Pydantic models and modular extraction. Covers context models for centralizing dict access, decomposing large files into packages, extracting pure functions for testability, and factory methods as single source of truth. |
| [`safe-refactoring-testing`](../skills/safe-refactoring-testing/SKILL.md) | Testing strategies for safe Python refactoring. Covers characterization tests to capture existing behavior, TDD for new abstractions, and regression safety. |

## Testing — Robot Framework

| Skill | Description |
| --- | --- |
| [`appium`](../skills/appium/SKILL.md) | AppiumLibrary tests for iOS and Android native apps, hybrid apps, and mobile browsers. |
| [`browser`](../skills/browser/SKILL.md) | Browser Library tests using Playwright-powered automation: locators, assertions, iframes, Shadow DOM, multi-tab. |
| [`selenium`](../skills/selenium/SKILL.md) | SeleniumLibrary tests: web UI automation, forms, multiple windows/frames, JavaScript execution. |
| [`requests`](../skills/requests/SKILL.md) | REST API tests using RequestsLibrary: HTTP, JSON/XML, sessions, auth, file uploads, response validation. |
| [`restinstance`](../skills/restinstance/SKILL.md) | REST API tests using RESTinstance: JSON Schema validation, built-in assertions, OpenAPI integration. |
| [`keyword-builder`](../skills/keyword-builder/SKILL.md) | Generate Robot Framework user keywords from structured intent. |
| [`testcase-builder`](../skills/testcase-builder/SKILL.md) | Generate Robot Framework test cases from structured requirements or scenarios. |
| [`resource-architect`](../skills/resource-architect/SKILL.md) | Design Robot Framework resource and variables layout for maintainable suites. |
| [`libdoc-search`](../skills/libdoc-search/SKILL.md) | Search Robot Framework library/resource/suite documentation to find matching keywords for a use case. |
| [`libdoc-explain`](../skills/libdoc-explain/SKILL.md) | Explain Robot Framework keywords and their arguments from library/resource/suite documentation. |
| [`results`](../skills/results/SKILL.md) | Parse Robot Framework `output.xml` into JSON summaries, suite/test breakdowns, tag/criticality stats, errors, and timing. |

## Testing — Python / scenarios

| Skill | Description |
| --- | --- |
| [`create-scenario-tests`](../skills/create-scenario-tests/SKILL.md) | Create Deep Agent workflow scenario tests using the langwatch/scenario framework: judges, criteria, agent workflows. |
| [`debugging-scenario-tests`](../skills/debugging-scenario-tests/SKILL.md) | Debug failing deep agent scenario tests by tracing execution flow and analyzing JSON response files. |
| [`integration-tests-framework`](../skills/integration-tests-framework/SKILL.md) | Run and debug Python integration tests using LocalStack, Redis, docker compose, and pytest. |

## Memory and discovery

| Skill | Description |
| --- | --- |
| [`mempalace`](../skills/mempalace/SKILL.md) | Recover prior context, reuse durable knowledge, avoid repeating investigations, and persist valuable outcomes via MemPalace MCP. |
| [`find-skills`](../skills/find-skills/SKILL.md) | Help users discover and install agent skills when they ask "how do I do X" or "is there a skill that can…". |
| [`cocoindex`](../skills/cocoindex/SKILL.md) | Build data processing pipelines with CocoIndex: incremental ETL, vector embeddings, knowledge graphs. |

## Visual artifacts

| Skill | Description |
| --- | --- |
| [`visual-explainer`](../skills/visual-explainer/SKILL.md) | Generate beautiful self-contained HTML pages that visually explain systems, code changes, plans, and data. Use proactively instead of rendering large ASCII tables. |
| [`excalidraw-mcp-diagrams`](../skills/excalidraw-mcp-diagrams/SKILL.md) | Create architecture and flow diagrams using the Excalidraw MCP. |
| [`miro-mcp`](../skills/miro-mcp/SKILL.md) | Create and edit Miro boards via MCP — flowcharts, docs, tables, images. |

## Caveman mode (token compression)

| Skill | Description |
| --- | --- |
| [`caveman`](../skills/caveman/SKILL.md) | Ultra-compressed communication mode. Cuts token usage ~75% by speaking like caveman while keeping full technical accuracy. Supports `lite`, `full`, `ultra`, and wenyan variants. |
| [`caveman-commit`](../skills/caveman-commit/SKILL.md) | Caveman commit-message generator. Conventional Commits, subject ≤50 chars, body only when "why" isn't obvious. Auto-triggers when staging changes. |
| [`caveman-review`](../skills/caveman-review/SKILL.md) | Ultra-compressed PR review comments. Each comment is one line: location, problem, fix. |
| [`caveman-compress`](../skills/caveman-compress/SKILL.md) / [`compress`](../skills/compress/SKILL.md) | Compress natural-language memory files (CLAUDE.md, todos, preferences) into caveman format. Human-readable backup saved as `FILE.original.md`. |
| [`caveman-help`](../skills/caveman-help/SKILL.md) | Quick-reference card for all caveman modes, skills, and commands. |

## Authoring rules

Each skill is just a directory containing a `SKILL.md` plus optional `references/`. The CLI ships them as a single tree — skill names are kebab-case, frontmatter `name:` must match the directory, and the body should stay under ~5,000 tokens with conditional content extracted to `references/`. Skip Claude Code's idiomatic limit and the agent will end up paying for unused branches every time the skill loads.
