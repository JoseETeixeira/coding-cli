# Scenario Tests Reference

Detailed reference for the Deep Agent workflow scenario testing framework.

## Complete Criteria Catalog

### Status and Lifecycle

```python
# Task status (lifecycle_status parameter)
status_criteria("WAITING")   # Agent must set task to WAITING
status_criteria("COMPLETED") # Agent must set task to COMPLETED
status_criteria("PAUSED")    # Agent must set task to PAUSED
status_criteria("IDLE")      # Agent must set task to IDLE

# Lifecycle status (alternative)
lifecycle_status_criteria("AWAITING_EXTERNAL_INPUT")
lifecycle_status_criteria("PAUSED")
lifecycle_status_criteria("COMPLETED")
```

### Timers

```python
# Basic timer
timer_criteria(hours=1.0)

# Timer with motivation
timer_criteria(hours=0.5, motivation="pending_status_follow_up")

# Timer deletion
timer_criteria(deleted=True)
```

### Communication

```python
# SMS communication
communication_criteria("sms", "acknowledge_arrival")
communication_criteria("sms", "request_pod_photo", content_must_include=["POD", "photo"])

# Email communication
communication_criteria("email", "confirm_delivery")

# Any channel
communication_criteria("any", "driver_notification")

# Negated (must NOT send)
communication_criteria("sms", "driver_contact", negated=True)
```

### Tool Usage

```python
# Tool must be called
tool_usage_criteria("send_sms", called=True)
tool_usage_criteria("create_task", called=True, extra="Escalate to human operator")

# Tool must NOT be called
tool_usage_criteria("send_sms", called=False, extra="Driver cooldown not satisfied")
tool_usage_criteria("create_task", called=False, extra="Task already created")
```

### Notifications

```python
# TMS Notes
tms_note_criteria("status_update")
tms_note_criteria("delivery_confirmed")
tms_note_criteria("stale_tracking_contact_attempt")

# Slack (internal)
slack_criteria("stale_tracking")
slack_criteria("detention_alert")
slack_criteria("unresponsive_escalation")

# Broker notification (Ally-style)
broker_notification_criteria("delay_notification", escalate=False)
broker_notification_criteria("urgent_escalation", escalate=True, escalation_type="restack")

# Any notification (broker-agnostic)
notification_any_criteria("status_update", escalate=False)
```

### Load State

```python
load_state_criteria("pod_collected")
load_state_criteria("delivered")
load_state_criteria("on_route")

# Specific helpers
load_state_delivered_criteria()
load_state_on_route_criteria()
load_state_pod_collected_criteria()
load_state_arrival_criteria(direction="delivery")
```

### ETA Checkpoint

```python
eta_update_criteria(direction="pickup")
eta_update_criteria(direction="delivery")
```

### Escalation

```python
escalation_criteria(allowed=True)   # Must escalate
escalation_criteria(allowed=False)  # Must NOT escalate

# No escalation tools
no_escalation_tools_criteria()
```

### Content Requirements

```python
# Detention language
detention_language_criteria(must_not_mention=True)   # Must NOT use detention terms
detention_language_criteria(must_not_mention=False)  # Must mention detention

# Neutral framing
neutral_framing_criteria()  # Must use neutral language instead of detention

# BOL disclaimer
bol_disclaimer_criteria(require_bol_reference=True, require_verify_language=True)

# Channel matching
channel_match_criteria("sms")    # Response must be SMS
channel_match_criteria("email")  # Response must be email
```

### Guards

```python
no_external_communication_criteria()  # No SMS, email, or Slack
no_escalation_tools_criteria()        # No create_task or create_issue
set_not_tracking_criteria()           # Must call set_load_location_tag_not_tracking
```

---

## MockContext STATIC_MOCKS

Pre-configured mocks that are always active:

| Mock Target | Default Return Value |
|-------------|---------------------|
| `send_sms` | `{"status": "SUCCESS", "message_id": "sms-test-123"}` |
| `send_slack_message` | `(True, None, {"status": "SUCCESS"})` |
| `send_broker_notification` | `(True, None, {"status": "SUCCESS"})` |
| `send_tms_notes` | `{"status": "SUCCESS", "result": "TMS note stored"}` |
| `reply_email_thread` | `{"status": "SUCCESS", "communication_id": "email-reply-123"}` |
| `create_schedule` (timer) | `{"status": "SUCCESS", "schedule_arn": "arn:aws:scheduler:test"}` |
| `delete_schedule` | `True` |
| `_create_task_impl` | `{"status": "SUCCESS", "task_uuid": "task-test-123"}` |
| `_create_issue_impl` | `{"status": "SUCCESS", "result": "Issue created"}` |
| `update_load_state_*` | `(True, None)` |
| `update_load_eta` | `(True, None)` |
| `store_task_metadata` | `True` |

---

## Scenario Framework (langwatch/scenario)

### Basic Structure

```python
result = await scenario.run(
    name="scenario name",
    description="context for judge",
    agents=[
        YourAgentAdapter(),       # Agent under test
        scenario.JudgeAgent(...), # Evaluator
    ],
    script=[
        scenario.agent(),  # Agent takes turn
        scenario.judge(),  # Judge evaluates
    ],
)
assert result.success
```

### Agent Adapter

```python
class MyAgentAdapter(scenario.AgentAdapter):
    @scenario.cache()  # Cache results for determinism
    async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
        # Invoke your agent and return OpenAI-format messages
        messages = await invoke_agent(...)
        return convert_to_openai_messages(messages)
```

### JudgeAgent

```python
scenario.JudgeAgent(
    model="gpt-4o",
    temperature=0.0,
    criteria=["criterion_1", "criterion_2"],
    system_prompt="You are an evaluation judge for X. Apply these criteria strictly: ..."
)
```

---

## File Templates

### scenario_definitions.py Template

```python
"""Scenario fixtures for {workflow} workflow tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from tests.deep_agents.workflow.core import (
    ScenarioConfig,
    StageConfig,
    make_your_judge,
    # ... import judges
)
from tests.deep_agents.workflow.shared.input_data import get_test_state

UTC = timezone.utc


@dataclass
class ScenarioFixture:
    config: ScenarioConfig
    context_kwargs: dict = field(default_factory=dict)
    post_assert: Callable | None = None


def _base_state(**kwargs) -> dict:
    return get_test_state(task_instruction_type="{workflow}", kwargs=kwargs or None)


def scenario_example() -> ScenarioFixture:
    """Example scenario description."""
    config = ScenarioConfig(
        name="Example Scenario",
        description="What this scenario tests",
        task="{workflow}",
        thread_id="example-123",
        initial_state=_base_state(),
        stages=[
            StageConfig(
                name="Stage 1",
                description="Stage description",
                judge=make_your_judge(),
            ),
        ],
    )
    return ScenarioFixture(config=config)


SCENARIO_BUILDERS = [
    ("example", scenario_example),
]
```

### test_scenarios.py Template

```python
"""Scenario tests for {workflow} workflow."""

from __future__ import annotations

import pytest

from tests.deep_agents.workflow.core import MockContext, run_scenario
from tests.deep_agents.workflow.{workflow}.scenario_definitions import (
    SCENARIO_BUILDERS,
    ScenarioFixture,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario_id, fixture_builder",
    SCENARIO_BUILDERS,
    ids=[scenario_id for scenario_id, _ in SCENARIO_BUILDERS],
)
async def test_{workflow}_scenarios(scenario_id: str, fixture_builder):
    fixture: ScenarioFixture = fixture_builder()
    with MockContext(**fixture.context_kwargs) as ctx:
        results = await run_scenario(fixture.config, ctx)
        assert all(result.success for result in results), f"Scenario failed: {scenario_id}"
        if fixture.post_assert:
            fixture.post_assert(ctx)
```

---

## Debugging Tips

### View Scenario Report

The scenario result contains detailed information:

```python
result = await scenario.run(...)
print(f"Success: {result.success}")
print(f"Passed: {result.passed_criteria}")
print(f"Failed: {result.failed_criteria}")
# Judge's reasoning is in the verdict
```

### Check Mock Calls

```python
def my_post_assert(ctx: MockContext):
    # Check if SMS was sent
    assert ctx.sms_mock.called
    
    # Check SMS content
    call_args = ctx.sms_mock.call_args_list[0]
    assert "expected content" in str(call_args)
    
    # Check metadata updates
    assert ctx.store_task_metadata_mock.called
```

### Common Failures

1. **Judge criteria not matching SOP**: Update criteria to match actual SOP behavior
2. **Inconsistent facts**: Ensure facts are logically consistent (e.g., attempts=0 means no prior contact)
3. **Missing mock**: If tool call fails, check MockContext.STATIC_MOCKS
4. **Import error**: Ensure judge is exported in `core/__init__.py`
