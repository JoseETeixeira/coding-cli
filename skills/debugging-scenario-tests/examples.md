# Debugging Examples

## Example 1: Wrong SOP Fetched (Root Cause from UFS Escalation)

### Symptom
Test `ufs_unresponsive_task_escalation` fails. Judge says "agent did not call `create_task`".

### Wrong Approach (Bottom-Up)
1. Check if `task_metadata_service` is mocked ✓
2. Check if mock returns correct values ✓
3. Check patch target path ✓
4. Conclude: "mock must be failing silently" ✗ **WRONG**

### Correct Approach (Top-Down)
1. Read JSON response, find `dynamic_sops_fetch` call:
   ```json
   {"name": "dynamic_sops_fetch", "arguments": "{\"sop_context\": \"pending_status_follow_up_sop\"}"}
   ```
   **Finding:** Agent fetched wrong SOP!

2. Check scenario definition:
   ```python
   state_builder=with_time_based_event(motivation="pending_status_follow_up")
   ```
   **Finding:** Motivation is wrong - should be `"unresponsive_contact"`

3. Also find `get_load_state` returned `"at-delivery"`:
   ```json
   {"content": "status='SUCCESS' result='at-delivery'"}
   ```
   **Finding:** Agent exited early because load appeared delivered

### Fix
```python
StageConfig(
    state_builder=with_time_based_event(
        motivation="unresponsive_contact",  # Fixed
    ),
    mock_overrides={
        "task_metadata": {...},
        "load_state": "at-pickup",  # Added
    },
)
```

**Time to fix after correct diagnosis: 5 minutes**

---

## Example 2: Timestamp Mismatch

### Symptom
Escalation conditions require `hours_since_first_unresponsive_contact >= 2`, but tool returns `0.0`.

### Wrong Approach
1. Check if timestamp is in mock_overrides ✓
2. Check if mock is applied ✓
3. Assume: "calculation must be wrong" ✗ **WRONG**

### Correct Approach
1. Check scenario base date:
   ```python
   base_time = datetime(2025, 11, 13, 16, 0, 0)
   ```

2. Check mock timestamp:
   ```python
   "unresponsive_contact_first_attempt_utc": "2025-11-15T18:00:00.000Z"
   ```
   **Finding:** 2025-11-15 is AFTER 2025-11-13! First attempt is "in the future"!

3. Result: `hours_since = now - future_time = negative → clamped to 0`

### Fix
```python
# Align timestamp with scenario base date (before escalation time)
"unresponsive_contact_first_attempt_utc": "2025-11-13T14:00:00.000Z"
```

---

## Example 3: Agent Sends Forbidden Email

### Symptom
Judge says "agent called `reply_best_email_thread` which is forbidden for UFS unresponsive scenarios".

### Analysis
1. Read JSON response - confirm agent called `reply_best_email_thread`
2. Check which SOP was fetched - was it the UFS SOP?
3. If wrong SOP: fix timer motivation
4. If correct SOP but wrong behavior: LLM didn't follow instructions

### Diagnosis
- If wrong SOP fetched → scenario configuration issue (fix motivation)
- If correct SOP fetched → LLM adherence issue (strengthen SOP wording)

---

## Example 4: Mock Override Not Applied

### Symptom
Mock values appear to be defaults despite `mock_overrides` being set.

### Checklist
1. Is the key in `mock_overrides` supported by `scenario_runner.py`?
   ```python
   # scenario_runner.py must handle the key
   if "task_metadata" in stage.mock_overrides:
       mock_context.set_task_metadata(stage.mock_overrides["task_metadata"])
   ```

2. Is `MockContext` patching the correct target?
   ```python
   # Must patch where it's CALLED, not where it's DEFINED
   # If deep_agent_tools.py does: from app.services import task_metadata_service
   # Patch: "app.services.task_metadata_service.get_task_metadata"
   # NOT: "app.utils.deep_agent_tools.task_metadata_service.get_task_metadata"
   ```

---

## Debugging Time Comparison

| Approach | Time Spent | Success Rate |
|----------|-----------|--------------|
| Bottom-up (mocks first) | 45-60 min | Low - often chase wrong hypothesis |
| Top-down (execution first) | 10-15 min | High - find actual cause quickly |

**Key insight:** Reading the JSON response file should be your FIRST action, not your last resort.
