# EMC Auditor Plugin for KiCad

**Version:** 1.0.0  
**KiCad Version:** 9.0.7+  
**Last Updated:** February 6, 2026

## Overview

The EMC Auditor plugin automatically checks your PCB design for electromagnetic compatibility (EMC) violations and visually marks them on the board. All rules are configurable via the `emc_rules.toml` file.

## Features

✅ **Via Stitching Verification** - Ensures critical signal vias have nearby GND return vias  
✅ **Decoupling Capacitor Proximity** - Verifies IC power pins have nearby decoupling caps  
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
✅ **Extensible Architecture** - Easy to add new EMC rules

## Available Rules and Documentation

The EMC Auditor plugin includes both **implemented** and **planned** rules. Each rule has dedicated documentation:

### ✅ Implemented Rules

| Rule | Status | Documentation | Description |
|------|--------|---------------|-------------|
| **Via Stitching** | ✅ Active | [VIA_STITCHING.md](VIA_STITCHING.md) | Ensures critical signal vias have nearby GND return vias within configurable distance (default 2mm). Prevents EMI radiation and maintains signal integrity. |
| **Decoupling Capacitors** | ✅ Active | [DECOUPLING.md](DECOUPLING.md) | Verifies IC power pins have decoupling capacitors within configurable distance (default 3mm). Uses **smart net matching** - only checks capacitors on the same power rail. Includes visual arrows to nearest cap. |

### 🚧 Planned Rules (Configuration Ready)

| Rule | Status | Documentation | Description |
|------|--------|---------------|-------------|
| **Clearance & Creepage** | 🚧 Config Ready | [CLEARANCE_CREEPAGE_GUIDE.md](CLEARANCE_CREEPAGE_GUIDE.md)<br>[CLEARANCE_QUICK_REF.md](CLEARANCE_QUICK_REF.md)<br>[CLEARANCE_VS_CREEPAGE_VISUAL.md](CLEARANCE_VS_CREEPAGE_VISUAL.md) | IEC60664-1 and IPC2221 electrical safety compliance. Verifies clearance (air gap) and creepage (surface path) between voltage domains. Supports reinforced insulation, overvoltage categories I-IV, pollution degrees 1-4. **Implementation pending**. |
| **Trace Width** | 🚧 Config Ready | [TRACE_WIDTH.md](TRACE_WIDTH.md) | Verifies power traces meet minimum width requirements based on current capacity. Includes IPC-2221 formulas for temperature rise and voltage drop calculations. **Implementation pending**. |
| **Ground Plane** | 🚧 Config Ready | [GROUND_PLANE.md](GROUND_PLANE.md) | Checks ground plane coverage percentage and detects gaps exceeding threshold. Ensures low-impedance return path and EMI shielding. **Implementation pending**. |

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

## Installation

1. Copy all files to your KiCad plugins directory:
   - Windows: `C:\Users\<username>\Documents\KiCad\9.0\3rdparty\plugins\`
   - Linux: `~/.local/share/kicad/9.0/3rdparty/plugins/`
   - macOS: `~/Library/Application Support/kicad/9.0/3rdparty/plugins/`

2. Required files:
   ```
   emc_auditor_plugin.py  (main plugin code)
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
enabled = true  # Set to true after implementing check function
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
