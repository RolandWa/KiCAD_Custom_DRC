"""
Clearance and Creepage Checking Module for EMC Auditor Plugin
Implements IEC60664-1 and IPC2221 electrical safety compliance

This module is called by emc_auditor_plugin.py and reuses its utility functions.
Configuration is read from emc_rules.toml [clearance_creepage] section.

Author: EMC Auditor Plugin
Version: 2.0.0 - Optimized with Visibility Graph + Dijkstra
Last Updated: 2026-02-13
"""

import pcbnew
import math
import heapq


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
        self.clearance_violations = 0
        self.creepage_violations = 0
        
        # Creepage checking statistics
        self.creepage_stats = {
            'pairs_checked': 0,
            'layers_skipped_obstacles': [],  # List of (domain_a, domain_b, layer, obstacle_count)
            'layers_calculated': [],  # List of (domain_a, domain_b, layer, actual_mm, required_mm)
            'layers_no_path': []  # List of (domain_a, domain_b, layer) - slot/cutout breaks path
        }
        
        # Performance limits
        self.max_obstacles = self.config.get('max_obstacles', 500)  # Maximum obstacles per layer for creepage pathfinding
        self.obstacle_search_margin_mm = self.config.get('obstacle_search_margin_mm', 12.0)  # Spatial filtering margin
    
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
        check_clearance_enabled = self.config.get('check_clearance', True)
        check_creepage_enabled = self.config.get('check_creepage', True)
        self.report_mode = self.config.get('report_mode', 'violations_only')
        modes = []
        if check_clearance_enabled:
            modes.append("Clearance (air gap)")
        if check_creepage_enabled:
            modes.append("Creepage (surface path)")
        if modes:
            self.log(f"Checks enabled: {' + '.join(modes)}", force=True)
        else:
            self.log("⚠️  Both check_clearance and check_creepage are disabled", force=True)
            return 0
        if self.report_mode == 'all_distances':
            self.log("Report mode: all_distances (reporting all pairs, not just violations)", force=True)
        
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
        
        # Step 5: Check clearance and/or creepage between all domain pairs
        self.log("\n--- Checking Between Domains ---")
        
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
                
                # Get voltage and reinforced flags from first feature in each domain
                voltage_a = features_a[0][4]  # voltage_rms from feature tuple
                voltage_b = features_b[0][4]
                reinforced_a = features_a[0][5]  # reinforced flag
                reinforced_b = features_b[0][5]
                
                # --- Clearance check (if enabled) ---
                actual_mm = None
                point1 = None
                point2 = None
                net_a = None
                net_b = None
                layer_a = None
                layer_b = None
                
                if check_clearance_enabled:
                    # Log number of comparisons to help user understand performance
                    num_comparisons = len(features_a) * len(features_b)
                    self.log(f"  Comparing {len(features_a)} × {len(features_b)} = {num_comparisons} pad pair(s)")
                    
                    # Calculate minimum clearance
                    result = self._calculate_clearance(features_a, features_b)
                    if not result:
                        self.log("  ⚠️  Could not calculate clearance")
                    else:
                        actual_mm, point1, point2, net_a, net_b, layer_a, layer_b = result
                        
                        # Lookup required clearance with layer information
                        required_mm, isolation_type, description = self._lookup_required_clearance(
                            domain_a, domain_b, voltage_a, voltage_b, reinforced_a, reinforced_b, layer_a, layer_b
                        )
                        
                        self.log(f"  Actual: {actual_mm:.2f}mm, Required: {required_mm:.2f}mm ({isolation_type})")
                        self.log(f"  Nets: {net_a} ↔ {net_b}")
                        
                        # Check for violation
                        if actual_mm < required_mm:
                            self._create_clearance_violation_marker(
                                domain_a, domain_b, actual_mm, required_mm, point1, point2, net_a, net_b, create_group_func
                            )
                            self.clearance_violations += 1
                        else:
                            self.log("  ✓ PASS (clearance)")
                            if self.report_mode == 'all_distances':
                                self.log(f"  ℹ️  {domain_a} ↔ {domain_b}: clearance {actual_mm:.2f}mm (req {required_mm:.2f}mm) — OK")
                
                # --- Creepage check (if enabled) ---
                if check_creepage_enabled:
                    self.creepage_stats['pairs_checked'] += 1
                    self.log("\n  --- Checking Creepage (Surface Path) ---")
                    
                    # Get pads for each domain (needed for pathfinding)
                    pads_a = [f[1] for f in features_a]  # Extract PAD objects from feature tuples (index 1)
                    pads_b = [f[1] for f in features_b]
                    
                    # Pre-compute required creepage so pathfinder can skip
                    # expensive Dijkstra when straight-line already passes
                    required_creepage_mm = self._lookup_required_creepage(
                        domain_a, domain_b, voltage_a, voltage_b, reinforced_a, reinforced_b
                    )
                    
                    # Check creepage on each copper layer
                    checked_layers = set()
                    for pad in pads_a + pads_b:
                        layer = pad.GetLayer()
                        layer_name = self.board.GetLayerName(layer)
                        # Check if it's a copper layer (F.Cu, B.Cu, In1.Cu, etc.)
                        is_copper = '.Cu' in layer_name
                        if layer not in checked_layers and is_copper:
                            checked_layers.add(layer)
                            
                            self.log(f"    Layer: {layer_name}")
                            
                            # Calculate creepage on this layer
                            creepage_result = self._calculate_creepage(
                                domain_a, domain_b, pads_a, pads_b, layer,
                                required_creepage_mm=required_creepage_mm
                            )
                            
                            if creepage_result:
                                actual_creepage_mm, path, start_pad, end_pad = creepage_result
                                
                                if actual_creepage_mm == float('inf'):
                                    self.log(f"      No valid creepage path (slot/cutout breaks path)")
                                    self.creepage_stats['layers_no_path'].append((domain_a, domain_b, layer_name))
                                    continue
                                
                                self.log(f"      Actual: {actual_creepage_mm:.2f}mm, Required: {required_creepage_mm:.2f}mm")
                                
                                # Track successful calculation
                                self.creepage_stats['layers_calculated'].append(
                                    (domain_a, domain_b, layer_name, actual_creepage_mm, required_creepage_mm)
                                )
                                
                                # Check for violation
                                if actual_creepage_mm < required_creepage_mm:
                                    self._create_creepage_violation_marker(
                                        domain_a, domain_b, actual_creepage_mm, required_creepage_mm,
                                        path, start_pad, end_pad, create_group_func
                                    )
                                    self.creepage_violations += 1
                                else:
                                    self.log(f"      ✓ PASS (creepage)")
                                    if self.report_mode == 'all_distances':
                                        self.log(f"      ℹ️  {domain_a} ↔ {domain_b} on {layer_name}: creepage {actual_creepage_mm:.2f}mm (req {required_creepage_mm:.2f}mm) — OK")
                                    if self.config.get('draw_creepage_path', False) and path and len(path) >= 2:
                                        self._draw_debug_creepage_path(
                                            domain_a, domain_b, actual_creepage_mm, required_creepage_mm,
                                            path, start_pad, end_pad, create_group_func
                                        )
                            else:
                                self.log(f"      Could not calculate creepage")
        
        # Report creepage checking summary if enabled
        if check_creepage_enabled:
            self._report_creepage_summary()
        
        self.log(f"\n=== CLEARANCE & CREEPAGE CHECK COMPLETE: {pairs_checked} pair(s) checked, {self.violation_count} violation(s) ===", force=True)
        if check_clearance_enabled:
            self.log(f"    Clearance violations: {self.clearance_violations}")
        if check_creepage_enabled:
            self.log(f"    Creepage violations: {self.creepage_violations}")
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
        failed_domains = []  # Track domains that got no net assignments
        
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
                failed_domains.append(domain_name)
        
        # Print board net inventory:
        #   list_all_nets = true  → show ALL nets (useful for first-time setup)
        #   list_all_nets = false → show only nets assigned to a domain
        list_all = self.config.get('list_all_nets', False)
        show_inventory = bool(failed_domains) or list_all
        if show_inventory:
            self.log(f"\n--- Board Net Inventory (configuration reference) ---")
            if failed_domains:
                self.log(f"  The following domain(s) found no nets: {', '.join(failed_domains)}")
                self.log(f"  Add matching substrings to 'net_patterns' in emc_rules.toml\n")
            all_net_names = sorted(
                net.GetNetname()
                for net in self.board.GetNetInfo().NetsByName().values()
                if net.GetNetname()
            )
            if list_all:
                # Show every net on the board
                if all_net_names:
                    self.log(f"  All nets on this board ({len(all_net_names)} total):")
                    for name in all_net_names:
                        assigned = domain_map.get(name, {}).get('domain_name', '')
                        tag = f"  → assigned to {assigned}" if assigned else ""
                        self.log(f"    • {name}{tag}")
                else:
                    self.log("  ⚠ Board has no named nets — is the PCB file loaded correctly?")
            else:
                # Show only nets assigned to a domain
                assigned_nets = sorted(n for n in all_net_names if n in domain_map)
                if assigned_nets:
                    self.log(f"  Assigned nets ({len(assigned_nets)} of {len(all_net_names)} total):")
                    for name in assigned_nets:
                        dname = domain_map[name]['domain_name']
                        self.log(f"    • {name}  → assigned to {dname}")
                else:
                    self.log("  ⚠ No nets assigned to any domain")
        
        return domain_map
    
    def _report_voltage_domains(self):
        """Print voltage domain assignments to log"""
        self.log(f"\n--- Voltage Domain Assignments ---")
        
        if not self.domain_map:
            self.log("⚠️  No nets assigned to any voltage domain — clearance/creepage check will be skipped")
            self.log("HINT: See 'Board Net Inventory' above to find the correct net names")
            self.log("HINT: Update 'net_patterns' in emc_rules.toml, or assign nets to Net Classes in KiCad")
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
    
    def _report_creepage_summary(self):
        """Print summary of creepage checking results and statistics"""
        self.log(f"\n--- Creepage Checking Summary ---")
        
        if not self.config.get('check_creepage', True):
            self.log("ℹ️  Creepage checking is disabled (check_creepage = false)")
            return
        
        pairs_checked = self.creepage_stats['pairs_checked']
        layers_skipped = self.creepage_stats['layers_skipped_obstacles']
        layers_calculated = self.creepage_stats['layers_calculated']
        layers_no_path = self.creepage_stats['layers_no_path']
        
        self.log(f"Domain pairs checked for creepage: {pairs_checked}")
        
        if layers_skipped:
            self.log(f"\n⚠️  Layers skipped due to obstacle limit ({len(layers_skipped)}):")
            for domain_a, domain_b, layer_name, obstacle_count in layers_skipped:
                self.log(f"  {domain_a} ↔ {domain_b} on {layer_name}: {obstacle_count} obstacles (limit: {self.max_obstacles})")
            self.log(f"\nℹ️  Obstacle Limit Guidance:")
            self.log(f"  Current: {self.max_obstacles} obstacles maximum")
            if layers_skipped:
                max_obstacles_seen = max(count for _, _, _, count in layers_skipped)
                self.log(f"  Your board: {max_obstacles_seen} obstacles maximum")
                if max_obstacles_seen > self.max_obstacles * 5:
                    self.log(f"  ⚠️  WARNING: Board has {max_obstacles_seen // self.max_obstacles}× more obstacles than limit!")
                    self.log(f"  Consider disabling creepage (check_creepage = false) or increasing limit")
                else:
                    self.log(f"  To enable creepage checking: increase 'max_obstacles' to {max_obstacles_seen + 100}")
        
        if layers_calculated:
            self.log(f"\n✅ Layers with successful creepage calculation ({len(layers_calculated)}):")
            for domain_a, domain_b, layer_name, actual_mm, required_mm in layers_calculated:
                status = "✅ PASS" if actual_mm >= required_mm else "❌ FAIL"
                self.log(f"  {domain_a} ↔ {domain_b} on {layer_name}: {actual_mm:.3f}mm (req: {required_mm}mm) {status}")
        
        if layers_no_path:
            self.log(f"\n⚠️  Layers with no creepage path found ({len(layers_no_path)}):")
            for domain_a, domain_b, layer_name in layers_no_path:
                self.log(f"  {domain_a} ↔ {domain_b} on {layer_name}: No surface path (may be separated by slots/cutouts)")
    
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

    def _is_external_layer(self, layer):
        """
        Determine if a layer is external (exposed) or internal (protected).
        
        Args:
            layer: pcbnew layer ID
        
        Returns:
            bool: True if external layer, False if internal
        """
        # Get layer name
        layer_name = self.board.GetLayerName(layer)
        
        # External layers: F.Cu (Front), B.Cu (Back)
        if layer == pcbnew.F_Cu or layer == pcbnew.B_Cu:
            return True
        
        # Internal layers: In1.Cu, In2.Cu, etc.
        if 'In' in layer_name and '.Cu' in layer_name:
            return False
        
        # Default to external (conservative)
        return True
    
    def _get_pad_polygon(self, pad, layer):
        """
        Get the actual polygon outline of a pad accounting for shape and rotation.
        
        Args:
            pad: pcbnew.PAD object
            layer: pcbnew layer ID
        
        Returns:
            SHAPE_POLY_SET: Actual pad outline polygon
        """
        # Create polygon set
        poly_set = pcbnew.SHAPE_POLY_SET()
        
        # Transform pad shape to polygon (accounts for rotation, oval, rounded rect, etc.)
        # Parameters: poly_set, layer, clearance, maxError, errorLoc
        # maxError: Maximum deviation when approximating curves (0.005mm = 5 micrometers)
        clearance = 0  # Exact pad outline
        max_error = pcbnew.FromMM(0.005)  # 5um tolerance for curve approximation
        pad.TransformShapeToPolygon(poly_set, layer, clearance, max_error, pcbnew.ERROR_INSIDE)
        
        return poly_set
    
    def _calculate_polygon_distance(self, poly_a, poly_b):
        """
        Calculate minimum edge-to-edge distance between two polygons.
        Uses point-to-segment distance for all vertices against all edges.
        
        Args:
            poly_a: SHAPE_POLY_SET for first pad
            poly_b: SHAPE_POLY_SET for second pad
        
        Returns:
            float: Minimum distance in internal units
        """
        min_distance = float('inf')
        
        # Get outline 0 from both polygon sets (pads typically have one outline)
        if poly_a.OutlineCount() == 0 or poly_b.OutlineCount() == 0:
            return min_distance
        
        outline_a = poly_a.Outline(0)
        outline_b = poly_b.Outline(0)
        
        # Get point count for both outlines
        count_a = outline_a.PointCount()
        count_b = outline_b.PointCount()
        
        # Early exit threshold: If we find distance < 0.01mm, stop searching (likely a violation)
        early_exit_threshold = pcbnew.FromMM(0.01)
        
        # Check all vertices of polygon A against all edges of polygon B
        for i in range(count_a):
            point_a = outline_a.CPoint(i)
            
            # Check distance to all edges of polygon B
            for j in range(count_b):
                point_b1 = outline_b.CPoint(j)
                point_b2 = outline_b.CPoint((j + 1) % count_b)  # Next point (wrap around)
                
                # Calculate distance from point A to line segment B1-B2
                dist = self._point_to_segment_distance(point_a, point_b1, point_b2)
                if dist < min_distance:
                    min_distance = dist
                    # Early exit if we found very close proximity
                    if min_distance < early_exit_threshold:
                        return min_distance
        
        # Check all vertices of polygon B against all edges of polygon A
        for i in range(count_b):
            point_b = outline_b.CPoint(i)
            
            # Check distance to all edges of polygon A
            for j in range(count_a):
                point_a1 = outline_a.CPoint(j)
                point_a2 = outline_a.CPoint((j + 1) % count_a)  # Next point (wrap around)
                
                # Calculate distance from point B to line segment A1-A2
                dist = self._point_to_segment_distance(point_b, point_a1, point_a2)
                if dist < min_distance:
                    min_distance = dist
                    # Early exit if we found very close proximity
                    if min_distance < early_exit_threshold:
                        return min_distance
        
        return min_distance
    
    def _point_to_segment_distance(self, point, seg_start, seg_end):
        """
        Calculate minimum distance from a point to a line segment.
        
        Args:
            point: VECTOR2I point
            seg_start: VECTOR2I segment start
            seg_end: VECTOR2I segment end
        
        Returns:
            float: Minimum distance in internal units
        """
        # Vector from segment start to end
        dx = seg_end.x - seg_start.x
        dy = seg_end.y - seg_start.y
        
        # Handle degenerate case (segment is a point)
        segment_length_sq = dx * dx + dy * dy
        if segment_length_sq == 0:
            # Segment is just a point, return distance to that point
            return self.get_distance(point, seg_start)
        
        # Calculate projection parameter t
        # t represents where along the segment the closest point lies
        # t=0 means seg_start, t=1 means seg_end
        t = ((point.x - seg_start.x) * dx + (point.y - seg_start.y) * dy) / segment_length_sq
        
        # Clamp t to [0, 1] to stay on the segment
        t = max(0, min(1, t))
        
        # Calculate closest point on segment
        closest_x = seg_start.x + t * dx
        closest_y = seg_start.y + t * dy
        
        # Return distance from point to closest point
        dist_x = point.x - closest_x
        dist_y = point.y - closest_y
        return math.sqrt(dist_x * dist_x + dist_y * dist_y)
    
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
        closest_layer_a = None
        closest_layer_b = None
        
        # Compare all pad pairs between domains (Phase 1: pad-to-pad only)
        for feature_a in features_a:
            ftype_a, pad_a, pos_a, net_a, voltage_a, reinforced_a = feature_a
            size_a = pad_a.GetSize()
            max_extent_a = max(size_a.x, size_a.y) / 2.0
            
            for feature_b in features_b:
                ftype_b, pad_b, pos_b, net_b, voltage_b, reinforced_b = feature_b
                size_b = pad_b.GetSize()
                max_extent_b = max(size_b.x, size_b.y) / 2.0
                
                # FAST PATH: Use center-to-center distance for quick rejection
                center_distance = self.get_distance(pos_a, pos_b)
                
                # Quick approximation: subtract max extents for rough edge distance
                approx_edge_distance = center_distance - max_extent_a - max_extent_b
                
                # If approximate distance is already much larger than current minimum,
                # skip expensive polygon calculation (threshold: 2mm)
                if approx_edge_distance > min_distance + pcbnew.FromMM(2.0):
                    continue
                
                # ACCURATE PATH: Only calculate exact polygon distance for close pads
                layer_a = pad_a.GetLayer()
                layer_b = pad_b.GetLayer()
                poly_a = self._get_pad_polygon(pad_a, layer_a)
                poly_b = self._get_pad_polygon(pad_b, layer_b)
                
                # Calculate accurate EDGE-TO-EDGE distance between polygons
                edge_distance = self._calculate_polygon_distance(poly_a, poly_b)
                
                # Ensure distance is not negative (overlapping pads)
                edge_distance = max(0, edge_distance)
                
                if edge_distance < min_distance:
                    min_distance = edge_distance
                    closest_point_a = pos_a
                    closest_point_b = pos_b
                    closest_net_a = net_a
                    closest_net_b = net_b
                    closest_layer_a = layer_a
                    closest_layer_b = layer_b
        
        if min_distance == float('inf'):
            return None
        
        # Convert from internal units to mm
        distance_mm = pcbnew.ToMM(min_distance)
        
        return (distance_mm, closest_point_a, closest_point_b, closest_net_a, closest_net_b, closest_layer_a, closest_layer_b)
    
    def _calculate_creepage(self, domain_a, domain_b, pads_a, pads_b, layer,
                             required_creepage_mm=None):
        """
        Calculate minimum surface path (creepage) between two domains.
        
        Uses Dijkstra pathfinding to find shortest path along PCB surface that:
        - Avoids crossing board edge or slots (infinite creepage)
        - Follows PCB surface on specified layer
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            pads_a: list of pcbnew.PAD, pads in domain A
            pads_b: list of pcbnew.PAD, pads in domain B
            layer: pcbnew layer ID to check on
            required_creepage_mm: float or None, required distance for early-exit
                optimisation — if straight-line edge-to-edge ≥ required, skip
                Dijkstra (slots can only increase the surface path per IEC 60664-1)
        
        Returns:
            tuple: (distance_mm, path_nodes, start_pad, end_pad) or (float('inf'), None, None, None) if no path
        """
        # Configuration limits to prevent hangs
        max_pairs_to_check = 3  # Only check closest pad pairs
        max_pads_per_domain = 5  # Limit pads sampled per domain
        
        # Build obstacle map (copper from all nets except domain A and B)
        obstacles = self._build_obstacle_map_for_layer(domain_a, domain_b, layer)
        
        layer_name = self.board.GetLayerName(layer)
        self.log(f"    Found {len(obstacles)} obstacle(s) on layer")
        
        # Early exit if too many obstacles (would be too slow)
        if len(obstacles) > self.max_obstacles:
            self.log(f"    ⚠️  Too many obstacles ({len(obstacles)} > {self.max_obstacles}), skipping creepage on this layer")
            self.creepage_stats['layers_skipped_obstacles'].append((domain_a, domain_b, layer_name, len(obstacles)))
            return None
        
        if len(obstacles) == 0:
            self.log(f"    No obstacles, using straight-line distance")
        
        # Find shortest creepage path between any pad pair
        min_creepage = float('inf')
        best_path = None
        best_start_pad = None
        best_end_pad = None
        
        # BUG FIX: Filter pads to only those present on the layer being checked.
        # Previously used all-layer pads, causing cross-layer pairs (e.g., F.Cu pad checked
        # against B.Cu pad) on a single-layer creepage pass — producing wrong geometry.
        pads_a_on_layer = [p for p in pads_a if p.IsOnLayer(layer)]
        pads_b_on_layer = [p for p in pads_b if p.IsOnLayer(layer)]

        if not pads_a_on_layer or not pads_b_on_layer:
            self.log(f"    No pads on layer {layer_name} for one or both domains, skipping")
            return None

        # Optimize: only check closest pad pairs (spatial pruning)
        # For each pad in domain A, find closest few pads in domain B
        max_pairs_to_check = min(max_pairs_to_check, len(pads_a_on_layer) * len(pads_b_on_layer))

        pairs_to_check = []
        for pad_a in pads_a_on_layer[:max_pads_per_domain]:  # Limit pads from domain A
            for pad_b in pads_b_on_layer[:max_pads_per_domain]:  # Limit pads from domain B
                # Quick distance estimate
                approx_dist = self.get_distance(pad_a.GetPosition(), pad_b.GetPosition())
                pairs_to_check.append((approx_dist, pad_a, pad_b))
        
        # Sort by distance, check closest pairs first
        pairs_to_check.sort(key=lambda x: x[0])
        pairs_to_check = pairs_to_check[:max_pairs_to_check]
        
        self.log(f"    Checking {len(pairs_to_check)} closest pad pair(s)...")
        
        for idx, (approx_dist, pad_a, pad_b) in enumerate(pairs_to_check):
            self.log(f"      Pair {idx+1}/{len(pairs_to_check)}: approx {pcbnew.ToMM(approx_dist):.2f}mm")
            
            # Pathfinding from pad_a edge to pad_b edge
            path = self._visibility_graph_path(
                start_pad=pad_a,
                goal_pad=pad_b,
                obstacles=obstacles,
                layer=layer,
                required_creepage_mm=required_creepage_mm
            )
            
            if path and path['length'] < min_creepage:
                min_creepage = path['length']
                best_path = path['nodes']
                best_start_pad = pad_a
                best_end_pad = pad_b
                self.log(f"        → New shortest path: {min_creepage:.2f}mm")
        
        return (min_creepage, best_path, best_start_pad, best_end_pad)
    
    def _lookup_required_clearance(self, domain_a, domain_b, voltage_a, voltage_b, reinforced_a, reinforced_b, layer_a=None, layer_b=None):
        """
        Look up required clearance distance from config/tables.
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            voltage_a: float, RMS voltage of domain A
            voltage_b: float, RMS voltage of domain B
            reinforced_a: bool, domain A requires reinforced insulation
            reinforced_b: bool, domain B requires reinforced insulation
            layer_a: pcbnew layer ID (optional), layer of closest pad in domain A
            layer_b: pcbnew layer ID (optional), layer of closest pad in domain B
        
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
                
                # isolation_requirements values are already specified with appropriate margins
                # Do NOT apply safety_margin_factor here (would be double-counting)
                return (clearance, isolation_type, description)
        
        # Step 2: Calculate from voltage difference and standard tables
        voltage_diff = abs(voltage_a - voltage_b)
        configured_standard = self.standard_params.get('standard', 'IEC60664-1')
        
        # Determine which standard/method to use
        standard_used = ""
        if configured_standard == 'IPC2221':
            # User explicitly selected IPC2221 for all voltages
            clearance = self._interpolate_ipc2221_clearance(
                voltage_diff, layer_a, layer_b
            )
            standard_used = "IPC2221"
            self.log(f"    → Using IPC2221 Table 6-1 (voltage {voltage_diff:.1f}V)")
        elif voltage_diff < 12.0:
            # Sub-12V: use IPC2221 functional spacing regardless of standard
            clearance = self._interpolate_ipc2221_clearance(
                voltage_diff, layer_a, layer_b
            )
            standard_used = "IPC2221"
            self.log(f"    → Using IPC2221 functional spacing (voltage {voltage_diff:.1f}V < 12V)")
        else:
            # IEC60664-1 safety spacing for ≥12V (or BOTH)
            overvoltage_cat = self.standard_params.get('overvoltage_category', 'II')
            clearance = self._interpolate_clearance_table(voltage_diff)
            
            # Apply overvoltage category correction factor
            ovc_factors = self.config.get('overvoltage_category_factors', {'I': 0.8, 'II': 1.0, 'III': 1.5, 'IV': 2.0})
            ovc_factor = ovc_factors.get(overvoltage_cat, 1.0)
            if ovc_factor != 1.0:
                clearance *= ovc_factor
                self.log(f"    → Applied OVC-{overvoltage_cat} factor: {ovc_factor:.1f}×")
            
            standard_used = f"IEC60664-1 (OVC-{overvoltage_cat})"
            self.log(f"    → Using IEC60664-1 OVC-{overvoltage_cat} (voltage {voltage_diff:.1f}V ≥ 12V)")
            
            # BOTH mode: also check IPC2221 and use the stricter value
            if configured_standard == 'BOTH':
                ipc_clearance = self._interpolate_ipc2221_clearance(
                    voltage_diff, layer_a, layer_b
                )
                if ipc_clearance > clearance:
                    self.log(f"    → IPC2221 is stricter ({ipc_clearance:.3f}mm > {clearance:.3f}mm), using IPC2221")
                    clearance = ipc_clearance
                    standard_used = f"IPC2221 (stricter than IEC60664-1)"
                else:
                    self.log(f"    → IEC60664-1 is stricter, keeping ({clearance:.3f}mm vs IPC2221 {ipc_clearance:.3f}mm)")
        
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
        
        # Step 6: Apply layer-specific reduction for internal layers (IPC2221 Section 6.2)
        layer_info = ""
        if layer_a is not None and layer_b is not None:
            # Both pads on internal layers get reduced clearance requirement
            is_external_a = self._is_external_layer(layer_a)
            is_external_b = self._is_external_layer(layer_b)
            
            if not is_external_a and not is_external_b:
                # Both internal: apply internal layer reduction factor
                internal_reduction = self.config.get('internal_layer_clearance_factor', 0.6)
                clearance *= internal_reduction
                layer_info = " (internal layers)"
                self.log(f"    → Applied internal layer reduction: {internal_reduction:.1f}×")
            elif is_external_a and is_external_b:
                layer_info = " (external layers)"
            else:
                layer_info = " (mixed layers)"
        
        description = f"{voltage_diff:.1f}V differential, {isolation_type} insulation, {standard_used}{layer_info}"
        
        return (clearance, isolation_type, description)
    
    def _lookup_required_creepage(self, domain_a, domain_b, voltage_a, voltage_b, reinforced_a, reinforced_b):
        """
        Look up required creepage distance from config/tables.
        
        Creepage uses same voltage-based lookup as clearance but with different tables
        based on material group and pollution degree.
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            voltage_a: float, RMS voltage of domain A
            voltage_b: float, RMS voltage of domain B
            reinforced_a: bool, domain A requires reinforced insulation
            reinforced_b: bool, domain B requires reinforced insulation
        
        Returns:
            float: Required creepage in mm
        """
        # Step 1: Check for specific isolation requirement in config
        for req in self.isolation_requirements:
            req_domain_a = req.get('domain_a', '')
            req_domain_b = req.get('domain_b', '')
            
            # Check both directions (A-B or B-A)
            if (req_domain_a == domain_a and req_domain_b == domain_b) or \
               (req_domain_a == domain_b and req_domain_b == domain_a):
                creepage = req.get('min_creepage_mm', 0)
                
                # isolation_requirements values are already specified with appropriate margins
                # Do NOT apply safety_margin_factor here (would be double-counting)
                return creepage
        
        # Step 2: Calculate from voltage difference and creepage tables
        voltage_diff = abs(voltage_a - voltage_b)
        
        # For low voltage (<12V), use same functional spacing as clearance
        if voltage_diff < 12.0:
            # IPC2221 doesn't differentiate clearance vs creepage
            creepage = self._interpolate_clearance_table(voltage_diff)
        else:
            # IEC60664-1 creepage depends on material group and pollution degree
            creepage = self._interpolate_creepage_table(voltage_diff)
        
        # Step 3: Apply reinforced insulation factor (2×)
        if reinforced_a or reinforced_b:
            creepage *= 2.0
        
        # Step 4: Apply safety margin
        safety_factor = self.config.get('safety_margin_factor', 1.2)
        creepage *= safety_factor
        
        return creepage
    
    def _interpolate_creepage_table(self, voltage_rms):
        """
        Interpolate creepage distance from IEC60664-1 tables.
        
        Uses material_group and pollution_degree from config to select correct table.
        
        Args:
            voltage_rms: float, RMS voltage differential
        
        Returns:
            float: Required creepage in mm
        """
        # Get creepage tables from config
        creepage_tables = self.config.get('iec60664_creepage_table', [])
        
        # Get material group and pollution degree from standard params
        material_group = self.standard_params.get('material_group', 'II')
        pollution_degree = self.standard_params.get('pollution_degree', 2)
        
        # Find all matching tables and merge voltages (supports HV extension tables)
        all_matching_voltages = []
        for table in creepage_tables:
            table_material = table.get('material', '')
            table_pollution = table.get('pollution', '')
            
            # Match by material group and pollution degree
            if material_group in table_material and str(pollution_degree) in table_pollution:
                all_matching_voltages.extend(table.get('voltages', []))
        
        if not all_matching_voltages:
            # Fallback: use clearance table with safety factor
            self.log(f"    ⚠️  No matching creepage table for Material Group {material_group}, PD{pollution_degree}")
            return self._interpolate_clearance_table(voltage_rms) * 1.5  # 1.5× safety factor
        
        # Merge and sort by voltage
        voltages = sorted(all_matching_voltages, key=lambda x: x[0])
        
        # Handle 0V case
        if voltage_rms <= 0:
            return voltages[0][1]
        
        # If voltage at or below lowest table entry
        if voltage_rms <= voltages[0][0]:
            return voltages[0][1]
        
        # If voltage above highest table entry — clamp and warn
        if voltage_rms >= voltages[-1][0]:
            max_v = voltages[-1][0]
            max_d = voltages[-1][1]
            if voltage_rms > max_v:
                self.log(
                    f"    ⚠️  WARNING: Voltage {voltage_rms:.0f}V exceeds creepage "
                    f"table maximum ({max_v:.0f}V). Using {max_d:.2f}mm "
                    f"(table max). IEC 60664-1 tables only cover up to "
                    f"{max_v:.0f}V — for higher voltages consult:",
                    force=True,
                )
                self.log(
                    f"       • IEC 60815  (creepage for polluted HV environments)",
                    force=True,
                )
                self.log(
                    f"       • IEC 60071-1 (insulation coordination, withstand voltages)",
                    force=True,
                )
                self.log(
                    f"       • IEC 61936-1 (power installations >1 kV AC clearances)",
                    force=True,
                )
                self.log(
                    f"       ➜ Consider potting compound or conformal/insulation "
                    f"coating to reduce required creepage distances.",
                    force=True,
                )
            return max_d
        
        # Linear interpolation
        for i in range(len(voltages) - 1):
            v_low, d_low = voltages[i]
            v_high, d_high = voltages[i + 1]
            
            if v_low <= voltage_rms <= v_high:
                ratio = (voltage_rms - v_low) / (v_high - v_low)
                creepage = d_low + ratio * (d_high - d_low)
                return creepage
        
        # Fallback
        return voltages[0][1]
    
    def _interpolate_clearance_table(self, voltage_rms):
        """
        Interpolate clearance distance from IEC60664-1/IPC2221 tables.
        
        Uses IPC2221 functional spacing for <12V (non-safety).
        Uses IEC60664-1 safety spacing for ≥12V.
        
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
            # Fallback: use minimum PCB fabrication capability
            return 0.13  # 0.13mm (5 mil) - IPC2221 minimum
        
        # Sort by voltage
        all_voltages.sort(key=lambda x: x[0])
        
        # Handle 0V case (minimum PCB clearance)
        if voltage_rms <= 0:
            return 0.13  # Minimum PCB fab capability (5 mil)
        
        # If voltage at or below lowest table entry, use lowest value
        if voltage_rms <= all_voltages[0][0]:
            return all_voltages[0][1]
        
        # If voltage above highest table entry — clamp and warn
        if voltage_rms >= all_voltages[-1][0]:
            max_v = all_voltages[-1][0]
            max_d = all_voltages[-1][1]
            if voltage_rms > max_v:
                self.log(
                    f"    ⚠️  WARNING: Voltage {voltage_rms:.0f}V exceeds clearance "
                    f"table maximum ({max_v:.0f}V). Using {max_d:.2f}mm "
                    f"(table max). IEC 60664-1 tables only cover up to "
                    f"{max_v:.0f}V — for higher voltages consult:",
                    force=True,
                )
                self.log(
                    f"       • IEC 60071-1 (insulation coordination, withstand voltages)",
                    force=True,
                )
                self.log(
                    f"       • IEC 61936-1 (power installations >1 kV AC clearances)",
                    force=True,
                )
                self.log(
                    f"       ➜ Consider potting compound or conformal/insulation "
                    f"coating to reduce required clearance distances.",
                    force=True,
                )
            return max_d
        
        # Linear interpolation between table entries
        for i in range(len(all_voltages) - 1):
            v_low, d_low = all_voltages[i]
            v_high, d_high = all_voltages[i + 1]
            
            if v_low <= voltage_rms <= v_high:
                # Linear interpolation
                ratio = (voltage_rms - v_low) / (v_high - v_low)
                clearance = d_low + ratio * (d_high - d_low)
                return clearance
        
        # Fallback: use minimum PCB fabrication capability
        return 0.13  # 0.13mm (5 mil) - IPC2221 minimum
    
    def _interpolate_ipc2221_clearance(self, voltage_rms, layer_a=None, layer_b=None):
        """
        Interpolate clearance from IPC2221 spacing tables (Table 6-1).

        Selects the appropriate sub-table based on layer type:
        - Both external + uncoated → "External (B1-B6)" / "Uncoated"
        - Both external + coated   → "External (B1-B6)" / "Coated"
        - Both internal            → "Internal (B2-B4)" / "Embedded"
        - Mixed / unknown          → external uncoated (conservative)

        Falls back to iec60664_clearance_table if no IPC2221 tables are
        defined in the TOML config.

        Args:
            voltage_rms: float, RMS voltage differential
            layer_a: pcbnew layer ID (optional)
            layer_b: pcbnew layer ID (optional)

        Returns:
            float: Required clearance in mm
        """
        ipc_tables = self.config.get('ipc2221_spacing_table', [])
        if not ipc_tables:
            # No IPC2221 tables configured — fall back to IEC60664
            self.log("    ⚠️  No ipc2221_spacing_table in config, falling back to IEC60664 table")
            return self._interpolate_clearance_table(voltage_rms)

        # Determine desired table variant from layer info
        if layer_a is not None and layer_b is not None:
            ext_a = self._is_external_layer(layer_a)
            ext_b = self._is_external_layer(layer_b)
            if not ext_a and not ext_b:
                desired_layer = "Internal"
                desired_condition = "Embedded"
            else:
                desired_layer = "External"
                desired_condition = "Uncoated"  # Conservative default
        else:
            desired_layer = "External"
            desired_condition = "Uncoated"

        # Find best matching table
        selected_table = None
        for table in ipc_tables:
            layer_type = table.get('layer_type', '')
            condition = table.get('condition', '')
            if desired_layer in layer_type and desired_condition in condition:
                selected_table = table
                break

        # Fallback: use first table if no exact match
        if selected_table is None:
            selected_table = ipc_tables[0]
            self.log(f"    ⚠️  No IPC2221 table for {desired_layer}/{desired_condition}, using '{selected_table.get('layer_type', '?')}'")

        voltages = selected_table.get('voltages', [])
        if not voltages:
            return self._interpolate_clearance_table(voltage_rms)

        voltages = sorted(voltages, key=lambda x: x[0])

        if voltage_rms <= 0:
            return voltages[0][1]
        if voltage_rms <= voltages[0][0]:
            return voltages[0][1]
        if voltage_rms >= voltages[-1][0]:
            max_v = voltages[-1][0]
            max_d = voltages[-1][1]
            if voltage_rms > max_v:
                self.log(
                    f"    ⚠️  WARNING: Voltage {voltage_rms:.0f}V exceeds IPC2221 "
                    f"table maximum ({max_v:.0f}V). Using {max_d:.2f}mm "
                    f"(table max). IPC2221 tables only cover up to "
                    f"{max_v:.0f}V — for higher voltages consult:",
                    force=True,
                )
                self.log(
                    f"       • IEC 60071-1 (insulation coordination, withstand voltages)",
                    force=True,
                )
                self.log(
                    f"       • IEC 61936-1 (power installations >1 kV AC clearances)",
                    force=True,
                )
                self.log(
                    f"       ➜ Consider potting compound or conformal/insulation "
                    f"coating to reduce required distances.",
                    force=True,
                )
            return max_d

        for i in range(len(voltages) - 1):
            v_low, d_low = voltages[i]
            v_high, d_high = voltages[i + 1]
            if v_low <= voltage_rms <= v_high:
                ratio = (voltage_rms - v_low) / (v_high - v_low)
                return d_low + ratio * (d_high - d_low)

        return voltages[-1][1]
    
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
        
        # Format violation message from template or default
        template = self.config.get(
            'violation_message_clearance',
            'CLEARANCE: {actual:.2f}mm < {required:.2f}mm ({domainA}-{domainB})'
        )
        msg_line1 = template.format(
            actual=actual_mm, required=required_mm,
            domainA=domain_a, domainB=domain_b
        )
        msg = f"{msg_line1}\n{net_a} ↔ {net_b}"
        
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
    
    def _build_obstacle_map_for_layer(self, domain_a, domain_b, layer):
        """
        Build obstacle map for creepage pathfinding.
        
        Returns all copper shapes on specified layer EXCEPT copper belonging
        to domain_a or domain_b (those are start/goal, not obstacles).
        
        Uses spatial filtering to only include obstacles near the path between domains,
        reducing obstacle count by ~10× for faster pathfinding.
        
        Args:
            domain_a: str, domain name to exclude
            domain_b: str, domain name to exclude
            layer: pcbnew layer ID
        
        Returns:
            list of dict: [{'polygon': SHAPE_POLY_SET, 'net': str}, ...]
        """
        obstacles = []
        
        # Get nets in each domain
        nets_a = set()
        nets_b = set()
        for net_name, domain_info in self.domain_map.items():
            if domain_info['domain_name'] == domain_a:
                nets_a.add(net_name)
            elif domain_info['domain_name'] == domain_b:
                nets_b.add(net_name)
        
        excluded_nets = nets_a | nets_b
        
        # SPATIAL FILTERING: Calculate bounding box from closest pads
        # This dramatically reduces obstacle count (e.g., 881 → ~80)
        pads_a = []
        pads_b = []
        for pad in self.board.GetPads():
            if not pad.IsOnLayer(layer):
                continue
            net = pad.GetNetname()
            if net in nets_a:
                pads_a.append(pad)
            elif net in nets_b:
                pads_b.append(pad)
        
        # Find closest pad pair to determine search area
        if pads_a and pads_b:
            min_dist = float('inf')
            closest_a_pos = None
            closest_b_pos = None
            
            for pad_a in pads_a:
                for pad_b in pads_b:
                    dist = self.get_distance(pad_a.GetPosition(), pad_b.GetPosition())
                    if dist < min_dist:
                        min_dist = dist
                        closest_a_pos = pad_a.GetPosition()
                        closest_b_pos = pad_b.GetPosition()
            
            # Create bounding box with margin around closest pads
            margin = pcbnew.FromMM(self.obstacle_search_margin_mm)
            bbox_min_x = min(closest_a_pos.x, closest_b_pos.x) - margin
            bbox_max_x = max(closest_a_pos.x, closest_b_pos.x) + margin
            bbox_min_y = min(closest_a_pos.y, closest_b_pos.y) - margin
            bbox_max_y = max(closest_a_pos.y, closest_b_pos.y) + margin
            
            # If slot barriers are configured, expand the search box to include
            # their bounding boxes (not the full board — that pulls in too many obstacles).
            # The path needs to route around slot tips, so the bbox must cover those.
            slot_layer_names_cfg = self.config.get('slot_layer_names', ['Edge.Cuts'])
            has_extra_slots = any(n != 'Edge.Cuts' for n in slot_layer_names_cfg)
            if has_extra_slots:
                # Collect slot barrier bboxes so the search area covers their tips
                extra_barrier_ids = set()
                for lname in slot_layer_names_cfg:
                    if lname == 'Edge.Cuts':
                        continue
                    try:
                        lyr_id = self.board.GetLayerID(lname)
                        if lyr_id >= 0:
                            extra_barrier_ids.add(lyr_id)
                    except Exception:
                        pass
                for drawing in self.board.GetDrawings():
                    if drawing.GetLayer() in extra_barrier_ids:
                        db = drawing.GetBoundingBox()
                        bbox_min_x = min(bbox_min_x, db.GetLeft()   - margin)
                        bbox_max_x = max(bbox_max_x, db.GetRight()  + margin)
                        bbox_min_y = min(bbox_min_y, db.GetTop()    - margin)
                        bbox_max_y = max(bbox_max_y, db.GetBottom() + margin)
                for fp in self.board.GetFootprints():
                    for graphic in fp.GraphicalItems():
                        if graphic.GetLayer() in extra_barrier_ids:
                            db = graphic.GetBoundingBox()
                            bbox_min_x = min(bbox_min_x, db.GetLeft()   - margin)
                            bbox_max_x = max(bbox_max_x, db.GetRight()  + margin)
                            bbox_min_y = min(bbox_min_y, db.GetTop()    - margin)
                            bbox_max_y = max(bbox_max_y, db.GetBottom() + margin)
                self.log(f"    Slot detour mode: search box expanded to cover slot barriers")
            
            def in_bounding_box(pos):
                """Check if position is within search area"""
                return (bbox_min_x <= pos.x <= bbox_max_x and 
                        bbox_min_y <= pos.y <= bbox_max_y)
            
            spatial_filtering_enabled = True
            self.log(f"    Spatial filtering: search box {pcbnew.ToMM(bbox_max_x - bbox_min_x):.1f}×{pcbnew.ToMM(bbox_max_y - bbox_min_y):.1f}mm")
        else:
            # Fallback: no spatial filtering if can't find pads
            def in_bounding_box(pos):
                return True
            spatial_filtering_enabled = False
            self.log(f"    Spatial filtering: disabled (no pads found)")
        
        # Collect all pads on this layer (excluding domain nets)
        for pad in self.board.GetPads():
            if not pad.IsOnLayer(layer):
                continue
            
            net_name = pad.GetNetname()
            if net_name in excluded_nets or net_name == "":
                continue
            
            # SPATIAL FILTER: Skip obstacles outside search area
            if not in_bounding_box(pad.GetPosition()):
                continue
            
            # Get pad polygon
            poly = pcbnew.SHAPE_POLY_SET()
            pad.TransformShapeToPolygon(poly, layer, 0, pcbnew.ERROR_INSIDE, False, True)
            
            if poly.OutlineCount() > 0:
                obstacles.append({
                    'polygon': poly,
                    'bbox': poly.BBox(),  # Cache bounding box for fast rejection
                    'net': net_name,
                    'type': 'pad'
                })
        
        # Collect tracks on this layer
        for track in self.board.GetTracks():
            if track.GetLayer() != layer:
                continue
            
            net_name = track.GetNetname()
            if net_name in excluded_nets or net_name == "":
                continue
            
            # SPATIAL FILTER: Skip obstacles outside search area
            track_start = track.GetStart()
            track_end = track.GetEnd()
            # Include track if either endpoint is in bounding box
            if not (in_bounding_box(track_start) or in_bounding_box(track_end)):
                continue
            
            # Convert track to polygon (approximate as rectangle)
            track_poly = pcbnew.SHAPE_POLY_SET()
            track.TransformShapeToPolygon(track_poly, layer, 0, pcbnew.ERROR_INSIDE, False, True)
            
            if track_poly.OutlineCount() > 0:
                obstacles.append({
                    'polygon': track_poly,
                    'bbox': track_poly.BBox(),  # Cache bounding box for fast rejection
                    'net': net_name,
                    'type': 'track'
                })
        
        # Collect zones (copper pours) on this layer
        for zone in self.board.Zones():
            if not zone.IsOnLayer(layer):
                continue
            
            net_name = zone.GetNetname()
            if net_name in excluded_nets or net_name == "":
                continue
            
            # SPATIAL FILTER: Skip zones whose bounding box doesn't overlap the search area.
            # BUG FIX: The previous center-point check missed large copper pours whose
            # center lies outside the search box but whose body extends well into it.
            zone_bbox = zone.GetBoundingBox()
            if spatial_filtering_enabled:
                if not (zone_bbox.GetRight()  >= bbox_min_x and
                        zone_bbox.GetLeft()   <= bbox_max_x and
                        zone_bbox.GetBottom() >= bbox_min_y and
                        zone_bbox.GetTop()    <= bbox_max_y):
                    continue
            
            zone_poly = zone.Outline()
            if zone_poly.OutlineCount() > 0:
                obstacles.append({
                    'polygon': zone_poly,
                    'bbox': zone_poly.BBox(),  # Cache bounding box for fast rejection
                    'net': net_name,
                    'type': 'zone'
                })
        
        # Collect Edge.Cuts and configured slot layers as creepage barriers.
        # A path that crosses a physical board cut has INFINITE creepage — it is impossible
        # without routing around the entire board edge.  These must be hard obstacles.
        #
        # IMPORTANT: spatial filtering is NOT applied here.  A slot that bisects the search
        # area can have both endpoints outside it while still physically blocking the path.
        slot_layer_names = self.config.get('slot_layer_names', ['Edge.Cuts'])
        barrier_layer_ids = {pcbnew.Edge_Cuts}  # Always include the standard KiCad constant
        for lname in slot_layer_names:
            try:
                lyr_id = self.board.GetLayerID(lname)
                if lyr_id >= 0:
                    barrier_layer_ids.add(lyr_id)
                    self.log(f"    Slot barrier layer: '{lname}' → layer ID {lyr_id}")
                else:
                    self.log(f"    WARNING: Slot layer '{lname}' → ID {lyr_id} (not found on board)")
            except Exception as e:
                self.log(f"    WARNING: Slot layer '{lname}' lookup failed: {e}")

        # Debug: list all board layers to help identify naming issues
        self.log(f"    Barrier layer IDs to search: {barrier_layer_ids}")

        edge_cut_count = 0

        # Board-level graphics on Edge.Cuts (lines, arcs, circles defining outline/slots)
        board_drawing_count = 0
        for drawing in self.board.GetDrawings():
            board_drawing_count += 1
            if drawing.GetLayer() not in barrier_layer_ids:
                continue
            self.log(f"    Found barrier drawing on layer {drawing.GetLayer()} "
                     f"({self.board.GetLayerName(drawing.GetLayer())}), "
                     f"shape type: {drawing.GetClass()}")
            draw_poly = pcbnew.SHAPE_POLY_SET()
            try:
                # 0.1mm clearance ensures even hairline/zero-width cuts create a definite
                # polygon barrier wide enough for the intersection tests to catch.
                drawing.TransformShapeToPolygon(
                    draw_poly, drawing.GetLayer(),
                    pcbnew.FromMM(0.1), pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE
                )
            except Exception:
                continue
            if draw_poly.OutlineCount() > 0:
                obstacles.append({
                    'polygon': draw_poly,
                    'bbox': draw_poly.BBox(),
                    'net': '',
                    'type': 'edge_cut',
                    'layer_name': self.board.GetLayerName(drawing.GetLayer())
                })
                edge_cut_count += 1

        # Footprint-level graphics on Edge.Cuts (slots routed into/through component pads)
        for footprint in self.board.GetFootprints():
            for graphic in footprint.GraphicalItems():
                if graphic.GetLayer() not in barrier_layer_ids:
                    continue
                draw_poly = pcbnew.SHAPE_POLY_SET()
                try:
                    graphic.TransformShapeToPolygon(
                        draw_poly, graphic.GetLayer(),
                        pcbnew.FromMM(0.1), pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE
                    )
                except Exception:
                    continue
                if draw_poly.OutlineCount() > 0:
                    obstacles.append({
                        'polygon': draw_poly,
                        'bbox': draw_poly.BBox(),
                        'net': '',
                        'type': 'edge_cut',
                        'layer_name': self.board.GetLayerName(graphic.GetLayer())
                    })
                    edge_cut_count += 1

        self.log(f"    Total board drawings scanned: {board_drawing_count}")
        if edge_cut_count > 0:
            self.log(f"    Added {edge_cut_count} Edge.Cuts/slot barrier(s) (infinite-creepage boundaries)")
        else:
            self.log(f"    WARNING: No slot barriers found! Check slot_layer_names in TOML")

        # Count obstacle types for diagnostics
        type_counts = {}
        for obs in obstacles:
            t = obs.get('type', 'unknown')
            type_counts[t] = type_counts.get(t, 0) + 1
        self.log(f"    Obstacle types: {type_counts}")

        filtering_status = "with spatial filtering" if spatial_filtering_enabled else "no filtering"
        self.log(f"    Built obstacle map ({filtering_status}): {len(obstacles)} obstacles on layer {self.board.GetLayerName(layer)}")
        return obstacles
    
    def _line_intersects_polygon(self, p1, p2, polygon, bbox=None):
        """
        Check if line segment (p1, p2) intersects or passes through polygon.
        
        Args:
            p1: pcbnew.VECTOR2I, line start
            p2: pcbnew.VECTOR2I, line end
            polygon: SHAPE_POLY_SET
            bbox: optional pre-computed bounding box for fast rejection
        
        Returns:
            bool: True if intersection exists
        """
        # Fast rejection: check bounding box first (if provided)
        if bbox and not self._line_intersects_bbox(p1, p2, bbox):
            return False
        
        # Check if either endpoint is inside polygon
        if polygon.Contains(p1) or polygon.Contains(p2):
            return True
        
        # Check if line segment crosses polygon edges
        for outline_idx in range(polygon.OutlineCount()):
            outline = polygon.Outline(outline_idx)
            point_count = outline.PointCount()
            
            for i in range(point_count):
                edge_start = outline.CPoint(i)
                edge_end = outline.CPoint((i + 1) % point_count)
                
                # Check segment-segment intersection
                if self._segments_intersect(p1, p2, edge_start, edge_end):
                    return True
        
        return False
    
    def _segments_intersect(self, p1, p2, p3, p4):
        """
        Check if line segment (p1,p2) intersects line segment (p3,p4).
        
        Uses cross-product method (CCW test).
        
        Args:
            p1, p2: pcbnew.VECTOR2I, first segment
            p3, p4: pcbnew.VECTOR2I, second segment
        
        Returns:
            bool: True if segments intersect
        """
        def ccw(a, b, c):
            """Check if three points are counter-clockwise"""
            return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x)
        
        # Segments intersect if endpoints are on opposite sides
        return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))
    
    def _line_intersects_bbox(self, p1, p2, bbox):
        """
        Fast bounding box intersection check (Cohen-Sutherland).
        Rejects 70-80% of line-polygon checks instantly.
        
        Args:
            p1, p2: pcbnew.VECTOR2I, line endpoints
            bbox: pcbnew.BOX2I, bounding box
        
        Returns:
            bool: True if line might intersect bbox (conservative)
        """
        # Get line bounding box
        line_min_x = min(p1.x, p2.x)
        line_max_x = max(p1.x, p2.x)
        line_min_y = min(p1.y, p2.y)
        line_max_y = max(p1.y, p2.y)
        
        # Fast rejection: no overlap if bboxes don't intersect
        if (line_max_x < bbox.GetLeft() or 
            line_min_x > bbox.GetRight() or
            line_max_y < bbox.GetTop() or
            line_min_y > bbox.GetBottom()):
            return False
        
        return True

    def _get_pad_edge_point(self, pad, target_pos, layer):
        """
        Return the point on the pad's copper boundary that is closest to target_pos.

        IEC 60664-1 defines creepage as the shortest path along the insulating surface
        between two CONDUCTIVE EDGES, not conductor centres.  Using pad centres can
        under-estimate creepage by half the pad diagonal on each side.

        Implementation: iterate every edge segment of the pad polygon outline and find
        the globally closest point on the boundary to target_pos (closest-point-on-
        segment projection).  Falls back to pad centre if the polygon is unavailable.

        Args:
            pad:        pcbnew.PAD
            target_pos: pcbnew.VECTOR2I  – the other pad's reference position
            layer:      pcbnew layer ID used for polygon calculation

        Returns:
            pcbnew.VECTOR2I: boundary point on the pad polygon closest to target_pos
        """
        poly = self._get_pad_polygon(pad, layer)
        if poly.OutlineCount() == 0:
            return pad.GetPosition()  # Fallback: polygon unavailable

        outline = poly.Outline(0)
        point_count = outline.PointCount()
        if point_count == 0:
            return pad.GetPosition()

        min_dist_sq = float('inf')
        closest = pad.GetPosition()

        for i in range(point_count):
            seg_start = outline.CPoint(i)
            seg_end   = outline.CPoint((i + 1) % point_count)

            # Project target_pos onto the edge segment, clamped to [0, 1]
            dx = seg_end.x - seg_start.x
            dy = seg_end.y - seg_start.y
            len_sq = dx * dx + dy * dy
            if len_sq == 0:
                candidate = seg_start
            else:
                t = ((target_pos.x - seg_start.x) * dx +
                     (target_pos.y - seg_start.y) * dy) / len_sq
                t = max(0.0, min(1.0, t))
                candidate = pcbnew.VECTOR2I(
                    int(seg_start.x + t * dx),
                    int(seg_start.y + t * dy)
                )

            # Use squared distance to avoid sqrt in comparisons
            ddx = candidate.x - target_pos.x
            ddy = candidate.y - target_pos.y
            dist_sq = ddx * ddx + ddy * ddy
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest = candidate

        return closest

    def _find_blocking_slots(self, point_a, point_b, slot_obstacles):
        """
        Find all slot obstacles that block a straight line between two points.

        Args:
            point_a: pcbnew.VECTOR2I
            point_b: pcbnew.VECTOR2I
            slot_obstacles: list of obstacle dicts (edge_cut type only)

        Returns:
            list of obstacle dicts that block the line
        """
        blockers = []
        for obs in slot_obstacles:
            poly = obs['polygon']
            bbox = obs.get('bbox')
            if self._line_intersects_polygon(point_a, point_b, poly, bbox):
                blockers.append(obs)
        return blockers

    def _path_crosses_slot(self, point_a, point_b, slot_obstacles):
        """
        Check if straight line from point_a to point_b intersects any slot.
        For creepage, only physical slots/cutouts are barriers — pads, zones,
        and other copper features are surface features the path travels along.

        Args:
            point_a: pcbnew.VECTOR2I
            point_b: pcbnew.VECTOR2I
            slot_obstacles: list of obstacle dicts (edge_cut type only)

        Returns:
            bool: True if path crosses a slot, False otherwise
        """
        for obs in slot_obstacles:
            poly = obs['polygon']
            bbox = obs.get('bbox')
            if self._line_intersects_polygon(point_a, point_b, poly, bbox):
                return True
        return False

    def _get_slot_waypoints(self, slot_obstacles, boundary_obstacles=None):
        """
        Extract offset waypoints around key corners of slot obstacles.
        Waypoints are filtered against ALL slot polygons (including board
        outline) to ensure they are in valid (non-slot, on-board) positions.

        Args:
            slot_obstacles: list of obstacle dicts — internal slots only
                (Edge.Cuts should NOT be passed here; it's the board outline)
            boundary_obstacles: optional list of Edge.Cuts obstacle dicts
                used only for filtering waypoints that land off-board

        Returns:
            dict: {obstacle_id: [list of VECTOR2I waypoints]} keyed by id(obs)
        """
        offset_iu = pcbnew.FromMM(0.1)  # 0.1mm offset — matches polygon buffer, tight routing
        diag = int(offset_iu * 0.707)   # diagonal offset
        # 8 directions: cardinal + diagonal
        offsets = [
            (offset_iu, 0), (-offset_iu, 0),
            (0, offset_iu), (0, -offset_iu),
            (diag, diag), (diag, -diag),
            (-diag, diag), (-diag, -diag),
        ]

        # Collect all slot polygons for cross-slot filtering
        # Include internal slot polys + optional Edge.Cuts boundary polys
        all_polys = [obs['polygon'] for obs in slot_obstacles]
        if boundary_obstacles:
            all_polys.extend(obs['polygon'] for obs in boundary_obstacles)

        slot_wp_map = {}
        for obs in slot_obstacles:
            # Use bounding box extremities instead of angle-based key vertices.
            # Slot polygons are rounded rectangles (line + buffer). The angle-based
            # approach picks vertices mid-side (where straight meets curve), missing
            # the actual tips where the path needs to go around.
            # The 4 bbox extremes (left, right, top, bottom midpoints) plus the
            # 4 bbox corners give complete coverage of slot tip waypoints.
            bbox = obs.get('bbox')
            if not bbox:
                continue
            cx = (bbox.GetLeft() + bbox.GetRight()) // 2
            cy = (bbox.GetTop() + bbox.GetBottom()) // 2
            tip_points = [
                pcbnew.VECTOR2I(bbox.GetLeft(), cy),    # left tip
                pcbnew.VECTOR2I(bbox.GetRight(), cy),   # right tip
                pcbnew.VECTOR2I(cx, bbox.GetTop()),     # top tip
                pcbnew.VECTOR2I(cx, bbox.GetBottom()),  # bottom tip
                pcbnew.VECTOR2I(bbox.GetLeft(), bbox.GetTop()),      # top-left corner
                pcbnew.VECTOR2I(bbox.GetRight(), bbox.GetTop()),     # top-right corner
                pcbnew.VECTOR2I(bbox.GetLeft(), bbox.GetBottom()),   # bottom-left corner
                pcbnew.VECTOR2I(bbox.GetRight(), bbox.GetBottom()),  # bottom-right corner
            ]
            wps = []
            seen = set()
            for kv in tip_points:
                for dx, dy in offsets:
                    pt = pcbnew.VECTOR2I(kv.x + dx, kv.y + dy)
                    key = (pt.x, pt.y)
                    if key not in seen:
                        seen.add(key)
                        # Filter: must not be inside ANY slot polygon
                        inside_any = False
                        for poly in all_polys:
                            if poly.Contains(pt):
                                inside_any = True
                                break
                        if not inside_any:
                            wps.append(pt)
            slot_wp_map[id(obs)] = wps
        return slot_wp_map

    def _dijkstra_waypoint_path(self, start, goal, slot_obstacles, slot_wp_map):
        """
        Find shortest slot-avoiding path using Dijkstra on the waypoint graph.

        Nodes = {start, goal} ∪ all waypoints from slot_wp_map.
        An edge exists between two nodes iff the straight line between them
        does not cross any slot obstacle.  Edge weight = Euclidean distance.

        This replaces the recursive detour approach which suffered from
        exponential branching on dense waypoint sets.

        Returns:
            dict: {'length_iu': int, 'nodes': [VECTOR2I, ...]} or None
        """
        # Collect unique waypoints
        all_wps = []
        seen = set()
        for wps in slot_wp_map.values():
            for wp in wps:
                key = (wp.x, wp.y)
                if key not in seen:
                    seen.add(key)
                    all_wps.append(wp)

        nodes = [start, goal] + all_wps
        n = len(nodes)

        # Build adjacency list — O(N²) visibility checks against slots only
        adj = [[] for _ in range(n)]
        vis_checks = 0
        for i in range(n):
            for j in range(i + 1, n):
                vis_checks += 1
                if not self._path_crosses_slot(nodes[i], nodes[j], slot_obstacles):
                    d = self.get_distance(nodes[i], nodes[j])
                    adj[i].append((j, d))
                    adj[j].append((i, d))

        # Dijkstra from node 0 (start) to node 1 (goal)
        dist = [float('inf')] * n
        prev = [-1] * n
        dist[0] = 0
        pq = [(0, 0)]  # (distance, node_index)

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if u == 1:  # reached goal
                break
            for v, w in adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))

        if dist[1] == float('inf'):
            self.log(f"        Dijkstra: no path found ({n} nodes, {vis_checks} visibility checks)")
            return None

        # Reconstruct path
        path = []
        cur = 1
        while cur != -1:
            path.append(nodes[cur])
            cur = prev[cur]
        path.reverse()

        edge_count = sum(len(a) for a in adj) // 2
        self.log(f"        Dijkstra: path found ({n} nodes, {edge_count} edges, "
                 f"{vis_checks} visibility checks)")
        return {'length_iu': dist[1], 'nodes': path}

    def _visibility_graph_path(self, start_pad, goal_pad, obstacles, layer,
                                required_creepage_mm=None):
        """
        Find shortest surface path using a visibility-graph + Dijkstra algorithm.

        For creepage, only physical slots/cutouts are barriers that the surface
        path must go around.  Pads, zones, and other copper features are on the
        board surface — the creepage path travels along them, not around them.

        Strategy:
        0. Early exit — straight-line ≥ required → PASS (slots only add length).
        1. Direct line — if no slot blocks it, return straight distance.
        2. Full visibility-graph + Dijkstra for slot detour.

        Args:
            start_pad: pcbnew.PAD
            goal_pad: pcbnew.PAD
            obstacles: list of obstacle dicts
            layer: pcbnew layer ID
            required_creepage_mm: float or None, if provided enables early-exit
                when straight-line distance already meets the requirement
                (per IEC 60664-1, slots can only increase the surface path)

        Returns:
            dict: {'length': float (mm), 'nodes': [VECTOR2I, ...]} or None
        """
        # IEC 60664-1: measure from conductive EDGE, not pad centre
        start = self._get_pad_edge_point(start_pad, goal_pad.GetPosition(), layer)
        goal  = self._get_pad_edge_point(goal_pad,  start_pad.GetPosition(), layer)

        # ------------------------------------------------------------------
        # STEP 0: Early exit — straight-line distance ≥ required creepage
        # Per IEC 60664-1, creepage is measured along the insulating surface.
        # Slots/cutouts can only INCREASE the surface path (force detours).
        # Therefore if the straight-line edge-to-edge distance already meets
        # the requirement, the actual creepage is guaranteed to pass — no
        # need to run the expensive Dijkstra pathfinder.
        # ------------------------------------------------------------------
        straight_line_mm = pcbnew.ToMM(self.get_distance(start, goal))
        if required_creepage_mm is not None and straight_line_mm >= required_creepage_mm:
            self.log(f"        Straight-line edge-to-edge: {straight_line_mm:.2f}mm "
                     f"≥ required {required_creepage_mm:.2f}mm")
            self.log(f"        → Skipping slot analysis (slots can only increase path)")
            return {'length': straight_line_mm, 'nodes': [start, goal]}

        # ------------------------------------------------------------------
        # Extract slot-only obstacles (the only real barriers for creepage)
        # Separate into:
        #   - edge_cuts_barriers: Edge.Cuts = external board outline
        #   - internal_slots: all other .Cuts layers = internal slots/cutouts
        # Edge.Cuts defines the board boundary — paths can't go off-board.
        # Internal slots are the obstacles the path must detour around.
        # ------------------------------------------------------------------
        all_slot_obstacles = [obs for obs in obstacles if obs.get('type') == 'edge_cut']
        edge_cuts_barriers = [obs for obs in all_slot_obstacles
                              if obs.get('layer_name') == 'Edge.Cuts']
        internal_slots = [obs for obs in all_slot_obstacles
                          if obs.get('layer_name') != 'Edge.Cuts']
        self.log(f"        Pathfinder: {len(all_slot_obstacles)} slot barriers "
                 f"({len(edge_cuts_barriers)} Edge.Cuts board outline, "
                 f"{len(internal_slots)} internal slots), "
                 f"{len(obstacles)} total obstacles")

        # ------------------------------------------------------------------
        # STEP 1: Direct line — no slot crossing means straight distance
        # Check against ALL barriers (board outline + internal slots)
        # ------------------------------------------------------------------
        crosses = self._path_crosses_slot(start, goal, all_slot_obstacles)
        self.log(f"        Direct line crosses slot: {crosses}")
        self.log(f"        Start: ({pcbnew.ToMM(start.x):.2f}, {pcbnew.ToMM(start.y):.2f})mm, "
                 f"Goal: ({pcbnew.ToMM(goal.x):.2f}, {pcbnew.ToMM(goal.y):.2f})mm")
        if not crosses:
            distance = pcbnew.ToMM(self.get_distance(start, goal))
            return {'length': distance, 'nodes': [start, goal]}

        # Check if only Edge.Cuts blocks (not internal slots)
        crosses_internal = self._path_crosses_slot(start, goal, internal_slots)
        if not crosses_internal:
            # Direct line only crosses the board outline — pads may be on
            # separate board sections or the board has a concave outline.
            # Still need to route around the board edge, so fall through.
            self.log(f"        Direct line crosses board outline only (no internal slots)")

        # ------------------------------------------------------------------
        # Collect waypoints ONLY around internal slots (not Edge.Cuts).
        # Edge.Cuts is the board boundary — waypoints around it would be
        # off-board and unreachable.  Internal slots are the real obstacles
        # the creepage path must detour around.
        # ------------------------------------------------------------------
        for si, s in enumerate(internal_slots):
            bb = s.get('bbox')
            if bb:
                self.log(f"        Slot[{si}]: ({pcbnew.ToMM(bb.GetLeft()):.2f}, "
                         f"{pcbnew.ToMM(bb.GetTop()):.2f})-"
                         f"({pcbnew.ToMM(bb.GetRight()):.2f}, "
                         f"{pcbnew.ToMM(bb.GetBottom()):.2f})mm")
        slot_wp_map = self._get_slot_waypoints(internal_slots,
                                                 boundary_obstacles=edge_cuts_barriers)

        total_wps = sum(len(v) for v in slot_wp_map.values())
        self.log(f"        Dijkstra waypoint graph: {len(internal_slots)} internal slots, "
                 f"{total_wps} waypoints (Edge.Cuts excluded from waypoints)")

        # ------------------------------------------------------------------
        # STEP 2: Dijkstra on waypoint graph
        # Nodes = {start, goal} ∪ all internal-slot waypoints.
        # Edges = pairs of nodes whose line doesn't cross any slot.
        # All slot obstacles (including Edge.Cuts) are used as barriers —
        # you still can't cross the board outline.
        # O(N²) visibility checks where N = waypoints + 2.
        # ------------------------------------------------------------------
        result = self._dijkstra_waypoint_path(
            start, goal, all_slot_obstacles, slot_wp_map)

        if result:
            length_mm = pcbnew.ToMM(result['length_iu'])
            hops = len(result['nodes']) - 2
            self.log(f"        Dijkstra found: {length_mm:.2f}mm "
                     f"({hops} intermediate waypoint{'s' if hops != 1 else ''})")
            for ni, node in enumerate(result['nodes']):
                label = "START" if ni == 0 else ("GOAL" if ni == len(result['nodes']) - 1 else f"WP{ni}")
                self.log(f"          {label}: ({pcbnew.ToMM(node.x):.2f}, {pcbnew.ToMM(node.y):.2f})mm")
            return {'length': length_mm, 'nodes': result['nodes']}

        # ------------------------------------------------------------------
        # STEP 3: Dijkstra failed — no path exists through waypoints
        # ------------------------------------------------------------------
        self.log(f"        Dijkstra: no path found through waypoints")
        self.log(f"        No valid creepage path (slot/cutout breaks path)")
        return None

    def _draw_debug_creepage_path(self, domain_a, domain_b, actual_mm, required_mm, path, start_pad, end_pad, create_group_func):
        """
        Draw the shortest creepage path as a debug polyline on the marker layer.
        Called when creepage PASSES and draw_creepage_path is enabled.
        """
        group = create_group_func(self.board, "CreepagePath", f"{domain_a}_{domain_b}", 0)
        general = self.auditor.config.get('general', {}) if self.auditor else {}
        line_width = pcbnew.FromMM(general.get('marker_line_width_mm', 0.1))

        # Draw path segments
        for i in range(len(path) - 1):
            seg = pcbnew.PCB_SHAPE(self.board)
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(path[i])
            seg.SetEnd(path[i + 1])
            seg.SetLayer(self.marker_layer)
            seg.SetWidth(line_width)
            self.board.Add(seg)
            group.AddItem(seg)

        # Add length label at path midpoint
        mid_idx = len(path) // 2
        mid_pt = path[mid_idx]
        hops = len(path) - 2
        start_net = start_pad.GetNetname()
        end_net = end_pad.GetNetname()
        label = (f"CREEPAGE: {actual_mm:.2f}mm (req {required_mm:.2f}mm) PASS\n"
                 f"{domain_a}-{domain_b}, {hops} waypoint{'s' if hops != 1 else ''}\n"
                 f"{start_net} ↔ {end_net}")
        text_size = pcbnew.FromMM(general.get('marker_text_size_mm', 0.5))
        text_offset = pcbnew.FromMM(general.get('marker_text_offset_mm', 1.2))
        txt = pcbnew.PCB_TEXT(self.board)
        txt.SetText(label)
        txt.SetPosition(pcbnew.VECTOR2I(mid_pt.x, mid_pt.y - text_offset))
        txt.SetLayer(self.marker_layer)
        txt.SetTextSize(pcbnew.VECTOR2I(text_size, text_size))
        txt.SetTextThickness(line_width)
        self.board.Add(txt)
        group.AddItem(txt)

        self.log(f"      Debug: drew creepage path ({len(path)} nodes, {hops} waypoints)")

    def _draw_plain_segment(self, pt_a, pt_b, group):
        """Draw a plain line segment on the marker layer (no arrowhead)."""
        general = self.auditor.config.get('general', {})
        line_width = pcbnew.FromMM(general.get('marker_line_width_mm', 0.1))
        seg = pcbnew.PCB_SHAPE(self.board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pt_a)
        seg.SetEnd(pt_b)
        seg.SetLayer(self.marker_layer)
        seg.SetWidth(line_width)
        self.board.Add(seg)
        group.AddItem(seg)

    def _create_creepage_violation_marker(self, domain_a, domain_b, actual_mm, required_mm, path, start_pad, end_pad, create_group_func):
        """
        Draw violation marker for insufficient creepage.
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            actual_mm: float, actual creepage measured
            required_mm: float, required creepage from tables
            path: list of pcbnew.VECTOR2I, creepage path nodes
            start_pad: pcbnew.PAD, start pad
            end_pad: pcbnew.PAD, end pad
            create_group_func: Function to create violation groups
        """
        self.violation_count += 1
        violation_group = create_group_func(self.board, "Creepage", f"{domain_a}_{domain_b}", self.violation_count)
        
        # Format violation message
        start_net = start_pad.GetNetname()
        end_net = end_pad.GetNetname()
        template = self.config.get(
            'violation_message_creepage',
            'CREEPAGE: {actual:.2f}mm < {required:.2f}mm ({domainA}-{domainB})'
        )
        msg_line1 = template.format(
            actual=actual_mm, required=required_mm,
            domainA=domain_a, domainB=domain_b
        )
        msg = f"{msg_line1}\n{start_net} ↔ {end_net}"
        
        # Draw marker at path midpoint
        if path and len(path) >= 2:
            midpoint_idx = len(path) // 2
            midpoint = path[midpoint_idx]
        else:
            # Fallback to pad midpoint
            midpoint_x = (start_pad.GetPosition().x + end_pad.GetPosition().x) // 2
            midpoint_y = (start_pad.GetPosition().y + end_pad.GetPosition().y) // 2
            midpoint = pcbnew.VECTOR2I(midpoint_x, midpoint_y)
        
        self.draw_marker(self.board, midpoint, msg, self.marker_layer, violation_group)
        
        # Draw creepage path as a clean polyline:
        #   - plain line segments for all intermediate hops
        #   - single arrowhead + length label only on the final segment
        if path and len(path) >= 2:
            for i in range(len(path) - 2):  # all but last segment
                self._draw_plain_segment(path[i], path[i + 1], violation_group)
            # Last segment: arrowhead marks endpoint, label shows measured length
            self.draw_arrow(self.board, path[-2], path[-1], f"{actual_mm:.2f}mm", self.marker_layer, violation_group)
        else:
            # No path nodes — fall back to a direct straight arrow between pads
            self.draw_arrow(self.board, start_pad.GetPosition(), end_pad.GetPosition(), f"{actual_mm:.2f}mm", self.marker_layer, violation_group)
        
        # Log to report
        self.log(f"  ❌ CREEPAGE VIOLATION: {domain_a} ({start_net}) ↔ {domain_b} ({end_net})", force=True)
        self.log(f"     Actual: {actual_mm:.2f}mm, Required: {required_mm:.2f}mm", force=True)


# Module metadata
__version__ = "1.0.0"
__author__ = "EMC Auditor Plugin"
__description__ = "Clearance and Creepage checking for IEC60664-1 / IPC2221 compliance"
