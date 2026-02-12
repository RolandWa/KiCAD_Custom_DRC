# Code Reusability Analysis - EMC Auditor Plugin
**Date**: 2026-02-12  
**Analyzed Files**: emc_auditor_plugin.py (798 lines) + 5 modules (2,735 lines total)

---

## Executive Summary

This analysis identifies **reusable code patterns** across the modular EMC Auditor Plugin architecture. The goal is to maximize code reuse by centralizing common patterns in the main plugin while keeping domain-specific logic in specialized modules.

**Key Findings**:
- ✅ **4 utility functions already centralized** (draw_marker, draw_arrow, get_distance, get_nets_by_class)
- ⚠️ **7 high-value opportunities** for further centralization (eliminate duplication)
- ✓ **Domain-specific code properly isolated** in modules (correct architecture)

---

## 1. Already Centralized Utilities (✅ GOOD ARCHITECTURE)

These functions are correctly centralized in `emc_auditor_plugin.py` and injected into modules via dependency injection:

### 1.1 Drawing Functions
```python
draw_error_marker(board, pos, message, layer, group)  # Line 623-643
draw_arrow(board, start, end, label, layer, group)    # Line 645-717
```
**Used by**: All 5 modules (via_stitching, decoupling, emi_filtering, ground_plane, clearance_creepage)  
**Benefit**: Single source of truth for marker styling, configurable from emc_rules.toml [general] section

### 1.2 Distance Calculation
```python
get_distance(p1, p2)  # Line 577-578
```
**Used by**: All 5 modules  
**Benefit**: Consistent distance calculation across all checks

### 1.3 Net Class Lookup
```python
get_nets_by_class(board, class_name)  # Line 580-621
```
**Used by**: via_stitching.py (line 102), clearance_creepage.py (line 221)  
**Benefit**: Handles KiCad Net Class string formats (single, comma-separated, wildcards)

### 1.4 Configuration Management
```python
load_config()           # Line 313-338
get_default_config()    # Line 340-365
```
**Used by**: Main plugin initialization  
**Benefit**: Centralized TOML parsing with fallback to defaults

---

## 2. Code Duplication - Opportunities for Centralization

### 2.1 ⭐ **PRIORITY 1: `log()` Method - IDENTICAL ACROSS ALL MODULES**

**Duplicated Code** (57 lines total across 5 files):
```python
# IDENTICAL in via_stitching.py, decoupling.py, emi_filtering.py, ground_plane.py, clearance_creepage.py
def log(self, msg, force=False):
    """Log message to console and report (only if verbose or force=True)"""
    if self.verbose or force:
        print(msg)
        if self.verbose:
            self.report_lines.append(msg)
```

**Locations**:
- via_stitching.py: Lines 56-61
- decoupling.py: Lines 56-61
- emi_filtering.py: Lines 56-61
- ground_plane.py: Lines 97-102
- clearance_creepage.py: Lines 56-61

**Impact**: High - This is 100% identical code repeated 5 times

**Recommended Solution**:
```python
# emc_auditor_plugin.py - Add new utility function
def create_logger(verbose, report_lines):
    """
    Create a logging function for modules to use.
    
    Args:
        verbose: bool - Enable detailed logging
        report_lines: list - Shared report lines array
    
    Returns:
        function: log(msg, force=False) that prints and appends to report
    """
    def log(msg, force=False):
        if verbose or force:
            print(msg)
            if verbose:
                report_lines.append(msg)
    return log

# In each module's check() method, receive as parameter:
def check(self, draw_marker_func, draw_arrow_func, get_distance_func, log_func):
    self.log = log_func  # Store for reuse
    # ... rest of check logic
```

**Estimated Lines Saved**: ~45 lines (remove from 5 modules, add 15 lines to main plugin)

---

### 2.2 ⭐ **PRIORITY 2: Violation Group Creation Pattern**

**Repeated Pattern** (appears 40+ times across all modules):
```python
# Pattern repeated in every violation creation:
violation_group = pcbnew.PCB_GROUP(self.board)
violation_group.SetName(f"EMC_{check_type}_{identifier}_{count}")
self.board.Add(violation_group)
```

**Locations**:
- via_stitching.py: Lines 172-174
- decoupling.py: Lines 150-152
- emi_filtering.py: Lines 111-123 (multiple instances)
- ground_plane.py: Lines 331-333, 359-361
- clearance_creepage.py: Lines 566-568

**Impact**: Medium-High - Eliminates boilerplate, ensures consistent group naming

**Recommended Solution**:
```python
# emc_auditor_plugin.py - Add new utility function
def create_violation_group(self, board, check_type, identifier, violation_number=None):
    """
    Create a standardized violation group for visual organization in KiCad.
    
    Args:
        board: pcbnew.BOARD object
        check_type: str - Type of check (Via, Decap, GndPlane, EMI, Clearance)
        identifier: str - Unique identifier (net name, component ref, etc.)
        violation_number: int - Optional violation sequence number
    
    Returns:
        pcbnew.PCB_GROUP: Created and added group object
    
    Example:
        group = self.create_violation_group(board, "Via", "CLK", 3)
        # Creates group named "EMC_Via_CLK_3"
    """
    group = pcbnew.PCB_GROUP(board)
    
    if violation_number is not None:
        name = f"EMC_{check_type}_{identifier}_{violation_number}"
    else:
        name = f"EMC_{check_type}_{identifier}"
    
    group.SetName(name)
    board.Add(group)
    return group

# Usage in modules:
group = self.create_violation_group(board, "Via", net_name, self.violation_count)
self.draw_marker(board, pos, msg, layer, group)
```

**Estimated Lines Saved**: ~80 lines (3 lines per violation × ~30 violations - 10 lines added)

---

### 2.3 ⭐ **PRIORITY 3: Net Pattern Matching Utilities**

**Repeated Pattern** (similar logic in multiple modules):
```python
# Ground net checking - via_stitching.py line 107, ground_plane.py line 137
if any(pat in net_name.upper() for pat in gnd_patterns):
    # ... handle ground net

# Power net checking - decoupling.py line 94, emi_filtering.py line 162
if any(pat in net_name.upper() for pat in power_patterns):
    # ... handle power net
```

**Impact**: Medium - Improves readability, consistent pattern matching

**Recommended Solution**:
```python
# emc_auditor_plugin.py - Add new utility functions
def is_ground_net(self, net_name, ground_patterns):
    """
    Check if a net name matches ground patterns.
    
    Args:
        net_name: str - Net name to check
        ground_patterns: list[str] - Ground net patterns (e.g., ['GND', 'VSS'])
    
    Returns:
        bool: True if net matches any ground pattern
    
    Example:
        >>> is_ground_net("Net-GND", ['GND', 'GROUND'])
        True
    """
    if not net_name:
        return False
    net_upper = net_name.upper()
    return any(pattern.upper() in net_upper for pattern in ground_patterns)

def is_power_net(self, net_name, power_patterns):
    """
    Check if a net name matches power patterns.
    
    Args:
        net_name: str - Net name to check
        power_patterns: list[str] - Power net patterns (e.g., ['VCC', '3V3'])
    
    Returns:
        bool: True if net matches any power pattern
    
    Example:
        >>> is_power_net("Net-VCC_3V3", ['VCC', 'VDD'])
        True
    """
    if not net_name:
        return False
    net_upper = net_name.upper()
    return any(pattern.upper() in net_upper for pattern in power_patterns)

# Usage in modules:
if self.is_ground_net(via.GetNetname(), gnd_patterns):
    gnd_vias.append(via)
```

**Estimated Lines Saved**: ~30 lines (simplifies pattern matching in 6+ locations)

---

### 2.4 ⭐ **PRIORITY 4: Via Filtering by Net Pattern**

**Repeated Logic** (similar iteration in via_stitching.py and ground_plane.py):
```python
# via_stitching.py lines 105-110
gnd_vias = []
for v in vias:
    v_net = str(v.GetNetname()).upper()
    if any(pat in v_net for pat in gnd_patterns):
        gnd_vias.append(v)

# ground_plane.py lines 404-412 - similar iteration for via clearance check
```

**Impact**: Medium - Eliminates duplicate via iteration logic

**Recommended Solution**:
```python
# emc_auditor_plugin.py - Add new utility function
def get_vias_by_net_pattern(self, board, net_patterns):
    """
    Get all vias that match specified net name patterns.
    
    Args:
        board: pcbnew.BOARD object
        net_patterns: list[str] - Net name patterns to match (case-insensitive)
    
    Returns:
        list[pcbnew.PCB_VIA]: Vias matching the patterns
    
    Example:
        >>> gnd_vias = self.get_vias_by_net_pattern(board, ['GND', 'VSS'])
        >>> print(f"Found {len(gnd_vias)} ground vias")
    """
    vias = []
    tracks = board.GetTracks()
    
    for track in tracks:
        if isinstance(track, pcbnew.PCB_VIA):
            net_name = str(track.GetNetname()).upper()
            if any(pattern.upper() in net_name for pattern in net_patterns):
                vias.append(track)
    
    return vias

# Usage in modules:
gnd_vias = self.get_vias_by_net_pattern(self.board, gnd_patterns)
```

**Estimated Lines Saved**: ~15 lines (remove from 2 modules, add function to main)

---

### 2.5 **PRIORITY 5: Ground Zone Filtering** (ground_plane.py specific)

**Complex Logic** (lines 137-165 in ground_plane.py):
```python
# 29 lines of zone iteration, filtering, area calculation, layer indexing
for zone in self.board.Zones():
    zone_net = zone.GetNetname().upper()
    # ... pattern matching
    # ... fill check
    # ... area calculation
    # ... layer indexing
```

**Impact**: Low-Medium - Only used in ground_plane.py currently, but could benefit future checks

**Recommended Solution**:
```python
# emc_auditor_plugin.py - Add new utility function
def get_ground_zones(self, board, ground_patterns, min_area_mm2=10.0, index_by_layer=True):
    """
    Get all filled ground zones above minimum area threshold.
    
    This function performs intelligent filtering:
    - Checks if zones are filled (unfilled zones can't be hit-tested)
    - Filters by net name pattern matching
    - Excludes zones below minimum bounding box area (filters copper islands)
    - Optionally indexes zones by layer for O(1) lookup performance
    
    Args:
        board: pcbnew.BOARD object
        ground_patterns: list[str] - Ground net patterns (e.g., ['GND', 'GROUND'])
        min_area_mm2: float - Minimum zone bounding box area in mm² (default 10.0)
        index_by_layer: bool - Return layer-indexed dict for fast lookup (default True)
    
    Returns:
        tuple: (zones_list, zones_by_layer_dict) or (zones_list, {}) if not indexed
    
    Example:
        >>> zones, zones_by_layer = self.get_ground_zones(board, ['GND'], 10.0)
        >>> print(f"Found {len(zones)} ground zones on {len(zones_by_layer)} layers")
    """
    zones = []
    zones_by_layer = {} if index_by_layer else None
    
    for zone in board.Zones():
        zone_net = zone.GetNetname().upper()
        
        # Check if zone matches ground patterns
        if not any(pattern.upper() in zone_net for pattern in ground_patterns):
            continue
        
        # Check if zone is filled (required for hit testing)
        if not zone.IsFilled():
            continue
        
        # Calculate bounding box area
        bbox = zone.GetBoundingBox()
        width_mm = pcbnew.ToMM(bbox.GetWidth())
        height_mm = pcbnew.ToMM(bbox.GetHeight())
        area_mm2 = width_mm * height_mm
        
        # Filter by minimum area
        if area_mm2 < min_area_mm2:
            continue
        
        # Add to results
        zones.append(zone)
        
        # Optionally index by layer
        if index_by_layer:
            layer = zone.GetLayer()
            if layer not in zones_by_layer:
                zones_by_layer[layer] = []
            zones_by_layer[layer].append(zone)
    
    return zones, zones_by_layer if index_by_layer else {}
```

**Estimated Lines Saved**: ~20 lines (if reused in future checks)

---

### 2.6 **PRIORITY 6: Coordinate Formatting**

**Repeated Pattern** (appears 50+ times across all modules):
```python
# Manual coordinate formatting - inconsistent precision
f"({pcbnew.ToMM(pos.x):.2f}, {pcbnew.ToMM(pos.y):.2f}) mm"
f"Position: ({pcbnew.ToMM(sample_x):.2f}, {pcbnew.ToMM(sample_y):.2f}) mm"
```

**Impact**: Low - Improves consistency, reduces typos

**Recommended Solution**:
```python
# emc_auditor_plugin.py - Add new utility function
def format_position_mm(self, pos, precision=2):
    """
    Format a position vector as "(X.XX, Y.YY) mm" string.
    
    Args:
        pos: pcbnew.VECTOR2I or tuple(x, y) - Position to format
        precision: int - Decimal places (default 2)
    
    Returns:
        str: Formatted coordinate string
    
    Example:
        >>> pos = pcbnew.VECTOR2I(pcbnew.FromMM(12.345), pcbnew.FromMM(67.890))
        >>> print(self.format_position_mm(pos))
        "(12.35, 67.89) mm"
    """
    if hasattr(pos, 'x') and hasattr(pos, 'y'):
        x_mm = pcbnew.ToMM(pos.x)
        y_mm = pcbnew.ToMM(pos.y)
    else:
        x_mm = pcbnew.ToMM(pos[0])
        y_mm = pcbnew.ToMM(pos[1])
    
    return f"({x_mm:.{precision}f}, {y_mm:.{precision}f}) mm"
```

**Estimated Lines Saved**: ~10 lines (cleaner code, not significant line reduction)

---

### 2.7 **PRIORITY 7: Adjacent Layer Calculation** (Optional)

**Location**: ground_plane.py lines 458-495 (38 lines)

**Current Status**: This is ground-plane-specific layer stack heuristics

**Recommendation**: 
- **Keep in ground_plane.py module** unless other checks need adjacent layer logic
- If future checks need this (e.g., trace impedance, differential pairs), move to main plugin
- Current placement is correct (domain-specific)

---

## 3. Code That Should NOT Be Centralized (✓ CORRECT)

The following code is correctly kept in specialized modules because it implements **domain-specific algorithms**:

### 3.1 EMI Filter Topology Classification (emi_filtering.py)
- Lines 197-519: Complex filter detection (Pi, T, LC, differential, common-mode)
- **Reason**: EMI-specific domain knowledge, not reusable by other checks

### 3.2 IEC60664-1 Table Interpolation (clearance_creepage.py)
- Lines 455-509: Voltage-to-clearance table interpolation
- **Reason**: Electrical safety standard implementation, specific to clearance check

### 3.3 Ground Plane Sampling Algorithm (ground_plane.py)
- Lines 257-352: Trace sampling, hit testing, gap detection with via/pad clearance
- **Reason**: Ground continuity-specific algorithm

### 3.4 Differential Pair Detection (emi_filtering.py)
- Lines 351-405: Common-mode choke/capacitor detection
- **Reason**: Interface-specific pattern matching

---

## 4. Implementation Recommendations

### Phase 1: High-Impact Centralization (Recommended)
Implement Priority 1-4 utilities to eliminate most code duplication:

1. **Add to emc_auditor_plugin.py** (new utility functions):
   ```python
   # Line ~580 (after get_nets_by_class)
   def create_logger(self, verbose, report_lines):
   def create_violation_group(self, board, check_type, identifier, violation_number=None):
   def is_ground_net(self, net_name, ground_patterns):
   def is_power_net(self, net_name, power_patterns):
   def get_vias_by_net_pattern(self, board, net_patterns):
   ```

2. **Update all 5 modules** (via_stitching, decoupling, emi_filtering, ground_plane, clearance_creepage):
   - Remove `log()` method from each module class
   - Update `check()` signature to receive `log_func` parameter
   - Replace violation group creation boilerplate with utility function calls
   - Replace pattern matching with `is_ground_net()` and `is_power_net()` calls

3. **Update delegation calls in emc_auditor_plugin.py**:
   ```python
   # Example: check_via_stitching
   log_func = self.create_logger(verbose, self.report_lines)
   violations = checker.check(
       draw_marker_func=self.draw_error_marker,
       draw_arrow_func=self.draw_arrow,
       get_distance_func=self.get_distance,
       log_func=log_func
   )
   ```

**Estimated Total Lines Saved**: ~150-200 lines across all files  
**Estimated Time**: 3-4 hours for implementation + testing

### Phase 2: Optional Enhancements (Future)
Implement Priority 5-6 if needed:
- `get_ground_zones()` - if more checks need zone filtering
- `format_position_mm()` - for consistent coordinate formatting

**Estimated Total Lines Saved**: ~30 lines  
**Estimated Time**: 1 hour

---

## 5. Architectural Correctness Assessment

### ✅ Good Practices Already Implemented:
1. **Dependency Injection**: Main plugin injects utility functions into modules (avoid tight coupling)
2. **Single Responsibility**: Each module handles one type of EMC check
3. **Configuration Centralization**: All settings in emc_rules.toml, loaded once by main plugin
4. **Shared State Management**: `report_lines` list shared between main and modules for unified reporting

### ⚠️ Areas for Improvement:
1. **Log Function Duplication**: Current code has 5 identical `log()` implementations
2. **Boilerplate Reduction**: Violation group creation could be abstracted
3. **Pattern Matching**: Common net filtering logic could be utilities

### ✓ Correctly Isolated Domain Logic:
- EMI filter classification algorithms
- Electrical safety standard calculations
- Ground plane continuity algorithms
- Differential pair detection heuristics

---

## 6. Migration Impact Assessment

### Low Risk Changes (Safe to implement):
✅ Priority 1-4 utilities - These are pure functions that don't change plugin behavior, only eliminate duplication

### Testing Requirements:
After implementing centralization:
1. Run full EMC audit on test board (CSI_current_measurment.kicad_pcb)
2. Verify violation counts unchanged:
   - Via stitching: 0 violations
   - Decoupling: 9 violations
   - Ground plane: 4 violations
   - EMI filtering: 22 violations
   - Clearance: 4 violations
   - **Total: 40 violations (must match previous results)**

3. Verify markers and arrows render correctly
4. Verify report text formatting unchanged

### Backwards Compatibility:
✅ **No breaking changes** - Modules remain compatible with existing main plugin until migration complete

---

## 7. Summary Table

| Priority | Utility Function | Lines Saved | Impact | Effort |
|----------|-----------------|-------------|--------|--------|
| 1 | `create_logger()` | ~45 | High | Low |
| 2 | `create_violation_group()` | ~80 | High | Medium |
| 3 | `is_ground_net()` / `is_power_net()` | ~30 | Medium | Low |
| 4 | `get_vias_by_net_pattern()` | ~15 | Medium | Low |
| 5 | `get_ground_zones()` | ~20 | Low | Medium |
| 6 | `format_position_mm()` | ~10 | Low | Low |
| **Total (P1-4)** | **4 functions** | **~170** | **High** | **2-3 hrs** |
| **Total (All)** | **6 functions** | **~200** | **High** | **4-5 hrs** |

---

## 8. Conclusion

The EMC Auditor Plugin has a **solid modular architecture** with good separation of concerns. The main opportunities for improvement are:

1. **Eliminate duplicate `log()` methods** (Priority 1) - 5 identical implementations
2. **Abstract violation group creation** (Priority 2) - 40+ instances of boilerplate
3. **Centralize net pattern matching** (Priority 3-4) - Improve readability

Implementing Priorities 1-4 would:
- ✅ Reduce codebase by ~170 lines (~6% reduction)
- ✅ Eliminate all code duplication
- ✅ Improve maintainability (single source of truth)
- ✅ Maintain existing architecture (no breaking changes)
- ✅ Preserve domain-specific logic in specialized modules

**Recommendation**: **Proceed with Phase 1 implementation** (Priorities 1-4) to maximize code reuse while preserving the excellent modular design.
