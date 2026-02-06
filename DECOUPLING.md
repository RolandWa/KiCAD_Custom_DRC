# Decoupling Capacitor Rule

**Last Updated:** February 6, 2026  
**Status:** ✅ Implemented and Active

## Purpose

Verifies that IC power pins have decoupling capacitors placed sufficiently close to suppress power supply noise, reduce ground bounce, and ensure stable operation. Proper decoupling is critical for preventing digital noise from affecting analog circuits and maintaining EMC compliance.

## Rule Parameters

### Configuration Section
```toml
[decoupling]
enabled = true
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_distance_mm` | 3.0 | Maximum distance from IC power pin to nearest capacitor (mm) |
| `ic_reference_prefixes` | ["U"] | Component prefixes requiring decoupling (typically ICs) |
| `capacitor_reference_prefixes` | ["C"] | Component prefixes to search for (capacitors) |
| `power_net_patterns` | ["VCC", "VDD", "PWR", "3V3", "5V", ...] | Power net name patterns (case-insensitive) |
| `draw_arrow_to_nearest_cap` | true | Draw arrow from IC pin to nearest capacitor |
| `show_capacitor_label` | true | Show capacitor reference (e.g., "→ C15") |

## How It Works

1. **Identify IC Power Pins**: Scans components with references matching `ic_reference_prefixes` for power pins connected to nets matching `power_net_patterns`
2. **Smart Net Matching**: For each power pin, searches ONLY for capacitors connected to the SAME power net
   - Example: U1 pin 7 on VCC → searches only capacitors with one pad on VCC net
   - Ignores capacitors on 3V3, 5V, or other power nets
3. **Distance Check**: Measures distance from power pin to nearest matching capacitor
4. **Violation Marking**: If distance exceeds `max_distance_mm`, draws marker with arrow pointing to nearest capacitor

## Smart Net Matching (Critical Feature)

**Problem**: Early versions checked ALL capacitors regardless of which power net they served, causing false positives on multi-voltage designs.

**Solution**: The plugin now performs **smart net matching**:

```python
# For U1 power pin on "VCC" net:
for each capacitor:
    for each pad on capacitor:
        if pad.GetNetname() == "VCC":
            capacitor_is_valid = True
```

**Result**: 
- ✅ U1 on VCC → searches C1 (VCC-GND), C2 (VCC-GND)
- ❌ U1 on VCC → ignores C10 (3V3-GND), C11 (5V-GND)

This prevents false positives on multi-rail designs.

## Violation Markers

Each violation creates an individual group:
- **Group Name**: `EMC_Decap_U1_VCC`, `EMC_Decap_U2_3V3`, etc.
- **Visual Elements**:
  - Red circle at IC power pin location
  - Violation message: "CAP TOO FAR (5.2mm)"
  - Arrow pointing to nearest capacitor
  - Capacitor reference label: "→ C15"
- **Layer**: Cmts.User (User Comments)

To delete violations one by one:
1. Click on violation marker
2. Right-click → "Select Items in Group"
3. Press Delete

## Best Practices

### Why Decoupling Capacitors Matter

**Local Energy Reservoir**: ICs draw pulsed current during switching:
- Power supply trace has inductance (L)
- Current pulse causes voltage drop: V = L × di/dt
- Decoupling capacitor provides local charge reservoir
- Reduces power supply ripple and ground bounce

**EMC Compliance**: Poor decoupling causes:
- Conducted emissions (power supply noise)
- Radiated emissions (power traces act as antennas)
- Susceptibility to external interference

### Recommended Placement

**Distance Guidelines**:
- **High-speed digital (>50 MHz)**: 0.5-1.5mm (very close)
- **Medium-speed digital (10-50 MHz)**: 1.5-3mm (moderately close)
- **Low-speed digital (<10 MHz)**: 3-5mm acceptable
- **Analog power supplies**: 1-2mm (critical for noise rejection)

**Multiple Capacitors**:
```
              C1(100nF)  ← 1-2mm from IC
                 ↓
            [IC Power Pin]
                 ↑
              C2(10µF)   ← 5-10mm from IC (bulk capacitance)
```

Use parallel capacitors of different values:
- **Small (100nF)**: High-frequency noise (placed VERY close)
- **Medium (1-10µF)**: Mid-frequency transients
- **Large (100µF)**: Bulk energy storage

### Example Configuration

```toml
[decoupling]
enabled = true
max_distance_mm = 2.0  # Stricter for high-speed designs

# Include other IC types
ic_reference_prefixes = ["U", "IC", "MCU", "FPGA"]

# Include tantalum and ceramic caps
capacitor_reference_prefixes = ["C", "CAP"]

# Support various power rail naming
power_net_patterns = [
    "VCC", "VDD", "VDDIO", "VDDA", "VDDR",  # Positive rails
    "3V3", "5V", "1V8", "2V5", "12V",        # Specific voltages
    "+3V3", "+5V", "+12V",                    # Signed voltages
    "PWR", "POWER", "SUPPLY"                  # Generic names
]

# Enable visual guidance
draw_arrow_to_nearest_cap = true
show_capacitor_label = true

violation_message = "CAP TOO FAR ({distance:.1f}mm) - ADD C NEAR PIN"
```

## Design Guidelines

### Correct Decoupling Placement
```
PCB Layout:
             C1 (100nF)
              ⬤   ← 1mm from IC power pin
             ╱ ╲
   VCC ═════╪═══╪═════ VCC trace
             │   │
         [Pin 7] [Pin 14]
             │   │
   GND ═════╪═══╪═════ GND plane
             │   │
            IC Body

✅ Capacitor placed between power pin and GND
✅ Short trace lengths minimize inductance
✅ Multiple vias to power/ground planes
```

### Incorrect Decoupling Placement
```
PCB Layout:
   VCC ═══════════════ (long trace)
             │
         [Pin 7]
             │
            IC Body
             │
         [Pin 14]
             │
   GND ═══════════════ (long trace)
             ╲   ╱
              ⬤   C1 (100nF) - 10mm away!

❌ Capacitor too far from IC power pin
❌ Long trace inductance defeats decoupling
❌ Ground bounce and voltage droop
```

## Common Issues

### False Positives

**Issue 1**: Plugin marks violation but capacitor exists nearby  
**Cause**: Capacitor not connected to same power net  
**Solution**: Verify capacitor pad is on correct power net (use KiCad "Highlight Net" feature)

**Issue 2**: Bulk capacitor flagged as "too far"  
**Cause**: Plugin checks distance to ANY capacitor, not just ceramic bypass  
**Solution**: Place small ceramic (100nF) close to IC, bulk capacitor can be farther away

### False Negatives

**Issue**: IC power pins not checked  
**Cause 1**: IC reference doesn't start with "U" (e.g., "MCU1" or "IC1")  
**Solution**: Add prefix to `ic_reference_prefixes`:
```toml
ic_reference_prefixes = ["U", "IC", "MCU", "FPGA", "CPU"]
```

**Cause 2**: Power net name doesn't match patterns  
**Solution**: Add net name to `power_net_patterns`:
```toml
power_net_patterns = ["VCC", "VDD", "PWR", "VCORE", "VBAT", "VLOGIC"]
```

## Technical Background

### PDN Impedance

**Power Distribution Network (PDN)** has impedance Z(f):
1. **DC resistance**: Trace resistance (low frequency)
2. **Inductive region**: L dominates (mid frequency) ← DECOUPLING TARGET
3. **Capacitive region**: C dominates (high frequency)

**Goal**: Keep Z(f) below target impedance across frequency range

**Formula**: Z_target = V_ripple / I_max  
Example: 50mV ripple, 1A current → 50mΩ target impedance

### Capacitor Effectiveness

Decoupling effectiveness depends on:
- **Capacitance (C)**: Larger = more charge storage
- **ESR (Equivalent Series Resistance)**: Lower = better high-freq response
- **ESL (Equivalent Series Inductance)**: Lower = higher effective frequency
- **Connection inductance**: Trace length and via inductance

**Self-Resonant Frequency (SRF)**: f_SRF = 1/(2π√(L×C))  
Above SRF, capacitor acts as inductor (useless!)

### Parallel Capacitor Benefits

Using multiple capacitors in parallel:
1. **Frequency coverage**: Different SRFs cover wide bandwidth
2. **Current sharing**: Reduces individual cap stress
3. **Redundancy**: Failure of one cap doesn't eliminate decoupling

**Example**:
- 100nF X7R: SRF ~10 MHz (high-freq noise)
- 10µF X5R: SRF ~1 MHz (mid-freq transients)
- 100µF electrolytic: SRF ~100 kHz (bulk storage)

## Verification Methods

### Oscilloscope Measurement

1. **Probe IC power pin directly** (minimize probe ground lead length!)
2. **Measure power supply ripple** during IC operation
3. **Acceptable ripple**: <50mV peak-to-peak for most digital ICs

### VNA Measurement (Advanced)

1. **Measure PDN impedance** with Vector Network Analyzer
2. **Frequency sweep**: 100 kHz to 100 MHz
3. **Target impedance**: Should stay below Z_target across frequency range

### Simulation Tools

- **SPICE**: Simulate PDN impedance with parasitics
- **ADS/Keysight**: Advanced PDN analysis
- **HyperLynx**: PCB power integrity simulation

## Related Rules

- **Via Stitching**: Must have GND vias near decoupling capacitors
- **Ground Plane Continuity**: Solid ground plane required for effective decoupling
- **Trace Width**: Power traces must handle peak current

## References

- **IPC-2221**: PCB design standard (capacitor placement guidelines)
- **Intel PDN Design Guidelines**: Power delivery network best practices
- **Xilinx UG483**: "7 Series FPGAs PCB Design Guide" (decoupling examples)
- **Henry Ott's "Electromagnetic Compatibility Engineering"**: Decoupling theory
- **Eric Bogatin's "Signal & Power Integrity - Simplified"**: PDN impedance analysis
- **Istvan Novak's "Power Integrity for I/O Interfaces"**: Advanced PDN design

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Initial implementation with smart net matching and individual violation grouping |
