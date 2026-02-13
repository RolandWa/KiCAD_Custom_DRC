# EMC Auditor Plugin for KiCad

**Version:** 1.4.0  
**KiCad Version:** 9.0.7+  
**Last Updated:** February 13, 2026

## Overview

The EMC Auditor plugin automatically checks your PCB design for electromagnetic compatibility (EMC) violations and visually marks them on the board. All rules are configurable via the `emc_rules.toml` file.

## What's New in v1.4.0 (February 13, 2026)

### ⚡ Clearance & Creepage Checking (IMPLEMENTED)
- **Full IEC60664-1 compliance** - Electrical safety verification for mains-powered equipment
- **Hybrid pathfinding algorithm**:
  - **Visibility graph + Dijkstra** for <100 obstacles (optimal shortest path)
  - **Fast A* algorithm** for dense boards (≥100 obstacles, handles up to 500 obstacles)
  - **Spatial indexing** (grid-based) dramatically reduces obstacle queries from O(N) to O(1)
- **Clearance checking** - Verifies minimum air gap between voltage domains (2D distance)
- **Creepage checking** - Calculates surface path along PCB, avoiding copper obstacles
- **KiCad Net Classes** - Preferred method for voltage domain assignment
- **Comprehensive configuration**:
  - 4 IEC60664-1 clearance tables (overvoltage categories I-IV)
  - 12 IEC60664-1 creepage tables (Material Groups I/II/IIIa/IIIb × Pollution Degrees 1/2/3)
  - 3 IPC2221 spacing tables (external coated/uncoated, internal embedded)
  - 6 voltage domains (MAINS_L, MAINS_N, HIGH_VOLTAGE_DC, LOW_VOLTAGE_DC, EXTRA_LOW_VOLTAGE, GROUND)
- **Performance**: 15-30 seconds for complex multi-voltage boards with multiple isolation requirements
- **Tested on real boards** - Successfully identified 6 safety violations on Ethernet/mains design

### Previous Updates - v1.3.0 (February 12, 2026)

### 🏗️ Modular Architecture Refactoring
- **Separated checker modules** - Each DRC check now in dedicated Python file for better maintainability
- **Dependency injection pattern** - Utility functions (draw markers, arrows, distance) injected from main plugin
- **Reduced complexity** - Main plugin reduced from 1172 to ~500 lines
- **New module files**:
  - `via_stitching.py` - Via stitching checker with Net Class support
  - `decoupling.py` - Decoupling capacitor proximity checker
  - `emi_filtering.py` - EMI filtering verification for connectors
  - `clearance_creepage.py` - IEC60664-1 and IPC2221 safety compliance checker (2206 lines)
  - `ground_plane.py` - Ground plane continuity checker
- **Shared reporting** - All modules write to common report log
- **Better extensibility** - Easy to add new checkers following established pattern

### 📦 Installation Changes
- **5 new Python module files required** - Must copy all module files to plugins directory
- **Updated sync script** - Automatically copies all required files

## Previous Updates - v1.2.0 (February 11, 2026)

### 🎯 Differential Topology Enhancements
- **Complete filter chain tracing** - Analyzes entire path from connector through common-mode component to IC
- **Compound filter types** - Detects and reports "Differential + RC/LC" topologies
- **Smart filter hierarchy** - Differential + line filtering satisfies higher requirements (e.g., "Differential + RC" passes LC spec)

### 🔧 Improved Component Analysis
- **Fixed series/shunt detection** - In-line resistors now correctly classified (at least 1 pad on signal, no GND/power = series)
- **Per-pad violation markers** - Circles drawn at exact pad positions, clearly showing which pin has issues
- **Enhanced topology reporting** - Shows complete component chain with series/shunt designation

### 📊 Example Output
```
J11 Ethernet Connector:
  ✓ Differential + RC filter detected
  Topology: Differential common-mode capacitor: C24 between LINE_P/LINE_N 
            + Line filter (RC): R34(R-series) → C22(C-shunt)
  Status: PASS (equivalent to LC requirement)
```

See [FILTER_CONFIG_MIGRATION.md](FILTER_CONFIG_MIGRATION.md) for complete technical details.

## Features

✅ **Via Stitching Verification** - Ensures critical signal vias have nearby GND return vias  
✅ **Decoupling Capacitor Proximity** - Verifies IC power pins have nearby decoupling caps  
✅ **Ground Plane Continuity** - Verifies continuous ground plane under high-speed traces with advanced filtering  
✅ **Clearance and Creepage Rules (IEC60664-1 / IPC2221)** - Safety compliance verification:
  - Electrical clearance (air gap) between voltage domains
  - Creepage distance (surface path) verification
  - Reinforced insulation for mains-to-SELV isolation
  - Overvoltage category I-IV support
  - Pollution degree 1-4 tables
  - Material group (CTI) for FR4 and specialty boards
  - Altitude correction for >2000m elevation  
✅ **TOML Configuration** - All rules externally configurable  
✅ **Custom Icon** - EMC shield symbol in KiCad toolbar  
✅ **Visual Markers** - Violations drawn on User.Comments layer  
✅ **Progress Dialog** - Real-time feedback for long-running checks  
✅ **Keyboard Shortcuts** - Ctrl+S to save report, Escape to close  
✅ **Extensible Architecture** - Easy to add new EMC rules

## Available Rules and Documentation

The EMC Auditor plugin includes both **implemented** and **planned** rules. Each rule has dedicated documentation:

### ✅ Implemented Rules

| Rule | Status | Documentation | Description |
|------|--------|---------------|-------------|
| **Via Stitching** | ✅ Active | [VIA_STITCHING.md](VIA_STITCHING.md) | Ensures critical signal vias have nearby GND return vias within configurable distance (default 2mm). Prevents EMI radiation and maintains signal integrity. |
| **Decoupling Capacitors** | ✅ Active | [DECOUPLING.md](DECOUPLING.md) | Verifies IC power pins have decoupling capacitors within configurable distance (default 3mm). Uses **smart net matching** - only checks capacitors on the same power rail. Includes visual arrows to nearest cap. |
| **Ground Plane Continuity** | ✅ Active | [GROUND_PLANE.md](GROUND_PLANE.md) | Verifies continuous ground plane underneath and around high-speed traces. Features: **performance optimized** (5-10× faster), **progress dialog**, **polygon area filtering**, **preferred layer priority**, **via/pad clearance ignore**. Checks for gaps under trace (default 0.5mm sampling) and clearance zone around trace (default 1mm). |
| **EMI Filtering** | ✅ Active | [FILTER_CONFIG_MIGRATION.md](FILTER_CONFIG_MIGRATION.md) | Verifies EMI filters on connector signal lines. Features: **differential topology tracing** (common-mode + line filters), **LC/RC/Pi/T detection**, **series/shunt component analysis**, **per-pad violation markers**, **compound filter types** ("Differential + RC"). Supports USB, Ethernet, CAN, RS485, and custom interfaces. |
| **Clearance & Creepage** | ✅ Active | [CLEARANCE_CREEPAGE_GUIDE.md](CLEARANCE_CREEPAGE_GUIDE.md)<br>[CLEARANCE_QUICK_REF.md](CLEARANCE_QUICK_REF.md)<br>[CLEARANCE_VS_CREEPAGE_VISUAL.md](CLEARANCE_VS_CREEPAGE_VISUAL.md) | IEC60664-1 and IPC2221 electrical safety compliance. Verifies **clearance** (air gap) and **creepage** (surface path) between voltage domains. Uses **KiCad Net Classes** for domain assignment with fallback to pattern matching. Supports reinforced insulation, overvoltage categories I-IV, pollution degrees 1-4, altitude correction. **Hybrid pathfinding algorithm**: Visibility graph + Dijkstra for <100 obstacles, Fast A* for dense boards (≥100 obstacles). **Spatial indexing** for performance (grid-based obstacle queries). Typical runtime: 15-30 seconds for complex multi-voltage boards. |

### 🚧 Planned Rules (Configuration Ready)

| Rule | Status | Documentation | Description |
|------|--------|---------------|-------------|
| **Trace Width** | 🚧 Config Ready | [TRACE_WIDTH.md](TRACE_WIDTH.md) | Verifies power traces meet minimum width requirements based on current capacity. Includes IPC-2221 formulas for temperature rise and voltage drop calculations. **Implementation pending**. |

### 📋 Additional Rule Templates

See [emc_rules_examples.toml](emc_rules_examples.toml) for configuration templates:
- Differential pairs (length matching, impedance)
- High-speed signals (stub length, bend radius)
- EMI filtering (filters on interfaces)
- Antenna rules, keepout areas, thermal relief
- Silkscreen clearance, power budget estimation

### Documentation Guide

**Quick Start**: Read [VIA_STITCHING.md](VIA_STITCHING.md) or [DECOUPLING.md](DECOUPLING.md) to understand implemented rules

**Safety Compliance**: See clearance/creepage documentation for high-voltage designs:
- [CLEARANCE_CREEPAGE_GUIDE.md](CLEARANCE_CREEPAGE_GUIDE.md) - Complete implementation guide (546 lines)
- [CLEARANCE_QUICK_REF.md](CLEARANCE_QUICK_REF.md) - Quick lookup tables (208 lines)
- [CLEARANCE_VS_CREEPAGE_VISUAL.md](CLEARANCE_VS_CREEPAGE_VISUAL.md) - Illustrated guide with ASCII diagrams (329 lines)

**Extend Plugin**: See "Adding New Rules" section below for implementation tutorial

## Copilot Development Rules

**FOR AI ASSISTANTS**: When modifying or extending this plugin, follow these rules:

### 0. Modular Architecture Pattern (NEW)

The plugin now uses a **modular architecture**:
- **Main plugin** (`emc_auditor_plugin.py`) - Orchestrates checks, provides utility functions
- **Checker modules** - Separate files for each DRC rule (`via_stitching.py`, `decoupling.py`, etc.)
- **Dependency injection** - Main plugin injects utility functions into checkers
- **Shared reporting** - All modules append to common `report_lines` list

**When to create a new module:**
- Complex checks with >100 lines of logic
- Checks requiring extensive configuration parsing
- Checks with multiple helper functions

**Module template:**
```python
class YourChecker:
    def __init__(self, board, marker_layer, config, report_lines, verbose=True, auditor=None):
        self.board = board
        self.marker_layer = marker_layer
        self.config = config
        self.report_lines = report_lines
        self.verbose = verbose
        self.auditor = auditor  # Access to main plugin utilities
        self.draw_marker = None  # Injected
        self.draw_arrow = None   # Injected
        self.get_distance = None # Injected
        self.violation_count = 0
    
    def check(self, draw_marker_func, draw_arrow_func, get_distance_func):
        # Store injected functions
        self.draw_marker = draw_marker_func
        self.draw_arrow = draw_arrow_func
        self.get_distance = get_distance_func
        # Perform checks...
        return self.violation_count
```

**Main plugin integration:**
```python
from your_module import YourChecker

checker = YourChecker(board, marker_layer, config, self.report_lines, verbose, self)
violations = checker.check(self.draw_error_marker, self.draw_arrow, self.get_distance)
```

### 1. Violation Marker Pattern (MANDATORY)

All DRC checks MUST use this exact visualization pattern:

```python
def check_your_rule(self, board, marker_layer, config):
    """Template for new DRC rule implementation"""
    violations = 0
    
    # Your checking logic here
    for item in items_to_check:
        if violation_detected:
            # Step 1: Create individual violation group
            violation_group = pcbnew.PCB_GROUP(board)
            violation_group.SetName(f"EMC_YourRule_{item_id}_{violations+1}")
            board.Add(violation_group)
            
            # Step 2: Draw circle + text at violation location
            self.draw_error_marker(
                board, 
                violation_position,  # pcbnew.VECTOR2I
                "YOUR VIOLATION MESSAGE",  # String with optional {distance} placeholder
                marker_layer, 
                violation_group
            )
            
            # Step 3 (OPTIONAL): Draw arrow to related component
            if show_arrow_to_target:
                self.draw_arrow(
                    board,
                    violation_position,  # Start point
                    target_position,     # End point (related component)
                    "→ TARGET_REF",      # Arrow label (component reference)
                    marker_layer,
                    violation_group
                )
            
            violations += 1
    
    return violations
```

### 2. Configuration Integration

**ALWAYS** support these config parameters:

```toml
[your_rule]
enabled = true                    # REQUIRED: Enable/disable rule
description = "What it checks"    # REQUIRED: Human-readable description
violation_message = "TEXT"        # REQUIRED: What to display at violation

# Rule-specific parameters (your custom logic)
max_distance_mm = 2.0
net_classes = ["HighSpeed"]
net_patterns = ["VCC", "GND"]

# Optional visual enhancements
draw_arrow_to_target = true       # OPTIONAL: Show arrow to related item
show_target_label = true          # OPTIONAL: Show component reference
```

### 3. Group Naming Convention

**Group names MUST follow this pattern:**
```python
f"EMC_{RuleCategory}_{ItemIdentifier}_{SequenceNumber}"
```

**Examples:**
- `"EMC_Decap_U1_VCC"` - Decoupling rule, IC U1, power net VCC
- `"EMC_Via_15"` - Via stitching rule, violation #15
- `"EMC_GndPlane_CLK_3"` - Ground plane rule, CLK net, violation #3
- `"EMC_TraceWidth_PWR_1"` - Trace width rule, PWR net, violation #1

**Why this matters:**
- User can click "Select Items in Group" to see all markers for one violation
- Deleting group removes circle + text + arrows together
- Naming pattern helps debugging and log analysis

### 4. Existing Helper Functions

**DO NOT REIMPLEMENT** these - they already exist:

```python
# Distance calculation (2D Euclidean)
self.get_distance(point1, point2)  # Returns distance in internal units

# Draw violation marker (circle + text)
self.draw_error_marker(board, position, message, layer, group)

# Draw arrow with optional label
self.draw_arrow(board, start_pos, end_pos, label, layer, group)

# Clear old markers before new run
self.clear_previous_markers(board)

# Unit conversions
pcbnew.FromMM(value_mm)  # mm → internal units
pcbnew.ToMM(value_iu)    # internal units → mm
```

### 5. Registration in Run() Method

**ALWAYS** add your check to `Run()` method with enable flag:

```python
def Run(self):
    # ... existing code ...
    
    # X. Your Rule Verification (if enabled)
    your_rule_cfg = self.config.get('your_rule', {})
    if your_rule_cfg.get('enabled', False):  # Default: disabled for new rules
        violations_found += self.check_your_rule(board, marker_layer, your_rule_cfg)
```

### 6. Error Handling Pattern

```python
try:
    # Your checking logic
    if not required_items:
        print("WARNING: No items found for [your_rule] check. Skipping.")
        return 0
except Exception as e:
    print(f"ERROR in [your_rule] check: {e}")
    return 0
```

### 7. Testing Checklist

Before committing new DRC rule:
- [ ] Rule can be enabled/disabled via `enabled = true/false`
- [ ] Violation markers visible on User.Comments layer
- [ ] Each violation has unique group name
- [ ] Clicking marker → right-click → "Select Items in Group" works
- [ ] Re-running plugin clears old markers
- [ ] Console shows "Found X violation(s)" count
- [ ] README.md updated with usage example
- [ ] Config file (`emc_rules.toml`) includes template

### 8. Performance Guidelines

- **Avoid O(n³)** algorithms - keep checks O(n²) or better
- **Cache layer lookups**: Call `board.GetLayerID()` once, not in loops
- **Use spatial indexing**: Group items by layer before distance checks
- **Limit arrow drawing**: Only show arrows if `draw_arrow = true` in config

### 9. Future Rule Integration

When implementing rules from `emc_rules.toml` (currently disabled):

**Priority order:**
1. **Trace Width** - Power trace current capacity
2. **Clearance/Creepage** - High-voltage safety (IEC60664-1)
3. **Differential Pairs** - Length matching, impedance
4. **High-Speed Signals** - Stub length, bend radius
5. **EMI Filtering** - Ferrite bead placement

Each follows the **same marker pattern** described above.

---

## Installation

1. Copy all files to your KiCad plugins directory:
   - Windows: `C:\Users\<username>\Documents\KiCad\9.0\3rdparty\plugins\`
   - Linux: `~/.local/share/kicad/9.0/3rdparty/plugins/`
   - macOS: `~/Library/Application Support/kicad/9.0/3rdparty/plugins/`

2. Required files (place directly in plugins directory, NOT in subfolder):
   ```
   emc_auditor_plugin.py  (main plugin orchestrator)
   via_stitching.py       (via stitching checker module)
   decoupling.py          (decoupling capacitor checker module)
   emi_filtering.py       (EMI filtering checker module)
   clearance_creepage.py  (clearance/creepage checker module)
   ground_plane.py        (ground plane continuity checker module)
   emc_rules.toml         (configuration file)
   emc_icon.png           (toolbar icon - KiCad 9.x requires PNG)
   ```

3. Install TOML library (if not using Python 3.11+):
   ```bash
   pip install tomli
   # or
   pip install toml
   ```

4. Restart KiCad

**Note**: All module files must be present even if checks are disabled. The plugin handles missing modules gracefully with warning messages.

## Development & Testing

When modifying the plugin code or configuration, use the sync script to quickly copy files to KiCad's plugins directory:

### Setup Sync Script (First Time Only)

1. Copy the template file:
   ```powershell
   Copy-Item sync_to_kicad.ps1.template sync_to_kicad.ps1
   ```

2. Edit `sync_to_kicad.ps1` and update the `$PluginsDir` variable with your KiCad path:
   ```powershell
   # Example paths:
   $PluginsDir = "C:\Users\<YourUsername>\Documents\KiCad\9.0\3rdparty\plugins"
   # Or for OneDrive:
   $PluginsDir = "C:\Users\<YourUsername>\OneDrive\<Path>\KiCad\9.0\3rdparty\plugins"
   ```

3. The `sync_to_kicad.ps1` file is gitignored (contains local paths) and won't be committed.

### Using the Sync Script

```powershell
# Run from repository root
.\sync_to_kicad.ps1
```

This automatically copies:
- `emc_auditor_plugin.py` → Main plugin orchestrator
- `via_stitching.py` → Via stitching checker module
- `decoupling.py` → Decoupling checker module
- `emi_filtering.py` → EMI filtering checker module
- `clearance_creepage.py` → Clearance/creepage checker module
- `emc_rules.toml` → Configuration
- `emc_icon.png` → Toolbar icon

**Development Workflow**:
1. Edit plugin code or configuration in your repository
2. Run `.\sync_to_kicad.ps1` to sync changes
3. Restart KiCad PCB Editor to reload plugin
4. Test changes on PCB design
5. Repeat as needed

**Note**: KiCad caches plugins on startup - you MUST restart KiCad PCB Editor after syncing changes.

## Usage

### Running the Plugin

1. Open your PCB design in KiCad PCB Editor
2. Click the **EMC Auditor** icon in the toolbar (shield with lightning bolt)
   - Or: **Tools → External Plugins → EMC Auditor**
3. Wait for analysis to complete
4. Check the **User.Comments** layer for violation markers

### Decoupling Capacitor Proximity

- **Red circles** mark IC power pins that are too far from capacitors
- **Text labels** show the actual distance measured (e.g., "CAP TOO FAR (4.2mm)")
- **Arrows with labels** point from the IC pin to the nearest capacitor (e.g., "→ C15")
  - **SMART MATCHING**: Only finds capacitors connected to the SAME power net (VCC→VCC, 3V3→3V3)
  - Helps identify which specific capacitor is being measured
  - Shows the direction to relocate capacitor for better proximity
  - Can be disabled in configuration if not needed
- **Each violation grouped**: Circle + text + arrow grouped together as "EMC_Decap_U1_VCC"

### Via Stitching

- **Red circles** mark critical signal vias missing nearby GND return vias
- **Text "NO GND VIA"** indicates the violation type
- **Each violation grouped**: Markers grouped as "EMC_Via_1", "EMC_Via_2", etc.

### Ground Plane Continuity

- **Red circles** mark locations where ground plane is missing under high-speed traces
- **Text labels** show violation type: "NO GND PLANE"
- **Each violation grouped**: Markers grouped as "EMC_GndPlane_NetName_1", etc.
- **Applies to**: High-speed net classes (HighSpeed, Clock, Differential, USB, Ethernet)
- **Advanced filtering** (NEW):
  - Ignores small copper islands (< 10mm² by default)
  - Skips false positives near ground vias (within 0.5mm)
  - Skips false positives near ground pads (within 0.3mm)
  - Prioritizes inner ground layers (In1.Cu, In2.Cu)
- **Progress dialog**: Shows real-time progress for long checks (>10 tracks)

**EMC Rationale:**
- Continuous ground under trace = minimal return path loop area (reduces radiated emissions)
- Clearance around trace = ground "moat" shields adjacent circuits from EMI
- Critical for signal integrity and EMC compliance

### Violation Visualization Examples

All rules use a **consistent visual language** for violations:

```
┌─────────────────────────────────────────────────────────┐
│  VIOLATION MARKER COMPONENTS (Standard for All Rules)   │
├─────────────────────────────────────────────────────────┤
│  1. ⭕ Red Circle  - Marks exact violation location     │
│  2. 📝 Text Label  - Describes violation type/distance  │
│  3. ➡️  Arrow      - Points to related component (optional) │
│  4. 🏷️  Label      - Identifies target component          │
│  5. 📦 Group       - All markers grouped for easy delete  │
└─────────────────────────────────────────────────────────┘

Example 1: Decoupling Capacitor Violation

    [U1 IC]                    [C15 Cap]
       |                          |
       ⭕ ← Red circle at IC pin
       |
   "CAP TOO FAR (4.2mm)" ← Distance text
       |
       ────────────────→ ← Arrow to nearest cap
                "→ C15" ← Capacitor label

   Group: "EMC_Decap_U1_VCC"


Example 2: Via Stitching Violation

    [Signal Via] ← High-speed trace via
         ⭕ ← Red circle
         |
    "NO GND VIA" ← Violation text

   Group: "EMC_Via_1"


Example 3: Ground Plane Violation

    [High-Speed Trace]
    ════════════════ ← Clock trace
           ⭕ ← Gap detected
           |
    "NO GND PLANE UNDER TRACE" ← Violation text
           |
           ────────→ ← Arrow to gap location
              "GND GAP"

   Group: "EMC_GndPlane_CLK_1"
```

**Visual Hierarchy:**
- **Circle size**: 0.8mm radius (configurable)
- **Text size**: 0.5mm height (configurable)
- **Line width**: 0.1mm (configurable)
- **Arrow length**: 0.5mm arrowhead
- **All drawn on**: User.Comments layer (Cmts.User)

### Managing Markers

Each violation has its own group for easy one-by-one deletion:
- **Delete single violation**: Click marker → right-click → "Select Items in Group" → Delete
- **Delete all violations**: Re-run plugin (auto-clears previous markers)
- **Group names**: "EMC_Decap_U1_VCC" (decoupling) or "EMC_Via_1" (via stitching)
- **Hide violations**: Turn off visibility of User.Comments layer

### Console Output

The plugin prints a summary to the KiCad console:
```
EMC config loaded: EMC Auditor v1.0.0
EMC Audit Complete. Found 3 violation(s).
Check User.Comments layer for markers.
```

## Configuration

### Edit Rules

Edit `emc_rules.toml` to customize verification rules:

```toml
[via_stitching]
enabled = true
max_distance_mm = 2.0  # Change to 1.5mm for stricter rules
critical_net_classes = ["HighSpeed", "Clock", "Differential"]
ground_net_patterns = ["GND", "GROUND", "VSS", "PGND", "AGND"]
violation_message = "NO GND VIA"

[decoupling]
enabled = true
max_distance_mm = 3.0  # Change to 5.0mm for relaxed rules
ic_reference_prefixes = ["U"]  # Add "IC" for other IC prefixes
capacitor_reference_prefixes = ["C"]
power_net_patterns = ["VCC", "VDD", "PWR", "3V3", "5V", "1V8"]
violation_message = "CAP TOO FAR ({distance:.1f}mm)"

# Visual arrow options
draw_arrow_to_nearest_cap = true  # Show arrow to nearest capacitor
show_capacitor_label = true       # Display capacitor reference (e.g., "→ C15")
```

**Arrow Visualization:**
- When a decoupling violation is found, an arrow is drawn from the IC power pin to the nearest capacitor
- The arrow label shows which capacitor is closest (e.g., "→ C15")
- This helps you quickly identify:
  - Which capacitor needs to be moved closer
  - The direction to relocate the capacitor
  - Alternative capacitor locations

**To disable arrows:**
```toml
draw_arrow_to_nearest_cap = false  # Hide arrows
show_capacitor_label = false       # Hide labels (if arrows enabled)
```

### Clearance and Creepage (IEC60664-1 / IPC2221)

**Define voltage domains:**

```toml
[clearance_creepage]
enabled = true  # ✅ IMPLEMENTED - Full IEC60664-1 compliance with hybrid pathfinding
check_clearance = true  # Verify air gap distances
check_creepage = true   # Verify surface path distances (requires hybrid algorithm)
standard = "IEC60664-1"  # or "IPC2221" or "BOTH"
overvoltage_category = "II"  # I-IV
pollution_degree = 2  # 1-4
material_group = "II"  # I, II, IIIa, IIIb (FR4 = II)

[[clearance_creepage.voltage_domains]]
name = "MAINS_230V"
voltage_rms = 230
net_patterns = ["AC_L", "MAINS_L", "LINE"]
requires_reinforced_insulation = true

[[clearance_creepage.voltage_domains]]
name = "ISOLATED_5V"
voltage_rms = 5
net_patterns = ["5V_ISO", "SELV"]

# Define safety requirements
[[clearance_creepage.isolation_requirements]]
domain_a = "MAINS_230V"
domain_b = "ISOLATED_5V"
isolation_type = "reinforced"
min_clearance_mm = 6.0  # 2× basic for 230V mains
min_creepage_mm = 8.0
description = "Mains to SELV - Class II equipment"
```

**Common Quick Values (20% safety margin included):**
- 3.3V/5V logic → GND: **0.15mm** (PCB fab minimum)
- 12V/24V power → GND: **0.6mm** (industrial standard)
- 48V (SELV) → GND: **0.75mm** (telecom safety limit)
- 230V AC → GND: **3.0mm clearance, 4.0mm creepage** (basic insulation)
- 230V AC → SELV: **7.2mm clearance, 9.6mm creepage** (reinforced) ⚠️

**See:** [CLEARANCE_QUICK_REF.md](CLEARANCE_QUICK_REF.md) for complete voltage tables

### Marker Appearance

Customize visual markers in `[general]` section:

```toml
[general]
marker_layer = "Cmts.User"       # Layer for markers
marker_circle_radius_mm = 0.8    # Circle size
marker_line_width_mm = 0.1       # Line thickness
marker_text_offset_mm = 1.2      # Text position offset
marker_text_size_mm = 0.5        # Text height
```

### Enable/Disable Rules

Set `enabled = false` to disable specific rule categories:

```toml
[via_stitching]
enabled = false  # Skip via stitching checks

[decoupling]
enabled = true   # Keep decoupling checks active
```

## Adding New Rules

The plugin architecture supports easy addition of new EMC verification rules.

### Step 1: Add Configuration Section

Add new rule configuration to `emc_rules.toml`:

```toml
[trace_width]
enabled = true
description = "Verifies minimum trace widths for high-current nets"
power_trace_min_width_mm = 0.5
power_net_patterns = ["VCC", "VDD", "PWR"]
violation_message = "TRACE TOO NARROW"
```

### Step 2: Implement Check Function

Add new method to `emc_auditor_plugin.py`:

```python
def check_trace_width(self, board, marker_layer, config):
    """Check minimum trace width for power nets"""
    min_width = pcbnew.FromMM(config.get('power_trace_min_width_mm', 0.5))
    power_patterns = [p.upper() for p in config.get('power_net_patterns', [])]
    violation_msg = config.get('violation_message', 'TRACE TOO NARROW')
    
    violations = 0
    for track in board.GetTracks():
        if isinstance(track, pcbnew.PCB_TRACK):
            net_name = track.GetNetname().upper()
            if any(pat in net_name for pat in power_patterns):
                if track.GetWidth() < min_width:
                    self.draw_error_marker(
                        board, 
                        track.GetStart(), 
                        violation_msg, 
                        marker_layer
                    )
                    violations += 1
    
    return violations
```

### Step 3: Add to Run Method

Enable the new check in the `Run()` method:

```python
def Run(self):
    # ... existing code ...
    
    # 3. Trace Width Verification (if enabled)
    trace_cfg = self.config.get('trace_width', {})
    if trace_cfg.get('enabled', False):
        violations_found += self.check_trace_width(board, marker_layer, trace_cfg)
```

## Future Rule Examples

The TOML configuration includes commented templates for:

- **Trace Width Rules** - Verify minimum widths for power traces
- **Ground Plane Rules** - Check ground plane coverage and gaps
- **Differential Pair Rules** - Verify length matching and impedance
- **High-Speed Signal Rules** - Check stub lengths and bend radius
- **EMI Filtering Rules** - Ensure filters on interfaces

To activate these rules:
1. Implement the check function (similar to Step 2 above)
2. Set `enabled = true` in the TOML file
3. Customize parameters for your design requirements

## Troubleshooting

### "No TOML library found" Error

Install TOML parser:
```bash
pip install tomli  # Recommended for Python < 3.11
# or
pip install toml   # Alternative
```

### Icon Not Showing

1. Verify `emc_icon.svg` is in the same directory as the plugin
2. Check file permissions (must be readable)
3. Restart KiCad after fixing

### Config Not Loading

1. Check `emc_rules.toml` syntax (use a TOML validator)
2. Ensure file is in the same directory as the plugin
3. Check KiCad console for error messages
4. Plugin will fall back to default values if config fails

### Markers Not Appearing

1. Enable the **User.Comments** layer in Layer Manager
2. Check if violations actually exist (console shows count)
3. Try clicking "View → Redraw" (F5) to refresh

## Technical Details

### PCB Layers Used

- **User.Comments (Cmts.User)** - Default marker layer (configurable)

### Python Dependencies

- `pcbnew` - KiCad Python API (built-in)
- `math` - Standard library
- `os` - Standard library
- `tomllib` / `tomli` / `toml` - TOML configuration parsing

### Performance

- Typical analysis time: 1-5 seconds for medium boards (500-2000 components)
- Scales linearly with component count
- Via checks: O(n²) for critical vias vs GND vias
- Decoupling checks: O(n×m) for ICs vs capacitors

## PCB Manufacturing DRC Files

This repository includes manufacturer-specific Design Rule Check (DRC) files to ensure your PCB design meets fabrication capabilities and requirements.

### JLCPCB Directory

**JLCPCB** is a leading Chinese PCB manufacturer offering fast turnaround and low-cost prototyping services. The `JLCPCB/` directory contains:

- **[JLCPCB.kicad_dru](JLCPCB/JLCPCB.kicad_dru)** - Design rules matching JLCPCB capabilities:
  - **Minimum track width**: 0.127mm (5 mil) for standard service
  - **Minimum spacing**: 0.127mm (5 mil) between copper features
  - **Minimum drill size**: 0.3mm for through-holes, 0.15mm for vias
  - **Solder mask expansion**: 0.05mm default
  - **Silkscreen clearance**: 0.15mm from pads and edges
  - **Board thickness**: 1.6mm standard (0.4-3.2mm available)
  - **Copper weight**: 1oz (35µm) standard, 2oz available
  - **Surface finish**: HASL, ENIG, OSP options
  
  **Use case**: Apply before ordering from JLCPCB to catch violations early  
  **How to use**: Tools → Design Rules Checker → Load Custom Rules → Select `JLCPCB.kicad_dru`

### PCBWAY Directory

**PCBWay** is a global PCB manufacturer offering advanced capabilities including HDI, rigid-flex, and metal-core PCBs. The `PCBWAY/` directory contains:

- **[PCBWay.kicad_dru](PCBWAY/PCBWay.kicad_dru)** - Design rules matching PCBWay capabilities:
  - **Minimum track width**: 0.1mm (4 mil) for standard service, 0.075mm (3 mil) for advanced
  - **Minimum spacing**: 0.1mm (4 mil) standard, tighter for HDI builds
  - **Minimum drill size**: 0.25mm for through-holes, 0.15mm for vias
  - **Via-in-pad support**: Available for BGA fanout
  - **Impedance control**: ±10% tolerance for controlled impedance traces
  - **Board stackup**: 2-32 layers supported
  - **Special materials**: Rogers, Taconic, aluminum-backed available
  - **Surface finish**: Multiple options including ENIG, immersion silver, hard gold
  
  **Use case**: Apply when designing complex boards with tight tolerances  
  **How to use**: Tools → Design Rules Checker → Load Custom Rules → Select `PCBWay.kicad_dru`

### EMC_DRC.kicad_dru (Root Level)

Custom DRC file for **EMC-specific checks** beyond standard manufacturing rules:
- High-speed signal routing requirements
- Return path verification for critical nets
- Antenna rule checks for RF designs
- ESD protection path validation

**Integration**: This file complements the EMC Auditor plugin by providing native KiCad DRC checks for EMC compliance.

### Usage Recommendations

1. **Start with manufacturer DRC**: Apply JLCPCB or PCBWay rules first to ensure basic manufacturability
2. **Add EMC checks**: Load `EMC_DRC.kicad_dru` or run EMC Auditor plugin for compliance verification
3. **Iterate**: Fix violations, re-check, verify with plugin markers on User.Comments layer
4. **Pre-order verification**: Always run manufacturer DRC before generating Gerber files

**Note**: Manufacturer capabilities may change. Always verify current specs on their websites:
- **JLCPCB**: https://jlcpcb.com/capabilities/pcb-capabilities
- **PCBWay**: https://www.pcbway.com/capabilities.html

## License

MIT License - See LICENSE file for details

## Support

For issues or feature requests, please open an issue on GitHub.

## Additional Documentation

- **[CLEARANCE_CREEPAGE_GUIDE.md](CLEARANCE_CREEPAGE_GUIDE.md)** - Complete IEC60664-1/IPC2221 implementation guide
  - Standard overview and concepts
  - Voltage domain identification
  - Distance calculation algorithms
  - Implementation pseudocode
  - Testing and validation procedures
  
- **[CLEARANCE_QUICK_REF.md](CLEARANCE_QUICK_REF.md)** - Quick reference card
  - Common voltage scenarios with exact values
  - Design rules and practical tips
  - Configuration examples
  - Verification checklist
  
- **[emc_rules_examples.toml](emc_rules_examples.toml)** - Additional rule templates
  - Antenna rule check
  - Keepout area verification
  - Thermal relief check
  - Silkscreen clearance
  - Power budget estimation

## Version History

### v1.4.0 (2026-02-13)
- **Clearance & Creepage checking IMPLEMENTED** - Full IEC60664-1 compliance
- Hybrid pathfinding algorithm:
  - Visibility graph + Dijkstra for <100 obstacles
  - Fast A* for dense boards (≥100 obstacles)
  - Spatial indexing for performance
- Clearance (air gap) and creepage (surface path) verification
- KiCad Net Classes support for voltage domain assignment
- Comprehensive configuration with 4 clearance + 12 creepage + 3 IPC2221 tables
- 6 voltage domains configured (MAINS, HV, LV, ELV, GND)
- Performance: 15-30 seconds for complex multi-voltage boards
- Tested on real boards: successfully found safety violations
- Documentation updated: Implementation details, algorithm descriptions

### v1.3.0 (2026-02-12)
- **Modular architecture refactoring** - Separated checkers into dedicated modules
- Main plugin reduced from 1172 to ~500 lines
- Added `via_stitching.py`, `decoupling.py`, `emi_filtering.py`, `clearance_creepage.py`
- Dependency injection pattern for utility functions
- Shared reporting across all modules
- Updated installation instructions for new module files
- Better code maintainability and extensibility

### v1.2.0 (2026-02-11)
- Differential topology enhancements for EMI filtering
- Complete filter chain tracing (common-mode + line filters)
- Compound filter types ("Differential + RC/LC")
- Fixed series/shunt detection for components
- Per-pad violation markers
- Enhanced topology reporting

### v1.1.0 (2026-02-10)
- Ground plane continuity checker improvements
- Performance optimization (5-10× faster)
- Progress dialog for long-running checks
- Polygon area filtering
- Via/pad clearance ignore zones

### v1.0.0 (2026-02-06)
- Initial release with TOML configuration
- Via stitching verification
- Decoupling capacitor proximity checks
- **Clearance and creepage rules (IEC60664-1 / IPC2221)**
  - Comprehensive voltage domain definitions
  - Reinforced insulation support for safety-critical circuits
  - Overvoltage category and pollution degree tables
  - Material group (CTI) specifications for FR4 and other materials
  - Altitude correction factors
- Custom EMC icon
- Extensible rule architecture
- Fixed `Frommm` → `FromMM` typo for KiCad 9.x compatibility

---

**See Also:**
- [emc_rules.toml](emc_rules.toml) - Rule configuration file
- [KiCad Plugin Documentation](https://docs.kicad.org/master/en/pcbnew/pcbnew.html#custom-plugins)
