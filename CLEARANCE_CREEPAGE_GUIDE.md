# IEC60664-1 and IPC2221 Clearance/Creepage Implementation Guide

**Standards Reference:**
- **IEC60664-1**: Insulation coordination for equipment within low-voltage systems
- **IPC2221**: Generic Standard on Printed Board Design

**Last Updated:** February 6, 2026

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

**2D Surface Pathfinding Algorithm:**

```python
def calculate_creepage(pad_a, pad_b, board):
    """
    Calculate minimum surface distance along PCB.
    
    Must consider:
    - PCB traces, pads, copper pours as obstacles
    - Slots/cutouts BREAK creepage path (infinite distance)
    - Grooves/isolations increase path length
    - Different layers have different paths
    """
    
    # 1. Build obstacle map (all copper on same layer)
    copper_obstacles = get_copper_shapes(board, layer)
    
    # 2. Run A* pathfinding on PCB surface
    # Avoid crossing any copper that belongs to other nets
    path = astar_surface_path(
        start=pad_a.position,
        goal=pad_b.position,
        obstacles=copper_obstacles,
        layer=layer
    )
    
    # 3. Check for slots/cutouts that break the path
    if crosses_pcb_edge(path, board):
        return float('inf')  # Creepage broken
    
    return path.length
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

## Implementation Pseudocode

### Main Checking Function

```python
def check_clearance_creepage(board, marker_layer, config):
    """
    Complete IEC60664-1 / IPC2221 verification.
    """
    
    violations = 0
    voltage_domains = config['voltage_domains']
    isolation_reqs = config['isolation_requirements']
    safety_factor = config.get('safety_margin_factor', 1.2)
    
    # Step 1: Classify all nets into voltage domains
    net_to_domain = {}
    for domain in voltage_domains:
        for net in board.GetNetsByPattern(domain['net_patterns']):
            net_to_domain[net] = domain
    
    # Step 2: Find all pad/trace pairs from different domains
    for pad_a in board.GetAllPads():
        net_a = pad_a.GetNetname()
        domain_a = net_to_domain.get(net_a)
        if not domain_a:
            continue  # Unknown voltage domain
        
        for pad_b in board.GetAllPads():
            if pad_a == pad_b:
                continue
            
            net_b = pad_b.GetNetname()
            domain_b = net_to_domain.get(net_b)
            if not domain_b or domain_a == domain_b:
                continue  # Same domain or unknown
            
            # Step 3: Calculate actual distances
            actual_clearance = calculate_clearance(pad_a, pad_b, board)
            actual_creepage = calculate_creepage(pad_a, pad_b, board)
            
            # Step 4: Lookup required distances
            required = lookup_isolation_requirement(
                domain_a, domain_b, isolation_reqs, config
            )
            
            required_clearance = required['clearance'] * safety_factor
            required_creepage = required['creepage'] * safety_factor
            
            # Step 5: Check violations
            if config['check_clearance'] and actual_clearance < required_clearance:
                msg = config['violation_message_clearance'].format(
                    actual=actual_clearance,
                    required=required_clearance,
                    domainA=domain_a['name'],
                    domainB=domain_b['name']
                )
                draw_error_marker(board, pad_a.GetPosition(), msg, marker_layer)
                violations += 1
            
            if config['check_creepage'] and actual_creepage < required_creepage:
                msg = config['violation_message_creepage'].format(
                    actual=actual_creepage,
                    required=required_creepage,
                    domainA=domain_a['name'],
                    domainB=domain_b['name']
                )
                draw_error_marker(board, pad_a.GetPosition(), msg, marker_layer)
                violations += 1
    
    return violations


def lookup_isolation_requirement(domain_a, domain_b, isolation_reqs, config):
    """
    Find required clearance/creepage for two domains.
    """
    
    # Check if specific requirement defined
    for req in isolation_reqs:
        if (req['domain_a'] == domain_a['name'] and 
            req['domain_b'] == domain_b['name']) or \
           (req['domain_a'] == domain_b['name'] and 
            req['domain_b'] == domain_a['name']):
            return {
                'clearance': req['min_clearance_mm'],
                'creepage': req['min_creepage_mm'],
                'type': req['isolation_type']
            }
    
    # Calculate from voltage difference and standard tables
    voltage_diff = abs(domain_a['voltage_rms'] - domain_b['voltage_rms'])
    
    if config['standard'] == "IEC60664-1":
        clearance = interpolate_from_table(
            voltage_diff, 
            config['iec60664_clearance_table']
        )
        creepage = interpolate_from_table(
            voltage_diff,
            config['iec60664_creepage_table']
        )
    
    elif config['standard'] == "IPC2221":
        spacing = interpolate_from_table(
            voltage_diff,
            config['ipc2221_spacing_table']
        )
        clearance = spacing
        creepage = spacing  # IPC2221 doesn't distinguish
    
    # Apply reinforced insulation factor
    if (domain_a.get('requires_reinforced_insulation') or 
        domain_b.get('requires_reinforced_insulation')):
        clearance *= 2.0
        creepage *= 2.0
    
    return {
        'clearance': clearance,
        'creepage': creepage,
        'type': 'basic'
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

## Next Steps for Implementation

1. **Implement basic clearance checking:**
   - Start with pad-to-pad distances only
   - Use 2D distance (ignore Z-axis initially)
   - Match nets to voltage domains

2. **Add creepage calculation:**
   - Implement surface pathfinding algorithm
   - Detect slots/cutouts
   - Handle different layers

3. **Add table interpolation:**
   - Parse voltage tables from TOML
   - Implement linear interpolation

4. **Add isolation requirement lookup:**
   - Check specific domain pairs first
   - Fall back to standard tables

5. **Apply safety factors:**
   - Reinforced insulation (2×)
   - Safety margin (1.2×)
   - Altitude correction

6. **Draw violation markers:**
   - Show actual vs required distances
   - Color-code by severity
   - Link to standard reference

7. **Generate report:**
   - Summary of all domain pairs
   - Minimum distance found for each
   - Pass/fail status

---

**Last Updated:** February 6, 2026  
**Configuration File:** `emc_rules.toml`  
**Plugin File:** `emc_auditor_plugin.py`
