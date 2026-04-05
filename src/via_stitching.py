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
        
        if not critical_vias:
            self.log("⚠️  No critical vias found - check Net Class assignments in KiCad", force=True)
            self.log(f"Expected Net Classes: {critical_classes}", force=True)
            return 0
        
        if not gnd_vias:
            self.log("⚠️  No ground vias found - check ground net names", force=True)
            self.log(f"Expected patterns: {gnd_patterns}", force=True)
            return 0
        
        # Check each critical via for nearby ground via
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
        
        self.log(f"\n=== VIA STITCHING CHECK COMPLETE: {self.violation_count} violation(s) ===", force=True)
        return self.violation_count


# Module metadata
__version__ = "1.0.0"
__author__ = "EMC Auditor Plugin"
__description__ = "Via stitching verification for EMI reduction and signal integrity"
