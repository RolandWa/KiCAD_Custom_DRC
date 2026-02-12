"""
Clearance and Creepage Checking Module for EMC Auditor Plugin
Implements IEC60664-1 and IPC2221 electrical safety compliance

This module is called by emc_auditor_plugin.py and reuses its utility functions.
Configuration is read from emc_rules.toml [clearance_creepage] section.

Author: EMC Auditor Plugin
Version: 1.0.0
Last Updated: 2026-02-11
"""

import pcbnew
import math


class ClearanceCreepageChecker:
    """
    Handles clearance and creepage verification between voltage domains.
    
    Clearance: Minimum air gap (3D shortest distance) between conductors
    Creepage: Minimum surface path distance along PCB between conductors
    
    Standards supported:
    - IEC60664-1: Electrical safety, overvoltage categories, pollution degrees
    - IPC2221: PCB spacing recommendations
    """
    
    def __init__(self, board, marker_layer, config, report_lines, verbose=True, auditor=None):
        """
        Initialize checker with board context and configuration.
        
        Args:
            board: pcbnew.BOARD instance
            marker_layer: KiCad layer ID for drawing violation markers
            config: Dictionary from emc_rules.toml [clearance_creepage] section
            report_lines: List to append report messages (shared with main plugin)
            verbose: Enable detailed logging
            auditor: Reference to EMCAuditorPlugin instance (for accessing utility functions)
        """
        self.board = board
        self.marker_layer = marker_layer
        self.config = config
        self.report_lines = report_lines
        self.verbose = verbose
        self.auditor = auditor  # Access to plugin's utility functions
        
        # Parsed data (populated during check)
        self.standard_params = {}
        self.domain_map = {}  # {net_name: domain_info}
        self.isolation_requirements = []
        
        # Utility functions (injected from main plugin)
        self.draw_marker = None
        self.draw_arrow = None
        self.get_distance = None
        
        # Results tracking
        self.violation_count = 0
    
    def check(self, draw_marker_func, draw_arrow_func, get_distance_func, log_func, create_group_func):
        """
        Main entry point - performs complete clearance/creepage verification.
        
        This is called from emc_auditor_plugin.py check_clearance_creepage() method.
        Utility functions are injected to avoid code duplication.
        
        Args:
            draw_marker_func: Function(board, pos, msg, layer, group) to draw error markers
            draw_arrow_func: Function(board, start, end, label, layer, group) to draw arrows
            get_distance_func: Function(pos1, pos2) to calculate distance between points
            log_func: Function(msg, force=False) for logging
            create_group_func: Function(board, check_type, identifier, number) creates PCB_GROUP
        
        Returns:
            int: Number of violations found
        """
        # Store utility functions for reuse throughout check
        self.log = log_func  # Centralized logger from main plugin
        self.draw_marker = draw_marker_func
        self.draw_arrow = draw_arrow_func
        self.get_distance = get_distance_func
        
        self.log("\n=== CLEARANCE & CREEPAGE CHECK START ===", force=True)
        self.log("Phase 1: Pad-to-pad clearance only (basic implementation)", force=True)
        
        # Step 1: Parse standard parameters from config
        self.standard_params = self._parse_standard_params()
        self._report_standard_params()
        
        # Step 2: Parse voltage domains (with KiCad Net Classes support)
        self.domain_map = self._parse_voltage_domains()
        self._report_voltage_domains()
        
        if not self.domain_map:
            self.log("⚠️  No nets assigned to voltage domains - check configuration", force=True)
            return 0
        
        # Step 3: Parse isolation requirements
        self.isolation_requirements = self.config.get('isolation_requirements', [])
        self._report_isolation_requirements()
        
        # Step 4: Get all copper features (pads) for each voltage domain
        self.log("\n--- Collecting Pads by Domain ---")
        features_by_domain = self._get_copper_features_by_domain()
        
        for domain_name, features in features_by_domain.items():
            self.log(f"  {domain_name}: {len(features)} pad(s)")
        
        # Step 5: Check clearance between all domain pairs
        self.log("\n--- Checking Clearance Between Domains ---")
        
        domain_names = list(features_by_domain.keys())
        pairs_checked = 0
        
        for i, domain_a in enumerate(domain_names):
            for j, domain_b in enumerate(domain_names):
                if i >= j:  # Skip self-pairs and duplicates
                    continue
                
                pairs_checked += 1
                self.log(f"\nChecking: {domain_a} ↔ {domain_b}")
                
                features_a = features_by_domain[domain_a]
                features_b = features_by_domain[domain_b]
                
                if not features_a or not features_b:
                    self.log("  ⚠️  Skipping (no features in one or both domains)")
                    continue
                
                # Calculate minimum clearance
                result = self._calculate_clearance(features_a, features_b)
                if not result:
                    self.log("  ⚠️  Could not calculate clearance")
                    continue
                
                actual_mm, point1, point2, net_a, net_b = result
                
                # Get voltage and reinforced flags from first feature in each domain
                voltage_a = features_a[0][4]  # voltage_rms from feature tuple
                voltage_b = features_b[0][4]
                reinforced_a = features_a[0][5]  # reinforced flag
                reinforced_b = features_b[0][5]
                
                # Lookup required clearance
                required_mm, isolation_type, description = self._lookup_required_clearance(
                    domain_a, domain_b, voltage_a, voltage_b, reinforced_a, reinforced_b
                )
                
                self.log(f"  Actual: {actual_mm:.2f}mm, Required: {required_mm:.2f}mm ({isolation_type})")
                self.log(f"  Nets: {net_a} ↔ {net_b}")
                
                # Check for violation
                if actual_mm < required_mm:
                    self._create_clearance_violation_marker(
                        domain_a, domain_b, actual_mm, required_mm, point1, point2, net_a, net_b, create_group_func
                    )
                else:
                    self.log("  ✓ PASS")
        
        self.log(f"\n=== CLEARANCE CHECK COMPLETE: {pairs_checked} pair(s) checked, {self.violation_count} violation(s) ===", force=True)
        return self.violation_count
    
    # ======================================================================
    # STEP 1: PARSE STANDARD PARAMETERS
    # ======================================================================
    
    def _parse_standard_params(self):
        """
        Parse standard selection and parameters from config.
        
        Returns:
            dict: {
                'standard': 'IEC60664-1' | 'IPC2221' | 'BOTH',
                'overvoltage_category': 'I' | 'II' | 'III' | 'IV',
                'pollution_degree': 1 | 2 | 3 | 4,
                'material_group': 'I' | 'II' | 'IIIa' | 'IIIb',
                'altitude_m': int (meters above sea level)
            }
        """
        return {
            'standard': self.config.get('standard', 'IEC60664-1'),
            'overvoltage_category': self.config.get('overvoltage_category', 'II'),
            'pollution_degree': self.config.get('pollution_degree', 2),
            'material_group': self.config.get('material_group', 'II'),
            'altitude_m': self.config.get('altitude_m', 1000)
        }
    
    def _report_standard_params(self):
        """Print standard parameters to log for traceability"""
        params = self.standard_params
        self.log("\n--- Standard Parameters ---")
        self.log(f"Standard: {params['standard']}")
        self.log(f"Overvoltage Category: {params['overvoltage_category']}")
        self.log(f"Pollution Degree: {params['pollution_degree']}")
        self.log(f"Material Group: {params['material_group']} (for creepage)")
        self.log(f"Altitude: {params['altitude_m']}m above sea level")
    
    # ======================================================================
    # STEP 2: PARSE VOLTAGE DOMAINS (WITH NET CLASSES SUPPORT)
    # ======================================================================
    
    def _parse_voltage_domains(self):
        """
        Parse voltage domains from config and map nets to domains.
        
        PRIORITY:
        1. KiCad Net Classes (preferred) - matches domain names to net class names
        2. net_patterns (fallback) - case-insensitive pattern matching
        
        Returns:
            dict: {
                net_name: {
                    'domain_name': str,
                    'voltage_rms': float,
                    'requires_reinforced_insulation': bool,
                    'source': 'net_class' | 'pattern'
                }
            }
        """
        voltage_domains = self.config.get('voltage_domains', [])
        domain_map = {}
        
        self.log(f"\n--- Parsing Voltage Domains ---")
        self.log(f"Found {len(voltage_domains)} domain(s) in configuration")
        
        for domain_config in voltage_domains:
            domain_name = domain_config.get('name', 'Unknown')
            voltage_rms = domain_config.get('voltage_rms', 0)
            net_patterns = domain_config.get('net_patterns', [])
            reinforced = domain_config.get('requires_reinforced_insulation', False)
            
            self.log(f"\n  Processing domain: {domain_name} ({voltage_rms}V)")
            
            # Try to match Net Class first (preferred) - use centralized helper
            nets_in_class = self.auditor.get_nets_by_class(self.board, domain_name)
            
            if nets_in_class:
                for net_name in nets_in_class:
                    domain_map[net_name] = {
                        'domain_name': domain_name,
                        'voltage_rms': voltage_rms,
                        'requires_reinforced_insulation': reinforced,
                        'source': 'net_class'
                    }
                self.log(f"    ✓ Assigned {len(nets_in_class)} net(s) via Net Class '{domain_name}'")
                continue  # Skip pattern matching if Net Class found
            else:
                self.log(f"    ⚠ No nets assigned to Net Class '{domain_name}'")
            
            # Fallback: Pattern matching for unclassified nets
            self.log(f"    → Trying pattern matching: {net_patterns}")
            pattern_matches = 0
            
            # Get all nets from board for pattern matching
            all_nets = self.board.GetNetInfo().NetsByName().values()
            
            for net in all_nets:
                net_name = net.GetNetname()
                if not net_name:  # Skip empty net names
                    continue
                    
                if net_name not in domain_map:  # Not already assigned via Net Class
                    for pattern in net_patterns:
                        if pattern.upper() in net_name.upper():
                            domain_map[net_name] = {
                                'domain_name': domain_name,
                                'voltage_rms': voltage_rms,
                                'requires_reinforced_insulation': reinforced,
                                'source': 'pattern'
                            }
                            pattern_matches += 1
                            break
            
            if pattern_matches > 0:
                self.log(f"    ✓ Assigned {pattern_matches} net(s) via pattern matching")
            else:
                self.log(f"    ⚠ No nets matched patterns")
        
        return domain_map
    
    def _report_voltage_domains(self):
        """Print voltage domain assignments to log"""
        self.log(f"\n--- Voltage Domain Assignments ---")
        
        if not self.domain_map:
            self.log("⚠️  No nets assigned to voltage domains")
            self.log("HINT: Define Net Classes in KiCad or check net_patterns in TOML config")
            return
        
        # Group nets by domain for cleaner output
        domains = {}
        for net_name, domain_info in self.domain_map.items():
            domain_name = domain_info['domain_name']
            if domain_name not in domains:
                domains[domain_name] = {
                    'voltage_rms': domain_info['voltage_rms'],
                    'reinforced': domain_info['requires_reinforced_insulation'],
                    'nets_from_class': [],
                    'nets_from_pattern': []
                }
            
            if domain_info['source'] == 'net_class':
                domains[domain_name]['nets_from_class'].append(net_name)
            else:
                domains[domain_name]['nets_from_pattern'].append(net_name)
        
        # Print grouped by domain
        for domain_name, domain_data in domains.items():
            voltage = domain_data['voltage_rms']
            reinforced = domain_data['reinforced']
            reinforced_str = " (REINFORCED)" if reinforced else ""
            
            self.log(f"\n{domain_name} domain ({voltage}V RMS{reinforced_str}):")
            
            if domain_data['nets_from_class']:
                self.log(f"  ✓ From Net Class: {', '.join(domain_data['nets_from_class'])}")
            
            if domain_data['nets_from_pattern']:
                self.log(f"  ✓ From patterns: {', '.join(domain_data['nets_from_pattern'])}")
    
    # ======================================================================
    # STEP 3: REPORT ISOLATION REQUIREMENTS
    # ======================================================================
    
    def _report_isolation_requirements(self):
        """Print isolation requirements between domain pairs"""
        self.log(f"\n--- Isolation Requirements Configured ---")
        
        if not self.isolation_requirements:
            self.log("⚠️  No specific isolation requirements defined")
            self.log("Will use voltage-based table lookup for all domain pairs")
            return
        
        self.log(f"Found {len(self.isolation_requirements)} specific requirement(s):")
        for req in self.isolation_requirements:
            domain_a = req.get('domain_a', '?')
            domain_b = req.get('domain_b', '?')
            isolation_type = req.get('isolation_type', 'basic')
            min_clearance = req.get('min_clearance_mm', 0)
            min_creepage = req.get('min_creepage_mm', 0)
            description = req.get('description', '')
            
            self.log(f"  {domain_a} ↔ {domain_b}: {isolation_type}")
            self.log(f"    Clearance: {min_clearance}mm, Creepage: {min_creepage}mm")
            if description:
                self.log(f"    ({description})")
    
    # ======================================================================
    # STEP 4-8: TODO - IMPLEMENTATION PENDING
    # ======================================================================
    
    def _get_copper_features_by_domain(self):
        """
        Get all copper features (pads only for Phase 1) for each voltage domain.
        
        Returns:
            dict: {
                domain_name: [
                    ('pad', pcbnew.PAD, position),
                    ...
                ]
            }
        """
        features_by_domain = {}
        
        # Initialize empty lists for each domain
        for net_name, domain_info in self.domain_map.items():
            domain_name = domain_info['domain_name']
            if domain_name not in features_by_domain:
                features_by_domain[domain_name] = []
        
        # Iterate through all footprints and pads
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                net = pad.GetNet()
                if not net:
                    continue  # Skip unconnected pads
                
                net_name = net.GetNetname()
                if net_name in self.domain_map:
                    domain_info = self.domain_map[net_name]
                    domain_name = domain_info['domain_name']
                    pad_pos = pad.GetPosition()
                    
                    # Store: (feature_type, object, position, net_name, voltage_rms, reinforced)
                    features_by_domain[domain_name].append((
                        'pad',
                        pad,
                        pad_pos,
                        net_name,
                        domain_info['voltage_rms'],
                        domain_info['requires_reinforced_insulation']
                    ))
        
        return features_by_domain
    
    def _get_domain_pairs(self):
        """
        Get all unique pairs of voltage domains to check.
        
        Yields:
            tuple: (domain_a_name, domain_b_name)
        """
        # TODO: Implement
        pass
    
    def _calculate_clearance(self, features_a, features_b):
        """
        Calculate minimum 2D clearance (air gap) between two domain feature lists.
        
        Args:
            features_a: list of features from domain A
            features_b: list of features from domain B
        
        Returns:
            tuple: (distance_mm, point1, point2, net_a, net_b) or None if no features
        """
        if not features_a or not features_b:
            return None
        
        min_distance = float('inf')
        closest_point_a = None
        closest_point_b = None
        closest_net_a = None
        closest_net_b = None
        
        # Compare all pad pairs between domains (Phase 1: pad-to-pad only)
        for feature_a in features_a:
            ftype_a, pad_a, pos_a, net_a, voltage_a, reinforced_a = feature_a
            
            for feature_b in features_b:
                ftype_b, pad_b, pos_b, net_b, voltage_b, reinforced_b = feature_b
                
                # Calculate 2D distance using injected utility function
                distance = self.get_distance(pos_a, pos_b)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_point_a = pos_a
                    closest_point_b = pos_b
                    closest_net_a = net_a
                    closest_net_b = net_b
        
        if min_distance == float('inf'):
            return None
        
        # Convert from internal units to mm
        distance_mm = pcbnew.ToMM(min_distance)
        
        return (distance_mm, closest_point_a, closest_point_b, closest_net_a, closest_net_b)
    
    def _calculate_creepage(self, domain_a, domain_b):
        """
        Calculate minimum surface path (creepage) between two domains.
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
        
        Returns:
            tuple: (distance_mm, path_line)
        """
        # TODO: Implement
        pass
    
    def _lookup_required_clearance(self, domain_a, domain_b, voltage_a, voltage_b, reinforced_a, reinforced_b):
        """
        Look up required clearance distance from config/tables.
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            voltage_a: float, RMS voltage of domain A
            voltage_b: float, RMS voltage of domain B
            reinforced_a: bool, domain A requires reinforced insulation
            reinforced_b: bool, domain B requires reinforced insulation
        
        Returns:
            tuple: (required_clearance_mm, isolation_type, description)
        """
        # Step 1: Check for specific isolation requirement in config
        for req in self.isolation_requirements:
            req_domain_a = req.get('domain_a', '')
            req_domain_b = req.get('domain_b', '')
            
            # Check both directions (A-B or B-A)
            if (req_domain_a == domain_a and req_domain_b == domain_b) or \
               (req_domain_a == domain_b and req_domain_b == domain_a):
                clearance = req.get('min_clearance_mm', 0)
                isolation_type = req.get('isolation_type', 'basic')
                description = req.get('description', '')
                
                # Apply safety margin
                safety_factor = self.config.get('safety_margin_factor', 1.2)
                clearance *= safety_factor
                
                return (clearance, isolation_type, description)
        
        # Step 2: Calculate from voltage difference and standard tables
        voltage_diff = abs(voltage_a - voltage_b)
        
        # Get clearance from IEC60664-1 table
        clearance = self._interpolate_clearance_table(voltage_diff)
        
        # Step 3: Apply reinforced insulation factor (2×)
        isolation_type = 'basic'
        if reinforced_a or reinforced_b:
            clearance *= 2.0
            isolation_type = 'reinforced'
        
        # Step 4: Apply safety margin
        safety_factor = self.config.get('safety_margin_factor', 1.2)
        clearance *= safety_factor
        
        # Step 5: Apply altitude correction if >2000m
        altitude = self.standard_params.get('altitude_m', 1000)
        if altitude > 2000:
            altitude_factor = 1.0 + 0.00025 * (altitude - 2000)
            clearance *= altitude_factor
        
        description = f"{voltage_diff:.1f}V differential, {isolation_type} insulation"
        
        return (clearance, isolation_type, description)
    
    def _interpolate_clearance_table(self, voltage_rms):
        """
        Interpolate clearance distance from IEC60664-1 table.
        
        Args:
            voltage_rms: float, RMS voltage differential
        
        Returns:
            float: Required clearance in mm
        """
        # Get clearance table from config
        clearance_tables = self.config.get('iec60664_clearance_table', [])
        
        # Build flat voltage list from all table sections
        all_voltages = []
        for table in clearance_tables:
            voltages = table.get('voltages', [])
            all_voltages.extend(voltages)
        
        if not all_voltages:
            # Fallback: use minimum safe spacing
            return 0.5  # 0.5mm minimum
        
        # Sort by voltage
        all_voltages.sort(key=lambda x: x[0])
        
        # If voltage below lowest table entry, use lowest value
        if voltage_rms <= all_voltages[0][0]:
            return all_voltages[0][1]
        
        # If voltage above highest table entry, use highest value
        if voltage_rms >= all_voltages[-1][0]:
            return all_voltages[-1][1]
        
        # Linear interpolation between table entries
        for i in range(len(all_voltages) - 1):
            v_low, d_low = all_voltages[i]
            v_high, d_high = all_voltages[i + 1]
            
            if v_low <= voltage_rms <= v_high:
                # Linear interpolation
                ratio = (voltage_rms - v_low) / (v_high - v_low)
                clearance = d_low + ratio * (d_high - d_low)
                return clearance
        
        # Fallback
        return 0.5
    
    def _create_clearance_violation_marker(self, domain_a, domain_b, actual_mm, required_mm, point1, point2, net_a, net_b, create_group_func):
        """
        Draw violation marker for insufficient clearance.
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            actual_mm: float, actual clearance measured
            required_mm: float, required clearance from tables
            point1: pcbnew.VECTOR2I, closest point on domain A
            point2: pcbnew.VECTOR2I, closest point on domain B
            net_a: str, net name on domain A
            net_b: str, net name on domain B
            create_group_func: Function to create violation groups
        """
        # Create unique group using centralized utility
        self.violation_count += 1
        violation_group = create_group_func(self.board, "Clearance", f"{domain_a}_{domain_b}", self.violation_count)
        
        # Format violation message
        msg = f"CLEARANCE: {actual_mm:.2f}mm < {required_mm:.2f}mm\n{domain_a}-{domain_b}\n{net_a} ↔ {net_b}"
        
        # Draw marker at midpoint between violations
        midpoint_x = (point1.x + point2.x) // 2
        midpoint_y = (point1.y + point2.y) // 2
        midpoint = pcbnew.VECTOR2I(midpoint_x, midpoint_y)
        
        # Use injected draw_marker function from main plugin
        self.draw_marker(self.board, midpoint, msg, self.marker_layer, violation_group)
        
        # Draw arrow from point1 to point2 showing violation path
        self.draw_arrow(self.board, point1, point2, f"{actual_mm:.2f}mm", self.marker_layer, violation_group)
        
        # Log to report
        self.log(f"  ❌ VIOLATION: {domain_a} ({net_a}) ↔ {domain_b} ({net_b})", force=True)
        self.log(f"     Actual: {actual_mm:.2f}mm, Required: {required_mm:.2f}mm", force=True)
    
    def _create_creepage_violation_marker(self, domain_a, domain_b, actual_mm, required_mm, path_start, path_end):
        """
        Draw violation marker for insufficient creepage.
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            actual_mm: float, actual creepage measured
            required_mm: float, required creepage from tables
            path_start: pcbnew.VECTOR2I, start of surface path
            path_end: pcbnew.VECTOR2I, end of surface path
        """
        # TODO: Implement using self.draw_marker() and self.draw_arrow()
        # Create group: f"EMC_Creepage_{domain_a}_{domain_b}_{self.violation_count+1}"
        # Message: f"CREEPAGE: {actual_mm:.2f}mm < {required_mm:.2f}mm ({domain_a}-{domain_b})"
        pass


# Module metadata
__version__ = "1.0.0"
__author__ = "EMC Auditor Plugin"
__description__ = "Clearance and Creepage checking for IEC60664-1 / IPC2221 compliance"
