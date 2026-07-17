# Python Refactoring Strategies - Examples

Concrete code examples extracted from production refactoring efforts.

## Example 1: Complete Pydantic Context Model

Full implementation of `OrderContextInput` with all property types:

```python
# app/models/order_context.py
"""Centralized order context model.

Single source of truth for extracting fields from order_data dictionaries.
Replaces scattered .get() chains across 15+ files.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# Centralized constant - imported by tests
REQUIRED_CONTEXT_FIELDS = frozenset({
    "order_id",
    "order_data",
    "order_summary",
    "deployment_color",
})


class OrderContextInput(BaseModel):
    """Type-safe accessor for order context fields."""
    
    model_config = ConfigDict(extra="forbid")  # Catch typos in field names
    
    order_id: str
    order_data: Dict[str, Any]
    order_summary: Optional[str] = None
    deployment_color: str = Field(default="blue")

    # ─────────────────────────────────────────────────────────
    # Company Properties (simple nested extraction)
    # ─────────────────────────────────────────────────────────
    
    @property
    def customer_name(self) -> Optional[str]:
        """Extract customer company name."""
        return self.order_data.get("companies", {}).get("customer", {}).get("name")

    @property
    def customer_uuid(self) -> Optional[str]:
        """Extract customer company UUID."""
        return self.order_data.get("companies", {}).get("customer", {}).get("uuid")

    @property
    def supplier_name(self) -> Optional[str]:
        """Extract supplier company name."""
        return self.order_data.get("companies", {}).get("supplier", {}).get("name")

    @property
    def supplier_uuid(self) -> Optional[str]:
        """Extract supplier company UUID."""
        return self.order_data.get("companies", {}).get("supplier", {}).get("uuid")

    @property
    def courier_name(self) -> Optional[str]:
        """Extract courier company name."""
        return self.order_data.get("companies", {}).get("courier", {}).get("name")

    @property
    def courier_license_number(self) -> Optional[str]:
        """Extract courier MC number."""
        return self.order_data.get("companies", {}).get("courier", {}).get("mc_number")

    # ─────────────────────────────────────────────────────────
    # Location Properties (static shortcuts)
    # ─────────────────────────────────────────────────────────
    
    @property
    def pickup_uuid(self) -> Optional[str]:
        """Extract pickup location UUID."""
        return self._get_location_field("pickup", "uuid")

    @property
    def delivery_uuid(self) -> Optional[str]:
        """Extract delivery location UUID."""
        return self._get_location_field("delivery", "uuid")

    @property
    def pickup_timezone(self) -> Optional[str]:
        """Extract pickup location timezone."""
        return self._get_location_field("pickup", "timezone")

    @property
    def delivery_timezone(self) -> Optional[str]:
        """Extract delivery location timezone."""
        return self._get_location_field("delivery", "timezone")

    @property
    def driver_uuid(self) -> Optional[str]:
        """Extract driver UUID from people section."""
        return self.order_data.get("people", {}).get("driver", {}).get("uuid")

    # ─────────────────────────────────────────────────────────
    # Internal Helper (DRY - avoids repetition)
    # ─────────────────────────────────────────────────────────
    
    def _get_location_field(self, location: str, field: str) -> Optional[str]:
        """Internal helper for extracting location fields."""
        return self.order_data.get("locations", {}).get(location, {}).get(field)

    # ─────────────────────────────────────────────────────────
    # Dynamic Accessors (runtime-determined location)
    # ─────────────────────────────────────────────────────────
    
    def get_location_uuid(self, location: str) -> Optional[str]:
        """Get UUID for dynamically specified location."""
        return self._get_location_field(location, "uuid")

    def get_location_timezone(self, location: str) -> Optional[str]:
        """Get timezone for dynamically specified location."""
        return self._get_location_field(location, "timezone")

    # ─────────────────────────────────────────────────────────
    # Factory Methods (Single Source of Truth)
    # ─────────────────────────────────────────────────────────
    
    @classmethod
    def from_dynamodb(cls, order_meta: Dict[str, Any]) -> "OrderContextInput":
        """Extract context from DynamoDB order metadata.
        
        Used by: task_worker processors, resumption handlers.
        """
        return cls(
            order_id=order_meta["order_id"],
            order_data=order_meta.get("order_data", {}),
            order_summary=order_meta.get("order_summary"),
            deployment_color=order_meta.get("deployment_color", "blue"),
        )

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> "OrderContextInput":
        """Extract context from graph state.
        
        Used by: graph nodes, utility functions.
        """
        return cls(
            order_id=state.get("order_id", ""),
            order_data=state.get("order_data", {}),
            order_summary=state.get("order_summary"),
            deployment_color=state.get("deployment_color", "blue"),
        )

    @classmethod
    def empty(cls, order_id: str = "") -> "OrderContextInput":
        """Create empty context for testing or defaults.
        
        Used by: test fixtures, error handling.
        """
        return cls(
            order_id=order_id,
            order_data={},
            order_summary=None,
            deployment_color="blue",
        )
```

---

## Example 2: TaskMetadataContext with Composition

Context model with nested composition and specialized accessors:

```python
# app/models/task_metadata_context.py
"""Task metadata context model.

Centralizes extraction of task metadata fields from raw dictionaries.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class RoutineContext(BaseModel):
    """Nested context for routine-specific data."""
    
    model_config = ConfigDict(extra="forbid")
    
    raw_data: Dict[str, Any]

    @property
    def routine_name(self) -> Optional[str]:
        return self.raw_data.get("name")

    @property
    def trigger_type(self) -> Optional[str]:
        return self.raw_data.get("trigger_type")

    @property
    def schedule_expression(self) -> Optional[str]:
        return self.raw_data.get("schedule_expression")

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RoutineContext":
        return cls(raw_data=data or {})

    @classmethod
    def empty(cls) -> "RoutineContext":
        return cls(raw_data={})


class TaskMetadataContext(BaseModel):
    """Centralized accessor for task metadata."""
    
    model_config = ConfigDict(extra="forbid")
    
    raw_metadata: Dict[str, Any]

    # ─────────────────────────────────────────────────────────
    # Task Identity Properties
    # ─────────────────────────────────────────────────────────
    
    @property
    def task_uuid(self) -> Optional[str]:
        return self.raw_metadata.get("task_uuid")

    @property
    def task_instruction_type(self) -> Optional[str]:
        return self.raw_metadata.get("task_instruction_type")

    @property
    def task_number(self) -> Optional[int]:
        return self.raw_metadata.get("task_number")

    @property
    def timezone(self) -> Optional[str]:
        return self.raw_metadata.get("timezone")

    # ─────────────────────────────────────────────────────────
    # Risk Properties
    # ─────────────────────────────────────────────────────────
    
    @property
    def risk_level(self) -> Optional[str]:
        return self.raw_metadata.get("risk_level")

    @property
    def previous_risk_level(self) -> Optional[str]:
        return self.raw_metadata.get("previous_risk_level")

    @property
    def risk_history(self) -> Optional[List[str]]:
        return self.raw_metadata.get("risk_history")

    # ─────────────────────────────────────────────────────────
    # Nested Data Properties (returns empty dict if missing)
    # ─────────────────────────────────────────────────────────
    
    @property
    def tracking_data(self) -> Dict[str, Any]:
        return self.raw_metadata.get("tracking_data", {})

    @property
    def tracking_timestamp(self) -> Optional[str]:
        """Convenience accessor for nested tracking timestamp."""
        return self.tracking_data.get("timestamp")

    @property
    def tracking_event_type(self) -> Optional[str]:
        """Convenience accessor for nested tracking event type."""
        return self.tracking_data.get("event_type")

    # ─────────────────────────────────────────────────────────
    # Routine Composition
    # ─────────────────────────────────────────────────────────
    
    @property
    def routine(self) -> RoutineContext:
        """Get routine context (composed model)."""
        return RoutineContext.from_dict(self.raw_metadata.get("routine"))

    # ─────────────────────────────────────────────────────────
    # Factory Methods
    # ─────────────────────────────────────────────────────────
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TaskMetadataContext":
        """Create from dictionary, handling None gracefully."""
        return cls(raw_metadata=data or {})

    @classmethod
    def from_state(cls, state: Dict[str, Any], key: str = "task_metadata") -> "TaskMetadataContext":
        """Extract from graph state."""
        return cls.from_dict(state.get(key))

    @classmethod
    def empty(cls) -> "TaskMetadataContext":
        """Create empty context for defaults."""
        return cls(raw_metadata={})
```

---

## Example 3: God Object Decomposition - Processor Package

Structure of extracted `processors/` package:

```python
# app/workers/processors/__init__.py
"""Message processors extracted from task_worker.py.

Each processor handles a single message type with focused responsibility.
"""
from app.workers.processors.task import process_task_message
from app.workers.processors.inbound import process_inbound_message
from app.workers.processors.tracking import process_tracking_update
from app.workers.processors.resumption import process_resumption_event
from app.workers.processors.time_based import process_time_based_event
from app.workers.processors.routine import process_routine_event
from app.workers.processors.order_update import process_order_update

__all__ = [
    "process_task_message",
    "process_inbound_message",
    "process_tracking_update",
    "process_resumption_event",
    "process_time_based_event",
    "process_routine_event",
    "process_order_update",
]
```

```python
# app/workers/processors/task.py
# pyright: reportImportCycles=false
"""Task message processor.

Extracted from task_worker.py to handle TASK message types only.
"""
from typing import Any, Dict

from celery import Task

from app.models.order_context import OrderContextInput
from app.models.state import TaskStatus
from app.services import order_service, task_service, queue_service


def process_task_message(
    task_instance: Task, message_data: Dict[str, Any], order_id: str
) -> Dict[str, Any]:
    """Process task-type message.
    
    Args:
        task_instance: Celery task instance for retry handling
        message_data: Raw message payload
        order_id: ID of order being processed
    
    Returns:
        Result dict with status and optional error details
    """
    # Lazy import to avoid circular dependency
    from app.workers.task_worker import process_task
    
    payload = message_data.get("payload", {})
    task_uuid = payload.get("task_uuid")
    
    # Get current data using centralized context model
    order_meta = order_service.get_order(order_id)
    if not order_meta:
        raise ValueError(f"Order {order_id} not found")
    
    context = OrderContextInput.from_dynamodb(order_meta)
    
    task_data = task_service.get_task(task_uuid)
    if not task_data:
        raise ValueError(f"Task {task_uuid} not found")
    
    # Check lifecycle status
    status = TaskStatus(task_data.get("lifecycle_status", TaskStatus.PENDING.value))
    
    if status not in (TaskStatus.PENDING, TaskStatus.ACTIVE):
        queue_service.move_to_dlq(message_data, reason="task_not_awaiting_input")
        return {"status": "skipped", "reason": "task_not_awaiting_input"}
    
    # Delegate to main processor
    return process_task(task_instance, context, task_data, payload)
```

---

## Example 4: Pure Function Service with Dataclasses

Complete buffer aggregation service:

```python
# app/services/buffer_aggregation_service.py
"""Pure functions for message buffer aggregation.

No I/O operations - all functions are pure transformations.
Easy to unit test without mocking.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedMessage:
    """Structured representation of a buffered message."""
    content: str
    channel: Optional[str]
    sender_uuid: Optional[str]
    sender_type: Optional[str]
    attachment_ids: List[str] = field(default_factory=list)
    inbound_uuid: Optional[str] = None
    buffered_at: Optional[str] = None
    order_id: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedTimeline:
    """Aggregated view of message timeline."""
    primary_channel: Optional[str]
    primary_sender_uuid: Optional[str]
    primary_sender_type: Optional[str]
    channel_timeline: List[str]
    sender_timeline: List[str]
    all_attachment_ids: List[str]
    inbound_uuids: List[str]
    message_count: int


def parse_buffered_messages(
    raw_messages: List[bytes],
    reverse_order: bool = True,
) -> List[ParsedMessage]:
    """Parse raw Redis messages into structured format.
    
    Args:
        raw_messages: List of JSON-encoded byte strings from Redis
        reverse_order: If True, reverse to chronological order (Redis returns newest first)
    
    Returns:
        List of parsed messages, skipping malformed entries
    """
    messages = []
    
    items = reversed(raw_messages) if reverse_order else raw_messages
    
    for raw in items:
        try:
            data = json.orders(raw)
            messages.append(ParsedMessage(
                content=data.get("content", ""),
                channel=data.get("channel"),
                sender_uuid=data.get("sender_uuid"),
                sender_type=data.get("sender_type"),
                attachment_ids=data.get("attachment_ids", []),
                inbound_uuid=data.get("inbound_uuid"),
                buffered_at=data.get("buffered_at"),
                order_id=data.get("order_id"),
                raw_data=data,
            ))
        except (json.JSONDecodeError, TypeError):
            # Skip malformed messages, log in caller
            continue
    
    return messages


def aggregate_message_timelines(messages: List[ParsedMessage]) -> AggregatedTimeline:
    """Aggregate timeline data from multiple messages.
    
    Primary values come from the first message (chronologically oldest).
    Timelines collect all values in order.
    
    Args:
        messages: List of parsed messages in chronological order
    
    Returns:
        Aggregated timeline with primary values and full history
    """
    if not messages:
        return AggregatedTimeline(
            primary_channel=None,
            primary_sender_uuid=None,
            primary_sender_type=None,
            channel_timeline=[],
            sender_timeline=[],
            all_attachment_ids=[],
            inbound_uuids=[],
            message_count=0,
        )
    
    first = messages[0]
    
    # Collect timelines
    channel_timeline = [m.channel for m in messages if m.channel]
    sender_timeline = [m.sender_uuid for m in messages if m.sender_uuid]
    all_attachments = []
    inbound_uuids = []
    
    for msg in messages:
        all_attachments.extend(msg.attachment_ids)
        if msg.inbound_uuid:
            inbound_uuids.append(msg.inbound_uuid)
    
    return AggregatedTimeline(
        primary_channel=first.channel,
        primary_sender_uuid=first.sender_uuid,
        primary_sender_type=first.sender_type,
        channel_timeline=channel_timeline,
        sender_timeline=sender_timeline,
        all_attachment_ids=all_attachments,
        inbound_uuids=inbound_uuids,
        message_count=len(messages),
    )


def format_aggregated_content(messages: List[ParsedMessage]) -> str:
    """Format multiple messages into single aggregated content string.
    
    Args:
        messages: List of parsed messages in chronological order
    
    Returns:
        Formatted string with numbered messages
    """
    if len(messages) == 1:
        return messages[0].content
    
    lines = []
    for i, msg in enumerate(messages, 1):
        lines.append(f"[Message {i}] {msg.content}")
    
    return "\n\n".join(lines)
```

---

## Example 5: Enum for Type Safety

Replace string constants with enum:

```python
# app/models/routine_name.py
"""Routine name enumeration.

Single source of truth for routine names across the codebase.
"""
from enum import Enum


class RoutineName(str, Enum):
    """Valid routine names."""
    
    HOURLY_ETA_CRM_NOTE = "hourly_eta_crm_note"
    HOURLY_TRACKING_CHECKPOINT = "hourly_tracking_checkpoint"
    CONFIRM_APPOINTMENT_REMINDER = "confirm_appointment_reminder"
    PRE_APPOINTMENT_CHECK = "pre_appointment_check"
    POST_APPOINTMENT_CHECK = "post_appointment_check"
    
    @classmethod
    def from_string(cls, value: str) -> "RoutineName":
        """Convert string to enum with validation."""
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Unknown routine: {value}. Valid: {[r.value for r in cls]}")
```

**Usage**:

```python
# BEFORE: String comparison scattered
if routine_name == "hourly_tracking_checkpoint":
    # handle...

# AFTER: Type-safe enum
if routine_name == RoutineName.HOURLY_TRACKING_CHECKPOINT:
    # handle...
```

---

## Example 6: DLQ Message Pydantic Model

Replace dict construction with model:

```python
# app/models/dlq_message.py
"""Dead Letter Queue message model."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class DLQMessage(BaseModel):
    """Structured DLQ message with metadata."""
    
    model_config = ConfigDict(extra="forbid")
    
    original_message: Dict[str, Any]
    reason: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    task_uuid: Optional[str] = None
    error_details: Optional[str] = None
    
    def to_queue_payload(self) -> Dict[str, Any]:
        """Convert to dict for queue."""
        return {
            "original_message": self.original_message,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "order_id": self.order_id,
            "task_uuid": self.task_uuid,
            "error_details": self.error_details,
        }
```

**Usage**:

```python
# BEFORE: Manual dict construction
dlq_payload = {
    "original_message": message,
    "reason": reason,
    "timestamp": datetime.utcnow().isoformat(),
    # ... forgot some fields
}

# AFTER: Type-safe model
dlq_msg = DLQMessage(
    original_message=message,
    reason=reason,
    order_id=order_id,
    task_uuid=task_uuid,
)
queue_service.send_to_dlq(dlq_msg.to_queue_payload())
```
