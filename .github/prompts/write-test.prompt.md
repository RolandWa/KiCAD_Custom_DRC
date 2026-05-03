---
description: "Write pytest test for a checker method. Creates test file with proper mocks, fixtures, and assertions. Use after implementing a checker method."
name: "Write Test"
argument-hint: "Module and method name to test (e.g., 'via_stitching.check', 'decoupling._check_capacitor_proximity')"
agent: "agent"
---

Write a complete pytest test for a checker method using the project's mock framework.

## Inputs

Extract from argument or ask:
- **Module**: Checker module (e.g., `via_stitching`, `signal_integrity`)
- **Method**: Method name to test (e.g., `check`, `_check_controlled_impedance`)
- **Test scenario**: Specific condition to test (e.g., "via too far from signal via", "impedance out of tolerance")

## Prerequisites — Check First

**Required mocks in tests/helpers.py**:
- `MockNet(name, net_class)` ✅
- `MockNetInfo(nets)` ✅
- `MockBoard(board_file, nets, layer_names)` ✅
- `MockTrack(start_xy, end_xy, net_name, net_class, layer_id, width_mm)` ❌ NOT YET IMPLEMENTED
- `MockVia(pos_xy, net_name, drill_mm, start_layer, end_layer)` ❌ NOT YET IMPLEMENTED
- `MockZone(polygon_pts, net_name, layer_id)` ❌ NOT YET IMPLEMENTED

**If required mocks are missing**: Ask user whether to:
1. Implement missing mocks first (e.g., MockTrack for trace-related tests)
2. Write test stub with `@pytest.mark.skip(reason="...")` detailing mock requirements

## Steps

1. **Read the implementation** in `src/<module>.py`:
   - Understand what the method checks
   - Identify thresholds and config keys used
   - Note what pcbnew objects it operates on (tracks, vias, zones, pads, etc.)

2. **Check existing test structure**:
   - Look at `tests/<module>/test_checks.py` or create if missing
   - Review similar tests in other modules for patterns
   - Check `tests/helpers.py` for available factory functions

3. **Create test structure** following this template:
   ```python
   import pytest
   from tests.helpers import MockBoard, MockNet, MockNetInfo, make_<module>_checker
   
   class Test<MethodName>:
       """Tests for <module>.<method>()."""
       
       def test_<scenario>_<expected_outcome>(self):
           """Test that <scenario> results in <expected_outcome>."""
           # Arrange
           nets = [MockNet("GND", "Default"), MockNet("SIGNAL", "HighSpeed")]
           board = MockBoard("test.kicad_pcb", nets, {"F.Cu": 0, "B.Cu": 31})
           config = {
               'threshold_mm': 2.0,
               'enabled': True
           }
           checker = make_<module>_checker(board, config)
           
           # Act
           violations = checker.<method>(...)
           
           # Assert
           assert violations == <expected_count>
           # TODO: verify marker drawn at correct position
   ```

4. **Mock the scenario**:
   - Create minimal mocks that trigger the specific code path
   - Use realistic values (e.g., via drill = 0.3mm, trace width = 0.2mm)
   - Position objects to clearly violate or satisfy the rule

5. **Add multiple test cases**:
   - **Pass case**: No violations (rule satisfied)
   - **Fail case**: One clear violation
   - **Edge case**: Exactly at threshold
   - **Disabled check**: `enabled = False` in config → 0 violations

6. **Add assertions**:
   - Violation count matches expected
   - `checker.report_lines` contains expected message text
   - If markers are drawn, verify positions (requires mocking `draw_marker_func`)

7. **Run the test**:
   ```powershell
   pytest tests/<module>/test_checks.py::<TestClass>::<test_method> -v
   ```

8. **Update module phase tracker** (if applicable):
   - Change `[test □]` to `[test ✓]` in module docstring

## Output

- New or updated `tests/<module>/test_checks.py`
- Test passes (`pytest` exit code 0)
- No test marked as `skip` unless blocked by missing mocks

## If Mocks Are Missing

Create stub with detailed requirements:
```python
@pytest.mark.skip(reason="TODO: implement MockTrack(start, end, net, layer, width) in helpers.py — mock 2 traces parallel at 0.5mm spacing — assert coupling violation")
def test_parallel_trace_coupling_detected(self):
    pass
```

Do NOT:
- Implement production code (only test code)
- Skip writing assertions (every test needs at least one assertion)
- Test multiple unrelated scenarios in one test function (split into separate tests)
