# PCB Clearance & Creepage Quick Reference Card
# IEC60664-1 / IPC2221

**Status:** ✅ Implementation Active (Use with EMC Auditor Plugin)  
**Last Updated:** February 13, 2026

**Conditions:** Overvoltage Category II, Pollution Degree 2, Material Group II (FR4), Altitude <2000m

---

## ⚡ Common Voltage Scenarios (IEC60664-1)

### Extra Low Voltage (ELV / SELV) - Safe to Touch
| From | To | Clearance | Creepage | Notes |
|------|-----|-----------|----------|-------|
| 3.3V | GND | 0.13mm | 0.13mm | Logic level |
| 5V | GND | 0.13mm | 0.13mm | USB, logic |
| 12V | GND | 0.5mm | 0.4mm | Automotive |
| 24V | GND | 0.5mm | 0.5mm | Industrial, PoE |
| 48V | GND | 0.6mm | 0.8mm | Telecom (SELV max) |

### Low Voltage (LV) - Basic Insulation
| From | To | Clearance | Creepage | Notes |
|------|-----|-----------|----------|-------|
| 100V | GND | 1.0mm | 1.25mm | DC bus |
| 120V AC | GND | 1.5mm | 1.8mm | US mains |
| 230V AC | GND | 2.5mm | 3.2mm | EU mains |
| 400V | GND | 4.0mm | 4.0mm | 3-phase industrial |

### Safety-Critical - Reinforced Insulation (2× Basic)
| From | To | Clearance | Creepage | Notes |
|------|-----|-----------|----------|-------|
| 230V AC | SELV | **6.0mm** | **8.0mm** | ⚠️ Mains to safe |
| 230V AC | Touch | **6.0mm** | **8.0mm** | ⚠️ User safety |
| 400V | SELV | **8.0mm** | **10.0mm** | ⚠️ High voltage isolation |

---

## 🛠️ IPC2221 Quick Values (Alternative Standard)

### External Layers (Uncoated)
| Voltage Range | Minimum Spacing |
|---------------|-----------------|
| 0-30V DC | 0.13mm (5 mil) |
| 31-50V | 0.13mm |
| 51-100V | 0.25mm (10 mil) |
| 101-150V | 0.4mm (16 mil) |
| 151-300V | 0.8mm (32 mil) |
| 301-500V | 1.5mm (60 mil) |

### Internal Layers (Coated/Embedded)
| Voltage Range | Minimum Spacing |
|---------------|-----------------|
| 0-50V | 0.1mm (4 mil) |
| 51-100V | 0.2mm (8 mil) |
| 101-300V | 0.4mm (16 mil) |
| 301-500V | 1.27mm (50 mil) |

---

## 🎯 Design Rules for Your PCB

### Recommended Minimums (With 20% Safety Margin)

**For Standard Electronics:**
```
3.3V / 5V logic:     0.15mm (6 mil)   ← PCB fab minimum
12V / 24V power:     0.6mm            ← Play it safe
48V (SELV limit):    0.75mm           ← Industrial standard
```

**For Mains-Powered Equipment:**
```
230V AC mains:       3.0mm clearance, 4.0mm creepage (basic)
230V AC to SELV:     7.2mm clearance, 9.6mm creepage (reinforced) ⚠️
```

**For High Voltage:**
```
400V DC bus:         4.8mm clearance, 6.0mm creepage
600V:                6.6mm clearance, 6.7mm creepage
```

---

## ⚠️ Critical Safety Zones

### DO NOT Cross (Without Proper Isolation):
1. **Mains AC ↔ SELV** - ALWAYS use reinforced insulation (2× distance)
2. **Mains AC ↔ User Touch** - ALWAYS reinforced insulation
3. **High Voltage ↔ Microcontroller** - Basic + supplementary OR reinforced

### Breaking Creepage Paths:
- **Slots/Cutouts:** Infinite creepage (you MUST route around board edge)
- **Routed Grooves:** Increases creepage distance = 2×depth + width
- **Isolation Barriers:** Physical plastic walls improve safety

---

## 🔧 Practical Tips

### Boost Your Clearance:
1. **Use opposite PCB sides** - Layer 1 (mains) vs Layer 4 (SELV) = max distance
2. **Add keepout zones** - Force router to maintain clearance
3. **Conformal coating** - Reduces creepage by ~30-50% (check with certifier)
4. **Increase PCB thickness** - 1.6mm → 2.4mm for better isolation

### PCB Fab Constraints:
| Feature | Standard | Advanced |
|---------|----------|----------|
| Min trace/space | 0.15mm (6 mil) | 0.10mm (4 mil) |
| Min clearance | 0.15mm | 0.10mm |
| Layer count | 2-6 layers | 8-20 layers |
| Board thickness | 1.6mm | 0.4-6.0mm |

### When to Use Each Standard:
- **IEC60664-1**: Safety certification (UL, CE, TÜV), medical, mains-powered
- **IPC2221**: General electronics, non-safety, manufacturability focus
- **Both**: Use most conservative value (typically IEC60664-1 for higher voltages)

---

## 📋 Quick Config for Your Design

### Edit `emc_rules.toml`:

**For standard industrial equipment (24V):**
```toml
[clearance_creepage]
enabled = true
standard = "IEC60664-1"
overvoltage_category = "II"
pollution_degree = 2
material_group = "II"  # FR4
safety_margin_factor = 1.2

# Define your voltages:
[[clearance_creepage.voltage_domains]]
name = "24V_POWER"
voltage_rms = 24
net_patterns = ["24V", "+24V", "VBUS"]
```

**For mains-powered equipment (230V AC):**
```toml
[[clearance_creepage.voltage_domains]]
name = "MAINS_LIVE"
voltage_rms = 230
net_patterns = ["AC_L", "MAINS_L", "LINE"]
requires_reinforced_insulation = true  # Critical!

[[clearance_creepage.voltage_domains]]
name = "ISOLATED_5V"
voltage_rms = 5
net_patterns = ["5V_ISO", "SELV_5V"]

# Safety requirement:
[[clearance_creepage.isolation_requirements]]
domain_a = "MAINS_LIVE"
domain_b = "ISOLATED_5V"
isolation_type = "reinforced"
min_clearance_mm = 6.0  # 2× basic for 230V
min_creepage_mm = 8.0
```

---

## 🧪 Verification Checklist

Before PCB manufacturing:
- [ ] Run EMC Auditor plugin
- [ ] Check User.Comments layer for violations
- [ ] Review Gerber files at 1:1 zoom
- [ ] Measure critical clearances with calipers on first prototype
- [ ] Hi-pot test at required voltage (if safety-critical)

---

## 📚 Standard References

- **IEC 60664-1:2020** - Primary safety standard
- **IPC-2221B:2012** - PCB design standard
- **UL 60950-1** - IT equipment safety (references IEC60664)
- **UL 62368-1** - Audio/video equipment safety
- **EN 60664-1** - European harmonized standard

---

## 🆘 Common Mistakes

❌ **Using trace width as clearance** - Different rules!  
✅ Use edge-to-edge distance, not center-to-center

❌ **Forgetting altitude** - Above 2000m needs 25-60% more clearance  
✅ Check your deployment location

❌ **Assuming solder mask = insulation** - It's NOT rated!  
✅ Measure copper-to-copper, mask is bonus

❌ **Basic insulation for mains-to-SELV** - DANGEROUS!  
✅ Always use reinforced (2×) for safety barriers

❌ **Ignoring creepage** - Surface tracking causes fires!  
✅ Check both clearance AND creepage

---

**Plugin Config:** `emc_rules.toml`  
**Full Guide:** `CLEARANCE_CREEPAGE_GUIDE.md`  
**Last Updated:** February 6, 2026
