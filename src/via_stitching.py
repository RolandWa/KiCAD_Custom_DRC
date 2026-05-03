"""
Via Stitching Verification Module for EMC Auditor Plugin
Ensures critical signal vias have nearby ground return vias for EMI reduction

This module is called by emc_auditor_plugin.py and reuses its utility functions.
Configuration is read from emc_rules.toml [via_stitching] section.

Author: EMC Auditor Plugin
Version: 1.0.0
Last Updated: 2026-02-12
"""

import pcbnew


class ViaStitchingChecker:
    """
    Handles via stitching verification for high-speed signals.
    
    Via stitching ensures that critical signal vias have nearby ground return vias
    to minimize EMI radiation and maintain signal integrity by providing a low-
    impedance return path for high-frequency currents.
    
    Standards reference:
    - IPC-2221: Generic Standard on Printed Board Design
    - High-Speed Digital Design: A Handbook of Black Magic (Howard Johnson)
    """
    
    def __init__(self, board, marker_layer, config, report_lines, verbose=True, auditor=None):
        """
        Initialize checker with board context and configuration.
        
        Args:
            board: pcbnew.BOARD instance
            marker_layer: KiCad layer ID for drawing violation markers
            config: Dictionary from emc_rules.toml [via_stitching] section
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
        
        # Results tracking
        self.violation_count = 0
    
    def check(self, draw_marker_func, draw_arrow_func, get_distance_func, log_func, create_group_func):
        """
        Main entry point - performs via stitching verification.
        
        Called from emc_auditor_plugin.py check_via_stitching() method.
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
        self.log = log_func  # Centralized logger from main plugin
        self.draw_marker = draw_marker_func
        self.draw_arrow = draw_arrow_func
        self.get_distance = get_distance_func
        
        self.log("\n=== VIA STITCHING CHECK START ===", force=True)
        
        # Parse configuration
        max_dist_mm = self.config.get('max_distance_mm', 2.0)
        max_dist = pcbnew.FromMM(max_dist_mm)
        critical_classes = self.config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        gnd_patterns = [p.upper() for p in self.config.get('ground_net_patterns', ['GND'])]
        violation_msg = self.config.get('violation_message', 'NO GND VIA')
        
        self.log(f"Max distance: {max_dist_mm} mm")
        self.log(f"Critical net classes: {critical_classes}")
        self.log(f"Ground patterns: {gnd_patterns}")
        
        # Get all vias from board
        tracks = self.board.GetTracks()
        vias = [t for t in tracks if isinstance(t, pcbnew.PCB_VIA)]
        
        # Filter critical vias (via Net Classes - preferred method)
        self.log("\n--- Scanning for Critical Vias ---")
        critical_vias = []
        seen_positions = {}  # Map position tuples to via objects to avoid duplicates
        
        for crit_class in critical_classes:
            # Use centralized get_nets_by_class utility
            nets_in_class = self.auditor.get_nets_by_class(self.board, crit_class)
            
            if nets_in_class:
                self.log(f"  ✓ Found Net Class '{crit_class}' with {len(nets_in_class)} net(s)")
                
                # Find vias on these nets
                for via in vias:
                    via_net = str(via.GetNetname())  # Explicit string conversion
                    if via_net in nets_in_class:
                        # Avoid duplicates using position as unique identifier
                        pos = via.GetPosition()
                        via_key = "{}_{}".format(pos.x, pos.y)  # String key, definitely hashable
                        
                        if via_key not in seen_positions:
                            seen_positions[via_key] = via
                            critical_vias.append(via)
                            via_class = str(via.GetNetClassName())  # Explicit string conversion
                            self.log(f"    Critical via: net='{via_net}', class='{via_class}'")
            else:
                # Fallback: Check if any vias have this class name in their net class string
                # (handles comma-separated class names)
                for via in vias:
                    via_class = str(via.GetNetClassName())  # Explicit string conversion
                    if crit_class in via_class:
                        # Avoid duplicates using position as unique identifier
                        pos = via.GetPosition()
                        via_key = "{}_{}".format(pos.x, pos.y)  # String key, definitely hashable
                        
                        if via_key not in seen_positions:
                            seen_positions[via_key] = via
                            critical_vias.append(via)
                            via_net = str(via.GetNetname())  # Explicit string conversion
                            self.log(f"    Critical via: net='{via_net}', class='{via_class}'")
        
        # Filter ground vias
        gnd_vias = []
        for v in vias:
            v_net = str(v.GetNetname()).upper()  # Explicit string conversion
            if any(pat in v_net for pat in gnd_patterns):
                gnd_vias.append(v)
        
        self.log(f"\n✓ Found {len(critical_vias)} critical via(s) and {len(gnd_vias)} ground via(s)", force=True)
        
        # Check each critical via for nearby ground via (only if critical vias exist)
        if critical_vias and gnd_vias:
            self.log("\n--- Checking Via Stitching ---")
            
            for cv in critical_vias:
                net_name = cv.GetNetname()
                pos = cv.GetPosition()
                self.log(f"\n>>> Checking via on net '{net_name}' at ({pcbnew.ToMM(pos.x):.2f}, {pcbnew.ToMM(pos.y):.2f}) mm")
                
                found = False
                nearest_dist = float('inf')
                nearest_gnd_via = None
                
                for gv in gnd_vias:
                    dist = self.get_distance(cv.GetPosition(), gv.GetPosition())
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest_gnd_via = gv
                    if dist <= max_dist:
                        found = True
                        self.log(f"    ✓ GND via found at {pcbnew.ToMM(dist):.2f} mm")
                        break
                
                if not found:
                    self.log(f"    ❌ NO GND VIA within {max_dist_mm} mm (nearest: {pcbnew.ToMM(nearest_dist):.2f} mm)", force=True)
                    
                    # Create violation group using centralized utility
                    self.violation_count += 1
                    violation_group = create_group_func(self.board, "Via", net_name, self.violation_count)
                    
                    # Draw marker at critical via location
                    self.draw_marker(
                        self.board,
                        cv.GetPosition(),
                        violation_msg,
                        self.marker_layer,
                        violation_group
                    )
                    
                    # Draw arrow to nearest ground via if exists
                    draw_arrow_to_nearest = self.config.get('draw_arrow_to_nearest_gnd', True)
                    if draw_arrow_to_nearest and nearest_gnd_via:
                        self.draw_arrow(
                            self.board,
                            cv.GetPosition(),
                            nearest_gnd_via.GetPosition(),
                            f"→ GND ({pcbnew.ToMM(nearest_dist):.1f}mm)",
                            self.marker_layer,
                            violation_group
                        )
                    
                    self.log(f"    ✓ Violation marker created", force=True)
        elif not critical_vias:
            self.log("⚠️  No critical vias found - skipping proximity check", force=True)
            self.log(f"Expected Net Classes: {critical_classes}", force=True)
        elif not gnd_vias:
            self.log("⚠️  No ground vias found - skipping proximity check", force=True)
            self.log(f"Expected patterns: {gnd_patterns}", force=True)
        
        # Check GND plane stitching density (if enabled)
        if self.config.get('check_gnd_plane_density', False):
            self._check_gnd_plane_stitch_density(gnd_vias, gnd_patterns, create_group_func)
        
        # Check board edge stitching (if enabled)
        if self.config.get('check_edge_stitching', False):
            self._check_board_edge_stitching(gnd_vias, gnd_patterns, create_group_func)
        
        self.log(f"\n=== VIA STITCHING CHECK COMPLETE: {self.violation_count} violation(s) ===", force=True)
        return self.violation_count
    
    def _check_gnd_plane_stitch_density(self, gnd_vias, gnd_patterns, create_group_func):
        """
        Check that GND copper zones have adequate via stitching density.
        
        Via stitching in GND planes reduces impedance, improves current distribution,
        and minimizes EMI radiation by providing low-inductance return paths.
        
        Args:
            gnd_vias: List of ground vias already filtered
            gnd_patterns: List of ground net name patterns (upper case)
            create_group_func: Function to create violation groups
        """
        self.log("\n--- Checking GND Plane Stitching Density ---", force=True)
        
        min_density = self.config.get('min_stitch_vias_per_cm2', 4.0)
        self.log(f"Minimum density: {min_density} vias/cm²")
        
        # Get all GND zones from board
        zones = self.board.Zones()
        gnd_zones = []
        
        for zone in zones:
            zone_net = str(zone.GetNetname()).upper()
            if any(pat in zone_net for pat in gnd_patterns):
                if zone.IsFilled():
                    gnd_zones.append(zone)
        
        self.log(f"Found {len(gnd_zones)} filled GND zone(s)")
        
        if not gnd_zones:
            self.log("⚠️  No filled GND zones found - skipping density check", force=True)
            return
        
        # Check density for each zone
        for zone in gnd_zones:
            zone_net = zone.GetNetname()
            
            # Get zone area in cm²
            area_internal = zone.GetFilledArea()  # Returns area in internal units²
            area_mm2 = area_internal / (pcbnew.FromMM(1) ** 2)
            area_cm2 = area_mm2 / 100.0
            
            if area_cm2 < 0.01:  # Skip tiny zones (< 0.01 cm² = 1 mm²)
                continue
            
            # Count vias inside this zone
            zone_layer = zone.GetLayer()
            vias_in_zone = 0
            
            for via in gnd_vias:
                via_pos = via.GetPosition()
                # Check if via is inside the filled zone area
                if zone.HitTestFilledArea(zone_layer, via_pos):
                    vias_in_zone += 1
            
            # Calculate actual density
            actual_density = vias_in_zone / area_cm2 if area_cm2 > 0 else 0
            
            self.log(f"\nZone '{zone_net}' on layer {self.board.GetLayerName(zone_layer)}:")
            self.log(f"  Area: {area_cm2:.2f} cm² ({area_mm2:.1f} mm²)")
            self.log(f"  Vias: {vias_in_zone}")
            self.log(f"  Density: {actual_density:.2f} vias/cm² (min: {min_density})")
            
            # Check if density is sufficient
            if actual_density < min_density:
                required_vias = int(area_cm2 * min_density)
                missing_vias = required_vias - vias_in_zone
                
                self.log(f"  ❌ INSUFFICIENT DENSITY (need {required_vias}, have {vias_in_zone}, missing {missing_vias})", force=True)
                
                # Create violation at zone center
                self.violation_count += 1
                zone_bbox = zone.GetBoundingBox()
                center_x = (zone_bbox.GetLeft() + zone_bbox.GetLeft() + zone_bbox.GetWidth()) // 2
                center_y = (zone_bbox.GetTop() + zone_bbox.GetTop() + zone_bbox.GetHeight()) // 2
                center_pos = pcbnew.VECTOR2I(center_x, center_y)
                
                violation_group = create_group_func(
                    self.board, "ViaDensity", zone_net, self.violation_count
                )
                
                self.draw_marker(
                    self.board,
                    center_pos,
                    f"LOW VIA DENSITY\n{actual_density:.1f}/{min_density} vias/cm²",
                    self.marker_layer,
                    violation_group
                )
            else:
                self.log(f"  ✓ Adequate density")
    
    def _check_board_edge_stitching(self, gnd_vias, gnd_patterns, create_group_func):
        """
        Check that board edges have adequate GND via stitching for EMI shielding.
        
        Board edge stitching helps contain EMI radiation by creating a "faraday cage"
        effect around the board perimeter.
        
        Args:
            gnd_vias: List of ground vias already filtered
            gnd_patterns: List of ground net name patterns (upper case)
            create_group_func: Function to create violation groups
        """
        self.log("\n--- Checking Board Edge Stitching ---", force=True)
        
        max_spacing_mm = self.config.get('max_edge_stitch_spacing_mm', 20.0)
        edge_margin_mm = self.config.get('edge_stitch_margin_mm', 2.0)
        
        self.log(f"Max spacing: {max_spacing_mm} mm")
        self.log(f"Edge margin: {edge_margin_mm} mm")
        
        max_spacing = pcbnew.FromMM(max_spacing_mm)
        edge_margin = pcbnew.FromMM(edge_margin_mm)
        
        # Get board bounding box
        bbox = self.board.GetBoardEdgesBoundingBox()
        
        # Define board edges (left, right, top, bottom)
        edges = {
            'left': (bbox.GetLeft(), bbox.GetTop(), bbox.GetLeft(), bbox.GetTop() + bbox.GetHeight()),
            'right': (bbox.GetLeft() + bbox.GetWidth(), bbox.GetTop(), 
                     bbox.GetLeft() + bbox.GetWidth(), bbox.GetTop() + bbox.GetHeight()),
            'top': (bbox.GetLeft(), bbox.GetTop(), bbox.GetLeft() + bbox.GetWidth(), bbox.GetTop()),
            'bottom': (bbox.GetLeft(), bbox.GetTop() + bbox.GetHeight(), 
                      bbox.GetLeft() + bbox.GetWidth(), bbox.GetTop() + bbox.GetHeight())
        }
        
        # Check each edge
        for edge_name, (x1, y1, x2, y2) in edges.items():
            self.log(f"\nChecking {edge_name} edge:")
            
            # Find vias near this edge
            edge_vias = []
            for via in gnd_vias:
                via_pos = via.GetPosition()
                
                # Calculate distance from via to edge line
                if edge_name in ['left', 'right']:
                    # Vertical edge
                    edge_x = x1
                    dist_to_edge = abs(via_pos.x - edge_x)
                    # Check if via is within margin and within edge bounds
                    if dist_to_edge <= edge_margin and y1 <= via_pos.y <= y2:
                        edge_vias.append((via, via_pos.y))  # Store position along edge
                else:
                    # Horizontal edge
                    edge_y = y1
                    dist_to_edge = abs(via_pos.y - edge_y)
                    # Check if via is within margin and within edge bounds
                    if dist_to_edge <= edge_margin and x1 <= via_pos.x <= x2:
                        edge_vias.append((via, via_pos.x))  # Store position along edge
            
            if not edge_vias:
                self.log(f"  ⚠️  No vias found near {edge_name} edge", force=True)
                continue
            
            # Sort vias by position along edge
            edge_vias.sort(key=lambda x: x[1])
            self.log(f"  Found {len(edge_vias)} via(s) near edge")
            
            # Check spacing between consecutive vias
            for i in range(len(edge_vias) - 1):
                via1, pos1 = edge_vias[i]
                via2, pos2 = edge_vias[i + 1]
                
                spacing = abs(pos2 - pos1)
                spacing_mm = pcbnew.ToMM(spacing)
                
                if spacing > max_spacing:
                    self.log(f"  ❌ GAP DETECTED: {spacing_mm:.1f} mm between vias (max: {max_spacing_mm} mm)", force=True)
                    
                    # Create violation at midpoint of gap
                    self.violation_count += 1
                    
                    if edge_name in ['left', 'right']:
                        mid_x = x1
                        mid_y = (pos1 + pos2) // 2
                    else:
                        mid_x = (pos1 + pos2) // 2
                        mid_y = y1
                    
                    mid_pos = pcbnew.VECTOR2I(mid_x, mid_y)
                    
                    violation_group = create_group_func(
                        self.board, "EdgeStitch", edge_name, self.violation_count
                    )
                    
                    self.draw_marker(
                        self.board,
                        mid_pos,
                        f"EDGE GAP\n{spacing_mm:.1f}mm > {max_spacing_mm}mm",
                        self.marker_layer,
                        violation_group
                    )
                else:
                    self.log(f"  ✓ Via spacing: {spacing_mm:.1f} mm")
            
            # Check distance from edge start/end to first/last via
            edge_length = abs(x2 - x1) if edge_name in ['top', 'bottom'] else abs(y2 - y1)
            if edge_vias:
                first_via_pos = edge_vias[0][1]
                last_via_pos = edge_vias[-1][1]
                
                start_edge = x1 if edge_name in ['top', 'bottom'] else y1
                end_edge = x2 if edge_name in ['top', 'bottom'] else y2
                
                start_gap = abs(first_via_pos - start_edge)
                end_gap = abs(last_via_pos - end_edge)
                
                if start_gap > max_spacing:
                    self.log(f"  ⚠️  Large gap at edge start: {pcbnew.ToMM(start_gap):.1f} mm", force=True)
                if end_gap > max_spacing:
                    self.log(f"  ⚠️  Large gap at edge end: {pcbnew.ToMM(end_gap):.1f} mm", force=True)


# Module metadata
__version__ = "1.1.0"
__author__ = "EMC Auditor Plugin"
__description__ = "Via stitching verification for EMI reduction and signal integrity"
