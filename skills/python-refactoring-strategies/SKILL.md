---
name: python-refactoring-strategies
description: Python refactoring patterns using Pydantic models and modular extraction. Covers context models for centralizing dict access, decomposing large files into packages, extracting pure functions for testability, and factory methods as single source of truth. Use when centralizing scattered .get() chains, breaking up God Objects, or creating data accessor models.
---

# Python Refactoring Strategies

Patterns for refactoring Python codebases using Pydantic models and modular extraction.

## When to Apply

| Problem | Pattern | Threshold |
|---------|---------|-----------|
| Scattered `.get()` chains | Pydantic Context Model | 3+ files with same extraction |
| Large file with many responsibilities | God Object Decomposition | 1000+ lines, 3+ responsibility categories |
| Business logic mixed with I/O | Pure Function Extraction | Complex transformations needing unit tests |
| Repeated dict construction | Factory Methods | Same dict built in 4+ places |

---

## Pattern 1: Pydantic Context Model

**Problem**: Scattered `.get()` chains extracting data from dictionaries.

```python
# BEFORE: Scattered across files
broker = load_data.get("companies", {}).get("broker", {}).get("name")
shipper = load_data.get("companies", {}).get("shipper", {}).get("name")
# Repeated in 10+ files with inconsistent defaults
```

**Solution**: Pydantic model with accessor properties.

```python
# app/models/load_context.py
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class LoadContextInput(BaseModel):
    """Centralized accessor for load context fields.
    
    Single source of truth for extracting fields from load_data.
    """
    
    load_id: str
    load_data: Dict[str, Any]
    load_summary: Optional[str] = None
    deployment_color: str = Field(default="blue")

    # Accessor properties (single source of truth)
    @property
    def broker_name(self) -> Optional[str]:
        return self.load_data.get("companies", {}).get("broker", {}).get("name")

    @property
    def shipper_name(self) -> Optional[str]:
        return self.load_data.get("companies", {}).get("shipper", {}).get("name")

    # Internal helper for DRY
    def _get_location_field(self, location: str, field: str) -> Optional[str]:
        return self.load_data.get("locations", {}).get(location, {}).get(field)

    # Dynamic accessor for runtime-determined values
    def get_location_timezone(self, location: str) -> Optional[str]:
        return self._get_location_field(location, "timezone")

    # Factory methods
    @classmethod
    def from_dynamodb(cls, load_meta: dict) -> "LoadContextInput":
        """Extract from DynamoDB response."""
        return cls(
            load_id=load_meta["load_id"],
            load_data=load_meta.get("load_data", {}),
            load_summary=load_meta.get("load_summary"),
            deployment_color=load_meta.get("deployment_color", "blue"),
        )

    @classmethod
    def from_state(cls, state: dict) -> "LoadContextInput":
        """Extract from graph state."""
        return cls(
            load_id=state.get("load_id", ""),
            load_data=state.get("load_data", {}),
            load_summary=state.get("load_summary"),
            deployment_color=state.get("deployment_color", "blue"),
        )
```

**Usage after refactoring**:

```python
# AFTER: Centralized extraction
ctx = LoadContextInput.from_state(state)
broker = ctx.broker_name
shipper = ctx.shipper_name
timezone = ctx.get_location_timezone("pickup")
```

---

## Pattern 2: God Object Decomposition

**Problem**: Large file with multiple responsibilities.

```
# BEFORE: task_worker.py (2,841 lines)
- 7 message processors
- 3 graph invocation functions
- Factory functions
- Health checks
- Utility functions
```

**Solution**: Extract to focused modules.

```
# AFTER: Organized package structure
app/workers/
├── task_worker.py         # 1,628 lines - thin orchestrator
├── health.py              # Health check tasks
├── graph_input.py         # Factory functions
└── processors/            # Message handlers
    ├── __init__.py
    ├── task.py
    ├── inbound.py
    ├── tracking.py
    ├── resumption.py
    ├── time_based.py
    ├── routine.py
    └── load_update.py
```

**Extraction template**:

```python
# app/workers/processors/task.py
"""Task message processor.

Extracted from task_worker.py for single responsibility.
"""
from typing import Any, Dict
from celery import Task

from app.models.load_context import LoadContextInput
from app.services import load_service, task_service


def process_task_message(
    task_instance: Task, message_data: Dict[str, Any], load_id: str
) -> Dict[str, Any]:
    """Process a task message."""
    # Lazy import to avoid circular dependency
    from app.workers.task_worker import process_task
    
    # Implementation moved from task_worker.py
    context = LoadContextInput.from_dynamodb(load_service.get_load(load_id))
    # ... rest of logic
```

**Update original file to import**:

```python
# app/workers/task_worker.py
from app.workers.processors.task import process_task_message as _process_task_message
```

---

## Pattern 3: Pure Function Extraction

**Problem**: Business logic mixed with I/O operations.

```python
# BEFORE: Mixed I/O and logic (hard to test)
def flush_message_buffer(task_uuid: str, load_id: str):
    messages = redis_client.lrange(buffer_key, 0, -1)  # I/O
    
    # 50 lines of transformation logic mixed in
    parsed = []
    for msg in messages:
        data = json.loads(msg)
        parsed.append(data)
    
    # More logic...
    aggregated = format_messages(parsed)
    
    redis_client.delete(buffer_key)  # I/O
    queue_service.enqueue(aggregated)  # I/O
```

**Solution**: Extract pure transformation functions.

```python
# app/services/buffer_aggregation_service.py
"""Pure functions for message aggregation (no I/O)."""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ParsedMessage:
    content: str
    channel: str
    sender_uuid: str


def parse_buffered_messages(raw_messages: List[bytes]) -> List[ParsedMessage]:
    """Pure function: transform raw bytes to structured data."""
    messages = []
    for msg in reversed(raw_messages):
        try:
            data = json.loads(msg)
            messages.append(ParsedMessage(
                content=data.get("content", ""),
                channel=data.get("channel"),
                sender_uuid=data.get("sender_uuid"),
            ))
        except json.JSONDecodeError:
            continue
    return messages


def aggregate_message_timelines(messages: List[ParsedMessage]) -> Dict[str, Any]:
    """Pure function: aggregate timeline data."""
    return {
        "primary_channel": messages[0].channel if messages else None,
        "channel_timeline": [m.channel for m in messages],
        "message_count": len(messages),
    }
```

**Thin orchestrator with I/O**:

```python
# app/workers/task_worker.py
def flush_message_buffer(task_uuid: str, load_id: str):
    """Thin wrapper: I/O only, delegates to pure functions."""
    from app.services.buffer_aggregation_service import (
        parse_buffered_messages,
        aggregate_message_timelines,
    )
    
    # I/O: fetch
    raw = redis_client.lrange(buffer_key, 0, -1)
    
    # Pure transformation (easily testable)
    parsed = parse_buffered_messages(raw)
    aggregated = aggregate_message_timelines(parsed)
    
    # I/O: write
    redis_client.delete(buffer_key)
    queue_service.enqueue(aggregated)
```

---

## Pattern 4: Factory Methods as Single Source of Truth

**Problem**: Same dict construction repeated in multiple places.

```python
# BEFORE: Repeated 4+ times with slight variations
load_data = {
    "load_id": load_id,
    "load_data": current_load_meta.get("load_data", {}),
    "load_summary": current_load_meta.get("load_summary"),
    "deployment_color": current_load_meta.get("deployment_color", "blue"),
}
```

**Solution**: Factory method on model.

```python
# Model with factory
class LoadContextInput(BaseModel):
    @classmethod
    def from_dynamodb(cls, load_meta: dict) -> "LoadContextInput":
        """Single source of truth for extraction."""
        return cls(
            load_id=load_meta["load_id"],
            load_data=load_meta.get("load_data", {}),
            load_summary=load_meta.get("load_summary"),
            deployment_color=load_meta.get("deployment_color", "blue"),
        )

# AFTER: All callers use factory
context = LoadContextInput.from_dynamodb(current_load_meta)
load_data = context.model_dump()
```

---

## Pattern 5: Incremental File-by-File Migration

**Process**:

1. Create inventory table
2. Migrate one file at a time
3. Run tests after each file
4. Document out-of-scope items

**Inventory template**:

| Priority | File | Extractions | Status |
|----------|------|-------------|--------|
| 1 | `tool_result_mappers.py` | 2 | Done |
| 2 | `routine_service.py` | 3 | Done |
| 3 | `tracking_handler.py` | 6 | In Progress |
| - | `deprecated_module.py` | 4 | Out of Scope |

**Migration checklist per file**:

```markdown
### File: app/utils/tool_result_mappers.py

- [ ] Add import for context model
- [ ] Identify extraction points (2 found)
- [ ] Replace extraction #1
- [ ] Replace extraction #2
- [ ] Run characterization tests
- [ ] All tests pass
```

---

## Handling Circular Imports

When extracted modules need to import from original file:

**Solution**: Lazy imports inside functions.

```python
# app/workers/processors/task.py
# pyright: reportImportCycles=false

def process_task_message(task_instance, message_data, load_id):
    # Lazy import to avoid circular dependency
    from app.workers.task_worker import process_task
    
    # ... use process_task
```

**Add directive** to suppress static analyzer warnings:
```python
# pyright: reportImportCycles=false
```

---

## Implementation Checklist Template

```markdown
### Phase X: {Description}

#### Pre-Implementation
- [ ] 1. Establish test baseline: `pytest tests/related/ -v`
- [ ] 2. Document current line count

#### Implementation
- [ ] 3. Create new module/model
- [ ] 4. Write unit tests (TDD)
- [ ] 5. Run unit tests: X tests pass
- [ ] 6. Write characterization tests
- [ ] 7. Run characterization tests: Y tests pass
- [ ] 8. Migrate file 1
- [ ] 9. Run all tests: still pass
- [ ] 10. Migrate file 2
- [ ] 11. Run all tests: still pass

#### Post-Implementation
- [ ] 12. Verify line count reduction
- [ ] 13. Update documentation
- [ ] 14. Total: X + Y = Z tests passing
```

---

## Additional Resources

For concrete code examples, see [examples.md](examples.md).
