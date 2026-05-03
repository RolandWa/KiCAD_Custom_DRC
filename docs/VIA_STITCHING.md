# Via Stitching Rule

**Last Updated:** May 3, 2026  
**Status:** ✅ Implemented and Active  
**Version:** 1.1.0

## Purpose

Verifies proper via stitching for EMI reduction and signal integrity through three complementary checks:

1. **Critical Via Proximity**: Ensures high-speed signal vias have nearby GND return vias
2. **GND Plane Density**: Verifies adequate via stitching density across GND copper pours
3. **Board Edge Stitching**: Checks perimeter stitching for EMI shielding

## Rule Parameters

### Configuration Section
```toml
[via_stitching]
enabled = true
```

### Core Parameters (Critical Via Proximity)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_distance_mm` | 2.0 | Maximum distance from critical via to nearest GND via (mm) |
| `critical_net_classes` | ["HighSpeed", "Clock", "Differential"] | Net classes requiring via stitching verification |
| `ground_net_patterns` | ["GND", "GROUND", "VSS", "PGND", "AGND"] | Net name patterns identifying ground vias (case-insensitive) |
| `violation_message` | "NO GND VIA" | Message displayed on violation markers |

### Advanced Parameters (NEW in v1.1.0)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `check_gnd_plane_density` | false | Enable GND plane via density checking |
| `min_stitch_vias_per_cm2` | 4.0 | Minimum via density in GND planes (vias/cm²) |
| `check_edge_stitching` | false | Enable board edge stitching verification |
| `max_edge_stitch_spacing_mm` | 20.0 | Maximum spacing between edge GND vias (mm) |
| `edge_stitch_margin_mm` | 2.0 | Distance from board edge to count as "edge via" (mm) |

## How It Works

### Check 1: Critical Via Proximity (Always Active)

1. **Identify Critical Vias**: Scans PCB for vias belonging to net classes defined in `critical_net_classes`
2. **Search for GND Vias**: For each critical via, searches for nearest via with net name matching `ground_net_patterns`
3. **Distance Check**: Measures distance between critical via and nearest GND via
4. **Violation Marking**: If distance exceeds `max_distance_mm`, draws violation marker with red circle and text label

### Check 2: GND Plane Density (Optional - v1.1.0)

**Purpose**: Ensures GND copper pours have adequate via stitching for current distribution and EMI reduction.

**How it works:**
1. **Scan GND Zones**: Identifies all filled copper zones with GND net names
2. **Calculate Area**: Computes zone area in cm² (skips zones < 0.01 cm²)
3. **Count Vias**: Uses `HitTestFilledArea()` to count vias inside each zone
4. **Calculate Density**: Actual density = vias / area (vias/cm²)
5. **Violation Marking**: If density < `min_stitch_vias_per_cm2`, draws marker at zone center

**Violation Message:**
```
LOW VIA DENSITY
1.6/4.0 vias/cm²
```

**Typical Requirements:**
- Standard boards: 2-4 vias/cm²
- High-speed designs: 4-6 vias/cm²
- RF/microwave boards: 6-10 vias/cm²

### Check 3: Board Edge Stitching (Optional - v1.1.0)

**Purpose**: Verifies perimeter stitching for EMI shielding ("Faraday cage" effect).

**How it works:**
1. **Get Board Bounds**: Retrieves board bounding box from edge cuts
2. **Check Each Edge**: Examines left, right, top, bottom edges independently
3. **Find Edge Vias**: Identifies GND vias within `edge_stitch_margin_mm` of each edge
4. **Measure Spacing**: Calculates distance between consecutive edge vias
5. **Violation Marking**: If gap > `max_edge_stitch_spacing_mm`, draws marker at gap midpoint

**Violation Message:**
```
EDGE GAP
60.0mm > 20.0mm
```

**Typical Requirements:**
- Standard boards: 20-30mm spacing
- High-frequency designs: 10-15mm spacing
- EMC-critical products: 5-10mm spacing

## Violation Markers

### Critical Via Proximity Violations

Each violation creates an individual group:
- **Group Name**: `EMC_Via_<netname>_<n>`
- **Visual Elements**: Red circle at via location + "NO GND VIA" text label
- **Layer**: Cmts.User (User Comments)
- **Optional**: Arrow pointing to nearest GND via with distance label

### GND Plane Density Violations

Each zone with insufficient density creates a violation:
- **Group Name**: `EMC_ViaDensity_<netname>_<n>`
- **Visual Elements**: Marker at zone center + density ratio text
- **Layer**: Cmts.User (User Comments)
- **Message Format**: `LOW VIA DENSITY\n{actual}/{required} vias/cm²`

### Board Edge Stitching Violations

Each gap in edge stitching creates a violation:
- **Group Name**: `EMC_EdgeStitch_<edge_name>_<n>`
- **Visual Elements**: Marker at gap midpoint + spacing text
- **Layer**: Cmts.User (User Comments)
- **Message Format**: `EDGE GAP\n{actual}mm > {max}mm`

### Deleting Violations

To delete violations one by one:
1. Click on violation marker
2. Right-click → "Select Items in Group"
3. Press Delete

## Configuration Examples

### Basic Configuration (Critical Vias Only)
```toml
[via_stitching]
enabled = true
max_distance_mm = 2.0
critical_net_classes = ["HighSpeed", "Clock", "Differential"]
ground_net_patterns = ["GND", "GROUND", "VSS"]
violation_message = "NO GND VIA"
```

### Standard Design (All Checks Enabled)
```toml
[via_stitching]
enabled = true

# Critical via proximity
max_distance_mm = 2.0
critical_net_classes = ["HighSpeed", "Clock", "Differential"]
ground_net_patterns = ["GND", "GROUND", "VSS", "PGND", "AGND"]

# GND plane density checking
check_gnd_plane_density = true
min_stitch_vias_per_cm2 = 4.0

# Board edge stitching
check_edge_stitching = true
max_edge_stitch_spacing_mm = 20.0
edge_stitch_margin_mm = 2.0
```

### High-Speed Design (Strict Requirements)
```toml
[via_stitching]
enabled = true

# Critical via proximity (stricter)
max_distance_mm = 1.5
critical_net_classes = ["HighSpeed", "Clock", "Differential", "USB", "HDMI", "Ethernet"]
ground_net_patterns = ["GND", "GROUND", "VSS", "PGND", "AGND", "DGND", "CHASSIS"]

# GND plane density (denser for high frequencies)
check_gnd_plane_density = true
min_stitch_vias_per_cm2 = 6.0

# Board edge stitching (tighter spacing)
check_edge_stitching = true
max_edge_stitch_spacing_mm = 10.0
edge_stitch_margin_mm = 2.0
```

### RF/Microwave Design (Maximum EMI Control)
```toml
[via_stitching]
enabled = true

# Critical via proximity (very strict)
max_distance_mm = 1.0
critical_net_classes = ["RF", "Antenna", "LO", "Clock"]

# GND plane density (very dense)
check_gnd_plane_density = true
min_stitch_vias_per_cm2 = 10.0

# Board edge stitching (very tight)
check_edge_stitching = true
max_edge_stitch_spacing_mm = 5.0
edge_stitch_margin_mm = 1.0
```

## Best Practices

### Why Via Stitching Matters

**High-Speed Signal Return Path**: When a signal transitions between layers via a via, the return current must follow. Without a nearby GND via:
- Return current takes longer path through ground plane
- Creates EMI radiation loop
- Degrades signal integrity
- Increases crosstalk

**Recommended Spacing**:
- **High-speed signals (>50 MHz)**: 1-2mm maximum
- **Clock lines**: 1mm maximum (place GND via on both sides)
- **Differential pairs**: 1-2mm on BOTH traces
- **General digital signals**: 3-5mm acceptable

### Example Configuration

```toml
[via_stitching]
enabled = true
max_distance_mm = 1.5  # Stricter for high-speed designs

# Include USB, HDMI, Ethernet as critical nets
critical_net_classes = ["HighSpeed", "Clock", "Differential", "USB", "HDMI"]

# Support various ground naming conventions
ground_net_patterns = ["GND", "GROUND", "VSS", "PGND", "AGND", "DGND", "CHASSIS"]

violation_message = "NO GND VIA WITHIN 1.5mm"
```

## Design Guidelines

### Correct Via Stitching
```
Signal Layer 1:  ----[Via]----
                      ↓ (signal via)
Ground Plane:    [GND Via] [GND Via]  ← Within 2mm
                      ↑              ↑
Signal Layer 2:  ----[Via]----

✅ Signal via has nearby GND return vias on both sides
```

### Incorrect Via Stitching
```
Signal Layer 1:  ----[Via]----
                      ↓ (signal via - ISOLATED!)
Ground Plane:    ==================
                 (no GND vias nearby - return current must spread)
                      ↑
Signal Layer 2:  ----[Via]----

❌ Signal via lacks nearby GND return vias
❌ Return current takes wide loop through plane
❌ EMI radiation, signal degradation
```

## Common Issues

### False Positives

**Issue**: Plugin marks via as violation but GND via exists nearby  
**Cause**: GND via net name doesn't match patterns in config  
**Solution**: Add your GND net name to `ground_net_patterns`:
```toml
ground_net_patterns = ["GND", "GROUND", "VSS", "PGND", "AGND", "GND_ISO", "SYS_GND"]
```

### False Negatives

**Issue**: Critical signals not checked for via stitching  
**Cause**: Net not assigned to critical net class  
**Solution**: In KiCad schematic, assign net to appropriate net class (Edit → Net Classes)

## Technical Background

### Return Current Physics

When signal current flows through a via:
1. **Forward current**: Flows through signal via
2. **Return current**: MUST flow back through GND via
3. **Loop area**: Distance between signal & GND vias creates EMI loop
4. **Inductance**: Larger loop = higher inductance = signal distortion

**Formula**: Loop inductance L ≈ 0.2 × d × ln(2d/r)  
Where d = distance between vias, r = via radius

### EMI Radiation

Unstitched vias act as **EMI antennas**:
- Larger loop area = more radiation
- Higher frequencies = worse radiation (λ smaller)
- Can cause FCC/CE compliance failures

### Signal Integrity Impact

Without proper stitching:
- **Reflections**: Impedance discontinuity at layer transition
- **Crosstalk**: Return current spreading couples to adjacent nets
- **Ground bounce**: Shared return path creates noise

## Advanced Features (v1.1.0)

### GND Plane Density Benefits

**Why Density Matters:**

1. **Current Distribution**: More vias provide multiple parallel paths for return currents, reducing inductance and voltage drop
2. **Thermal Management**: Dense via stitching improves heat spreading from hot components to GND planes
3. **Ground Bounce Reduction**: Lower impedance ground plane reduces simultaneous switching noise (SSN)
4. **EMI Suppression**: Better-stitched planes act as more effective electromagnetic shields

**Physics:**
- Loop inductance L ∝ 1/√(via_count)
- Impedance Z = √(L/C), so more vias → lower Z → better performance
- Each via adds parallel path: Z_total = Z_single / n

**Design Guidelines:**
```
Standard Digital:    2-4 vias/cm²  (spacing ~15-20mm)
High-Speed Digital:  4-6 vias/cm²  (spacing ~10-15mm)
RF/Microwave:       6-10 vias/cm²  (spacing ~5-10mm)
Power Electronics:  10-20 vias/cm² (spacing ~3-5mm)
```

**Calculation Example:**
```
Board: 50mm x 50mm GND zone = 2500mm² = 25cm²
Requirement: 4 vias/cm²
Needed: 25cm² × 4 vias/cm² = 100 vias minimum
```

### Board Edge Stitching Benefits

**Why Edge Stitching Matters:**

1. **Faraday Cage Effect**: Perimeter stitching creates electromagnetic barrier, containing EMI radiation within board
2. **ESD Immunity**: Edge stitching provides low-impedance path for ESD currents to reach ground plane
3. **Common-Mode Current Control**: Prevents common-mode currents from radiating at board edges
4. **Cable EMI Reduction**: Reduces coupling between PCB and attached cables

**Physics:**
- Radiation ∝ (gap_size / wavelength)²
- At 1 GHz: λ = 300mm, so 20mm gap = (20/300)² = 0.4% radiation
- At 10 GHz: λ = 30mm, so 20mm gap = (20/30)² = 44% radiation!

**Design Guidelines:**
```
Low Frequency (<100MHz):    20-30mm spacing
Standard Digital (100MHz-1GHz): 10-20mm spacing
High-Speed (1-10GHz):        5-10mm spacing
RF/Millimeter-wave (>10GHz):  <5mm spacing

Rule of Thumb: spacing ≤ λ/20 where λ = wavelength at highest frequency
```

**EMC Standards Compliance:**
- **CISPR 32 (Radiated Emissions)**: Edge stitching helps pass Class A/B limits
- **IEC 61000-4-2 (ESD)**: Improves immunity to contact/air discharge
- **IEC 61000-4-3 (Radiated Immunity)**: Reduces susceptibility to external fields

### Signal Integrity Impact

## Related Rules

- **Differential Pairs**: Requires TWO GND vias (one near each trace)
- **High-Speed Signals**: May enforce stricter distance limits
- **Ground Plane Continuity**: Verifies solid ground plane exists

## References

- **IPC-2221**: PCB design standard (via spacing guidelines)
- **IPC-2226**: High-speed PCB design (via stitching best practices)
- **Howard Johnson's "High-Speed Digital Design"**: Chapter on vias and return paths
- **Eric Bogatin's "Signal Integrity - Simplified"**: Via discontinuities analysis
- **CISPR 32**: EMC standard for multimedia equipment (radiated emissions)
- **IEC 61000-4-2**: ESD immunity testing standard
- **IEC 61000-4-3**: Radiated RF immunity testing standard

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Initial implementation with individual violation grouping |
| 1.1.0 | 2026-05-03 | Added GND plane density checking and board edge stitching verification |

## Testing

**Test Coverage:** 92% (10/10 tests passing)

**Test Scenarios:**
- ✅ Critical via without nearby GND via (violation detected)
- ✅ Critical via with GND via within threshold (no violation)
- ✅ Non-critical nets skipped correctly
- ✅ VCC and unnetted vias not counted as GND vias
- ✅ Large GND zone with insufficient via density (violation detected)
- ✅ GND zone with adequate via density (no violation)
- ✅ Board edge with large gap in stitching (violation detected)
- ✅ Board edge with adequate stitching (no violation)
- ✅ Empty config handled gracefully
- ✅ Multiple edge checking (left, right, top, bottom)

## Troubleshooting

### False Positives: GND Plane Density

**Issue**: Violation reported on small GND zones  
**Cause**: Zone too small to meet density requirement  
**Solution**: Adjust `min_stitch_vias_per_cm2` or skip small zones manually

### False Positives: Edge Stitching

**Issue**: Corner gaps reported even with corner vias  
**Cause**: Corner via detection needs tuning  
**Solution**: Adjust `edge_stitch_margin_mm` to catch corner vias

### Performance Considerations

**Large Boards**: Edge stitching check scales O(n) with number of vias  
**Dense GND Planes**: `HitTestFilledArea()` can be slow on complex zones  
**Recommendation**: Disable checks during active design, enable before final review

### Common Mistakes

❌ **Disabling all checks**: Set specific feature flags, not main `enabled = false`  
✅ **Correct**: `check_gnd_plane_density = false`

❌ **Too strict requirements**: 10 vias/cm² is overkill for standard digital  
✅ **Reasonable**: 4 vias/cm² for high-speed, 2 vias/cm² for standard

❌ **Zero edge margin**: `edge_stitch_margin_mm = 0` misses offset vias  
✅ **Practical**: 2-3mm margin catches vias near edge
