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
        self.create_group = None
        
        # Results tracking
        self.violation_count = 0
        self.warning_count = 0
    
    def check(self, draw_marker_func, draw_arrow_func, get_distance_func, log_func, create_group_func):
        """
        Main entry point - performs decoupling capacitor verification.
        
        Called from emc_auditor_plugin.py check_decoupling() method.
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
        self.create_group = create_group_func
        
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
        
        # Package type and via checking configuration
        prefer_smd = self.config.get('prefer_smd_capacitors', True)
        non_smd_value_threshold_uf = self.config.get('non_smd_value_threshold_uf', 22.0)
        check_via_count = self.config.get('check_via_count', True)
        min_vias_per_cap = self.config.get('min_vias_per_capacitor', 2)
        via_search_radius_mm = self.config.get('via_search_radius_mm', 2.0)
        
        self.log(f"Max distance: {max_dist_mm} mm")
        self.log(f"IC prefixes: {ic_prefixes}")
        self.log(f"Capacitor prefixes: {cap_prefixes}")
        self.log(f"Power net patterns: {power_patterns}")
        self.log(f"Prefer SMD capacitors: {prefer_smd}")
        self.log(f"Non-SMD threshold: {non_smd_value_threshold_uf} µF")
        self.log(f"Via count check: {check_via_count} (min {min_vias_per_cap} vias)")
        
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
                        nearest_cap_fp = None
                        
                        # Find nearest capacitor CONNECTED TO THE SAME POWER NET
                        # Prioritize SMD capacitors if configured
                        smd_candidates = []
                        tht_candidates = []
                        
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
                                    is_smd = self._is_smd_footprint(cap)
                                    
                                    if prefer_smd and is_smd:
                                        smd_candidates.append((d, cap, cap_ref))
                                    else:
                                        tht_candidates.append((d, cap, cap_ref))
                        
                        # Select nearest capacitor (prioritize SMD if configured)
                        if prefer_smd and smd_candidates:
                            smd_candidates.sort(key=lambda x: x[0])
                            best_dist, nearest_cap_fp, nearest_cap_ref = smd_candidates[0]
                            nearest_cap_pos = nearest_cap_fp.GetPosition()
                        elif tht_candidates or smd_candidates:
                            all_candidates = smd_candidates + tht_candidates
                            all_candidates.sort(key=lambda x: x[0])
                            best_dist, nearest_cap_fp, nearest_cap_ref = all_candidates[0]
                            nearest_cap_pos = nearest_cap_fp.GetPosition()
                        
                        # Log result of capacitor search
                        dist_mm = pcbnew.ToMM(best_dist) if best_dist != float('inf') else float('inf')
                        if best_dist <= max_dist:
                            cap_info = f"{nearest_cap_ref}"
                            if nearest_cap_fp:
                                is_smd = self._is_smd_footprint(nearest_cap_fp)
                                cap_info += f" ({'SMD' if is_smd else 'THT'})"
                            self.log(f"        ✓ Nearest capacitor ({cap_info}): {dist_mm:.2f} mm - OK")
                            
                            # Check via count if enabled
                            if check_via_count and nearest_cap_fp:
                                via_count = self._count_vias_near_capacitor(nearest_cap_fp, via_search_radius_mm)
                                if via_count < min_vias_per_cap:
                                    self.warning_count += 1
                                    warning_group = self.create_group(self.board, "DecapViaWarn", nearest_cap_ref, None)
                                    warning_msg = f"⚠ LOW VIA COUNT\n{nearest_cap_ref}\n{via_count}/{min_vias_per_cap} vias"
                                    self.draw_marker(
                                        self.board,
                                        nearest_cap_fp.GetPosition(),
                                        warning_msg,
                                        self.marker_layer,
                                        warning_group
                                    )
                                    self.log(f"        ⚠ Warning: Only {via_count} via(s) near capacitor (min {min_vias_per_cap})")
                                else:
                                    self.log(f"        ✓ Via count OK: {via_count} via(s)")
                        else:
                            self.log(f"        ❌ Nearest capacitor ({nearest_cap_ref if nearest_cap_ref else 'NONE'}): {dist_mm:.2f} mm - EXCEEDS {max_dist_mm} mm limit")
                        
                        # If violation found, create individual group and draw markers
                        if best_dist > max_dist:
                            # Check if nearest cap is non-SMD large capacitor (warning instead of error)
                            is_warning = False
                            if nearest_cap_fp and not self._is_smd_footprint(nearest_cap_fp):
                                cap_value_uf = self._get_capacitor_value_uf(nearest_cap_fp)
                                if cap_value_uf is not None and cap_value_uf >= non_smd_value_threshold_uf:
                                    is_warning = True
                                    self.warning_count += 1
                                    self.log(f"        ⚠ Warning: Non-SMD bulk cap ({cap_value_uf:.1f}µF) - acceptable for large values")
                            
                            if is_warning:
                                # Create warning marker (yellow)
                                warning_group = self.create_group(self.board, "DecapWarn", f"{ref}_{power_net}", None)
                                dist_mm = pcbnew.ToMM(best_dist)
                                msg = f"⚠ BULK CAP FAR\n({dist_mm:.1f}mm)\nTHT OK >22µF"
                                self.draw_marker(
                                    self.board,
                                    pad.GetPosition(),
                                    msg,
                                    self.marker_layer,
                                    warning_group
                                )
                            else:
                                # Create error violation
                                self.violation_count += 1
                                violation_group = self.create_group(self.board, "Decap", f"{ref}_{power_net}", None)
                                
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
                                group_to_use = warning_group if is_warning else violation_group
                                self.draw_arrow(
                                    self.board,
                                    pad.GetPosition(),
                                    nearest_cap_pos,
                                    label,
                                    self.marker_layer,
                                    group_to_use
                                )
        
        self.log(f"\n=== DECOUPLING CHECK COMPLETE: {self.violation_count} violation(s), {self.warning_count} warning(s) ===", force=True)
        return self.violation_count
    
    def _is_smd_footprint(self, footprint):
        """
        Determine if a footprint is SMD (Surface Mount Device) or THT (Through-Hole).
        
        Args:
            footprint: pcbnew.FOOTPRINT instance
            
        Returns:
            bool: True if SMD, False if THT
        """
        # Check pad attributes - SMD pads have no drill hole
        for pad in footprint.Pads():
            # If any pad has a drill hole, it's THT
            drill_size = pad.GetDrillSize()
            if drill_size.x > 0 or drill_size.y > 0:
                return False
        
        # All pads are surface mount (no drill holes)
        return True
    
    def _count_vias_near_capacitor(self, cap_footprint, search_radius_mm):
        """
        Count vias within search radius of capacitor pads.
        
        Args:
            cap_footprint: pcbnew.FOOTPRINT instance of capacitor
            search_radius_mm: Search radius in millimeters
            
        Returns:
            int: Number of vias found near capacitor
        """
        search_radius = pcbnew.FromMM(search_radius_mm)
        via_count = 0
        
        # Get capacitor pad positions
        cap_positions = [pad.GetPosition() for pad in cap_footprint.Pads()]
        
        # Search for vias near any capacitor pad
        for track in self.board.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA):
                via_pos = track.GetPosition()
                
                # Check if via is within search radius of any cap pad
                for cap_pos in cap_positions:
                    distance = self.get_distance(via_pos, cap_pos)
                    if distance <= search_radius:
                        via_count += 1
                        break  # Count each via only once
        
        return via_count
    
    def _get_capacitor_value_uf(self, footprint):
        """
        Extract capacitor value in microfarads from footprint properties.
        
        Args:
            footprint: pcbnew.FOOTPRINT instance
            
        Returns:
            float: Capacitor value in microfarads, or None if not parseable
        """
        import re
        
        # Try to get value from Value field
        try:
            value_field = footprint.GetValue()
            value_str = str(value_field)
            
            # Parse various formats: "100nF", "0.1uF", "22µF", "100uF"
            # Extract number and unit (case-insensitive)
            # Note: µ can be either U+00B5 (micro sign) or U+03BC (Greek mu)
            match = re.match(r'([0-9.]+)\s*(p|n|u|µ|μ)?f', value_str, re.IGNORECASE)
            if match:
                number = float(match.group(1))
                prefix = match.group(2)
                
                # Normalize prefix - convert µ/μ BEFORE uppercasing
                # Note: µ (U+00B5 micro sign) .upper() becomes Μ (U+039C Greek uppercase mu)
                # So we must replace before calling .upper()
                if prefix:
                    prefix = prefix.replace('µ', 'u').replace('μ', 'u')  # Both micro variants -> u
                    prefix = prefix.upper()  # Now safe to uppercase
                else:
                    prefix = ''  # Just "F" with no prefix
                
                # Convert to microfarads based on prefix
                if prefix == 'P':
                    return number / 1_000_000  # pF to µF
                elif prefix == 'N':
                    return number / 1_000  # nF to µF
                elif prefix == 'U':
                    return number  # Already in µF
                elif prefix == '':
                    return number * 1_000_000  # F to µF
        except Exception:
            pass
        
        return None


# Module metadata
__version__ = "1.0.0"
__author__ = "EMC Auditor Plugin"
__description__ = "Decoupling capacitor proximity verification for signal integrity"
