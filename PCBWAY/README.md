# Design Rules for PCBWay

**PCBWay** is a global PCB manufacturer headquartered in Shenzhen, China, offering:
- **Advanced capabilities**: HDI, rigid-flex, metal-core PCBs
- **Quality**: ISO 9001:2015, IPC-Class-2/3, UL certification
- **Materials**: FR4, Rogers, Taconic, aluminum-backed, flexible substrates
- **Services**: PCB fabrication, assembly, 3D printing, CNC machining, injection molding

## Manufacturing Capabilities

### Standard Service
- **Layers**: 1-32 layers (up to 40 layers custom available)
- **Board size**: Min 5×5mm, Max 610×1200mm (custom larger available)
- **Board thickness**: 0.2mm - 6.0mm (standard), up to 10mm custom
- **Copper weight**: 0.5oz, **1oz (35µm)** standard, 2oz, 3oz, 4oz, 6oz, 8oz, 10oz available
- **Surface finish**:
  - HASL (Hot Air Solder Leveling)
  - LeadFree HASL
  - **ENIG** (Electroless Nickel Immersion Gold) - recommended
  - OSP (Organic Solderability Preservative)
  - Immersion Silver, Immersion Tin
  - Hard Gold (for edge connectors, wear resistance)
  - ENEPIG (for wire bonding and gold wire attachment)

### Design Rules (Standard Service)

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Track width | 0.1mm (4 mil) | 0.15mm (6 mil) | 0.075mm (3 mil) for advanced HDI |
| Track spacing | 0.1mm (4 mil) | 0.15mm (6 mil) | Copper-to-copper clearance |
| Via hole diameter | 0.25mm | 0.3mm | Min 0.1mm for laser-drilled microvias |
| Via annular ring | 0.125mm | 0.15mm | Drill-to-pad offset |
| PTH hole diameter | 0.25mm | 0.3mm | Through-hole component leads |
| Pad-to-hole ratio | 1.4:1 | 2:1 | Pad diameter / hole diameter |
| Solder mask bridge | 0.06mm | 0.1mm | Between adjacent pads (HDI: 0.05mm) |
| Solder mask expansion | 0.05mm | 0.1mm | Pad to mask opening |
| Silkscreen width | 0.1mm | 0.15mm | Line and text thickness |
| Silkscreen-to-pad clearance | 0.1mm | 0.15mm | Prevent silkscreen on pads |
| Board outline clearance | 0.1mm | 0.3mm | Components to edge |

### Advanced Capabilities

#### HDI (High-Density Interconnect)
- **Microvia diameter**: 0.1mm (4 mil) laser-drilled
- **Via-in-pad**: Filled and plated for BGA fanout
- **Build-up layers**: 1+N+1, 2+N+2, 3+N+3 stackup
- **Aspect ratio**: Up to 10:1 (depth:diameter)
- **Applications**: Smartphones, tablets, high-density designs

#### Impedance Control
- **Tolerance**: ±10% standard, ±5% for critical RF designs
- **Supported impedances**: 25Ω - 120Ω (single-ended and differential)
- **Stackup design**: PCBWay provides impedance calculator and stackup recommendations
- **Testing**: 100% coupon testing with TDR (Time-Domain Reflectometry)

#### Rigid-Flex PCB
- **Flex layers**: 1-6 layers flexible substrate (polyimide)
- **Rigid layers**: 2-20 layers FR4
- **Bend radius**: ≥ 10× flex thickness (dynamic), ≥ 6× (static)
- **Applications**: Wearables, aerospace, medical devices

#### Metal-Core PCB (MCPCB)
- **Substrate**: Aluminum or copper base (1-3mm thick)
- **Thermal conductivity**: 1-8 W/m·K
- **Copper layers**: 1-2 layers (35µm - 105µm)
- **Applications**: LED lighting, power electronics, motor controllers

### Special Features
- **Gold fingers**: Hard gold (5-30µin) or ENIG for edge connectors
- **Castellated holes**: Half-cut vias on board edges for module assembly
- **Countersunk holes**: Flush mounting for screws
- **Blind/buried vias**: Available for multilayer boards (4+ layers)
- **Back drilling**: Stub removal for high-speed signals (>5 Gbps)
- **Peelable solder mask**: Removable mask for selective plating areas

## KiCad DRC File

The `PCBWay.kicad_dru` file in this directory contains pre-configured design rules matching PCBWay standard service capabilities.

### How to Use in KiCad

1. Open your PCB design in KiCad PCB Editor
2. Go to **Tools → Design Rules Checker**
3. Click **Load Custom Rules**
4. Select `PCBWay.kicad_dru`
5. Click **Run DRC**
6. Review and fix any violations before generating Gerbers

### Included Rules

The DRC file checks:
- ✅ Minimum track width (0.1mm)
- ✅ Minimum spacing between copper features (0.1mm)
- ✅ Via and hole sizes (min 0.25mm)
- ✅ Annular ring requirements (min 0.125mm)
- ✅ Solder mask clearances and bridges
- ✅ Silkscreen clearance from pads and edges
- ✅ Board outline to component spacing
- ✅ Impedance-controlled trace widths (if specified)

### Common Design Mistakes

❌ **Do NOT**:
- Use track widths < 0.1mm without ordering HDI service
- Create solder mask slivers < 0.06mm between pads
- Place vias < 0.25mm without specifying microvia service
- Assume impedance without stackup calculation (contact PCBWay)
- Use differential pairs without verifying spacing/width for target impedance

✅ **DO**:
- Use impedance calculator for RF and high-speed designs
- Add teardrops to vias for better reliability (especially HDI)
- Specify controlled impedance on order (provide target Ω)
- Use via-in-pad with plating/filling for BGA packages
- Consider back drilling for signals > 5 Gbps (SerDes, PCIe Gen3+)
- Use ENIG finish for fine-pitch components (QFN, BGA, 0201)

## Ordering Tips

### File Preparation
1. **Gerber format**: Use RS-274X or X2 format (preferred)
2. **Required files**:
   - `.GTL` - Top copper layer
   - `.GBL` - Bottom copper layer
   - `.G1`, `.G2`, ... - Inner layers (for multilayer)
   - `.GTO` - Top silkscreen
   - `.GBO` - Bottom silkscreen
   - `.GTS` - Top solder mask
   - `.GBS` - Bottom solder mask
   - `.GML` or `.GKO` - Board outline
   - `.TXT` - Drill file (Excellon format)
3. **Stackup file**: Include layer stackup diagram (especially for impedance control)
4. **Compression**: ZIP all files together
5. **Upload**: Use PCBWay instant quote tool

### Special Requirements Documentation

**For impedance control**:
- Provide target impedance (e.g., 50Ω single-ended, 100Ω differential)
- Specify dielectric material (FR4 standard, Rogers for RF)
- Include test coupon on panel for verification

**For HDI designs**:
- Specify microvia type (0.1mm, 0.15mm laser-drilled)
- Indicate via-in-pad locations (filled and plated)
- Provide cross-section diagram with build-up layers

**For rigid-flex**:
- Mark flex and rigid zones clearly on outline layer
- Specify bend radius and flex cycles (dynamic vs static)
- Include stiffener locations and material

### Cost Optimization
- **Panelization**: Combine multiple boards (max 610×1200mm)
- **Standard stackup**: Use common stackups (4-layer: 1.6mm FR4)
- **Standard colors**: Green is cheapest (also blue, red, white, black, yellow, matte black, matte green)
- **Avoid upcharges**: Gold fingers, impedance control, special materials add cost

### Lead Time
- **Standard**: 3-5 days production + shipping
- **Expedited**: 24-48 hours available (extra cost)
- **DHL/FedEx**: 3-7 days worldwide shipping
- **Economy shipping**: 7-21 days (budget option)

## Case Studies

### Example 1: High-Speed DDR4 Design
- **Requirements**: 6-layer board, 1.6mm thickness, 100Ω differential impedance
- **Stackup**: Sig-GND-Sig-PWR-GND-Sig
- **DRC settings**: 0.1mm track/space, 0.3mm vias
- **Finish**: ENIG (fine-pitch BGA)
- **Result**: ±8% impedance tolerance, no signal integrity issues

### Example 2: 100W LED Driver (MCPCB)
- **Requirements**: 2-layer aluminum-core PCB, 2mm Al substrate
- **Thermal**: 2 W/m·K thermal conductivity
- **Copper**: 70µm (2oz) for high current (10A)
- **DRC settings**: 0.4mm track width for power traces
- **Result**: Junction temp reduced by 30°C vs FR4

### Example 3: Wearable Fitness Tracker (Rigid-Flex)
- **Requirements**: 4-layer rigid-flex, 0.8mm rigid + 0.2mm flex
- **Flex zone**: 2-layer polyimide, dynamic bending (10,000 cycles)
- **Components**: BGA processor, LGA IMU on rigid zones
- **DRC settings**: 0.15mm track/space, stiffeners under components
- **Result**: Passed 50,000 bend cycle testing

## References

- **PCBWay website**: https://www.pcbway.com
- **Capabilities**: https://www.pcbway.com/capabilities.html
- **Impedance calculator**: https://www.pcbway.com/pcb_prototype/impedance_calculator.html
- **HDI guide**: https://www.pcbway.com/blog/PCB_Design_Tutorial/HDI_PCB_Design_Guide.html
- **Stackup designer**: https://www.pcbway.com/pcb_prototype/stackup_designer.html

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Initial DRC file for standard PCBWay service |

---

**Note**: Capabilities and pricing subject to change. Always verify current specifications on PCBWay website and contact their engineering team for complex designs requiring impedance control, HDI, or rigid-flex.
