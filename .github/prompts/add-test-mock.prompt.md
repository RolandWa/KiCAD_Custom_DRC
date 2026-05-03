---
description: "Add test mocks to tests/helpers.py for pcbnew objects. Use when tests are blocked by missing MockTrack, MockVia, MockZone, etc."
name: "Add Test Mock"
argument-hint: "Mock class name (e.g., 'MockTrack', 'MockVia', 'MockZone')"
agent: "agent"
---

Implement a pcbnew mock class in `tests/helpers.py` following the project's mock pattern.

## Inputs

Extract from argument or ask:
- **Mock class**: Name of mock to implement (e.g., `MockTrack`, `MockVia`, `MockZone`, `MockFootprint`, `MockPad`)

## Prerequisites

1. **Read existing mocks** in [tests/helpers.py](../tests/helpers.py):
   - `MockNet` — minimal NETINFO_ITEM with name and net class
   - `MockNetInfo` — container with GetNetCount(), GetNetItem(), NetsByName()
   - `MockBoard` — BOARD stub with file path, nets, layer names

2. **Read conftest.py** to see what pcbnew stubs already exist:
   - `pcbnew.VECTOR2I` — minimal 2D point with x, y attributes
   - `pcbnew.PCB_TRACK`, `pcbnew.PCB_VIA`, `pcbnew.ZONE` — empty class stubs
   - `pcbnew.FromMM()`, `pcbnew.ToMM()` — unit conversion functions

3. **Identify required methods** by searching the checker module:
   ```powershell
   # Find all methods called on Track objects
   Select-String -Path src/*.py -Pattern "\.Get\w+\(" | Where-Object { $_ -match "track\." }
   ```

## Common Mock Requirements

### MockTrack
Must support:
- `.GetStart()` → VECTOR2I (start point in internal units)
- `.GetEnd()` → VECTOR2I (end point in internal units)
- `.GetNetname()` → str (net name like "GND", "SIGNAL_P")
- `.GetNetClassName()` → str (net class like "Default", "HighSpeed")
- `.GetLayer()` → int (layer ID, e.g., 0 for F.Cu)
- `.GetWidth()` → int (trace width in internal units)
- `.IsOnLayer(layer_id)` → bool (check if trace on specified layer)

Constructor signature:
```python
class MockTrack:
    def __init__(self, start_xy: tuple, end_xy: tuple, net_name: str, 
                 net_class: str, layer_id: int, width_mm: float):
        """
        Args:
            start_xy: (x_mm, y_mm) starting point
            end_xy: (x_mm, y_mm) ending point
            net_name: Net name (e.g., "GND")
            net_class: Net class name (e.g., "Default")
            layer_id: KiCad layer ID (0=F.Cu, 31=B.Cu)
            width_mm: Trace width in millimeters
        """
```

### MockVia
Must support:
- `.GetX()` → int (X coordinate in internal units)
- `.GetY()` → int (Y coordinate in internal units)
- `.GetPosition()` → VECTOR2I
- `.GetNetname()` → str
- `.GetDrillValue()` → int (drill diameter in internal units)
- `.IsOnLayer(layer_id)` → bool
- `.TopLayer()` → int (top layer ID)
- `.BottomLayer()` → int (bottom layer ID)

Constructor signature:
```python
class MockVia:
    def __init__(self, pos_xy: tuple, net_name: str, drill_mm: float,
                 start_layer: int, end_layer: int):
        """
        Args:
            pos_xy: (x_mm, y_mm) via center
            net_name: Net name
            drill_mm: Drill diameter in millimeters
            start_layer: Top layer ID (e.g., 0 for F.Cu)
            end_layer: Bottom layer ID (e.g., 31 for B.Cu)
        """
```

### MockZone
Must support:
- `.GetNetname()` → str
- `.GetLayer()` → int
- `.IsOnLayer(layer_id)` → bool
- `.Outline()` → outline container (iterable of point lists)
- `.GetNumCorners()` → int
- `.GetCornerPosition(idx)` → VECTOR2I

Constructor signature:
```python
class MockZone:
    def __init__(self, polygon_pts: list[tuple], net_name: str, layer_id: int):
        """
        Args:
            polygon_pts: List of (x_mm, y_mm) tuples defining zone boundary
            net_name: Net name (e.g., "GND")
            layer_id: Layer ID
        """
```

## Implementation Pattern

1. **Store constructor arguments** in internal units (convert from mm):
   ```python
   import pcbnew  # Mock from conftest.py
   
   self._start = pcbnew.VECTOR2I(
       pcbnew.FromMM(start_xy[0]),
       pcbnew.FromMM(start_xy[1])
   )
   ```

2. **Implement getter methods** returning stored values:
   ```python
   def GetStart(self):
       return self._start
   ```

3. **Handle layer queries**:
   ```python
   def IsOnLayer(self, layer_id):
       return self._layer == layer_id
   ```

4. **Add to `__all__`** export list at top of helpers.py

5. **Add factory function** (optional, for common scenarios):
   ```python
   def make_gnd_via(x_mm, y_mm):
       """Quick factory for GND stitching via."""
       return MockVia((x_mm, y_mm), "GND", drill_mm=0.3, start_layer=0, end_layer=31)
   ```

## Validation

1. **Import test**:
   ```python
   python -c "from tests.helpers import MockTrack; print('OK')"
   ```

2. **Method test**:
   ```python
   python -c "from tests.helpers import MockTrack; t = MockTrack((0,0), (10,10), 'GND', 'Default', 0, 0.2); print(t.GetStart(), t.GetNetname())"
   ```

3. **Run affected tests**:
   ```powershell
   pytest tests/<module>/ -v  # Run tests that depend on this mock
   ```

## Output

- Updated `tests/helpers.py` with new mock class
- Validation tests pass
- Affected test files can now be un-skipped

Do NOT:
- Implement methods not needed by any test (keep mocks minimal)
- Add real pcbnew API complexity (mocks should be simple stubs)
- Implement board geometry calculations in mocks (keep them as data holders)
