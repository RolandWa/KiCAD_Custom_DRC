# Isolation Requirements Analysis

## Configuration Review (Material Group II + Pollution Degree 2)

### 1. MAINS_L (230V) ↔ EXTRA_LOW_VOLTAGE (5V): **reinforced**
- **Configured**: Clearance 6.0mm, Creepage 8.0mm
- **IEC60664-1 @ 230V Basic**: Clearance 2.5mm, Creepage 2.5mm
- **IEC60664-1 @ 230V Reinforced** (2× basic): Clearance 5.0mm, Creepage 5.0mm
- **Analysis**: ✅ **MORE CONSERVATIVE** than standard
  - Clearance: 6.0mm > 5.0mm (20% extra margin)
  - Creepage: 8.0mm > 5.0mm (60% extra margin)
- **Justification**: Appropriate for mains-to-SELV isolation where safety is critical

### 2. HIGH_VOLTAGE_DC (400V) ↔ LOW_VOLTAGE_DC (24V): **basic**
- **Configured**: Clearance 4.0mm, Creepage 5.0mm
- **Voltage difference**: 376V ≈ 400V
- **IEC60664-1 @ 400V Basic**: Clearance 4.0mm, Creepage 4.0mm
- **Analysis**: ✅ **MATCHES OR EXCEEDS** standard
  - Clearance: 4.0mm = 4.0mm (exact match)
  - Creepage: 5.0mm > 4.0mm (25% extra margin)
- **Justification**: Extra creepage margin appropriate for high voltage DC

### 3. MAINS_L (230V) ↔ GROUND (0V): **basic**
- **Configured**: Clearance 2.5mm, Creepage 3.2mm
- **IEC60664-1 @ 230V Basic**: Clearance 2.5mm, Creepage 2.5mm
- **Analysis**: ✅ **MORE CONSERVATIVE** than standard
  - Clearance: 2.5mm = 2.5mm (exact match)
  - Creepage: 3.2mm > 2.5mm (28% extra margin) - actually matches 300V table entry!
- **Justification**: Conservative approach for mains-to-ground isolation

## ⚠️ CRITICAL ISSUE: Double Safety Margin Application

The report shows:
```
MAINS_L ↔ EXTRA_LOW_VOLTAGE: Required: 7.20mm (reinforced)
```

But configuration specifies: `min_clearance_mm = 6.0`

**Calculation**: 6.0mm × 1.2 (safety_margin_factor) = **7.2mm**

### Problem:
The code is applying `safety_margin_factor = 1.2` to the **already-conservative** configured values in `isolation_requirements` table!

The configured values (6.0mm, 8.0mm, etc.) already include appropriate safety margins. Applying an additional 1.2× factor results in:
- Clearance: 6.0mm → 7.2mm (44% over IEC60664-1 reinforced!)
- Creepage: 8.0mm → 9.6mm (92% over IEC60664-1 reinforced!)

### Recommendation:
The `safety_margin_factor` should **ONLY** be applied to:
- Voltage-based table lookups (when no specific isolation_requirement is defined)
- **NOT** to explicit `isolation_requirements` entries (which are already specified with appropriate margins)

### Impact:
Current behavior makes requirements unnecessarily strict, causing false violations on otherwise compliant designs.

## Conclusion

✅ **Isolation requirements values are correct and appropriately conservative**

❌ **Code incorrectly applies safety_margin_factor to these pre-configured values**

**Fix needed**: In `_lookup_required_clearance()` function, skip applying `safety_margin_factor` when using `isolation_requirements` table.
