---
description: "Use when implementing, editing, or extending signal_integrity.py. Loads the phased implementation roadmap and key pcbnew API patterns for signal integrity checks."
applyTo: "signal_integrity.py"
---

# Signal Integrity Checker — Implementation Guide

`signal_integrity.py` (~2,400 lines) has Phases 1–2 largely implemented. Several `_check_*()` methods carry a stale `TODO: Implementation needed` docstring but contain working code — **read the method body before writing new code**. Phases 3–4 checks are genuine stubs that return 0.

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
| Unreferenced Traces | `_check_unreferenced_traces()` | ✅ Implemented |
| Critical Net Isolation (SE) | `_check_critical_net_isolation_single()` | ✅ Implemented |
| Controlled Impedance | `_check_controlled_impedance()` | ✅ Implemented (microstrip + stripline + differential) |

### Phase 3 — Advanced (Complex Geometry)
| Check | Method | Status |
|-------|--------|--------|
| Critical Net Isolation (Diff) | `_check_critical_net_isolation_differential()` | ❌ Stub |
| Crosstalk / Net Coupling | `_check_net_coupling()` | ❌ Stub |
| Differential Pair Length Match | `_check_differential_pair_matching()` | ❌ Stub |
| Differential Running Skew | `_check_differential_running_skew()` | ❌ Stub |

### Phase 4 — Expert (Multi-Layer)
| Check | Method | Status |
|-------|--------|--------|
| Reference Plane Crossing | `_check_reference_plane_crossing()` | ❌ Stub |
| Reference Plane Changing | `_check_reference_plane_changing()` | ❌ Stub |

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
