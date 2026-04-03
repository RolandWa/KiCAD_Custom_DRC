"""
Signal Integrity Verification Module for EMC Auditor Plugin
Comprehensive signal and via integrity checks for EMI reduction and signal quality

This module is called by emc_auditor_plugin.py and reuses its utility functions.
Configuration is read from emc_rules.toml [signal_integrity] section.

Author: EMC Auditor Plugin
Version: 1.0.0
Last Updated: 2026-02-13

================================================================================
IMPLEMENTATION PRIORITY - TODO LIST (Easy → Hard)
================================================================================

PHASE 1 - EASY (Basic Geometry & Filtering)
────────────────────────────────────────────────────────────────────────────
□ CHECK 5: Net Length Maximum
  Difficulty: ★☆☆☆☆ (EASIEST)
  - Simple: Iterate tracks, sum lengths per net, compare to threshold
  - APIs available: GetTracks(), GetLength()
  - No complex algorithms needed
  - Estimated time: 2-3 hours

□ CHECK 4: Exposed Critical Traces  
  Difficulty: ★★☆☆☆
  - Check if trace layer is outer layer (F.Cu or B.Cu)
  - Sum exposed segment lengths per net
  - Simple layer ID comparison
  - Estimated time: 3-4 hours

□ CHECK 8: Unconnected Via Pads
  Difficulty: ★★☆☆☆
  - Get via layer span, iterate internal layers
  - Check GetConnectedItems() on each layer
  - Flag if no connections found
  - Estimated time: 4-5 hours


PHASE 2 - MEDIUM (Spatial Analysis & Pattern Matching)
────────────────────────────────────────────────────────────────────────────
□ CHECK 14: Controlled Impedance Verification
  Difficulty: ★★★☆☆
  - Use analytical formulas (no FEM needed!)
  - ✅ STACKUP READING: Fully implemented! Reads from KiCad 7.0+ board files
  - ✅ FORMULAS: Microstrip, Stripline, CPW, Differential all implemented
  - Extract geometry: trace width, thickness, dielectric height, Er
  - Calculate impedance using IPC-2141/Wadell formulas
  - Transmission line types: Microstrip, Stripline, Coplanar
  - Fast calculation with 5-10% accuracy (sufficient for DRC)
  - Estimated time: 4-5 hours remaining (stackup API done!)

□ CHECK 12: Differential Pair Length Matching
  Difficulty: ★★★☆☆
  - Implement _identify_differential_pairs() with regex
  - Calculate total length for both traces (reuse CHECK 5 logic)
  - Compare P vs N lengths
  - Estimate time: 5-6 hours

□ CHECK 9: Critical Net Isolation (Single-Ended)
  Difficulty: ★★★☆☆
  - Requires perpendicular scanning from trace
  - Check nearby traces within distance threshold
  - Verify if neighbor is GND net (pattern matching)
  - Spatial search needed but simplified (2D)
  - Estimated time: 6-8 hours

□ CHECK 1: Trace Near Plane Edge
  Difficulty: ★★★☆☆
  - Extract zone boundaries: GetZones(), GetOutline()
  - Calculate distance from trace to polygon edge
  - Geometry: point-to-polygon distance
  - Estimated time: 6-8 hours

□ CHECK 7: Unreferenced Traces (Above/Below Reference Plane)
  Difficulty: ★★★☆☆
  - Similar to CHECK 1 but checks vertical plane coverage
  - Map signal layers to adjacent plane layers
  - Check if trace segments overlap with plane polygons
  - Estimated time: 7-9 hours


PHASE 3 - ADVANCED (Complex Geometry & Graph Algorithms)
────────────────────────────────────────────────────────────────────────────
□ CHECK 11: Net Coupling / Crosstalk Analysis
  Difficulty: ★★★★☆
  - Build spatial index (R-tree or grid) for all segments
  - Detect parallel segments with angular tolerance
  - Calculate overlap length and minimum spacing
  - Compute coupling coefficient (length/spacing ratio)
  - Requires efficient spatial queries
  - Estimated time: 10-12 hours

□ CHECK 6: Net Stub Check
  Difficulty: ★★★★☆
  - Build connectivity graph per net
  - Detect branch points (T-junctions)
  - Calculate stub lengths from graph
  - Handle via stubs (unused via tails)
  - Graph traversal algorithms needed
  - Estimated time: 10-12 hours

□ CHECK 10: Critical Net Isolation (Differential)
  Difficulty: ★★★★☆
  - Requires CHECK 12 differential pair identification
  - Determine pair orientation (which traces are inside/outside)
  - Check outer edges only (not between pair)
  - More complex geometry than single-ended isolation
  - Estimated time: 8-10 hours


PHASE 4 - EXPERT (Multi-Layer & Advanced Analysis)
────────────────────────────────────────────────────────────────────────────
□ CHECK 2: Reference Plane Crossing
  Difficulty: ★★★★★
  - Analyze layer stackup (signal layers vs plane layers)
  - For each via: determine reference planes on start/end layers
  - Detect plane net name changes (GND → AGND, GND → +3V3)
  - Search for stitching vias nearby
  - Requires stackup understanding
  - Estimated time: 12-15 hours

□ CHECK 3: Reference Plane Changing
  Difficulty: ★★★★★
  - Continuous trace path tracking (segment by segment)
  - At each segment, determine plane directly below/above
  - Detect transitions between different plane nets or gaps
  - Horizontal plane changes (gaps in planes on same layer)
  - Most complex plane analysis
  - Estimated time: 12-15 hours

□ CHECK 13: Differential Running Skew
  Difficulty: ★★★★★ (HARDEST)
  - Traverse both P and N traces simultaneously from source
  - Track cumulative length at each point
  - Calculate running skew continuously
  - Detect serpentine compensation sections
  - Requires sophisticated paired trace traversal algorithm
  - Estimated time: 15-18 hours


PHASE 5 - FUTURE ENHANCEMENTS (Not from SiWave, but valuable)
────────────────────────────────────────────────────────────────────────────
□ Via Anti-Pad Violations
  - Check via clearance holes in plane layers
  - Verify anti-pad diameter ≥ pad + 2×clearance
  
□ Via-to-Via Spacing
  - Minimum edge-to-edge spacing check
  - Manufacturing constraint verification

□ Wide Power/Ground Traces
  - Check trace width vs length for power nets
  - Ensure adequate current capacity


IMPLEMENTATION RECOMMENDATIONS:
────────────────────────────────────────────────────────────────────────────
1. Start with PHASE 1 to build confidence and test framework integration
2. Implement helper methods incrementally:
   - _is_critical_net() - Already exists
   - _identify_differential_pairs() - Needed for PHASE 2
   - _get_reference_planes() - Needed for PHASE 4
   - _build_connectivity_graph() - Needed for PHASE 3
3. Test each check thoroughly with real PCB data before moving to next
4. Build spatial indexing infrastructure during PHASE 2 for reuse in PHASE 3
5. Consider using existing KiCad DRC engine APIs where available

Total Estimated Development Time: 120-150 hours (3-4 weeks full-time)
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

            # Find minimum distance from trace midpoint to any reference zone boundary
            mid = track.GetCenter()
            min_found = None
            for plane_layer in candidate_layers:
                for outline in zone_outlines.get(plane_layer, []):
                    for poly_idx in range(outline.OutlineCount()):
                        poly = outline.Outline(poly_idx)
                        for pt_idx in range(poly.PointCount()):
                            pt = poly.CPoint(pt_idx)
                            dx = mid.x - pt.x
                            dy = mid.y - pt.y
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
    # CHECK 2: Reference Plane Crossing
    # ========================================================================
    
    def _check_reference_plane_crossing(self):
        """
        Check for signals crossing between different reference planes.
        
        TODO: Implementation needed
        
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
        
        # TODO: Implement reference plane detection per layer
        # TODO: Implement via transition analysis
        # TODO: Check for stitching vias near plane crossings
        
        violations = 0
        self.log(f"TODO: Reference plane crossing check - {violations} violations")
        return violations
    
    # ========================================================================
    # CHECK 3: Reference Plane Changing
    # ========================================================================
    
    def _check_reference_plane_changing(self):
        """
        Check for signals changing reference planes along their path.
        
        TODO: Implementation needed
        
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
        
        # TODO: Implement continuous trace path tracking
        # TODO: Implement reference plane mapping under trace segments
        # TODO: Detect and flag reference plane transitions
        
        violations = 0
        self.log(f"TODO: Reference plane changing check - {violations} violations")
        return violations
    
    # ========================================================================
    # CHECK 4: Length of Exposed Critical Traces
    # ========================================================================
    
    def _check_exposed_critical_traces(self):
        """
        Check for critical traces not buried between reference planes.
        
        TODO: Implementation needed
        
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
        
        TODO: Implementation needed
        
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
        
        TODO: Implementation needed
        
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
        - stub_calculation_method: 'physical' or 'electrical' length
        
        Standards:
        - Rule of thumb: Stub length < λ/10 at highest frequency
        - Via stubs: <1.5mm for signals >1GHz; consider backdrilling for >5GHz
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Net Stubs ---")
        
        # TODO: Implement connectivity graph building
        # TODO: Detect via stubs (unused via tails)
        # TODO: Detect branch stubs (T-junctions)
        # TODO: Calculate stub lengths and create violations
        
        violations = 0
        self.log(f"TODO: Net stub check - {violations} violations")
        return violations
    
    # ========================================================================
    # CHECK 7: Above/Below Reference Plane Check
    # ========================================================================
    
    def _check_unreferenced_traces(self):
        """
        Check for trace segments lacking reference planes above or below.
        
        TODO: Implementation needed
        
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

        # Build set of copper layers with reference plane coverage per layer
        # zone_bboxes[layer_id] = list of (xmin, ymin, xmax, ymax, SHAPE_POLY_SET)
        zone_polys = {}  # layer_id → list of SHAPE_POLY_SET
        for zone in self.board.Zones():
            net_name = zone.GetNetname()
            if not any(p.upper() in net_name.upper() for p in gnd_patterns):
                continue
            layer_id = zone.GetLayer()
            outline = zone.Outline()
            if outline is None:
                continue
            zone_polys.setdefault(layer_id, []).append(outline)

        if not zone_polys:
            self.log("  No reference plane zones found — skipping")
            return 0

        copper_layers = [l for l in range(pcbnew.F_Cu, pcbnew.B_Cu + 1)
                         if self.board.IsLayerEnabled(l)]

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

            # Check if at least one adjacent layer has a reference plane covering the midpoint
            mid = track.GetCenter()
            has_reference = False
            for offset in (-1, 1):
                adj_idx = sig_idx + offset
                if 0 <= adj_idx < len(copper_layers):
                    plane_layer = copper_layers[adj_idx]
                    for outline in zone_polys.get(plane_layer, []):
                        if outline.Contains(mid):
                            has_reference = True
                            break
                if has_reference:
                    break

            if not has_reference:
                net_unref[net_name] = net_unref.get(net_name, 0) + track.GetLength()
                net_class_cache[net_name] = net_class
                if net_name not in net_positions:
                    net_positions[net_name] = mid

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
        
        TODO: Implementation needed
        
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
        
        TODO: Implementation needed
        
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
        
        TODO: Implementation needed
        
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
          Example: [r'(.+)_P$', r'(.+)_N$'], [r'(.+)\+$', r'(.+)-$']
        - min_isolation_distance_mm: Minimum spacing to other signals (default: 4× pair width)
        - guard_trace_max_distance_mm: Max distance for guard qualification (default: 1.5mm)
        - require_both_sides: If True, require isolation on both outer edges (default: True)
        - ground_net_patterns: Patterns for ground guard nets
        
        Standards:
        - USB 2.0: 90Ω ±15% differential impedance, isolated routing
        - HDMI: 100Ω differential, guard or 4W spacing to adjacent signals
        - PCIe: Strict differential routing with isolation requirements
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Critical Net Isolation (Differential) ---")
        
        # TODO: Implement differential pair identification (P/N, +/- naming)
        # TODO: Determine pair orientation and outer edges
        # TODO: Scan for external isolation (guards or vacant zones)
        # TODO: Create violations for inadequate edge isolation
        
        violations = 0
        self.log(f"TODO: Critical net isolation (differential) check - {violations} violations")
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
        Check for excessive accumulated skew along differential pair path.
        
        TODO: Implementation needed
        
        Description:
        While total length matching is important, the PROGRESSIVE skew accumulation
        along the route also matters. Even if P and N are same total length, if one
        trace takes a longer path initially then compensates later, the accumulated
        skew in between can cause issues.
        
        Running skew rule:
        - At any point along the pair route, if skew exceeds threshold (e.g., 1mm),
          it must be compensated within a distance limit (e.g., 5mm)
        - This prevents long sections where skew is excessive
        
        Algorithm:
        1. For each differential pair:
           - Track both P and N traces simultaneously from source
           - At regular intervals, calculate cumulative length of each trace
           - Calculate running skew: |length_P - length_N| at each point
           - Track maximum uncompensated skew distance
        2. Flag if skew exceeds max_skew and isn't compensated within compensation_distance
        3. Identify serpentine sections (length compensation)
        
        Configuration parameters:
        - max_running_skew_mm: Maximum allowed instantaneous skew (default: 1.0mm)
        - compensation_distance_mm: Distance within which skew must be corrected (default: 5.0mm)
        - sample_interval_mm: Interval for skew measurement (default: 0.5mm)
        - detect_serpentines: Flag serpentines as compensation attempts (default: True)
        - critical_net_classes: Net classes requiring this check
        
        Use cases:
        - Source-synchronous interfaces (DDR, LVDS) very sensitive to skew
        - High-speed serial links (PCIe, SATA) need tight skew control
        - Less critical for asynchronous interfaces
        
        Standards:
        - JEDEC DDR4: Strict skew requirements within byte groups
        - PCIe: Running skew limits prevent excessive jitter accumulation
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Differential Running Skew ---")
        
        # TODO: Implement paired trace traversal algorithm
        # TODO: Calculate cumulative length at sample points
        # TODO: Track running skew accumulation
        # TODO: Detect where skew exceeds limits without compensation
        # TODO: Create violations showing skew zones
        
        violations = 0
        self.log(f"TODO: Differential running skew check - {violations} violations")
        return violations
    
    # ========================================================================
    # CHECK 14: Controlled Impedance Verification
    # ========================================================================
    
    def _check_controlled_impedance(self):
        """
        Verify trace impedance using analytical formulas (geometry-based).
        
        TODO: Implementation needed
        
        Description:
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
            
            # Check tolerance
            error = abs(Z0_calc - Z0_target)
            
            if error > tolerance_ohms:
                violations += 1
                percent_error = (error / Z0_target) * 100
                
                # Create compact PCB marker
                violation_msg = f"❌ {net_name}\nZ0: {Z0_calc:.1f}Ω (target {Z0_target:.1f}Ω)"
                
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
                self.log(f"  ❌ {net_name}: Z0={Z0_calc:.1f}Ω (target {Z0_target:.1f}Ω ±{tolerance_ohms}Ω) ERROR: {error:.1f}Ω ({percent_error:.1f}%)")
                self.log(f"     Layer: {layer_name} ({tline_type}), Width: {W_mm:.3f}mm, H: {H_mm:.3f}mm, t: {t_um:.1f}µm, εr: {Er:.2f}")
            else:
                self.log(f"  ✓ {net_name}: Z0={Z0_calc:.1f}Ω (target {Z0_target:.1f}Ω) PASS")
        
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
        
        TODO: Implementation needed
        
        Args:
            signal_layer: KiCad layer ID of signal layer
            
        Returns:
            tuple: (layer_above, layer_below) - KiCad layer IDs or None
        """
        # TODO: Implement layer stack analysis
        return (None, None)
    
    def _extract_plane_boundaries(self, plane_layer):
        """
        Extract polygon boundaries of copper planes on a layer.
        
        TODO: Implementation needed
        
        Args:
            plane_layer: KiCad layer ID
            
        Returns:
            list: List of polygon outlines (SHAPE_POLY_SET or similar)
        """
        # TODO: Iterate zones on layer, extract outlines
        return []
    
    def _calculate_trace_length(self, net):
        """
        Calculate total routed length of a net including vias.
        
        TODO: Implementation needed
        
        Args:
            net: pcbnew.NETINFO_ITEM
            
        Returns:
            float: Total length in internal units
        """
        # TODO: Sum all track segments + via heights
        return 0
    
    def _build_connectivity_graph(self, net):
        """
        Build graph of connections for stub detection.
        
        TODO: Implementation needed
        
        Args:
            net: pcbnew.NETINFO_ITEM
            
        Returns:
            dict: Graph structure with nodes and edges
        """
        # TODO: Build graph from tracks, vias, pads
        return {}
    
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
        # TODO: Parse net names for P/N, +/-, true/complement patterns
        # Common patterns: _P/_N, _DP/_DN, +/-, _T/_C, _TRUE/_COMP
        return {}
    
    def _find_parallel_segments(self, segment, max_distance, angular_tolerance=10):
        """
        Find trace segments running parallel to a given segment.
        
        TODO: Implementation needed
        
        Args:
            segment: Track segment to check
            max_distance: Maximum perpendicular distance to consider
            angular_tolerance: Max angle deviation to consider parallel (degrees)
            
        Returns:
            list: List of (track, parallel_length, min_spacing) tuples
        """
        # TODO: Use spatial indexing for efficiency
        # TODO: Calculate segment angle and compare with candidates
        # TODO: Measure overlap length and minimum spacing
        return []
    
    def _calculate_spacing_along_pair(self, net_p, net_n, sample_interval_mm=1.0):
        """
        Sample spacing between differential pair traces along route.
        
        TODO: Implementation needed
        
        Args:
            net_p: Positive net (pcbnew.NETINFO_ITEM)
            net_n: Negative net (pcbnew.NETINFO_ITEM)
            sample_interval_mm: Distance between sampling points
            
        Returns:
            list: List of spacing measurements in internal units
        """
        # TODO: Traverse both traces in parallel
        # TODO: Sample spacing at regular intervals
        # TODO: Return spacing measurements for statistical analysis
        return []
    
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
        Calculate stripline impedance (symmetric between two planes).
        
        TODO: Implementation needed
        
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
        Calculate coplanar waveguide impedance.
        
        TODO: Implementation needed (requires elliptic integral)
        
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
        
        # Approximation of elliptic integral ratio K(k)/K(k')
        # Using logarithmic approximation (accurate to ~1%)
        K_ratio = math.pi / math.log(2 * (1 + math.sqrt(k_prime)) / (1 - math.sqrt(k_prime)))
        
        if has_ground_plane:
            # CPWG: ground plane present
            Er_eff = Er
            # Modified k accounting for ground plane (sinh approximation)
            sinh_W = math.sinh(math.pi * W_mm / (4 * H_mm))
            sinh_WS = math.sinh(math.pi * (W_mm + 2*S_mm) / (4 * H_mm))
            k1 = sinh_W / sinh_WS
            k1_prime = math.sqrt(1 - k1**2)
            K_ratio = math.pi / math.log(2 * (1 + math.sqrt(k1_prime)) / (1 - math.sqrt(k1_prime)))
        else:
            # CPW: no ground plane (air above)
            Er_eff = (Er + 1) / 2
        
        Z0 = (30 * math.pi / math.sqrt(Er_eff)) * K_ratio
        
        return Z0
    
    def _detect_transmission_line_type(self, layer_name):
        """
        Detect transmission line type based on layer position.
        
        TODO: Implementation needed
        
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
                    r'\(class\s+"([^"]+)"(.*?)(?=\s*\(class\s+"|\s*\)\s*\(|\Z)',
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
