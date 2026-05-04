---
name: create-scenario-tests
description: Create Deep Agent workflow scenario tests using the langwatch/scenario framework. Use when creating new scenario tests, adding judges, defining criteria, or testing agent workflows for confirm_delivery, confirm_pickup, tracking_checkpoint, or ETA checkpoint routines.
---

# Creating Scenario Tests for Deep Agent Workflows

## Quick Reference

```
tests/deep_agents/workflow/
├── core/                        # Reusable framework
│   ├── criteria.py              # Criteria helper functions
│   ├── judge_factory.py         # Pre-built judge factories
│   ├── mock_context.py          # MockContext for service mocks
│   ├── adapters.py              # LangGraph agent adapters
│   └── scenario_runner.py       # Multi-stage execution
├── {workflow}/                  # Per-workflow tests
│   ├── scenario_definitions.py  # Scenario fixtures
│   └── test_scenarios.py        # Parametrized test runner
└── shared/input_data.py         # Test state builders
```

---

## Creating a New Scenario

### Step 1: Create Judge (if needed)

Add to `core/judge_factory.py`:

```python
def make_my_new_judge() -> scenario.JudgeAgent:
    """Purpose: What this judge validates."""
    criteria: CriteriaList = [
        tool_usage_criteria("send_sms", called=True),
        tms_note_criteria("status_update"),
        slack_criteria("notification_purpose"),
        status_criteria("WAITING"),
    ]
    return create_judge(criteria, context="description of evaluation context")
```

### Step 2: Export Judge

Add to `core/__init__.py`:

```python
# In imports section
from .judge_factory import (
    # ... existing judges ...
    make_my_new_judge,
)

# In __all__ list
__all__ = [
    # ... existing exports ...
    "make_my_new_judge",
]
```

### Step 3: Create Scenario Fixture

Add to `{workflow}/scenario_definitions.py`:

```python
def scenario_my_new_scenario() -> ScenarioFixture:
    """Docstring explaining what this scenario tests."""
    config = ScenarioConfig(
        name="My Scenario Name",
        description="Detailed description for judge context",
        task="confirm_delivery",  # or confirm_pickup, etc.
        thread_id="unique-thread-id-123",
        initial_state=_base_state(),
        stages=[
            StageConfig(
                name="Stage 1",
                description="What happens in this stage",
                judge=make_my_new_judge(),
            ),
        ],
    )
    return ScenarioFixture(config=config)
```

### Step 4: Register Scenario

Add to `SCENARIO_BUILDERS` at bottom of `scenario_definitions.py`:

```python
SCENARIO_BUILDERS = [
    # ... existing scenarios ...
    ("my_new_scenario", scenario_my_new_scenario),
]
```

---

## Available Criteria Helpers

Import from `tests.deep_agents.workflow.core`:

| Helper | Purpose | Example |
|--------|---------|---------|
| `status_criteria(status)` | Verify `set_task_status` call | `status_criteria("WAITING")` |
| `timer_criteria(hours, motivation)` | Verify `set_timer` call | `timer_criteria(hours=1.0, motivation="follow_up")` |
| `communication_criteria(channel, purpose)` | Verify SMS/email sent | `communication_criteria("sms", "acknowledge_driver")` |
| `tms_note_criteria(purpose)` | Verify `send_tms_notes` call | `tms_note_criteria("status_update")` |
| `slack_criteria(purpose)` | Verify `send_slack_message` | `slack_criteria("stale_tracking")` |
| `tool_usage_criteria(tool, called)` | Generic tool usage | `tool_usage_criteria("create_task", called=False)` |
| `broker_notification_criteria(purpose, escalate)` | Ally broker notifications | `broker_notification_criteria("delay", escalate=True)` |
| `escalation_criteria(allowed)` | Verify escalation behavior | `escalation_criteria(allowed=False)` |
| `load_state_criteria(state)` | Verify load state update | `load_state_criteria("delivered")` |

---

## MockContext Configuration

Use `context_kwargs` in fixture or override per-stage:

```python
return ScenarioFixture(
    config=config,
    context_kwargs={
        "current_time": datetime(2025, 11, 15, 18, 0, tzinfo=UTC),
        "classify_attachments_result": {"att-id": {"category": "pod"}},
        "check_document_result": {"att-id": True},
        "past_comms_summary": "Previous conversation...",
        "load_state": "at-delivery",
        "task_metadata": {"stale_tracking_attempts": 1},
    },
)
```

### Available Mock Overrides

| Property | Purpose |
|----------|---------|
| `current_time` | Override `get_current_time_utc()` |
| `classify_attachments_result` | Mock attachment classification |
| `check_document_result` | Mock document validation |
| `past_comms_summary` | Mock conversation history |
| `load_state` | Single load state value |
| `load_state_sequence` | Sequence of states for multi-call |
| `task_metadata` | Mock DynamoDB task metadata |

---

## Multi-Stage Scenarios

For scenarios with multiple agent invocations:

```python
def scenario_multi_stage() -> ScenarioFixture:
    config = ScenarioConfig(
        name="Multi-Stage Scenario",
        description="Tests agent across multiple interactions",
        task="confirm_delivery",
        thread_id="multi-stage-123",
        initial_state=_base_state(),
        stages=[
            StageConfig(
                name="Stage 1: Initial Contact",
                description="Agent sends first message",
                judge=make_initial_contact_judge(),
            ),
            StageConfig(
                name="Stage 2: Driver Response",
                description="Agent handles driver reply",
                judge=make_response_judge(),
                state_builder=with_inbound_communication(
                    content="Driver message here",
                    channel="sms",
                ),
            ),
            StageConfig(
                name="Stage 3: Follow-up Timer",
                description="Agent handles timer event",
                judge=make_follow_up_judge(),
                state_builder=with_time_based_event(
                    motivation="pending_status_follow_up",
                    reminder_message="Follow up with driver",
                ),
                time_override=datetime(2025, 11, 15, 20, 0, tzinfo=UTC),
            ),
        ],
    )
    return ScenarioFixture(config=config)
```

### State Builders

| Builder | Purpose |
|---------|---------|
| `with_inbound_communication(content, channel, attachments)` | Add driver/broker message |
| `with_time_based_event(motivation, reminder_message)` | Add timer trigger |
| `with_tracking_data(tracking_data)` | Add tracking information |
| `with_resumption_context(message, source)` | Add human operator resumption |

---

## Workflow-Specific Patterns

### Stale Tracking (tracking_checkpoint)

Uses facts-based fixtures with custom adapter:

```python
@dataclass
class StaleTrackingScenarioFixture:
    name: str
    description: str
    facts: dict  # Contains tracking timestamps, attempt counts
    judge: scenario.JudgeAgent
    context_kwargs: dict | None = None

def scenario_ufs_stale_first_attempt() -> StaleTrackingScenarioFixture:
    now = datetime.now(UTC)
    facts = {
        "broker_name": "UFS",
        "tracking_ever_established": True,
        "tracking_age_minutes": 60.0,
        "stale_tracking_attempts": 0,
        "last_stale_tracking_driver_contact_utc": None,
        # ... more facts
    }
    return StaleTrackingScenarioFixture(
        name="UFS - First Attempt SMS",
        description="First stale tracking attempt uses SMS",
        facts=facts,
        judge=make_ufs_stale_first_attempt_sms_judge(),
    )
```

### Confirm Delivery / Pickup

Uses ScenarioConfig with multi-stage support. See `confirm_delivery/scenario_definitions.py` for examples.

---

## Running Tests

```bash
# Run all scenarios for a workflow
poetry run pytest tests/deep_agents/workflow/confirm_delivery/ -v

# Run specific scenario by ID
poetry run pytest tests/deep_agents/workflow/confirm_delivery/ -k "my_scenario_id" -v

# Collect tests without running (verify registration)
poetry run pytest tests/deep_agents/workflow/ --collect-only -q

# Run with timeout for slow LLM calls
poetry run pytest tests/deep_agents/workflow/ -v --timeout=120
```

---

## Checklist for New Scenarios

1. **Judge**
   - [ ] Created in `judge_factory.py` with descriptive docstring
   - [ ] Uses appropriate criteria helpers
   - [ ] Exported in `core/__init__.py` (imports + `__all__`)

2. **Scenario Fixture**
   - [ ] Created function in `scenario_definitions.py`
   - [ ] Has descriptive docstring explaining what it tests
   - [ ] Facts/state values are logically consistent
   - [ ] Context kwargs set if needed (time, mocks)

3. **Registration**
   - [ ] Added to `SCENARIO_BUILDERS` list
   - [ ] ID is unique and descriptive (snake_case)
   - [ ] Imported judge in scenario_definitions.py

4. **Verification**
   - [ ] `pytest --collect-only` shows new scenario
   - [ ] No linter errors in modified files

---

## Anti-Patterns

### Inconsistent Facts

```python
# BAD: attempts=0 but last_contact has a value
facts = {
    "stale_tracking_attempts": 0,
    "last_stale_tracking_driver_contact_utc": "2025-01-01T12:00:00Z",  # Inconsistent!
}

# GOOD: attempts=0 means no contact yet
facts = {
    "stale_tracking_attempts": 0,
    "last_stale_tracking_driver_contact_utc": None,
}
```

### Missing Judge Export

```python
# BAD: Judge created but not exported - import will fail
# Only in judge_factory.py, missing from __init__.py

# GOOD: Judge exported in both places
# judge_factory.py: def make_my_judge()
# __init__.py: from .judge_factory import make_my_judge
# __init__.py: __all__ = [..., "make_my_judge"]
```

### Vague Criteria Descriptions

```python
# BAD: Unclear what the agent should do
criteria = [("does_something", "The agent does something.")]

# GOOD: Specific tool and expected behavior
criteria = [
    tool_usage_criteria("send_sms", called=True, extra="Must send SMS to driver"),
    tms_note_criteria("tracking_status_update"),
]
```
