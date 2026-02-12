"""
Decoupling Capacitor Verification Module for EMC Auditor Plugin
Ensures ICs have nearby decoupling capacitors on power pins for signal integrity

This module is called by emc_auditor_plugin.py and reuses its utility functions.
Configuration is read from emc_rules.toml [decoupling] section.

Author: EMC Auditor Plugin
Version: 1.0.0
Last Updated: 2026-02-12
"""

import pcbnew


class DecouplingChecker:
    """
    Handles decoupling capacitor proximity verification for IC power pins.
    
    Decoupling capacitors provide local energy storage and reduce power supply noise,
    ensuring stable operation of ICs by providing a low-impedance path for high-
    frequency noise currents. Proper placement is critical for signal integrity.
    
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
            config: Dictionary from emc_rules.toml [decoupling] section
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
    
    def log(self, msg, force=False):
        """Log message to console and report (only if verbose or force=True)"""
        if self.verbose or force:
            print(msg)
            if self.verbose:
                self.report_lines.append(msg)
    
    def check(self, draw_marker_func, draw_arrow_func, get_distance_func):
        """
        Main entry point - performs decoupling capacitor verification.
        
        Called from emc_auditor_plugin.py check_decoupling() method.
        Utility functions are injected to avoid code duplication.
        
        Args:
            draw_marker_func: Function(board, pos, msg, layer, group)
            draw_arrow_func: Function(board, start, end, label, layer, group)
            get_distance_func: Function(pos1, pos2) returns distance
        
        Returns:
            int: Number of violations found
        """
        # Store utility functions for reuse
        self.draw_marker = draw_marker_func
        self.draw_arrow = draw_arrow_func
        self.get_distance = get_distance_func
        
        self.log("\n=== DECOUPLING CAPACITOR CHECK START ===", force=True)
        
        # Parse configuration
        max_dist_mm = self.config.get('max_distance_mm', 3.0)
        max_dist = pcbnew.FromMM(max_dist_mm)
        ic_prefixes = self.config.get('ic_reference_prefixes', ['U'])
        cap_prefixes = self.config.get('capacitor_reference_prefixes', ['C'])
        power_patterns = [p.upper() for p in self.config.get('power_net_patterns', ['VCC', 'VDD'])]
        violation_msg_template = self.config.get('violation_message', 'CAP TOO FAR ({distance:.1f}mm)')
        draw_arrow = self.config.get('draw_arrow_to_nearest_cap', True)
        show_label = self.config.get('show_capacitor_label', True)
        
        self.log(f"Max distance: {max_dist_mm} mm")
        self.log(f"IC prefixes: {ic_prefixes}")
        self.log(f"Capacitor prefixes: {cap_prefixes}")
        self.log(f"Power net patterns: {power_patterns}")
        
        # Scan all ICs
        for footprint in self.board.GetFootprints():
            ref = str(footprint.GetReference())
            if any(ref.startswith(prefix) for prefix in ic_prefixes):
                self.log(f"\n>>> Found IC: {ref}")
                
                # Check each power pad
                for pad in footprint.Pads():
                    net_name = str(pad.GetNetname()).upper()
                    power_net = str(pad.GetNetname())  # Get actual net name for matching
                    
                    if any(pat in net_name for pat in power_patterns):
                        pad_pos = pad.GetPosition()
                        pad_x_mm = pcbnew.ToMM(pad_pos.x)
                        pad_y_mm = pcbnew.ToMM(pad_pos.y)
                        self.log(f"    Checking power pad '{power_net}' at ({pad_x_mm:.2f}, {pad_y_mm:.2f}) mm")
                        
                        best_dist = float('inf')
                        nearest_cap_pos = None
                        nearest_cap_ref = None
                        
                        # Find nearest capacitor CONNECTED TO THE SAME POWER NET
                        for cap in self.board.GetFootprints():
                            cap_ref = str(cap.GetReference())
                            if any(cap_ref.startswith(prefix) for prefix in cap_prefixes):
                                # Check if capacitor is connected to this power net
                                cap_connected = False
                                for cap_pad in cap.Pads():
                                    if str(cap_pad.GetNetname()) == power_net:
                                        cap_connected = True
                                        break
                                
                                # Only consider capacitors on the same power net
                                if cap_connected:
                                    d = self.get_distance(pad.GetPosition(), cap.GetPosition())
                                    if d < best_dist:
                                        best_dist = d
                                        nearest_cap_pos = cap.GetPosition()
                                        nearest_cap_ref = cap_ref
                        
                        # Log result of capacitor search
                        dist_mm = pcbnew.ToMM(best_dist) if best_dist != float('inf') else float('inf')
                        if best_dist <= max_dist:
                            self.log(f"        ✓ Nearest capacitor ({nearest_cap_ref}): {dist_mm:.2f} mm - OK")
                        else:
                            self.log(f"        ❌ Nearest capacitor ({nearest_cap_ref if nearest_cap_ref else 'NONE'}): {dist_mm:.2f} mm - EXCEEDS {max_dist_mm} mm limit")
                        
                        # If violation found, create individual group and draw markers
                        if best_dist > max_dist:
                            # Create violation group
                            self.violation_count += 1
                            violation_group = pcbnew.PCB_GROUP(self.board)
                            violation_group.SetName(f"EMC_Decap_{ref}_{power_net}")
                            self.board.Add(violation_group)
                            
                            dist_mm = pcbnew.ToMM(best_dist)
                            msg = violation_msg_template.format(distance=dist_mm)
                            self.draw_marker(
                                self.board,
                                pad.GetPosition(),
                                msg,
                                self.marker_layer,
                                violation_group
                            )
                            pad_x_mm = pcbnew.ToMM(pad.GetPosition().x)
                            pad_y_mm = pcbnew.ToMM(pad.GetPosition().y)
                            self.log(f"        ✓ Violation marker created at ({pad_x_mm:.2f}, {pad_y_mm:.2f}) mm", force=True)
                            
                            # Draw arrow showing where the nearest capacitor is
                            if draw_arrow and nearest_cap_pos:
                                label = f"→ {nearest_cap_ref}" if show_label else ""
                                self.draw_arrow(
                                    self.board,
                                    pad.GetPosition(),
                                    nearest_cap_pos,
                                    label,
                                    self.marker_layer,
                                    violation_group
                                )
        
        self.log(f"\n=== DECOUPLING CHECK COMPLETE: {self.violation_count} violation(s) ===", force=True)
        return self.violation_count


# Module metadata
__version__ = "1.0.0"
__author__ = "EMC Auditor Plugin"
__description__ = "Decoupling capacitor proximity verification for signal integrity"
