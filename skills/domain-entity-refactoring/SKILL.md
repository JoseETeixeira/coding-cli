---
name: domain-entity-refactoring
description: Identifies scattered knowledge patterns and refactors them into Domain Entities (Value Objects). Use when string patterns are duplicated across 3+ files, when implicit contracts exist between creators and consumers, when bugs arise from pattern divergence, or when significant research is needed to understand how something works.
---

# Domain Entity Refactoring Pattern

## When to Apply This Pattern

Apply when you observe **any** of these code smells:

| Smell | Example |
|-------|---------|
| **Scattered string patterns** | `f"rme-{prefix}-{id}"` in 5+ files |
| **Implicit contracts** | Creators and consumers must agree on format |
| **Research-heavy debugging** | 2+ hours to understand how something works |
| **Pattern divergence bugs** | One file uses `eta-note-`, another uses `eta_note_` |
| **No compiler enforcement** | Typos in format strings fail silently |

## When NOT to Apply

- Pattern used in only 1-2 places (not worth the abstraction)
- Simple one-off strings (no implicit contracts)
- Performance-critical hot paths (dataclass overhead matters)

## Implementation Checklist

```
Domain Entity Refactoring:
- [ ] Step 1: Identify all occurrences of the pattern
- [ ] Step 2: Create domain entity (frozen dataclass)
- [ ] Step 3: Add enum for types (if applicable)
- [ ] Step 4: Add factory methods for type-safe creation
- [ ] Step 5: Add parsing method (from_name/from_string)
- [ ] Step 6: Add validation in __post_init__
- [ ] Step 7: Add helper methods (belongs_to_X, is_Y)
- [ ] Step 8: Write comprehensive tests (round-trip, validation, edge cases)
- [ ] Step 9: Update all callers
- [ ] Step 10: Document with ADR
```

## Entity Structure Template

```python
"""
{EntityName} - Domain entity for {description}.

This module is the SINGLE SOURCE OF TRUTH for all {pattern} patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

# Define types/prefixes if applicable
PrefixType = Literal["a", "b"]


class EntityType(str, Enum):
    """All entity types in the system."""
    TYPE_A = "type_a"
    TYPE_B = "type_b"


# Regex patterns for parsing
_PATTERNS = {
    EntityType.TYPE_A: re.compile(r"^prefix-a-([ab])-(.+)$"),
    EntityType.TYPE_B: re.compile(r"^prefix-b-([ab])-(.+)$"),
}


@dataclass(frozen=True)
class EntityIdentifier:
    """Value object representing the entity's identity."""

    entity_type: EntityType
    primary_id: str
    prefix: Optional[PrefixType] = None
    secondary_id: Optional[str] = None

    def __post_init__(self):
        """Validate the entity after creation."""
        # Add validation logic here
        if self.entity_type == EntityType.TYPE_A and not self.prefix:
            raise ValueError("prefix is required for TYPE_A")

    @property
    def name(self) -> str:
        """Generate the string representation (SINGLE SOURCE OF TRUTH)."""
        if self.entity_type == EntityType.TYPE_A:
            return f"prefix-a-{self.prefix}-{self.primary_id}"
        elif self.entity_type == EntityType.TYPE_B:
            return f"prefix-b-{self.prefix}-{self.primary_id}"
        raise ValueError(f"Unknown type: {self.entity_type}")

    @classmethod
    def from_name(cls, name: str) -> "EntityIdentifier":
        """Parse an existing string into an EntityIdentifier."""
        for entity_type, pattern in _PATTERNS.items():
            match = pattern.match(name)
            if match:
                return cls(
                    entity_type=entity_type,
                    primary_id=match.group(2),
                    prefix=match.group(1),
                )
        # Fallback for unknown patterns
        return cls(entity_type=EntityType.TYPE_A, primary_id=name)

    # Factory methods for type-safe creation
    @classmethod
    def type_a(cls, primary_id: str, prefix: str) -> "EntityIdentifier":
        """Factory method for TYPE_A entities."""
        return cls(entity_type=EntityType.TYPE_A, primary_id=primary_id, prefix=prefix)

    # Helper methods
    def belongs_to(self, primary_id: str) -> bool:
        """Check ownership."""
        return self.primary_id == primary_id

    def is_type_a(self) -> bool:
        """Type check helper."""
        return self.entity_type == EntityType.TYPE_A
```

## Test Categories

Every domain entity needs these test categories:

1. **Factory Methods** - Each factory creates correct type
2. **Name Generation** - `.name` produces correct patterns
3. **Parsing** - `from_name()` correctly identifies types
4. **Round-trip** - `create -> name -> parse -> same values`
5. **Validation** - Invalid inputs rejected with clear errors
6. **Edge Cases** - Empty strings, special characters, UUIDs

## Real Example: ScheduleIdentifier

See `app/models/schedule_identifier.py` for a production implementation:

```python
# Creating schedules (type-safe)
identifier = ScheduleIdentifier.tracking_checkpoint(load_id, "pickup")
result = create_routine_schedule(identifier=identifier, trigger_time=time)

# Parsing existing names (in cleanup)
identifier = ScheduleIdentifier.from_name(schedule_name)
if identifier.is_routine() and identifier.belongs_to_load(load_id):
    delete_schedule(schedule_name)
```

## Migration Strategy

1. **Phase 1**: Create entity module + tests (no callers changed)
2. **Phase 2**: Update consumers (parsing/cleanup code)
3. **Phase 3**: Update producers (creation code)
4. **Phase 4**: Update remaining callers
5. **Phase 5**: Document with ADR

Each phase can be rolled back independently.

## Additional Resources

- [ADR Example](docs/architecture/adr-schedule-identifier.md)
- [Implementation Plan Example](docs/wip/application-errors/schedule-identifier-architecture-plan.md)
