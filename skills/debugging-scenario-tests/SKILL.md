---
name: debugging-scenario-tests
description: Debug failing deep agent workflow scenario tests by tracing execution flow. Use when scenario tests fail, when investigating mock issues, when tests pass/fail unexpectedly, or when analyzing JSON response files from test runs.
---

# Debugging Scenario Tests

## Core Principle: Top-Down, Not Bottom-Up

**Always trace execution flow from scenario → agent behavior → tool calls → mocks.**

Never start by debugging mocks or patch targets. Start by understanding what the agent actually did.

## Debugging Checklist

Copy and track progress:

```
Debug Progress:
- [ ] Step 1: Read actual execution output (JSON response)
- [ ] Step 2: Identify which SOP was fetched
- [ ] Step 3: Check timer motivation in scenario definition
- [ ] Step 4: Check load_state mock value
- [ ] Step 5: Trace tool call sequence
- [ ] Step 6: Only then check mock configurations
```

## Step 1: Read Execution Output First

Before hypothesizing about mocks or code issues, read the JSON response file:

```bash
# Find the response file (usually in docs/wip/ or test output)
# Look for tool calls the agent made
```

**Key questions:**
- What `dynamic_sops_fetch` call was made? Which SOP was requested?
- Did the agent call `get_time_to_appointment`? With what response?
- Did the agent call `get_load_state`? What value returned?
- Did the agent exit early? Why?

## Step 2: Understand the Dispatch Chain

Timer motivation determines which SOP is fetched:

| Timer Motivation | SOP Fetched | Contains |
|------------------|-------------|----------|
| `unresponsive_contact` | `unresponsive_driver_sop` | Escalation logic, task creation |
| `pending_status_follow_up` | `pending_status_follow_up_sop` | Status check, early exit on delivery |
| `initial_contact` | `initial_contact_sop` | First contact logic |

**Critical:** If you see the wrong SOP being fetched, check `state_builder=with_time_based_event(motivation=...)` in the scenario definition.

## Step 3: Check Scenario Configuration

Common issues in `scenario_definitions.py`:

### Wrong Timer Motivation

```python
# BAD: This fetches pending_status_follow_up_sop (no escalation logic)
StageConfig(
    state_builder=with_time_based_event(
        motivation="pending_status_follow_up",  # ← Wrong for escalation
    ),
)

# GOOD: This fetches unresponsive_driver_sop (has Scenario 4 escalation)
StageConfig(
    state_builder=with_time_based_event(
        motivation="unresponsive_contact",  # ← Correct
    ),
)
```

### Missing Load State Mock

```python
# BAD: Default load_state is "at-delivery" - agent may exit early
StageConfig(
    mock_overrides={
        "task_metadata": {...},
        # Missing load_state!
    },
)

# GOOD: Explicit load_state keeps agent in expected workflow
StageConfig(
    mock_overrides={
        "task_metadata": {...},
        "load_state": "at-pickup",  # ← Prevents early exit
    },
)
```

### Timestamp Mismatches

Ensure timestamps in `mock_overrides` align with scenario base date:

```python
# If scenario uses base_time = datetime(2025, 11, 13, ...)
# Then timestamps must also be 2025-11-13, NOT a future date

mock_overrides={
    "task_metadata": {
        # BAD: 2025-11-15 is AFTER base_time → hours_since = 0
        "unresponsive_contact_first_attempt_utc": "2025-11-15T18:00:00.000Z",
        
        # GOOD: 2025-11-13 is BEFORE escalation → hours_since > 2
        "unresponsive_contact_first_attempt_utc": "2025-11-13T14:00:00.000Z",
    }
}
```

## Step 4: Verify Mock Application

Only after understanding execution flow, check mock mechanics:

1. **Is the mock configured in `MockContext`?**
   - Check `tests/deep_agents/workflow/core/mock_context.py`
   
2. **Is `mock_overrides` applied in `scenario_runner.py`?**
   - Check the `run_scenario` function handles your override key

3. **Is the patch target correct?**
   - Must match the import path where the function is called, not defined

## Anti-Patterns

### Don't Trust Bug Reports as Root Causes

Bug reports describe **symptoms**, not causes. Always verify:

```markdown
# Bug report says: "task_metadata_service not mocked"
# Reality might be: Mock exists, but wrong SOP was fetched so code never ran
```

### Don't Debug Bottom-Up

```markdown
# BAD sequence:
1. Check mock patch target
2. Check import paths
3. Check return values
4. Finally read what agent did  ← Too late!

# GOOD sequence:
1. Read JSON response - what did agent do?
2. Identify unexpected behavior
3. Trace back to scenario config
4. Only then check mocks if needed
```

### Don't Assume Code Issues

Most scenario failures are **configuration issues**, not code bugs:
- Wrong timer motivation
- Missing mock overrides
- Timestamp misalignment
- Incorrect load_state

## Quick Reference: Mock Override Keys

| Key | Purpose | Example Value |
|-----|---------|---------------|
| `task_metadata` | Unresponsive tracking data | `{"unresponsive_contact_attempts": 2}` |
| `load_state` | Current load status | `"at-pickup"`, `"at-delivery"` |
| `tracking_data` | Tracking age, staleness | `{"tracking_age_minutes": 200}` |
| `sms_history` | Driver response detection | `[{"direction": "inbound", ...}]` |

## Files to Check (In Order)

1. **JSON response file** - What the agent actually did
2. **scenario_definitions.py** - Stage configs, mock_overrides, state_builder
3. **SOP file** - What behavior is expected for the fetched SOP
4. **mock_context.py** - Only if mock mechanics are suspect
5. **scenario_runner.py** - Only if override application is suspect
