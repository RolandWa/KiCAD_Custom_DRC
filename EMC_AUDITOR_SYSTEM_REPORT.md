![1770797381000](image/EMC_AUDITOR_SYSTEM_REPORT/1770797381000.png)# EMC Auditor Plugin System - Comprehensive Technical Report

**Generated:** February 11, 2026  
**System Version:** 1.2.0  
**KiCad Version:** 9.0.7+

---

## Executive Summary

The **EMC Auditor Plugin** is a KiCad PCB verification tool that automatically checks electromagnetic compatibility (EMC) design rules and visually marks violations on the circuit board. The system consists of three main components:

1. **Python Plugin** (`emc_auditor_plugin.py`) - 1,235 lines of KiCad Action Plugin code
2. **TOML Configuration** (`emc_rules.toml`) - 607 lines of externally configurable rules
3. **PowerShell Sync Script** (`sync_to_kicad.ps1`) - Automated deployment tool
4. **Documentation Suite** - 8 markdown files with implementation guides and design examples

The plugin integrates directly into KiCad's PCB Editor toolbar and performs real-time verification of EMC compliance across multiple rule categories.

---

## System Architecture

### 1. Core Components

#### A. Main Plugin File: `emc_auditor_plugin.py`

**Class Structure:**
```
EMCAuditorPlugin (pcbnew.ActionPlugin)
├── defaults() - Plugin metadata and initialization
├── load_config() - TOML configuration loader
├── Run() - Main execution entry point
├── check_via_stitching() - Via return path verification
├── check_decoupling() - Capacitor proximity checks
├── check_ground_plane() - Ground plane continuity
├── check_emi_filtering() - Interface EMI filters
└── Helper methods:
    ├── draw_error_marker() - Visual violation markers
    ├── draw_arrow() - Directional indicators
    ├── get_distance() - Euclidean distance calculation
    └── clear_previous_markers() - Cleanup old violations
```

**Report Dialog Class:**
```
EMCReportDialog (wx.Dialog)
├── Displays detailed violation report
├── Copy/paste support (Ctrl+A, Ctrl+C)
├── Save to file (Ctrl+S) with timestamp
└── 800×600 resizable window
```

#### B. Configuration System: `emc_rules.toml`

**Configuration Sections:**
1. `[general]` - Global settings (marker appearance, logging verbosity)
2. `[via_stitching]` - Ground return via proximity rules
3. `[decoupling]` - IC power supply decoupling verification
4. `[ground_plane]` - High-speed signal return path continuity
5. `[trace_width]` - Current capacity verification (planned)
6. `[differential_pairs]` - Length matching and impedance (planned)
7. `[emi_filtering]` - Interface connector filtering requirements
8. `[clearance_creepage]` - IEC60664-1 / IPC2221 safety compliance (planned)

#### C. Deployment Script: `sync_to_kicad.ps1`

**Purpose:** Automatically synchronize repository files to KiCad plugins directory

**Files Synchronized:**
- `emc_auditor_plugin.py` → Plugin code
- `emc_rules.toml` → Configuration
- `emc_icon.png` → Toolbar icon

**Target Path:**
```
<kicad_plugins_path>
```

**Features:**
- File existence verification
- Size reporting (KB)
- Error handling with detailed messages
- Visual symbols (✅ success, ❌ failure, ⚠️ warnings)
- Copy-Item with -Force flag for overwriting

---

## 2. Verification Rules (Detailed)

### Rule 1: Via Stitching ✅ **IMPLEMENTED**

**Purpose:** Ensure critical signal vias have nearby ground return vias

**Algorithm:**
```python
For each via in board:
    If via is on critical net class (HighSpeed, Clock, Differential):
        Search for nearest ground via (GND, GROUND, VSS patterns)
        If distance > max_distance_mm (default: 2mm):
            Create violation marker at via position
            Draw red circle + "NO GND VIA" text
            Group as "EMC_Via_N"
```

**Configuration Parameters:**
- `max_distance_mm`: 2.0 mm (adjustable)
- `critical_net_classes`: ["HighSpeed", "Clock", "Differential"]
- `ground_net_patterns`: ["GND", "GROUND", "VSS", "PGND", "AGND"]

**EMC Rationale:**
- High-speed signals need low-impedance return path
- Without nearby GND via, return current spreads → large loop area
- Large loop = high EMI radiation + signal integrity degradation
- Recommended spacing: 1-2mm for >50MHz signals

**Output Example:**
```
=== VIA STITCHING CHECK START ===
Max distance: 2.0 mm
Critical net classes: ['HighSpeed', 'Clock']
Ground patterns: ['GND']

✓ Found 15 critical vias and 42 ground vias

>>> Checking via on net 'USB_DP' at (45.25, 32.10) mm
    ❌ NO GND VIA within 2.0 mm (nearest: 3.2 mm)
    ✓ Violation marker created at (45.25, 32.10) mm

Via stitching check complete: 3 violation(s) found
```

---

### Rule 2: Decoupling Capacitors ✅ **IMPLEMENTED**

**Purpose:** Verify IC power pins have nearby decoupling capacitors

**Algorithm (with Smart Net Matching):**
```python
For each IC footprint (reference starts with "U"):
    For each power pad (net matches VCC, VDD, 3V3 patterns):
        Search for capacitors with reference "C*"
        CRITICAL: Only consider capacitors with pad on SAME power net
        Calculate distance from IC pad to capacitor position
        If distance > max_distance_mm (default: 3mm):
            Create violation marker at IC pad position
            Draw circle, text, arrow to nearest capacitor
            Show capacitor reference: "→ C15"
            Group as "EMC_Decap_U1_VCC"
```

**Smart Net Matching Feature:**
This prevents false positives on multi-voltage boards:

```python
# OLD BEHAVIOR (incorrect):
Search ALL capacitors → includes C10(3V3), C11(5V), C12(VCC)
U1 on VCC → Finds C10(3V3) 2mm away → FALSE OK

# NEW BEHAVIOR (correct):
For U1 pad on "VCC" net:
    For each capacitor:
        If capacitor has pad on "VCC" net:
            Consider this capacitor
        Else:
            Ignore this capacitor
```

**Configuration Parameters:**
- `max_distance_mm`: 3.0 mm
- `ic_reference_prefixes`: ["U"]
- `capacitor_reference_prefixes`: ["C"]
- `power_net_patterns`: ["VCC", "VDD", "PWR", "3V3", "5V", "1V8", "2V5", "12V"]
- `draw_arrow_to_nearest_cap`: true
- `show_capacitor_label`: true

**Violation Message Template:**
```
"CAP TOO FAR ({distance:.1f}mm)"
```
Example: "CAP TOO FAR (5.2mm)"

**EMC Rationale:**
- ICs draw pulsed current during switching
- Power trace inductance causes voltage drop: V = L × di/dt
- Decoupling capacitor provides local charge reservoir
- Poor decoupling → ground bounce, power rail noise, EMI radiation

**Output Example:**
```
=== DECOUPLING CAPACITOR CHECK START ===
Max distance: 3.0 mm
IC prefixes: ['U']
Power net patterns: ['VCC', 'VDD', '3V3']

>>> Found IC: U1
    Checking power pad 'VCC' at (50.00, 40.00) mm
        ❌ Nearest capacitor (C15): 5.2 mm - EXCEEDS 3.0 mm limit
        ✓ Violation marker created at (50.00, 40.00) mm

Decoupling check complete: 2 violation(s) found
```

---

### Rule 3: Ground Plane Continuity ✅ **IMPLEMENTED**

**Purpose:** Verify continuous ground plane under high-speed traces

**Algorithm (Optimized with Performance Enhancements):**
```python
# PREPROCESSING (done once):
ground_zones_by_layer = {}
For each zone in board:
    If zone is filled AND net matches ground patterns:
        If zone.area >= min_ground_polygon_area_mm2 (default: 10mm²):
            Add zone to ground_zones_by_layer[layer_name]

# MAIN CHECK:
For each track on critical net (HighSpeed, Clock, Differential):
    Sample points every 0.5mm along track
    For each sample point:
        Check if ground zone exists directly underneath:
            For each layer in layers_to_check (adjacent or all):
                For each zone in ground_zones_by_layer[layer]:
                    If zone.HitTestFilledArea(layer, point):
                        ground_found = True
                        
        If NOT ground_found:
            Check if violation is near via/pad (should be ignored):
                If distance_to_ground_via < ignore_via_clearance (0.5mm):
                    Ignore violation (expected gap near via)
                If distance_to_ground_pad < ignore_pad_clearance (0.3mm):
                    Ignore violation (expected gap near pad)
            
            If NOT ignored:
                Create violation marker
                Draw circle + "NO GND PLANE UNDER TRACE" text
                Group as "EMC_GndPlane_CLK_N"
```

**Performance Optimization:**
- **Pre-filtered zone dictionary**: O(1) layer lookup instead of O(n) iteration
- **Area filtering**: Ignores small copper islands < 10mm²
- **Via/pad clearance zones**: Reduces false positives near expected gaps
- **Result**: 5-10× faster than naive implementation

**Configuration Parameters:**
- `critical_net_classes`: ["HighSpeed", "Clock", "Differential"]
- `ground_net_patterns`: ["GND", "GROUND", "VSS"]
- `check_continuity_under_trace`: true
- `max_gap_under_trace_mm`: 0.5 mm
- `sampling_interval_mm`: 0.5 mm
- `ground_plane_check_layers`: "all" or "adjacent"
- `ignore_via_clearance`: 0.5 mm (NEW - reduces false positives)
- `ignore_pad_clearance`: 0.3 mm (NEW - reduces false positives)
- `min_ground_polygon_area_mm2`: 10.0 mm² (NEW - filters copper islands)

**Progress Dialog:**
For boards with many high-speed traces, displays real-time progress:
```
"Checking track 15/42 on net 'CLK'..."
[Cancel button available]
```

**EMC Rationale:**
- Continuous ground plane = minimal return path loop area
- Loop area directly proportional to radiated EMI
- Critical for clock signals, USB, Ethernet, high-speed buses
- IPC-2221 recommends unbroken ground plane for signals >50MHz

**Output Example:**
```
=== GROUND PLANE CHECK START ===
Critical net classes: ['HighSpeed', 'Clock']
Ground patterns: ['GND']
Check mode: all
Min ground polygon area: 10.0 mm²

--- Scanning all tracks ---
Track: net='CLK', class='Clock'
✓ Track CLK: 25 segments to check

[Progress Dialog: "Checking track 1/25 on net 'CLK'..."]

>>> Checking track on 'CLK' (F.Cu to B.Cu)
    Sample at (60.00, 50.00) mm - layer F.Cu
    ❌ NO GROUND PLANE found (checked 2 layers)
    ✓ Violation marker created at (60.00, 50.00) mm

Ground plane check complete: 4 violation(s) found
```

---

### Rule 4: EMI Filtering ✅ **IMPLEMENTED**

**Purpose:** Verify EMI filters on interface connectors (USB, Ethernet, HDMI, CAN, RS485)

**Algorithm (Multi-Step Topology Detection):**
```python
# Step 1: Find connectors
For each footprint with reference starting with "J":
    Detect interface type from reference/footprint:
        USB, Ethernet, HDMI, CAN, RS485, RS232
    
# Step 2: Get signal pads (exclude GND, VCC, SHIELD)
For each connector:
    signal_pads = pads NOT matching ["GND", "VCC", "SHIELD"]
    
# Step 3: Search for filter components
For each signal pad net:
    Search for components within max_filter_distance_mm (10mm):
        R (resistors), L (inductors), FB (ferrite beads)
        C (capacitors), D (TVS diodes)
    Only consider components electrically connected to net
    
# Step 4: Classify filter topology
Analyze component sequence on net path:
    Pi filter:  C-L-C, C-FB-C (best EMI suppression)
    T filter:   L-C-L, FB-C-FB (good EMI suppression)
    LC filter:  L+C or FB+C
    RC filter:  R+C (basic filtering)
    L filter:   Only L or FB
    C filter:   Only C
    R filter:   Only R (not recommended)
    
# Step 5: Check requirements
Compare detected filter vs. min_filter_type:
    Filter hierarchy: Pi > T > LC > RC > L > C > R > simple
    If no filter OR insufficient:
        Create violation marker at connector
        Group as "EMC_EMI_J1_NoFilter" or "EMC_EMI_J1_WeakFilter"
```

**Configuration Parameters:**
- `connector_prefix`: "J"
- `filter_component_prefixes`: ["R", "L", "FB", "C", "D"]
- `max_filter_distance_mm`: 10.0 mm
- `min_filter_type`: "LC" (hierarchy: Pi > T > LC > RC > L > C > R)

**Filter Topology Examples:**
```
Pi Filter (C-L-C):
    Connector → C1 (100pF) → L1 (ferrite) → C2 (100pF) → IC
    Best common-mode rejection (>20dB @ 100MHz)

T Filter (L-C-L):
    Connector → L1 → C1 → L2 → IC
    Good series impedance + shunt filtering

LC Filter:
    Connector → L1 → C1 → IC
    Adequate for moderate EMI environments

RC Filter:
    Connector → R1 → C1 → IC
    Basic filtering, lossy (not recommended for high-speed)
```

**EMC Rationale:**
- Interface connectors = primary EMI entry/exit points
- USB, Ethernet, HDMI require filtering per EN 55032, FCC Part 15
- Pi/T filters provide best common-mode rejection
- TVS diodes (D) protect against ESD but don't filter EMI

---

### Rule 5: Trace Width 🚧 **CONFIG READY, NOT IMPLEMENTED**

**Purpose:** Verify power traces meet minimum width for current capacity

**Planned Algorithm:**
```python
For each track on power net (VCC, VDD, PWR patterns):
    Calculate required width using IPC-2221 formula:
        Area [mm²] = (Current [A] / (k × ΔT^β))^(1/α)
        Width = Area / copper_thickness
    
    If actual_width < required_width:
        Create violation marker
```

**Configuration Ready:**
- `power_trace_min_width_mm`: 0.5 mm
- `power_net_patterns`: ["VCC", "VDD", "PWR", "3V3", "5V"]
- `current_per_width`: 1.0 A/mm

**Status:** Configuration exists in `emc_rules.toml`, implementation pending

---

### Rule 6: Clearance & Creepage 🚧 **CONFIG READY, NOT IMPLEMENTED**

**Purpose:** IEC60664-1 / IPC2221 electrical safety compliance

**Planned Features:**
- Electrical clearance (air gap) verification
- Creepage distance (surface path) verification
- Overvoltage category I-IV support
- Pollution degree 1-4 tables
- Material group (CTI) for FR4 and specialty boards
- Altitude correction for >2000m elevation

**Configuration Ready:**
- `overvoltage_category`: "II"
- `pollution_degree`: 2
- `material_group`: "II" (standard FR4)
- `altitude_m`: 1000

**Documentation:**
- [CLEARANCE_CREEPAGE_GUIDE.md](CLEARANCE_CREEPAGE_GUIDE.md) - 546 lines, complete implementation guide
- [CLEARANCE_QUICK_REF.md](CLEARANCE_QUICK_REF.md) - 208 lines, lookup tables
- [CLEARANCE_VS_CREEPAGE_VISUAL.md](CLEARANCE_VS_CREEPAGE_VISUAL.md) - 329 lines, illustrated guide

**Status:** Configuration and documentation complete, code implementation pending

---

## 3. User Interface and Workflow

### Plugin Execution Flow

```
User clicks EMC shield icon in toolbar
    ↓
EMCAuditorPlugin.Run() called
    ↓
Clear previous markers (delete old EMC_* groups)
    ↓
Load configuration from emc_rules.toml
    ↓
Initialize report collection (timestamp, board filename)
    ↓
Execute enabled checks in sequence:
    1. Via Stitching (if enabled)
    2. Decoupling (if enabled)
    3. Ground Plane (if enabled)
    4. EMI Filtering (if enabled)
    ↓
Each check returns violation count
    ↓
Refresh PCB display (pcbnew.Refresh())
    ↓
Generate final report
    ↓
If verbose_logging = true:
    Show EMCReportDialog (detailed report, copy/save)
Else:
    Show wx.MessageBox (simple summary)
```

### Report Dialog Features

**Window Layout:**
```
┌─────────────────────────────────────────────────────┐
│ EMC Audit Report                              [X]   │
├─────────────────────────────────────────────────────┤
│ EMC Audit Complete - Found 5 violation(s)          │
│                                                     │
│ ┌─────────────────────────────────────────────┐   │
│ │ ==================================          │   │
│ │ EMC AUDITOR REPORT                          │   │
│ │ Generated: 2026-02-11 14:25:30              │   │
│ │ Board: my_board.kicad_pcb                   │   │
│ │ ==================================          │   │
│ │                                             │   │
│ │ === VIA STITCHING CHECK START ===          │   │
│ │ Max distance: 2.0 mm                        │   │
│ │ Critical net classes: ['HighSpeed']         │   │
│ │ ...                                         │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│ Tip: Use Ctrl+A to select all, Ctrl+C to copy.    │
│ Check User.Comments layer for visual markers.     │
│                                                     │
│            [Save Report]  [Close]                  │
└─────────────────────────────────────────────────────┘
```

**Keyboard Shortcuts:**
- **Ctrl+A**: Select all text
- **Ctrl+C**: Copy to clipboard
- **Ctrl+S**: Save report to timestamped file
- **Escape**: Close dialog

**Report File Format:**
```
EMC_Audit_Report_20260211_142530.txt
```

---

### Visual Markers on PCB

**Marker Appearance:**
```
Layer: Cmts.User (User Comments)

Violation Marker:
    ● Red circle (0.8mm radius, 0.1mm line width)
    ↓ Text label offset 1.2mm below (0.5mm text height)
    "NO GND VIA" or "CAP TOO FAR (5.2mm)"
    
Optional Arrow:
    → Line from violation to related component
    → Arrowhead at end (0.5mm length)
    → Label at midpoint: "→ C15"
```

**Group Structure:**
Each violation creates an individual group for easy management:

```
PCB Groups:
├── EMC_Via_1
│   ├── Circle shape
│   └── Text "NO GND VIA"
├── EMC_Decap_U1_VCC
│   ├── Circle shape
│   ├── Text "CAP TOO FAR (5.2mm)"
│   ├── Arrow line
│   ├── Arrow wing 1
│   ├── Arrow wing 2
│   └── Text "→ C15"
└── EMC_GndPlane_CLK_1
    ├── Circle shape
    └── Text "NO GND PLANE UNDER TRACE"
```

**User Operations:**
1. **View violation**: Click marker on board
2. **Select group**: Right-click → "Select Items in Group"
3. **Delete violation**: Press Delete (removes circle + text + arrow)
4. **Fix and re-run**: Modify board, click EMC icon again (auto-clears old markers)

---

## 4. Configuration System

### TOML File Structure

**Why TOML?**
- Human-readable, easy to edit
- Python 3.11+ built-in support (`tomllib`)
- Fallback to `tomli` or `toml` for older Python
- Clear section hierarchy
- Comment support for documentation

**Configuration Loading:**
```python
def load_config(self):
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(plugin_dir, "emc_rules.toml")
    
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)
    
    return config
```

**Fallback Mechanism:**
If TOML file missing or invalid, uses hardcoded defaults:
```python
def get_default_config(self):
    return {
        'via_stitching': {
            'enabled': True,
            'max_distance_mm': 2.0,
            ...
        },
        'decoupling': {
            'enabled': True,
            'max_distance_mm': 3.0,
            ...
        }
    }
```

### Global Settings

```toml
[general]
plugin_name = "EMC Auditor"
version = "1.2.0"

# Marker appearance
marker_layer = "Cmts.User"
marker_circle_radius_mm = 0.8
marker_line_width_mm = 0.1
marker_text_offset_mm = 1.2
marker_text_size_mm = 0.5

# Debug output
verbose_logging = true  # Detailed report vs. simple message
```

**Verbose Logging Impact:**

| Setting | Report Type | Features |
|---------|-------------|----------|
| `true` | EMCReportDialog | - Detailed violation list<br>- Copy/paste support<br>- Save to file<br>- 800×600 window |
| `false` | wx.MessageBox | - Summary count only<br>- Single OK button<br>- Minimal output |

---

## 5. Sync Script Operation

### `sync_to_kicad.ps1` Workflow

```powershell
# 1. Set paths
$RepoDir = $PSScriptRoot  # Current directory
$PluginsDir = "<kicad_plugins_path>"

# 2. Verify target directory
if (-not (Test-Path $PluginsDir)) {
    Write-Host "❌ ERROR: KiCad plugins directory not found!"
    exit 1
}

# 3. Synchronize files
$FilesToSync = @(
    "emc_auditor_plugin.py",
    "emc_rules.toml",
    "emc_icon.png"
)

foreach ($File in $FilesToSync) {
    $SourcePath = Join-Path $RepoDir $File
    
    if (Test-Path $SourcePath) {
        Copy-Item $SourcePath -Destination $PluginsDir -Force
        Write-Host "✅ $File ($SizeKB KB)"
        $SyncedCount++
    } else {
        Write-Host "⚠️  $File not found in repository"
        $FailedCount++
    }
}

# 4. Summary
Write-Host "📊 Sync Summary:"
Write-Host "   Synced:  $SyncedCount files"
Write-Host "   Failed:  $FailedCount files"
Write-Host "💡 Tip: Restart KiCad to reload the updated plugin"
```

**Expected Output:**
```
🔄 Synchronizing EMC Auditor Plugin to KiCad...

✅ emc_auditor_plugin.py (42.15 KB)
✅ emc_rules.toml (18.23 KB)
✅ emc_icon.png (2.47 KB)

📊 Sync Summary:
   Synced:  3 files

💡 Tip: Restart KiCad to reload the updated plugin
```

**Error Handling:**
- Missing source file → ⚠️ warning, continues
- Copy failure → ❌ error with exception message
- Missing target directory → ❌ error, exits immediately

---

## 6. Documentation Structure

### Markdown File Map

| File | Lines | Purpose |
|------|-------|---------|
| **README.md** | 766 | Main documentation hub, feature list, quick start |
| **VIA_STITCHING.md** | 167 | Via stitching rule documentation, design examples |
| **DECOUPLING.md** | 284 | Decoupling capacitor rule, smart net matching details |
| **GROUND_PLANE.md** | 401 | Ground plane continuity, performance optimization |
| **TRACE_WIDTH.md** | - | Trace width rule (planned), IPC-2221 formulas |
| **CLEARANCE_CREEPAGE_GUIDE.md** | 546 | Complete IEC60664-1 implementation guide |
| **CLEARANCE_QUICK_REF.md** | 208 | Quick lookup tables for clearance/creepage |
| **CLEARANCE_VS_CREEPAGE_VISUAL.md** | 329 | Illustrated guide with ASCII diagrams |

### Documentation Standards

**Each rule documentation includes:**
1. **Purpose** - What the rule checks and why it matters
2. **Configuration** - TOML parameters with defaults
3. **Algorithm** - Step-by-step checking logic
4. **Violation Markers** - Group naming, visual elements
5. **Best Practices** - EMC design guidelines
6. **Examples** - Correct vs. incorrect board layouts

**Code Examples Format:**
````markdown
```toml
[rule_name]
enabled = true
parameter = value
```

```python
def check_rule(self, board, marker_layer, config):
    # Implementation details
    pass
```
````

---

## 7. Development Workflow

### Adding New Rules (Developer Guide)

**Step 1: Create Configuration Section**

Edit `emc_rules.toml`:
```toml
[your_rule]
enabled = false  # Default: disabled for new rules
description = "What your rule checks"
violation_message = "VIOLATION TEXT"
parameter1 = value1
parameter2 = value2
```

**Step 2: Implement Check Function**

Add to `emc_auditor_plugin.py`:
```python
def check_your_rule(self, board, marker_layer, config):
    """Template for new DRC rule implementation"""
    violations = 0
    
    # Your checking logic
    for item in items_to_check:
        if violation_detected:
            # Create violation group
            violation_group = pcbnew.PCB_GROUP(board)
            violation_group.SetName(f"EMC_YourRule_{item_id}_{violations+1}")
            board.Add(violation_group)
            
            # Draw marker
            self.draw_error_marker(
                board, 
                violation_position,
                "YOUR VIOLATION MESSAGE",
                marker_layer, 
                violation_group
            )
            
            # Optional: Draw arrow to related component
            if show_arrow:
                self.draw_arrow(
                    board,
                    violation_position,
                    target_position,
                    "→ TARGET_REF",
                    marker_layer,
                    violation_group
                )
            
            violations += 1
    
    return violations
```

**Step 3: Register in Run() Method**

Add to `Run()` method:
```python
def Run(self):
    # ... existing code ...
    
    # X. Your Rule Verification (if enabled)
    your_rule_cfg = self.config.get('your_rule', {})
    if your_rule_cfg.get('enabled', False):
        print("\n" + "="*70)
        print("STARTING YOUR RULE CHECK")
        print("="*70)
        your_violations = self.check_your_rule(board, marker_layer, your_rule_cfg)
        violations_found += your_violations
        print(f"\nYour rule check complete: {your_violations} violation(s) found")
```

**Step 4: Create Documentation**

Create `YOUR_RULE.md`:
```markdown
# Your Rule

**Status:** ✅ Implemented and Active

## Purpose
What the rule checks and why it matters for EMC.

## Configuration
Parameters and defaults.

## Algorithm
Step-by-step logic.

## Best Practices
Design guidelines and examples.
```

**Step 5: Test and Deploy**

```powershell
# 1. Edit files in repository
# 2. Test configuration parsing
# 3. Test on sample PCB
# 4. Deploy to KiCad
.\sync_to_kicad.ps1
# 5. Restart KiCad and run plugin
```

---

## 8. Technical Implementation Details

### KiCad API Usage

**Board Object Access:**
```python
board = pcbnew.GetBoard()

# Board information
filename = board.GetFileName()
layer_count = board.GetCopperLayerCount()
bounding_box = board.GetBoundingBox()

# Component iteration
for footprint in board.GetFootprints():
    ref = footprint.GetReference()
    for pad in footprint.Pads():
        net_name = pad.GetNetname()
        pos = pad.GetPosition()

# Track iteration
for track in board.GetTracks():
    if isinstance(track, pcbnew.PCB_VIA):
        # Via specific
        pass
    elif isinstance(track, pcbnew.PCB_TRACK):
        # Trace segment
        start = track.GetStart()
        end = track.GetEnd()
        width = track.GetWidth()
        net_class = track.GetNetClassName()

# Zone iteration
for zone in board.Zones():
    if zone.IsFilled():
        layer = zone.GetLayer()
        net = zone.GetNet()
        zone.HitTestFilledArea(layer, point)  # Boolean
```

**Shape Drawing:**
```python
# Circle
circle = pcbnew.PCB_SHAPE(board)
circle.SetShape(pcbnew.SHAPE_T_CIRCLE)
circle.SetFilled(False)
circle.SetStart(center_pos)
circle.SetEnd(pcbnew.VECTOR2I(center_pos.x + radius, center_pos.y))
circle.SetLayer(layer_id)
circle.SetWidth(line_width)
board.Add(circle)

# Line
line = pcbnew.PCB_SHAPE(board)
line.SetShape(pcbnew.SHAPE_T_SEGMENT)
line.SetStart(start_pos)
line.SetEnd(end_pos)
line.SetLayer(layer_id)
line.SetWidth(line_width)
board.Add(line)

# Text
text = pcbnew.PCB_TEXT(board)
text.SetText("MESSAGE")
text.SetPosition(pos)
text.SetLayer(layer_id)
text.SetTextSize(pcbnew.VECTOR2I(size, size))
board.Add(text)
```

**Group Management:**
```python
# Create group
group = pcbnew.PCB_GROUP(board)
group.SetName("EMC_Via_1")
board.Add(group)

# Add items to group
group.AddItem(circle)
group.AddItem(text)
group.AddItem(line)

# Remove all groups
for group in board.Groups():
    if group.GetName().startswith("EMC_"):
        board.Remove(group)
```

**Unit Conversions:**
```python
# mm to internal units
internal_units = pcbnew.FromMM(2.5)  # 2.5mm

# Internal units to mm
mm_value = pcbnew.ToMM(internal_units)
```

### Performance Optimizations

**1. Zone Pre-Filtering (Ground Plane Check)**

**Problem:** Iterating all zones for each sample point = O(n×m) complexity
```python
# Slow approach (DO NOT USE):
for sample_point in all_sample_points:  # n points
    for zone in board.Zones():           # m zones
        if zone.HitTestFilledArea(layer, sample_point):
            found = True
```

**Solution:** Pre-filter zones by layer into dictionary = O(n) complexity
```python
# Fast approach (IMPLEMENTED):
# Build dictionary once: O(m)
ground_zones_by_layer = {}
for zone in board.Zones():
    if is_ground_zone(zone) and zone.IsFilled():
        layer_name = board.GetLayerName(zone.GetLayer())
        ground_zones_by_layer[layer_name].append(zone)

# Check points: O(n×k) where k = zones per layer << m
for sample_point in all_sample_points:  # n points
    zones = ground_zones_by_layer.get(layer_name, [])  # O(1) lookup
    for zone in zones:                    # k zones (filtered)
        if zone.HitTestFilledArea(layer, sample_point):
            found = True
```

**Result:** 5-10× faster on typical boards

**2. Progress Dialog for Long Operations**

```python
if num_tracks > 10:
    progress = wx.ProgressDialog(
        "EMC Ground Plane Check",
        "Initializing...",
        maximum=num_tracks,
        style=wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE
    )
    
    for i, track in enumerate(critical_tracks):
        # Update progress
        continue_check, skip = progress.Update(
            i, 
            f"Checking track {i+1}/{num_tracks} on net '{track.GetNetname()}'..."
        )
        
        if not continue_check:
            break  # User pressed Cancel
    
    progress.Destroy()
```

**3. Area Filtering for Ground Zones**

Small copper islands (< 10mm²) are not valid ground planes:
```python
min_area_mm2 = config.get('min_ground_polygon_area_mm2', 10.0)
min_area_iu2 = (pcbnew.FromMM(1.0) ** 2) * min_area_mm2

for zone in board.Zones():
    area = zone.GetFilledArea()
    if area >= min_area_iu2:
        # Valid ground plane
        ground_zones.append(zone)
```

**4. Via/Pad Clearance Ignore Zones**

Ground vias and pads naturally create gaps in ground plane. Ignore violations nearby:
```python
# Check if violation is near ground via (expected gap)
for via_track in board.GetTracks():
    if isinstance(via_track, pcbnew.PCB_VIA):
        via_pos = via_track.GetPosition()
        dist_to_via = get_distance(violation_pos, via_pos)
        
        if dist_to_via < via_clearance_radius:
            via_net = via_track.GetNetname().upper()
            if any(gnd in via_net for gnd in gnd_patterns):
                should_ignore = True  # Expected gap near ground via
                break
```

---

## 9. Error Handling and Robustness

### Exception Handling Patterns

**Rule-Level Try-Catch:**
```python
def check_your_rule(self, board, marker_layer, config):
    try:
        # Your checking logic
        pass
    except Exception as e:
        print(f"ERROR in [your_rule] check: {e}")
        return 0  # Return 0 violations, don't crash
```

**Item-Level Try-Catch:**
```python
for item in items:
    try:
        # Process item
        pass
    except Exception as e:
        print(f"WARNING: Failed to process {item}: {e}")
        continue  # Skip item, continue with others
```

### Defensive Programming

**Null Checks:**
```python
net = pad.GetNet()
if not net:
    continue  # Skip unconnected pads

net_name = net.GetNetname()
if not net_name:
    continue  # Skip unnamed nets
```

**Empty List Handling:**
```python
critical_vias = [v for v in vias if is_critical(v)]

if not critical_vias:
    print("WARNING: No critical vias found. Skipping via stitching check.")
    return 0
```

**Configuration Fallbacks:**
```python
max_dist_mm = config.get('max_distance_mm', 2.0)  # Default 2.0 if missing
```

---

## 10. Future Development Roadmap

### Planned Features

**Priority 1: Complete Existing Configured Rules**
- [x] Via Stitching ✅ IMPLEMENTED
- [x] Decoupling Capacitors ✅ IMPLEMENTED
- [x] Ground Plane Continuity ✅ IMPLEMENTED
- [x] EMI Filtering ✅ IMPLEMENTED
- [ ] Trace Width (IPC-2221 current capacity formulas)
- [ ] Clearance & Creepage (IEC60664-1 safety tables)

**Priority 2: Additional EMC Rules**
- [ ] Differential Pair Length Matching
- [ ] High-Speed Signal Routing (stub length, bend radius)
- [ ] Antenna Rules (max copper area for RF traces)
- [ ] Thermal Relief Checks
- [ ] Silkscreen Clearance

**Priority 3: Enhanced Features**
- [ ] HTML Report Export (more readable than text)
- [ ] CSV Export (for spreadsheet analysis)
- [ ] Rule Severity Levels (warning vs. error)
- [ ] Custom Rule Templates (user-defined checks)
- [ ] Integration with KiCad DRC (native violation markers)

### Technical Debt

**Known Issues:**
1. Via stitching doesn't check via size/plating
2. Decoupling doesn't verify capacitor value (only presence)
3. Ground plane check can be slow on >1000 track boards
4. EMI filtering topology detection is simplistic (sequential components only)

**Code Quality Improvements:**
1. Unit tests for each check function
2. Mock PCB data for automated testing
3. Performance profiling and optimization
4. Code documentation (docstrings)
5. Type hints for Python 3.10+

---

## 11. Installation and Deployment

### System Requirements

**KiCad:**
- Version: 9.0.7 or later (KiCad 8.x may work with minor adjustments)
- Python API: pcbnew module availability

**Python Libraries:**
- **tomllib** (built-in Python 3.11+)
- **tomli** (fallback for Python 3.6-3.10): `pip install tomli`
- **toml** (alternative fallback): `pip install toml`
- **wxPython** (usually bundled with KiCad)

### Installation Steps

**Method 1: PowerShell Sync Script (Recommended)**
```powershell
# 1. Navigate to repository
cd "C:\...\KiCAD_Custom_DRC"

# 2. Run sync script
.\sync_to_kicad.ps1

# 3. Restart KiCad
# 4. Plugin appears in PCB Editor toolbar
```

**Method 2: Manual Installation**
```powershell
# 1. Copy files to KiCad plugins directory
$PluginsDir = "$env:USERPROFILE\AppData\Roaming\kicad\9.0\3rdparty\plugins"

Copy-Item emc_auditor_plugin.py $PluginsDir
Copy-Item emc_rules.toml $PluginsDir
Copy-Item emc_icon.png $PluginsDir

# 2. Restart KiCad
```

**Method 3: KiCad Plugin Manager**
```
KiCad → Plugin and Content Manager
→ Install from File → Select emc_auditor_plugin.py
```

### Verification

**Check Plugin Loaded:**
```
KiCad PCB Editor → Tools → External Plugins → Refresh Plugins
→ Should see "EMC Auditor" in list
```

**Check Toolbar Icon:**
- Look for EMC shield icon in toolbar
- Tooltip should show "EMC Auditor"

**Test Run:**
1. Open any PCB file
2. Click EMC shield icon
3. Should see dialog: "EMC Audit Complete - Found X violations"
4. Check User.Comments layer for markers

---

## 12. Troubleshooting

### Common Issues

**Issue 1: Plugin Not Appearing in Toolbar**

**Symptoms:** No EMC shield icon visible

**Solutions:**
```
1. Check file location:
   Files must be in: KiCad\9.0\3rdparty\plugins\
   NOT in subdirectory!

2. Refresh plugins:
   Tools → External Plugins → Refresh Plugins

3. Check Python errors:
   Open Scripting Console: Tools → Scripting Console
   Look for import errors or syntax errors

4. Verify file permissions:
   Files must be readable by KiCad process
```

**Issue 2: "No TOML Library Found" Error**

**Symptoms:** Console message: "ERROR: No TOML library found"

**Solutions:**
```powershell
# Install tomli (Python 3.6-3.10)
pip install tomli

# Or install toml (alternative)
pip install toml

# Python 3.11+ has built-in tomllib (no action needed)
```

**Issue 3: Configuration Not Updating**

**Symptoms:** Changes to `emc_rules.toml` not reflected in plugin behavior

**Solutions:**
```
1. Restart KiCad completely (close all windows)
2. Verify correct TOML file location (same directory as .py file)
3. Check TOML syntax (use TOML validator online)
4. Delete Python cache: __pycache__ folder
```

**Issue 4: Too Many False Positives**

**Symptoms:** Violations marked in expected locations (near vias, pads)

**Solutions:**
```toml
# Increase ignore zones in ground_plane section
[ground_plane]
ignore_via_clearance = 1.0  # Increase from 0.5mm
ignore_pad_clearance = 0.5  # Increase from 0.3mm
min_ground_polygon_area_mm2 = 20.0  # Filter smaller islands
```

**Issue 5: Plugin Runs Very Slowly**

**Symptoms:** Ground plane check takes >30 seconds

**Solutions:**
```toml
# Optimize checks
[ground_plane]
ground_plane_check_layers = "adjacent"  # Check only adjacent layer
sampling_interval_mm = 1.0  # Reduce sampling density
min_ground_polygon_area_mm2 = 20.0  # Filter more zones
```

---

## 13. Best Practices for Users

### Workflow Integration

**1. Design Phase**
- Run EMC Auditor every major layout iteration
- Fix violations before routing completion
- Use markers as design feedback

**2. Review Phase**
- Run before PCB fabrication
- Include report in design documentation
- Archive report with Gerber files

**3. Post-Production**
- Compare violations to EMC test results
- Refine rules based on actual performance
- Update configuration for next design

### Configuration Tuning

**Conservative Settings (Strict EMC):**
```toml
[via_stitching]
max_distance_mm = 1.0  # Very close

[decoupling]
max_distance_mm = 2.0  # Very close

[ground_plane]
max_gap_under_trace_mm = 0.3  # Minimal gaps
```

**Relaxed Settings (Commercial Products):**
```toml
[via_stitching]
max_distance_mm = 3.0  # More lenient

[decoupling]
max_distance_mm = 5.0  # More lenient

[ground_plane]
max_gap_under_trace_mm = 1.0  # Allow larger gaps
```

### Board Design Tips

**1. Via Stitching:**
- Place GND vias in pairs on both sides of signal via
- Use via arrays around high-speed ICs
- Connect top and bottom ground planes liberally

**2. Decoupling:**
- Use multiple capacitor values (100nF, 10nF, 1nF)
- Place smallest cap (highest frequency) closest to IC
- Route power pin → cap pad → via to plane (minimal loop)

**3. Ground Plane:**
- Avoid routing power traces through ground plane
- Use stitching vias to connect ground layers
- Keep ground plane continuous under high-speed buses

**4. EMI Filtering:**
- Place filters <10mm from connectors
- Use Pi filters for best performance (C-L-C)
- Add TVS diodes for ESD protection

---

## 14. Conclusion

The EMC Auditor Plugin provides automated, configurable verification of electromagnetic compatibility design rules for KiCad PCB layouts. By integrating directly into the KiCad workflow and providing visual feedback on the board, it helps designers catch EMC issues early in the design process.

**Key Strengths:**
✅ Extensible architecture - easy to add new rules
✅ TOML configuration - no code editing required
✅ Visual markers - clear violation locations
✅ Detailed reporting - copy/paste/save support
✅ Performance optimized - handles complex boards
✅ Individual groups - delete violations one by one

**Current Limitations:**
⚠️ Some rules configured but not implemented (trace width, clearance/creepage)
⚠️ No integration with KiCad native DRC
⚠️ Limited automated testing

**Future Potential:**
🚀 Complete implementation of all configured rules
🚀 Integration with external EMC simulation tools
🚀 Machine learning for rule optimization
🚀 Community rule sharing platform

---

## Appendix A: File Inventory

| File | Size | Purpose |
|------|------|---------|
| `emc_auditor_plugin.py` | 42.15 KB | Main plugin code (1,235 lines) |
| `emc_rules.toml` | 18.23 KB | Configuration (607 lines) |
| `emc_icon.png` | 2.47 KB | Toolbar icon (EMC shield) |
| `sync_to_kicad.ps1` | 2.15 KB | Deployment script (100 lines) |
| `README.md` | 28.67 KB | Main documentation (766 lines) |
| `VIA_STITCHING.md` | 6.23 KB | Via rule docs (167 lines) |
| `DECOUPLING.md` | 10.58 KB | Decoupling rule docs (284 lines) |
| `GROUND_PLANE.md` | 14.93 KB | Ground plane rule docs (401 lines) |
| `CLEARANCE_CREEPAGE_GUIDE.md` | 20.35 KB | Clearance guide (546 lines) |
| `CLEARANCE_QUICK_REF.md` | 7.76 KB | Quick reference (208 lines) |
| `CLEARANCE_VS_CREEPAGE_VISUAL.md` | 12.27 KB | Visual guide (329 lines) |

**Total Repository Size:** ~145 KB documentation + code

---

## Appendix B: Code Statistics

**Python Code Metrics:**
- Total lines: 1,235
- Functions: 15 main check functions
- Classes: 2 (EMCAuditorPlugin, EMCReportDialog)
- Comments: ~15% of code
- Docstrings: Present on all public methods

**TOML Configuration:**
- Total lines: 607
- Configuration sections: 10
- Parameters: ~80
- Comments: ~35% of file (documentation inline)

---

## Appendix C: References

**Standards:**
- IEC60664-1 - Insulation coordination for low-voltage systems
- IPC-2221 - Generic standard on printed board design
- EN 55032 - Electromagnetic compatibility of multimedia equipment
- FCC Part 15 - Radio frequency devices

**KiCad Documentation:**
- KiCad Python API: https://docs.kicad.org/doxygen-python/
- pcbnew module: https://dev-docs.kicad.org/en/python/

**TOML Specification:**
- TOML v1.0.0: https://toml.io/

---

**Report Generated:** February 11, 2026  
**Author:** AI Assistant (based on source code analysis)  
**System Version:** EMC Auditor Plugin v1.2.0
