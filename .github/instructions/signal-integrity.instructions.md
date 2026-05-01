---
description: "Use when implementing, editing, or extending signal_integrity.py. Loads the phased implementation roadmap and key pcbnew API patterns for signal integrity checks."
applyTo: "src/signal_integrity.py"
---

# Signal Integrity Checker — Implementation Guide

`signal_integrity.py` (~2,400 lines) — **Phases 1–2 FULLY IMPLEMENTED** (~1,235 LOC working code), Phases 3–4 are stubs.

**✅ Working Checks (Phase 1/2)**:
- Net length limits per net class
- Exposed critical traces on outer layers
- Unconnected via pads (floating on internal layers)
- Trace proximity to reference plane edge (point-to-segment distance)
- **Trace proximity to board edge (Edge.Cuts outline, EMI + manufacturing)**
- Unreferenced traces (multi-point sampling, zone containment)
- Critical net isolation (3W rule, guard trace exemption)
- Controlled impedance (microstrip + stripline + differential, IPC-2141A)

**Note**: Some implemented methods have **stale `TODO: Implementation needed` docstrings** — these have been updated. Always read the method body to verify actual implementation status.

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
| Net Stub | `_check_net_stubs()` | 672 | ❌ Stub — body is `# TODO` comments only, returns 0 |
| Critical Net Isolation (Diff) | `_check_critical_net_isolation_differential()` | 1173 | ❌ Stub — body is `# TODO` comments only, returns 0 |
| Crosstalk / Net Coupling | `_check_net_coupling()` | 1225 | ❌ Stub — body is `# TODO` comments only, returns 0 |
| Differential Pair Length Match | `_check_differential_pair_matching()` | 1288 | ❌ Stub — body is `# TODO` comments only, returns 0 |
| Differential Running Skew | `_check_differential_running_skew()` | 1424 | ❌ Stub — body is `# TODO` comments only, returns 0 |

### Phase 4 — Expert (Multi-Layer)
| Check | Method | Line | Status |
|-------|--------|------|--------|
| Reference Plane Crossing | `_check_reference_plane_crossing()` | ~414 | ❌ Stub — body is `# TODO` comments only, returns 0 |
| Reference Plane Changing | `_check_reference_plane_changing()` | ~459 | ❌ Stub — body is `# TODO` comments only, returns 0 |

### Helper Stubs — Required by Phase 3/4 Checks

These helper methods exist in the file but return empty/zero results. Implement these **before** the parent check methods.

| Helper | Line | Used By | What It Must Return |
|--------|------|---------|---------------------|
| `_get_reference_planes(signal_layer)` | 1990 | Phase 4 checks | `list[int]` — layer IDs of adjacent copper planes |
| `_extract_plane_boundaries(plane_layer)` | 2005 | Phase 4 checks | `list[SHAPE_POLY_SET]` — polygons of copper zones on layer |
| `_calculate_trace_length(net)` | 2020 | Phase 3 length-match | `float` mm — sum of all track segments + via heights |
| `_build_connectivity_graph(net)` | 2035 | Stub check, coupling | `dict` adjacency graph: `{point → [adjacent_points]}` |
| `_find_parallel_segments(segment, max_distance, angular_tolerance)` | 2111 | Net coupling | `list[PCB_TRACK]` — segments within distance running parallel |
| `_calculate_spacing_along_pair(net_p, net_n, sample_interval_mm)` | 2130 | Running skew | `list[float]` — spacing samples between P/N traces |

### Impedance Helpers — Partially Implemented

| Method | Line | Status |
|--------|------|--------|
| `_calculate_cpw_impedance(W, S, H, Er, has_ground_plane)` | 2352 | ⚠️ Stub — elliptic integral (Wen 1969) not yet coded; returns approximation only |

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
