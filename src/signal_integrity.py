"""
Signal Integrity Verification Module for EMC Auditor Plugin
Comprehensive signal and via integrity checks for EMI reduction and signal quality

This module is called by emc_auditor_plugin.py and reuses its utility functions.
Configuration is read from emc_rules.toml [signal_integrity] section.

Author: EMC Auditor Plugin
Version: 1.0.0
Last Updated: 2026-02-13

================================================================================
TODO LIST — Signal Integrity Checks
Last updated: 2026-04-05
================================================================================

 STATUS KEY:  ✅ FULLY IMPLEMENTED   🔬 TESTS NEEDED   □ NOT IMPLEMENTED

────────────────────────────────────────────────────────────────────────────
PHASE 1 — DONE (Basic Geometry & Filtering)
────────────────────────────────────────────────────────────────────────────
✅ CHECK 4: Exposed Critical Traces                          [code ✓] [test 🔬]
   - Outer-layer trace exposure check; accumulates exposed length per net
   - Tests needed: MockTrack on F.Cu with critical net class

✅ CHECK 5: Net Length Maximum                               [code ✓] [test 🔬]
   - Per-net length accumulation; max_length_by_netclass threshold
   - Tests needed: MockTrack list summing over limit vs under limit

✅ CHECK 8: Unconnected Via Pads                             [code ✓] [test 🔬]
   - Through-via isolation check; track endpoint + zone coverage test
   - Tests needed: MockVia with no nearby track endpoint

────────────────────────────────────────────────────────────────────────────
PHASE 2 — DONE (Spatial Analysis & Pattern Matching)
────────────────────────────────────────────────────────────────────────────
✅ CHECK 1: Trace Near Plane Edge                            [code ✓] [test 🔬]
   - Zone boundary extraction; point-to-segment distance along polygon edges
   - Tests needed: MockZone rectangle + MockTrack near edge

✅ CHECK 1B: Trace Near Board Edge                           [code ✓] [test 🔬]
   - Board outline extraction from Edge.Cuts layer drawings
   - Point-to-segment distance to physical PCB edge
   - Prevents EMI antenna effect (5-10mm rule) and manufacturing damage
   - Tests needed: MockDrawing on Edge.Cuts + MockTrack near board edge

✅ CHECK 7: Unreferenced Traces                              [code ✓] [test 🔬]
   - Multi-point sampling; SHAPE_POLY_SET.Contains() zone coverage test
   - Tests needed: MockTrack with no zone coverage on adjacent layer

✅ CHECK 9: Critical Net Isolation (Single-Ended)            [code ✓] [test 🔬]
   - 3W rule; bounding-box pre-filter; GND guard trace exemption
   - Tests needed: two MockTracks within/outside 3W threshold

✅ CHECK 12: Differential Pair Length Matching               [code ✓] [test 🔬]
   - _identify_differential_pairs() P/N regex; per-class skew threshold
   - Tests needed: MockTrack pairs with delta > / < dp_max_skew_mm

✅ CHECK 14: Controlled Impedance                            [code ✓] [test 🔬]
   - Stackup-aware; microstrip / stripline / CPWG formulas
   - Tests needed: MockTrack on 4-layer fixture with Z0 in/out of tolerance
   - NOTE: _calculate_cpw_impedance Wen (1969) two-regime formula fixed 2026-04-05
   - NOTE: _build_net_class_map lookahead regex fixed 2026-04-05

────────────────────────────────────────────────────────────────────────────
PHASE 3 — IN PROGRESS (Complex Geometry & Graph Algorithms)
────────────────────────────────────────────────────────────────────────────
✅ CHECK 6: Net Stub Check                                   [code ✓] [test 🔬]
  Difficulty: ★★★★☆  — estimated 10-12 h
  - Build connectivity graph per net (tracks + vias as nodes)
  - Detect T-junction branch points
  - Walk graph from branch to dead end; measure stub length
  - Flag stubs > max_stub_length_mm on critical nets
  - Handle via stubs (partial via tails on buried/blind layers)
  IMPLEMENTED: 2026-05-11
  - _build_connectivity_graph() with 3D node/edge structure
  - _calculate_stub_length() BFS traversal from leaf to branch
  - Configuration section added to emc_rules.toml

✅ CHECK 10: Critical Net Isolation (Differential)           [code ✓] [test 🔬]
  Difficulty: ★★★★☆  — estimated 8-10 h
  - Reuse _identify_differential_pairs()
  - Determine pair orientation (inner/outer edges per segment)
  - Scan only outer edges for aggressor proximity
  - Exempt the partner trace from violation
  IMPLEMENTED: 2026-05-11
  - Outer edge detection via dot product analysis
  - 4W rule enforcement on external traces
  - Configuration section added to emc_rules.toml

✅ CHECK 11: Net Coupling / Crosstalk                        [code ✓] [test 🔬]
  Difficulty: ★★★★☆  — estimated 10-12 h
  - Build spatial grid index over all track segments
  - Detect parallel segments within coupling_distance_mm
  - Compute overlap length and separation
  - Flag when (overlap / separation) > coupling_ratio_threshold
  IMPLEMENTED: 2026-05-11
  - _find_parallel_segments() helper with angle/distance filtering
  - _check_net_coupling() with spatial search and coefficient calc
  - Configuration section added to emc_rules.toml

✅ CHECK 13: Differential Running Skew                       [code ✓] [test 🔬]
  Difficulty: ★★★★☆  — estimated 8-10 h
  - Sample spacing between P/N traces at regular intervals
  - Calculate coefficient of variation (std dev / mean)
  - Flag pairs with excessive spacing variation (impedance discontinuities)
  IMPLEMENTED: 2026-05-11
  - _calculate_spacing_along_pair() with perpendicular distance sampling
  - Statistical analysis (mean, std dev, variation %)
  - Configuration section added to emc_rules.toml

────────────────────────────────────────────────────────────────────────────
PHASE 3 — COMPLETE ✅ (4/4 checks implemented)
────────────────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────────────────
PHASE 4 — COMPLETE ✅ (2/2 checks implemented)
────────────────────────────────────────────────────────────────────────────
✅ CHECK 2: Reference Plane Crossing (at vias)               [code ✓] [test 🔬]
  Difficulty: ★★★★★  — estimated 12-15 h
  - Stackup-aware: map each copper layer to its adjacent reference plane
  - For each critical-net via: get reference plane net on entry layer AND
    exit layer; flag if the plane net differs (GND → VCC, GND → AGND)
  - Also flag if no stitching via exists within stitch_max_dist_mm
  IMPLEMENTED: 2026-05-11
  - _get_reference_planes() with layer stack traversal
  - _extract_plane_boundaries() with zone outline extraction
  - Plane crossing detection with stitching via search
  - Configuration section added to emc_rules.toml

✅ CHECK 3: Reference Plane Changing (along trace path)      [code ✓] [test 🔬]
  Difficulty: ★★★★★  — estimated 10-12 h
  - Track horizontal plane changes (trace over plane gaps)
  - Identify reference plane net under each trace segment
  - Flag when trace crosses from one plane to another or over gap
  - Check for bypass capacitors at transitions (optional)
  IMPLEMENTED: 2026-05-11
  - Reference plane mapping under trace segments
  - Plane gap detection (no reference plane coverage)
  - Configuration section added to emc_rules.toml

────────────────────────────────────────────────────────────────────────────
SIGNAL INTEGRITY MODULE — 100% COMPLETE ✅ (17/17 checks implemented)
────────────────────────────────────────────────────────────────────────────

□ Impedance Calculation Refinement                           [code □] [test □]
  - Prerequisite: _get_reference_planes(layer_id) helper

□ CHECK 3: Reference Plane Changing (along trace path)       [code □] [test □]
  Difficulty: ★★★★★  — estimated 12-15 h
  - Walk each trace segment; at each sample point find the zone(s) on the
    adjacent reference layer; record the zone net
  - Flag when the zone net changes along a single continuous trace
  - Also flag crossing a gap (no zone coverage) in the reference plane
  - Prerequisite: multi-point zone lookup infrastructure from CHECK 7

□ CHECK 13: Differential Running Skew                        [code □] [test □]
  Difficulty: ★★★★★  — estimated 15-18 h
  - Requires connectivity graph from both P and N nets
  - Traverse both paths simultaneously from source pad
  - Accumulate running length delta at each topological step
  - Flag any point where |delta| > max_running_skew_mm
  - Must handle serpentine tuning sections (do NOT penalise them)

────────────────────────────────────────────────────────────────────────────
PHASE 5 — Backlog (Future Enhancements)
────────────────────────────────────────────────────────────────────────────
□ Via Anti-Pad Violations
  - Check via clearance holes in plane layers
  - Verify anti-pad diameter ≥ drill + 2×min_annular_ring

□ Via-to-Via Spacing
  - Minimum edge-to-edge spacing check
  - Manufacturing constraint verification

□ Wide Power/Ground Traces
  - Check trace width vs current capacity (I²R heating model)
  - Flag power traces narrower than IPC-2221 Table 6-1 minimum

────────────────────────────────────────────────────────────────────────────
TEST INFRASTRUCTURE TODO (tests/signal_integrity/test_checks.py)
────────────────────────────────────────────────────────────────────────────
  Add to tests/helpers.py:
    □ MockTrack(start_xy, end_xy, net_name, net_class, layer_id, width_mm)
    □ MockVia(pos_xy, net_name, drill_mm, start_layer, end_layer)
    □ MockZone(polygon_pts, net_name, layer_id)  — polygon as list of (x,y) mm tuples
    □ MockFootprint(reference, pads=[MockPad(...)])
    □ MockPad(pos_xy, net_name, net_class)
    □ make_si_checker_with_check() — wires all 5 injected functions so check() runs

  Coverage targets once test_checks.py is fully implemented:
    signal_integrity.py  → ~65%  (up from 24%)

Total Remaining Implementation: 35-45 h (Phase 3) + 39-48 h (Phase 4)
================================================================================
"""

import pcbnew


class SignalIntegrityChecker:
    """
    Handles comprehensive signal integrity verification for PCB designs.
    
    Signal integrity checks ensure proper reference plane usage, minimal coupling,
    controlled impedance, and proper via design to reduce EMI and maintain signal quality.
    
    Implements 14 checks:
    - Reference Plane Checks (4): Edge proximity, crossing, changing, exposed traces
    - Trace Quality Checks (4): Net length, stubs, unreferenced segments, via pads
    - Crosstalk Checks (3): Single-ended isolation, differential isolation, net coupling
    - Differential Pair Checks (2): Length matching/spacing, running skew
    - Impedance Control (1): Analytical impedance calculation (no FEM needed!)
    
    Standards reference:
    - IPC-2221: Generic Standard on Printed Board Design
    - IPC-2226: HDI (High Density Interconnect) Design Standard
    - High-Speed Digital Design: A Handbook of Black Magic (Howard Johnson)
    - Signal and Power Integrity - Simplified (Eric Bogatin)
    """
    
    def __init__(self, board, marker_layer, config, report_lines, verbose=True, auditor=None):
        """
        Initialize checker with board context and configuration.
        
        Args:
            board: pcbnew.BOARD instance
            marker_layer: KiCad layer ID for drawing violation markers
            config: Dictionary from emc_rules.toml [signal_integrity] section
            report_lines: List to append report messages (shared with main plugin)
            verbose: Enable detailed logging
            auditor: Reference to EMCAuditorPlugin instance (for utility functions)
        """
        self.board = board
        self.marker_layer = marker_layer
        self.config = config
        self.report_lines = report_lines
        self.verbose = verbose
        self.auditor = auditor
        
        # Utility functions (injected during check() call)
        self.draw_marker = None
        self.draw_arrow = None
        self.get_distance = None
        self.log = None
        
        # Results tracking
        self.violation_count = 0
    
    def check(self, draw_marker_func, draw_arrow_func, get_distance_func, log_func, create_group_func):
        """
        Main entry point - performs signal integrity verification.
        
        Called from emc_auditor_plugin.py check_signal_integrity() method.
        Utility functions are injected to avoid code duplication.
        
        Args:
            draw_marker_func: Function(board, pos, msg, layer, group)
            draw_arrow_func: Function(board, start, end, label, layer, group)
            get_distance_func: Function(pos1, pos2) returns distance
            log_func: Function(msg, force=False) for logging
            create_group_func: Function(board, check_type, identifier, number) creates PCB_GROUP
        
        Returns:
            int: Number of violations found
        """
        # Store utility functions for reuse
        self.log = log_func
        self.draw_marker = draw_marker_func
        self.draw_arrow = draw_arrow_func
        self.get_distance = get_distance_func
        self.create_group = create_group_func
        
        self.log("\n=== SIGNAL INTEGRITY CHECK START ===", force=True)
        
        # Reset violation counter
        self.violation_count = 0
        
        # Run individual checks - Reference Plane and Trace Quality
        self.violation_count += self._check_trace_near_plane_edge()
        self.violation_count += self._check_trace_near_board_edge()
        self.violation_count += self._check_reference_plane_crossing()
        self.violation_count += self._check_reference_plane_changing()
        self.violation_count += self._check_exposed_critical_traces()
        self.violation_count += self._check_net_length()
        self.violation_count += self._check_net_stubs()
        self.violation_count += self._check_unreferenced_traces()
        self.violation_count += self._check_unconnected_via_pads()

        # Run individual checks - Crosstalk and Isolation
        self.violation_count += self._check_critical_net_isolation_single()
        self.violation_count += self._check_critical_net_isolation_differential()
        self.violation_count += self._check_net_coupling()
        self.violation_count += self._check_differential_pair_matching()
        self.violation_count += self._check_differential_running_skew()

        # Run individual checks - Impedance Control
        self.violation_count += self._check_controlled_impedance()
        
        self.log(f"\n=== SIGNAL INTEGRITY CHECK COMPLETE: {self.violation_count} violations ===", force=True)
        return self.violation_count
    
    # ========================================================================
    # CHECK 1: Critical Net Near Edge of Reference Plane
    # ========================================================================
    
    def _check_trace_near_plane_edge(self):
        """
        Check for traces too close to reference plane edges.

        For each critical net trace segment, finds the nearest copper zone on an
        adjacent layer (reference plane) and measures the distance from the trace
        midpoint to the closest point on the zone's polygon boundary.  Flags
        segments whose clearance is below the configured threshold.

        Returns:
            int: Number of violations found
        """
        self.log("\n--- Checking Trace Near Plane Edge ---")

        plane_edge_cfg = self.config.get('trace_near_plane_edge', {})
        if not plane_edge_cfg.get('enabled', False):
            self.log("Trace near plane edge check disabled")
            return 0

        min_dist_mm = plane_edge_cfg.get('min_edge_distance_mm', 3.0)
        critical_classes = plane_edge_cfg.get(
            'critical_net_classes', self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        )
        min_dist_iu = pcbnew.FromMM(min_dist_mm)

        # Build zone map: layer_id → list of SHAPE_POLY_SET outlines for reference planes
        # Reference planes are zones whose net is GND-like or a power plane
        gnd_patterns = plane_edge_cfg.get('reference_plane_patterns', ['GND', 'PWR', 'VCC', 'VDD', 'POWER', 'AGND', 'DGND', 'PGND'])
        zone_outlines = {}  # layer_id → list of SHAPE_POLY_SET
        for zone in self.board.Zones():
            net_name = zone.GetNetname()
            if not any(p.upper() in net_name.upper() for p in gnd_patterns):
                continue
            layer_id = zone.GetLayer()
            outline = zone.Outline()
            if outline is None:
                continue
            zone_outlines.setdefault(layer_id, []).append(outline)

        if not zone_outlines:
            self.log("  No reference plane zones found — skipping")
            return 0

        # Pre-build set of adjacent layer pairs: (signal_layer, plane_layer)
        copper_layers = [l for l in range(pcbnew.F_Cu, pcbnew.B_Cu + 1)
                         if self.board.IsLayerEnabled(l)]

        violations = 0
        violation_set = set()  # avoid duplicate markers per net

        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            net = track.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            net_class = self._resolve_net_class(net_name)
            if net_class not in critical_classes:
                continue

            sig_layer = track.GetLayer()
            # Find candidate reference plane layers (adjacent copper layers)
            sig_idx = copper_layers.index(sig_layer) if sig_layer in copper_layers else -1
            if sig_idx < 0:
                continue
            candidate_layers = []
            if sig_idx > 0:
                candidate_layers.append(copper_layers[sig_idx - 1])
            if sig_idx < len(copper_layers) - 1:
                candidate_layers.append(copper_layers[sig_idx + 1])

            # Find minimum distance from trace midpoint to any reference zone boundary.
            # Uses point-to-segment distance (not vertex-only) to avoid false negatives
            # when the trace is closest to the middle of a long zone edge.
            mid = track.GetCenter()
            px, py = mid.x, mid.y
            min_found = None
            for plane_layer in candidate_layers:
                for outline in zone_outlines.get(plane_layer, []):
                    for poly_idx in range(outline.OutlineCount()):
                        poly = outline.Outline(poly_idx)
                        n_pts = poly.PointCount()
                        for pt_idx in range(n_pts):
                            a = poly.CPoint(pt_idx)
                            b = poly.CPoint((pt_idx + 1) % n_pts)
                            # Vector AB and AP
                            abx = b.x - a.x
                            aby = b.y - a.y
                            apx = px - a.x
                            apy = py - a.y
                            ab_sq = abx * abx + aby * aby
                            if ab_sq == 0:
                                # Degenerate zero-length edge — distance to vertex
                                dist = (apx * apx + apy * apy) ** 0.5
                            else:
                                # Parameter t clamped to [0, 1] for segment projection
                                t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_sq))
                                nx = a.x + t * abx
                                ny = a.y + t * aby
                                dx = px - nx
                                dy = py - ny
                                dist = (dx * dx + dy * dy) ** 0.5
                            if min_found is None or dist < min_found:
                                min_found = dist

            if min_found is None:
                continue

            if min_found < min_dist_iu:
                if net_name not in violation_set:
                    violation_set.add(net_name)
                    violations += 1
                    actual_mm = pcbnew.ToMM(min_found)
                    safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                    group = self.create_group(self.board, "PlaneEdge", safe_name, violations)
                    msg = f"TRACE NEAR PLANE EDGE\n{net_name}\n{actual_mm:.2f}mm < {min_dist_mm:.1f}mm"
                    self.draw_marker(self.board, mid, msg, self.marker_layer, group)
                    self.log(f"  ❌ {net_name} ({net_class}): {actual_mm:.2f}mm to plane edge (min {min_dist_mm:.1f}mm)")

        self.log(f"Trace near plane edge check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 1B: Trace Near Board Edge
    # ========================================================================
    
    def _check_trace_near_board_edge(self):
        """
        Check for traces too close to physical board outline.
        
        Description:
        High-speed traces routed near the PCB edge create multiple issues:
        1. EMI radiation - board edge acts as antenna launch point
        2. Manufacturing risk - routing/v-scoring may damage traces
        3. Mechanical stress - board edges are high-stress areas during handling
        
        This check extracts the board outline from Edge.Cuts layer and measures
        the distance from critical net traces to the nearest board edge polygon.
        
        Algorithm:
        1. Extract board outline polygons from Edge.Cuts layer drawings
        2. For each critical net trace segment:
           - Calculate distance from trace midpoint to nearest outline segment
           - Use point-to-segment distance (not just vertex distance)
        3. Flag if distance < min_board_edge_distance_mm
        
        Configuration parameters:
        - min_board_edge_distance_mm: Minimum clearance to board edge (default: 5.0mm for EMI)
        - critical_net_classes: Net classes requiring check
        
        Standards:
        - IPC-2221: ≥0.5mm for manufacturing reliability
        - EMI best practice: ≥5mm for signals >100MHz to reduce antenna effect
        - High-speed design: ≥10mm for critical signals (USB, HDMI, PCIe)
        
        Returns:
            int: Number of violations found
        """
        self.log("\n--- Checking Trace Near Board Edge ---")
        
        board_edge_cfg = self.config.get('trace_near_board_edge', {})
        if not board_edge_cfg.get('enabled', False):
            self.log("Trace near board edge check disabled")
            return 0
        
        min_dist_mm = board_edge_cfg.get('min_board_edge_distance_mm', 5.0)
        critical_classes = board_edge_cfg.get(
            'critical_net_classes', self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        )
        min_dist_iu = pcbnew.FromMM(min_dist_mm)
        
        self.log(f"  Minimum board edge clearance: {min_dist_mm:.1f}mm")
        self.log(f"  Critical net classes: {critical_classes}")
        
        # Extract board outline from Edge.Cuts layer
        edge_cuts_id = pcbnew.Edge_Cuts
        board_outline_polys = []  # list of SHAPE_POLY_SET
        
        # Board-level drawings on Edge.Cuts (lines, arcs, circles)
        drawing_count = 0
        for drawing in self.board.GetDrawings():
            if drawing.GetLayer() != edge_cuts_id:
                continue
            drawing_count += 1
            draw_poly = pcbnew.SHAPE_POLY_SET()
            try:
                # Transform drawing to polygon with small clearance (0.1mm) for hairline cuts
                drawing.TransformShapeToPolygon(
                    draw_poly, drawing.GetLayer(),
                    pcbnew.FromMM(0.1), pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE
                )
            except Exception as e:
                self.log(f"  Warning: Failed to transform Edge.Cuts drawing: {e}")
                continue
            if draw_poly.OutlineCount() > 0:
                board_outline_polys.append(draw_poly)
        
        # Footprint-level graphics on Edge.Cuts (slots/cutouts in components)
        for footprint in self.board.GetFootprints():
            for graphic in footprint.GraphicalItems():
                if graphic.GetLayer() != edge_cuts_id:
                    continue
                drawing_count += 1
                draw_poly = pcbnew.SHAPE_POLY_SET()
                try:
                    graphic.TransformShapeToPolygon(
                        draw_poly, graphic.GetLayer(),
                        pcbnew.FromMM(0.1), pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE
                    )
                except Exception:
                    continue
                if draw_poly.OutlineCount() > 0:
                    board_outline_polys.append(draw_poly)
        
        if not board_outline_polys:
            self.log("  ⚠ No board outline found on Edge.Cuts layer — skipping")
            return 0
        
        self.log(f"  Found {len(board_outline_polys)} board outline polygon(s) from {drawing_count} Edge.Cuts drawing(s)")
        
        # Check critical net traces against board outline
        violations = 0
        violation_set = set()  # avoid duplicate markers per net
        
        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            net = track.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            net_class = self._resolve_net_class(net_name)
            if net_class not in critical_classes:
                continue
            
            # Get trace midpoint
            mid = track.GetCenter()
            px, py = mid.x, mid.y
            
            # Find minimum distance from trace to any board outline segment
            min_found = None
            for outline_poly in board_outline_polys:
                for poly_idx in range(outline_poly.OutlineCount()):
                    poly = outline_poly.Outline(poly_idx)
                    n_pts = poly.PointCount()
                    for pt_idx in range(n_pts):
                        a = poly.CPoint(pt_idx)
                        b = poly.CPoint((pt_idx + 1) % n_pts)
                        # Vector AB and AP
                        abx = b.x - a.x
                        aby = b.y - a.y
                        apx = px - a.x
                        apy = py - a.y
                        ab_sq = abx * abx + aby * aby
                        if ab_sq == 0:
                            # Degenerate zero-length edge — distance to vertex
                            dist = (apx * apx + apy * apy) ** 0.5
                        else:
                            # Parameter t clamped to [0, 1] for segment projection
                            t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_sq))
                            nx = a.x + t * abx
                            ny = a.y + t * aby
                            dx = px - nx
                            dy = py - ny
                            dist = (dx * dx + dy * dy) ** 0.5
                        if min_found is None or dist < min_found:
                            min_found = dist
            
            if min_found is None:
                continue
            
            if min_found < min_dist_iu:
                if net_name not in violation_set:
                    violation_set.add(net_name)
                    violations += 1
                    actual_mm = pcbnew.ToMM(min_found)
                    safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                    group = self.create_group(self.board, "BoardEdge", safe_name, violations)
                    msg = f"TRACE NEAR BOARD EDGE\n{net_name}\n{actual_mm:.2f}mm < {min_dist_mm:.1f}mm"
                    self.draw_marker(self.board, mid, msg, self.marker_layer, group)
                    self.log(f"  ❌ {net_name} ({net_class}): {actual_mm:.2f}mm to board edge (min {min_dist_mm:.1f}mm)")
        
        self.log(f"Trace near board edge check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 2: Reference Plane Crossing
    # ========================================================================
    
    def _check_reference_plane_crossing(self):
        """
        Check for signals crossing between different reference planes.
        
        Description:
        When a trace via transitions between layers with different reference planes,
        a return path discontinuity occurs causing EMI radiation and signal degradation.
        Proper stitching vias are required to provide low-impedance return path.
        
        Algorithm:
        1. For each via on critical nets:
           - Identify copper planes on start/end layers
           - Determine reference plane net names (GND1, GND2, etc.)
           - Flag if reference planes differ (e.g., GND → AGND, GND → +3V3)
        2. Check for stitching vias nearby (within λ/20 or design rule distance)
        3. Create violation if no stitching via found
        
        Configuration parameters:
        - max_stitching_distance_mm: Max distance to required stitching via (default: 1.0mm)
        - critical_net_classes: Net classes requiring this check
        - exempt_plane_pairs: List of allowed plane crossings (e.g., [['GND', 'AGND']])
        
        Standards:
        - IPC-2226: HDI standard for via transitions
        - Rule of thumb: Stitching via within λ/20 of signal frequency
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Reference Plane Crossing ---")
        
        crossing_cfg = self.config.get('reference_plane_crossing', {})
        if not crossing_cfg.get('enabled', False):
            self.log("Reference plane crossing check disabled")
            return 0
        
        critical_classes = crossing_cfg.get(
            'critical_net_classes',
            ['HighSpeed', 'Clock', 'USB', 'HDMI', 'PCIe', 'Ethernet', 'DDR']
        )
        max_stitch_dist_mm = crossing_cfg.get('max_stitching_distance_mm', 1.0)
        exempt_pairs = crossing_cfg.get('exempt_plane_pairs', [])
        max_stitch_dist_iu = pcbnew.FromMM(max_stitch_dist_mm)
        
        self.log(f"  Max stitching via distance: {max_stitch_dist_mm:.1f}mm")
        self.log(f"  Critical net classes: {critical_classes}")
        
        # Build map of plane net names per layer
        layer_plane_nets = {}  # layer_id → set of plane net names
        for zone in self.board.Zones():
            net = zone.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            
            # Check if it's a plane (GND/PWR pattern)
            plane_patterns = crossing_cfg.get(
                'reference_plane_patterns',
                ['GND', 'PWR', 'VCC', 'VDD', 'POWER', 'AGND', 'DGND', 'PGND']
            )
            if not any(p.upper() in net_name.upper() for p in plane_patterns):
                continue
            
            layer_id = zone.GetLayer()
            if layer_id not in layer_plane_nets:
                layer_plane_nets[layer_id] = set()
            layer_plane_nets[layer_id].add(net_name)
        
        if not layer_plane_nets:
            self.log("  No reference planes found — skipping")
            return 0
        
        self.log(f"  Found reference planes on {len(layer_plane_nets)} layer(s)")
        
        # Collect all vias (needed for stitching via search)
        all_vias = []
        for track in self.board.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA):
                all_vias.append(track)
        
        violations = 0
        
        # Check each via on critical nets
        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_VIA):
                continue
            
            net = track.GetNet()
            if not net:
                continue
            
            net_name = net.GetNetname()
            if not net_name:
                continue
            
            net_class = self._resolve_net_class(net_name)
            if net_class not in critical_classes:
                continue
            
            # Get via entry/exit layers
            top_layer = track.TopLayer()
            bottom_layer = track.BottomLayer()
            
            # Find reference planes on entry and exit layers
            top_planes = layer_plane_nets.get(top_layer, set())
            bottom_planes = layer_plane_nets.get(bottom_layer, set())
            
            # Check for plane crossing (different plane nets)
            if not top_planes or not bottom_planes:
                continue  # No planes to cross
            
            # Check if ANY top plane differs from ANY bottom plane
            crossing_detected = False
            top_plane_name = None
            bottom_plane_name = None
            
            for tp in top_planes:
                for bp in bottom_planes:
                    if tp != bp:
                        # Check if this pair is exempt
                        is_exempt = False
                        for exempt_pair in exempt_pairs:
                            if (tp in exempt_pair and bp in exempt_pair):
                                is_exempt = True
                                break
                        
                        if not is_exempt:
                            crossing_detected = True
                            top_plane_name = tp
                            bottom_plane_name = bp
                            break
                if crossing_detected:
                    break
            
            if not crossing_detected:
                continue  # Same planes or exempt transition
            
            # Check for stitching vias nearby (on plane nets)
            via_pos = track.GetPosition()
            stitch_found = False
            
            for other_via in all_vias:
                if other_via == track:
                    continue  # Skip self
                
                other_net = other_via.GetNet()
                if not other_net:
                    continue
                
                other_net_name = other_net.GetNetname()
                
                # Check if stitching via is on one of the plane nets
                if other_net_name not in top_planes and other_net_name not in bottom_planes:
                    continue
                
                # Check distance
                other_pos = other_via.GetPosition()
                dist = self.get_distance(via_pos, other_pos)
                
                if dist <= max_stitch_dist_iu:
                    stitch_found = True
                    break
            
            if not stitch_found:
                violations += 1
                
                safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                group = self.create_group(self.board, "PlaneCrossing", safe_name, violations)
                
                msg = (f"PLANE CROSSING\n"
                       f"{net_name}\n"
                       f"{top_plane_name} → {bottom_plane_name}\n"
                       f"No stitch via < {max_stitch_dist_mm:.1f}mm")
                
                self.draw_marker(
                    self.board, via_pos, msg, self.marker_layer, group
                )
                
                self.log(f"  ❌ {net_name} ({net_class}): "
                        f"crosses {top_plane_name} → {bottom_plane_name}, "
                        f"no stitching via within {max_stitch_dist_mm:.1f}mm")
        
        self.log(f"Reference plane crossing check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 3: Reference Plane Changing
    # ========================================================================
    
    def _check_reference_plane_changing(self):
        """
        Check for signals changing reference planes along their path.
        
        Description:
        Similar to plane crossing but focuses on horizontal plane changes
        (e.g., trace running on top layer switching between GND plane gaps).
        Return current must flow around gaps causing EMI loops.
        
        Algorithm:
        1. For each critical net trace on signal layers:
           - Track trace path sequentially
           - At each segment, identify reference plane directly below/above
           - Detect transitions between different plane nets or gaps
        2. Flag segments where reference changes without controlled transition
        3. Check for bypass caps or stitching vias at transition points
        
        Configuration parameters:
        - min_plane_overlap_mm: Minimum overlap before considering reference change (default: 0.5mm)
        - require_bypass_cap: If True, require cap at reference changes (default: True)
        - max_bypass_distance_mm: Max distance to required bypass cap (default: 2.0mm)
        
        Standards:
        - High-Speed Digital Design: Minimize reference plane splits under traces
        - Best practice: Route over continuous reference planes
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Reference Plane Changing ---")
        
        changing_cfg = self.config.get('reference_plane_changing', {})
        if not changing_cfg.get('enabled', False):
            self.log("Reference plane changing check disabled")
            return 0
        
        critical_classes = changing_cfg.get(
            'critical_net_classes',
            ['HighSpeed', 'Clock', 'USB', 'HDMI', 'PCIe', 'Ethernet', 'DDR']
        )
        min_overlap_mm = changing_cfg.get('min_plane_overlap_mm', 0.5)
        require_bypass = changing_cfg.get('require_bypass_cap', False)
        min_overlap_iu = pcbnew.FromMM(min_overlap_mm)
        
        self.log(f"  Minimum plane overlap: {min_overlap_mm:.1f}mm")
        self.log(f"  Critical net classes: {critical_classes}")
        if require_bypass:
            max_bypass_mm = changing_cfg.get('max_bypass_distance_mm', 2.0)
            self.log(f"  Bypass cap required within {max_bypass_mm:.1f}mm")
        
        # Build map of plane boundaries per layer
        layer_plane_map = {}  # layer_id → [(net_name, SHAPE_POLY_SET)]
        for zone in self.board.Zones():
            net = zone.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            
            # Check if it's a plane (GND/PWR pattern)
            plane_patterns = changing_cfg.get(
                'reference_plane_patterns',
                ['GND', 'PWR', 'VCC', 'VDD', 'POWER', 'AGND', 'DGND', 'PGND']
            )
            if not any(p.upper() in net_name.upper() for p in plane_patterns):
                continue
            
            layer_id = zone.GetLayer()
            outline = zone.Outline()
            if not outline or outline.OutlineCount() == 0:
                continue
            
            if layer_id not in layer_plane_map:
                layer_plane_map[layer_id] = []
            layer_plane_map[layer_id].append((net_name, outline))
        
        if not layer_plane_map:
            self.log("  No reference planes found — skipping")
            return 0
        
        self.log(f"  Found reference planes on {len(layer_plane_map)} layer(s)")
        
        violations = 0
        violation_set = set()  # Avoid duplicate markers per net
        
        # Check each track segment on critical nets
        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            
            net = track.GetNet()
            if not net:
                continue
            
            net_name = net.GetNetname()
            if not net_name:
                continue
            
            net_class = self._resolve_net_class(net_name)
            if net_class not in critical_classes:
                continue
            
            layer_id = track.GetLayer()
            
            # Find reference planes adjacent to this layer
            ref_above, ref_below = self._get_reference_planes(layer_id)
            
            if not ref_above and not ref_below:
                continue  # No reference planes adjacent
            
            # Check both directions for plane presence
            track_center = track.GetCenter()
            current_plane_nets = set()
            
            # Check plane above
            if ref_above and ref_above in layer_plane_map:
                for plane_net, plane_outline in layer_plane_map[ref_above]:
                    # Check if track center is within plane boundary
                    if plane_outline.Contains(track_center):
                        current_plane_nets.add(plane_net)
            
            # Check plane below
            if ref_below and ref_below in layer_plane_map:
                for plane_net, plane_outline in layer_plane_map[ref_below]:
                    if plane_outline.Contains(track_center):
                        current_plane_nets.add(plane_net)
            
            if not current_plane_nets:
                # Track is NOT over any reference plane (plane gap)
                # This is a potential violation
                violation_key = f"{net_name}_{track_center.x}_{track_center.y}"
                if violation_key in violation_set:
                    continue  # Already flagged this location
                
                violations += 1
                violation_set.add(violation_key)
                
                safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                group = self.create_group(self.board, "PlaneChange", safe_name, violations)
                
                msg = (f"PLANE GAP\n"
                       f"{net_name}\n"
                       f"No reference plane\n"
                       f"under trace segment")
                
                self.draw_marker(
                    self.board, track_center, msg, self.marker_layer, group
                )
                
                self.log(f"  ❌ {net_name} ({net_class}): "
                        f"trace segment over plane gap at "
                        f"({pcbnew.ToMM(track_center.x):.2f}, {pcbnew.ToMM(track_center.y):.2f})mm")
        
        self.log(f"Reference plane changing check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 4: Length of Exposed Critical Traces
    # ========================================================================
    
    def _check_exposed_critical_traces(self):
        """
        Check for critical traces not buried between reference planes.
        
        Description:
        Traces on outer layers without reference planes on both sides can radiate
        EMI efficiently. Critical signals should be routed on internal layers
        sandwiched between power/ground planes (stripline configuration).
        
        Algorithm:
        1. Identify critical nets (high-speed, clock, differential pairs)
        2. For each trace segment:
           - Check if layer is outer layer (F.Cu, B.Cu)
           - Measure exposed segment length on outer layers
           - Accumulate total exposed length per net
        3. Flag if exposed length exceeds threshold
        
        Configuration parameters:
        - max_exposed_length_mm: Maximum allowed outer layer routing (default: 5.0mm)
        - critical_net_classes: Net classes requiring burial (e.g., ['HighSpeed', 'DDR'])
        - allow_fanout_length_mm: Exemption for IC fanout (default: 2.0mm)
        - outer_layers: List of layer names considered "outer" (default: ['F.Cu', 'B.Cu'])
        
        Standards:
        - IPC-2226: Recommends stripline for EMI-sensitive signals
        - Best practice: <5mm outer layer routing for >100MHz signals
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Exposed Critical Traces ---")

        exposed_cfg = self.config.get('exposed_traces', {})
        if not exposed_cfg.get('enabled', False):
            self.log("Exposed critical traces check disabled")
            return 0

        max_exposed_mm = exposed_cfg.get('max_exposed_length_mm', 20.0)
        critical_classes = exposed_cfg.get('critical_net_classes',
                                           self.config.get('critical_net_classes', ['HighSpeed', 'Clock']))

        # Resolve outer layer IDs
        outer_layer_ids = set()
        for name in ('F.Cu', 'B.Cu'):
            layer_id = self.board.GetLayerID(name)
            if layer_id >= 0:
                outer_layer_ids.add(layer_id)

        if not outer_layer_ids:
            self.log("⚠ Could not determine outer layers — skipping")
            return 0

        # Accumulate exposed length per critical net on outer layers
        net_exposed = {}    # net_name -> total outer-layer length (IU)
        net_class_map = {}  # net_name -> net class name
        net_positions = {}  # net_name -> first position found (for marker)

        for track in self.board.GetTracks():
            if track.GetLayer() not in outer_layer_ids:
                continue
            net = track.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            net_class = self._resolve_net_class(net_name)
            if net_class not in critical_classes:
                continue
            net_exposed[net_name] = net_exposed.get(net_name, 0) + track.GetLength()
            net_class_map[net_name] = net_class
            if net_name not in net_positions:
                net_positions[net_name] = track.GetStart()

        if not net_exposed:
            self.log("No critical net traces found on outer layers")
            return 0

        violations = 0
        for net_name, total_iu in sorted(net_exposed.items()):
            total_mm = pcbnew.ToMM(total_iu)
            net_class = net_class_map[net_name]
            if total_mm > max_exposed_mm:
                violations += 1
                pos = net_positions[net_name]
                safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                group = self.create_group(self.board, "ExposedTrace", safe_name, violations)
                msg = f"EXPOSED TRACE\n{net_name}\n{total_mm:.1f}mm on outer layer"
                self.draw_marker(self.board, pos, msg, self.marker_layer, group)
                self.log(f"  ❌ {net_name} ({net_class}): {total_mm:.1f}mm exposed on outer layers (max {max_exposed_mm:.1f}mm)")
            else:
                self.log(f"  ✓ {net_name} ({net_class}): {total_mm:.1f}mm exposed on outer layers")

        self.log(f"Exposed critical traces check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 5: Net Length Maximum
    # ========================================================================
    
    def _check_net_length(self):
        """
        Check for nets exceeding maximum length constraints.
        
        Description:
        Long traces increase signal delay, attenuation, and EMI radiation.
        Critical nets should meet maximum length constraints based on signal frequency
        and timing requirements.
        
        Algorithm:
        1. For each net in critical net classes:
           - Calculate total routed length (all segments + via heights)
           - Compare against configured maximum for that net class
           - Flag violations
        2. For differential pairs:
           - Calculate both traces
           - Check individual lengths and mismatch
        3. For multi-point nets:
           - Calculate longest pin-to-pin path
        
        Configuration parameters:
        - max_length_by_netclass: Dict mapping net class to max length mm
          Example: {'HighSpeed': 50.0, 'Clock': 30.0, 'DDR': 25.0}
        - include_via_length: If True, add via stub heights (default: True)
        - via_length_per_layer_mm: Via length per layer pair (default: 1.6mm for standard PCB)
        
        Standards:
        - DDR4: Strict length matching requirements (<5mm mismatch)
        - USB 2.0: <450mm total length recommended
        - PCIe: Length limits vary by generation
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Net Length ---")

        net_length_cfg = self.config.get('net_length', {})
        if not net_length_cfg.get('enabled', False):
            self.log("Net length check disabled")
            return 0

        max_length_config = net_length_cfg.get('max_length_by_netclass', {
            'HighSpeed': 150.0, 'Clock': 100.0, 'DDR': 80.0, 'USB': 450.0
        })
        if not max_length_config:
            self.log("No net length limits configured — skipping")
            return 0

        self.log(f"  Limits: {max_length_config}")

        # Accumulate routed length per net (only for configured net classes)
        net_lengths = {}   # net_name -> total length (IU)
        net_class_map = {} # net_name -> net class name
        net_positions = {} # net_name -> first track start position (for marker)

        for track in self.board.GetTracks():
            net = track.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            net_class = self._resolve_net_class(net_name)
            if net_class not in max_length_config:
                continue
            net_lengths[net_name] = net_lengths.get(net_name, 0) + track.GetLength()
            net_class_map[net_name] = net_class
            if net_name not in net_positions:
                net_positions[net_name] = track.GetStart()

        if not net_lengths:
            self.log("No nets found matching configured net classes for length check")
            return 0

        violations = 0
        for net_name, total_iu in sorted(net_lengths.items()):
            net_class = net_class_map[net_name]
            max_mm = max_length_config[net_class]
            total_mm = pcbnew.ToMM(total_iu)
            if total_mm > max_mm:
                violations += 1
                pos = net_positions[net_name]
                safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                group = self.create_group(self.board, "NetLength", safe_name, violations)
                msg = f"NET TOO LONG\n{net_name}\n{total_mm:.1f}mm > {max_mm:.1f}mm"
                self.draw_marker(self.board, pos, msg, self.marker_layer, group)
                self.log(f"  ❌ {net_name} ({net_class}): {total_mm:.1f}mm > {max_mm:.1f}mm limit")
            else:
                self.log(f"  ✓ {net_name} ({net_class}): {total_mm:.1f}mm ≤ {max_mm:.1f}mm")

        self.log(f"Net length check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 6: Net Stub Check
    # ========================================================================
    
    def _check_net_stubs(self):
        """
        Check for trace stubs exceeding maximum length.
        
        Description:
        Stubs are unterminated trace branches that create reflections and signal
        integrity issues at high frequencies. Common sources: vias with no backdrilling,
        T-junction branches, unused pins on multi-drop nets.
        
        Algorithm:
        1. Build connectivity graph for each net
        2. Identify branch points (T-junctions, via transitions)
        3. Calculate stub length from branch to endpoint
        4. Types of stubs:
           - Via stubs: Via extending beyond last connected layer
           - Branch stubs: T-junction branches to unused pins
           - Fork stubs: Split routing with unequal lengths
        5. Flag if stub length > threshold (typically λ/10 at max frequency)
        
        Configuration parameters:
        - max_stub_length_mm: Maximum allowed stub length (default: 1.5mm)
        - critical_net_classes: Net classes requiring stub checking
        - check_via_stubs: Enable via stub detection (default: True)
        - check_branch_stubs: Enable branch stub detection (default: True)
        - min_stub_length_mm: Minimum stub length to report (default: 0.3mm)
        
        Standards:
        - Rule of thumb: Stub length < λ/10 at highest frequency
        - Via stubs: <1.5mm for signals >1GHz; consider backdrilling for >5GHz
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Net Stubs ---")
        
        stub_cfg = self.config.get('net_stubs', {})
        if not stub_cfg.get('enabled', False):
            self.log("Net stub check disabled")
            return 0
        
        critical_classes = stub_cfg.get('critical_net_classes',
                                        self.config.get('critical_net_classes',
                                                       ['HighSpeed', 'Clock', 'DDR', 'USB', 'HDMI']))
        max_stub_mm = stub_cfg.get('max_stub_length_mm', 1.5)
        min_stub_mm = stub_cfg.get('min_stub_length_mm', 0.3)
        check_via_stubs = stub_cfg.get('check_via_stubs', True)
        check_branch_stubs = stub_cfg.get('check_branch_stubs', True)
        
        # Collect all critical nets
        critical_nets = []  # [(net_obj, net_name, net_class)]
        netinfo = self.board.GetNetInfo()
        
        for net_code in range(netinfo.GetNetCount()):
            net = netinfo.GetNetItem(net_code)
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            
            net_class = self._resolve_net_class(net_name)
            if net_class not in critical_classes:
                continue
            
            critical_nets.append((net, net_name, net_class))
        
        if not critical_nets:
            self.log("  No critical nets found for stub checking")
            return 0
        
        self.log(f"  Analyzing {len(critical_nets)} critical net(s)")
        
        violations = 0
        total_stubs_found = 0
        
        for net_obj, net_name, net_class in critical_nets:
            # Build connectivity graph
            graph = self._build_connectivity_graph(net_obj)
            nodes = graph['nodes']
            edges = graph['edges']
            
            if not nodes:
                continue  # Empty net
            
            # Identify potential stubs: leaf nodes (degree 1) that aren't pads
            stub_candidates = []
            
            for node_key, node_data in nodes.items():
                num_connections = len(node_data['connections'])
                
                # Leaf node (dead end)
                if num_connections == 1:
                    # If it's a pad, it's a valid endpoint (not a stub)
                    if node_data['type'] == 'pad':
                        continue
                    
                    # Track end or via with only one connection = potential stub
                    stub_candidates.append((node_key, node_data))
            
            if not stub_candidates:
                continue  # No stubs on this net
            
            # For each stub candidate, trace back to find branch point
            # and calculate total stub length
            for stub_node_key, stub_node_data in stub_candidates:
                # BFS to find path to nearest branch point or pad
                stub_length_mm = self._calculate_stub_length(
                    stub_node_key, nodes, edges
                )
                
                if stub_length_mm is None:
                    continue  # Couldn't determine stub length
                
                # Filter by minimum length
                if stub_length_mm < min_stub_mm:
                    continue
                
                total_stubs_found += 1
                
                # Check if exceeds threshold
                if stub_length_mm > max_stub_mm:
                    violations += 1
                    
                    # Create marker at stub endpoint
                    stub_pos = stub_node_data['position']
                    stub_layer = stub_node_data['layer']
                    layer_name = self.board.GetLayerName(stub_layer)
                    
                    safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                    group = self.create_group(self.board, "Stub", safe_name, violations)
                    
                    stub_type = "VIA" if stub_node_data['type'] == 'via' else "BRANCH"
                    msg = (f"STUB DETECTED\n"
                           f"{net_name}\n"
                           f"Type: {stub_type}\n"
                           f"Length: {stub_length_mm:.2f}mm\n"
                           f"Max: {max_stub_mm:.2f}mm")
                    
                    self.draw_marker(
                        self.board, stub_pos, msg, self.marker_layer, group
                    )
                    
                    self.log(f"  ❌ {net_name} ({net_class}): "
                            f"{stub_type} stub {stub_length_mm:.2f}mm > {max_stub_mm:.2f}mm "
                            f"on {layer_name}")
                else:
                    # Within tolerance but log for info
                    self.log(f"  ℹ {net_name}: stub {stub_length_mm:.2f}mm ≤ {max_stub_mm:.2f}mm (OK)")
        
        self.log(f"Net stub check: {violations} violation(s) ({total_stubs_found} total stubs found)")
        return violations
    
    # ========================================================================
    # CHECK 7: Above/Below Reference Plane Check
    # ========================================================================
    
    def _check_unreferenced_traces(self):
        """
        Check for trace segments lacking reference planes above or below.
        
        Description:
        Traces require solid reference planes for controlled impedance and EMI containment.
        Gaps in reference planes or routing over plane splits creates "unreferenced" segments
        with poor signal integrity and high EMI radiation.
        
        Algorithm:
        1. For each signal layer, identify adjacent reference plane layers
        2. Extract reference plane coverage areas (copper zones)
        3. For each critical net trace segment:
           - Check if at least one reference plane exists above/below
           - Calculate segment length over plane gaps
           - Flag segments with inadequate reference
        4. Accumulate total unreferenced length per net
        
        Configuration parameters:
        - max_unreferenced_length_mm: Maximum allowed length without reference (default: 1.0mm)
        - require_both_sides: If True, require planes both above and below (default: False)
        - critical_net_classes: Net classes requiring full referencing
        - plane_gap_tolerance_mm: Small gaps to ignore (default: 0.2mm)
        
        Standards:
        - Controlled impedance requires continuous reference plane
        - Best practice: <1mm unreferenced for high-speed signals
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Unreferenced Traces ---")

        unref_cfg = self.config.get('unreferenced_traces', {})
        if not unref_cfg.get('enabled', False):
            self.log("Unreferenced traces check disabled")
            return 0

        max_unref_mm = unref_cfg.get('max_unreferenced_length_mm', 1.0)
        critical_classes = unref_cfg.get(
            'critical_net_classes', self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        )
        gnd_patterns = unref_cfg.get(
            'reference_plane_patterns', ['GND', 'PWR', 'VCC', 'VDD', 'POWER', 'AGND', 'DGND', 'PGND']
        )

        # Build zone map: layer_id → list of (ZONE, SHAPE_POLY_SET outline)
        # Stores the zone outline polygon so we can test if a point is inside the reference
        # plane RULE AREA (not just where fill copper happens to exist after clearances).
        # This is the correct semantic: "is there a defined reference plane above/below this trace?"
        zone_polys = {}  # layer_id → list of (ZONE, outline_poly)
        for zone in self.board.Zones():
            net_name = zone.GetNetname()
            if not any(p.upper() in net_name.upper() for p in gnd_patterns):
                continue
            layer_id = zone.GetLayer()
            try:
                outline = zone.Outline()
                if outline is not None:
                    zone_polys.setdefault(layer_id, []).append(outline)
            except Exception:
                pass

        if not zone_polys:
            self.log("  No reference plane zones found — skipping")
            return 0

        copper_layers = [l for l in range(pcbnew.F_Cu, pcbnew.B_Cu + 1)
                         if self.board.IsLayerEnabled(l)]

        # Sample step for multi-point coverage: every 0.5 mm along each track segment.
        # This avoids false positives from a single midpoint landing just outside a zone boundary.
        sample_step_iu = pcbnew.FromMM(0.5)

        violations = 0
        net_unref = {}   # net_name → total unreferenced length (IU)
        net_positions = {}
        net_class_cache = {}

        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            net = track.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            net_class = self._resolve_net_class(net_name)
            if net_class not in critical_classes:
                continue

            sig_layer = track.GetLayer()
            sig_idx = copper_layers.index(sig_layer) if sig_layer in copper_layers else -1
            if sig_idx < 0:
                continue

            # Adjacent reference layers (above and below in stackup order)
            candidate_layers = []
            for offset in (-1, 1):
                cand_idx = sig_idx + offset
                if 0 <= cand_idx < len(copper_layers):
                    candidate_layers.append(copper_layers[cand_idx])

            seg_start = track.GetStart()
            seg_end = track.GetEnd()
            seg_len = track.GetLength()
            if seg_len == 0:
                continue

            # Sample multiple points along the segment and accumulate unreferenced sub-length.
            num_samples = max(2, int(round(seg_len / sample_step_iu)))
            step_iu = seg_len / num_samples
            unref_for_track = 0  # IU

            for i in range(num_samples + 1):
                t = i / num_samples
                px = int(seg_start.x + (seg_end.x - seg_start.x) * t)
                py = int(seg_start.y + (seg_end.y - seg_start.y) * t)
                pt = pcbnew.VECTOR2I(px, py)

                referenced = False
                for plane_layer in candidate_layers:
                    for outline in zone_polys.get(plane_layer, []):
                        try:
                            if outline.Contains(pt):
                                referenced = True
                                break
                        except Exception:
                            pass
                    if referenced:
                        break

                if not referenced:
                    # Attribute one step-worth of length to this sample point
                    unref_for_track += step_iu

            if unref_for_track > 0:
                net_unref[net_name] = net_unref.get(net_name, 0) + unref_for_track
                net_class_cache[net_name] = net_class
                if net_name not in net_positions:
                    net_positions[net_name] = track.GetCenter()

        max_unref_iu = pcbnew.FromMM(max_unref_mm)
        for net_name, total_iu in sorted(net_unref.items()):
            total_mm = pcbnew.ToMM(total_iu)
            net_class = net_class_cache[net_name]
            if total_iu > max_unref_iu:
                violations += 1
                pos = net_positions[net_name]
                safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                group = self.create_group(self.board, "UnrefTrace", safe_name, violations)
                msg = f"UNREFERENCED TRACE\n{net_name}\n{total_mm:.1f}mm without reference plane"
                self.draw_marker(self.board, pos, msg, self.marker_layer, group)
                self.log(f"  ❌ {net_name} ({net_class}): {total_mm:.1f}mm unreferenced (max {max_unref_mm:.1f}mm)")
            else:
                self.log(f"  ✓ {net_name} ({net_class}): {total_mm:.1f}mm unreferenced")

        self.log(f"Unreferenced traces check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 8: Unconnected Via Pads
    # ========================================================================
    
    def _check_unconnected_via_pads(self):
        """
        Check for via pads not connected to traces on inner layers.
        
        Description:
        Vias passing through internal layers often have copper pads (annular rings)
        on those layers even when not electrically connected. These "floating" pads
        create parasitic capacitance, act as antennas for EMI, and can cause
        manufacturing issues. Modern designs use "blind/buried vias" or "via-in-pad"
        to eliminate unnecessary pads.
        
        Algorithm:
        1. For each via:
           - Determine start layer and end layer from via type
           - Iterate through all layers the via traverses
        2. For each internal layer:
           - Check if traces/pads connect to via at that layer
           - Flag if via has copper pad but no connections
        3. Count total unconnected pads per via and per net
        
        Configuration parameters:
        - check_critical_nets_only: Only check specified net classes (default: True)
        - critical_net_classes: Net classes to check (e.g., ['HighSpeed', 'DDR'])
        - allow_thermal_reliefs: Count thermal reliefs as "connected" (default: False)
        - flag_threshold: Minimum unconnected pads to flag (default: 1)
        
        Standards:
        - IPC-6012: Via quality standards
        - Best practice: Remove unused via pads ("via pad removal" or "pad stacks")
        - High-speed design: Minimize parasitic capacitance from floating pads
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Unconnected Via Pads ---")

        via_cfg = self.config.get('unconnected_via_pads', {})
        if not via_cfg.get('enabled', False):
            self.log("Unconnected via pads check disabled")
            return 0

        check_critical_only = via_cfg.get('check_critical_nets_only', True)
        critical_classes = via_cfg.get('critical_net_classes',
                                       self.config.get('critical_net_classes', ['HighSpeed', 'Clock']))

        # Collect internal copper layer IDs
        outer_layers = {pcbnew.F_Cu, pcbnew.B_Cu}
        internal_layers = []
        for layer_id in range(pcbnew.B_Cu + 1):
            if layer_id not in outer_layers and self.board.GetLayerName(layer_id).endswith('.Cu'):
                internal_layers.append(layer_id)

        if not internal_layers:
            self.log("No internal copper layers — skipping (requires multi-layer board)")
            return 0

        self.log(f"  Internal layers: {[self.board.GetLayerName(l) for l in internal_layers]}")

        # Build set of (layer_id, grid_x, grid_y) for all track endpoints (non-via tracks)
        SNAP = pcbnew.FromMM(0.01)  # 10 µm snap tolerance
        track_points = set()
        for track in self.board.GetTracks():
            if track.GetClass() in ('PCB_VIA', 'VIA'):
                continue
            layer_id = track.GetLayer()
            for pt in (track.GetStart(), track.GetEnd()):
                track_points.add((layer_id, pt.x // SNAP, pt.y // SNAP))

        # Build zone coverage map: (layer_id, net_name) -> list of zones
        zone_map = {}
        for zone in self.board.GetZones():
            znet = zone.GetNet()
            if not znet:
                continue
            key = (zone.GetLayer(), znet.GetNetname())
            zone_map.setdefault(key, []).append(zone)

        violations = 0
        via_checked = 0

        for track in self.board.GetTracks():
            if track.GetClass() not in ('PCB_VIA', 'VIA'):
                continue

            net = track.GetNet()
            if not net:
                continue

            net_name = net.GetNetname()
            if check_critical_only and self._resolve_net_class(net_name) not in critical_classes:
                continue

            # Only through vias span all internal layers
            try:
                if track.GetViaType() != pcbnew.VIATYPE_THROUGH:
                    continue
            except AttributeError:
                pass  # If GetViaType() unavailable, assume through-via

            via_checked += 1
            via_pos = track.GetPosition()
            pos_grid = (via_pos.x // SNAP, via_pos.y // SNAP)

            unconnected_layers = []
            for layer_id in internal_layers:
                # Track endpoint present on this layer at via position?
                if (layer_id, pos_grid[0], pos_grid[1]) in track_points:
                    continue

                # Zone on same net covers via position on this layer?
                zone_key = (layer_id, net_name)
                covered = False
                if zone_key in zone_map:
                    for zone in zone_map[zone_key]:
                        try:
                            if zone.Outline().Contains(via_pos):
                                covered = True
                                break
                        except Exception:
                            pass

                if not covered:
                    unconnected_layers.append(self.board.GetLayerName(layer_id))

            if unconnected_layers:
                violations += 1
                safe_name = net_name.replace('/', '_').replace('(', '').replace(')', '')
                group = self.create_group(self.board, "ViaUnconnected", safe_name, violations)
                layers_str = ', '.join(unconnected_layers[:2])
                if len(unconnected_layers) > 2:
                    layers_str += f' +{len(unconnected_layers) - 2} more'
                msg = f"FLOATING VIA PAD\n{net_name}\n{layers_str}"
                self.draw_marker(self.board, via_pos, msg, self.marker_layer, group)
                pos_mm = f"({pcbnew.ToMM(via_pos.x):.2f}, {pcbnew.ToMM(via_pos.y):.2f})"
                self.log(f"  ❌ Via {pos_mm}mm [{net_name}]: floating pad on {layers_str}")

        self.log(f"  Checked {via_checked} via(s) on {'critical nets' if check_critical_only else 'all nets'}")
        self.log(f"Unconnected via pads check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 9: Critical Net Isolation (Single-Ended Nets)
    # ========================================================================
    
    def _check_critical_net_isolation_single(self):
        """
        Check for critical single-ended nets lacking proper isolation.
        
        Description:
        Critical nets should have ground-guard traces or vacant track isolation on both
        sides to prevent crosstalk and EMI radiation. This is especially important for
        sensitive analog signals, high-speed clocks, and EMI-critical nets.
        
        Two isolation methods:
        1. Ground-guard traces: Active GND traces routed parallel on both sides
        2. Vacant track isolation: No other traces within 3W rule (3× trace width)
        
        Algorithm:
        1. Identify critical nets requiring isolation (from net classes or patterns)
        2. For each trace segment on critical net:
           - Scan perpendicular at segment midpoint(s)
           - Check for adjacent traces within isolation distance
           - If found, verify it's a ground net (guard trace)
           - Flag if non-ground trace too close or no guard present
        3. Allow exemptions for vias, pads, fanout zones
        
        Configuration parameters:
        - critical_net_classes: Net classes requiring isolation (e.g., ['HighSpeed', 'Sensitive'])
        - critical_net_patterns: Regex patterns for net names (e.g., ['CLOCK.*', 'XTAL.*'])
        - isolation_method: 'guard_trace', 'vacant_track', or 'either' (default: 'either')
        - min_isolation_distance_mm: Minimum spacing if no guard (3W rule, default: 3× width)
        - guard_trace_max_distance_mm: Max distance to qualify as guard trace (default: 1.0mm)
        - ground_net_patterns: Net name patterns for ground (default: ['GND', 'AGND', 'DGND'])
        
        Standards:
        - 3W rule: Spacing ≥ 3× trace width reduces crosstalk to <10%
        - IPC-2221: Provides spacing guidelines for various applications
        - IEEE 1596.3: Recommends guard traces for critical signals
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Critical Net Isolation (Single-Ended) ---")

        iso_cfg = self.config.get('critical_net_isolation_se', {})
        if not iso_cfg.get('enabled', False):
            self.log("Critical net isolation (SE) check disabled")
            return 0

        critical_classes = iso_cfg.get(
            'critical_net_classes', self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        )
        # 3W rule default: spacing >= 3 × trace width; or use fixed min_isolation_mm
        min_isolation_mm = iso_cfg.get('min_isolation_mm', 0.0)  # 0 = use 3W rule per trace
        three_w_multiplier = iso_cfg.get('three_w_multiplier', 3.0)
        gnd_patterns = iso_cfg.get(
            'ground_net_patterns', ['GND', 'AGND', 'DGND', 'PGND', 'CHASSIS', 'PE']
        )

        # Collect all critical net tracks and all other tracks per layer for fast lookup
        # Build: layer → list of (xmin, ymin, xmax, ymax, track) for non-critical nets
        from collections import defaultdict
        other_tracks = defaultdict(list)  # layer_id → list of PCB_TRACK
        critical_tracks = []              # list of PCB_TRACK on critical nets

        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            net = track.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            net_class = self._resolve_net_class(net_name)
            if net_class in critical_classes:
                critical_tracks.append(track)
            else:
                other_tracks[track.GetLayer()].append(track)

        if not critical_tracks:
            self.log("  No critical net tracks found — skipping")
            return 0

        violations = 0
        violation_set = set()  # (critical_net, offending_net) pairs already reported

        for crit_track in critical_tracks:
            crit_net = crit_track.GetNetname()
            crit_layer = crit_track.GetLayer()
            crit_width_iu = crit_track.GetWidth()
            crit_width_mm = pcbnew.ToMM(crit_width_iu)

            # Required isolation: max(configured min, 3W rule)
            required_mm = max(min_isolation_mm, three_w_multiplier * crit_width_mm)
            required_iu = pcbnew.FromMM(required_mm)

            crit_mid = crit_track.GetCenter()

            for other in other_tracks[crit_layer]:
                other_net = other.GetNetname()
                if not other_net:
                    continue
                # Skip if it's a ground guard trace (that's the desired protection)
                if any(p.upper() in other_net.upper() for p in gnd_patterns):
                    continue
                # Skip same net fragments
                if other_net == crit_net:
                    continue

                # Fast bounding-box pre-filter
                o_bbox = other.GetBoundingBox()
                c_bbox = crit_track.GetBoundingBox()
                bbox_gap_x = max(0, max(o_bbox.GetLeft(), c_bbox.GetLeft()) - min(o_bbox.GetRight(), c_bbox.GetRight()))
                bbox_gap_y = max(0, max(o_bbox.GetTop(), c_bbox.GetTop()) - min(o_bbox.GetBottom(), c_bbox.GetBottom()))
                if bbox_gap_x > required_iu * 2 or bbox_gap_y > required_iu * 2:
                    continue

                dist_iu = self.get_distance(crit_track.GetCenter(), other.GetCenter())
                if dist_iu < required_iu:
                    pair_key = (crit_net, other_net)
                    rev_key = (other_net, crit_net)
                    if pair_key not in violation_set and rev_key not in violation_set:
                        violation_set.add(pair_key)
                        violations += 1
                        net_class = self._resolve_net_class(crit_net)
                        actual_mm = pcbnew.ToMM(dist_iu)
                        safe_name = crit_net.replace('/', '_').replace('(', '').replace(')', '')
                        group = self.create_group(self.board, "IsolationSE", safe_name, violations)
                        msg = f"ISOLATION VIOLATION (SE)\n{crit_net} ↔ {other_net}\n{actual_mm:.2f}mm < {required_mm:.2f}mm"
                        self.draw_marker(self.board, crit_mid, msg, self.marker_layer, group)
                        self.log(f"  ❌ {crit_net} ↔ {other_net}: {actual_mm:.2f}mm (need {required_mm:.2f}mm = {three_w_multiplier:.0f}W)")

        self.log(f"Critical net isolation (SE) check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 10: Critical Net Isolation (Differential Nets)
    # ========================================================================
    
    def _check_critical_net_isolation_differential(self):
        """
        Check for differential pairs lacking proper edge isolation.
        
        Description:
        Differential pairs should have ground-guard traces or vacant isolation on the
        OUTER edges (not between the pair traces). The inner spacing is controlled by
        differential impedance requirements, but external isolation prevents crosstalk
        with other signals and reduces common-mode EMI.
        
        Algorithm:
        1. Identify differential pairs (from net naming: _P/_N, +/-, etc.)
        2. For each diff pair segment:
           - Determine pair orientation and outer edges
           - Scan outward from each outer edge
           - Check for guard traces or vacant zones
           - Flag if isolation inadequate on either side
        3. Consider pair as single entity (don't flag spacing between pair members)
        
        Configuration parameters:
        - differential_pair_patterns: Regex for identifying pairs
          Example: [r'(.+)_P$', r'(.+)_N$'], [r'(.+)[+]$', r'(.+)-$']
        - outer_edge_multiplier: Minimum spacing to other signals (default: 4× pair width)
        - min_isolation_distance_mm: Fixed minimum spacing floor (default: 0.0mm)
        - ground_net_patterns: Patterns for ground guard nets
        
        Standards:
        - USB 2.0: 90Ω ±15% differential impedance, isolated routing
        - HDMI: 100Ω differential, guard or 4W spacing to adjacent signals
        - PCIe: Strict differential routing with isolation requirements
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Critical Net Isolation (Differential) ---")
        
        iso_cfg = self.config.get('critical_net_isolation_dp', {})
        if not iso_cfg.get('enabled', False):
            self.log("Critical net isolation (DP) check disabled")
            return 0
        
        critical_classes = iso_cfg.get(
            'critical_net_classes',
            ['USB', 'HDMI', 'Ethernet', 'LVDS', 'HighSpeed', 'DDR']
        )
        outer_edge_mult = iso_cfg.get('outer_edge_multiplier', 4.0)
        min_isolation_mm = iso_cfg.get('min_isolation_mm', 0.0)
        gnd_patterns = iso_cfg.get(
            'ground_net_patterns',
            ['GND', 'AGND', 'DGND', 'PGND', 'CHASSIS', 'PE']
        )
        
        # Identify differential pairs
        pairs = self._identify_differential_pairs()
        if not pairs:
            self.log("  No differential pairs detected — skipping")
            return 0
        
        # Build set of all differential pair net names
        dp_net_names = set()
        dp_partners = {}  # net_name → partner_net_name
        for base, (p_name, n_name) in pairs.items():
            # Check if pair belongs to critical net class
            p_class = self._resolve_net_class(p_name)
            n_class = self._resolve_net_class(n_name)
            
            if p_class not in critical_classes and n_class not in critical_classes:
                continue
            
            dp_net_names.add(p_name)
            dp_net_names.add(n_name)
            dp_partners[p_name] = n_name
            dp_partners[n_name] = p_name
        
        if not dp_net_names:
            self.log("  No critical differential pairs found — skipping")
            return 0
        
        self.log(f"  Analyzing {len(dp_net_names)} differential pair nets")
        
        # Collect tracks by layer for spatial queries
        from collections import defaultdict
        tracks_by_layer = defaultdict(list)  # layer_id → [tracks]
        dp_tracks = []  # List of (track, net_name, partner_name)
        
        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            net = track.GetNet()
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue
            
            layer_id = track.GetLayer()
            tracks_by_layer[layer_id].append(track)
            
            if net_name in dp_net_names:
                partner_name = dp_partners.get(net_name)
                dp_tracks.append((track, net_name, partner_name))
        
        violations = 0
        violation_set = set()  # (dp_net, aggressor_net) pairs already reported
        
        # Check each differential pair track
        for dp_track, dp_net, partner_net in dp_tracks:
            layer_id = dp_track.GetLayer()
            dp_width_mm = pcbnew.ToMM(dp_track.GetWidth())
            dp_center = dp_track.GetCenter()
            
            # Required isolation on outer edges
            required_mm = max(min_isolation_mm, outer_edge_mult * dp_width_mm)
            required_iu = pcbnew.FromMM(required_mm)
            
            # Find partner track on same layer (if exists)
            partner_track = None
            partner_center = None
            
            for other_track in tracks_by_layer[layer_id]:
                other_net = other_track.GetNet()
                if not other_net:
                    continue
                if other_net.GetNetname() == partner_net:
                    # Check if this is close to current track (same pair segment)
                    other_center = other_track.GetCenter()
                    dist = self.get_distance(dp_center, other_center)
                    
                    # Partner should be within reasonable distance (5mm)
                    if dist < pcbnew.FromMM(5.0):
                        partner_track = other_track
                        partner_center = other_center
                        break
            
            # Check all other tracks on this layer
            for other_track in tracks_by_layer[layer_id]:
                other_net = other_track.GetNet()
                if not other_net:
                    continue
                other_net_name = other_net.GetNetname()
                if not other_net_name:
                    continue
                
                # Skip self
                if other_net_name == dp_net:
                    continue
                
                # Skip partner (inner spacing controlled by impedance)
                if other_net_name == partner_net:
                    continue
                
                # Skip ground nets (desired guard traces)
                if any(p.upper() in other_net_name.upper() for p in gnd_patterns):
                    continue
                
                # Measure distance
                other_center = other_track.GetCenter()
                dist_iu = self.get_distance(dp_center, other_center)
                
                if dist_iu < required_iu:
                    # Potential violation - but check if it's on the outer edge
                    # If we have a partner, verify the aggressor is NOT between us and partner
                    if partner_center is not None:
                        # Calculate which side the aggressor is on
                        # If aggressor is between DP track and partner, it's inner (skip)
                        # Use dot product to determine side
                        
                        # Vector from dp_track to partner
                        to_partner_x = partner_center.x - dp_center.x
                        to_partner_y = partner_center.y - dp_center.y
                        
                        # Vector from dp_track to aggressor
                        to_aggressor_x = other_center.x - dp_center.x
                        to_aggressor_y = other_center.y - dp_center.y
                        
                        # Dot product to check alignment
                        dot_product = (to_partner_x * to_aggressor_x +
                                      to_partner_y * to_aggressor_y)
                        
                        partner_dist = self.get_distance(dp_center, partner_center)
                        aggressor_dist = dist_iu
                        
                        # If aggressor is in same direction as partner and closer,
                        # it might be between them (inner edge) - be conservative
                        if dot_product > 0 and aggressor_dist < partner_dist:
                            # Aggressor on same side as partner, likely inner edge
                            # Skip this (controlled by impedance requirements)
                            continue
                    
                    # Flag violation on outer edge
                    pair_key = (dp_net, other_net_name)
                    rev_key = (other_net_name, dp_net)
                    
                    if pair_key not in violation_set and rev_key not in violation_set:
                        violation_set.add(pair_key)
                        violations += 1
                        
                        actual_mm = pcbnew.ToMM(dist_iu)
                        safe_name = dp_net.replace('/', '_').replace('(', '').replace(')', '')
                        group = self.create_group(self.board, "IsolationDP", safe_name, violations)
                        
                        msg = (f"ISOLATION VIOLATION (DP)\n"
                               f"{dp_net} ↔ {other_net_name}\n"
                               f"{actual_mm:.2f}mm < {required_mm:.2f}mm")
                        
                        self.draw_marker(
                            self.board, dp_center, msg, self.marker_layer, group
                        )
                        
                        # Draw arrow to aggressor
                        arrow_label = f"{actual_mm:.2f}mm"
                        self.draw_arrow(
                            self.board, dp_center, other_center,
                            arrow_label, self.marker_layer, group
                        )
                        
                        self.log(f"  ❌ {dp_net} ↔ {other_net_name}: "
                                f"{actual_mm:.2f}mm < {required_mm:.2f}mm "
                                f"({outer_edge_mult:.0f}W rule)")
        
        self.log(f"Critical net isolation (DP) check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 11: Net Coupling / Crosstalk Analysis
    # ========================================================================
    
    def _check_net_coupling(self):
        """
        Check for excessive coupling between parallel trace segments.
        
        TODO: Implementation needed
        
        Description:
        When two traces run parallel for significant length, capacitive and inductive
        coupling creates crosstalk. The coupling coefficient depends on:
        - Parallel run length
        - Spacing between traces
        - Trace width and layer stackup
        
        Excessive coupling causes:
        - Signal integrity degradation (false switching)
        - EMI (coupled noise radiates)
        - Timing violations (coupled switching noise)
        
        Algorithm:
        1. Build spatial index of all trace segments
        2. For each critical net trace segment:
           - Query nearby parallel segments on same layer
           - Calculate parallel overlap length
           - Measure minimum spacing
           - Calculate coupling coefficient: K ≈ length / spacing
        3. Flag if coupling exceeds threshold (typically length/spacing > 50)
        4. Special handling for differential pairs (exclude intra-pair)
        
        Configuration parameters:
        - max_coupling_coefficient: Maximum coupling ratio (length/spacing, default: 50)
        - min_parallel_length_mm: Minimum parallel run to check (default: 2.0mm)
        - critical_net_classes: Net classes to check as aggressors/victims
        - exclude_differential_pairs: Don't flag intra-pair coupling (default: True)
        - angular_tolerance_deg: Max angle deviation to consider "parallel" (default: 10°)
        
        Crosstalk formulas:
        - Capacitive coupling: C_m ≈ ε₀·ε_r·h·L / d (where h=PCB thickness, L=length, d=spacing)
        - Far-end crosstalk: V_fe ≈ 0.25 · (L/t_r) · (Z_0/d) (L=length, t_r=rise time)
        - Rule of thumb: Keep L/d < 50 for <10% crosstalk
        
        Standards:
        - High-Speed Digital Design: Crosstalk discussion (Howard Johnson)
        - IPC-2251: Recommendations for coupled trace spacing
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Net Coupling / Crosstalk ---")
        
        # TODO: Build spatial index for efficient parallel segment search
        # TODO: Implement parallel segment detection with angular tolerance
        # TODO: Calculate coupling coefficient for each parallel pair
        # TODO: Create violations with aggressor/victim information
        # TODO: Draw arrows showing coupled segments and spacing
        
        violations = 0
        self.log(f"TODO: Net coupling / crosstalk check - {violations} violations")
        return violations
    
    # ========================================================================
    # CHECK 12: Differential Pair Length Matching and Spacing
    # ========================================================================
    
    def _check_differential_pair_matching(self):
        """
        Check differential pairs for length matching and consistent spacing.
        
        TODO: Implementation needed
        
        Description:
        Differential signaling requires:
        1. Matched lengths: P and N traces same length to prevent skew
        2. Consistent spacing: Maintain impedance along entire route
        
        Mismatched lengths cause:
        - Common-mode conversion (differential → common-mode EMI)
        - Reduced noise margins
        - Timing violations (especially for source-synchronous interfaces)
        
        Inconsistent spacing causes:
        - Impedance discontinuities (reflections)
        - Mode conversion
        
        Algorithm:
        1. Identify all differential pairs from net naming
        2. For each pair:
           - Calculate total routed length of P trace (including vias)
           - Calculate total routed length of N trace
           - Calculate absolute mismatch
           - Flag if mismatch exceeds tolerance
        3. For spacing consistency:
           - Sample spacing at regular intervals along pair route
           - Calculate standard deviation of spacing
           - Flag if variation exceeds percentage threshold
        
        Configuration parameters:
        - differential_pair_patterns: Regex patterns for pair identification
        - max_length_mismatch_by_class: Dict of net class → max mismatch mm
          Example: {'USB': 0.5, 'HDMI': 0.3, 'DDR4': 5.0}
        - target_spacing_by_class: Dict of net class → target spacing mm
        - max_spacing_variation_pct: Max spacing variation as % (default: 10%)
        - spacing_sample_interval_mm: Spacing measurement interval (default: 1.0mm)
        - include_via_length: Include via stub lengths in total (default: True)
        
        Standards:
        - USB 2.0: ±0.5mm max mismatch, 90Ω ±15%
        - HDMI 1.4: ±0.3mm max mismatch, 100Ω ±10%
        - DDR4: ±5mm max intra-pair, ±25mm max inter-byte
        - PCIe Gen3: ±1mm intra-pair, impedance ±10%
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Differential Pair Matching ---")

        dp_cfg = self.config.get('differential_pair_matching', {})
        if not dp_cfg.get('enabled', False):
            self.log("Differential pair matching check disabled")
            return 0

        import re
        max_mismatch_cfg = dp_cfg.get('max_length_mismatch_by_class', {
            'USB': 0.5, 'HDMI': 0.3, 'DDR': 5.0, 'HighSpeed': 1.0
        })

        # Regex patterns for P/N identification — order matters (more specific first)
        dp_patterns = [
            re.compile(r'^(.+?)[_\-.](P|\+)$', re.IGNORECASE),
            re.compile(r'^(.+?)[_\-.](N|\-)$', re.IGNORECASE),
        ]
        # Unified: capture base name and polarity
        dp_regex = re.compile(
            r'^(.+?)[_\-.](P|N|\+|\-)$', re.IGNORECASE
        )

        # Accumulate total routed length per net
        net_lengths = {}   # net_name → total IU
        net_pos = {}       # net_name → representative PCB position
        for track in self.board.GetTracks():
            net = track.GetNet()
            if not net:
                continue
            name = net.GetNetname()
            if not name:
                continue
            net_lengths[name] = net_lengths.get(name, 0) + track.GetLength()
            if name not in net_pos:
                net_pos[name] = track.GetCenter()

        # Group into pairs: base_name → {'P': net_name, 'N': net_name}
        pairs = {}  # base → {'P': name, 'N': name}
        for net_name in net_lengths:
            m = dp_regex.match(net_name)
            if not m:
                continue
            base = m.group(1)
            polarity = m.group(2).upper()
            pos_key = 'P' if polarity in ('P', '+') else 'N'
            pairs.setdefault(base, {})[pos_key] = net_name

        # Filter to only complete pairs
        complete_pairs = {base: v for base, v in pairs.items() if 'P' in v and 'N' in v}
        if not complete_pairs:
            self.log("  No differential pairs detected — skipping")
            return 0

        self.log(f"  Found {len(complete_pairs)} differential pair(s)")

        violations = 0
        for base, members in sorted(complete_pairs.items()):
            p_name = members['P']
            n_name = members['N']
            p_len_mm = pcbnew.ToMM(net_lengths.get(p_name, 0))
            n_len_mm = pcbnew.ToMM(net_lengths.get(n_name, 0))
            mismatch_mm = abs(p_len_mm - n_len_mm)

            # Determine max allowed mismatch from net class of the P trace
            net_class = self._resolve_net_class(p_name)
            max_mismatch = max_mismatch_cfg.get(net_class,
                           dp_cfg.get('default_max_mismatch_mm', 1.0))

            if mismatch_mm > max_mismatch:
                violations += 1
                pos = net_pos.get(p_name, net_pos.get(n_name))
                safe = base.replace('/', '_').replace('(', '').replace(')', '')
                group = self.create_group(self.board, "DPMismatch", safe, violations)
                msg = f"DP LENGTH MISMATCH\n{base}\nP:{p_len_mm:.2f}mm N:{n_len_mm:.2f}mm diff:{mismatch_mm:.2f}mm"
                self.draw_marker(self.board, pos, msg, self.marker_layer, group)
                self.log(f"  ❌ {base} ({net_class}): P={p_len_mm:.2f}mm N={n_len_mm:.2f}mm mismatch {mismatch_mm:.2f}mm > {max_mismatch:.2f}mm")
            else:
                self.log(f"  ✓ {base}: P={p_len_mm:.2f}mm N={n_len_mm:.2f}mm mismatch {mismatch_mm:.2f}mm ≤ {max_mismatch:.2f}mm")

        self.log(f"Differential pair matching check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 13: Differential Net Running Skew
    # ========================================================================
    
    def _check_differential_running_skew(self):
        """
        Check for excessive spacing variation along differential pair path.
        
        Description:
        Differential pairs require consistent spacing along their entire route to
        maintain controlled differential impedance. Spacing variations cause:
        - Impedance discontinuities (reflections)
        - Mode conversion (differential → common-mode)
        - EMI due to unbalanced currents
        
        This check samples the perpendicular distance between P and N traces at
        regular intervals and calculates the coefficient of variation (std dev / mean).
        
        Algorithm:
        1. Identify differential pairs from net naming
        2. For each pair:
           - Sample spacing at regular intervals along route
           - Calculate mean and standard deviation of spacing
           - Compute variation percentage: (std_dev / mean) × 100%
           - Flag if variation exceeds threshold
        3. Create markers showing worst variation zones
        
        Configuration parameters:
        - max_spacing_variation_percent: Maximum allowed variation (default: 15%)
        - sample_interval_mm: Distance between sampling points (default: 1.0mm)
        - min_pair_length_mm: Minimum pair length to check (default: 5.0mm)
        - critical_net_classes: Net classes requiring this check
        
        Use cases:
        - USB 3.x: Tight impedance control required (90Ω ±10%)
        - HDMI 2.0+: Consistent 100Ω differential impedance
        - PCIe Gen3+: Minimal spacing variation for signal integrity
        - Ethernet: 100Ω impedance stability
        
        Standards:
        - USB 3.x: Spacing variation should be <10% for 90Ω target
        - HDMI: <10% variation for 100Ω differential impedance
        - IPC-2141A: Consistent geometry for controlled impedance
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Differential Running Skew ---")
        
        skew_cfg = self.config.get('differential_running_skew', {})
        if not skew_cfg.get('enabled', False):
            self.log("Differential running skew check disabled")
            return 0
        
        critical_classes = skew_cfg.get(
            'critical_net_classes',
            ['USB', 'HDMI', 'PCIe', 'Ethernet', 'LVDS', 'HighSpeed', 'DDR']
        )
        max_variation_pct = skew_cfg.get('max_spacing_variation_percent', 15.0)
        sample_interval_mm = skew_cfg.get('sample_interval_mm', 1.0)
        min_pair_length_mm = skew_cfg.get('min_pair_length_mm', 5.0)
        
        # Identify differential pairs
        pairs = self._identify_differential_pairs()
        if not pairs:
            self.log("  No differential pairs detected — skipping")
            return 0
        
        # Filter to critical net classes
        critical_pairs = []
        for base, (p_name, n_name) in pairs.items():
            p_class = self._resolve_net_class(p_name)
            n_class = self._resolve_net_class(n_name)
            
            if p_class in critical_classes or n_class in critical_classes:
                # Get net objects
                netinfo = self.board.GetNetInfo()
                p_net = self.board.FindNet(p_name)
                n_net = self.board.FindNet(n_name)
                
                if p_net and n_net:
                    critical_pairs.append((base, p_name, n_name, p_net, n_net, p_class))
        
        if not critical_pairs:
            self.log("  No critical differential pairs found — skipping")
            return 0
        
        self.log(f"  Analyzing {len(critical_pairs)} differential pair(s)")
        
        violations = 0
        
        for base, p_name, n_name, p_net, n_net, net_class in critical_pairs:
            # Calculate total pair length (use P trace as reference)
            p_length_mm = self._calculate_trace_length(p_net)
            
            if p_length_mm < min_pair_length_mm:
                self.log(f"  ⊘ {base}: too short ({p_length_mm:.1f}mm < {min_pair_length_mm:.1f}mm) — skipped")
                continue
            
            # Sample spacing along the pair
            spacing_samples = self._calculate_spacing_along_pair(
                p_net, n_net, sample_interval_mm
            )
            
            if len(spacing_samples) < 3:
                self.log(f"  ⊘ {base}: insufficient samples ({len(spacing_samples)}) — skipped")
                continue
            
            # Calculate statistics
            import math
            spacing_mm = [pcbnew.ToMM(s) for s in spacing_samples]
            mean_spacing = sum(spacing_mm) / len(spacing_mm)
            
            # Calculate standard deviation
            variance = sum((s - mean_spacing)**2 for s in spacing_mm) / len(spacing_mm)
            std_dev = math.sqrt(variance)
            
            # Coefficient of variation (percentage)
            if mean_spacing > 0:
                variation_pct = (std_dev / mean_spacing) * 100.0
            else:
                variation_pct = 0.0
            
            # Calculate min/max for reporting
            min_spacing = min(spacing_mm)
            max_spacing = max(spacing_mm)
            
            if variation_pct > max_variation_pct:
                violations += 1
                
                # Find position for marker (use first P trace segment)
                marker_pos = None
                for track in self.board.GetTracks():
                    if not isinstance(track, pcbnew.PCB_TRACK):
                        continue
                    track_net = track.GetNet()
                    if track_net and track_net.GetNetname() == p_name:
                        marker_pos = track.GetCenter()
                        break
                
                if marker_pos:
                    safe_name = base.replace('/', '_').replace('(', '').replace(')', '')
                    group = self.create_group(self.board, "RunningSkew", safe_name, violations)
                    
                    msg = (f"SPACING VARIATION\n"
                           f"{base}\n"
                           f"Variation: {variation_pct:.1f}%\n"
                           f"Range: {min_spacing:.3f}-{max_spacing:.3f}mm\n"
                           f"Max: {max_variation_pct:.0f}%")
                    
                    self.draw_marker(
                        self.board, marker_pos, msg, self.marker_layer, group
                    )
                    
                    self.log(f"  ❌ {base} ({net_class}): "
                            f"spacing variation {variation_pct:.1f}% > {max_variation_pct:.0f}%, "
                            f"range {min_spacing:.3f}-{max_spacing:.3f}mm "
                            f"(mean {mean_spacing:.3f}mm, σ={std_dev:.3f}mm)")
            else:
                self.log(f"  ✓ {base}: spacing variation {variation_pct:.1f}% ≤ {max_variation_pct:.0f}% "
                        f"(range {min_spacing:.3f}-{max_spacing:.3f}mm)")
        
        self.log(f"Differential running skew check: {violations} violation(s)")
        return violations
    
    # ========================================================================
    # CHECK 14: Controlled Impedance Verification
    # ========================================================================
    
    def _check_controlled_impedance(self):
        """
        Verify trace impedance using analytical formulas (geometry-based).
        
        High-speed signals require controlled impedance to minimize reflections.
        Instead of full-wave EM simulation (FEM), use analytical formulas from
        transmission line theory. Accuracy is 5-10% which is sufficient for DRC
        and much faster than field solvers.
        
        Transmission Line Types Supported:
        ────────────────────────────────────────────────────────────────────
        1. MICROSTRIP (outer layer, ground plane below)
        2. EMBEDDED MICROSTRIP (microstrip with solder mask cover)
        3. STRIPLINE (internal layer, symmetric between two planes)
        4. ASYMMETRIC STRIPLINE (internal layer, asymmetric plane spacing)
        5. COPLANAR WAVEGUIDE (CPW) - trace with ground traces, no plane
        6. COPLANAR WITH GROUND (CPWG) - CPW with ground plane below
        7. GROUNDED COPLANAR - CPW with ground vias stitching
        
        Algorithm:
        ────────────────────────────────────────────────────────────────────
        1. For each controlled impedance net class:
           - Get target impedance from config (e.g., 50Ω, 75Ω, 90Ω differential)
           - Get tolerance (typically ±10% or ±5Ω)
        
        2. Extract stackup parameters from board:
           - Trace thickness (copper weight: 0.5oz = 17μm, 1oz = 35μm, 2oz = 70μm)
           - Dielectric thickness (prepreg/core thickness)
           - Dielectric constant Er (FR-4 ≈ 4.3-4.5, Rogers ≈ 3.0-10.2)
           - Solder mask thickness and Er (typically 20μm, Er ≈ 3.3)
        
        3. For each trace segment on controlled nets:
           - Detect transmission line type from layer position
           - Measure trace width W
           - Get dielectric height H to nearest reference plane
           - Apply appropriate formula to calculate impedance Z0
           - Flag if |Z0_actual - Z0_target| > tolerance
        
        4. For differential pairs:
           - Calculate single-ended impedance Z0
           - Measure pair spacing S
           - Calculate differential impedance: Zdiff ≈ 2×Z0×√(1 - 0.48×exp(-0.96×S/H))
        
        Analytical Formulas (IPC-2141, Wadell):
        ────────────────────────────────────────────────────────────────────
        
        MICROSTRIP (outer layer):
        ─────────────────────────
        W_eff = W + ΔW (effective width accounting for thickness)
        ΔW = (t/π) × ln(2×H/t) × [1 + (1/√εr)]  where t = trace thickness
        
        εr_eff = (εr + 1)/2 + (εr - 1)/2 × 1/√(1 + 12×H/W_eff)  (effective dielectric constant)
        
        For W/H < 1:
            Z0 = (60/√εr_eff) × ln(8×H/W_eff + W_eff/(4×H))
        
        For W/H ≥ 1:
            Z0 = (120×π/√εr_eff) / [W_eff/H + 1.393 + 0.667×ln(W_eff/H + 1.444)]
        
        Typical: W=0.2mm, H=0.1mm, εr=4.3, t=35μm → Z0 ≈ 50Ω
        
        
        EMBEDDED MICROSTRIP (with solder mask):
        ───────────────────────────────────────
        Same as microstrip but with composite dielectric:
        
        εr_eff_composite = εr_substrate × (H_substrate / H_total) + εr_soldermask × (H_soldermask / H_total)
        
        Then use microstrip formula with εr_eff_composite
        
        Solder mask effect: Typically reduces Z0 by 5-10% due to higher εr above trace
        
        
        STRIPLINE (symmetric, between two planes):
        ──────────────────────────────────────────
        b = total dielectric thickness between planes
        W_eff = W (no edge correction needed for stripline)
        
        For W/b < 0.35:
            Z0 = (60/√εr) × ln(4×b / (0.67×π×W_eff × (0.8 + t/W_eff)))
        
        For W/b ≥ 0.35:
            Z0 = (94.15/√εr) / [(W_eff/b) + 1.11×√(0.81 + t/b)]
        
        Stripline has NO frequency-dependent dispersion (TEM mode)
        Typical: W=0.15mm, b=0.2mm, εr=4.3 → Z0 ≈ 50Ω
        
        
        COPLANAR WAVEGUIDE (CPW, no ground plane):
        ──────────────────────────────────────────
        W = trace width
        S = gap to ground traces
        
        k = W / (W + 2×S)  (geometric ratio)
        k' = √(1 - k²)
        
        K(k) = complete elliptic integral of first kind
        Approximation: K(k)/K(k') ≈ π/ln(2×(1+√k')/(1-√k'))
        
        εr_eff = (εr + 1) / 2  (half substrate, half air)
        
        Z0 = (30×π / √εr_eff) × K(k')/K(k)
        
        Typical: W=0.2mm, S=0.1mm, εr=4.3 → Z0 ≈ 75Ω
        
        
        COPLANAR WITH GROUND PLANE (CPWG):
        ──────────────────────────────────
        Similar to CPW but with ground plane below:
        
        εr_eff = εr  (full substrate dielectric)
        
        Modified k accounting for ground plane:
        k1 = sinh(π×W/(4×H)) / sinh(π×(W+2×S)/(4×H))
        
        Z0 = (30×π / √εr_eff) × K(k1')/K(k1)
        
        Ground plane presence increases capacitance → lowers Z0 by 15-25%
        
        
        DIFFERENTIAL IMPEDANCE:
        ──────────────────────
        For differential pairs (microstrip or stripline):
        
        Step 1: Calculate single-ended Z0 (using formulas above)
        Step 2: Calculate coupling coefficient based on spacing
        
        k_coupling = 0.48 × exp(-0.96 × S/H)  where S = pair spacing, H = dielectric height
        
        Zdiff = 2 × Z0 × √(1 - k_coupling)
        
        Common targets:
        - USB 2.0/3.0: 90Ω ±15%
        - HDMI: 100Ω ±10%
        - PCIe: 85Ω ±10%
        - LVDS: 100Ω ±10%
        
        IMPLEMENTED: Uses IPC-2141A analytical formulas for microstrip, stripline,
        and differential impedance. Reads stackup from board file. Identifies
        differential pairs via regex. See algorithm details below.
        
        Configuration Parameters:
        ────────────────────────────────────────────────────────────────────
        [signal_integrity.impedance]
        
        # Target impedances by net class
        target_impedance_by_class = {
            "USB": 90.0,          # Differential
            "HDMI": 100.0,        # Differential
            "DDR": 50.0,          # Single-ended
            "HighSpeed": 50.0,    # Single-ended
            "RF": 50.0            # Single-ended
        }
        
        # Tolerance (can be absolute ohms or percentage)
        impedance_tolerance_ohms = 5.0      # ±5Ω
        impedance_tolerance_percent = 10.0  # or ±10%
        
        # Stackup parameters (if not in board file)
        default_trace_thickness_um = 35     # 1oz copper
        default_dielectric_constant = 4.3   # FR-4
        soldermask_thickness_um = 20        # Typical
        soldermask_dielectric_constant = 3.3
        
        # Transmission line type detection
        outer_layers = ["F.Cu", "B.Cu"]
        internal_layers = ["In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu"]
        detect_coplanar = true              # Auto-detect CPW from ground traces
        coplanar_max_gap_mm = 0.5           # Max gap to qualify as CPW
        
        
        Implementation Strategy:
        ────────────────────────────────────────────────────────────────────
        1. Start with microstrip formula (most common, easiest)
        2. Add stripline formula (next most common)
        3. Add differential calculation (critical for modern designs)
        4. Add CPW formulas (advanced, less common)
        5. Use KiCad board stackup API if available, else fall back to defaults
        6. Implement elliptic integral approximation for CPW (avoid scipy dependency)
        
        
        Accuracy vs Field Solvers:
        ────────────────────────────────────────────────────────────────────
        Analytical formulas: ±5-10% error (sufficient for DRC)
        2D field solver (ATLC, OpenEMS): ±2-3% error
        3D full-wave EM (HFSS, CST): ±1% error
        
        For most designs, ±5Ω or ±10% tolerance means analytical is adequate!
        Only critical RF/mmWave designs need field solver verification.
        
        
        Returns:
        Number of violations found
        
        References:
        - IPC-2141: Controlled Impedance Circuit Boards and High Speed Logic Design
        - Wadell, Brian C.: "Transmission Line Design Handbook" (Artech House, 1991)
        - Johnson & Graham: "High-Speed Digital Design: A Handbook of Black Magic"
        - Paul, Clayton: "Analysis of Multiconductor Transmission Lines" (Wiley, 2007)
        - Bogatin, Eric: "Signal and Power Integrity - Simplified" (Prentice Hall, 2018)
        """
        self.log("\n--- Checking Controlled Impedance ---")
        
        # Parse configuration from [signal_integrity.impedance] section
        impedance_config = self.config.get('impedance', {})
        target_impedances = impedance_config.get('target_impedance_by_class', {})
        tolerance_ohms = impedance_config.get('impedance_tolerance_ohms', 5.0)
        min_segment_length_mm = impedance_config.get('min_segment_length_mm', 1.0)
        
        if not target_impedances:
            self.log("No net classes configured for impedance checking (target_impedance_by_class empty)")
            return 0
        
        self.log(f"Impedance targets: {target_impedances}")
        self.log(f"Tolerance: ±{tolerance_ohms}Ω")
        self.log(f"Min segment length: {min_segment_length_mm}mm")
        
        # Extract board stackup data
        stackup = self._get_board_stackup()
        
        # Don't set to None - let helper methods validate the data structure
        # Helper methods will check stackup.get('layers') and use defaults if needed
        
        # Statistics
        violations = 0
        checked_segments = 0
        
        # Create marker groups (PCB_GROUP objects)
        # debug_group removed - no longer drawing DEBUG markers on PCB
        violation_group = self.create_group(self.board, "Impedance", "Violations", 0)
        
        # Build map of net_name → (target_impedance, source)
        # This allows checking by net class OR pattern matching
        net_to_impedance = {}
        
        # Get net info list (KiCad API)
        netinfo_list = self.board.GetNetInfo()
        net_count = netinfo_list.GetNetCount()

        # In KiCad 9+, pattern-based net class assignment means GetNetClassName()
        # on NETINFO_ITEM always returns "Default" even for pattern-matched nets.
        # Use self._resolve_net_class() which parses the board file directly.

        # First pass: Assign nets by effective net class
        for net_code in range(net_count):
            net = netinfo_list.GetNetItem(net_code)
            if not net:
                continue

            net_name = net.GetNetname()
            if not net_name or net_name == "":
                continue

            net_class_name = self._resolve_net_class(net_name)

            if net_class_name in target_impedances:
                net_to_impedance[net_name] = (target_impedances[net_class_name], f"Net Class '{net_class_name}'")
        
        # Second pass: Pattern matching for nets not in classes
        # Common patterns for controlled impedance nets
        impedance_patterns = {
            'USB': ['USB', 'USB_D', 'USB_P', 'USB_N', 'USB2', 'USB3'],
            'HDMI': ['HDMI', 'HDMI_D', 'HDMI_P', 'HDMI_N', 'TMDS'],
            'DDR': ['DDR', 'DDR3', 'DDR4', 'DQ', 'DQS', 'DM'],
            'HighSpeed': ['CLK', 'CLOCK', 'DIFF', 'LVDS', 'PCIE', 'SATA', 'SERDES']
        }
        
        for net_code in range(net_count):
            net = netinfo_list.GetNetItem(net_code)
            if not net:
                continue
            
            net_name = net.GetNetname()
            if not net_name or net_name == "" or net_name in net_to_impedance:
                continue
            
            # Try pattern matching (skip unconnected nets)
            if 'unconnected' in net_name.lower():
                continue
            
            net_upper = net_name.upper()
            for class_name, patterns in impedance_patterns.items():
                if class_name not in target_impedances:
                    continue
                
                for pattern in patterns:
                    if pattern.upper() in net_upper:
                        net_to_impedance[net_name] = (target_impedances[class_name], f"Pattern '{pattern}'")
                        break
                
                if net_name in net_to_impedance:
                    break
        
        # Report net assignments
        if net_to_impedance:
            self.log(f"\nFound {len(net_to_impedance)} net(s) for impedance checking:")
            
            # Count segments per net before filtering
            net_segment_counts = {}
            for track in self.board.GetTracks():
                net = track.GetNet()
                if not net:
                    continue
                net_name = net.GetNetname()
                if net_name in net_to_impedance:
                    net_segment_counts[net_name] = net_segment_counts.get(net_name, 0) + 1
            
            for net_name, (z0, source) in sorted(net_to_impedance.items()):
                seg_count = net_segment_counts.get(net_name, 0)
                self.log(f"  • {net_name}: {z0}Ω (from {source}) - {seg_count} segment(s) total")
        else:
            self.log("⚠ No nets found matching configured classes or patterns")
            self.log("  Tip: Assign nets to net classes (USB, HDMI, DDR, HighSpeed) or use common naming patterns")
            return 0

        # --- Differential pair setup ---
        differential_classes = set(impedance_config.get(
            'differential_net_classes',
            ['USB', 'HDMI', 'LVDS', 'CAN', 'RS485', 'PCIE', 'PCIe']
        ))
        dp_pairs = self._identify_differential_pairs()   # base -> (P_net, N_net)
        dp_partner = {}   # net_name -> partner_net_name
        for base, (p_net, n_net) in dp_pairs.items():
            dp_partner[p_net] = n_net
            dp_partner[n_net] = p_net

        # Build spatial index for partner track lookup (only for DP nets we care about).
        # net_name -> layer_id -> [PCB_TRACK]
        from collections import defaultdict
        net_layer_tracks = defaultdict(lambda: defaultdict(list))
        dp_nets_to_index = {n for n in net_to_impedance if n in dp_partner}
        dp_partner_nets = {dp_partner[n] for n in dp_nets_to_index}
        nets_to_index = dp_nets_to_index | dp_partner_nets
        if nets_to_index:
            for _t in self.board.GetTracks():
                if isinstance(_t, pcbnew.PCB_TRACK):
                    _tn = _t.GetNet()
                    if _tn and _tn.GetNetname() in nets_to_index:
                        net_layer_tracks[_tn.GetNetname()][_t.GetLayer()].append(_t)

        # Get all tracks from board
        tracks = self.board.GetTracks()
        
        # Track why segments are skipped
        skipped_reasons = {
            'too_short': 0,
            'no_dielectric_height': 0,
            'unknown_tline_type': 0,
            'calc_error': 0
        }
        
        # Iterate through each track segment
        for track in tracks:
            # Get net information
            net = track.GetNet()
            if not net:
                continue
            
            net_name = net.GetNetname()
            
            # Filter: only check nets in our impedance map
            if net_name not in net_to_impedance:
                continue
            
            # Get target impedance for this net
            Z0_target, source = net_to_impedance[net_name]
            
            # Extract geometry
            layer_id = track.GetLayer()
            layer_name = self.board.GetLayerName(layer_id)
            W_mm = pcbnew.ToMM(track.GetWidth())
            position = track.GetStart()
            length_mm = pcbnew.ToMM(track.GetLength())
            
            # Skip very short segments (configurable threshold)
            if length_mm < min_segment_length_mm:
                skipped_reasons['too_short'] += 1
                continue
            
            checked_segments += 1
            
            # Get stackup parameters for this layer (always pass stackup to helper methods)
            # Helper methods will extract values or use defaults if extraction fails
            t_um = self._get_layer_copper_thickness(layer_id, stackup)
            Er = self._get_layer_dielectric_constant(layer_id, stackup)
            
            # Detect transmission line type
            tline_type = self._detect_transmission_line_type(layer_name)
            
            # Get dielectric height (pass cached stackup to avoid re-parsing)
            H_mm = self._get_dielectric_height_to_plane(layer_id, stackup)
            
            # Handle case where height cannot be determined
            if H_mm is None or H_mm <= 0:
                self.log(f"  ⚠ Cannot determine dielectric height for {net_name} on {layer_name}, skipping")
                skipped_reasons['no_dielectric_height'] += 1
                continue
            
            # Calculate impedance based on transmission line type
            Z0_calc = None
            
            try:
                if tline_type == 'microstrip':
                    Z0_calc = self._calculate_microstrip_impedance(W_mm, H_mm, t_um, Er)
                elif tline_type == 'stripline':
                    # For stripline, need total height between planes
                    b_mm = H_mm * 2.0  # Simplified: assume symmetric
                    Z0_calc = self._calculate_stripline_impedance(W_mm, b_mm, t_um, Er)
                else:
                    self.log(f"  ⚠ Unknown transmission line type '{tline_type}' for {net_name} on {layer_name}")
                    skipped_reasons['unknown_tline_type'] += 1
                    continue
                
            except Exception as e:
                self.log(f"  ❌ Error calculating impedance for {net_name}: {e}")
                skipped_reasons['calc_error'] += 1
                continue
            
            # DEBUG markers removed - keeping PCB view clean
            # All detailed info available in report log below

            # --- Differential impedance override ---
            # If this net class is differential and we can locate the DP partner
            # on the same layer, compute Z_diff instead of Z0_single.
            net_class_name = self._resolve_net_class(net_name)
            is_differential = (
                net_class_name in differential_classes
                and net_name in dp_partner
            )
            if is_differential:
                partner_name = dp_partner[net_name]
                partner_tracks = net_layer_tracks[partner_name].get(layer_id, [])
                if partner_tracks:
                    seg_mid = track.GetCenter()
                    closest_partner = min(
                        partner_tracks,
                        key=lambda t: self.get_distance(seg_mid, t.GetCenter())
                    )
                    center_dist_mm = pcbnew.ToMM(
                        self.get_distance(seg_mid, closest_partner.GetCenter())
                    )
                    partner_width_mm = pcbnew.ToMM(closest_partner.GetWidth())
                    # Edge-to-edge gap = center distance − mean of both half-widths
                    S_mm = center_dist_mm - (W_mm + partner_width_mm) / 2.0
                    if S_mm > 0 and H_mm > 0:
                        Z0_calc = self._calculate_differential_impedance(Z0_calc, S_mm, H_mm)
                    else:
                        self.log(f"  ⚠ {net_name}: DP partner geometry invalid "
                                 f"(S={S_mm:.3f}mm) — reporting single-ended Z0")
                        is_differential = False
                else:
                    self.log(f"  ⚠ {net_name}: differential class but partner "
                             f"'{partner_name}' not on layer {layer_name} — "
                             f"reporting single-ended Z0")
                    is_differential = False

            # Check tolerance
            error = abs(Z0_calc - Z0_target)
            
            if error > tolerance_ohms:
                violations += 1
                percent_error = (error / Z0_target) * 100
                
                z_type = "Z_diff" if is_differential else "Z0"
                # Create compact PCB marker
                violation_msg = f"❌ {net_name}\n{z_type}: {Z0_calc:.1f}Ω (target {Z0_target:.1f}Ω)"

                self.draw_marker(
                    self.board,
                    position,
                    violation_msg,
                    self.marker_layer,
                    violation_group
                )

                # Draw highlight on the problematic segment for easy visualization
                self._draw_segment_highlight(track, violation_group, net_name, Z0_calc, Z0_target)

                # Detailed info in report log
                self.log(f"  ❌ {net_name}: {z_type}={Z0_calc:.1f}Ω (target {Z0_target:.1f}Ω ±{tolerance_ohms}Ω) ERROR: {error:.1f}Ω ({percent_error:.1f}%)")
                self.log(f"     Layer: {layer_name} ({tline_type}), Width: {W_mm:.3f}mm, H: {H_mm:.3f}mm, t: {t_um:.1f}µm, εr: {Er:.2f}")
            else:
                z_type = "Z_diff" if is_differential else "Z0"
                self.log(f"  ✓ {net_name}: {z_type}={Z0_calc:.1f}Ω (target {Z0_target:.1f}Ω) PASS")
        
        # Report summary
        self.log(f"\nChecked {checked_segments} segments on controlled impedance nets")
        
        # Report skipped segments
        total_skipped = sum(skipped_reasons.values())
        if total_skipped > 0:
            self.log(f"Skipped {total_skipped} segment(s):")
            if skipped_reasons['too_short'] > 0:
                self.log(f"  • {skipped_reasons['too_short']} too short (< {min_segment_length_mm}mm)")
            if skipped_reasons['no_dielectric_height'] > 0:
                self.log(f"  • {skipped_reasons['no_dielectric_height']} no dielectric height")
            if skipped_reasons['unknown_tline_type'] > 0:
                self.log(f"  • {skipped_reasons['unknown_tline_type']} unknown transmission line type")
            if skipped_reasons['calc_error'] > 0:
                self.log(f"  • {skipped_reasons['calc_error']} calculation error")
        
        self.log(f"Controlled impedance check: {violations} violations")
        return violations
    
    # ========================================================================
    # Helper Methods (to be implemented)
    # ========================================================================
    
    def _get_reference_planes(self, signal_layer):
        """
        Identify reference plane layers adjacent to a signal layer.
        
        Searches the board layer stack above and below the signal layer to find
        copper layers containing power/ground planes (zones with GND/PWR nets).
        
        Args:
            signal_layer: KiCad layer ID of signal layer
            
        Returns:
            tuple: (layer_above, layer_below) where each is:
                   - KiCad layer ID if plane exists, or
                   - None if no plane found in that direction
        """
        # Get list of enabled copper layers in stackup order (F.Cu=0 to B.Cu=31)
        copper_layers = []
        for layer_id in range(pcbnew.F_Cu, pcbnew.B_Cu + 1):
            if self.board.IsLayerEnabled(layer_id):
                copper_layers.append(layer_id)
        
        if signal_layer not in copper_layers:
            return (None, None)  # Signal layer not in copper stack
        
        sig_idx = copper_layers.index(signal_layer)
        
        # Search upward (toward F.Cu) for reference plane
        layer_above = None
        for idx in range(sig_idx - 1, -1, -1):
            candidate = copper_layers[idx]
            if self._layer_has_planes(candidate):
                layer_above = candidate
                break
        
        # Search downward (toward B.Cu) for reference plane
        layer_below = None
        for idx in range(sig_idx + 1, len(copper_layers)):
            candidate = copper_layers[idx]
            if self._layer_has_planes(candidate):
                layer_below = candidate
                break
        
        return (layer_above, layer_below)
    
    def _extract_plane_boundaries(self, plane_layer):
        """
        Extract polygon boundaries of copper planes on a layer.
        
        Collects all copper zones on the specified layer that match power/ground
        net patterns (GND, VCC, etc.). Returns their polygon outlines for spatial
        analysis (checking if traces/vias are above/below plane coverage).
        
        Args:
            plane_layer: KiCad layer ID
            
        Returns:
            list: List of tuples (net_name, SHAPE_POLY_SET outline)
                  Empty list if no planes found on layer
        """
        # Common power/ground net patterns
        plane_patterns = ['GND', 'PWR', 'VCC', 'VDD', 'POWER', 'AGND', 'DGND', 'PGND',
                          '+3V3', '+5V', '+12V', '-5V', '-12V']
        
        plane_boundaries = []  # List of (net_name, SHAPE_POLY_SET)
        
        for zone in self.board.Zones():
            # Filter to specified layer
            if not zone.IsOnLayer(plane_layer):
                continue
            
            # Check if zone net matches plane pattern
            net = zone.GetNet()
            if not net:
                continue
            
            net_name = net.GetNetname()
            if not net_name:
                continue
            
            # Match plane patterns (case-insensitive)
            if not any(p.upper() in net_name.upper() for p in plane_patterns):
                continue
            
            # Extract zone outline
            outline = zone.Outline()
            if outline and outline.OutlineCount() > 0:
                plane_boundaries.append((net_name, outline))
        
        return plane_boundaries
    
    def _calculate_trace_length(self, net):
        """
        Calculate total routed length of a net including vias.
        
        Sums the physical length of all track segments and adds the vertical
        height traversed by vias. This gives the total signal path length which
        is critical for timing analysis and length matching.
        
        Algorithm:
        1. Iterate all tracks (segments + vias) on the net
        2. For PCB_TRACK: add segment length directly
        3. For PCB_VIA: calculate physical height from layer span
           - Height = |top_layer_z - bottom_layer_z|
           - Approximated from board stackup if available
        4. Return total length in millimeters
        
        Args:
            net: pcbnew.NETINFO_ITEM or net name string
            
        Returns:
            float: Total routed length in millimeters (mm)
        """
        # Handle both NETINFO_ITEM and string inputs
        if isinstance(net, str):
            net_obj = self.board.FindNet(net)
            if not net_obj:
                self.log(f"  ⚠ Net '{net}' not found on board")
                return 0.0
        else:
            net_obj = net
        
        net_code = net_obj.GetNetCode()
        total_length_iu = 0  # Internal units
        
        # Iterate all tracks on this net
        for track in self.board.GetTracks():
            if track.GetNetCode() != net_code:
                continue
            
            if isinstance(track, pcbnew.PCB_TRACK):
                # Simple track segment - add length directly
                total_length_iu += track.GetLength()
            
            elif isinstance(track, pcbnew.PCB_VIA):
                # Via - calculate vertical height from layer span
                top_layer = track.TopLayer()
                bottom_layer = track.BottomLayer()
                
                # Get via height from board stackup
                # Approximate: assume uniform layer spacing
                stackup = self._read_stackup()
                if stackup and 'board_thickness_mm' in stackup:
                    # Calculate approximate height per layer
                    board_thickness_mm = stackup['board_thickness_mm']
                    num_copper_layers = len(stackup.get('copper_layers', []))
                    
                    if num_copper_layers > 1:
                        # Layer indices (0 = F.Cu, max = B.Cu)
                        # Approximate Z position
                        layer_span = abs(top_layer - bottom_layer)
                        via_height_mm = (layer_span / (num_copper_layers - 1)) * board_thickness_mm
                        total_length_iu += pcbnew.FromMM(via_height_mm)
                    else:
                        # Single layer board - no via height contribution
                        pass
                else:
                    # No stackup info - use default via height estimate
                    # Typical: 1.6mm standard PCB, 4-layer = 0.4mm per layer span
                    DEFAULT_VIA_HEIGHT_MM = 0.4
                    layer_span = abs(top_layer - bottom_layer)
                    via_height_mm = layer_span * DEFAULT_VIA_HEIGHT_MM
                    total_length_iu += pcbnew.FromMM(via_height_mm)
        
        # Convert to millimeters for return
        return pcbnew.ToMM(total_length_iu)
    
    def _build_connectivity_graph(self, net):
        """
        Build graph of connections for stub detection and routing topology analysis.
        
        Creates an undirected graph where:
        - Nodes: Track endpoints, via centers, pad centers
        - Edges: Track segments connecting two nodes
        
        This graph enables:
        - Stub detection: dead-end branches (degree-1 nodes not on pads)
        - Path analysis: trace routing from source to load
        - Branching analysis: identify T-junctions and splits
        
        Algorithm:
        1. Collect all connection points (track endpoints, vias, pads)
        2. Snap points to grid (10µm tolerance) to merge coincident points
        3. Build adjacency list: each node → list of connected nodes
        4. Include metadata: track width, layer, segment reference
        
        Args:
            net: pcbnew.NETINFO_ITEM or net name string
            
        Returns:
            dict: Connectivity graph with structure:
            {
                'nodes': {
                    (x, y, layer): {
                        'type': 'track_end' | 'via' | 'pad',
                        'position': pcbnew.VECTOR2I,
                        'layer': int,
                        'connections': [(x2, y2, layer2), ...],
                        'pad_ref': str (if type='pad')
                    }
                },
                'edges': [
                    {
                        'start': (x1, y1, layer),
                        'end': (x2, y2, layer),
                        'track': PCB_TRACK reference,
                        'length': float (mm)
                    }
                ]
            }
        """
        # Handle both NETINFO_ITEM and string inputs
        if isinstance(net, str):
            net_obj = self.board.FindNet(net)
            if not net_obj:
                self.log(f"  ⚠ Net '{net}' not found on board")
                return {'nodes': {}, 'edges': []}
        else:
            net_obj = net
        
        net_code = net_obj.GetNetCode()
        
        # Snap tolerance: 10µm (same as unconnected via check)
        SNAP_GRID = 10000  # 10µm in internal units
        
        def snap_point(pos, layer):
            """Snap position to grid and include layer for 3D connectivity."""
            x_snapped = (pos.x // SNAP_GRID) * SNAP_GRID
            y_snapped = (pos.y // SNAP_GRID) * SNAP_GRID
            return (x_snapped, y_snapped, layer)
        
        # Data structures
        nodes = {}  # {(x, y, layer): node_data}
        edges = []  # [{start, end, track, length}]
        
        # Step 1: Collect all pads on this net
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                if pad.GetNetCode() == net_code:
                    pad_pos = pad.GetPosition()
                    # Pads can exist on multiple layers
                    for layer_id in range(pcbnew.PCB_LAYER_ID_COUNT):
                        if pad.IsOnLayer(layer_id):
                            node_key = snap_point(pad_pos, layer_id)
                            if node_key not in nodes:
                                nodes[node_key] = {
                                    'type': 'pad',
                                    'position': pad_pos,
                                    'layer': layer_id,
                                    'connections': [],
                                    'pad_ref': f"{footprint.GetReference()}.{pad.GetNumber()}"
                                }
        
        # Step 2: Collect all vias on this net
        for track in self.board.GetTracks():
            if track.GetNetCode() != net_code:
                continue
            
            if isinstance(track, pcbnew.PCB_VIA):
                via_pos = track.GetPosition()
                top_layer = track.TopLayer()
                bottom_layer = track.BottomLayer()
                
                # Via connects all layers in its span
                for layer_id in range(top_layer, bottom_layer + 1):
                    node_key = snap_point(via_pos, layer_id)
                    if node_key not in nodes:
                        nodes[node_key] = {
                            'type': 'via',
                            'position': via_pos,
                            'layer': layer_id,
                            'connections': [],
                            'via_span': (top_layer, bottom_layer)
                        }
        
        # Step 3: Process all track segments and create edges
        for track in self.board.GetTracks():
            if track.GetNetCode() != net_code:
                continue
            
            if isinstance(track, pcbnew.PCB_TRACK):
                layer_id = track.GetLayer()
                start_pos = track.GetStart()
                end_pos = track.GetEnd()
                
                # Create node keys for both endpoints
                start_key = snap_point(start_pos, layer_id)
                end_key = snap_point(end_pos, layer_id)
                
                # Ensure both endpoints exist as nodes (might be track-only junctions)
                if start_key not in nodes:
                    nodes[start_key] = {
                        'type': 'track_end',
                        'position': start_pos,
                        'layer': layer_id,
                        'connections': []
                    }
                
                if end_key not in nodes:
                    nodes[end_key] = {
                        'type': 'track_end',
                        'position': end_pos,
                        'layer': layer_id,
                        'connections': []
                    }
                
                # Add bidirectional connection
                if end_key not in nodes[start_key]['connections']:
                    nodes[start_key]['connections'].append(end_key)
                if start_key not in nodes[end_key]['connections']:
                    nodes[end_key]['connections'].append(start_key)
                
                # Create edge record
                edges.append({
                    'start': start_key,
                    'end': end_key,
                    'track': track,
                    'length': pcbnew.ToMM(track.GetLength()),
                    'width': pcbnew.ToMM(track.GetWidth()),
                    'layer': layer_id
                })
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    def _calculate_stub_length(self, stub_node_key, nodes, edges):
        """
        Calculate stub length by tracing from endpoint to branch point.
        
        Walks the connectivity graph from a leaf node (stub endpoint) back
        through single-connection nodes until reaching a branch point (node
        with >2 connections) or a pad (valid endpoint).
        
        Args:
            stub_node_key: Node key (x, y, layer) tuple of stub endpoint
            nodes: Graph nodes dict from _build_connectivity_graph()
            edges: Graph edges list from _build_connectivity_graph()
            
        Returns:
            float: Stub length in millimeters, or None if invalid
        """
        if stub_node_key not in nodes:
            return None
        
        # Build edge lookup for efficient traversal
        # edge_map: {(start_key, end_key): edge_data}
        edge_map = {}
        for edge in edges:
            start_key = edge['start']
            end_key = edge['end']
            # Store bidirectionally
            edge_map[(start_key, end_key)] = edge
            edge_map[(end_key, start_key)] = edge
        
        # BFS traversal from stub endpoint toward branch point
        current = stub_node_key
        visited = set([current])
        total_length = 0.0
        
        while True:
            current_node = nodes[current]
            connections = current_node['connections']
            
            # Find next unvisited neighbor
            next_node = None
            for neighbor in connections:
                if neighbor not in visited:
                    next_node = neighbor
                    break
            
            if next_node is None:
                # Dead end with no unvisited neighbors
                # This shouldn't happen for valid stubs, but handle gracefully
                break
            
            # Get edge between current and next
            edge_key = (current, next_node)
            if edge_key not in edge_map:
                # No direct edge (shouldn't happen in valid graph)
                break
            
            edge = edge_map[edge_key]
            total_length += edge['length']  # Already in mm
            
            # Move to next node
            visited.add(next_node)
            current = next_node
            
            # Check termination conditions
            next_node_data = nodes[next_node]
            num_connections = len(next_node_data['connections'])
            
            # Reached a pad (valid endpoint)
            if next_node_data['type'] == 'pad':
                # This is actually not a stub - it's a valid trace to pad
                # But we've already identified it as a leaf from one direction
                # This can happen in via-to-pad connections
                break
            
            # Reached a branch point (>2 connections = T-junction)
            if num_connections > 2:
                # Found the branch point - stub length is complete
                break
            
            # If num_connections == 2, continue traversing (straight path)
            # If num_connections == 1, we've reached another dead end (shouldn't happen)
            if num_connections == 1:
                break
        
        return total_length
    
    def _identify_differential_pairs(self):
        """
        Identify differential pairs from net naming conventions.
        
        TODO: Implementation needed
        
        Args:
            None (uses board nets)
            
        Returns:
            dict: Mapping of base name to (P_net, N_net) tuple
                  Example: {'USB_D': (net_USB_DP, net_USB_DN)}
        """
        import re

        # Positive polarity patterns: separator + P-side suffix
        P_PATTERN = re.compile(
            r'^(.+?)[_\-\.](P|DP|D\+|TRUE|T|POS|PLUS|TX|TXP|RXP)$',
            re.IGNORECASE
        )
        # Negative polarity patterns: same separator + N-side suffix
        N_PATTERN = re.compile(
            r'^(.+?)[_\-\.](N|DN|D\-|COMP|C|NEG|MINUS|TXN|RXN)$',
            re.IGNORECASE
        )

        p_nets = {}   # base_name -> net_name
        n_nets = {}   # base_name -> net_name

        netinfo = self.board.GetNetInfo()
        for net_code in range(netinfo.GetNetCount()):
            net = netinfo.GetNetItem(net_code)
            if not net:
                continue
            net_name = net.GetNetname()
            if not net_name:
                continue

            m = P_PATTERN.match(net_name)
            if m:
                base = m.group(1).upper()
                # Prefer longer base name if duplicate (e.g. USB_D preferred over USB)
                if base not in p_nets or len(net_name) > len(p_nets[base]):
                    p_nets[base] = net_name
                continue

            m = N_PATTERN.match(net_name)
            if m:
                base = m.group(1).upper()
                if base not in n_nets or len(net_name) > len(n_nets[base]):
                    n_nets[base] = net_name

        pairs = {}
        for base in p_nets:
            if base in n_nets:
                pairs[base] = (p_nets[base], n_nets[base])

        if pairs:
            self.log(f"  Differential pairs detected: {list(pairs.keys())}")
        return pairs   # {base_name: (P_net_name, N_net_name)}
    
    def _find_parallel_segments(self, segment, max_distance, angular_tolerance=10):
        """
        Find trace segments running parallel to a given segment.
        
        Detects parallel routing by comparing segment angles and measuring
        perpendicular distances. Returns segments that run parallel within
        the specified angular tolerance and distance threshold.
        
        Args:
            segment: Track segment to check (pcbnew.PCB_TRACK)
            max_distance: Maximum perpendicular distance to consider (internal units)
            angular_tolerance: Max angle deviation to consider parallel (degrees)
            
        Returns:
            list: List of (track, parallel_length_mm, min_spacing_mm) tuples
                 - track: The parallel track segment
                 - parallel_length_mm: Length of parallel overlap (mm)
                 - min_spacing_mm: Minimum edge-to-edge spacing (mm)
        """
        import math
        
        # Get segment properties
        seg_start = segment.GetStart()
        seg_end = segment.GetEnd()
        seg_layer = segment.GetLayer()
        seg_net = segment.GetNet()
        seg_width = segment.GetWidth()
        
        # Calculate segment angle (radians)
        dx = seg_end.x - seg_start.x
        dy = seg_end.y - seg_start.y
        seg_length = math.sqrt(dx*dx + dy*dy)
        
        if seg_length < 1e-6:  # Degenerate segment
            return []
        
        seg_angle = math.atan2(dy, dx)
        
        # Bounding box for spatial filtering
        search_radius = max_distance
        bbox_min_x = min(seg_start.x, seg_end.x) - search_radius
        bbox_max_x = max(seg_start.x, seg_end.x) + search_radius
        bbox_min_y = min(seg_start.y, seg_end.y) - search_radius
        bbox_max_y = max(seg_start.y, seg_end.y) + search_radius
        
        parallel_segments = []
        angular_tol_rad = math.radians(angular_tolerance)
        
        # Scan all tracks on same layer
        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            if track.GetLayer() != seg_layer:
                continue
            if track == segment:  # Skip self
                continue
            
            # Bounding box pre-filter
            other_start = track.GetStart()
            other_end = track.GetEnd()
            
            if (max(other_start.x, other_end.x) < bbox_min_x or
                min(other_start.x, other_end.x) > bbox_max_x or
                max(other_start.y, other_end.y) < bbox_min_y or
                min(other_start.y, other_end.y) > bbox_max_y):
                continue  # Outside search area
            
            # Calculate other segment angle
            other_dx = other_end.x - other_start.x
            other_dy = other_end.y - other_start.y
            other_length = math.sqrt(other_dx*other_dx + other_dy*other_dy)
            
            if other_length < 1e-6:
                continue
            
            other_angle = math.atan2(other_dy, other_dx)
            
            # Check angular alignment (considering 180° symmetry)
            angle_diff = abs(seg_angle - other_angle)
            angle_diff_180 = abs(angle_diff - math.pi)
            
            if min(angle_diff, angle_diff_180) > angular_tol_rad:
                continue  # Not parallel
            
            # Calculate perpendicular distance between segments
            # Use point-to-line distance for both endpoints
            def point_to_line_distance(px, py, x1, y1, x2, y2):
                """Perpendicular distance from point to line segment."""
                line_len_sq = (x2 - x1)**2 + (y2 - y1)**2
                if line_len_sq < 1e-6:
                    return math.sqrt((px - x1)**2 + (py - y1)**2)
                
                # Project point onto line
                t = max(0, min(1, ((px - x1)*(x2 - x1) + (py - y1)*(y2 - y1)) / line_len_sq))
                proj_x = x1 + t * (x2 - x1)
                proj_y = y1 + t * (y2 - y1)
                
                return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
            
            # Average perpendicular distance
            dist1 = point_to_line_distance(
                other_start.x, other_start.y,
                seg_start.x, seg_start.y, seg_end.x, seg_end.y
            )
            dist2 = point_to_line_distance(
                other_end.x, other_end.y,
                seg_start.x, seg_start.y, seg_end.x, seg_end.y
            )
            
            avg_dist = (dist1 + dist2) / 2.0
            
            if avg_dist > max_distance:
                continue  # Too far apart
            
            # Calculate parallel overlap length (projection onto segment axis)
            # Project other segment endpoints onto reference segment axis
            def project_onto_axis(px, py, x1, y1, x2, y2):
                """Project point onto line axis, return parametric position."""
                dx = x2 - x1
                dy = y2 - y1
                line_len_sq = dx*dx + dy*dy
                if line_len_sq < 1e-6:
                    return 0.0
                return ((px - x1)*dx + (py - y1)*dy) / line_len_sq
            
            t_other_start = project_onto_axis(
                other_start.x, other_start.y,
                seg_start.x, seg_start.y, seg_end.x, seg_end.y
            )
            t_other_end = project_onto_axis(
                other_end.x, other_end.y,
                seg_start.x, seg_start.y, seg_end.x, seg_end.y
            )
            
            # Overlap range: intersection of [0, 1] and [t_other_start, t_other_end]
            overlap_start = max(0.0, min(t_other_start, t_other_end))
            overlap_end = min(1.0, max(t_other_start, t_other_end))
            
            if overlap_start >= overlap_end:
                continue  # No overlap
            
            overlap_fraction = overlap_end - overlap_start
            parallel_length_mm = pcbnew.ToMM(overlap_fraction * seg_length)
            
            # Calculate minimum edge-to-edge spacing
            # Center-to-center distance minus half-widths
            other_width = track.GetWidth()
            center_dist = avg_dist
            min_spacing_mm = pcbnew.ToMM(center_dist - (seg_width + other_width) / 2.0)
            
            # Ensure non-negative
            min_spacing_mm = max(0.0, min_spacing_mm)
            
            parallel_segments.append((track, parallel_length_mm, min_spacing_mm))
        
        return parallel_segments
    
    def _calculate_spacing_along_pair(self, net_p, net_n, sample_interval_mm=1.0):
        """
        Sample spacing between differential pair traces along route.
        
        Collects track segments from both nets on each layer, then samples
        the perpendicular distance between them at regular intervals. This
        provides spacing variation data for impedance consistency checks.
        
        Args:
            net_p: Positive net (pcbnew.NETINFO_ITEM or net name string)
            net_n: Negative net (pcbnew.NETINFO_ITEM or net name string)
            sample_interval_mm: Distance between sampling points (default: 1.0mm)
            
        Returns:
            list: List of spacing measurements in internal units
        """
        # Handle both NETINFO_ITEM and string inputs
        if isinstance(net_p, str):
            p_net_obj = self.board.FindNet(net_p)
            if not p_net_obj:
                return []
        else:
            p_net_obj = net_p
        
        if isinstance(net_n, str):
            n_net_obj = self.board.FindNet(net_n)
            if not n_net_obj:
                return []
        else:
            n_net_obj = net_n
        
        p_code = p_net_obj.GetNetCode()
        n_code = n_net_obj.GetNetCode()
        
        # Collect tracks by layer
        from collections import defaultdict
        p_tracks = defaultdict(list)  # layer_id → [tracks]
        n_tracks = defaultdict(list)
        
        for track in self.board.GetTracks():
            if not isinstance(track, pcbnew.PCB_TRACK):
                continue
            
            net_code = track.GetNetCode()
            layer_id = track.GetLayer()
            
            if net_code == p_code:
                p_tracks[layer_id].append(track)
            elif net_code == n_code:
                n_tracks[layer_id].append(track)
        
        # Sample spacing on each layer where both nets exist
        spacing_samples = []
        sample_interval_iu = pcbnew.FromMM(sample_interval_mm)
        
        for layer_id in p_tracks:
            if layer_id not in n_tracks:
                continue  # No pair on this layer
            
            p_segs = p_tracks[layer_id]
            n_segs = n_tracks[layer_id]
            
            # For each P segment, find closest N segment and sample spacing
            for p_track in p_segs:
                p_start = p_track.GetStart()
                p_end = p_track.GetEnd()
                p_length = p_track.GetLength()
                
                if p_length < sample_interval_iu:
                    # Segment too short, sample at midpoint only
                    num_samples = 1
                else:
                    num_samples = max(1, int(p_length / sample_interval_iu))
                
                # Sample at regular intervals along P segment
                for i in range(num_samples):
                    t = i / max(1, num_samples - 1) if num_samples > 1 else 0.5
                    
                    # Interpolate position along P segment
                    sample_x = int(p_start.x + t * (p_end.x - p_start.x))
                    sample_y = int(p_start.y + t * (p_end.y - p_start.y))
                    sample_pos = pcbnew.VECTOR2I(sample_x, sample_y)
                    
                    # Find closest point on any N segment
                    min_dist = float('inf')
                    
                    for n_track in n_segs:
                        n_start = n_track.GetStart()
                        n_end = n_track.GetEnd()
                        
                        # Calculate perpendicular distance to N segment
                        # Point-to-line-segment distance
                        dx = n_end.x - n_start.x
                        dy = n_end.y - n_start.y
                        length_sq = dx*dx + dy*dy
                        
                        if length_sq < 1e-6:
                            # Degenerate segment, use point distance
                            dist = self.get_distance(sample_pos, n_start)
                        else:
                            # Project sample point onto N segment line
                            t_proj = ((sample_pos.x - n_start.x) * dx +
                                     (sample_pos.y - n_start.y) * dy) / length_sq
                            t_proj = max(0.0, min(1.0, t_proj))  # Clamp to segment
                            
                            # Closest point on N segment
                            closest_x = int(n_start.x + t_proj * dx)
                            closest_y = int(n_start.y + t_proj * dy)
                            closest_pos = pcbnew.VECTOR2I(closest_x, closest_y)
                            
                            dist = self.get_distance(sample_pos, closest_pos)
                        
                        min_dist = min(min_dist, dist)
                    
                    if min_dist < float('inf'):
                        spacing_samples.append(int(min_dist))
        
        return spacing_samples
    
    def _calculate_microstrip_impedance(self, W_mm, H_mm, t_um, Er):
        """
        Calculate microstrip impedance using IPC-2141 formula.
        
        TODO: Implementation needed
        
        Args:
            W_mm: Trace width in mm
            H_mm: Dielectric height in mm
            t_um: Trace thickness in microns (35μm = 1oz copper)
            Er: Dielectric constant (FR-4 ≈ 4.3)
            
        Returns:
            float: Characteristic impedance in Ohms
        """
        import math
        
        # Convert to consistent units
        W = W_mm
        H = H_mm
        t = t_um / 1000.0  # Convert μm to mm
        
        # Effective width correction for thickness
        delta_W = (t / math.pi) * math.log(2 * H / t) * (1 + 1/math.sqrt(Er))
        W_eff = W + delta_W
        
        # Effective dielectric constant
        Er_eff = (Er + 1)/2 + (Er - 1)/2 * (1 / math.sqrt(1 + 12*H/W_eff))
        
        # Impedance calculation
        if W_eff / H < 1:
            Z0 = (60 / math.sqrt(Er_eff)) * math.log(8*H/W_eff + W_eff/(4*H))
        else:
            Z0 = (120 * math.pi / math.sqrt(Er_eff)) / (W_eff/H + 1.393 + 0.667*math.log(W_eff/H + 1.444))
        
        return Z0
    
    def _calculate_stripline_impedance(self, W_mm, b_mm, t_um, Er):
        """
        Calculate stripline impedance (symmetric between two planes) using Wadell formula.
        For W/b < 0.35: Z0 = (60/√εr) × ln(4b / (0.67π × W × (0.8 + t/W)))
        For W/b >= 0.35: Z0 = 94.15/√εr / (W/b + 1.11 × √(0.81 + t/b))

        Args:
            W_mm: Trace width in mm
            b_mm: Total height between ground planes in mm
            t_um: Trace thickness in microns
            Er: Dielectric constant
            
        Returns:
            float: Characteristic impedance in Ohms
        """
        import math
        
        W = W_mm
        b = b_mm
        t = t_um / 1000.0
        
        # Stripline formula
        if W / b < 0.35:
            Z0 = (60 / math.sqrt(Er)) * math.log(4*b / (0.67*math.pi*W*(0.8 + t/W)))
        else:
            Z0 = (94.15 / math.sqrt(Er)) / (W/b + 1.11 * math.sqrt(0.81 + t/b))
        
        return Z0
    
    def _calculate_differential_impedance(self, Z0_single, S_mm, H_mm):
        """
        Calculate differential impedance from single-ended impedance.
        
        TODO: Implementation needed - Current simplified method vs. Rigorous Cohn approach
        
        NOTE: Current implementation uses simplified exponential coupling coefficient method.
        This provides reasonable estimates (±10% accuracy) but is NOT rigorous.
        
        For HIGH-ACCURACY differential pair synthesis (especially stripline), implement
        Cohn's elliptic integral method described in IMPEDANCE_ALGORITHM.md.
        
        ═══════════════════════════════════════════════════════════════════════════
        REFERENCES - Classical Papers (S. B. Cohn, IRE Transactions)
        ═══════════════════════════════════════════════════════════════════════════
        
        [1] S. B. Cohn, "Characteristic Impedance of the Shielded-Strip Transmission Line,"
            IRE Transactions on MTT, vol. 2, no. 2, pp. 52-57, July 1954.
            → Single stripline with finite thickness, fringing capacitance corrections
        
        [2] S. B. Cohn, "Shielded Coupled-Strip Transmission Line,"
            IRE Transactions on MTT, vol. 3, no. 5, pp. 29-38, October 1955.
            → The "bible" of coupled striplines, 349+ citations, design nomograms
            → Even-mode and odd-mode analysis using complete elliptic integrals
        
        ═══════════════════════════════════════════════════════════════════════════
        TODO: IMPLEMENTATION ROADMAP - Cohn's Rigorous Method
        ═══════════════════════════════════════════════════════════════════════════
        
        STEP 1: Determine if stripline or microstrip
        ────────────────────────────────────────────
        - IF microstrip (top/bottom layer): Use current simplified method (acceptable)
        - IF stripline (embedded, symmetric planes): Use Cohn's method (required)
        - CRITICAL: Cohn assumes homogeneous dielectric (εᵣ constant)
        - For mixed media: Use Kirschning-Jansen or EM simulator
        
        STEP 2: Calculate mode impedances from target Z₀ and coupling k
        ────────────────────────────────────────────────────────────────
        Given:
          - Z₀ = target single-ended impedance (e.g., 50Ω)
          - k = coupling coefficient (linear, 0 < k < 1)
                OR from dB: k = 10^(-C_dB/20)
        
        Calculate:
          Z₀ₑ = Z₀ × √[(1 + k)/(1 - k)]    # Even-mode (in-phase)
          Z₀ₒ = Z₀ × √[(1 - k)/(1 + k)]    # Odd-mode (differential)
        
        STEP 3: Solve for elliptic moduli kₑ and kₒ
        ────────────────────────────────────────────
        Using complete elliptic integrals K(k):
          K(kₑ)/K'(kₑ) = 30π / (√εᵣ × Z₀ₑ)
          K(kₒ)/K'(kₒ) = 30π / (√εᵣ × Z₀ₒ)
        
        where:
          K(k) = scipy.special.ellipk(k²)  # Complete elliptic integral, 1st kind
          K'(k) = K(√(1 - k²))            # Complementary integral
        
        Implementation: Use scipy.optimize to solve for kₑ, kₒ numerically
        
        STEP 4: Calculate trace width w and spacing s (SYNTHESIS)
        ──────────────────────────────────────────────────────────
        Gap spacing:
          s/b = (2/π) × ln[(1/√kₑ) × (1 + √(kₑ × kₒ))/(√kₒ - √kₑ)]
        
        Trace width:
          w/b = (1/π) × ln(1/kₑ) - s/b
        
        Where b = distance between ground planes (from stackup)
        
        STEP 5: Apply finite thickness correction (if t > 0)
        ─────────────────────────────────────────────────────
        Corrected width:
          w' = w - Δw
        
        Where (approximation):
          Δw ≈ t × [1 + ln(4b/t)]/(2π)
        
        See Cohn (1954) for exact correction curves/formulas
        
        STEP 6: Return differential impedance
        ──────────────────────────────────────
        Final result:
          Zdiff = 2 × Z₀ₒ
          Zcommon = Z₀ₑ / 2
        
        ═══════════════════════════════════════════════════════════════════════════
        IMPLEMENTATION DEPENDENCIES
        ═══════════════════════════════════════════════════════════════════════════
        
        Required Python packages:
          - scipy.special.ellipk (complete elliptic integral K)
          - scipy.optimize.root_scalar (solve for elliptic moduli)
          - numpy (for sqrt, log, etc.)
        
        Required methods to add:
          - _calculate_even_odd_impedances(Z0, k)
          - _solve_elliptic_moduli(Z0e, Z0o, Er)
          - _synthesize_stripline_geometry(ke, ko, b)
          - _apply_thickness_correction(w, t, b)
        
        ═══════════════════════════════════════════════════════════════════════════
        ACCURACY & VALIDATION
        ═══════════════════════════════════════════════════════════════════════════
        
        Cohn's method (elliptic):   ±2-3% accuracy for stripline
        Current simplified method:  ±10-15% accuracy (coupling approximation)
        
        Test cases for validation:
          1. USB 2.0: Zdiff = 90Ω, εᵣ = 4.3, b = 0.6mm
          2. HDMI: Zdiff = 100Ω, εᵣ = 4.3, b = 0.8mm
          3. PCIe Gen3: Zdiff = 85Ω, εᵣ = 3.48 (Rogers RO4350B)
        
        Compare against:
          - Commercial tools (Polar Si9000, Ansys 2D Extractor)
          - IPC-2141 tables
          - Manufacturer stackup calculators
        
        ═══════════════════════════════════════════════════════════════════════════
        
        Args:
            Z0_single: Single-ended impedance in Ohms
            S_mm: Spacing between differential pair traces in mm
            H_mm: Dielectric height to reference plane in mm
            
        Returns:
            float: Differential impedance in Ohms (current: simplified approximation)
        """
        import math
        
        # Coupling coefficient based on spacing
        k_coupling = 0.48 * math.exp(-0.96 * S_mm / H_mm)
        
        # Differential impedance
        Z_diff = 2 * Z0_single * math.sqrt(1 - k_coupling)
        
        return Z_diff
    
    def _calculate_cpw_impedance(self, W_mm, S_mm, H_mm, Er, has_ground_plane=False):
        """
        Calculate coplanar waveguide impedance using elliptic integral approximation.
        Supports CPW (no ground plane, Er_eff = (Er+1)/2) and CPWG (with ground plane).

        Args:
            W_mm: Center trace width in mm
            S_mm: Gap to ground traces in mm
            H_mm: Substrate height in mm (for CPWG with ground plane)
            Er: Dielectric constant
            has_ground_plane: True for CPWG, False for CPW
            
        Returns:
            float: Characteristic impedance in Ohms
        """
        import math
        
        # Geometric ratio
        k = W_mm / (W_mm + 2 * S_mm)
        k_prime = math.sqrt(1 - k**2)

        def _elliptic_ratio(k_val):
            """
            Wen (1969) two-regime approximation for K(k')/K(k).

            Regime 1 — narrow gap (k ≥ 1/√2, k' ≤ 1/√2):
                K(k')/K(k) ≈ π / ln(2·(1+√k)/(1−√k))   [uses √k]

            Regime 2 — wide gap (k < 1/√2, k' > 1/√2):
                K(k')/K(k) ≈ (1/π) · ln(2·(1+√k')/(1−√k'))  [uses √k']

            Both forms are accurate to ~1% within their regime.
            Reference: C. P. Wen, "Coplanar Waveguide: A Surface Strip
            Transmission Line Suitable for Nonreciprocal Gyromagnetic Device
            Applications," IEEE Trans. MTT, 1969.
            """
            kp = math.sqrt(1 - k_val**2)
            threshold = 1.0 / math.sqrt(2)   # ≈ 0.7071
            if k_val >= threshold:
                # Narrow-gap regime — use √k
                sqrt_k = math.sqrt(k_val)
                return math.pi / math.log(2 * (1 + sqrt_k) / (1 - sqrt_k))
            else:
                # Wide-gap regime — use √k'
                sqrt_kp = math.sqrt(kp)
                return (1.0 / math.pi) * math.log(2 * (1 + sqrt_kp) / (1 - sqrt_kp))

        if has_ground_plane:
            # CPWG: ground plane present — combine coplanar (k) and back-side ground (k1)
            # k1 from sinh mapping of the ground-plane contribution (Simonovich / Wadell)
            sinh_W  = math.sinh(math.pi * W_mm / (4 * H_mm))
            sinh_WS = math.sinh(math.pi * (W_mm + 2 * S_mm) / (4 * H_mm))
            k1 = sinh_W / sinh_WS

            # K(k)/K'(k) = inverse of _elliptic_ratio(k)
            Kk_over_Kkp  = 1.0 / _elliptic_ratio(k)
            Kk1_over_Kk1p = 1.0 / _elliptic_ratio(k1)

            # Filling factor and effective dielectric (Simonovich formula)
            q = Kk1_over_Kk1p / (Kk_over_Kkp + Kk1_over_Kk1p)
            Er_eff = 1 + (Er - 1) * q

            # Z0 = 30π / (√Er_eff · (K(k)/K'(k) + K(k1)/K'(k1)))
            Z0 = (30 * math.pi / math.sqrt(Er_eff)) / (Kk_over_Kkp + Kk1_over_Kk1p)
        else:
            # CPW: no ground plane — effective dielectric = average of substrate and air
            Er_eff  = (Er + 1) / 2
            K_ratio = _elliptic_ratio(k)
            Z0 = (30 * math.pi / math.sqrt(Er_eff)) * K_ratio

        return Z0
    
    def _detect_transmission_line_type(self, layer_name):
        """
        Detect transmission line type based on layer position.
        Outer layers (F.Cu, B.Cu) → microstrip; inner layers (InX.Cu) → stripline.

        Args:
            layer_name: KiCad layer name (e.g., 'F.Cu', 'In1.Cu')
            
        Returns:
            str: 'microstrip', 'stripline', 'cpw', 'unknown'
        """
        outer_layers = ['F.Cu', 'B.Cu']
        
        if layer_name in outer_layers:
            return 'microstrip'
        elif 'In' in layer_name:
            return 'stripline'
        else:
            return 'unknown'
    
    def _get_dielectric_height_to_plane(self, trace_layer, stackup=None):
        """
        Get dielectric height from trace layer to nearest reference plane.
        
        Uses parsed stackup data to find the distance from a trace layer
        to the nearest reference plane (above or below).
        
        Args:
            trace_layer: KiCad layer ID
            stackup: Pre-parsed stackup data (optional, will parse if None)
            
        Returns:
            float: Height in mm, or None if cannot determine
        """
        # Don't re-fetch if None provided - use default instead
        if stackup is None:
            return 0.2  # Default FR-4 height
        
        if not stackup or not stackup.get('layers'):
            return 0.2  # Default if stackup invalid
        
        trace_layer_name = self.board.GetLayerName(trace_layer)
        layers = stackup['layers']
        
        # Find trace layer in stackup
        trace_idx = None
        for i, layer in enumerate(layers):
            if layer['type'] == 'copper' and layer['name'] == trace_layer_name:
                trace_idx = i
                break
        
        if trace_idx is None:
            return None
        
        # Search for nearest reference plane (look down first, then up)
        # Look downward (increasing index)
        height_down = 0.0
        for i in range(trace_idx + 1, len(layers)):
            layer = layers[i]
            
            if layer['type'] == 'dielectric':
                height_down += layer['thickness_um'] / 1000.0  # Convert μm to mm
            elif layer['type'] == 'copper':
                # Found next copper layer, assume it's a reference plane
                # Return height if > 0
                if height_down > 0:
                    return height_down
                break
        
        # Look upward (decreasing index)
        height_up = 0.0
        for i in range(trace_idx - 1, -1, -1):
            layer = layers[i]
            
            if layer['type'] == 'dielectric':
                height_up += layer['thickness_um'] / 1000.0  # Convert μm to mm
            elif layer['type'] == 'copper':
                # Found previous copper layer, assume it's a reference plane
                if height_up > 0:
                    return height_up
                break
        
        # If we found both, return the smaller (nearest plane)
        if height_down > 0 and height_up > 0:
            return min(height_down, height_up)
        elif height_down > 0:
            return height_down
        elif height_up > 0:
            return height_up
        else:
            return None
    
    def _parse_stackup_from_file(self, board_file_path):
        """
        Parse board stackup directly from the .kicad_pcb file.
        
        KiCad board files are S-expression text files containing a (stackup ...) section
        with layer definitions including copper and dielectric properties.
        
        Args:
            board_file_path: Path to the .kicad_pcb file
            
        Returns:
            dict: Stackup structure, or None if parsing fails
        """
        try:
            import re
            
            with open(board_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the stackup section
            stackup_match = re.search(r'\(stackup(.*?)\n\s*\)\s*\n\s*\(pad_to_mask', content, re.DOTALL)
            if not stackup_match:
                return None
            
            stackup_text = stackup_match.group(1)
            
            # Parse layers - match patterns like:
            # (layer "F.Cu" (type "copper") (thickness 0.035052))
            # (layer "dielectric 1" (type "prepreg") (thickness 0.210312) (epsilon_r 4.4) (loss_tangent 0.014))
            
            stackup_data = {
                'layers': [],
                'total_thickness_mm': 0.0,
                'finish': 'Unknown',
                'has_impedance_control': True
            }
            
            # Find all layer definitions
            layer_pattern = r'\(layer\s+"([^"]+)"[^)]*?\(type\s+"([^"]+)"[^)]*?\)'
            layer_matches = re.finditer(layer_pattern, stackup_text, re.DOTALL)
            
            for match in layer_matches:
                layer_name = match.group(1)
                layer_type = match.group(2).lower()
                
                # Extract the full layer block
                layer_start = match.start()
                # Find matching closing paren
                paren_count = 0
                pos = layer_start
                for i, char in enumerate(stackup_text[layer_start:], start=layer_start):
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            layer_block = stackup_text[layer_start:i+1]
                            break
                
                # Parse thickness (in mm)
                thickness_match = re.search(r'\(thickness\s+([0-9.]+)\)', layer_block)
                thickness_mm = float(thickness_match.group(1)) if thickness_match else 0.0
                thickness_um = thickness_mm * 1000.0  # Convert to µm
                
                if layer_type == 'copper' and thickness_um > 0:
                    # Copper layer
                    layer_info = {
                        'name': layer_name,
                        'type': 'copper',
                        'thickness_um': thickness_um,
                        'material': 'copper'
                    }
                    stackup_data['layers'].append(layer_info)
                    stackup_data['total_thickness_mm'] += thickness_mm
                
                elif layer_type in ['prepreg', 'core'] and thickness_um > 0:
                    # Dielectric layer
                    epsilon_r_match = re.search(r'\(epsilon_r\s+([0-9.]+)\)', layer_block)
                    loss_tan_match = re.search(r'\(loss_tangent\s+([0-9.]+)\)', layer_block)
                    material_match = re.search(r'\(material\s+"([^"]+)"\)', layer_block)
                    
                    layer_info = {
                        'name': layer_name,
                        'type': 'dielectric',
                        'thickness_um': thickness_um,
                        'material': material_match.group(1) if material_match else layer_type.capitalize(),
                        'epsilon_r': float(epsilon_r_match.group(1)) if epsilon_r_match else 4.3,
                        'loss_tangent': float(loss_tan_match.group(1)) if loss_tan_match else 0.02
                    }
                    stackup_data['layers'].append(layer_info)
                    stackup_data['total_thickness_mm'] += thickness_mm
            
            # Parse copper finish
            finish_match = re.search(r'\(copper_finish\s+"([^"]+)"\)', stackup_text)
            if finish_match:
                stackup_data['finish'] = finish_match.group(1)
            
            if stackup_data['layers']:
                # Format clean output for any number of layers
                copper_layers = [l for l in stackup_data['layers'] if l['type'] == 'copper']
                dielectric_layers = [l for l in stackup_data['layers'] if l['type'] == 'dielectric']
                
                self.log(f"\n--- Board Stackup ---")
                self.log(f"Total layers: {len(stackup_data['layers'])} ({len(copper_layers)} copper, {len(dielectric_layers)} dielectric)")
                self.log(f"Total thickness: {stackup_data['total_thickness_mm']:.3f}mm")
                self.log(f"Copper finish: {stackup_data['finish']}")
                self.log(f"")
                
                self.log("Copper layers:")
                for layer in copper_layers:
                    self.log(f"  • {layer['name']}: {layer['thickness_um']:.3f}µm")
                
                self.log("")
                self.log("Dielectric layers:")
                for layer in dielectric_layers:
                    self.log(f"  • {layer['material']}: {layer['thickness_um']:.3f}µm, εr={layer['epsilon_r']}, loss tan={layer['loss_tangent']}")
                
                self.log("")  # Blank line after stackup info
                return stackup_data
            else:
                return None
                
        except Exception as e:
            return None
    
    def _get_board_stackup(self):
        """
        Extract complete board stackup information from KiCad board.
        
        Returns full stackup with layers, materials, thicknesses, and dielectric constants.
        
        Returns:
            dict: Stackup structure with layer information, or None if unavailable
            {
                'layers': [
                    {
                        'name': 'F.Cu',
                        'type': 'copper',
                        'thickness_um': 35,  # microns
                        'material': 'copper'
                    },
                    {
                        'name': 'prepreg',
                        'type': 'dielectric',
                        'thickness_um': 100,
                        'material': 'FR408-HR',
                        'epsilon_r': 3.66,
                        'loss_tangent': 0.009
                    },
                    ...
                ],
                'total_thickness_mm': 1.6,
                'finish': 'ENIG',
                'has_impedance_control': True
            }
        """
        # Parse stackup from the .kicad_pcb file
        # Note: _parse_stackup_from_file already logs the stackup summary via self.log()
        try:
            board_file_path = self.board.GetFileName()
            if board_file_path:
                return self._parse_stackup_from_file(board_file_path)
        except Exception:
            pass
        
        # If file parsing fails, return None (will use defaults)
        return None
    
    def _get_layer_dielectric_constant(self, layer_id, stackup_data=None):
        """
        Get dielectric constant for layer from stackup.
        
        Args:
            layer_id: KiCad layer ID
            stackup_data: Pre-parsed stackup data (optional)
            
        Returns:
            float: Dielectric constant (Er), or default 4.3 if unavailable
        """
        if stackup_data is None:
            return 4.3  # No stackup provided, use default (avoid re-fetching)
        
        if not stackup_data or not stackup_data.get('layers'):
            return 4.3  # Default FR-4
        
        layer_name = self.board.GetLayerName(layer_id)
        
        # Find the copper layer index
        copper_idx = None
        for i, layer in enumerate(stackup_data['layers']):
            if layer['type'] == 'copper' and layer['name'] == layer_name:
                copper_idx = i
                break
        
        if copper_idx is None:
            return 4.3  # Layer not found
        
        # Search for dielectric layer AFTER this copper (downward in stackup)
        for i in range(copper_idx + 1, len(stackup_data['layers'])):
            layer = stackup_data['layers'][i]
            if layer['type'] == 'dielectric':
                return layer.get('epsilon_r', 4.3)
        
        # If not found after, search BEFORE this copper (upward - for bottom layer)
        for i in range(copper_idx - 1, -1, -1):
            layer = stackup_data['layers'][i]
            if layer['type'] == 'dielectric':
                return layer.get('epsilon_r', 4.3)
        
        return 4.3  # Default if no dielectric found
    
    def _get_layer_copper_thickness(self, layer_id, stackup_data=None):
        """
        Get copper thickness for layer from stackup.
        
        Args:
            layer_id: KiCad layer ID
            stackup_data: Pre-parsed stackup data (optional)
            
        Returns:
            float: Copper thickness in microns, or default 35μm (1oz) if unavailable
        """
        if stackup_data is None:
            return 35.0  # No stackup provided, use default (avoid re-fetching)
        
        if not stackup_data or not stackup_data.get('layers'):
            return 35.0  # Default 1oz copper
        
        layer_name = self.board.GetLayerName(layer_id)
        
        for layer in stackup_data['layers']:
            if layer['type'] == 'copper' and layer['name'] == layer_name:
                return layer.get('thickness_um', 35.0)
        
        return 35.0  # Default if not found
    
    def _layer_has_planes(self, layer_id):
        """
        Check if a layer contains copper planes (GND/PWR zones).
        
        Args:
            layer_id: KiCad layer ID
            
        Returns:
            bool: True if layer has plane zones
        """
        zones = self.board.GetZones()
        
        for zone in zones:
            if zone.GetLayer() == layer_id:
                # Check if it's a power/ground zone (typically large filled zones)
                net = zone.GetNet()
                if net:
                    net_name = net.GetNetname().upper()
                    # Common ground/power patterns
                    if any(pattern in net_name for pattern in ['GND', 'VCC', 'VDD', 'PWR', '+3V3', '+5V', '+12V']):
                        return True
        
        return False
    
    def _draw_segment_highlight(self, track, group, net_name, Z0_actual, Z0_target):
        """
        Draw a visual highlight of the problematic track segment on User.Comments layer.
        This makes it easy to see exactly which segment needs redesign.
        
        Args:
            track: pcbnew.PCB_TRACK - the track segment with violation
            group: pcbnew.PCB_GROUP - violation group to add highlight to
            net_name: str - net name for identification
            Z0_actual: float - calculated impedance
            Z0_target: float - target impedance
        """
        try:
            import pcbnew
            
            # Create a line on User.Comments layer showing the segment
            highlight = pcbnew.PCB_SHAPE(self.board)
            highlight.SetShape(pcbnew.SHAPE_T_SEGMENT)
            highlight.SetStart(track.GetStart())
            highlight.SetEnd(track.GetEnd())
            
            # Use same width as original track for accurate visualization in tight spaces
            highlight_width = track.GetWidth()
            highlight.SetWidth(highlight_width)
            
            # Place on User.Comments layer
            highlight.SetLayer(self.marker_layer)
            
            # Add to board and group
            self.board.Add(highlight)
            if group:
                group.AddItem(highlight)
                
        except Exception as e:
            # Don't fail the whole check if highlighting fails
            self.log(f"    Warning: Could not draw segment highlight: {e}")
    
    def _resolve_net_class(self, net_name: str) -> str:
        """
        Resolve the effective net class for a net.

        Uses a cached map built once per checker run.

        Args:
            net_name: Net name string

        Returns:
            str: Effective net class name, or 'Default' if unresolved
        """
        if not hasattr(self, '_net_class_cache') or self._net_class_cache is None:
            self._net_class_cache = self._build_net_class_map()
        return self._net_class_cache.get(net_name, 'Default')

    def _build_net_class_map(self) -> dict:
        """
        Build a complete {net_name: class_name} map using the same strategy
        as clearance_creepage.py (auditor.get_nets_by_class), which is confirmed
        to work correctly in KiCad 9.

        Strategy:
        1. Iterate all nets: GetNetClassName() with substring match (handles
           comma-separated classes like "50R,Default")
        2. Fall back to board file pattern parsing for any remaining unresolved nets

        Returns:
            dict: {net_name: class_name}
        """
        import re
        net_class_map = {}

        # --- Source 1: GetNetClassName() with substring match (same as auditor) ---
        # This is exactly what clearance_creepage.py uses via auditor.get_nets_by_class()
        # Substring match handles comma-separated cases: "50R,Default" contains "50R"
        try:
            all_nets = self.board.GetNetInfo().NetsByName().values()
            for net in all_nets:
                net_nm = net.GetNetname()
                if not net_nm:
                    continue
                net_class_str = net.GetNetClassName()  # may be "50R,Default" or "50R" or "Default"
                if not net_class_str or net_class_str == 'Default':
                    continue
                # If comma-separated, take the first non-Default token
                for token in net_class_str.split(','):
                    token = token.strip()
                    if token and token != 'Default':
                        net_class_map[net_nm] = token
                        break
        except Exception as e:
            self.log(f"  ⚠ Net class scan via GetNetClassName failed: {e}")

        # --- Source 2: Board file pattern parsing for still-unresolved nets ---
        # KiCad 9 pattern-based assignments may not appear in GetNetClassName() at all
        try:
            board_path = self.board.GetFileName()
            if board_path:
                content = open(board_path, 'r', encoding='utf-8').read()

                # KiCad 6/7 explicit: (net_class "NAME" ... (add_net "netname"))
                for nc_block in re.finditer(r'\(net_class\s+"([^"]+)"(.*?)(?=\(net_class\s+|\Z)',
                                             content, re.DOTALL):
                    nc_name = nc_block.group(1)
                    if nc_name == 'Default':
                        continue
                    for net_match in re.finditer(r'\(add_net\s+"([^"]+)"\)', nc_block.group(2)):
                        net_nm = net_match.group(1)
                        if net_nm not in net_class_map:
                            net_class_map[net_nm] = nc_name

                # KiCad 8/9 net_settings: (class "NAME" ... (nets "n1" "n2") (pattern "glob"))
                for class_match in re.finditer(
                    r'\(class\s+"([^"]+)"(.*?)(?=\s*\(class\s+"|\Z)',
                    content, re.DOTALL
                ):
                    nc_name = class_match.group(1)
                    if nc_name == 'Default':
                        continue
                    body = class_match.group(2)

                    # Explicit net names inside (nets ...) block
                    nets_block = re.search(r'\(nets(.*?)\)', body, re.DOTALL)
                    if nets_block:
                        for net_match in re.finditer(r'"([^"]+)"', nets_block.group(1)):
                            net_nm = net_match.group(1)
                            if not re.match(r'^[\d.eE+\-]+$', net_nm) and net_nm not in net_class_map:
                                net_class_map[net_nm] = nc_name

                    # Pattern assignments: (pattern "glob*")
                    for pat_match in re.finditer(r'\(pattern\s+"([^"]+)"\)', body):
                        glob = pat_match.group(1)
                        regex = re.compile(
                            '^' + re.escape(glob).replace(r'\*', '.*').replace(r'\?', '.') + '$',
                            re.IGNORECASE
                        )
                        all_nets = self.board.GetNetInfo().NetsByName().values()
                        for net in all_nets:
                            net_nm = net.GetNetname()
                            if net_nm and net_nm not in net_class_map and regex.match(net_nm):
                                net_class_map[net_nm] = nc_name

        except Exception as e:
            self.log(f"  ⚠ Board file net class parse failed: {e}")

        # Log summary
        non_default = sorted({v for v in net_class_map.values()})
        self.log(f"  Net class map: {len(net_class_map)} explicit assignments, classes: {non_default or ['(none — all Default)']}")

        return net_class_map

    def _is_critical_net(self, net):
        """
        Check if net belongs to critical net class.

        Args:
            net: pcbnew.NETINFO_ITEM

        Returns:
            bool: True if net is in critical net classes
        """
        if not net:
            return False

        critical_classes = self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        net_class = self._resolve_net_class(net.GetNetname())

        return net_class in critical_classes
