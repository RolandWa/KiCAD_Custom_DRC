"""
Ground Plane Continuity Checker Module
Part of EMC Auditor Plugin for KiCad

Verifies ground plane continuity under and around high-speed traces.
Uses configurable parameters from emc_rules.toml [ground_plane] section.

Author: EMC Auditor Team
License: MIT (see LICENSE file in repository)
"""

import pcbnew
import math

try:
    import wx
    HAS_WX = True
except ImportError:
    HAS_WX = False  # Testing environment without wxPython


class GroundPlaneChecker:
    """
    Checks ground plane continuity under and around high-speed signal traces.
    
    This checker validates that critical signals (e.g., HighSpeed, Clock net classes)
    have continuous ground plane coverage on adjacent or specified layers. It can:
    - Check continuity directly under traces (detects gaps/splits)
    - Check clearance around traces (ensures adequate ground reference nearby)
    - Support both adjacent-layer and all-layer checking modes
    - Ignore gaps near ground vias and pads (configurable clearance)
    - Show progress dialog for large boards (cancelable)
    
    Configuration (from emc_rules.toml [ground_plane] section):
        enabled: bool - Enable/disable this check
        critical_net_classes: list[str] - Net classes requiring ground plane (e.g., ['HighSpeed', 'Clock'])
        ground_net_patterns: list[str] - Ground net name patterns (e.g., ['GND', 'GROUND', 'VSS'])
        check_continuity_under_trace: bool - Check for gaps directly under trace
        check_clearance_around_trace: bool - Check for adequate ground around trace
        ground_plane_check_layers: str - 'adjacent' or 'all' (which layers to check)
        check_both_sides: bool - Check both sides perpendicular to trace (clearance check)
        ignore_via_clearance: float - Ignore gaps within X mm of ground vias
        ignore_pad_clearance: float - Ignore gaps within X mm of ground pads
        min_ground_polygon_area_mm2: float - Minimum zone area to consider (filters small islands)
        max_gap_under_trace_mm: float - Maximum allowable gap under trace (unused in current implementation)
        sampling_interval_mm: float - Distance between sample points along trace
        min_clearance_around_trace_mm: float - Clearance zone width around trace
        max_ground_gap_in_clearance_zone_mm: float - Maximum gap in clearance zone (unused)
        preferred_ground_layers: list[str] - Preferred ground layers to check first (optional)
        violation_message_no_ground: str - Message for continuity violation
        violation_message_insufficient_clearance: str - Message for clearance violation
    
    Usage:
        checker = GroundPlaneChecker(board, marker_layer, config, report_lines, verbose, auditor)
        violations = checker.check(draw_marker_func, draw_arrow_func, get_distance_func)
    """
    
    def __init__(self, board, marker_layer, config, report_lines, verbose, auditor):
        """
        Initialize Ground Plane Checker.
        
        Args:
            board: pcbnew.BOARD object
            marker_layer: Layer ID for drawing violation markers
            config: Configuration dict from emc_rules.toml [ground_plane] section
            report_lines: Shared list for report text (modified in-place)
            verbose: bool - Enable verbose logging and reporting
            auditor: Reference to main EMCAuditorPlugin instance (for utility method access)
        """
        self.board = board
        self.marker_layer = marker_layer
        self.config = config
        self.report_lines = report_lines
        self.verbose = verbose
        self.auditor = auditor  # For accessing get_nets_by_class() if needed
    
    def check(self, draw_marker_func, draw_arrow_func, get_distance_func, log_func, create_group_func):
        """
        Execute ground plane continuity check.
        
        This method receives utility functions from the main plugin via dependency injection,
        avoiding code duplication while maintaining modularity.
        
        Args:
            draw_marker_func: Function to draw violation markers (signature: board, pos, msg, layer, group)
            draw_arrow_func: Function to draw directional arrows (signature: board, start, end, label, layer, group)
            get_distance_func: Function to calculate distance (signature: p1, p2 -> float)
            log_func: Function(msg, force=False) for logging
            create_group_func: Function(board, check_type, identifier, number) creates PCB_GROUP
        
        Returns:
            int: Number of violations found
        """
        # Store utility functions for reuse
        self.log = log_func  # Centralized logger from main plugin
        self.log("\n=== GROUND PLANE CHECK START ===", force=True)
        
        # Load configuration parameters
        critical_classes = self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        gnd_patterns = [p.upper() for p in self.config.get('ground_net_patterns', ['GND'])]
        
        self.log(f"Looking for net classes: {critical_classes}")
        self.log(f"Looking for ground patterns: {gnd_patterns}")
        
        check_continuity = self.config.get('check_continuity_under_trace', True)
        check_clearance = self.config.get('check_clearance_around_trace', True)
        check_mode = self.config.get('ground_plane_check_layers', 'adjacent')  # 'adjacent' or 'all'
        check_both = self.config.get('check_both_sides', True)
        check_split_crossing = self.config.get('check_split_plane_crossing', True)  # NEW: Priority 2
        check_return_vias = self.config.get('check_return_via_continuity', True)  # NEW: Priority 3
        return_via_max_dist_mm = self.config.get('return_via_max_distance_mm', 3.0)  # mm
        ignore_via_clearance_mm = self.config.get('ignore_via_clearance', 0.5)  # mm
        ignore_pad_clearance_mm = self.config.get('ignore_pad_clearance', 0.3)  # mm
        min_area_mm2 = self.config.get('min_ground_polygon_area_mm2', 10.0)
        
        self.log(f"Check mode: {check_mode}")
        self.log(f"Check continuity: {check_continuity}")
        self.log(f"Check clearance: {check_clearance}")
        self.log(f"Check split crossing: {check_split_crossing}")
        self.log(f"Check return vias: {check_return_vias}")
        self.log(f"Return via max distance: {return_via_max_dist_mm} mm")
        self.log(f"Check both sides: {check_both}")
        self.log(f"Ignore via clearance: {ignore_via_clearance_mm} mm")
        self.log(f"Ignore pad clearance: {ignore_pad_clearance_mm} mm")
        self.log(f"Min ground polygon area: {min_area_mm2} mm²")
        
        max_gap_under = pcbnew.FromMM(self.config.get('max_gap_under_trace_mm', 0.5))
        sampling_interval = pcbnew.FromMM(self.config.get('sampling_interval_mm', 0.5))
        clearance_zone = pcbnew.FromMM(self.config.get('min_clearance_around_trace_mm', 1.0))
        max_gap_clearance = pcbnew.FromMM(self.config.get('max_ground_gap_in_clearance_zone_mm', 2.0))
        via_clearance_radius = pcbnew.FromMM(ignore_via_clearance_mm)
        pad_clearance_radius = pcbnew.FromMM(ignore_pad_clearance_mm)
        
        violation_msg_no_gnd = self.config.get('violation_message_no_ground', 'NO GND PLANE UNDER TRACE')
        violation_msg_clearance = self.config.get('violation_message_insufficient_clearance', 'INSUFFICIENT GND AROUND TRACE')
        
        violations = 0
        
        # Get all tracks on critical net classes
        self.log("\n--- Scanning all tracks ---")
        critical_tracks = []
        for track in self.board.GetTracks():
            if isinstance(track, pcbnew.PCB_TRACK):
                net_name = track.GetNetname()
                net_class = track.GetNetClassName()
                # Check if any critical class name is in the net class string
                # (KiCad may return "HighSpeed,Default" for nets in multiple classes)
                is_critical = any(crit_class in net_class for crit_class in critical_classes)
                
                # Debug output for CLK or if already marked critical
                if is_critical or 'CLK' in net_name.upper():
                    self.log(f"Track: net='{net_name}', class='{net_class}'")
                    if is_critical:
                        critical_tracks.append(track)
                        self.log(f"  ✓ Added to critical check")
        
        if not critical_tracks:
            self.log(f"\n❌ ERROR: No tracks found in critical net classes!", force=True)
            self.log(f"Expected classes: {critical_classes}", force=True)
            self.log("HINT: Check your KiCad net classes (Edit → Board Setup → Net Classes)", force=True)
            return 0
        
        # Get ALL zones (not just ground) for split plane detection - Priority 2
        # Dynamic zone discovery: no layer-to-plane assumptions
        self.log("\n--- Scanning all zones (dynamic discovery) ---")
        ground_zones = []
        all_reference_zones = []  # All zones (ground AND power) for split detection
        ground_zones_by_layer = {}  # Pre-filter zones by layer for O(1) lookup
        all_zones_by_layer = {}  # All reference planes by layer
        
        for zone in self.board.Zones():
            zone_net = zone.GetNetname().upper()
            zone_layer = zone.GetLayer()
            layer_name = self.board.GetLayerName(zone_layer)
            is_filled = zone.IsFilled()
            self.log(f"Zone: net='{zone.GetNetname()}', layer={layer_name}, filled={is_filled}")
            
            if not is_filled:
                self.log(f"  ⚠️  WARNING: Zone NOT FILLED! Press 'B' to fill zones.")
                continue  # Skip unfilled zones (can't hit test them)
            
            # Check minimum polygon area (filter out small copper islands)
            bbox = zone.GetBoundingBox()
            width_mm = pcbnew.ToMM(bbox.GetWidth())
            height_mm = pcbnew.ToMM(bbox.GetHeight())
            zone_area_mm2 = width_mm * height_mm  # Bounding box area in mm²
            if zone_area_mm2 < min_area_mm2:
                self.log(f"  ⚠️  Zone too small ({zone_area_mm2:.1f} mm² < {min_area_mm2:.1f} mm²), skipping")
                continue
            
            # Add ALL zones to reference plane list (for split detection)
            all_reference_zones.append(zone)
            if zone_layer not in all_zones_by_layer:
                all_zones_by_layer[zone_layer] = []
            all_zones_by_layer[zone_layer].append(zone)
            
            # Also track ground zones specifically
            if any(pat in zone_net for pat in gnd_patterns):
                ground_zones.append(zone)
                
                # Add to layer-indexed dict for fast lookup
                if zone_layer not in ground_zones_by_layer:
                    ground_zones_by_layer[zone_layer] = []
                ground_zones_by_layer[zone_layer].append(zone)
                self.log(f"  ✓ Added as GROUND zone ({zone_area_mm2:.1f} mm²)")
            else:
                self.log(f"  ✓ Added as REFERENCE zone (non-ground) ({zone_area_mm2:.1f} mm²)")
        
        if not ground_zones:
            self.log(f"\n❌ ERROR: No ground plane zones found!", force=True)
            self.log(f"Looking for patterns: {gnd_patterns}", force=True)
            self.log("HINT: Check zone net names contain GND, GROUND, VSS, etc.", force=True)
            return 0
        
        # Apply preferred ground layers if specified
        preferred_layers = self.config.get('preferred_ground_layers', [])
        if preferred_layers:
            self.log(f"\nPreferred ground layers: {preferred_layers}")
            # Sort ground zones by preferred layer priority
            # Zones on preferred layers will be checked first
            preferred_layer_names = [name.upper() for name in preferred_layers]
            for layer_id, zones in ground_zones_by_layer.items():
                layer_name = self.board.GetLayerName(layer_id).upper()
                # Check if this layer matches any preferred pattern
                is_preferred = any(pref in layer_name for pref in preferred_layer_names)
                if is_preferred:
                    self.log(f"  ✓ Layer {self.board.GetLayerName(layer_id)} marked as preferred")
        
        self.log(f"\n✓ Found {len(critical_tracks)} critical tracks, {len(ground_zones)} ground zones, {len(all_reference_zones)} total reference zones", force=True)
        self.log(f"   Ground zones indexed by {len(ground_zones_by_layer)} layers for fast lookup", force=True)
        self.log(f"   All zones indexed by {len(all_zones_by_layer)} layers for split detection", force=True)
        self.log("="*60)
        
        # Create progress dialog for user feedback
        progress = None
        if HAS_WX and len(critical_tracks) > 10:  # Only show progress for substantial work
            try:
                progress = wx.ProgressDialog(
                    "Ground Plane Check",
                    "Checking ground plane continuity...",
                    maximum=len(critical_tracks),
                    style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
                )
            except Exception as e:
                self.log(f"  ⚠️  Could not create progress dialog: {e}")
                progress = None
        
        # Check each critical track
        for track_idx, track in enumerate(critical_tracks):
            # Update progress dialog
            if progress:
                cont, skip = progress.Update(
                    track_idx, 
                    f"Checking track {track_idx+1}/{len(critical_tracks)} on net '{track.GetNetname()}'..."
                )
                if not cont:  # User clicked Cancel
                    self.log("\n⚠️  Ground plane check CANCELLED by user", force=True)
                    progress.Destroy()
                    return violations
            
            net_name = track.GetNetname()
            start = track.GetStart()
            end = track.GetEnd()
            track_layer = track.GetLayer()
            track_layer_name = self.board.GetLayerName(track_layer)
            
            self.log(f"\n>>> Checking track on net '{net_name}', layer {track_layer_name}")
            self.log(f"    Start: ({pcbnew.ToMM(start.x):.2f}, {pcbnew.ToMM(start.y):.2f}) mm")
            self.log(f"    End: ({pcbnew.ToMM(end.x):.2f}, {pcbnew.ToMM(end.y):.2f}) mm")
            
            # Determine which layers to check
            if check_mode == 'all':
                # Check all ground zones on all layers
                layers_to_check = list(set([zone.GetLayer() for zone in ground_zones]))
                layer_names = [self.board.GetLayerName(l) for l in layers_to_check]
                self.log(f"    Checking ground on ALL layers: {layer_names}")
            else:
                # Check only adjacent layer
                adjacent_layer = self.get_adjacent_ground_layer(track_layer)
                if adjacent_layer is None:
                    self.log(f"    ⚠️  No adjacent layer found, skipping")
                    continue
                layers_to_check = [adjacent_layer]
                self.log(f"    Checking ground on adjacent layer: {self.board.GetLayerName(adjacent_layer)}")
            
            # Sample points along the track
            track_length = get_distance_func(start, end)
            if track_length == 0:
                self.log(f"    ⚠️  Zero-length track, skipping")
                continue
            
            num_samples = max(2, int(track_length / sampling_interval))
            self.log(f"    Track length: {pcbnew.ToMM(track_length):.2f} mm, samples: {num_samples}")
            
            # ========== PRIORITY 1: Check continuity under trace (slot/gap detection) ==========
            if check_continuity:
                gap_found = False
                gap_position = None
                
                for i in range(num_samples + 1):
                    t = i / num_samples
                    sample_x = int(start.x + (end.x - start.x) * t)
                    sample_y = int(start.y + (end.y - start.y) * t)
                    sample_pos = pcbnew.VECTOR2I(sample_x, sample_y)
                    
                    # Check if ground plane exists at this point on ANY of the layers to check
                    # Use pre-filtered zones by layer for O(1) lookup instead of O(n) iteration
                    has_ground_on_any_layer = False
                    for check_layer in layers_to_check:
                        # Only check zones on this specific layer (much faster)
                        for zone in ground_zones_by_layer.get(check_layer, []):
                            # HitTestFilledArea checks if point is inside filled zone
                            if zone.HitTestFilledArea(check_layer, sample_pos):
                                has_ground_on_any_layer = True
                                break
                        if has_ground_on_any_layer:
                            break
                    
                    if not has_ground_on_any_layer:
                        # Check if violation is near a via or pad (should be ignored)
                        should_ignore = self._should_ignore_gap_near_ground_connections(
                            sample_pos, gnd_patterns, 
                            via_clearance_radius, pad_clearance_radius,
                            ignore_via_clearance_mm, ignore_pad_clearance_mm,
                            get_distance_func
                        )
                        
                        if not should_ignore:
                            gap_found = True
                            gap_position = sample_pos
                            self.log(f"    ❌ GAP FOUND at sample {i}/{num_samples}:")
                            self.log(f"       Position: ({pcbnew.ToMM(sample_x):.2f}, {pcbnew.ToMM(sample_y):.2f}) mm")
                        break
                
                if gap_found and gap_position:
                    # Create violation marker using centralized utility
                    violation_group = create_group_func(self.board, "GndPlane", net_name, violations+1)
                    
                    draw_marker_func(self.board, gap_position, violation_msg_no_gnd, self.marker_layer, violation_group)
                    violations += 1
                    self.log(f"    ✓ Violation marker created at ({pcbnew.ToMM(gap_position.x):.2f}, {pcbnew.ToMM(gap_position.y):.2f}) mm", force=True)
                else:
                    self.log(f"    ✓ No gaps found - ground plane continuous")
            
            # ========== PRIORITY 2: Check split plane crossing ==========
            if check_split_crossing:
                self.log(f"\n    --- Checking split plane crossing ---")
                split_violation = self._check_split_plane_crossing(
                    track, start, end, num_samples, layers_to_check,
                    all_zones_by_layer, gnd_patterns,
                    draw_marker_func, create_group_func, net_name
                )
                if split_violation > 0:
                    violations += split_violation
                    self.log(f"    ✓ {split_violation} split crossing violation(s) found", force=True)
                else:
                    self.log(f"    ✓ No split plane crossings")
            
            # Check clearance around trace
            if check_clearance:
                clearance_violation = False
                clearance_pos = None
                
                # Sample perpendicular to track for clearance check
                for i in range(num_samples + 1):
                    t = i / num_samples
                    sample_x = int(start.x + (end.x - start.x) * t)
                    sample_y = int(start.y + (end.y - start.y) * t)
                    
                    # Check points at clearance_zone distance perpendicular to track
                    dx = end.x - start.x
                    dy = end.y - start.y
                    length = math.sqrt(dx*dx + dy*dy)
                    
                    if length > 0:
                        # Perpendicular vector
                        perp_x = -dy / length * clearance_zone
                        perp_y = dx / length * clearance_zone
                        
                        # Check both sides (or just one if check_both_sides = false)
                        sides = [1, -1] if check_both else [1]
                        for side in sides:
                            check_x = int(sample_x + side * perp_x)
                            check_y = int(sample_y + side * perp_y)
                            check_pos = pcbnew.VECTOR2I(check_x, check_y)
                            
                            # Check if ground plane exists within clearance zone on any layer
                            # Use pre-filtered zones by layer for O(1) lookup
                            has_ground_nearby = False
                            for check_layer in layers_to_check:
                                # Only check zones on this specific layer (much faster)
                                for zone in ground_zones_by_layer.get(check_layer, []):
                                    if zone.HitTestFilledArea(check_layer, check_pos):
                                        has_ground_nearby = True
                                        break
                                if has_ground_nearby:
                                    break
                            
                            if not has_ground_nearby:
                                # Check if violation is near a via or pad (should be ignored)
                                should_ignore = self._should_ignore_gap_near_ground_connections(
                                    check_pos, gnd_patterns,
                                    via_clearance_radius, pad_clearance_radius,
                                    ignore_via_clearance_mm, ignore_pad_clearance_mm,
                                    get_distance_func
                                )
                                
                                if not should_ignore:
                                    clearance_violation = True
                                    clearance_pos = check_pos
                                break
                    
                    if clearance_violation:
                        break
                
                if clearance_violation and clearance_pos:
                    # Create violation marker using centralized utility
                    violation_group = create_group_func(self.board, "GndPlane", f"{net_name}_clearance", violations+1)
                    
                    # Draw marker at track position (not at clearance check point)
                    track_center_x = (start.x + end.x) // 2
                    track_center_y = (start.y + end.y) // 2
                    track_center = pcbnew.VECTOR2I(track_center_x, track_center_y)
                    
                    draw_marker_func(self.board, track_center, violation_msg_clearance, self.marker_layer, violation_group)
                    
                    # Draw arrow pointing to ground gap
                    draw_arrow_func(self.board, track_center, clearance_pos, "GND GAP", self.marker_layer, violation_group)
                    violations += 1
        
        # Clean up progress dialog
        if progress:
            progress.Destroy()
        
        # ========== PRIORITY 3: Check return via continuity ==========
        if check_return_vias:
            self.log("\n=== RETURN VIA CONTINUITY CHECK ===", force=True)
            return_via_violations = self._check_return_via_continuity(
                gnd_patterns, return_via_max_dist_mm,
                draw_marker_func, create_group_func, get_distance_func
            )
            violations += return_via_violations
            self.log(f"✓ Return via check complete: {return_via_violations} violations", force=True)
        
        return violations
    
    def _check_split_plane_crossing(self, track, start, end, num_samples, layers_to_check,
                                     all_zones_by_layer, gnd_patterns,
                                     draw_marker_func, create_group_func, net_name):
        """
        PRIORITY 2: Detect when a trace crosses from one reference plane to another (split crossing).
        
        This check identifies traces that cross splits between different reference planes
        (e.g., GND to VCC, or between two isolated GND pours). Such crossings create
        return path discontinuities and EMI issues.
        
        Key Design Insight (from user):
        - NO layer-to-plane mapping assumptions
        - Boards may use split planes on certain layers
        - Some designs use only ground alignment under specific signals
        - Some use double tracks for high-current paths (power LEDs, motors)
        
        Algorithm:
        1. Sample points along trace
        2. For each point, identify which zone(s) it's over (dynamically)
        3. Detect transitions from one zone to another (split crossing)
        4. Flag violations where trace crosses between different reference nets
        
        Args:
            track: PCB_TRACK object
            start: VECTOR2I start position
            end: VECTOR2I end position
            num_samples: int - number of sample points
            layers_to_check: list[int] - layer IDs to check
            all_zones_by_layer: dict[int, list[ZONE]] - all zones indexed by layer
            gnd_patterns: list[str] - ground net patterns (uppercase)
            draw_marker_func: Function to draw violation markers
            create_group_func: Function to create PCB groups
            net_name: str - signal net name
        
        Returns:
            int: Number of violations found
        """
        violations = 0
        prev_zone_net = None  # Track which zone we were over in previous sample
        prev_sample_pos = None
        split_msg = self.config.get('violation_message_split_crossing', 'SPLIT PLANE CROSSING')
        
        for i in range(num_samples + 1):
            t = i / num_samples
            sample_x = int(start.x + (end.x - start.x) * t)
            sample_y = int(start.y + (end.y - start.y) * t)
            sample_pos = pcbnew.VECTOR2I(sample_x, sample_y)
            
            # Find which zone(s) this point is over (dynamic discovery)
            current_zone_net = None
            current_zone_obj = None
            
            for check_layer in layers_to_check:
                for zone in all_zones_by_layer.get(check_layer, []):
                    if zone.HitTestFilledArea(check_layer, sample_pos):
                        current_zone_net = zone.GetNetname().upper()
                        current_zone_obj = zone
                        break
                if current_zone_net:
                    break
            
            # Check for split crossing
            if prev_zone_net is not None and current_zone_net is not None:
                if prev_zone_net != current_zone_net:
                    # Trace crossed from one reference plane to another!
                    self.log(f"    ❌ SPLIT CROSSING: {prev_zone_net} → {current_zone_net}")
                    self.log(f"       Position: ({pcbnew.ToMM(sample_x):.2f}, {pcbnew.ToMM(sample_y):.2f}) mm")
                    
                    # Create violation marker
                    violation_group = create_group_func(self.board, "GndPlaneSplit", net_name, violations+1)
                    
                    # Draw marker at crossing point
                    msg = f"{split_msg}: {prev_zone_net}→{current_zone_net}"
                    draw_marker_func(self.board, sample_pos, msg, self.marker_layer, violation_group)
                    violations += 1
            
            # Update tracking
            prev_zone_net = current_zone_net
            prev_sample_pos = sample_pos
        
        return violations
    
    def _check_return_via_continuity(self, gnd_patterns, max_distance_mm,
                                     draw_marker_func, create_group_func, get_distance_func):
        """
        PRIORITY 3: Check that signal vias changing layers have nearby ground vias.
        
        When a signal via transitions between layers, the return current must also
        transition. Without a nearby ground via, the return path has high impedance,
        causing EMI radiation and signal integrity issues.
        
        IPC-2221 / High-Speed Design Guidelines:
        - Return vias should be within 3mm (default) of signal vias
        - Closer is better: <1mm for high-speed (USB, Ethernet)
        - Multiple return vias for differential pairs
        
        Algorithm:
        1. Find all signal vias (non-ground nets)
        2. For each signal via, find nearest ground via
        3. Flag violation if distance > max_distance_mm
        
        Args:
            gnd_patterns: list[str] - ground net patterns (uppercase)
            max_distance_mm: float - maximum allowed distance
            draw_marker_func: Function to draw violation markers
            create_group_func: Function to create PCB groups
            get_distance_func: Function to calculate distance
        
        Returns:
            int: Number of violations found
        """
        violations = 0
        max_distance = pcbnew.FromMM(max_distance_mm)
        violation_msg = self.config.get('violation_message_no_return_via', 'NO RETURN VIA')
        
        # Collect all vias, categorized
        signal_vias = []
        ground_vias = []
        
        for track in self.board.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA):
                via_net = track.GetNetname().upper()
                is_ground = any(gnd in via_net for gnd in gnd_patterns)
                
                if is_ground:
                    ground_vias.append(track)
                else:
                    signal_vias.append(track)
        
        self.log(f"Found {len(signal_vias)} signal vias, {len(ground_vias)} ground vias")
        
        if not ground_vias:
            self.log("⚠️  No ground vias found - skipping return via check")
            return 0
        
        # Check each signal via for nearby ground via
        for via in signal_vias:
            via_pos = via.GetPosition()
            via_net = via.GetNetname()
            
            # Find nearest ground via
            min_dist = float('inf')
            nearest_gnd_via = None
            
            for gnd_via in ground_vias:
                gnd_pos = gnd_via.GetPosition()
                dist = get_distance_func(via_pos, gnd_pos)
                
                if dist < min_dist:
                    min_dist = dist
                    nearest_gnd_via = gnd_via
            
            # Check if violation
            if min_dist > max_distance:
                self.log(f"    ❌ Via on '{via_net}' has no return via within {max_distance_mm}mm (nearest: {pcbnew.ToMM(min_dist):.2f}mm)")
                
                # Create violation marker
                violation_group = create_group_func(self.board, "ReturnVia", via_net, violations+1)
                
                msg = f"{violation_msg}: {pcbnew.ToMM(min_dist):.1f}mm"
                draw_marker_func(self.board, via_pos, msg, self.marker_layer, violation_group)
                violations += 1
            else:
                self.log(f"    ✓ Via on '{via_net}' OK (return via {pcbnew.ToMM(min_dist):.2f}mm away)")
        
        return violations
    
    def _should_ignore_gap_near_ground_connections(self, pos, gnd_patterns, 
                                                    via_clearance_radius, pad_clearance_radius,
                                                    ignore_via_clearance_mm, ignore_pad_clearance_mm,
                                                    get_distance_func):
        """
        Check if a gap should be ignored because it's near a ground via or pad.
        
        This helper method consolidates the duplicate logic for checking if violations
        occur near ground connection points (which are expected to have gaps in the plane).
        
        Args:
            pos: VECTOR2I position to check
            gnd_patterns: list[str] - Ground net name patterns (uppercase)
            via_clearance_radius: int - Clearance radius around vias (in KiCad units)
            pad_clearance_radius: int - Clearance radius around pads (in KiCad units)
            ignore_via_clearance_mm: float - User config value (0 = disabled)
            ignore_pad_clearance_mm: float - User config value (0 = disabled)
            get_distance_func: Injected distance calculation function
        
        Returns:
            bool: True if gap should be ignored, False otherwise
        """
        if ignore_via_clearance_mm <= 0 and ignore_pad_clearance_mm <= 0:
            return False
        
        # Check pads
        if ignore_pad_clearance_mm > 0:
            for footprint in self.board.GetFootprints():
                for pad in footprint.Pads():
                    pad_pos = pad.GetPosition()
                    dist_to_pad = get_distance_func(pos, pad_pos)
                    
                    # Ignore if near ground pad
                    if dist_to_pad < pad_clearance_radius:
                        pad_net = pad.GetNetname().upper()
                        if any(gnd in pad_net for gnd in gnd_patterns):
                            self.log(f"    ⚠️  Gap near GND pad, ignoring")
                            return True
        
        # Check vias
        if ignore_via_clearance_mm > 0:
            for via_track in self.board.GetTracks():
                if isinstance(via_track, pcbnew.PCB_VIA):
                    via_pos = via_track.GetPosition()
                    dist_to_via = get_distance_func(pos, via_pos)
                    
                    if dist_to_via < via_clearance_radius:
                        via_net = via_track.GetNetname().upper()
                        if any(gnd in via_net for gnd in gnd_patterns):
                            self.log(f"    ⚠️  Gap near GND via, ignoring")
                            return True
        
        return False
    
    def get_adjacent_ground_layer(self, signal_layer):
        """
        Get the adjacent layer that typically contains ground plane.
        
        This method determines which layer to check for ground plane based on the
        signal layer and the board's layer stack. The heuristics are:
        - 2-layer: Return opposite layer
        - 4-layer: Assume stack F.Cu-GND-PWR-B.Cu, return In1.Cu for F.Cu, In2.Cu for B.Cu
        - 6+ layer: Return first inner layer for F.Cu, last inner layer for B.Cu
        
        Args:
            signal_layer: Layer ID of the signal trace
        
        Returns:
            int: Layer ID of adjacent ground plane layer, or None if not determinable
        """
        layer_count = self.board.GetCopperLayerCount()
        
        # For 2-layer boards
        if layer_count == 2:
            if signal_layer == pcbnew.F_Cu:
                return pcbnew.B_Cu
            elif signal_layer == pcbnew.B_Cu:
                return pcbnew.F_Cu
        
        # For 4-layer boards (typical: F.Cu-GND-PWR-B.Cu)
        elif layer_count == 4:
            if signal_layer == pcbnew.F_Cu:
                return pcbnew.In1_Cu  # Inner layer 1 (typically GND)
            elif signal_layer == pcbnew.B_Cu:
                return pcbnew.In2_Cu  # Inner layer 2 (typically PWR or GND)
        
        # For 6+ layer boards, assume next inner layer
        else:
            if signal_layer == pcbnew.F_Cu:
                return pcbnew.In1_Cu
            elif signal_layer == pcbnew.B_Cu:
                # Last inner layer
                return self.board.GetLayerID(f"In{layer_count-2}.Cu")
        
        return None
