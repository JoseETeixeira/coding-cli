---
name: karpathy-guidelines
description: Behavioral guardrails for Claude, Codex, and Copilot coding work. Use when writing, reviewing, refactoring, debugging, or planning code changes where hidden assumptions, overcomplication, broad diffs, weak verification, lossy early gates, or over-deterministic agentic routing could cause mistakes. The Agentic Workflows section is always in scope for any agent/workflow change.
---

# Coding behavior guardrails

Bias toward caution and verification on non-trivial work. For an obvious one-line
change, apply judgment and keep momentum — skip any lens whose object is not in
the diff. These guidelines merge with the project's own canon (`AGENTS.md`,
`instructions/`, `CLAUDE.md`), never override it.

The working test for the whole set: **every changed line traces to the request or
to cleanup your own change caused, and a reviewer's follow-up cleanup commit would
be empty.**

## 1. Think before coding

- State assumptions explicitly. If an assumption changes the implementation, data
  model, UX, security, cost, or migration path, ask instead of guessing.
- When a request has multiple plausible meanings, name the interpretations and the
  consequence of each. Do not pick one silently.
- If a simpler or lower-risk approach satisfies the goal, say so and push back.
- Treat the task framing — a PRD, ticket, or implementation guideline — as a
  proposal to challenge, not a given. Before planning, look for a simpler path that
  meets the actual goal with less mechanism and name it. Reframe an over-specified
  spec with the user (e.g. "always prompt the user" when a signal you already have
  answers the question) instead of building it as written.
- If something is unclear, stop and name what is confusing before editing.

## 2. Simplicity first

Minimum code that solves the stated problem — nothing speculative. No features
beyond the ask, no abstractions for single-use code, no configurability that was
not requested, no error handling for impossible states. If 200 lines could be 50,
rewrite it. Ask: would a senior engineer call this overcomplicated?

**Do not add logs, metrics, events, or tracing just to make a branch explicit or
because they might be useful later.** Before adding observability, name the unique
operational question it answers and why existing downstream signals cannot. If the
normal data flow is already observable, rely on that evidence. Keep existing log
event names stable wherever dashboards or runbooks depend on them.

### DRY / YAGNI / SOLID checkpoint

Run this while planning and again during self-review.

- **DRY** — one home for each piece of knowledge. Before adding a private helper,
  search for an existing implementation of the same domain rule or contract; reuse
  or extract a shared module. Do not deduplicate merely similar syntax whose
  semantics differ.
- **YAGNI** — implement the current requirement only. No behavior, config,
  abstraction, fallback, edge-case handling, or observability for a hypothetical
  or low-impact future problem unless the spec or current evidence requires it.
- **SOLID** — one responsibility per module, small interfaces with substantial
  behavior behind them, explicit dependencies, extensions at clean seams. Do not
  create a class, interface, or layer that has no current consumer.

YAGNI constrains DRY and SOLID: neither authorizes speculative abstraction. If you
intentionally depart from one, record a one-sentence rationale in the plan/review
(name the principle, the tradeoff, the evidence). Only add a code comment if a
future maintainer needs that rationale.

### Preserve information until the decision boundary

Deterministic code may normalize composite or provenance-bearing input, but must
not collapse it before the layer that owns the decision.

- Treat summaries, primary-item fields, booleans, scores, and labels as lossy
  views. Do not substitute one for the underlying evidence when valid elements may
  differ.
- Keep a derived fact scoped to the question it answers. A guard built for safety,
  visibility, caching, dedup, or transport does not determine semantic eligibility
  or business meaning.
- Before an early return, filter, or exclusive route, state what information
  becomes unreachable and prove the discarded distinctions cannot change a valid
  outcome. If judgment depends on them, preserve and pass them onward while
  constraining only the permitted effects.

Ask which distinctions the change collapses; whether mixed, partial, conflicting,
or reordered inputs contain valid work the gate would erase; and whether the
invariant applies to the whole input or only one element. Test those variations
whenever the change adds a lossy projection or early gate.

### Agentic workflows: constrain authority, not conversation shape

**Always in scope for any agent, graph, routine, classifier, or
inbound-communication change.** Do not default to deterministic routing merely
because the happy-path sequence can be drawn as branches or states. Before adding
a router, state machine, exclusive intent selection, or classifier-driven branch,
decide whether it protects a hard invariant or is trying to predict how a
conversation unfolds.

- Treat inbound communications as **unordered, interruptible, and potentially
  multi-intent**. Do not assume the next event answers the last question, that one
  message carries a single actionable intent, or that events arrive in designed
  order.
- Treat classifiers, pending questions, timers, and prior workflow state as
  **context for the agent**, not an exclusive route, unless a business invariant
  demands exclusivity. A classification must not suppress unrelated actionable
  content merely because it adds useful context.
- Prefer giving the agent the relevant history, tools, and operational guidance so
  it assembles the full agenda for the current turn, combines compatible actions,
  and decides whether a new message resolves earlier context.
- **Keep deterministic enforcement for capability and safety boundaries only:**
  permissions, irreversible or externally-visible state changes, idempotency and
  dedup, exact calculations and mappings, and invariants with one correct outcome.
- Do not use "more agentic" to move bookkeeping, exact contracts, or safety
  enforcement into probabilistic instructions. Openness applies to judgment and
  orchestration inside bounded capabilities — never to operational authority.

During planning and adversarial review, answer explicitly:

1. What event-order or single-intent assumptions does this design encode?
2. What happens when an unrelated message arrives between a question and its
   answer, or when one message contains multiple intents?
3. Could deterministic code define what the agent *may* do while the agent decides
   what it *should* do from the full context?
4. Are the deterministic branches protecting an invariant, or compensating for a
   prompt/context/tool design that is too constrained?

Add tests that vary event order and combine intents whenever the workflow carries
context across turns. Remembered failure: converting classifier context into an
exclusive route and assuming the next inbound message resolved a pending question
suppressed other valid work and broke when the conversation arrived in a different
sequence. A deliberate exclusive route that protects a business invariant — one
whose events flow through a designated source-of-truth channel, for instance — is
not this failure; do not narrow it.

### Tool design: thin capability, no embedded judgment

A tool is a capability the agent invokes, not a decision-maker. It performs one
clear, named action in the shape of its neighbors — mirror an existing tool (e.g.
`update_status`) rather than inventing a pattern.

- Keep business and decision logic out of tool internals. A tool that accretes
  value-precedence, conflict resolution, freshness gating, or multi-branch "which
  value wins" logic has swallowed a decision that belongs to the agent (skill body)
  or a single-responsibility service contract. Leave the tool a thin write/read and
  push the judgment to the layer that owns it — the same authority boundary as the
  agentic-workflows rule above, applied to tools.
- Do not require the LLM to supply an identifier — a record/entity/task UUID, list
  index, or reference key — as a tool argument. Models hallucinate IDs. Resolve
  identifiers from workflow state, the current task context, or a lookup the tool
  performs itself. A tool that needs "which record" derives it from context; it
  does not ask the agent to pass a number.

## 3. Surgical changes

- Touch only what the requested change requires. Do not improve, refactor,
  reformat, or rewrite comments in adjacent code that is not broken.
- Match existing style, naming, and patterns even if you would do it differently.
- Remove imports/variables/helpers/files that YOUR change made unused. Do not
  delete pre-existing dead code unless asked — mention it instead.
- If your diff creates the 2nd copy of a multi-line idiom carrying the same
  rationale comment, extract one helper and move the rationale into its docstring;
  repoint test patch targets to that module in the same commit. Same shape without
  the same rationale: leave it. Pre-existing duplication you did not touch: mention
  it, do not extract.
- When your change alters what a mechanism does, grep for what it made false or
  dead — prose (docstrings, comments, prompt/skill/config text, test docstrings),
  config/map/registry entries that only served the old path, AND contract tests
  that pin the old value (grep the test tree for a removed flag or renamed key
  before declaring done) — and fix it in the same commit. Only fix what you
  falsified; superseded design docs get a note, not a rewrite.

## 4. Goal-driven execution

Turn vague tasks into verifiable goals before implementing:

- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Refactor X" → ensure the preservation checks pass before and after.

For multi-step work keep a short plan where each step has a matching check. Run the
most relevant tests/commands before finishing; if a check cannot run, state why and
the residual risk. Strong success criteria let you loop independently.

## 5. Self-review before presenting

Run the adversarial pass on your own diff BEFORE presenting it. Skip any lens whose
object is absent from the diff.

- **Concept ledger.** List every NEW name the diff defines (functions, classes,
  module constants, enum values, config keys, files, tags). One line each: the
  domain distinction it encodes, or the interface you do not control that requires
  it. Can't write the line → merge or inline it. A near-duplicate name that encodes
  a real distinction passes — put the one-line why-not-reuse at its definition. The
  ledger ships with the presentation; every new definition maps 1:1 to an entry.
- **Kill-list.** Grep the diff for these shapes and fix unless the name/split is a
  required interface or a test seam (then relocate the rationale, never delete it):
  - public wrapper delegating to a single private `_impl` → one function until a
    second caller exists;
  - module constant with one use site → inline it;
  - named one-expression coercion with one caller (e.g. a bool wrapper over a
    tri-state) → write `is True` / `is not True` at the call site (tests assert
    `is True`/`is False`/`is None`, one per state); migrate callers, no compat
    wrapper;
  - helper returning a diagnostics dict when every caller branches yes/no → make it
    a predicate;
  - values computed only to feed a log line at a layer that does not decide →
    delete them; log where you decide;
  - dataclass copy-constructed field-by-field to change one field →
    `dataclasses.replace`.
- **Standing rules as a checklist.** Walk the project's own named rules
  (`AGENTS.md`, `instructions/`, `CLAUDE.md`, memory) explicitly against the diff.
  Past failures were rules that existed and were not invoked.
- **Structure honesty.** Does any function mix a multi-way business decision with
  side-effect mechanics, or carry a docstring describing one branch's plumbing
  instead of the decision? Split the mechanics into a helper; the docstring
  describes the decision.

### Skill and prompt compression

After a skill, SOP, or agent prompt behaves correctly, run a compression pass
before presenting or pushing it:

- Apply the project's canonical authoring guide when one exists, and follow it on
  progressive-disclosure tiers, token budget, and tool-table language rather than
  improvising a format.
- Preserve the behavioral contract; remove explanations the model already knows,
  repeated preconditions, mechanism/history narration, and wording that does not
  change the next action.
- Prefer a compact routing table, explicit boundaries, and default-plus-exception
  rules over repeated branch prose. Do not split a short cohesive procedure just to
  improve a size metric.
- Measure before/after line and token counts, render the full composed prompt the
  agent sees, and read it for contradictions.
- Re-run the scenarios that established correctness plus neighboring regressions. A
  shorter prompt is an improvement only when behavior is preserved.

## 6. Feature work — reach for the canonical flow

Do not freehand the process; use the canonical Batman flow instead.

- **Substantial work** (architecture change, new feature/integration, cross-module
  refactor, unclear multi-file bug, tracked work, production-risk surface) → the
  full **Batman** 8-phase flow: Understanding → Requirements → Design → Task
  Planning → Implementation → Tests → Code Review → Documentation, with explicit
  user approval after each of the four planning phases and Understanding never
  skipped. Stress-test the design with the `grill-me` skill before locking a spec.
- **Read-only questions, exploration, exact doc/config edits, obvious low-risk
  fixes** → handle inline (still run the mnemo `task_context` preflight when using
  repository evidence).
- Behavior changes require an owning approved PRD and accepted ADRs before
  implementation; append outcomes after verification.

## 7. PR push gate

Before pushing any branch that will back a pull request:

1. Run `/simplify` and address every applicable simplification finding.
2. Run `/code-review` against `instructions/code-review.instructions.md` and
   address every actionable finding.
3. Record any intentionally accepted finding with its rationale before pushing.
4. After the push lands on a PR with bot reviewers, arm a Monitor (~30 min) for
   the re-review before closing out.
5. Apply external bot-review findings (Codex/Copilot on the PR) critically, not
   wholesale. They optimize for defensiveness and will request edge-case handling,
   extra guards, and refactors that drift the diff past the task's scope. Act on a
   finding only when it is correct AND critical to the task; otherwise reply on the
   thread documenting why it is out of scope or deferred (open a follow-up if
   warranted) rather than implementing it. When a finding is genuinely ambiguous —
   real defect vs over-engineering — ask the user before changing code. Do not let
   successive bot rounds accrete complexity the task never required.

Do not push the PR branch until the simplify and review passes have completed. Do
not create commits or PRs unless the user asks.
