# Ground Plane Rule

**Last Updated:** February 10, 2026  
**Status:** ✅ Implemented and Active

## Purpose

Verifies ground plane continuity and adequate coverage to ensure low-impedance return path for high-speed signals. This implementation checks for continuous ground plane underneath and around critical signal traces, with advanced filtering to reduce false positives.

## Rule Parameters

### Configuration Section
```toml
[ground_plane]
enabled = true  # Ground plane checking active
```

### Core Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `check_high_speed_nets` | true | Enable checking for high-speed signals |
| `critical_net_classes` | ["HighSpeed", "Clock", "Differential"] | Net classes requiring ground plane verification |
| `ground_net_patterns` | ["GND", "GROUND", "VSS", "PGND", "AGND"] | Ground net name patterns (case-insensitive) |
| `sample_distance_mm` | 0.5 | Distance between check points along trace (mm) |
| `clearance_distance_mm` | 1.0 | Required ground clearance around trace (mm) |
| `check_both_sides` | true | Check ground plane on both sides of trace (top/bottom) |

### Advanced Filtering Parameters (NEW)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_ground_polygon_area_mm2` | 10.0 | Minimum polygon area to consider as valid ground (mm²) - filters out small copper islands |
| `preferred_ground_layers` | ["In1.Cu", "In2.Cu"] | Priority layers for ground plane (inner layers preferred) |
| `ignore_via_clearance` | 0.5 | Ignore violations within this distance from ground vias (mm) - reduces false positives near vias |
| `ignore_pad_clearance` | 0.3 | Ignore violations within this distance from ground pads (mm) - reduces false positives near component pads |

### Visualization Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `violation_message` | "NO GND PLANE" | Message displayed on violation markers |
| `draw_arrow_to_gap` | false | Draw arrow pointing to gap location |

## How It Works

1. **Identify Critical Traces**: Scans PCB for tracks belonging to net classes defined in `critical_net_classes` (HighSpeed, Clock, Differential)
2. **Sample Track Points**: Places check points every `sample_distance_mm` along each critical trace (default 0.5mm)
3. **Ground Plane Search**: For each check point:
   - Searches all layers for ground zones (matching `ground_net_patterns`)
   - Prioritizes layers listed in `preferred_ground_layers` (inner layers)
   - Filters out small copper islands (< `min_ground_polygon_area_mm2`)
   - Checks if point is directly under trace (zone hit test)
4. **Clearance Verification**: Verifies ground plane extends `clearance_distance_mm` around trace
5. **Advanced Filtering**:
   - Ignores violations within `ignore_via_clearance` of ground vias (reduces false positives)
   - Ignores violations within `ignore_pad_clearance` of ground pads (component connections)
6. **Violation Marking**: If no ground found or clearance insufficient, draws violation marker

### Performance Optimization

The implementation uses **pre-filtered zone dictionary** for 5-10× faster checking:
```python
# Build dictionary once: layer_name -> list of ground zones
ground_zones_by_layer = {}
for zone in board.Zones():
    if zone.IsFilled() and is_ground_net(zone):
        if area >= min_area:  # Filter small polygons
            layer_name = board.GetLayerName(zone.GetLayer())
            ground_zones_by_layer[layer_name].append(zone)

# O(1) lookup instead of O(n) iteration per check point
zones = ground_zones_by_layer.get(layer_name, [])
```

### Progress Dialog

For boards with >10 tracks to check, displays progress dialog:
- Shows current track number and total count
- Displays net name being checked
- Cancel button to abort long-running checks
- Example: "Checking track 15/42 on net 'CLK'..."

## Violation Markers

Each violation creates an individual group:
- **Group Name**: `EMC_GndPlane_CLK_1`, `EMC_GndPlane_USB_D+_2`, etc.
- **Visual Elements**: Red circle at violation location + "NO GND PLANE" text label
- **Layer**: Cmts.User (User Comments)

To delete violations one by one:
1. Click on violation marker
2. Right-click → "Select Items in Group"
3. Press Delete

## Ground Plane Theory

### Why Ground Planes Matter

**1. Low-Impedance Return Path**:
- Signal current flows out on signal trace
- Return current flows back through ground plane
- High impedance forces return current to spread, creating EMI

**2. EMI Shielding**:
- Ground plane acts as Faraday shield
- Blocks electric field coupling between layers
- Reflects radiated emissions back into board

**3. Thermal Management**:
- Large copper area dissipates heat from components
- Reduces hot spots and thermal gradients

**4. Voltage Reference**:
- Provides stable 0V reference for all signals
- Reduces ground bounce (voltage variation between GND points)

### Ground Plane Coverage Guidelines

| Application | Min Coverage | Typical Coverage | Notes |
|-------------|--------------|------------------|-------|
| Low-speed digital | 30% | 40-60% | Basic noise immunity |
| High-speed digital | 60% | 80-95% | Critical for signal integrity |
| Mixed-signal (ADC/DAC) | 70% | 85-98% | Isolate analog/digital GND |
| RF/microwave | 90% | 95-100% | Continuous plane essential |
| Power electronics | 50% | 60-80% | Balance thermal & isolation |

### Gap Tolerance

**Acceptable Gaps**:
- **Narrow slots** (< 2mm): Generally acceptable for routing
- **Under high-speed traces**: AVOID - forces return current detour
- **Between analog/digital sections**: Intentional (single-point connection)

**Critical Gaps** (violations):
- **Wide gaps** (> 5mm): Breaks return path continuity
- **Under differential pairs**: Causes impedance discontinuity
- **Across signal via transitions**: Increases EMI radiation

## Recommended Configurations

### Standard Digital Design
```toml
[ground_plane]
enabled = true
check_high_speed_nets = true
critical_net_classes = ["HighSpeed", "Clock", "Differential"]
ground_net_patterns = ["GND", "GROUND", "VSS"]
sample_distance_mm = 0.5  # Moderate resolution
clearance_distance_mm = 1.0  # Standard clearance

# Filtering
min_ground_polygon_area_mm2 = 10.0  # Ignore small copper islands
preferred_ground_layers = ["In1.Cu", "In2.Cu"]  # Inner layers preferred
ignore_via_clearance = 0.5  # Reduce false positives near vias
ignore_pad_clearance = 0.3  # Reduce false positives near pads

check_both_sides = true  # Check top and bottom
violation_message = "NO GND PLANE"
```

### High-Speed Digital Design (Stricter)
```toml
[ground_plane]
enabled = true
check_high_speed_nets = true
critical_net_classes = ["HighSpeed", "Clock", "Differential", "USB", "HDMI"]
sample_distance_mm = 0.25  # Higher resolution for critical signals
clearance_distance_mm = 2.0  # Wider clearance for better shielding

# Stricter filtering
min_ground_polygon_area_mm2 = 25.0  # Larger minimum polygon
preferred_ground_layers = ["In1.Cu", "In2.Cu"]
ignore_via_clearance = 0.3  # Tighter tolerance
ignore_pad_clearance = 0.2

check_both_sides = true
violation_message = "GND PLANE GAP - SI RISK"
```

### Mixed-Signal Design (Analog Focus)
```toml
[ground_plane]
enabled = true
critical_net_classes = ["Analog", "ADC", "DAC"]
ground_net_patterns = ["AGND", "GND_A", "ANALOG_GND"]  # Analog ground only
sample_distance_mm = 0.3
clearance_distance_mm = 1.5

# Focus on analog ground plane
min_ground_polygon_area_mm2 = 15.0
preferred_ground_layers = ["In1.Cu"]  # Dedicated analog ground layer
ignore_via_clearance = 0.4
ignore_pad_clearance = 0.25

check_both_sides = false  # Check only adjacent layer
violation_message = "ANALOG GND PLANE MISSING"
```

### 2-Layer Design (Relaxed)
```toml
[ground_plane]
enabled = true
critical_net_classes = ["HighSpeed", "Clock"]
sample_distance_mm = 1.0  # Lower resolution (limited ground on 2-layer)
clearance_distance_mm = 0.5  # Smaller clearance acceptable

# More lenient filtering for 2-layer boards
min_ground_polygon_area_mm2 = 5.0  # Accept smaller polygons
preferred_ground_layers = ["B.Cu"]  # Bottom layer ground pour
ignore_via_clearance = 0.8  # More tolerance
ignore_pad_clearance = 0.5

check_both_sides = false  # Check only bottom layer
violation_message = "GND POUR GAP"
```

## Design Guidelines

### High-Speed Trace Ground Plane Requirements

**Critical Principle**: High-speed signals need **continuous ground plane** directly underneath for proper return current path.

```
Cross-Section View (4-layer board):

Layer 1 (Signal):  =====[Trace]=====  ← High-speed signal
                         ↓ (Electric field couples to ground)
Layer 2 (Ground):  ██████████████  ← Solid ground plane (95%+ coverage)
Layer 3 (Power):   VCC zones, 3V3 zones
Layer 4 (Signal):  Bottom routing

✅ Ground plane on Layer 2 provides return path for Layer 1 signals
✅ Minimal gaps - plugin verifies continuity under critical traces
```

### What the Plugin Checks

**1. Ground Plane Under Trace** (sample_distance_mm):
```
Top View:
           Check Point 1   Check Point 2   Check Point 3
                ↓              ↓              ↓
=================[Trace]============================
       ░░░░░░░░░░░░░░░░░░░░░↑
       Ground plane on adjacent layer (Layer 2)
       Plugin samples every 0.5mm by default

✅ Check point directly over ground zone → PASS
❌ Check point over gap in ground → VIOLATION
```

**2. Clearance Around Trace** (clearance_distance_mm):
```
Top View of Ground Layer:

       ┌──────────────────┐
       │  Clearance Zone  │  ← 1mm clearance (default)
       │   (must be GND)  │
       └──────────────────┘
            [Trace path]
       ┌──────────────────┐
       │  Clearance Zone  │
       │   (must be GND)  │
       └──────────────────┘

✅ Ground extends 1mm on both sides → PASS
❌ Non-ground zone within 1mm → VIOLATION
```

**3. Advanced Filtering**:
- **Small Polygon Filter**: Ignores copper islands < 10mm² (not useful for return current)
- **Via/Pad Tolerance**: Skips violations within 0.5mm of ground vias, 0.3mm of ground pads
- **Preferred Layers**: Prioritizes inner layers (In1.Cu, In2.Cu) for ground plane

### Example Violations and Fixes

**Violation 1: Gap Under High-Speed Trace**
```
Layer 1: ========[CLK]========  ← 100 MHz clock
Layer 2:   GND     [GAP]    GND  ← Ground plane interrupted
                    ↑
            Plugin marks violation here

FIX: Fill gap with ground copper or reroute clock trace
```

**Violation 2: Insufficient Clearance**
```
Layer 1: ========[USB_D+]========
Layer 2: [Signal]  GND  [Signal]  ← Other signals too close
           ↑
   Clearance zone invaded by non-ground traces

FIX: Move other signals away from USB differential pair
```

**False Positive (Now Filtered)**:
```
Layer 1: ========[Trace]========
Layer 2:   GND   [Via]   GND  ← Ground via interrupts plane
                  ↑
          Plugin ignores (within 0.5mm of GND via)

No violation → Via clearance filter prevents false positive
```

### Correct vs. Incorrect Design
**✅ CORRECT**: Continuous ground plane under high-speed traces
```
Top Layer:    ======[CLK 100MHz]======
              │                      │
Inner Layer:  ██████████████████████  ← Solid GND plane
              │    Return current     │
              └─────path flows here───┘

Result: Low impedance, minimal EMI, clean signal
```

**❌ INCORRECT**: Gap in ground plane under trace
```
Top Layer:    ======[CLK 100MHz]======
                       │
Inner Layer:  GND     [GAP]     GND  ← Gap forces detour
              │                  │
              └──Return current──┘
                 spreads around gap
                 (creates EMI loop)

Result: High impedance, EMI radiation, signal degradation
```

## Best Practices

### Rule 1: Use Plugin to Verify Critical Traces
- Enable plugin for high-speed nets (>50 MHz)
- Run audit after routing changes
- Fix violations before manufacturing

### Rule 2: Choose Appropriate Sample Distance
- High-speed (>100 MHz): 0.25mm sampling
- Medium-speed (50-100 MHz): 0.5mm sampling (default)
- Low-speed (<50 MHz): 1.0mm sampling acceptable

### Rule 3: Tune Filtering Parameters
- Increase `min_ground_polygon_area_mm2` if too many false positives from small copper
- Adjust `ignore_via_clearance` / `ignore_pad_clearance` based on board complexity
- Use `preferred_ground_layers` to prioritize inner ground planes

### Rule 4: Review Violations Systematically
- Check "NO GND PLANE" markers on User.Comments layer
- Delete false positives (near intentional gaps)
- Fix real violations by adding ground copper or rerouting

### Rule 5: Combined Rules
- Use with **Via Stitching** rule for complete ground integrity
- Combine with **Decoupling** rule for power integrity
- Ground plane + via stitching = complete EMC solution

## Performance Features

### Speed Optimization
- **Pre-filtered zone dictionary**: 5-10× faster than naive O(n⁴) algorithm
- **Layer indexing**: O(1) lookup instead of iterating all zones per check point
- **Polygon area filter**: Skips small copper islands automatically

### Progress Feedback
- Shows progress dialog for boards with >10 critical tracks
- Displays current track number and net name
- Cancel button to abort long-running checks
- Example: "Checking track 15/42 on net 'CLK'..."

### Keyboard Shortcuts (in Report Dialog)
- **Ctrl+S**: Save report to file
- **Escape**: Close report dialog

## Related Rules

- **Via Stitching**: Ensures ground vias near signal vias (complementary check)
- **Decoupling**: Power supply noise reduction (combines with ground plane)
- **Clearance/Creepage**: High-voltage isolation affected by ground plane geometry

## References

- **IPC-2221**: PCB design standard (layer stackup guidelines)
- **IPC-2226**: High-speed design guide (ground plane requirements)
- **Howard Johnson's "High-Speed Digital Design"**: Ground plane theory
- **Henry Ott's "Electromagnetic Compatibility Engineering"**: EMI shielding
- **Eric Bogatin's "Signal Integrity - Simplified"**: Return path analysis

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Configuration created, implementation pending |
| 1.1.0 | 2026-02-10 | Implementation complete with performance optimization, progress dialog, advanced filtering |

---

**Status**: ✅ **Production Ready** - Fully implemented, tested, and deployed
