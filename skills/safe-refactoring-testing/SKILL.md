---
name: safe-refactoring-testing
description: Testing strategies for safe Python refactoring. Covers characterization tests to capture existing behavior, TDD for new abstractions, and regression safety. Use when refactoring existing code, extracting functions to new modules, creating new models or services, or when asking about characterization tests or test-driven refactoring.
---

# Safe Refactoring Testing

Testing strategies to ensure behavior preservation when refactoring Python code.

## When to Apply

- Extracting functions to new modules
- Creating new abstractions (Pydantic models, services)
- Replacing scattered patterns with centralized code
- Decomposing large files into packages
- Any change where "it should work exactly the same" is the goal

## Safe Refactoring Workflow

```
Phase A: Characterization Tests
  1. Write tests that call EXISTING functions
  2. Tests PASS (current behavior captured)
  3. Keep as regression safety net

Phase B: TDD for New Code
  1. Write tests for NEW abstractions
  2. Tests FAIL (code doesn't exist)
  3. Implement minimal code
  4. Tests PASS

Phase C: Refactor
  1. Replace old code with new abstractions
  2. Run characterization tests
  3. Must still PASS (behavior preserved)
  4. If FAIL: refactoring broke behavior
```

## Test Categories

| Category | Purpose | When Written | Expected Result |
|----------|---------|--------------|-----------------|
| Characterization | Capture existing behavior | Before any changes | PASS immediately |
| Unit (TDD) | Define new abstraction contract | Before implementation | FAIL then PASS |
| Regression | Verify no breakage | After refactoring | Must still PASS |

## Characterization Test Pattern

Write tests that document current behavior before touching production code.

**Naming convention**: `test_*_characterization.py`

**Template**:

```python
"""Characterization tests for {module_name}.

These tests capture CURRENT behavior before refactoring.
They should PASS now and continue to PASS after refactoring.
"""
import pytest
from unittest.mock import patch, MagicMock


class Test{FunctionName}Characterization:
    """Capture current behavior of {function_name}()."""

    def test_returns_expected_output_for_typical_input(self):
        """Current behavior: {describe what happens}."""
        # Arrange
        input_data = {"key": "value"}
        
        # Act
        result = function_under_test(input_data)
        
        # Assert - document current behavior
        assert result["status"] == "expected_value"

    def test_handles_missing_data_gracefully(self):
        """Current behavior: returns None when data missing."""
        result = function_under_test({})
        assert result is None

    def test_handles_edge_case(self):
        """Current behavior: {edge case description}."""
        # Document the edge case behavior
        pass
```

**Key principles**:
- Test WHAT the function does, not HOW it does it
- Include edge cases and error conditions
- Mock external dependencies (services, I/O)
- Run tests BEFORE making any changes to verify they pass

## TDD for New Abstractions

When creating new models, services, or helpers, write tests first.

**Workflow**:

```
RED   → Write test for desired behavior → Test FAILS
GREEN → Write minimal implementation    → Test PASSES
REFACTOR → Clean up code               → Test still PASSES
```

**Template for Pydantic model tests**:

```python
"""Unit tests for {ModelName} (TDD).

These tests are written BEFORE implementation.
Expected flow: FAIL → implement → PASS
"""
import pytest


class Test{ModelName}Properties:
    """Tests for accessor properties."""

    def test_property_returns_value_when_present(self):
        ctx = ModelName(raw_data={"field": "value"})
        assert ctx.field == "value"

    def test_property_returns_none_when_missing(self):
        ctx = ModelName(raw_data={})
        assert ctx.field is None


class Test{ModelName}FactoryMethods:
    """Tests for factory methods."""

    def test_from_dict_with_data(self):
        data = {"field": "value"}
        ctx = ModelName.from_dict(data)
        assert ctx.field == "value"

    def test_from_dict_with_none(self):
        ctx = ModelName.from_dict(None)
        assert ctx.raw_data == {}

    def test_from_state_extracts_nested_data(self):
        state = {"outer_key": {"field": "value"}}
        ctx = ModelName.from_state(state)
        assert ctx.field == "value"
```

## Validation Checklist Pattern

Use explicit test counts as completion criteria.

**Template**:

```markdown
### Phase X Validation Criteria

- [ ] Characterization tests written: X tests
- [ ] All characterization tests PASS before changes
- [ ] Unit tests for new code: Y tests
- [ ] Unit tests FAIL initially (TDD red phase confirmed)
- [ ] Implementation complete: unit tests PASS
- [ ] Refactoring complete: characterization tests still PASS
- [ ] Total tests: X + Y = Z tests passing
```

**Example from real refactoring**:

```markdown
Phase 4 Validation:
- [x] 19 characterization tests created
- [x] All 19 PASS before refactoring
- [x] 24 unit tests for new properties
- [x] All 24 FAIL initially (TDD confirmed)
- [x] Implementation complete: 24 PASS
- [x] Refactoring complete: 19 characterization still PASS
- [x] Total: 43 tests passing
```

## Test Execution Order

For each extraction or refactoring:

```bash
# 1. Write characterization tests
# 2. Verify they pass BEFORE changes
pytest tests/path/test_*_characterization.py -v

# 3. Write unit tests for new code (should FAIL)
pytest tests/path/test_new_module.py -v

# 4. Implement new code (tests should PASS)
pytest tests/path/test_new_module.py -v

# 5. Refactor old code to use new abstraction
# 6. Verify characterization tests still pass
pytest tests/path/test_*_characterization.py -v

# 7. Run full related test suite
pytest tests/related_module/ -v
```

## Common Mistakes to Avoid

| Mistake | Why It's Bad | Better Approach |
|---------|--------------|-----------------|
| Skipping characterization tests | No safety net for refactoring | Always write them first |
| Testing implementation details | Tests break when internals change | Test observable behavior |
| Writing tests after refactoring | Can't catch regressions | Write before changes |
| Not mocking external services | Slow, flaky tests | Mock at service boundary |
| Vague test counts | No clear completion criteria | Use explicit numbers |

## When to Mock vs. Test Real Code

| Scenario | Approach |
|----------|----------|
| External services (API, DB) | Mock |
| Pure transformation functions | Test directly |
| Functions with I/O | Mock I/O, test logic |
| Complex business logic | Test directly with fixtures |

## Additional Resources

For concrete examples from production refactoring, see [examples.md](examples.md).
