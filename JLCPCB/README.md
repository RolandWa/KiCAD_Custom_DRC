# Design Rules for JLCPCB

**JLCPCB** (Shenzhen JLC Electronics Co., Ltd.) is one of the world's largest PCB manufacturers, offering:
- **Fast turnaround**: 24-hour production for 2-layer boards
- **Low cost**: Starting at $2 for 10 pcs (100×100mm)
- **Quality**: IPC-Class-2 standard, UL certification
- **Assembly**: SMT assembly with 150,000+ component library

## Manufacturing Capabilities

### Standard Service
- **Layers**: 1-6 layers (up to 32 layers available)
- **Board size**: Min 20×20mm, Max 500×500mm (larger custom available)
- **Board thickness**: 0.4mm, 0.6mm, 0.8mm, 1.0mm, 1.2mm, **1.6mm** (standard), 2.0mm, 2.5mm, 3.2mm
- **Copper weight**: **1oz (35µm)** standard, 0.5oz, 2oz, 3oz, 4oz available
- **Surface finish**: 
  - HASL (Hot Air Solder Leveling) - default
  - LeadFree HASL
  - ENIG (Electroless Nickel Immersion Gold) - recommended for fine-pitch
  - OSP (Organic Solderability Preservative)
  - Immersion Silver, Immersion Tin, Hard Gold

### Design Rules (Standard Service)

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Track width | 0.127mm (5 mil) | 0.2mm (8 mil) | Smaller available with advanced service |
| Track spacing | 0.127mm (5 mil) | 0.2mm (8 mil) | Copper-to-copper clearance |
| Via hole diameter | 0.3mm | 0.4mm | Min 0.15mm for buried/blind vias |
| Via annular ring | 0.15mm | 0.2mm | Drill-to-pad offset |
| PTH hole diameter | 0.3mm | 0.4mm | Through-hole component leads |
| Pad-to-hole ratio | 1.5:1 | 2:1 | Pad diameter / hole diameter |
| Solder mask bridge | 0.07mm | 0.1mm | Between adjacent pads |
| Solder mask expansion | 0.05mm | 0.1mm | Pad to mask opening |
| Silkscreen width | 0.15mm | 0.2mm | Line and text thickness |
| Silkscreen-to-pad clearance | 0.15mm | 0.2mm | Prevent silkscreen on pads |
| Board outline clearance | 0.2mm | 0.5mm | Components to edge |

### Advanced Service (Tighter Tolerances)
- **Track width/spacing**: Down to 0.09mm (3.5 mil)
- **Via diameter**: Down to 0.2mm
- **HDI capabilities**: Laser-drilled microvias
- **Blind/buried vias**: Available for 4+ layer boards
- **Impedance control**: ±10% tolerance for 50Ω, 75Ω, 90Ω, 100Ω

### Special Features
- **Gold fingers**: Hard gold plating for edge connectors
- **Castellated holes**: Half-cut vias on board edges
- **Countersunk holes**: For flush mounting screws
- **Controlled impedance**: Available for RF and high-speed designs
- **Stiffeners**: FR4 or aluminum stiffeners for flex areas

## KiCad DRC File

The `JLCPCB.kicad_dru` file in this directory contains pre-configured design rules matching JLCPCB standard service capabilities.

### How to Use in KiCad

1. Open your PCB design in KiCad PCB Editor
2. Go to **Tools → Design Rules Checker**
3. Click **Load Custom Rules**
4. Select `JLCPCB.kicad_dru`
5. Click **Run DRC**
6. Review and fix any violations before generating Gerbers

### Included Rules

The DRC file checks:
- ✅ Minimum track width (0.127mm)
- ✅ Minimum spacing between copper features (0.127mm)
- ✅ Via and hole sizes (min 0.3mm)
- ✅ Annular ring requirements (min 0.15mm)
- ✅ Solder mask clearances and bridges
- ✅ Silkscreen clearance from pads and edges
- ✅ Board outline to component spacing

### Common Design Mistakes

❌ **Do NOT**:
- Use track widths < 0.127mm without ordering advanced service
- Place silkscreen text on pads (will be removed)
- Use vias < 0.3mm without specifying buried/blind via service
- Create solder mask slivers < 0.07mm between pads
- Place components < 0.2mm from board edge

✅ **DO**:
- Add teardrops to vias for better reliability
- Use 0.2mm (8 mil) as minimum for high-reliability designs
- Verify copper-to-edge clearance (0.2mm minimum)
- Check that all drill holes are ≥ 0.3mm
- Use ENIG finish for fine-pitch QFN/BGA packages

## Ordering Tips

### File Preparation
1. **Gerber format**: Use RS-274X or X2 format
2. **Required files**:
   - `.GTL` - Top copper layer
   - `.GBL` - Bottom copper layer
   - `.GTO` - Top silkscreen
   - `.GBO` - Bottom silkscreen
   - `.GTS` - Top solder mask
   - `.GBS` - Bottom solder mask
   - `.GML` or `.GKO` - Board outline
   - `.TXT` - Drill file (Excellon format)
3. **Compression**: ZIP all Gerber files together
4. **Upload**: Drag & drop to JLCPCB website

### Cost Optimization
- **Panelization**: Multiple designs per board (max 500×500mm)
- **Standard colors**: Green is cheapest (also blue, red, white, black, yellow)
- **Standard finish**: HASL or LeadFree HASL (no extra cost)
- **Avoid**: Gold fingers, impedance control, special materials (significant upcharge)

### Lead Time
- **Standard**: 24-48 hours production + shipping
- **Economic shipping**: 7-15 days (cheap)
- **DHL/FedEx**: 3-5 days (recommended for prototypes)

## References

- **JLCPCB website**: https://jlcpcb.com
- **Capabilities**: https://jlcpcb.com/capabilities/pcb-capabilities
- **SMT Assembly**: https://jlcpcb.com/smt-assembly
- **Help Center**: https://support.jlcpcb.com

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Initial DRC file for standard JLCPCB service |

---

**Note**: Capabilities and pricing subject to change. Always verify current specifications on JLCPCB website before ordering.
