"""
EMI Filtering Verification Module for EMC Auditor Plugin
Checks interface connectors (USB, Ethernet, CAN, etc.) for proper EMI filtering

This module is called by emc_auditor_plugin.py and reuses its utility functions.
Configuration is read from emc_rules.toml [emi_filtering] section.

Author: EMC Auditor Plugin
Version: 1.0.0
Last Updated: 2026-02-12
"""

import pcbnew
import math


class EMIFilteringChecker:
    """
    Handles EMI filtering verification on interface connectors.
    
    EMI filters prevent electromagnetic interference on external connections,
    protecting both the device and connected equipment. Different interface
    types require different filter topologies (LC, Pi, T, differential).
    
    Standards reference:
    - CISPR 32: Electromagnetic compatibility of multimedia equipment
    - IEC 61000-4-6: Immunity to conducted disturbances
    - USB 2.0/3.0: EMI requirements for USB interfaces
    - IEEE 802.3: Ethernet PHY filtering requirements
    """
    
    def __init__(self, board, marker_layer, config, report_lines, verbose=True, auditor=None):
        """
        Initialize checker with board context and configuration.
        
        Args:
            board: pcbnew.BOARD instance
            marker_layer: KiCad layer ID for drawing violation markers
            config: Dictionary from emc_rules.toml [emi_filtering] section
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
        Main entry point - performs EMI filtering verification.
        
        Called from emc_auditor_plugin.py check_emi_filtering() method.
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
        
        self.log("\n=== EMI FILTERING CHECK START ===", force=True)
        
        # Parse configuration
        connector_prefix = self.config.get('connector_prefix', 'J')
        filter_prefixes = self.config.get('filter_component_prefixes', ['R', 'L', 'FB', 'C', 'D'])
        max_distance_mm = self.config.get('max_filter_distance_mm', 10.0)
        min_filter_type = self.config.get('min_filter_type', 'simple')
        violation_msg = self.config.get('violation_message', 'MISSING EMI FILTER')
        
        max_distance = pcbnew.FromMM(max_distance_mm)
        
        self.log(f"Connector prefix: '{connector_prefix}'")
        self.log(f"Filter component prefixes: {filter_prefixes}")
        self.log(f"Maximum filter distance: {max_distance_mm} mm")
        self.log(f"Minimum required filter type: {min_filter_type}")
        
        # Step 1: Find all connectors with specified prefix
        self.log("\n--- Scanning for connectors ---")
        connectors = self._find_connectors(connector_prefix)
        self.log(f"Found {len(connectors)} connector(s) with prefix '{connector_prefix}'")
        
        if not connectors:
            self.log("No connectors found - check complete", force=True)
            return 0
        
        # Step 2: For each connector, detect interface type and check for EMI filtering
        for conn_ref, conn_fp in connectors:
            self.log(f"\n--- Checking connector {conn_ref} ---")
            conn_pos = conn_fp.GetPosition()
            
            # Detect interface type from reference or footprint name
            interface_type = self._detect_interface_type(conn_ref, conn_fp)
            self.log(f"Interface type: {interface_type}")
            
            # Get all signal pads from connector (exclude GND, VCC, etc.)
            signal_pads = self._get_signal_pads(conn_fp)
            self.log(f"Found {len(signal_pads)} signal pad(s)")
            
            if not signal_pads:
                self.log("  ⚠️  No signal pads found (all GND/VCC?) - skipping")
                continue
            
            # Step 3: Check EMI filter on each signal line and track per-pad results
            pad_results = []
            
            for pad in signal_pads:
                net = pad.GetNet()
                if not net:
                    continue
                
                net_name = str(net.GetNetname())
                pad_num = str(pad.GetNumber())
                self.log(f"  Checking net '{net_name}' on pad {pad_num}")
                
                # Find filter components on this net (improved algorithm)
                filter_result = self._classify_filter_topology_improved(
                    net, conn_pos, max_distance, filter_prefixes
                )
                
                if filter_result:
                    filter_type, distance, topology_description = filter_result
                    self.log(f"    Found filter: {filter_type}")
                    self.log(f"    Topology: {topology_description}")
                    self.log(f"    Distance to first component: {pcbnew.ToMM(distance):.2f} mm")
                    
                    # Check if this filter meets requirement
                    filter_sufficient = self._check_filter_requirement(filter_type, min_filter_type)
                    pad_results.append((pad, filter_type, distance, topology_description, filter_sufficient))
                    
                    if filter_sufficient:
                        self.log(f"    ✓ Filter OK: {filter_type} at {pcbnew.ToMM(distance):.2f} mm")
                    else:
                        self.log(f"    ❌ VIOLATION: Filter type '{filter_type}' insufficient (need '{min_filter_type}')", force=True)
                else:
                    self.log(f"    ❌ VIOLATION: No EMI filter found within {max_distance_mm} mm", force=True)
                    pad_results.append((pad, None, float('inf'), None, False))
            
            # Step 4: Create markers for each pad with violations
            for pad, filter_type, distance, topology, sufficient in pad_results:
                if not sufficient:
                    self.violation_count += 1
                    pad_pos = pad.GetPosition()
                    pad_num = str(pad.GetNumber())
                    net_name = str(pad.GetNet().GetNetname()) if pad.GetNet() else "NC"
                    
                    if filter_type is None:
                        # No filter found - use centralized utility
                        violation_group = create_group_func(self.board, "EMI", f"{conn_ref}_Pad{pad_num}_NoFilter", None)
                        
                        marker_text = f"{violation_msg}\n({interface_type})"
                        self.draw_marker(self.board, pad_pos, marker_text, self.marker_layer, violation_group)
                    else:
                        # Insufficient filter - use centralized utility
                        violation_group = create_group_func(self.board, "EMI", f"{conn_ref}_Pad{pad_num}_WeakFilter", None)
                        
                        marker_text = f"WEAK FILTER\n({filter_type}<{min_filter_type})"
                        self.draw_marker(self.board, pad_pos, marker_text, self.marker_layer, violation_group)
        
        self.log(f"\n=== EMI FILTERING CHECK COMPLETE: {self.violation_count} violation(s) ===", force=True)
        return self.violation_count
    
    def _find_connectors(self, prefix):
        """Find all footprints with reference starting with specified prefix (e.g., 'J')"""
        connectors = []
        for fp in self.board.GetFootprints():
            ref = str(fp.GetReference())
            if ref.startswith(prefix):
                connectors.append((ref, fp))
        return connectors
    
    def _detect_interface_type(self, ref, footprint):
        """Detect interface type from reference or footprint name"""
        ref_upper = ref.upper()
        
        # Get footprint name - convert UTF8 to string
        try:
            fp_name = str(footprint.GetFPID().GetLibItemName()).upper()
        except:
            fp_name = ""
        
        # Check common interface patterns
        if 'USB' in ref_upper or 'USB' in fp_name:
            return 'USB'
        elif 'ETH' in ref_upper or 'RJ45' in fp_name or 'ETHERNET' in fp_name:
            return 'Ethernet'
        elif 'HDMI' in ref_upper or 'HDMI' in fp_name:
            return 'HDMI'
        elif 'CAN' in ref_upper:
            return 'CAN'
        elif 'RS485' in ref_upper or 'RS-485' in ref_upper:
            return 'RS485'
        elif 'RS232' in ref_upper or 'RS-232' in ref_upper:
            return 'RS232'
        else:
            return 'Unknown'
    
    def _get_signal_pads(self, footprint):
        """Get signal pads from connector (exclude GND, VCC, shield, etc.)"""
        signal_pads = []
        
        ground_patterns = ['GND', 'GROUND', 'VSS', 'PGND', 'AGND', 'DGND', 'SHIELD', 'SH']
        power_patterns = ['VCC', 'VDD', 'PWR', '3V3', '5V', '1V8', '2V5', '12V', '+3V3', '+5V', '+', 'VBUS']
        
        for pad in footprint.Pads():
            net = pad.GetNet()
            if not net:
                continue
            
            net_name = str(net.GetNetname()).upper()
            
            # Exclude ground and power nets
            is_ground = any(pattern in net_name for pattern in ground_patterns)
            is_power = any(pattern in net_name for pattern in power_patterns)
            
            if not is_ground and not is_power:
                signal_pads.append(pad)
        
        return signal_pads
    
    def _classify_filter_topology_improved(self, net, connector_pos, max_distance, prefixes):
        """Improved filter topology detection with series/shunt analysis"""
        # Find first component within max_distance
        first_component = self._find_first_filter_component(net, connector_pos, max_distance, prefixes)
        
        if not first_component:
            return None
        
        first_ref, first_fp, first_distance = first_component
        
        # Find all filter components on this net
        all_filter_components = []
        for fp in self.board.GetFootprints():
            ref = str(fp.GetReference())
            
            if not any(ref.startswith(prefix) for prefix in prefixes):
                continue
            
            component_on_net = False
            for pad in fp.Pads():
                if pad.GetNet() and pad.GetNet().GetNetCode() == net.GetNetCode():
                    component_on_net = True
                    break
            
            if component_on_net:
                comp_pos = fp.GetPosition()
                distance = math.sqrt(
                    (comp_pos.x - connector_pos.x)**2 + 
                    (comp_pos.y - connector_pos.y)**2
                )
                all_filter_components.append((ref, fp, distance))
        
        if not all_filter_components:
            return None
        
        # Analyze each component
        component_analysis = []
        series_components = []
        shunt_components = []
        
        for ref, fp, distance in all_filter_components:
            comp_type, net_info = self._analyze_component_placement(fp, net)
            component_analysis.append({
                'ref': ref,
                'type': comp_type,
                'component_class': ref[0] if ref else '?',
                'distance': distance,
                'nets': net_info
            })
            
            if comp_type == 'series':
                series_components.append(ref)
            elif comp_type == 'shunt':
                shunt_components.append(ref)
        
        # Sort by distance
        component_analysis.sort(key=lambda x: x['distance'])
        
        # Detect differential pair filters
        diff_pair_filter = self._detect_differential_pair_filter(net, connector_pos, max_distance)
        
        # Classify topology
        filter_type, topology_desc = self._classify_topology_from_analysis(
            component_analysis, series_components, shunt_components, diff_pair_filter
        )
        
        return (filter_type, first_distance, topology_desc)
    
    def _find_first_filter_component(self, net, connector_pos, max_distance, prefixes):
        """Find the first filter component within max_distance of connector"""
        nearest_component = None
        nearest_distance = float('inf')
        
        for fp in self.board.GetFootprints():
            ref = str(fp.GetReference())
            
            if not any(ref.startswith(prefix) for prefix in prefixes):
                continue
            
            component_on_net = False
            for pad in fp.Pads():
                if pad.GetNet() and pad.GetNet().GetNetCode() == net.GetNetCode():
                    component_on_net = True
                    break
            
            if not component_on_net:
                continue
            
            comp_pos = fp.GetPosition()
            distance = math.sqrt(
                (comp_pos.x - connector_pos.x)**2 + 
                (comp_pos.y - connector_pos.y)**2
            )
            
            if distance <= max_distance and distance < nearest_distance:
                nearest_component = (ref, fp, distance)
                nearest_distance = distance
        
        return nearest_component
    
    def _analyze_component_placement(self, footprint, signal_net):
        """Determine if component is series (in-line) or shunt (to GND/power)"""
        pads = list(footprint.Pads())
        
        if len(pads) < 2:
            return ('unknown', {})
        
        pad_nets = []
        for pad in pads:
            net = pad.GetNet()
            if net:
                pad_nets.append(str(net.GetNetname()))
            else:
                pad_nets.append('NC')
        
        ground_patterns = self.config.get('ground_patterns', ['GND', 'GROUND', 'VSS', 'AGND', 'DGND', 'PGND'])
        power_patterns = self.config.get('power_patterns', ['VCC', 'VDD', 'PWR', '+', 'VBUS', '3V3', '5V'])
        gnd_power_patterns = ground_patterns + power_patterns
        
        signal_net_name = str(signal_net.GetNetname())
        signal_net_count = pad_nets.count(signal_net_name)
        
        has_gnd_power = any(
            any(pattern in net_name.upper() for pattern in gnd_power_patterns)
            for net_name in pad_nets if net_name != 'NC'
        )
        
        if signal_net_count >= 1 and has_gnd_power:
            return ('shunt', {'type': 'shunt', 'nets': pad_nets})
        elif signal_net_count >= 1 and not has_gnd_power:
            return ('series', {'type': 'series', 'nets': pad_nets})
        else:
            return ('unknown', {'type': 'unknown', 'nets': pad_nets})
    
    def _detect_differential_pair_filter(self, net, connector_pos, max_distance):
        """Detect common-mode choke or differential pair filter"""
        net_name = str(net.GetNetname())
        
        diff_config = self.config.get('differential_pairs', {})
        diff_patterns = diff_config.get('patterns', [
            ['_P', '_N'], ['_p', '_n'], ['+', '-'],
            ['DP', 'DM'], ['dp', 'dm'],
            ['TXP', 'TXN'], ['txp', 'txn'],
            ['RXP', 'RXN'], ['rxp', 'rxn']
        ])
        diff_patterns = [tuple(pair) for pair in diff_patterns]
        
        pair_net = None
        for pos_suffix, neg_suffix in diff_patterns:
            if pos_suffix in net_name:
                pair_net_name = net_name.replace(pos_suffix, neg_suffix)
                pair_net = self.board.FindNet(pair_net_name)
                if pair_net:
                    break
            elif neg_suffix in net_name:
                pair_net_name = net_name.replace(neg_suffix, pos_suffix)
                pair_net = self.board.FindNet(pair_net_name)
                if pair_net:
                    break
        
        if not pair_net:
            return None
        
        min_pins = diff_config.get('min_common_mode_choke_pins', 4)
        component_classes = self.config.get('component_classes', {})
        inductor_prefixes = component_classes.get('inductor_prefixes', ['L', 'FB'])
        capacitor_prefixes = component_classes.get('capacitor_prefixes', ['C'])
        
        # Look for common-mode choke
        for fp in self.board.GetFootprints():
            ref = str(fp.GetReference())
            
            if not any(ref.startswith(prefix) for prefix in inductor_prefixes):
                continue
            
            pads = list(fp.Pads())
            if len(pads) < min_pins:
                continue
            
            comp_pos = fp.GetPosition()
            distance = math.sqrt(
                (comp_pos.x - connector_pos.x)**2 + 
                (comp_pos.y - connector_pos.y)**2
            )
            
            if distance > max_distance:
                continue
            
            nets_on_component = set()
            for pad in pads:
                pad_net = pad.GetNet()
                if pad_net:
                    nets_on_component.add(pad_net.GetNetCode())
            
            if net.GetNetCode() in nets_on_component and pair_net.GetNetCode() in nets_on_component:
                return {
                    'ref': ref,
                    'type': 'common_mode_choke',
                    'net1': net_name,
                    'net2': str(pair_net.GetNetname()),
                    'distance': distance
                }
        
        # Look for common-mode capacitor
        for fp in self.board.GetFootprints():
            ref = str(fp.GetReference())
            
            if not any(ref.startswith(prefix) for prefix in capacitor_prefixes):
                continue
            
            pads = list(fp.Pads())
            if len(pads) != 2:
                continue
            
            comp_pos = fp.GetPosition()
            distance = math.sqrt(
                (comp_pos.x - connector_pos.x)**2 + 
                (comp_pos.y - connector_pos.y)**2
            )
            
            if distance > max_distance:
                continue
            
            pad_nets = []
            for pad in pads:
                pad_net = pad.GetNet()
                if pad_net:
                    pad_nets.append(pad_net.GetNetCode())
            
            if len(pad_nets) == 2:
                if ((net.GetNetCode() in pad_nets and pair_net.GetNetCode() in pad_nets) and
                    (pad_nets[0] != pad_nets[1])):
                    return {
                        'ref': ref,
                        'type': 'common_mode_capacitor',
                        'net1': net_name,
                        'net2': str(pair_net.GetNetname()),
                        'distance': distance
                    }
        
        return None
    
    def _classify_line_filter_type(self, line_components, inductor_prefixes, capacitor_prefixes, resistor_prefixes):
        """Classify filter type for individual differential line components"""
        if not line_components:
            return 'simple'
        
        has_series_L = any(
            any(comp['ref'].startswith(prefix) for prefix in inductor_prefixes)
            for comp in line_components if comp['type'] == 'series'
        )
        has_series_R = any(
            any(comp['ref'].startswith(prefix) for prefix in resistor_prefixes)
            for comp in line_components if comp['type'] == 'series'
        )
        has_shunt_C = any(
            any(comp['ref'].startswith(prefix) for prefix in capacitor_prefixes)
            for comp in line_components if comp['type'] == 'shunt'
        )
        
        series_count = sum(1 for comp in line_components if comp['type'] == 'series')
        shunt_count = sum(1 for comp in line_components if comp['type'] == 'shunt')
        
        # Pi filter
        if shunt_count >= 2 and series_count >= 1 and (has_series_L or has_series_R):
            if (len(line_components) >= 3 and 
                line_components[0]['type'] == 'shunt' and 
                line_components[1]['type'] == 'series' and 
                line_components[2]['type'] == 'shunt'):
                return 'Pi' if has_series_L else 'RC'
        
        # T filter
        if series_count >= 2 and shunt_count >= 1 and has_shunt_C:
            if (len(line_components) >= 3 and 
                line_components[0]['type'] == 'series' and 
                line_components[1]['type'] == 'shunt' and 
                line_components[2]['type'] == 'series'):
                return 'T' if has_series_L else 'RC'
        
        if has_series_L and has_shunt_C:
            return 'LC'
        if has_series_R and has_shunt_C:
            return 'RC'
        if has_series_L:
            return 'L'
        if has_shunt_C:
            return 'C'
        if has_series_R:
            return 'R'
        
        return 'simple'
    
    def _classify_topology_from_analysis(self, component_analysis, series_components, shunt_components, diff_pair_filter):
        """Classify filter topology from component analysis"""
        component_classes = self.config.get('component_classes', {})
        inductor_prefixes = component_classes.get('inductor_prefixes', ['L', 'FB'])
        capacitor_prefixes = component_classes.get('capacitor_prefixes', ['C'])
        resistor_prefixes = component_classes.get('resistor_prefixes', ['R'])
        
        # Differential pair filter
        if diff_pair_filter:
            filter_type = diff_pair_filter.get('type', 'common_mode_choke')
            ref = diff_pair_filter['ref']
            net1 = diff_pair_filter['net1']
            net2 = diff_pair_filter['net2']
            
            if filter_type == 'common_mode_choke':
                cm_desc = f"Differential common-mode choke: {ref} on {net1}/{net2}"
            elif filter_type == 'common_mode_capacitor':
                cm_desc = f"Differential common-mode capacitor: {ref} between {net1}/{net2}"
            else:
                cm_desc = f"Differential filter: {ref} on {net1}/{net2}"
            
            line_components = [comp for comp in component_analysis if comp['ref'] != ref]
            
            if line_components:
                line_desc_parts = []
                for comp in line_components:
                    c_ref = comp['ref']
                    c_class = comp['component_class']
                    c_type = comp['type']
                    
                    if c_type == 'series':
                        line_desc_parts.append(f"{c_ref}({c_class}-series)")
                    elif c_type == 'shunt':
                        line_desc_parts.append(f"{c_ref}({c_class}-shunt)")
                    else:
                        line_desc_parts.append(f"{c_ref}({c_class})")
                
                line_topology = " → ".join(line_desc_parts)
                line_filter_type = self._classify_line_filter_type(line_components, inductor_prefixes, capacitor_prefixes, resistor_prefixes)
                
                combined_desc = f"{cm_desc} + Line filter ({line_filter_type}): {line_topology}"
                
                if line_filter_type in ['Pi', 'T', 'LC']:
                    return (line_filter_type, combined_desc)
                else:
                    return ('Differential + RC', combined_desc)
            else:
                return ('Differential', cm_desc)
        
        if not component_analysis:
            return ('None', 'No filter components found')
        
        # Build topology description
        desc_parts = []
        for comp in component_analysis:
            ref = comp['ref']
            comp_class = comp['component_class']
            comp_type = comp['type']
            
            if comp_type == 'series':
                desc_parts.append(f"{ref}({comp_class}-series)")
            elif comp_type == 'shunt':
                desc_parts.append(f"{ref}({comp_class}-shunt)")
            else:
                desc_parts.append(f"{ref}({comp_class})")
        
        topology_desc = " → ".join(desc_parts)
        
        # Classify topology
        has_series_L = any(
            any(comp['ref'].startswith(prefix) for prefix in inductor_prefixes)
            for comp in component_analysis if comp['type'] == 'series'
        )
        has_shunt_C = any(
            any(comp['ref'].startswith(prefix) for prefix in capacitor_prefixes)
            for comp in component_analysis if comp['type'] == 'shunt'
        )
        has_series_R = any(
            any(comp['ref'].startswith(prefix) for prefix in resistor_prefixes)
            for comp in component_analysis if comp['type'] == 'series'
        )
        
        # Pi filter
        if len(shunt_components) >= 2 and (has_series_L or has_series_R):
            if (len(component_analysis) >= 3 and 
                component_analysis[0]['type'] == 'shunt' and 
                component_analysis[1]['type'] == 'series' and 
                component_analysis[2]['type'] == 'shunt'):
                if has_series_L:
                    return ('Pi', f"Pi filter: {topology_desc}")
                else:
                    return ('RC', f"RC Pi filter: {topology_desc}")
        
        # T filter
        if len(series_components) >= 2 and has_shunt_C:
            if (len(component_analysis) >= 3 and 
                component_analysis[0]['type'] == 'series' and 
                component_analysis[1]['type'] == 'shunt' and 
                component_analysis[2]['type'] == 'series'):
                if has_series_L:
                    return ('T', f"T filter: {topology_desc}")
                else:
                    return ('T', f"RC T filter: {topology_desc}")
        
        if has_series_L and has_shunt_C:
            return ('LC', f"LC filter: {topology_desc}")
        if has_series_R and has_shunt_C:
            return ('RC', f"RC filter: {topology_desc}")
        if has_series_L:
            return ('L', f"Series inductor: {topology_desc}")
        if has_shunt_C:
            return ('C', f"Shunt capacitor: {topology_desc}")
        if has_series_R:
            return ('R', f"Series resistor: {topology_desc}")
        
        return ('simple', f"Simple filter: {topology_desc}")
    
    def _check_filter_requirement(self, actual_type, required_type):
        """Check if actual filter meets minimum requirement"""
        if actual_type is None:
            return False
        
        hierarchy = ['Pi', 'T', 'LC', 'RC', 'L', 'C', 'R', 'simple']
        
        # Handle compound differential filter types
        if 'Differential' in actual_type:
            if '+' in actual_type:
                parts = actual_type.split('+')
                if len(parts) >= 2:
                    line_filter = parts[1].strip()
                    try:
                        line_rank = hierarchy.index(line_filter)
                        required_rank = hierarchy.index(required_type)
                        effective_rank = max(0, line_rank - 1)
                        return effective_rank <= required_rank
                    except ValueError:
                        pass
            try:
                actual_rank = hierarchy.index('RC')
                required_rank = hierarchy.index(required_type)
                return actual_rank <= required_rank
            except ValueError:
                return False
        
        try:
            actual_rank = hierarchy.index(actual_type)
            required_rank = hierarchy.index(required_type)
            return actual_rank <= required_rank
        except ValueError:
            return False


# Module metadata
__version__ = "1.0.0"
__author__ = "EMC Auditor Plugin"
__description__ = "EMI filtering verification for interface connectors"
