---
name: sop-vs-agent-behavior
description: Systematically compares agent execution (tool calls, reasoning) to the SOP the agent had in context to find why the agent did not follow the SOP. Use when the agent had the right SOP and tools but still failed judge criteria, when classifying AGENT_OR_SETUP vs JUDGE_MISMATCH, when finding the needle-in-the-haystack root cause, or when comparing agent behavior to SOP sections.
---

# SOP vs Agent Behavior

## When to Use This Skill

Use this skill **after** ruling out configuration and setup issues. If you have not yet verified execution flow and scenario config, use the [debugging-scenario-tests](.cursor/skills/debugging-scenario-tests/SKILL.md) skill first (read stage JSON → which SOP fetched → timer motivation, load_state, mocks). This skill is for cases where the agent **had the correct SOP and tools** but **did not follow the SOP** — the "needle in the haystack" analysis.

**Triggers:** Agent didn't follow SOP; classifying AGENT_OR_SETUP vs JUDGE_MISMATCH; judge says unmet criteria but agent had context; finding why agent did X when SOP says Y.

## Core Principle

**Compare evidence, not assumptions.** Build a verified-facts table: what the SOP says, what the agent had in context, what the agent did. Then explain the gap (wording confusion, underweighted section, wrong tool choice, early exit).

## Checklist

Copy and track progress:

```
SOP vs Behavior Progress:
- [ ] Step 1: Identify which SOP was fetched and which sections apply
- [ ] Step 2: List tools available to the agent (from SOP or tool list)
- [ ] Step 3: Extract what the agent did (tool calls, reasoning, order)
- [ ] Step 4: Build verified-facts table (SOP says / Agent had / Agent did)
- [ ] Step 5: Gap analysis — why the mismatch (wording, weight, missing step)
- [ ] Step 6: Output verdict + root cause + proposed fix
```

## Step 1: Identify SOP and Relevant Sections

- **From stage JSON:** In `messages[]`, find a tool message where the tool was `dynamic_sops_fetch`. The message `content` holds the SOP text; `metadata` may contain `path` (e.g. `app/templates/tasks/confirm_delivery/unrelated_inbound_communication/ally/SOP.md`).
- **By convention:** `app/templates/tasks/<task>/<sub_agent>/<broker_lower>/SOP.md` (shipper-specific: add `<shipper_group>/SOP.md` under broker when applicable).
- **Relevant sections:** Match the scenario type (e.g. "Driver requests missing info" → Intent 3 "Questions about load", "load information missing" subsection). Quote the exact SOP bullets or paragraphs that require the unmet criteria.

## Step 2: Tools Available to the Agent

- From the **SOP text** (e.g. "Use `send_broker_notification` with `escalate=true`", "Use `send_tms_notes`").
- From the **stage context** or graph: which tools were in scope for this sub-agent. If the agent did not call a tool the SOP requires, note whether that tool was available (if unsure, state "assumed available" and focus on behavior).

## Step 3: What the Agent Did

From the stage JSON `messages[]`:

- **Assistant messages:** Read `content` (reasoning) and `toolCalls[]` (name, arguments). Order matters.
- **Tool messages:** Confirm success/failure and result shape; for `dynamic_sops_fetch`, the SOP content is in the tool result.
- **Sequence:** List tool calls in order (e.g. `dynamic_sops_fetch(unrelated_inbound_communication_sop)` → `get_load_info` → `send_sms` → stop). Note if the agent exited without calling a required tool.

## Step 4: Verified-Facts Table

Build a small table so the comparison is explicit:

| Fact | SOP says | Agent had in context | Agent did |
|------|----------|------------------------|-----------|
| Escalation when load info not found | Use `send_broker_notification` with `escalate=true`; send TMS note | Unrelated-inbound SOP with Intent 3 "missing info" instructions | Sent SMS only; no broker notification; no TMS note |
| … | … | … | … |

Adjust rows to the specific failure. This makes the gap obvious and avoids vague "agent didn't follow SOP" conclusions.

## Step 5: Gap Analysis (Why the Mismatch)

Common causes:

- **Wording confusion:** SOP says "Slack" or "notify broker" but the tool is `send_broker_notification`. Agent may have underweighted the instruction or mapped "Slack" to a different action.
- **Underweighted subsection:** The required step is in a sub-bullet or "Sending a notification when load information is missing"; agent followed the main intent but skipped the escalation sub-step.
- **Early exit:** Agent decided "no further tools needed" after one action (e.g. sent SMS) and did not read or apply the escalation requirement.
- **Wrong intent or branch:** Agent classified the message under a different intent (e.g. no_action_required) so never applied the intent card that requires the missing action.
- **Tool name vs natural language:** SOP describes the action in prose; agent had the tool but did not associate the prose with the tool name — call this out explicitly in root cause.

Use the verified-facts table to choose the most likely cause and state it in one or two sentences.

## Step 6: Output Format

Produce a short report so it can be aggregated (e.g. with other failed stages):

```markdown
- **Verdict:** AGENT_OR_SETUP | JUDGE_MISMATCH | CONFIG_ISSUE | UNCLEAR
- **Unmet:** [list judge criteria that were unmet]
- **Root cause:** [2–4 sentences: what SOP required, what agent had, what agent did, and why the gap — wording, underweighting, wrong branch, etc.]
- **Proposed fix:** [No judge change. Fix agent behavior / clarify SOP / fix scenario config — and what to change.]
```

**Verdict guidance:**

- **AGENT_OR_SETUP:** SOP requires the unmet behavior; agent had the right SOP and tools but did not perform it. Fix agent or verify state/mocks so the agent reaches the right path.
- **JUDGE_MISMATCH:** SOP does not require what the judge marks as unmet. Fix judge (criteria or logic).
- **CONFIG_ISSUE:** Wrong SOP fetched, wrong timer motivation, or missing/incorrect mocks (e.g. load_state, task_metadata). Fix scenario config; see debugging-scenario-tests.
- **UNCLEAR:** Cannot determine from evidence; call out what’s missing (e.g. SOP section ambiguous, tool availability unknown).

## Artifacts Quick Reference

| What you need | Where |
|---------------|--------|
| Which SOP was fetched | Stage JSON `messages[]` → tool message for `dynamic_sops_fetch` → `metadata.path` or result content |
| SOP full text | Same tool message `content` (or read file at `path`) |
| Agent tool calls and order | `messages[]` → assistant messages → `toolCalls[]` (name, arguments) |
| Agent reasoning | `messages[]` → assistant messages → `content` |
| Judge unmet criteria | Stage `results.unmetCriteria`, `results.reasoning` |
| Scenario/stage context | Stage `input_data`, `metadata`, scenario_id, task, broker |

## Anti-Patterns

- **Don’t assume without evidence:** Avoid "agent probably didn’t read the SOP." Point to the section the agent had and the tool it did or didn’t call.
- **Don’t skip the verified-facts table:** Without it, root cause stays vague and fixes are hard to prioritize.
- **Don’t blame the judge first:** If the SOP clearly requires the behavior and the agent didn’t do it, verdict is AGENT_OR_SETUP (or CONFIG_ISSUE if wrong SOP was fetched); only mark JUDGE_MISMATCH when the SOP does not require the unmet criterion.
- **Don’t mix config debugging with behavior analysis:** If the wrong SOP was fetched (e.g. wrong timer motivation), that’s CONFIG_ISSUE — fix scenario config per debugging-scenario-tests, then re-run; SOP-vs-agent-behavior is for when the **right** SOP was in context and the agent still didn’t follow it.

## Relation to Other Skills

- **debugging-scenario-tests:** Use first to confirm correct execution flow (which SOP, mocks, timer motivation). Use SOP-vs-agent-behavior when the failure is specifically "agent had the right SOP and tools but didn’t follow the SOP."
- **create-scenario-tests / scenario judges:** After root cause is AGENT_OR_SETUP or JUDGE_MISMATCH, use those skills to adjust scenarios or judges as needed.
