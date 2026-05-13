# Domain Entity Examples

## Example 1: ScheduleIdentifier (This Codebase)

### Problem
EventBridge schedule names were created with patterns like:
- `f"rme-{p|d}-{load_id}"` (morning ETA)
- `f"eta-note-{p|d}-{load_id}"` (hourly ETA)
- `f"tracking-checkpoint-{p|d}-{load_id}"` (tracking)
- `{task_uuid}` (task timers)

These patterns were scattered across 15+ files with no central authority.

### Solution
Created `ScheduleIdentifier` as single source of truth:

```python
# Before (scattered)
event_id = f"tracking-checkpoint-{loc_prefix}-{load_id}"

# After (centralized)
identifier = ScheduleIdentifier.tracking_checkpoint(load_id, location_context)
event_id = identifier.name
```

### Benefits
- Type-safe creation via factory methods
- Bidirectional (create names, parse names)
- Validation at creation time
- 44 unit tests covering all patterns

---

## Example 2: API Endpoint Paths (Hypothetical)

### Problem
API paths constructed in multiple places:
```python
# In service A
url = f"/api/v2/loads/{load_id}/status"

# In service B  
url = f"/api/v2/loads/{load_id}/status"  # Duplicated

# In test
url = f"/api/v2/load/{load_id}/status"  # Typo: "load" vs "loads"
```

### Solution
```python
class ApiEndpoint:
    @classmethod
    def load_status(cls, load_id: str) -> str:
        return f"/api/v2/loads/{load_id}/status"
```

---

## Example 3: Cache Keys (Hypothetical)

### Problem
Redis cache keys with inconsistent patterns:
```python
# File 1
key = f"user:{user_id}:profile"

# File 2
key = f"user-{user_id}-profile"  # Different separator!

# File 3
key = f"user:{user_id}:profile:v2"  # Added version
```

### Solution
```python
@dataclass(frozen=True)
class CacheKey:
    namespace: str
    entity_id: str
    suffix: str
    version: int = 1

    @property
    def key(self) -> str:
        return f"{self.namespace}:{self.entity_id}:{self.suffix}:v{self.version}"

    @classmethod
    def user_profile(cls, user_id: str) -> "CacheKey":
        return cls(namespace="user", entity_id=user_id, suffix="profile")
```

---

## Identifying Candidates

Search for these patterns in your codebase:

```bash
# Find f-string patterns that might be duplicated
rg 'f"[a-z]+-\{' --type py

# Find string formatting with common prefixes
rg '\.format\(' --type py | grep -E '(prefix|key|name|path|url)'

# Find potential naming patterns
rg 'f"[a-z]+-[a-z]+-\{' --type py
```

---

## Decision Matrix

| Criterion | Create Entity | Keep Strings |
|-----------|---------------|--------------|
| Occurrences | 3+ files | 1-2 files |
| Contract complexity | Multiple fields | Single value |
| Bug history | Pattern-related bugs | None |
| Maintenance burden | High (many files) | Low |
| Type safety need | High (critical paths) | Low |
