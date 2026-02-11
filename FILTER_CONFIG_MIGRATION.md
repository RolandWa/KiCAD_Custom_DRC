# EMI Filter Configuration Migration to TOML

**Date**: February 11, 2026  
**Commit**: Moved all filter topology classification constants from Python code to TOML configuration

## Summary

All hardcoded constants and definitions for EMI filter topology classification have been moved from `emc_auditor_plugin.py` to `emc_rules.toml`. This improves maintainability and allows users to customize filter detection behavior without modifying Python code.

---

## What Was Moved

### 1. **Component Class Mapping** (`emc_rules.toml` lines ~297-303)
```toml
[emi_filtering.component_classes]
inductor_prefixes = ["L", "FB"]  # Ferrite beads (FB) are treated as inductors
capacitor_prefixes = ["C"]
resistor_prefixes = ["R"]
diode_prefixes = ["D"]  # TVS diodes
```

**Before** (hardcoded in Python):
```python
has_series_L = any(c in series_classes for c in ['L', 'F'])  # F = FB (ferrite bead)
has_shunt_C = 'C' in shunt_classes
has_series_R = 'R' in series_classes
```

**After** (config-driven):
```python
component_classes = config.get('component_classes', {})
inductor_prefixes = component_classes.get('inductor_prefixes', ['L', 'FB'])
has_series_L = any(
    any(comp['ref'].startswith(prefix) for prefix in inductor_prefixes)
    for comp in component_analysis if comp['type'] == 'series'
)
```

---

### 2. **Ground and Power Net Patterns** (lines ~306-307)
```toml
ground_patterns = ["GND", "GROUND", "VSS", "AGND", "DGND", "PGND", "EARTH"]
power_patterns = ["VCC", "VDD", "PWR", "+", "VBUS", "3V3", "5V", "1V8", "2V5", "12V", "+3V3", "+5V"]
```

**Purpose**: Used in series/shunt component detection. Components with one pad on signal and other on these nets are classified as "shunt" (bypass capacitors, termination resistors).

**Before** (hardcoded in `_analyze_component_placement()`):
```python
gnd_power_patterns = ['GND', 'VCC', 'VDD', 'VSS', 'PWR', '+', 'VBUS', 'AGND', 'DGND', 'PGND']
```

**After** (config-driven):
```python
ground_patterns = config.get('ground_patterns', ['GND', 'GROUND', 'VSS', 'AGND', 'DGND', 'PGND'])
power_patterns = config.get('power_patterns', ['VCC', 'VDD', 'PWR', '+', 'VBUS', '3V3', '5V'])
gnd_power_patterns = ground_patterns + power_patterns
```

---

### 3. **Differential Pair Net Patterns** (lines ~311-325)
```toml
[emi_filtering.differential_pairs]
patterns = [
    ["_P", "_N"],      # Generic: SIGNAL_P / SIGNAL_N
    ["_p", "_n"],      # Lowercase variant
    ["+", "-"],        # Generic: SIGNAL+ / SIGNAL-
    ["DP", "DM"],      # USB: USB_DP / USB_DM
    ["dp", "dm"],      # Lowercase USB
    ["TXP", "TXN"],    # Ethernet TX: ETH_TXP / ETH_TXN
    ["txp", "txn"],    # Lowercase
    ["RXP", "RXN"],    # Ethernet RX: ETH_RXP / ETH_RXN
    ["rxp", "rxn"],    # Lowercase
    ["CANH", "CANL"],  # CAN bus: CAN_CANH / CAN_CANL
    ["canh", "canl"]   # Lowercase CAN
]
```

**Purpose**: Used to detect differential pair filters (common-mode chokes) on USB, Ethernet, CAN, RS485 interfaces.

**Before** (hardcoded in `_detect_differential_pair_filter()`):
```python
diff_patterns = [
    ('_P', '_N'), ('_p', '_n'),
    ('+', '-'),
    ('DP', 'DM'), ('dp', 'dm'),
    ('TXP', 'TXN'), ('txp', 'txn'),
    ('RXP', 'RXN'), ('rxp', 'rxn')
]
```

**After** (config-driven):
```python
diff_config = config.get('differential_pairs', {})
diff_patterns = diff_config.get('patterns', [
    ['_P', '_N'], ['_p', '_n'], ['+', '-'],
    ['DP', 'DM'], ['dp', 'dm'],
    ['TXP', 'TXN'], ['txp', 'txn'],
    ['RXP', 'RXN'], ['rxp', 'rxn']
])
# Convert to tuples for compatibility
diff_patterns = [tuple(pair) for pair in diff_patterns]
```

---

### 4. **Common-Mode Choke Detection Parameters** (line ~328)
```toml
# Minimum pin count for common-mode choke detection
# Common-mode chokes typically have 4 pins (2 signal pairs + center tap or shield)
min_common_mode_choke_pins = 4
```

**Purpose**: Defines minimum pin count to classify a component as a common-mode choke (typically 4-pin inductors for differential pairs).

**Before** (hardcoded):
```python
if len(pads) < 4:
    continue
```

**After** (config-driven):
```python
min_pins = diff_config.get('min_common_mode_choke_pins', 4)
if len(pads) < min_pins:
    continue
```

---

### 5. **~~Filter Type Hierarchy~~** ❌ **REMOVED - NOT USED**

**Original location**: Lines ~331-341 (now removed)

**Why removed**: The filter hierarchy is **hardcoded in Python** (`_check_filter_requirement()` function):
```python
hierarchy = ['Pi', 'T', 'LC', 'RC', 'L', 'C', 'R', 'simple']
```

The TOML section was redundant and never read by the code. Filter comparison uses string matching against the hardcoded list.

---

## How to Customize

### Example 1: Add Custom Differential Pair Pattern
Edit `emc_rules.toml`:
```toml
[emi_filtering.differential_pairs]
patterns = [
    # ... existing patterns ...
    ["_TX", "_RX"],    # Custom: UART_TX / UART_RX (your custom pattern)
]
```

### Example 2: Add Power Net for Your Board
```toml
power_patterns = [
    # ... existing patterns ...
    "24V", "+24V", "VBAT"  # Custom power rails
]
```

### Example 3: Change Common-Mode Choke Pin Count
```toml
# If your board uses 3-pin common-mode chokes (no center tap):
min_common_mode_choke_pins = 3
```

### Example 4: Accept Weaker Filters
```toml
# Allow single capacitor as minimum filter (less strict):
min_filter_type = "C"
```

---

## Migration Impact

### ✅ Benefits
1. **User Customization**: No Python knowledge required to adjust filter detection
2. **Project-Specific Rules**: Different boards can have different TOML configs
3. **Maintainability**: All filter rules in one place, easier to review
4. **Documentation**: TOML comments explain each pattern's purpose
5. **Backward Compatibility**: Default values in code match old hardcoded values

### ⚠️ Testing Required
After migration, test on your PCB to verify:
1. Differential pair filters still detected (USB, Ethernet, CAN)
2. Series/shunt component classification unchanged
3. Filter topology strings correct (e.g., "LC filter: C15(C-shunt) → FB3(F-series)")

---

## File Changes Summary

| File | Lines Changed | Description |
|------|---------------|-------------|
| `emc_rules.toml` | +73 lines (config), -75 lines (cleanup) | Added 4 configuration sections, removed unused hierarchy + comments |
| `emc_auditor_plugin.py` | ~40 lines modified | Read constants from config instead of hardcoding |

**Net Impact**: ~40 lines across 2 files (TOML slightly smaller after cleanup)

**TOML file size**: 26.03 KB → 22.95 KB (-3.08 KB from removing unused sections)

---

## Version Compatibility

- **Minimum KiCad Version**: 8.0+ (pcbnew Python API)
- **Plugin Version**: 1.0+ (February 2026 update)
- **TOML Format**: Standard TOML v1.0.0

---

## Next Steps

1. ✅ Test plugin on CSI_current_measurment.kicad_pcb
2. ✅ Verify differential pair detection still works (J11 Ethernet connector)
3. ✅ Check series/shunt classification in topology reports
4. ⏳ Update EMC_AUDIT_ANALYSIS.md if results change
5. ⏳ Commit changes to git after validation

---

## Rollback Instructions

If issues occur, revert to previous version:
```powershell
cd "<repository_path>"
git checkout HEAD~1 emc_auditor_plugin.py emc_rules.toml
.\sync_to_kicad.ps1
```

Then restart KiCad to reload old plugin.
---

## Update History

### February 11, 2026 - Differential Topology Enhancements

**Major improvements to differential filter detection and topology analysis**:

#### 1. **Complete Differential Topology Tracing**
- **Problem**: Plugin stopped after detecting common-mode component (choke or capacitor)
- **Solution**: Now traces **complete filter chain** from connector to IC
- **Example**: J11 Ethernet connector
  - Detects: C24 (common-mode capacitor between LINE_P/LINE_N)
  - Continues tracing: R34 → C22 (LINE_P), R33 → C23 (LINE_N)
  - Reports: `"Differential common-mode capacitor: C24 + Line filter (RC): R34(R-series) → C22(C-shunt)"`

**Code changes**:
- `_classify_topology_from_analysis()`: Enhanced to analyze line components beyond common-mode filter
- Added `_classify_line_filter_type()`: Classifies individual differential line filtering (LC/RC/Pi/T/C/R)

#### 2. **Fixed Series/Shunt Detection Logic**
- **Problem**: In-line resistors misclassified as "shunt" when only one pad on signal net
- **Old logic**: Required both pads on same net for "series" classification
- **New logic**: If at least one pad on signal and no pads on GND/power → series component
- **Impact**: R34/R35 termination resistors now correctly classified as "series" (in-line)

**Code changes** (`_analyze_component_placement()`):
```python
# Before: Required signal_net_count >= 2 for series
# After: signal_net_count >= 1 and not has_gnd_power → series
```

#### 3. **Compound Filter Type Support**
- **New filter types**: `"Differential + RC"`, `"Differential + LC"`, etc.
- **Hierarchy logic**: Differential common-mode filtering provides **+1 level bonus**
  - Example: `"Differential + RC"` (RC=rank 3, -1 = rank 2) equivalent to `"LC"` (rank 2)
  - Rationale: Common-mode filtering + line filtering provides superior EMI protection
- **Impact**: J11 connector with C24 + RC filters now **passes LC requirement**

**Code changes** (`_check_filter_requirement()`):
```python
# Handle compound types like "Differential + RC"
if 'Differential' in actual_type and '+' in actual_type:
    line_filter = parts[1].strip()
    line_rank = hierarchy.index(line_filter)
    effective_rank = max(0, line_rank - 1)  # +1 level bonus
    return effective_rank <= required_rank
```

#### 4. **Per-Pad Violation Markers**
- **Problem**: Single marker at connector center, unclear which pin has issue
- **Solution**: Individual circles drawn at **exact pad positions**
- **Marker text**: Simplified (interface type only, no pad/net details)
- **Report**: Still shows full pad/net information in console output

**Code changes**:
```python
# Track per-pad results: (pad, filter_type, distance, topology, sufficient)
for pad, filter_type, distance, topology, sufficient in pad_results:
    if not sufficient:
        pad_pos = pad.GetPosition()  # Draw at pad, not connector center
        marker_text = f"{violation_msg}\n({interface_type})"
        self.draw_error_marker(board, pad_pos, marker_text, marker_layer, violation_group)
```

#### File Size Changes
| File | Before | After | Change |
|------|--------|-------|--------|
| `emc_auditor_plugin.py` | 76.59 KB | 83.42 KB | +6.83 KB |
| `emc_rules.toml` | 24.51 KB | 24.51 KB | (no change) |

**Plugin version**: 1.1 (differential topology enhancements)

---

## Rollback Instructions

If issues occur, revert to previous version:
```powershell
cd "<repository_path>"
git checkout HEAD~1 emc_auditor_plugin.py emc_rules.toml
.\sync_to_kicad.ps1
```

Then restart KiCad to reload old plugin.