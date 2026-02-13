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
        self._check_trace_near_plane_edge()
        self._check_reference_plane_crossing()
        self._check_reference_plane_changing()
        self._check_exposed_critical_traces()
        self._check_net_length()
        self._check_net_stubs()
        self._check_unreferenced_traces()
        self._check_unconnected_via_pads()
        
        # Run individual checks - Crosstalk and Isolation
        self._check_critical_net_isolation_single()
        self._check_critical_net_isolation_differential()
        self._check_net_coupling()
        self._check_differential_pair_matching()
        self._check_differential_running_skew()
        
        # Run individual checks - Impedance Control
        self._check_controlled_impedance()
        
        self.log(f"\n=== SIGNAL INTEGRITY CHECK COMPLETE: {self.violation_count} violations ===", force=True)
        return self.violation_count
    
    # ========================================================================
    # CHECK 1: Critical Net Near Edge of Reference Plane
    # ========================================================================
    
    def _check_trace_near_plane_edge(self):
        """
        Check for traces too close to reference plane edges.
        
        TODO: Implementation needed
        
        Description:
        Traces routed near the edge of their reference plane can radiate EMI
        and suffer from impedance discontinuities due to lack of proper return path.
        
        Algorithm:
        1. Identify all copper plane zones (GND/power planes)
        2. Extract plane edge boundaries (polygons)
        3. For each critical net trace segment:
           - Find closest reference plane (layer above/below)
           - Calculate minimum distance to plane edge
           - Flag if distance < threshold (typically 3x trace width or 3-5mm)
        
        Configuration parameters:
        - min_edge_distance_mm: Minimum distance from trace to plane edge (default: 3.0mm)
        - critical_net_classes: List of net classes to check (e.g., ['HighSpeed', 'Clock'])
        - check_all_signals: If True, check all signal traces (default: False)
        
        Standards:
        - IPC-2221: Recommends 3x trace width clearance minimum
        - Best practice: 5mm for high-speed signals
        
        Returns:
        Number of violations found
        """
        self.log("\n--- Checking Trace Near Plane Edge ---")
        
        # Parse configuration
        # min_edge_distance_mm = self.config.get('min_edge_distance_mm', 3.0)
        # critical_net_classes = self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        
        # TODO: Implement plane boundary extraction
        # TODO: Implement trace-to-boundary distance calculation
        # TODO: Create violation markers for traces too close to edges
        
        violations = 0
        self.log(f"TODO: Trace near plane edge check - {violations} violations")
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
        
        # TODO: Implement outer layer detection
        # TODO: Calculate total exposed length per critical net
        # TODO: Flag nets with excessive outer layer routing
        
        violations = 0
        self.log(f"TODO: Exposed critical traces check - {violations} violations")
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
        
        # TODO: Implement net length calculation including vias
        # TODO: Compare against per-netclass limits
        # TODO: Special handling for differential pairs
        
        violations = 0
        self.log(f"TODO: Net length check - {violations} violations")
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
        
        # TODO: Map signal layers to reference plane layers
        # TODO: Extract plane coverage polygons
        # TODO: Calculate trace segments outside plane coverage
        # TODO: Flag excessive unreferenced lengths
        
        violations = 0
        self.log(f"TODO: Unreferenced traces check - {violations} violations")
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
        
        # TODO: Implement via layer span detection
        # TODO: Check connectivity on each internal layer
        # TODO: Flag vias with unconnected pads on internal layers
        
        violations = 0
        self.log(f"TODO: Unconnected via pads check - {violations} violations")
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
        
        # TODO: Implement critical net identification
        # TODO: Scan adjacent traces perpendicular to critical traces
        # TODO: Verify ground guards or vacant isolation zones
        # TODO: Create violation markers where isolation inadequate
        
        violations = 0
        self.log(f"TODO: Critical net isolation (single-ended) check - {violations} violations")
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
        
        # TODO: Identify differential pairs from net names
        # TODO: Calculate total routed length for each trace in pair
        # TODO: Compare lengths and flag mismatches
        # TODO: Sample spacing along pair route
        # TODO: Calculate spacing variation and flag inconsistencies
        
        violations = 0
        self.log(f"TODO: Differential pair matching check - {violations} violations")
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
        
        if not target_impedances:
            self.log("No net classes configured for impedance checking (target_impedance_by_class empty)")
            return 0
        
        self.log(f"Impedance targets: {target_impedances}")
        self.log(f"Tolerance: ±{tolerance_ohms}Ω")
        
        # Extract board stackup data
        stackup = self._get_board_stackup()
        
        if not stackup:
            self.log("⚠ No stackup data available, using FR-4 defaults (35µm copper, εr=4.3)")
        
        # TODO: For each controlled impedance net class:
        #   - Get all trace segments using GetTracks()
        #   - For each segment on controlled net:
        #       * Get layer with segment.GetLayer()
        #       * Detect transmission line type using _detect_transmission_line_type()
        #       * Get trace width: segment.GetWidth()
        #       * Get dielectric height: _get_dielectric_height_to_plane(layer)
        #       * Get copper thickness: _get_layer_copper_thickness(layer)
        #       * Get dielectric constant: _get_layer_dielectric_constant(layer)
        #       * Calculate Z0 using _calculate_microstrip_impedance() or _calculate_stripline_impedance()
        #       * For differential pairs: measure spacing S, calculate Zdiff with _calculate_differential_impedance()
        #       * Compare Z0_calc vs Z0_target from config
        #       * If |Z0_calc - Z0_target| > tolerance: create violation marker
        #
        # Example implementation pattern:
        #   for track in self.board.GetTracks():
        #       net = track.GetNet()
        #       if not net or net.GetNetClassName() not in target_impedances:
        #           continue
        #       
        #       layer = track.GetLayer()
        #       W_mm = pcbnew.ToMM(track.GetWidth())
        #       H_mm = self._get_dielectric_height_to_plane(layer)
        #       t_um = self._get_layer_copper_thickness(layer)
        #       Er = self._get_layer_dielectric_constant(layer)
        #       
        #       if self._detect_transmission_line_type(layer) == 'microstrip':
        #           Z0 = self._calculate_microstrip_impedance(W_mm, H_mm, t_um, Er)
        #       elif self._detect_transmission_line_type(layer) == 'stripline':
        #           b_mm = H_mm * 2  # symmetric stripline
        #           Z0 = self._calculate_stripline_impedance(W_mm, b_mm, t_um, Er)
        #       
        #       Z0_target = target_impedances[net.GetNetClassName()]
        #       if abs(Z0 - Z0_target) > tolerance_ohms:
        #           self.draw_marker(self.board, track.GetStart(), 
        #                          f"Z0={Z0:.1f}Ω (target={Z0_target:.1f}Ω)", 
        #                          self.marker_layer, group)
        
        violations = 0
        self.log(f"TODO: Controlled impedance check - {violations} violations")
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
        
        TODO: Implementation needed
        
        Args:
            Z0_single: Single-ended impedance in Ohms
            S_mm: Spacing between differential pair traces in mm
            H_mm: Dielectric height to reference plane in mm
            
        Returns:
            float: Differential impedance in Ohms
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
    
    def _get_dielectric_height_to_plane(self, trace_layer):
        """
        Get dielectric height from trace layer to nearest reference plane.
        
        Implementation uses KiCad's BOARD_STACKUP API (KiCad 7.0+)
        
        Args:
            trace_layer: KiCad layer ID
            
        Returns:
            float: Height in mm, or None if cannot determine
        """
        try:
            # KiCad 7.0+ has board stackup API
            design_settings = self.board.GetDesignSettings()
            stackup = design_settings.GetStackupDescriptor()
            
            if not stackup:
                self.log("Warning: No stackup data in board file, using defaults")
                return None
            
            # Get all stackup items
            stackup_items = stackup.GetList()
            trace_layer_name = self.board.GetLayerName(trace_layer)
            
            # Find the trace layer in stackup
            dielectric_height = 0.0
            found_trace_layer = False
            
            for item in stackup_items:
                layer_name = item.GetLayerName()
                
                if layer_name == trace_layer_name:
                    found_trace_layer = True
                    # Found trace layer, now accumulate dielectric until we hit a plane
                    continue
                
                if found_trace_layer:
                    # Check if this is a dielectric layer
                    if item.GetType() == pcbnew.BS_ITEM_TYPE_DIELECTRIC:
                        thickness = item.GetThickness()  # in internal units
                        dielectric_height += pcbnew.ToMM(thickness)
                    
                    # Check if this is a copper plane layer (GND/PWR)
                    elif item.GetType() == pcbnew.BS_ITEM_TYPE_COPPER:
                        layer_id = item.GetBrdLayerId()
                        # Check if this layer has copper zones (planes)
                        if self._layer_has_planes(layer_id):
                            # Found reference plane, return accumulated height
                            return dielectric_height
            
            # If no plane found, return None
            return None
            
        except AttributeError:
            # Older KiCad version without stackup API
            self.log("Warning: KiCad version does not support stackup API, using defaults")
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
        try:
            board_file_path = self.board.GetFileName()
            if board_file_path:
                return self._parse_stackup_from_file(board_file_path)
        except Exception:
            pass
        
        # If file parsing fails, return None (will use defaults)
        return None
    
    def _get_layer_dielectric_constant(self, layer_id):
        """
        Get dielectric constant for layer from stackup.
        
        Args:
            layer_id: KiCad layer ID
            
        Returns:
            float: Dielectric constant (Er), or default 4.3 if unavailable
        """
        stackup_data = self._get_board_stackup()
        
        if not stackup_data:
            return 4.3  # Default FR-4
        
        layer_name = self.board.GetLayerName(layer_id)
        
        # Find the dielectric layer after this copper layer
        found_copper = False
        for layer in stackup_data['layers']:
            if layer['type'] == 'copper' and layer['name'] == layer_name:
                found_copper = True
                continue
            
            if found_copper and layer['type'] == 'dielectric':
                return layer.get('epsilon_r', 4.3)
        
        return 4.3  # Default if not found
    
    def _get_layer_copper_thickness(self, layer_id):
        """
        Get copper thickness for layer from stackup.
        
        Args:
            layer_id: KiCad layer ID
            
        Returns:
            float: Copper thickness in microns, or default 35μm (1oz) if unavailable
        """
        stackup_data = self._get_board_stackup()
        
        if not stackup_data:
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
        net_class = net.GetNetClassName()
        
        return net_class in critical_classes
