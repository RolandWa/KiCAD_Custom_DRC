# Ground Plane Rule

**Last Updated:** February 6, 2026  
**Status:** 🚧 Future Implementation (Configuration Ready)

## Purpose

Verifies ground plane continuity and adequate coverage area to ensure low-impedance return path for signals, effective EMI shielding, and thermal management. A solid ground plane is fundamental to PCB performance and EMC compliance.

## Rule Parameters

### Configuration Section
```toml
[ground_plane]
enabled = false  # Set to true when implementation is ready
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_coverage_percent` | 30.0 | Minimum ground plane area as percentage of total board area |
| `max_gap_mm` | 5.0 | Maximum allowable gap in ground plane (mm) |

## How It Will Work (Planned)

1. **Identify Ground Layers**: Detect layers designated as ground planes (typically Layer 2 in 4-layer boards)
2. **Calculate Coverage**: Measure total copper area on ground layers vs. total board area
3. **Gap Detection**: Scan for slots, cutouts, or discontinuities exceeding `max_gap_mm`
4. **Violation Marking**: If coverage < minimum or gap > maximum, draw violation markers

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
min_coverage_percent = 50.0  # Moderate coverage
max_gap_mm = 5.0  # Tolerate small routing channels

violation_message = "GND PLANE GAP > 5mm"
```

### High-Speed Digital Design
```toml
[ground_plane]
enabled = true
min_coverage_percent = 80.0  # High coverage required
max_gap_mm = 2.0  # Minimize gaps under signals

violation_message = "GND PLANE GAP > 2mm - SI RISK"
```

### Mixed-Signal Design (ADC/DAC)
```toml
[ground_plane]
enabled = true
min_coverage_percent = 75.0  # High coverage for noise immunity

# Allow intentional split between analog/digital
max_gap_mm = 10.0  # Wider tolerance for isolation slots

# Optional: Define separate analog and digital ground zones
analog_gnd_patterns = ["AGND", "GND_A"]
digital_gnd_patterns = ["DGND", "GND_D"]
require_single_point_connection = true

violation_message = "GND PLANE COVERAGE LOW OR UNINTENTIONAL GAP"
```

### RF/Microwave Design
```toml
[ground_plane]
enabled = true
min_coverage_percent = 95.0  # Near-complete coverage
max_gap_mm = 0.5  # Very strict gap control

violation_message = "GND PLANE COMPROMISED - RF PERFORMANCE RISK"
```

## Design Guidelines

### 4-Layer Stackup (Recommended)
```
Layer 1 (Signal):   Components, routing, controlled impedance
Layer 2 (Ground):   Solid ground plane (95%+ coverage)
Layer 3 (Power):    Power planes (VCC, 3V3, 5V zones)
Layer 4 (Signal):   Bottom-side components, routing

✅ Ground plane on Layer 2 provides reference for Layer 1 & 4
✅ Minimal gaps - only for critical via transitions
```

### 2-Layer Board (Compromised Ground)
```
Layer 1 (Top):      Components, signal routing
Layer 2 (Bottom):   GND pour + necessary routing

⚠️ Ground coverage typically 40-60% (routing reduces area)
⚠️ Use ground pour flood fill, prioritize GND over signals
⚠️ Add stitching vias every 10-20mm to maintain reference
```

### Correct Ground Plane Design
```
Top View:
┌─────────────────────────────────┐
│ Ground Plane Layer (95% copper) │
│                                  │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │ ← Solid copper
│  ▓▓▓[Via]▓▓▓▓▓▓▓▓▓[Via]▓▓▓▓▓▓  │   (minimal gaps)
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │
└─────────────────────────────────┘

✅ Continuous copper coverage
✅ Vias for layer transitions
✅ No unnecessary routing on GND layer
```

### Incorrect Ground Plane Design
```
Top View:
┌─────────────────────────────────┐
│ Ground Plane Layer (30% copper) │
│                                  │
│  ▓▓ ────── ▓▓▓ ────────╮ ▓▓▓▓  │ ← Signal traces
│  ▓  [Via]     [Via]  ──╯       │   cutting through
│  ▓▓▓ ────────────────── ▓▓▓    │   GND plane!
└─────────────────────────────────┘

❌ Traces routed on GND layer
❌ Large gaps break return path
❌ Poor EMI shielding
```

## Implementation Plan

### Phase 1: Coverage Calculation
```python
def check_ground_plane_coverage(board, config):
    """Calculate ground plane coverage percentage"""
    violations = []
    
    # Get board dimensions
    board_area = board.GetBoardEdgesBoundingBox().GetArea() / 1e6  # mm²
    
    # Identify ground layers
    for layer in [pcbnew.B_Cu, pcbnew.In1_Cu]:  # Bottom, inner layers
        gnd_area = 0
        
        # Sum area of all zones on this layer
        for zone in board.Zones():
            if zone.GetLayerSet().Contains(layer):
                net_name = zone.GetNetname()
                if "GND" in net_name.upper():
                    gnd_area += zone.GetBoundingBox().GetArea() / 1e6
        
        # Calculate coverage
        coverage_percent = (gnd_area / board_area) * 100
        min_coverage = config['ground_plane']['min_coverage_percent']
        
        if coverage_percent < min_coverage:
            violations.append({
                'layer': layer,
                'coverage': coverage_percent,
                'message': f"GND COVERAGE {coverage_percent:.1f}% < {min_coverage}%"
            })
    
    return violations
```

### Phase 2: Gap Detection
```python
def detect_ground_plane_gaps(board, config):
    """Find gaps in ground plane exceeding threshold"""
    violations = []
    max_gap_mm = config['ground_plane']['max_gap_mm']
    
    # For each ground zone, trace outline and find gaps
    for zone in board.Zones():
        net_name = zone.GetNetname()
        if "GND" in net_name.upper():
            outline = zone.Outline()
            
            # Detect discontinuities (simplified algorithm)
            for i in range(outline.PointCount() - 1):
                p1 = outline.GetPoint(i)
                p2 = outline.GetPoint(i + 1)
                gap_dist = (p2 - p1).EuclideanNorm() / 1e6  # mm
                
                if gap_dist > max_gap_mm:
                    violations.append({
                        'location': (p1 + p2) / 2,
                        'gap': gap_dist,
                        'message': f"GND GAP {gap_dist:.1f}mm"
                    })
    
    return violations
```

### Phase 3: Signal Layer Correlation
```python
def analyze_return_path_integrity(board, config):
    """Check if high-speed signals have continuous ground return"""
    violations = []
    
    # For each high-speed trace on top layer
    for track in board.GetTracks():
        if track.GetNetClasses() and "HighSpeed" in track.GetNetClasses():
            # Project track onto ground plane layer
            # Check for gaps directly underneath
            # (Complex geometry analysis required)
            pass  # Implementation TBD
    
    return violations
```

## Verification Methods

### Visual Inspection in KiCad

1. **3D Viewer**: Rotate board to see ground plane through layers
2. **Layer Manager**: Toggle visibility to inspect each layer
3. **Highlight Net**: Right-click GND net → "Highlight" to see all copper

### Simulation Tools

- **FastIE (Agilent)**: Power/ground plane impedance analysis
- **HyperLynx**: Ground bounce and EMI simulation
- **ANSYS Q3D**: Parasitic extraction and current distribution

### Measurement Techniques

- **TDR (Time-Domain Reflectometry)**: Detect impedance discontinuities
- **VNA (Vector Network Analyzer)**: Measure ground plane impedance vs. frequency
- **Near-field probe**: EMI scanning to find hot spots (gaps)

## Common Mistakes

### Mistake 1: Routing Signals on Ground Layer
**Problem**: Traces on ground layer create gaps in return path  
**Solution**: Reserve ground layer for copper pour only, route signals on outer layers

### Mistake 2: Power Connector Placement Over Gap
**Problem**: High current return path crosses ground plane gap  
**Solution**: Place power connectors over solid copper area

### Mistake 3: Thermal Reliefs on Ground Connections
**Problem**: Thermal reliefs increase ground impedance  
**Solution**: Use solid connection for ground vias (no thermal relief)

### Mistake 4: Isolated Ground Islands
**Problem**: Unconnected ground pours don't provide return path  
**Solution**: Verify all GND zones connect with stitching vias

## Ground Plane Best Practices

### Rule 1: Maximize Coverage
- Target 80%+ on dedicated ground layer
- Fill unused areas with ground pour
- Avoid unnecessary routing on ground layer

### Rule 2: Minimize Gaps
- Keep gaps < 2mm where possible
- NEVER route high-speed signals over gaps
- Use ground stitching vias at gap boundaries

### Rule 3: Layer Stackup
- 4-layer: Dedicate Layer 2 (inner) to ground
- 6-layer: Dedicate Layers 2 and 5 to ground
- 2-layer: Flood Layer 2 with ground, minimize routing

### Rule 4: Mixed-Signal Isolation
- Separate analog and digital ground zones
- Single-point connection (star ground)
- Analog ground continuous under ADC/DAC

### Rule 5: Via Stitching
- Place GND vias every 10-20mm
- Add GND vias near signal via transitions
- Use via fence around noisy sections

## Related Rules

- **Via Stitching**: Ensures ground continuity between layers
- **Clearance/Creepage**: Ground plane affects high-voltage isolation
- **Trace Width**: Ground return path must handle same current as power trace

## References

- **IPC-2221**: PCB design standard (layer stackup guidelines)
- **IPC-2226**: High-speed design guide (ground plane requirements)
- **Howard Johnson's "High-Speed Digital Design"**: Ground plane theory
- **Henry Ott's "Electromagnetic Compatibility Engineering"**: EMI shielding
- **Eric Bogatin's "Signal Integrity - Simplified"**: Return path analysis
- **Lee Ritchey's "Right the First Time"**: Stackup and grounding

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Configuration created, implementation pending |
