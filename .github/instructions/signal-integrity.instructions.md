---
description: "Use when implementing, editing, or extending signal_integrity.py. Loads the phased implementation roadmap and key pcbnew API patterns for signal integrity checks."
applyTo: "src/signal_integrity.py"
---

# Signal Integrity Checker — Implementation Guide

`signal_integrity.py` (~2,400 lines) — **16 of 17 checks FULLY IMPLEMENTED** (~2,200 LOC working code).

**✅ Working Checks (Phases 1–4):**
- Net length limits per net class
- Exposed critical traces on outer layers
- Unconnected via pads (floating on internal layers)
- Trace proximity to reference plane edge (point-to-segment distance)
- **Trace proximity to board edge (Edge.Cuts outline, EMI + manufacturing)**
- Unreferenced traces (multi-point sampling, zone containment)
- Critical net isolation — single-ended (3W rule, guard trace exemption)
- Critical net isolation — differential pairs (4W rule, outer edge detection)
- Controlled impedance (microstrip + stripline + differential, IPC-2141A)
- Net stub detection (T-junctions, via stubs, connectivity graph)
- Differential pair length matching (P/N skew tolerance)
- Differential running skew (spacing variation analysis)
- Reference plane crossing at vias (plane transitions, stitching via search)
- Reference plane changing along traces (plane gaps, trace over split)

**❌ NOT IMPLEMENTED:**
- Net coupling / crosstalk check (stub with TODO comments at lines 2027-2034)

**Note**: All Phase 3/4 methods have been implemented except `_check_net_coupling()`. Helper functions are complete.

## Implementation Status

### Phase 1 — Easy (Basic Geometry & Filtering)
| Check | Method | Status |
|-------|--------|--------|
| Net Length Max | `_check_net_length()` | ✅ Implemented |
| Exposed Critical Traces | `_check_exposed_critical_traces()` | ✅ Implemented |
| Net Stub | `_check_net_stubs()` | ❌ Stub — implement next |
| Unconnected Via Pads | `_check_unconnected_via_pads()` | ✅ Implemented |

### Phase 2 — Medium (Spatial Analysis)
| Check | Method | Status |
|-------|--------|--------|
| Trace Near Plane Edge | `_check_trace_near_plane_edge()` | ✅ Implemented |
| Trace Near Board Edge | `_check_trace_near_board_edge()` | ✅ Implemented |
| Unreferenced Traces | `_check_unreferenced_traces()` | ✅ Implemented |
| Critical Net Isolation (SE) | `_check_critical_net_isolation_single()` | ✅ Implemented |
| Controlled Impedance | `_check_controlled_impedance()` | ✅ Implemented (microstrip + stripline + differential) |

### Phase 3 — Advanced (Complex Geometry)
| Check | Method | Line | Status |
|-------|--------|------|--------|
| Net Stub | `_check_net_stubs()` | 672+ | ✅ Implemented — connectivity graph, stub length calculation |
| Critical Net Isolation (Diff) | `_check_critical_net_isolation_differential()` | 1173+ | ✅ Implemented — outer edge detection, 4W rule |
| Crosstalk / Net Coupling | `_check_net_coupling()` | 2020-2035 | ❌ **STUB** — 5 TODO comments, returns 0 |
| Differential Pair Length Match | `_check_differential_pair_matching()` | 1288+ | ✅ Implemented — length matching, skew tolerance |
| Differential Running Skew | `_check_differential_running_skew()` | 1424+ | ✅ Implemented — spacing variation, CV analysis |

### Phase 4 — Expert (Multi-Layer)
| Check | Method | Line | Status |
|-------|--------|------|--------|
| Reference Plane Crossing | `_check_reference_plane_crossing()` | ~414 | ✅ Implemented — plane transitions, stitching via search |
| Reference Plane Changing | `_check_reference_plane_changing()` | ~459 | ✅ Implemented — trace over gaps, plane mapping |

### Helper Functions — Implementation Status

All Phase 3/4 helper methods have been implemented.

| Helper | Line | Used By | Status |
|--------|------|---------|--------|
| `_get_reference_planes(signal_layer)` | ~1990 | Phase 4 checks | ✅ Implemented — layer stack traversal |
| `_extract_plane_boundaries(plane_layer)` | ~2005 | Phase 4 checks | ✅ Implemented — zone outline extraction |
| `_calculate_trace_length(net)` | ~2020 | Phase 3 length-match | ✅ Implemented — segment + via length sum |
| `_build_connectivity_graph(net)` | ~2035 | Stub check | ✅ Implemented — 3D adjacency graph |
| `_find_parallel_segments(segment, max_distance, angular_tolerance)` | ~2111 | Net coupling | ✅ Implemented — spatial search (unused, caller is stub) |
| `_calculate_spacing_along_pair(net_p, net_n, sample_interval_mm)` | ~2130 | Running skew | ✅ Implemented — perpendicular distance sampling |

### Impedance Helpers — Partially Implemented

| Method | Line | Status |
|--------|------|--------|
| `_calculate_cpw_impedance(W, S, H, Er, has_ground_plane)` | 2352 | ⚠️ **APPROXIMATION** — Wen (1969) elliptic integral not implemented; uses simplified formula |

## pcbnew API Patterns

```python
# Iterate all tracks (segments + vias)
for track in self.board.GetTracks():
    if isinstance(track, pcbnew.PCB_TRACK):   # segment
        length = track.GetLength()
        layer  = track.GetLayer()
        net    = track.GetNetname()
    if isinstance(track, pcbnew.PCB_VIA):     # via
        span = (track.TopLayer(), track.BottomLayer())

# Sum net length
from collections import defaultdict
net_lengths = defaultdict(float)
for track in self.board.GetTracks():
    net_lengths[track.GetNetname()] += pcbnew.ToMM(track.GetLength())

# Detect outer (exposed) layers
OUTER_LAYERS = {pcbnew.F_Cu, pcbnew.B_Cu}
is_exposed = track.GetLayer() in OUTER_LAYERS

# Access copper zones (reference planes)
for zone in self.board.Zones():
    if zone.IsOnLayer(layer_id):
        outline = zone.GetOutline()  # SHAPE_POLY_SET

# Differential pair detection (regex pattern)
import re
DP_PATTERN = re.compile(r'^(.+)[_\-\.](P|N|\+|\-)$', re.IGNORECASE)
match = DP_PATTERN.match(net_name)
if match:
    base_name, polarity = match.group(1), match.group(2)
```

## Impedance Calculation Notes

The stackup reading API is already implemented inside the module — look for `_read_stackup()`. 
Use IPC-2141A formulas:
- **Microstrip**: $Z_0 = \frac{87}{\sqrt{\varepsilon_r + 1.41}} \ln\left(\frac{5.98h}{0.8w + t}\right)$
- **Stripline**: $Z_0 = \frac{60}{\sqrt{\varepsilon_r}} \ln\left(\frac{4b}{0.67\pi(0.8w + t)}\right)$

## Mandatory Patterns

- All thresholds from `self.config.get('key', default)` — never hardcode
- All coordinates via `pcbnew.FromMM()` / `pcbnew.ToMM()`
- Draw violations with injected `draw_marker_func`, not directly
- Each `_check_*()` method ≤ 50 lines; extract helpers as needed
- The main `check()` `try/except` already wraps each sub-call — individual methods do NOT need their own try/except
