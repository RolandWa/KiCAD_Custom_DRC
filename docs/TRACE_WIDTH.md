# Trace Width Rule

**Last Updated:** February 6, 2026  
**Status:** 🚧 Future Implementation (Configuration Ready)

## Purpose

Verifies that power traces have sufficient width to handle expected current without excessive voltage drop or overheating. Proper trace sizing is critical for thermal management, voltage regulation, and preventing PCB damage.

## Rule Parameters

### Configuration Section
```toml
[trace_width]
enabled = false  # Set to true when implementation is ready
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `power_trace_min_width_mm` | 0.5 | Minimum trace width for power traces (mm) |
| `power_net_patterns` | ["VCC", "VDD", "PWR", "3V3", "5V"] | Power net name patterns |
| `current_per_width` | 1.0 | Current capacity per mm width for external layers (A/mm) |

## How It Will Work (Planned)

1. **Identify Power Traces**: Scan traces on nets matching `power_net_patterns`
2. **Measure Trace Width**: Get actual width of each trace segment
3. **Compare to Minimum**: Check if width meets `power_trace_min_width_mm`
4. **Current Capacity Check**: Calculate maximum safe current based on width
5. **Violation Marking**: If trace too narrow, draw marker at narrowest segment

## Trace Width Sizing Theory

### IPC-2221 Current Capacity Formula

**Formula**: A = (I / (k × ΔT^b))^(1/c)

Where:
- **A** = cross-sectional area (mil²)
- **I** = maximum current (A)
- **ΔT** = temperature rise (°C)
- **k, b, c** = constants based on layer:
  - External layer: k=0.048, b=0.44, c=0.725
  - Internal layer: k=0.024, b=0.44, c=0.725

**Simplified Rule of Thumb**:
- **External layer**: 1A per 0.5mm width (10°C rise, 1oz copper)
- **Internal layer**: 1A per 0.8mm width (10°C rise, 1oz copper)

### Factors Affecting Current Capacity

1. **Copper Weight**:
   - 0.5oz (17µm): 70% of 1oz capacity
   - 1oz (35µm): Standard (baseline)
   - 2oz (70µm): 2× capacity

2. **Allowed Temperature Rise**:
   - 10°C: Conservative (recommended)
   - 20°C: Moderate
   - 30°C: Aggressive (max for FR4)

3. **Trace Length**:
   - Short traces (<10mm): Can use smaller width
   - Long traces (>50mm): Voltage drop becomes critical

4. **Ambient Temperature**:
   - < 50°C: Standard sizing
   - 50-85°C: Derate by 20%
   - > 85°C: Derate by 40%

### Voltage Drop Calculation

**Formula**: V_drop = I × R = I × (ρ × L / A)

Where:
- **ρ** = copper resistivity (1.68×10⁻⁸ Ω·m at 20°C)
- **L** = trace length (m)
- **A** = cross-sectional area (m²)

**Typical Values**:
- **1oz copper, 1mm wide trace**: ~0.5 mΩ/mm
- **0.5oz copper, 0.5mm wide trace**: ~2 mΩ/mm

**Acceptable Voltage Drop**:
- **Digital power**: < 50mV (< 2% for 3.3V rail)
- **Analog power**: < 10mV (critical for ADC reference)
- **High current (>5A)**: < 100mV

## Recommended Configurations

### Low-Power Design (< 500mA)
```toml
[trace_width]
enabled = true
power_trace_min_width_mm = 0.3  # 300µm trace
power_net_patterns = ["3V3", "5V", "VCC", "VDD"]
current_per_width = 1.5  # 1.5A per mm (conservative)
violation_message = "TRACE TOO NARROW FOR LOW-POWER"
```

### Medium-Power Design (500mA - 2A)
```toml
[trace_width]
enabled = true
power_trace_min_width_mm = 0.5  # 500µm trace
power_net_patterns = ["3V3", "5V", "12V", "VCC", "VDD"]
current_per_width = 1.0  # 1A per mm (standard)
violation_message = "TRACE TOO NARROW FOR MED-POWER"
```

### High-Power Design (> 2A)
```toml
[trace_width]
enabled = true
power_trace_min_width_mm = 1.5  # 1.5mm trace
power_net_patterns = ["12V", "24V", "48V", "PWR_OUT", "MOTOR_PWR"]
current_per_width = 1.0  # 1A per mm (requires 2oz copper)
violation_message = "TRACE TOO NARROW FOR HIGH-POWER"
```

## Design Guidelines

### Correct Power Trace Sizing
```
3.3V @ 1A:
  Width: 0.5mm (external), 0.8mm (internal)
  Length: < 100mm
  Temperature rise: < 10°C
  Voltage drop: < 30mV

5V @ 3A:
  Width: 1.5mm (external), 2.5mm (internal)
  Length: < 50mm
  Temperature rise: < 10°C
  Voltage drop: < 50mV

12V @ 5A:
  Width: 3mm (external), 5mm (internal)
  OR use copper pour/plane
  Temperature rise: < 15°C
  Voltage drop: < 100mV
```

### Trace Width vs Current Chart

| Current | 10°C Rise | 20°C Rise | Layer Type | Copper Weight |
|---------|-----------|-----------|------------|---------------|
| 0.5A | 0.25mm | 0.15mm | External | 1oz |
| 1A | 0.5mm | 0.3mm | External | 1oz |
| 2A | 1.2mm | 0.8mm | External | 1oz |
| 3A | 2.0mm | 1.4mm | External | 1oz |
| 5A | 3.5mm | 2.5mm | External | 1oz |
| 10A | 8mm | 6mm | External | 1oz |
| 10A | 4mm | 3mm | External | 2oz |
| 20A | **Use plane** | **Use plane** | - | 2oz |

**Note**: Internal layers require ~1.5× wider traces for same current

## Implementation Plan

### Phase 1: Basic Width Check
```python
def check_trace_width(board, config):
    """Check if power traces meet minimum width requirement"""
    violations = []
    power_patterns = config['trace_width']['power_net_patterns']
    min_width_mm = config['trace_width']['power_trace_min_width_mm']
    
    for track in board.GetTracks():
        net_name = track.GetNetname()
        
        # Check if this is a power net
        if any(pattern in net_name.upper() for pattern in power_patterns):
            width_mm = track.GetWidth() / 1e6  # Convert to mm
            
            if width_mm < min_width_mm:
                violations.append({
                    'location': track.GetStart(),
                    'message': f"TRACE {width_mm:.2f}mm < {min_width_mm:.2f}mm",
                    'net': net_name
                })
    
    return violations
```

### Phase 2: Current Capacity Check
```python
def calculate_current_capacity(width_mm, copper_oz=1, temp_rise_c=10, is_external=True):
    """Calculate maximum current for given trace width"""
    # IPC-2221 formula implementation
    area_mil2 = (width_mm * 39.37) * (copper_oz * 1.4)  # Convert to mil²
    
    k = 0.048 if is_external else 0.024
    b = 0.44
    c = 0.725
    
    current_a = k * (temp_rise_c ** b) * (area_mil2 ** c)
    return current_a
```

### Phase 3: Voltage Drop Analysis
```python
def calculate_voltage_drop(current_a, length_mm, width_mm, copper_oz=1):
    """Calculate voltage drop along trace"""
    # Copper resistivity at 20°C
    rho = 1.68e-8  # Ω·m
    
    # Cross-sectional area
    thickness_m = copper_oz * 35e-6  # 35µm per oz
    width_m = width_mm / 1000
    area_m2 = thickness_m * width_m
    
    # Resistance
    length_m = length_mm / 1000
    resistance = rho * length_m / area_m2
    
    # Voltage drop
    v_drop = current_a * resistance
    return v_drop
```

## Verification Tools

### Online Calculators
- **4pcb.com Trace Width Calculator**: Simple interface, IPC-2221 based
- **Saturn PCB Toolkit**: Advanced trace impedance and current calculations
- **KiCad Calculator**: Built-in trace width calculator (Tools → Calculator)

### Thermal Simulation
- **ANSYS Icepak**: Professional thermal simulation
- **COMSOL Multiphysics**: FEA thermal analysis
- **Thermal camera**: Practical validation during prototyping

## Common Mistakes

### Mistake 1: Ignoring Copper Weight
**Problem**: Assuming all boards use 1oz copper  
**Solution**: Check fabrication specs, derate if 0.5oz or uprate if 2oz

### Mistake 2: Neck-Down at Vias
**Problem**: Wide trace narrows at via pad  
**Solution**: Use teardrops or keep via pad diameter ≥ trace width

### Mistake 3: Long Thin Traces
**Problem**: Voltage drop exceeds acceptable limit  
**Solution**: Calculate total resistance × current, verify V_drop < 50mV

### Mistake 4: Thermal Relief on Power Planes
**Problem**: Using thermal relief on power connections reduces current capacity  
**Solution**: Use solid connection (no thermal relief) for high-current nets

## Related Rules

- **Via Stitching**: Return current path must also be sized properly
- **Ground Plane**: GND return path resistance affects total system impedance
- **Clearance/Creepage**: Wider traces may require increased spacing

## References

- **IPC-2221**: Generic Standard on Printed Board Design
- **IPC-2152**: Standard for Determining Current Carrying Capacity in Printed Board Design
- **MIL-STD-275**: Printed Wiring for Electronic Equipment
- **Ulaby's "Circuits"**: Resistance and power dissipation fundamentals
- **Douglas Brooks' "Temperature Rise in PCB Traces"**: Detailed thermal analysis

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Configuration created, implementation pending |
