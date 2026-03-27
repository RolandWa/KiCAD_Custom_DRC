# IEC60664-1 and IPC2221 Clearance/Creepage Implementation Guide

**Standards Reference:**
- **IEC60664-1**: Insulation coordination for equipment within low-voltage systems
- **IPC2221**: Generic Standard on Printed Board Design

**Status:** ✅ **FULLY IMPLEMENTED** (Version 3.0.0)  
**Implementation:** `clearance_creepage.py` (~2934 lines)  
**Algorithm:** Dijkstra Waypoint Graph with Bounding-Box Extremity Waypoints  
**Last Updated:** March 27, 2026

---

## Standard Overview

### IEC60664-1 - Insulation Coordination

**Purpose:** Defines minimum clearance and creepage distances for electrical insulation safety.

**Key Concepts:**

1. **Clearance** - Shortest distance through air between two conductive parts
   - Critical for preventing electrical arc/flashover
   - Affected by: voltage, overvoltage category, pollution degree, altitude

2. **Creepage** - Shortest distance along insulating surface between two conductive parts
   - Critical for preventing surface tracking/carbonization
   - Affected by: voltage, pollution degree, material CTI (Comparative Tracking Index)

3. **Overvoltage Categories:**
   - **Category I**: Protected electronics (computers, smartphones)
   - **Category II**: Appliances, tools, household equipment ⭐ MOST COMMON
   - **Category III**: Fixed installations, distribution panels
   - **Category IV**: Utility connection, overhead lines

4. **Pollution Degrees:**
   - **Degree 1**: Clean room, hermetically sealed
   - **Degree 2**: Normal indoor environment ⭐ MOST COMMON
   - **Degree 3**: Industrial environment, moisture/dust
   - **Degree 4**: Outdoor, continuous conductive pollution

5. **Material Groups (CTI):**
   - **Group I**: CTI ≥600 (ceramics, PTFE, polyimide)
   - **Group II**: CTI 400-599 (standard FR4) ⭐ MOST COMMON
   - **Group IIIa**: CTI 175-399 (phenolic, low-grade FR4)
   - **Group IIIb**: CTI 100-174 (poor insulators)

6. **Insulation Types:**
   - **Basic**: Single level of protection (most circuits)
   - **Supplementary**: Additional to basic (belt + suspenders)
   - **Reinforced**: Enhanced single level = basic + supplementary (SAFETY CRITICAL)

### IPC2221 - PCB Design Standard

**Purpose:** General PCB design requirements including conductor spacing.

**Key Differences from IEC60664-1:**
- More conservative for some voltage ranges
- Simpler tables (voltage-based only)
- Differentiates external vs internal layers
- Assumes coated (conformal coating) vs uncoated boards

**When to Use:**
- IEC60664-1: Safety-critical applications, CE/UL certification
- IPC2221: General electronics, non-safety circuits, manufacturability

---

## Voltage Domain Identification

### Step 1: Define Voltage Rails

Identify all power domains on your PCB:

```toml
[[clearance_creepage.voltage_domains]]
name = "MAINS_230V"
voltage_rms = 230          # RMS voltage for AC, absolute for DC
net_patterns = ["AC_L", "MAINS_L", "LINE", "L_"]
requires_reinforced_insulation = true  # Safety-critical
```

### Step 2: Map Nets to Domains

Plugin matches net names against patterns:
- Case-insensitive matching
- Substring search (e.g., "GND" matches "PGND", "AGND", "GND_ISO")
- Multiple patterns per domain

**Example Net Mapping:**
```
Net Name       → Matched Domain
"AC_L_IN"      → MAINS_L
"AC_N_OUT"     → MAINS_N
"HV_POS_400V"  → HIGH_VOLTAGE_DC
"+12V_MAIN"    → LOW_VOLTAGE_DC
"3V3_MCU"      → EXTRA_LOW_VOLTAGE
"GND_ISO"      → GROUND
```

### Step 3: Define Isolation Requirements

For critical domain pairs, specify exact requirements:

```toml
[[clearance_creepage.isolation_requirements]]
domain_a = "MAINS_L"
domain_b = "EXTRA_LOW_VOLTAGE"
isolation_type = "reinforced"
min_clearance_mm = 6.0    # IEC60664-1 Table F.1
min_creepage_mm = 8.0     # IEC60664-1 Table F.4 × reinforced factor
description = "Mains to SELV - Class II equipment"
```

---

## Distance Calculation Methods

### Clearance (Air Gap)

**3D Shortest Path Algorithm:**

```python
def calculate_clearance(pad_a, pad_b, board):
    """
    Calculate minimum 3D distance between two pads/traces.
    
    Must consider:
    - Pad edge to pad edge (not center to center)
    - Different layer heights (Z-axis)
    - Board thickness and stackup
    - Keepout zones, slots, cutouts
    """
    
    # 1. Get pad geometries (complex shapes require edge detection)
    poly_a = get_pad_polygon(pad_a)
    poly_b = get_pad_polygon(pad_b)
    
    # 2. Find closest edge points
    min_dist = float('inf')
    for point_a in poly_a.edges:
        for point_b in poly_b.edges:
            # Calculate 3D distance
            dx = point_a.x - point_b.x
            dy = point_a.y - point_b.y
            dz = get_layer_height(point_a.layer) - get_layer_height(point_b.layer)
            dist = math.sqrt(dx**2 + dy**2 + dz**2)
            
            if dist < min_dist:
                min_dist = dist
    
    return min_dist
```

**Considerations:**
- PCB vias create vertical "bridges" between layers
- Through-hole components span multiple layers
- Thermal reliefs and teardrops affect edge calculations
- Solder mask slightly increases clearance (~0.05mm)

### Creepage (Surface Path)

**Dijkstra Waypoint Graph Algorithm:**

The creepage path is measured along the PCB surface, routing around physical
slots/cutouts that break the surface path. The algorithm uses a Dijkstra-based
waypoint graph with bounding-box extremity waypoints placed at slot tips.

```python
def calculate_creepage(pad_a, pad_b, board):
    """
    Calculate minimum surface distance along PCB.
    
    Key design decisions:
    - Only slots/cutouts are barriers (pads/traces are surface features)
    - Edge.Cuts = board outline (boundary, no waypoints generated)
    - Internal .Cuts layers = isolation slots (waypoints at tips)
    - Waypoints placed at bbox extremities with 0.1mm offset
    - Dijkstra finds guaranteed shortest path on waypoint graph
    """
    
    # 1. Separate slot barriers into board outline vs internal slots
    edge_cuts = [obs for obs in obstacles if layer == 'Edge.Cuts']
    internal_slots = [obs for obs in obstacles if layer != 'Edge.Cuts']
    
    # 2. Generate waypoints at bounding-box extremities of each slot
    # 8 reference points per slot: 4 midpoints + 4 corners
    # Each expanded in 8 directions (cardinal + diagonal) at 0.1mm offset
    waypoints = get_slot_waypoints(internal_slots, boundary=edge_cuts)
    
    # 3. Build visibility graph: edge exists iff line doesn't cross any slot
    # O(N²) visibility checks where N = waypoints + start + goal
    graph = build_visibility_graph(start, goal, waypoints, all_slots)
    
    # 4. Dijkstra shortest path on the visibility graph
    path = dijkstra(graph, start, goal)
    
    return path.length  # or None if no path exists
```

**Special Cases:**

1. **Slots/Cutouts:**
   ```
   Pad A ----[  SLOT  ]---- Pad B
   
   Clearance: Measured across slot (air gap)
   Creepage: INFINITE (path broken, must go around board edge)
   ```

2. **Grooves (Routed Channels):**
   ```
   Pad A ----v GROOVE v---- Pad B
   
   Creepage: Distance down groove wall + across + up other wall
            = 2 × groove_depth + groove_width
   ```

3. **Different Layers:**
   ```
   Layer 1: Pad A --------|
                          | VIA
   Layer 2:              |----- Pad B
   
   Creepage: Surface path on Layer 1 + via barrel + Layer 2
   ```

---

## Lookup Table Interpolation

### Linear Interpolation for Voltages

When actual voltage falls between table entries:

```python
def interpolate_clearance(voltage_rms, table):
    """
    Linear interpolation between table values.
    
    Example table:
    100V → 1.0mm
    150V → 1.5mm
    
    Query: 125V
    Result: 1.25mm (halfway between)
    """
    
    # Find bracketing entries
    for i in range(len(table) - 1):
        v_low, d_low = table[i]
        v_high, d_high = table[i+1]
        
        if v_low <= voltage_rms <= v_high:
            # Linear interpolation
            ratio = (voltage_rms - v_low) / (v_high - v_low)
            distance = d_low + ratio * (d_high - d_low)
            return distance
    
    # Voltage above highest table entry
    if voltage_rms > table[-1][0]:
        print(f"WARNING: {voltage_rms}V exceeds table max")
        return table[-1][1]  # Use highest value
    
    return table[0][1]  # Use lowest value
```

### Reinforced Insulation Factor

**IEC60664-1 Requirements:**

- **Basic Insulation**: Use table value directly
- **Supplementary Insulation**: Use table value directly
- **Reinforced Insulation**: **DOUBLE the table value** (or use higher voltage category)

```python
if isolation_type == "reinforced":
    required_clearance *= 2.0
    required_creepage *= 2.0
```

**Example:**
- 230V AC, Basic Insulation: 2.5mm clearance
- 230V AC, Reinforced Insulation: **5.0mm clearance**

---

## Implementation Details

### Status: ✅ IMPLEMENTED (Version 3.0.0)

The clearance/creepage checker is **fully implemented** in `clearance_creepage.py` (~2934 lines).

### Architecture

**File:** `clearance_creepage.py`  
**Class:** `ClearanceCreepageChecker`  
**Algorithm:** Dijkstra waypoint graph with bbox extremity waypoints + A* fallback

### Key Components

1. **ObstacleSpatialIndex** - Grid-based spatial indexing
   - Reduces obstacle queries from O(N) to O(1) average case
   - Configurable cell size (default 5mm)
   - Dramatically improves performance on dense boards

2. **ClearanceCreepageChecker** - Main verification engine
   - Parses voltage domains from config (supports KiCad Net Classes + pattern matching)
   - Calculates clearance (2D air gap) between domain pairs
   - Calculates creepage (surface path) using Dijkstra waypoint graph
   - Draws violation markers with detailed messaging
   - Optional debug path visualization on marker layer

### Clearance Calculation (Air Gap)

**Method:** 2D Euclidean distance between pad edges

```python
# IEC 60664-1: measure from conductive EDGE, not pad centre
start = get_pad_edge_point(pad_a, toward=pad_b)
goal  = get_pad_edge_point(pad_b, toward=pad_a)
distance = math.sqrt((x2-x1)**2 + (y2-y1)**2)
```

**Notes:**
- Measures pad **edge-to-edge** (not center-to-center) per IEC 60664-1
- Uses `_get_pad_edge_point()` to find closest boundary point
- 2D distance (does not consider Z-axis/layer heights)

### Creepage Calculation (Surface Path)

**Primary Algorithm: Dijkstra Waypoint Graph**

The creepage pathfinder routes around physical slots/cutouts that break the PCB
surface. Only slots are barriers — pads, traces, and zones are surface features
the creepage path travels along (not around).

#### Step 1: Slot Barrier Separation

Slot barriers are separated into two categories:
- **Edge.Cuts** (layer ID 25) = Board outline boundary
  - Paths cannot cross the board edge
  - No waypoints generated (they'd be off-board)
- **Internal .Cuts layers** (e.g., GM1_2mm_slots.Cuts, layer ID 21) = Isolation slots
  - These are the obstacles the path must detour around
  - Waypoints are generated at their tips/corners

#### Step 2: Bounding-Box Extremity Waypoints

For each internal slot, waypoints are generated at **bounding-box extremities**:

```
  ┌──────────────────────────┐ ← slot bbox
  │  ×  ──────  ×  ──────  × │ ← top corners + midpoint
  │  │                     │  │
  │  ×        SLOT         ×  │ ← left/right midpoints
  │  │                     │  │
  │  ×  ──────  ×  ──────  × │ ← bottom corners + midpoint  
  └──────────────────────────┘
        8 reference points per slot
```

Each reference point is expanded in **8 directions** (cardinal + diagonal) with
**0.1mm offset** from the slot polygon, then filtered:
- Must not be inside any slot polygon
- Must not be outside the board boundary (Edge.Cuts)

This produces ~40-50 valid waypoints per slot (520 total for 11 slots).

**Why bbox extremities?** Slot polygons are rounded rectangles (line +
`TransformShapeToPolygon` 0.1mm buffer). Angle-based vertex extraction picks
mid-side vertices (where straight meets curve), missing the actual slot tips.
Bbox extremities always capture the true tip positions.

#### Step 3: Dijkstra on Visibility Graph

```
Nodes = {start, goal} ∪ all_waypoints
Edges = {(A, B) | straight line A→B doesn't cross ANY slot}
Weight = Euclidean distance
```

- **O(N²)** visibility checks where N = waypoints + 2
- Each check tests line segment against all slot polygons (including Edge.Cuts)
- Uses bbox fast-rejection + CCW segment-polygon intersection test
- Standard Dijkstra with priority queue finds guaranteed shortest path

**Typical performance:** 522 nodes, ~22K edges, ~136K visibility checks

#### Step 4: Fallback (Fast A*)

If Dijkstra fails (rare), a Fast A* with spatial grid index is available
for dense boards with 100+ obstacles.

#### Obstacle Detection

**Slot obstacles** = Physical board cutouts that break the surface path:
- Edge.Cuts segments (board outline)
- Internal .Cuts layer segments (isolation slots)
- Converted to polygons via `TransformShapeToPolygon(0.1mm buffer)`

**Other obstacles** (pads, tracks, zones) are tracked for spatial filtering
but do NOT block the creepage path — they are surface features.

**Spatial filtering** expands search box to cover all slot barriers

#### Multi-Layer Handling

Checks creepage **independently on each copper layer**:
- F.Cu (front copper)
- B.Cu (back copper)
- Inner layers (if configured)

Reports **shortest path across all layers**

Checks the **3 closest pad pairs** per domain pair for efficiency.

#### Debug Visualization

When `draw_creepage_path = true` in TOML config:
- Draws polyline showing the actual creepage path on the marker layer
- Shows distance label (actual vs required)
- Useful for verifying path correctness visually in KiCad

#### Special Cases

1. **No path found** - Board slot/cutout completely isolates domains
2. **Direct line-of-sight** - No slot crossing, returns straight distance
3. **Board outline only** - Path crosses Edge.Cuts but not internal slots

### Performance Characteristics

**Typical Runtime** (complex multi-voltage board):
- 6 voltage domains → up to 15 domain pairs to check
- 3-6 domain pairs have conductors to measure
- 3 closest pad pairs checked per domain pair
- 10-30 seconds total execution time

**Example Statistics** (HV_Attenuator test board):
```
Domain Pair: HV_8kV ↔ GROUND (80kV → 0V)
  Layer F.Cu: 306 obstacles, 19 slot barriers
    11 internal slots → 520 waypoints
    Dijkstra: 522 nodes, 22284 edges, 135981 visibility checks
    Shortest path: 10.16mm via 6 waypoints (required: 12.0mm) ❌

Path: START(212.08, 142.84) → WP1(212.57, 144.03) → WP2(213.53, 144.17)
    → WP3(214.63, 144.03) → WP4(214.77, 142.23) → WP5(214.70, 141.10)
    → WP6(214.60, 140.10) → GOAL(213.20, 137.61)
```

### Configuration

See [emc_rules.toml](emc_rules.toml) for complete configuration:

```toml
[clearance_creepage]
enabled = true
check_clearance = true          # Air gap distance
check_creepage = true           # Surface path distance
safety_margin_factor = 1.2      # 20% safety margin
max_obstacles = 500             # Performance limit per layer
obstacle_search_margin_mm = 20.0  # Spatial filtering
list_all_nets = false           # true = show all nets, false = assigned only
draw_creepage_path = true       # Draw debug path on marker layer
slot_layer_names = ["Edge.Cuts", "GM1_2mm_slots.Cuts"]  # Slot barrier layers

[[clearance_creepage.voltage_domains]]
name = "MAINS_L"
voltage_rms = 230.0
net_class = "Mains"  # Preferred: KiCad Net Class
net_patterns = ["AC_L", "MAINS_L", "LINE"]  # Fallback: pattern matching
requires_reinforced_insulation = true

[[clearance_creepage.isolation_requirements]]
domain_a = "MAINS_L"
domain_b = "EXTRA_LOW_VOLTAGE"
isolation_type = "reinforced"
min_clearance_mm = 6.0
min_creepage_mm = 8.0
```

### Key Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `slot_layer_names` | `["Edge.Cuts"]` | Layers containing slot/cutout barriers |
| `draw_creepage_path` | `false` | Draw debug polyline showing creepage path |
| `list_all_nets` | `true` | Show all board nets vs only assigned nets |
| `max_obstacles` | `500` | Max obstacles per layer before skipping |

### Usage Example

1. **Assign nets to voltage domains** using KiCad Net Classes:
   - Edit → Net Classes → Add "Mains", "HighVoltage", "LowVoltage"
   - Assign nets to classes in PCB Editor

2. **Run EMC Auditor** from toolbar or Actions menu

3. **Review violations** on User.Comments layer:
   - Red circles at violation locations
   - Text shows actual vs required distance
   - Delete markers individually or by group

### Extending the Implementation

To modify the algorithm:
- Edit `clearance_creepage.py`
- Key methods: `_calculate_clearance()`, `_calculate_creepage()`
- **Pathfinding entry point:** `_visibility_graph_path()` — separates Edge.Cuts from internal slots
- **Waypoint generation:** `_get_slot_waypoints()` — bbox extremity waypoints with 0.1mm offset
- **Shortest path:** `_dijkstra_waypoint_path()` — Dijkstra on visibility graph of waypoints
- **Slot intersection:** `_path_crosses_slot()` — checks line against slot polygons only
- **Debug visualization:** `_draw_debug_creepage_path()` — polyline on marker layer
- **A* fallback:** `_astar_surface_path_fast()` — dense board fallback
- Adjust performance limits: `max_obstacles`, `obstacle_search_margin_mm`

---

## Lookup Table Interpolation (LEGACY PSEUDOCODE BELOW)
    }
```

---

## Practical Design Guidelines

### Common PCB Voltage Scenarios

| Voltage Rails | Min Clearance | Min Creepage | Notes |
|---------------|---------------|--------------|-------|
| 3.3V - GND | 0.13mm | 0.13mm | IPC2221 minimum trace spacing |
| 5V - GND | 0.13mm | 0.13mm | Standard logic levels |
| 12V - GND | 0.5mm | 0.5mm | Automotive/industrial |
| 24V - GND | 0.5mm | 0.5mm | Industrial control |
| 48V - GND | 0.6mm | 0.8mm | Telecom power (SELV limit) |
| 230V AC - GND | 2.5mm | 3.2mm | EU mains, basic insulation |
| 230V AC - SELV | **6.0mm** | **8.0mm** | **Reinforced insulation** |
| 400V DC - GND | 4.0mm | 5.0mm | High-voltage DC |

### Design Rules of Thumb

**For Certification:**
1. Always use **IEC60664-1** for safety-critical products
2. Add **20% safety margin** (already in config: `safety_margin_factor = 1.2`)
3. Use **Overvoltage Category II** (typical appliances)
4. Use **Pollution Degree 2** (normal indoor)
5. Assume **Material Group II** (standard FR4 PCB)

**For Manufacturability:**
1. Minimum trace spacing: **0.15mm** (6 mil) for standard PCB fab
2. Conformal coating allows **reduced creepage** (~50% of uncoated)
3. Solder mask provides **~0.05mm** additional insulation
4. Use **isolation slots** to break unwanted creepage paths

**For High Reliability:**
1. Add physical barriers (plastic walls, isolators) for critical isolation
2. Use layers strategically: mains on Layer 1, SELV on Layer 4 (opposite sides)
3. Route high-voltage traces away from board edges
4. Verify with **hi-pot testing** (500V-4000V stress test)

### Altitude Correction

Above 2000m elevation, clearance must increase:

| Altitude | Clearance Factor |
|----------|------------------|
| 0-2000m | 1.0× (no change) |
| 2000-3000m | 1.25× |
| 3000-4000m | 1.4× |
| 4000-5000m | 1.6× |

**Implementation:**
```python
if altitude_m > 2000:
    altitude_factor = 1.0 + 0.00025 * (altitude_m - 2000)
    required_clearance *= altitude_factor
```

---

## Testing and Validation

### Hi-Pot Testing

**Purpose:** Verify actual insulation withstands overvoltage.

**Test Voltage:**
- Basic insulation: 2× working voltage + 1000V (AC) or 1414V (DC)
- Reinforced insulation: 2× (basic test voltage)

**Example:**
- 230V AC mains, reinforced insulation
- Test voltage: 2 × (2 × 230 + 1000) = **2920V AC**
- Apply for 60 seconds, no breakdown/leakage

### Inspection Methods

1. **Visual Inspection:** Measure with calipers at narrowest points
2. **PCB Design Rule Check (DRC):** KiCad automated verification
3. **Gerber Review:** Verify clearances in manufacturing files
4. **First Article Inspection:** Measure on actual PCB with microscope

---

## References

**Standards Documents:**
- IEC 60664-1:2020 - Insulation coordination for equipment within low-voltage systems
- IPC-2221B:2012 - Generic Standard on Printed Board Design
- UL 60950-1 / UL 62368-1 - Safety standards referencing IEC60664-1

**Online Resources:**
- [IEC 60664-1 Standard Purchase](https://webstore.iec.ch/)
- [IPC Standards](https://www.ipc.org/standards)
- [PCB Design Guidelines - Altium](https://www.altium.com/)
- [Creepage and Clearance Calculator - OMRON](https://www.omron.com/)

**KiCad Documentation:**
- [Python Plugin Development](https://docs.kicad.org/master/en/pcbnew/pcbnew.html#custom-plugins)
- [pcbnew Python API](https://docs.kicad.org/doxygen-python/namespacepcbnew.html)

---

## Algorithm Evolution

| Version | Date | Algorithm | Key Change |
|---------|------|-----------|------------|
| 1.0 | Jan 2026 | Recursive detour | Initial slot-avoidance pathfinding |
| 2.0 | Feb 2026 | Hybrid A* + Visibility Graph | Angle-based key vertices, spatial indexing |
| 3.0 | Mar 2026 | Dijkstra Waypoint Graph | Bbox extremity waypoints, Edge.Cuts separation |

### Version 3.0 Key Improvements

1. **Bbox extremity waypoints** replace angle-based vertex extraction
   - Slot polygons are rounded rectangles; angle-based approach picked mid-side vertices
   - Bbox approach always finds actual slot tips (4 midpoints + 4 corners per slot)

2. **Edge.Cuts separation** — board outline vs internal slots
   - Edge.Cuts = board boundary (no waypoints, used only as barrier)
   - Internal .Cuts layers = isolation slots (waypoints generated at tips)

3. **Dijkstra replaces recursive detour**
   - Recursive approach burned 5000+ calls on dense waypoint sets
   - Dijkstra on waypoint graph: guaranteed shortest path, instant results

4. **0.1mm waypoint offset** — tight routing at slot edges
   - Matches the polygon buffer size from `TransformShapeToPolygon`
   - 1.0mm was too far from slots; 0.01mm caused grazing intersection failures

5. **Debug creepage path visualization**
   - `draw_creepage_path = true` draws polyline + label on marker layer
   - Shows actual routing path for visual verification

6. **Pad edge-to-edge measurement**
   - IEC 60664-1 requires measurement from conductive edges, not pad centres
   - `_get_pad_edge_point()` finds closest boundary point toward opposing pad

### Validated Results

On HV_Attenuator test board (80kV domain vs GND, 11 internal slots):
- **Path distance:** 10.16mm (routes around L-shaped slot barrier)
- **Slot extension test:** Adding 1mm to slot → path increases by 2mm (2:1 ratio confirmed)
- **Performance:** 522 nodes, 22K edges, 136K visibility checks

---

**Last Updated:** March 27, 2026  
**Configuration File:** `emc_rules.toml`  
**Plugin File:** `emc_auditor_plugin.py`
