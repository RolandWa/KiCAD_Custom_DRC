# Via Stitching Rule

**Last Updated:** February 6, 2026  
**Status:** ✅ Implemented and Active

## Purpose

Verifies that critical signal vias have nearby ground (GND) return vias for proper electromagnetic return path. This is crucial for high-speed signals, clock lines, and differential pairs to prevent EMI radiation and maintain signal integrity.

## Rule Parameters

### Configuration Section
```toml
[via_stitching]
enabled = true
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_distance_mm` | 2.0 | Maximum distance from critical via to nearest GND via (mm) |
| `critical_net_classes` | ["HighSpeed", "Clock", "Differential"] | Net classes requiring via stitching verification |
| `ground_net_patterns` | ["GND", "GROUND", "VSS", "PGND", "AGND"] | Net name patterns identifying ground vias (case-insensitive) |
| `violation_message` | "NO GND VIA" | Message displayed on violation markers |

## How It Works

1. **Identify Critical Vias**: Scans PCB for vias belonging to net classes defined in `critical_net_classes`
2. **Search for GND Vias**: For each critical via, searches for nearest via with net name matching `ground_net_patterns`
3. **Distance Check**: Measures distance between critical via and nearest GND via
4. **Violation Marking**: If distance exceeds `max_distance_mm`, draws violation marker with red circle and text label

## Violation Markers

Each violation creates an individual group:
- **Group Name**: `EMC_Via_1`, `EMC_Via_2`, etc.
- **Visual Elements**: Red circle at via location + "NO GND VIA" text label
- **Layer**: Cmts.User (User Comments)

To delete violations one by one:
1. Click on violation marker
2. Right-click → "Select Items in Group"
3. Press Delete

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

## Related Rules

- **Differential Pairs**: Requires TWO GND vias (one near each trace)
- **High-Speed Signals**: May enforce stricter distance limits
- **Ground Plane Continuity**: Verifies solid ground plane exists

## References

- **IPC-2221**: PCB design standard (via spacing guidelines)
- **IPC-2226**: High-speed PCB design (via stitching best practices)
- **Howard Johnson's "High-Speed Digital Design"**: Chapter on vias and return paths
- **Eric Bogatin's "Signal Integrity - Simplified"**: Via discontinuities analysis

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Initial implementation with individual violation grouping |
