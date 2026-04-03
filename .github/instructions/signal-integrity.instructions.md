---
description: "Use when implementing, editing, or extending signal_integrity.py. Loads the phased implementation roadmap and key pcbnew API patterns for signal integrity checks."
applyTo: "signal_integrity.py"
---

# Signal Integrity Checker — Implementation Guide

`signal_integrity.py` is a **stub module** — the class skeleton and dependency injection are in place, but all `_check_*()` methods are empty and the module always returns 0 violations. Implement checks using the phased roadmap below.

## Implementation Roadmap

Work Phase 1 → Phase 4 in order. Each phase's checks are prerequisites for later phases.

### Phase 1 — Easy (Basic Geometry & Filtering)
| Check | Method | Difficulty | Est. Time |
|-------|--------|-----------|-----------|
| Net Length Max | `_check_net_length()` | ★☆☆☆☆ | 2–3 h |
| Exposed Critical Traces | `_check_exposed_critical_traces()` | ★★☆☆☆ | 3–4 h |
| Unconnected Via Pads | `_check_unconnected_via_pads()` | ★★☆☆☆ | 4–5 h |

### Phase 2 — Medium (Spatial Analysis)
| Check | Method | Difficulty | Est. Time |
|-------|--------|-----------|-----------|
| Controlled Impedance | `_check_controlled_impedance()` | ★★★☆☆ | 4–5 h (stackup API already done) |
| Differential Pair Length Match | `_check_differential_pair_length()` | ★★★☆☆ | 5–6 h |
| Critical Net Isolation (SE) | `_check_critical_net_isolation_se()` | ★★★☆☆ | 6–8 h |
| Trace Near Plane Edge | `_check_trace_near_plane_edge()` | ★★★☆☆ | 6–8 h |
| Unreferenced Traces | `_check_unreferenced_traces()` | ★★★☆☆ | 7–9 h |

### Phase 3 — Advanced (Complex Geometry)
| Check | Method | Difficulty | Est. Time |
|-------|--------|-----------|-----------|
| Crosstalk / Net Coupling | `_check_net_coupling()` | ★★★★☆ | 10–12 h |
| Net Stub | `_check_net_stub()` | ★★★★☆ | 10–12 h |
| Critical Net Isolation (Diff) | `_check_critical_net_isolation_diff()` | ★★★★☆ | 8–10 h |

### Phase 4 — Expert (Multi-Layer)
| Check | Method | Difficulty | Est. Time |
|-------|--------|-----------|-----------|
| Reference Plane Crossing | `_check_reference_plane_crossing()` | ★★★★★ | 12–15 h |
| Reference Plane Changing | `_check_reference_plane_changing()` | ★★★★★ | 12–15 h |

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
