# Safe Refactoring Testing - Examples

Concrete examples extracted from production refactoring efforts.

## Example 1: Characterization Tests for Location Extraction

Before refactoring scattered `.get()` chains into `LoadContextInput` properties, capture existing behavior:

```python
"""Characterization tests for tool_result_mappers location UUID extraction.

These tests capture CURRENT behavior before refactoring.
They should PASS now and continue to PASS after refactoring.
"""
import pytest
from app.utils.tool_result_mappers import map_tool_result


class TestMapTimelineLocationUuidCharacterization:
    """Capture current location UUID extraction behavior in _map_timeline."""

    def test_resolves_timezone_from_pickup_uuid_match(self):
        """Current behavior: matches pickup UUID to resolve timezone."""
        tool_result = {
            "status": "SUCCESS",
            "result": {"calculated_eta": "2026-01-28T15:00:00Z"}
        }
        state = {
            "load_data": {
                "locations": {
                    "pickup": {"uuid": "loc-123", "timezone": "America/Chicago"},
                    "delivery": {"uuid": "loc-456", "timezone": "America/New_York"}
                }
            }
        }
        injected_context = {"location_id": "loc-123"}
        
        result = map_tool_result(
            "timeline_sanity_check_with_tracking_data",
            tool_result,
            state,
            injected_context
        )
        
        # Verify timezone was resolved from pickup
        assert "calculated_eta_local" in result["result"]

    def test_handles_missing_locations(self):
        """Current behavior: handles missing locations gracefully."""
        tool_result = {
            "status": "SUCCESS",
            "result": {"calculated_eta": "2026-01-28T15:00:00Z"}
        }
        state = {"load_data": {}}
        injected_context = {"location_id": "loc-123"}
        
        result = map_tool_result(
            "timeline_sanity_check_with_tracking_data",
            tool_result,
            state,
            injected_context
        )
        
        # Should not crash, uses UTC fallback
        assert result is not None

    def test_handles_missing_uuid_in_locations(self):
        """Current behavior: handles missing UUID in location data."""
        tool_result = {
            "status": "SUCCESS",
            "result": {"calculated_eta": "2026-01-28T15:00:00Z"}
        }
        state = {
            "load_data": {
                "locations": {
                    "pickup": {"timezone": "America/Chicago"},  # No UUID
                    "delivery": {"timezone": "America/New_York"}
                }
            }
        }
        injected_context = {"location_id": "loc-123"}
        
        result = map_tool_result(
            "timeline_sanity_check_with_tracking_data",
            tool_result,
            state,
            injected_context
        )
        
        # Should not crash
        assert result is not None
```

---

## Example 2: TDD Unit Tests for Pydantic Model Properties

Write failing tests first when creating new `TaskMetadataContext` model:

```python
"""Unit tests for TaskMetadataContext model (TDD).

These tests are written BEFORE implementation.
Expected flow: FAIL → implement → PASS
"""
import pytest
from app.models.task_metadata_context import TaskMetadataContext


class TestTaskMetadataContextRiskProperties:
    """Tests for risk-related properties."""

    def test_risk_level_returns_value_when_present(self):
        ctx = TaskMetadataContext(raw_metadata={"risk_level": "HIGH"})
        assert ctx.risk_level == "HIGH"

    def test_risk_level_returns_none_when_missing(self):
        ctx = TaskMetadataContext(raw_metadata={})
        assert ctx.risk_level is None

    def test_previous_risk_level_returns_value_when_present(self):
        ctx = TaskMetadataContext(raw_metadata={"previous_risk_level": "LOW"})
        assert ctx.previous_risk_level == "LOW"

    def test_risk_history_returns_list_when_present(self):
        ctx = TaskMetadataContext(raw_metadata={"risk_history": ["LOW", "MEDIUM", "HIGH"]})
        assert ctx.risk_history == ["LOW", "MEDIUM", "HIGH"]

    def test_risk_history_returns_none_when_missing(self):
        ctx = TaskMetadataContext(raw_metadata={})
        assert ctx.risk_history is None


class TestTaskMetadataContextTrackingProperties:
    """Tests for tracking data properties."""

    def test_tracking_data_returns_dict_when_present(self):
        ctx = TaskMetadataContext(raw_metadata={"tracking_data": {"timestamp": "2026-01-28T10:00:00Z"}})
        assert ctx.tracking_data == {"timestamp": "2026-01-28T10:00:00Z"}

    def test_tracking_data_returns_empty_dict_when_missing(self):
        ctx = TaskMetadataContext(raw_metadata={})
        assert ctx.tracking_data == {}

    def test_tracking_timestamp_from_nested_data(self):
        ctx = TaskMetadataContext(raw_metadata={"tracking_data": {"timestamp": "2026-01-28T10:00:00Z"}})
        assert ctx.tracking_timestamp == "2026-01-28T10:00:00Z"

    def test_tracking_timestamp_returns_none_when_no_tracking_data(self):
        ctx = TaskMetadataContext(raw_metadata={})
        assert ctx.tracking_timestamp is None


class TestTaskMetadataContextFactoryMethods:
    """Tests for factory methods."""

    def test_from_dict_with_data(self):
        data = {"risk_level": "MEDIUM", "timezone": "America/Chicago"}
        ctx = TaskMetadataContext.from_dict(data)
        assert ctx.risk_level == "MEDIUM"
        assert ctx.timezone == "America/Chicago"

    def test_from_dict_with_none(self):
        ctx = TaskMetadataContext.from_dict(None)
        assert ctx.raw_metadata == {}

    def test_from_dict_with_empty_dict(self):
        ctx = TaskMetadataContext.from_dict({})
        assert ctx.raw_metadata == {}

    def test_empty_creates_empty_context(self):
        ctx = TaskMetadataContext.empty()
        assert ctx.raw_metadata == {}
        assert ctx.risk_level is None
```

---

## Example 3: Characterization Tests for Message Processor Extraction

Before extracting `_process_task_message` to a separate module:

```python
"""Characterization tests for _process_task_message.

These tests capture existing behavior BEFORE extraction.
"""
from unittest.mock import Mock, patch
import pytest
from app.models.state import TaskStatus


class TestProcessTaskMessageCharacterization:
    """Capture current behavior of task message processing."""
    
    load_id = "load-123"
    task_uuid = "task-456"
    
    def _build_message(self, **overrides):
        base = {
            "payload": {
                "task_uuid": self.task_uuid,
                "task_instruction_type": "CONFIRM_PICKUP",
            }
        }
        base["payload"].update(overrides)
        return base
    
    @patch("app.workers.task_worker.queue_service")
    @patch("app.workers.task_worker.process_task")
    @patch("app.workers.task_worker.task_service")
    @patch("app.workers.task_worker.load_service")
    def test_success_when_task_pending(
        self, mock_load, mock_task, mock_process, mock_queue
    ):
        """Current behavior: processes successfully when task is PENDING."""
        from app.workers import task_worker
        
        mock_load.get_load.return_value = {"load_data": {}}
        mock_task.get_task.return_value = {
            "task_uuid": self.task_uuid,
            "lifecycle_status": TaskStatus.PENDING.value,
        }
        mock_process.return_value = {"status": "completed"}
        
        result = task_worker._process_task_message(
            Mock(), self._build_message(), self.load_id
        )
        
        assert result["status"] == "completed"
        mock_process.assert_called_once()
        mock_queue.move_to_dlq.assert_not_called()
    
    @patch("app.workers.task_worker.queue_service")
    @patch("app.workers.task_worker.task_service")
    @patch("app.workers.task_worker.load_service")
    def test_skip_when_task_paused(self, mock_load, mock_task, mock_queue):
        """Current behavior: skips and DLQs when task is PAUSED."""
        from app.workers import task_worker
        
        mock_load.get_load.return_value = {"load_data": {}}
        mock_task.get_task.return_value = {
            "task_uuid": self.task_uuid,
            "lifecycle_status": TaskStatus.PAUSED.value,
        }
        
        result = task_worker._process_task_message(
            Mock(), self._build_message(), self.load_id
        )
        
        assert result["status"] == "skipped"
        assert result["reason"] == "task_not_awaiting_input"
        mock_queue.move_to_dlq.assert_called_once()
    
    @patch("app.workers.task_worker.task_service")
    @patch("app.workers.task_worker.load_service")
    def test_error_when_load_not_found(self, mock_load, mock_task):
        """Current behavior: raises ValueError when load not found."""
        from app.workers import task_worker
        
        mock_load.get_load.return_value = None
        
        with pytest.raises(ValueError, match="not found"):
            task_worker._process_task_message(
                Mock(), self._build_message(), self.load_id
            )
```

---

## Example 4: Validation Checklist from Real Refactoring

From Phase 5 (TaskMetadataContext) implementation:

```markdown
### Phase 5 Validation Criteria (All met)

- [x] `TaskMetadataContext` Pydantic model created with 18 properties
- [x] `from_dict()` and `empty()` factory methods implemented
- [x] 45 unit tests written (TDD)
- [x] All 45 FAIL initially (TDD red phase confirmed)
- [x] Implementation complete: all 45 PASS
- [x] 46 characterization tests for 3 target files
- [x] All characterization tests PASS before refactoring
- [x] 29 extractions refactored across 3 files
- [x] All characterization tests still PASS after refactoring
- [x] Total: 91 tests passing
```

---

## Example 5: Test File Organization

Recommended structure for a refactoring effort:

```
tests/
├── models/
│   ├── test_load_context.py              # Unit tests for model (TDD)
│   └── test_task_metadata_context.py     # Unit tests for model (TDD)
├── utils/
│   └── test_tool_result_mappers_characterization.py  # Characterization
├── services/
│   └── test_routine_service_characterization.py      # Characterization
├── graphs/
│   └── routines/
│       ├── test_tracking_checkpoint_characterization.py  # Characterization
│       └── test_hourly_eta_tms_note_characterization.py  # Characterization
└── workers/
    └── processors/
        ├── test_task_processor.py        # Characterization + unit
        └── test_inbound_processor.py     # Characterization + unit
```

**Naming conventions**:
- `test_*_characterization.py` - Behavior capture tests
- `test_*.py` in `models/` - TDD unit tests for new code
- `test_*.py` in `processors/` - Mixed characterization + unit

---

## Example 6: Pure Function Tests (No Mocking Required)

For extracted pure transformation functions:

```python
"""Unit tests for buffer aggregation pure functions.

No mocking needed - these are pure transformations.
"""
import json
import pytest
from app.services.buffer_aggregation_service import (
    parse_buffered_messages,
    aggregate_message_timelines,
    ParsedMessage,
)


class TestParseBufferedMessages:
    """Tests for parse_buffered_messages function."""

    def test_parse_single_message(self):
        raw = [json.dumps({"content": "hello", "channel": "sms"}).encode()]
        result = parse_buffered_messages(raw)
        
        assert len(result) == 1
        assert result[0].content == "hello"
        assert result[0].channel == "sms"

    def test_parse_multiple_messages_reverse_order(self):
        # Redis returns newest first, function reverses to chronological
        raw = [
            json.dumps({"content": "second"}).encode(),
            json.dumps({"content": "first"}).encode(),
        ]
        result = parse_buffered_messages(raw, reverse_order=True)
        
        assert result[0].content == "first"
        assert result[1].content == "second"

    def test_parse_skips_malformed_json(self):
        raw = [
            json.dumps({"content": "valid"}).encode(),
            b"not valid json",
            json.dumps({"content": "also valid"}).encode(),
        ]
        result = parse_buffered_messages(raw)
        
        assert len(result) == 2


class TestAggregateMessageTimelines:
    """Tests for aggregate_message_timelines function."""

    def test_aggregate_primary_from_first_message(self):
        messages = [
            ParsedMessage(content="first", channel="sms", sender_uuid="d1",
                         sender_type="driver", attachment_ids=[], inbound_uuid="i1",
                         buffered_at=None, load_id=None, raw_data={}),
            ParsedMessage(content="second", channel="email", sender_uuid="d2",
                         sender_type="dispatcher", attachment_ids=[], inbound_uuid="i2",
                         buffered_at=None, load_id=None, raw_data={}),
        ]
        result = aggregate_message_timelines(messages)
        
        # Primary values from first message
        assert result.primary_channel == "sms"
        assert result.primary_sender_uuid == "d1"
        
        # Timeline includes all
        assert result.channel_timeline == ["sms", "email"]

    def test_aggregate_collects_all_attachments(self):
        messages = [
            ParsedMessage(content="a", channel=None, sender_uuid=None, sender_type=None,
                         attachment_ids=["att-1a", "att-1b"], inbound_uuid=None,
                         buffered_at=None, load_id=None, raw_data={}),
            ParsedMessage(content="b", channel=None, sender_uuid=None, sender_type=None,
                         attachment_ids=["att-2"], inbound_uuid=None,
                         buffered_at=None, load_id=None, raw_data={}),
        ]
        result = aggregate_message_timelines(messages)
        
        assert result.all_attachment_ids == ["att-1a", "att-1b", "att-2"]
```
