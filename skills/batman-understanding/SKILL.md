---
name: batman-understanding
description: "Use when: starting a new Batman task, creating or updating `.batman/<task-slug>/steering/understanding.md`, validating current codebase behavior before requirements, mapping likely files/symbols/tests/docs, or detecting architecture-change risk during Phase 1 Understanding." 
---

# Batman Understanding

## Purpose

Create a validated, evidence-backed Phase 1 understanding before Batman writes requirements, design, or tasks.

The output is always:

```text
.batman/<task-slug>/steering/understanding.md
```

This skill is for understanding the current state of the codebase and likely change surface. Do not draft requirements, design, or implementation tasks here.

---

## When To Use

Use this skill when:

- a user starts a new feature, fix, refactor, or architecture task with Batman;
- Batman needs to create or revise `.batman/<task-slug>/steering/understanding.md`;
- requirements/design/task planning would otherwise depend on assumptions;
- the task may affect multiple projects, services, workflows, tools, tests, docs, or infrastructure;
- architecture-change risk needs to be identified before requirements.

Do not use this skill for tiny one-off answers, direct command output, or already-approved implementation tasks.

---

## Workflow

### 1. Establish Context

1. Derive a short `task-slug` from the user request using kebab-case.
2. Check relevant memory only when prior project history may matter.
3. Identify the likely project area, such as `ai_watchtower`, `backend`, `frontend`, `robin-error-dashboard`, or cross-project.
4. Prefer repository/project instructions already in context before inventing process.

### 2. Search The Codebase

Run `freighthero-codebase/:search_codebase` with a query derived from the user request.

Then use targeted follow-up searches or `freighthero-codebase/:explain_code` for likely:

- files and symbols;
- service boundaries;
- graph/workflow nodes;
- Skills/SOPs, prompts, templates, or tools;
- tests and fixtures;
- infrastructure/configuration;
- docs and runbooks.

When the search space is broad, use a read-only subagent. Tell the subagent to return files, symbols, current behavior, risks, and likely test/doc impact. Do not ask the subagent to draft requirements.

### 3. Explain Current Behavior

Summarize what the code appears to do today. Include:

- main entry points;
- current data flow;
- important branching or routing rules;
- state transitions or side effects;
- existing tests and coverage gaps;
- known docs/runbooks related to the area.

Use source identifiers from codebase search/explain results when available. If you read local files, reference file paths and symbols.

### 4. Detect Architecture Risk

Flag an architecture-change risk if the task may change or add:

- infrastructure resources or deployment topology;
- queues, workers, event flows, or storage contracts;
- agent workflow architecture, graph orchestration, Skills/SOP behavior, or tool contracts;
- cross-service API contracts;
- model routing, provider fallback, or rollout modes;
- source-of-truth boundaries such as TMS-owned milestone state.

If flagged, the later design phase must present options with pros/cons and get user validation before implementation.

### 5. Write Understanding

Create or update `.batman/<task-slug>/steering/understanding.md` using this template:

```markdown
# Understanding: <Task Title>

## User Goal

<One short paragraph describing what the user wants and the intended outcome.>

## Task Slug

`<task-slug>`

## Current Behavior

- <What the relevant code does today.>
- <Important workflow, state, API, or data-flow notes.>

## Likely Change Surface

### Files And Symbols

- [path/to/file.py](path/to/file.py) — `<symbol>`: <why it matters>

### Tests

- [path/to/test_file.py](path/to/test_file.py) — <existing or missing coverage>

### Configuration And Infrastructure

- <Relevant settings, environment variables, queues, services, Docker/Terraform files, or none found.>

### Documentation

- <Relevant docs/runbooks/latex chapters, or docs likely needing updates.>

## Evidence

- <Search/explain source identifier or file reference>: <fact learned>

## Open Questions

- <Question or ambiguity. Use `None` if there are no known questions.>

## Risks And Constraints

- <Behavioral, operational, test, security, rollout, or backwards-compatibility risk.>

## Architecture Change Assessment

- Status: `none` | `possible` | `required`
- Reason: <why>
- Areas affected: <files/services/data flows/infrastructure/tests/docs>

## Initial Verification Ideas

- <Targeted tests, regression tests, manual checks, docs build, or deployment validation ideas.>
```

### 6. Validate With User

Present the understanding as a draft and ask the user to validate:

- whether the current behavior explanation is correct;
- whether the likely files/modules are the right ones;
- whether any important service, workflow, test, doc, or constraint is missing;
- whether the architecture-change assessment is accurate.

Stop after this draft. Continue to requirements only after explicit user approval.

---

## Quality Bar

The understanding is ready when:

- it names the likely files and symbols, not just broad directories;
- it explains current behavior in plain engineering terms;
- it records concrete evidence from search/explain or file reads;
- it identifies tests and documentation likely affected;
- it explicitly states architecture-change risk;
- it has no implementation plan disguised as understanding;
- it ends with a validation request, not requirements.

---

## Common Mistakes

- Skipping codebase search because the requested change sounds obvious.
- Writing requirements before the user approves the understanding.
- Naming only folders instead of concrete files and symbols.
- Omitting tests, docs, config, or infrastructure from the change surface.
- Treating architecture changes as implementation details.
- Using unsupported file links or references that do not exist in the workspace.
