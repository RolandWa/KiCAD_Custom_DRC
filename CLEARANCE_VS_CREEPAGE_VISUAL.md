# Clearance vs Creepage Visual Guide

**Status:** ✅ Implementation Active (Use with EMC Auditor Plugin)  
**Last Updated:** March 27, 2026
**Algorithm:** Dijkstra Waypoint Graph with Bbox Extremity Waypoints (v3.0)

---

## 📏 What's the Difference?

### CLEARANCE - Shortest path through AIR
```
Component A                      Component B
   [Pad]                            [Pad]
     |                                |
     |    <---- CLEARANCE ---->       |
     |    (straight line, 3D)         |
     |________________________________|
            THROUGH AIR
```

**Purpose:** Prevents electrical arcing/flashover through air  
**Measurement:** Shortest 3D straight-line distance  
**Critical for:** High voltage, transient protection  

---

### CREEPAGE - Shortest path along SURFACE
```
Component A                      Component B
   [Pad]                            [Pad]
     |_______________________________|
       ALONG PCB SURFACE (2D path)
           CREEPAGE DISTANCE
```

**Purpose:** Prevents surface tracking/carbonization  
**Measurement:** Shortest path following PCB surface  
**Critical for:** Contamination, humidity, long-term reliability  

---

## 🔍 Real-World Examples

### Example 1: Flat PCB (Simple Case)

```
  230V Pad              5V Pad
  ┌──┐                 ┌──┐
  │  │◄───────────────►│  │
  └──┘    8.0mm        └──┘
       (both equal)

  Flat PCB Surface
  ═══════════════════════════

CLEARANCE = 8.0mm (air gap)
CREEPAGE  = 8.0mm (surface path)
Result: SAME distance ✅
```

---

### Example 2: PCB with Components (Obstacle)

```
  230V Pad    Component   5V Pad
  ┌──┐       ┌─────────┐  ┌──┐
  │  │       │ [CHIP] │  │  │
  └──┘       └─────────┘  └──┘
    │                        │
    └────────────────────────┘

Top View:
  230V ────────────────── 5V
      (direct air path)

CLEARANCE = 10mm (straight line through air) ✅
CREEPAGE  = 18mm (must go AROUND chip) ⚠️
Result: Creepage LONGER than clearance
```

**Violation:** If required creepage is 15mm, clearance passes but creepage fails!

---

### Example 3: Slot in PCB (Path Broken)

```
  230V Pad        SLOT         5V Pad
  ┌──┐           ║  ║         ┌──┐
  │  │◄─────────►║  ║◄───────►│  │
  └──┘  6mm      ║  ║  6mm    └──┘
                 ║  ║
  PCB Surface    ║  ║   PCB Surface
  ═══════════════╝  ╚═══════════════

CLEARANCE = 6mm (across slot, through air) ✅
CREEPAGE  = INFINITE ⚠️ (path is broken!)

Result: Must route around entire board edge:
  
  ┌────────────────────────────────┐
  │230V Pad              5V Pad    │
  │  ┌──┐      SLOT      ┌──┐     │
  │  │  │      ║  ║      │  │     │
  │  └──┘◄─────║  ║─────►└──┘     │
  │      ╲     ║  ║     ╱          │
  │       ╲    ║  ║    ╱           │
  └────────╲───╝  ╚───╱────────────┘
            ╲          ╱
             ╲________╱
           CREEPAGE PATH
          (around board edge)
          = 80mm ⚠️
```

**Slot Effect:** Creepage becomes MUCH longer than clearance!

---

### Example 4: Routed Groove (Increased Distance)

```
Side View:                    Top View:

  230V         5V              230V ───[Groove]─── 5V
  Pad          Pad             Pad                 Pad
  ┌─┐          ┌─┐             ┌──┐               ┌──┐
  └─┘▼         └─┘             │  │               │  │
═════╗         ╔═════          └──┘               └──┘
     ║  GROOVE ║                    5mm direct
     ║  2mm    ║
     ║  wide   ║               Actual creepage path:
═════╝    ▲    ╚═════         
           └───────────         Pad → Down wall (1mm)
                                    → Across bottom (5mm)
CLEARANCE = 5mm (across top)        → Up wall (1mm)
CREEPAGE  = 1 + 5 + 1 = 7mm         = 7mm total
            (down + across + up)
```

**Groove Effect:** Creepage = width + 2×depth

---

## 🎯 Which is Critical When?

### Clearance Dominates (Higher Risk):
- ✅ **High voltage spikes** (lightning, switching transients)
- ✅ **Thin air** (high altitude >2000m)
- ✅ **Clean environment** (low pollution degree)
- ✅ **Dry conditions** (no moisture)

**Example:** 400V DC motor drive at 3000m altitude  
→ Clearance is the limiting factor

---

### Creepage Dominates (Higher Risk):
- ✅ **Contamination** (dust, metal particles, water)
- ✅ **High humidity** (condensation, salt spray)
- ✅ **Poor materials** (low CTI, phenolic boards)
- ✅ **Slots/grooves** (breaks surface path)

**Example:** 24V outdoor sensor in marine environment  
→ Creepage is the limiting factor

---

## 📊 Typical Clearance vs Creepage Comparison

| Voltage | Basic Clearance | Creepage (PD2, Mat II) | Ratio |
|---------|-----------------|------------------------|-------|
| 12V | 0.5mm | 0.4mm | 1.25× |
| 50V | 0.6mm | 0.8mm | 0.75× ⚠️ |
| 100V | 1.0mm | 1.25mm | 0.80× ⚠️ |
| 230V | 2.5mm | 3.2mm | 0.78× ⚠️ |
| 400V | 4.0mm | 4.0mm | 1.0× |
| 600V | 5.5mm | 5.6mm | 0.98× |

**Key Insight:** At ≤400V, creepage is often MORE RESTRICTIVE than clearance!

---

## 🛠️ How the Algorithm Finds the Shortest Creepage Path

### Dijkstra Waypoint Graph (v3.0)

The EMC Auditor uses a Dijkstra-based waypoint graph to find the shortest
surface path around PCB slots/cutouts.

```
  Step 1: Separate barriers              Step 2: Generate waypoints
  ┌────────────────────┐          ┌────────────────────┐
  │ Edge.Cuts = boundary   │          │  × × ×       × × × │
  │ (no waypoints here)   │          │  × SLOT ×   × SLOT × │
  │                        │          │  × × ×       × × × │
  │ Internal slots =       │          │                        │
  │ obstacles to route     │          │  Waypoints at bbox     │
  │ around (waypoints!)    │          │  extremities (0.1mm)   │
  └────────────────────┘          └────────────────────┘

  Step 3: Build visibility graph         Step 4: Dijkstra shortest path
  ┌────────────────────┐          ┌────────────────────┐
  │ S───WP1    WP5───G   │          │ S─►WP1              │
  │ │ ╲   SLOT  / │      │          │     │    SLOT         │
  │ │  WP2  WP4   │      │          │    WP2     WP5─►G  │
  │ │ /          \ │      │          │     │  SLOT /        │
  │ WP3    SLOT  WP6     │          │    WP3──WP4           │
  │ Edges where no slot   │          │ Shortest path found!  │
  │ crossing exists        │          │ 10.16mm (6 waypoints) │
  └────────────────────┘          └────────────────────┘
```

### Slot Extension = 2× Path Increase (Validated)

```
  Before (slot = 10mm):              After (slot = 11mm, +1mm):
  ┌───────────────┐              ┌────────────────┐
  │     ╭──╮        │              │      ╭──╮         │
  │ S─►│SL│─►G    │              │ S──►│SL│──►G    │
  │     ╰──╯        │              │      ╰──╯         │
  └───────────────┘              └────────────────┘
  Path: 10.16mm                    Path: 12.15mm (+1.99mm)

  Δ = ~2mm = 2 × 1mm slot extension
  (path adds ~1mm on approach + ~1mm on departure)
```

---

## ⚠️ Common Design Mistakes

### ❌ Mistake 1: Only Checking Clearance
```
Designer: "5mm clearance to mains - good!"
Reality: Creepage = 12mm (goes around component) - FAIL! ⚠️
```

**Fix:** Always check BOTH clearance AND creepage

---

### ❌ Mistake 2: Measuring Center-to-Center
```
   Pad A (2mm dia)         Pad B (2mm dia)
      [●]◄────10mm────►[●]
      
Wrong: 10mm clearance ❌
Right: 10 - 1 - 1 = 8mm clearance ✅
       (edge to edge)
```

**Fix:** Measure from pad EDGES, not centers

---

### ❌ Mistake 3: Forgetting About Vias
```
Top Layer:    230V Pad ───────── [Via]
                                   │
Bottom Layer:                     │
                            5V Pad─┘

Creepage path:
  230V pad surface → via barrel → 5V pad
  = Top copper + barrel + bottom copper
```

**Fix:** Include via barrel length in creepage calculation

---

### ❌ Mistake 4: Assuming Solder Mask = Insulation
```
   230V Copper    0.05mm mask    5V Copper
   ┌─────────┐   ╱────────╲   ┌─────────┐
   │█████████│  │░░░░░░░░│  │█████████│
   └─────────┘   ╲────────╱   └─────────┘
       │           Solder           │
       │            Mask            │
       └──────► CLEARANCE ◄─────────┘
            (copper to copper)
```

**Solder mask is NOT rated insulation!**

**Fix:** Measure copper-to-copper; mask is a bonus

---

## 🔧 Practical Design Solutions

### Solution 1: Use Opposite Board Sides
```
Top Layer (Layer 1):     230V mains traces
                         ═══════════════════
                         
    [1.6mm FR4 board thickness]
    
Bottom Layer (Layer 4):  5V SELV traces
                         ═══════════════════

Clearance through board = √(lateral² + 1.6²)
Result: Maximum isolation in minimum space ✅
```

---

### Solution 2: Add Physical Barrier
```
  230V Zone         Plastic Wall         5V Zone
  ┌─────────┐      ║          ║      ┌─────────┐
  │ Mains   │      ║ Barrier  ║      │  SELV   │
  │ Traces  │◄────►║  5mm     ║◄────►│ Traces  │
  └─────────┘      ║ Height   ║      └─────────┘
═══════════════════╩══════════╩═══════════════════
         PCB             ▲
                         │
                    Allows closer
                   component placement
```

---

### Solution 3: Routed Slot (Break Creepage)
```
Before:                     After:
  230V ──── 5V              230V ║ ║ 5V
  (8mm creepage)            (slot breaks path)
                            
  ⚠️ Marginal              ✅ Infinite creepage
                              each side isolated
```

**Caution:** Slots weaken mechanical strength - use sparingly!

---

## 📐 Measurement Tools

### During Design (Software):
1. **KiCad DRC:** Set custom clearance rules per net class
2. **EMC Auditor Plugin:** Automated clearance/creepage verification
   - Dijkstra waypoint graph finds shortest surface path around slots
   - Debug visualization: `draw_creepage_path = true` shows routing path
   - Configurable slot layers via `slot_layer_names` in TOML
3. **3D Viewer:** Visual inspection of clearances

### After Manufacturing (Hardware):
1. **Calipers:** 0.01mm precision, measure suspected violations
2. **Microscope:** 10-50× magnification for tiny gaps
3. **Hi-Pot Tester:** Electrical verification (stress test at 2-4kV)

---

## 🎓 Summary: Key Takeaways

| Aspect | Clearance | Creepage |
|--------|-----------|----------|
| **Path** | Through air (3D) | Along surface (2D) |
| **Prevents** | Arcing, flashover | Tracking, carbonization |
| **Affected by** | Voltage, altitude, transients | Voltage, pollution, material |
| **Typical values** | 0.5-10mm | 0.4-15mm |
| **Broken by** | Nothing (air always present) | Slots, cutouts |
| **Increased by** | Components (3D obstacles) | Components, grooves, paths |

**Golden Rule:** ✅ **ALWAYS verify BOTH** clearance AND creepage!

**Critical Safety:** ⚠️ For mains-to-SELV, use **reinforced insulation** (2× basic)

---

**See Also:**
- [CLEARANCE_QUICK_REF.md](CLEARANCE_QUICK_REF.md) - Quick voltage reference tables
- [CLEARANCE_CREEPAGE_GUIDE.md](CLEARANCE_CREEPAGE_GUIDE.md) - Complete implementation guide
- [emc_rules.toml](emc_rules.toml) - Plugin configuration file

**Standards:**
- IEC 60664-1:2020 - Insulation coordination
- IPC-2221B:2012 - PCB design standard

**Last Updated:** March 27, 2026
