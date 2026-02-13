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
        self.max_obstacles = 100  # Maximum obstacles per layer for creepage pathfinding
    
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
        check_creepage_enabled = self.config.get('check_creepage', False)
        if check_creepage_enabled:
            self.log("Phase 2: Clearance (air gap) + Creepage (surface path) checking", force=True)
        else:
            self.log("Phase 1: Clearance (air gap) only - creepage disabled", force=True)
        
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
                
                # Log number of comparisons to help user understand performance
                num_comparisons = len(features_a) * len(features_b)
                self.log(f"  Comparing {len(features_a)} × {len(features_b)} = {num_comparisons} pad pair(s)")
                
                # Calculate minimum clearance
                result = self._calculate_clearance(features_a, features_b)
                if not result:
                    self.log("  ⚠️  Could not calculate clearance")
                    continue
                
                actual_mm, point1, point2, net_a, net_b, layer_a, layer_b = result
                
                # Get voltage and reinforced flags from first feature in each domain
                voltage_a = features_a[0][4]  # voltage_rms from feature tuple
                voltage_b = features_b[0][4]
                reinforced_a = features_a[0][5]  # reinforced flag
                reinforced_b = features_b[0][5]
                
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
                    self.log("  ✓ PASS")
                
                # Step 6: Check creepage (if enabled)
                if self.config.get('check_creepage', False):
                    self.creepage_stats['pairs_checked'] += 1
                    self.log("\n  --- Checking Creepage (Surface Path) ---")
                    
                    # Get pads for each domain (needed for pathfinding)
                    pads_a = [f[1] for f in features_a]  # Extract PAD objects from feature tuples (index 1)
                    pads_b = [f[1] for f in features_b]
                    
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
                                domain_a, domain_b, pads_a, pads_b, layer
                            )
                            
                            if creepage_result:
                                actual_creepage_mm, path, start_pad, end_pad = creepage_result
                                
                                if actual_creepage_mm == float('inf'):
                                    self.log(f"      No valid creepage path (slot/cutout breaks path)")
                                    self.creepage_stats['layers_no_path'].append((domain_a, domain_b, layer_name))
                                    continue
                                
                                # Lookup required creepage
                                required_creepage_mm = self._lookup_required_creepage(
                                    domain_a, domain_b, voltage_a, voltage_b, reinforced_a, reinforced_b
                                )
                                
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
                                    self.log(f"      ✓ PASS")
                            else:
                                self.log(f"      Could not calculate creepage")
        
        # Report creepage checking summary if enabled
        if self.config.get('check_creepage', False):
            self._report_creepage_summary()
        
        self.log(f"\n=== CLEARANCE & CREEPAGE CHECK COMPLETE: {pairs_checked} pair(s) checked, {self.violation_count} violation(s) ===", force=True)
        if self.config.get('check_creepage', False):
            self.log(f"    Clearance violations: {self.clearance_violations}")
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
    
    def _report_creepage_summary(self):
        """Print summary of creepage checking results and statistics"""
        self.log(f"\n--- Creepage Checking Summary ---")
        
        if not self.config.get('check_creepage', False):
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
    
    def _calculate_creepage(self, domain_a, domain_b, pads_a, pads_b, layer):
        """
        Calculate minimum surface path (creepage) between two domains.
        
        Uses A* pathfinding to find shortest path along PCB surface that:
        - Avoids crossing copper from other nets (obstacles)
        - Does not cross board edge or slots (infinite creepage)
        - Follows PCB surface on specified layer
        
        Args:
            domain_a: str, domain name
            domain_b: str, domain name
            pads_a: list of pcbnew.PAD, pads in domain A
            pads_b: list of pcbnew.PAD, pads in domain B
            layer: pcbnew layer ID to check on
        
        Returns:
            tuple: (distance_mm, path_nodes, start_pad, end_pad) or (float('inf'), None, None, None) if no path
        """
        import heapq
        
        # Configuration - AGGRESSIVE limits to prevent hangs
        max_iterations = 1000  # Reduced from 10000 - A* iterations per pad pair
        fast_rejection_factor = 2.0  # Skip if clearance already sufficient
        max_pairs_to_check = 5  # Reduced from 20 - only check closest pad pairs
        max_pads_per_domain = 5  # Reduced from 10 - limit pads sampled
        
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
        
        # Optimize: only check closest pad pairs (spatial pruning)
        # For each pad in domain A, find closest few pads in domain B
        max_pairs_to_check = min(max_pairs_to_check, len(pads_a) * len(pads_b))
        
        pairs_to_check = []
        for pad_a in pads_a[:max_pads_per_domain]:  # Limit pads from domain A
            for pad_b in pads_b[:max_pads_per_domain]:  # Limit pads from domain B
                # Quick distance estimate
                approx_dist = self.get_distance(pad_a.GetPosition(), pad_b.GetPosition())
                pairs_to_check.append((approx_dist, pad_a, pad_b))
        
        # Sort by distance, check closest pairs first
        pairs_to_check.sort(key=lambda x: x[0])
        pairs_to_check = pairs_to_check[:max_pairs_to_check]
        
        self.log(f"    Checking {len(pairs_to_check)} closest pad pair(s)...")
        
        for idx, (approx_dist, pad_a, pad_b) in enumerate(pairs_to_check):
            self.log(f"      Pair {idx+1}/{len(pairs_to_check)}: approx {pcbnew.ToMM(approx_dist):.2f}mm")
            
            # A* pathfinding from pad_a edge to pad_b edge
            path = self._astar_surface_path(
                start_pad=pad_a,
                goal_pad=pad_b,
                obstacles=obstacles,
                layer=layer,
                max_iterations=max_iterations
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
        
        # Determine which standard/method to use based on voltage
        standard_used = ""
        if voltage_diff < 12.0:
            # IPC2221 functional spacing for sub-12V
            clearance = self._interpolate_clearance_table(voltage_diff)
            standard_used = "IPC2221"
            self.log(f"    → Using IPC2221 functional spacing (voltage {voltage_diff:.1f}V < 12V)")
        else:
            # IEC60664-1 safety spacing for ≥12V
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
        
        # Find matching table
        selected_table = None
        for table in creepage_tables:
            table_material = table.get('material', '')
            table_pollution = table.get('pollution', '')
            
            # Match by material group and pollution degree
            if material_group in table_material and str(pollution_degree) in table_pollution:
                selected_table = table
                break
        
        if not selected_table:
            # Fallback: use first table or clearance table
            self.log(f"    ⚠️  No matching creepage table for Material Group {material_group}, PD{pollution_degree}")
            # Use clearance as conservative fallback (creepage typically > clearance)
            return self._interpolate_clearance_table(voltage_rms) * 1.5  # 1.5× safety factor
        
        # Get voltage list from selected table
        voltages = selected_table.get('voltages', [])
        
        if not voltages:
            # Fallback
            return self._interpolate_clearance_table(voltage_rms) * 1.5
        
        # Sort by voltage
        voltages.sort(key=lambda x: x[0])
        
        # Handle 0V case
        if voltage_rms <= 0:
            return voltages[0][1]
        
        # If voltage at or below lowest table entry
        if voltage_rms <= voltages[0][0]:
            return voltages[0][1]
        
        # If voltage above highest table entry
        if voltage_rms >= voltages[-1][0]:
            return voltages[-1][1]
        
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
        
        # Fallback: use minimum PCB fabrication capability
        return 0.13  # 0.13mm (5 mil) - IPC2221 minimum
    
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
    
    def _build_obstacle_map_for_layer(self, domain_a, domain_b, layer):
        """
        Build obstacle map for creepage pathfinding.
        
        Returns all copper shapes on specified layer EXCEPT copper belonging
        to domain_a or domain_b (those are start/goal, not obstacles).
        
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
        
        # Collect all pads on this layer (excluding domain nets)
        for pad in self.board.GetPads():
            if not pad.IsOnLayer(layer):
                continue
            
            net_name = pad.GetNetname()
            if net_name in excluded_nets or net_name == "":
                continue
            
            # Get pad polygon
            poly = pcbnew.SHAPE_POLY_SET()
            pad.TransformShapeToPolygon(poly, layer, 0, pcbnew.ERROR_INSIDE, False, True)
            
            if poly.OutlineCount() > 0:
                obstacles.append({
                    'polygon': poly,
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
            
            # Convert track to polygon (approximate as rectangle)
            track_poly = pcbnew.SHAPE_POLY_SET()
            track.TransformShapeToPolygon(track_poly, layer, 0, pcbnew.ERROR_INSIDE, False, True)
            
            if track_poly.OutlineCount() > 0:
                obstacles.append({
                    'polygon': track_poly,
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
            
            zone_poly = zone.Outline()
            if zone_poly.OutlineCount() > 0:
                obstacles.append({
                    'polygon': zone_poly,
                    'net': net_name,
                    'type': 'zone'
                })
        
        self.log(f"    Built obstacle map: {len(obstacles)} obstacles on layer {self.board.GetLayerName(layer)}")
        return obstacles
    
    def _path_crosses_obstacle(self, point_a, point_b, obstacles):
        """
        Check if straight line from point_a to point_b intersects any obstacle.
        
        Args:
            point_a: pcbnew.VECTOR2I, start point
            point_b: pcbnew.VECTOR2I, end point
            obstacles: list of obstacle dicts
        
        Returns:
            bool: True if path crosses obstacle, False otherwise
        """
        # Fast rejection: if no obstacles, path is clear
        if len(obstacles) == 0:
            return False
        
        # Check each obstacle
        for obstacle in obstacles:
            poly = obstacle['polygon']
            
            # Check if line segment intersects polygon
            if self._line_intersects_polygon(point_a, point_b, poly):
                return True
        
        return False
    
    def _line_intersects_polygon(self, p1, p2, polygon):
        """
        Check if line segment (p1, p2) intersects or passes through polygon.
        
        Args:
            p1: pcbnew.VECTOR2I, line start
            p2: pcbnew.VECTOR2I, line end
            polygon: SHAPE_POLY_SET
        
        Returns:
            bool: True if intersection exists
        """
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
    
    def _astar_surface_path(self, start_pad, goal_pad, obstacles, layer, max_iterations=10000):
        """
        A* pathfinding algorithm to find shortest surface path.
        
        Args:
            start_pad: pcbnew.PAD, starting pad
            goal_pad: pcbnew.PAD, goal pad
            obstacles: list of obstacle dicts
            layer: pcbnew layer ID
            max_iterations: int, maximum A* iterations
        
        Returns:
            dict: {'length': float (mm), 'nodes': [VECTOR2I, ...]} or None if no path
        """
        import heapq
        
        start = start_pad.GetPosition()
        goal = goal_pad.GetPosition()
        
        # If direct path is clear, use it
        if not self._path_crosses_obstacle(start, goal, obstacles):
            distance = pcbnew.ToMM(self.get_distance(start, goal))
            return {'length': distance, 'nodes': [start, goal]}
        
        # Initialize A* data structures
        open_set = []  # Priority queue: (f_score, counter, node)
        closed_set = set()
        came_from = {}
        g_score = {self._node_key(start): 0}
        
        counter = 0  # For tie-breaking in priority queue
        heapq.heappush(open_set, (self._heuristic(start, goal), counter, start))
        counter += 1
        
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            # Progress logging every 100 iterations
            if iterations % 100 == 0:
                self.log(f"        A* iteration {iterations}/{max_iterations}...")
            
            current_f, _, current = heapq.heappop(open_set)
            current_key = self._node_key(current)
            
            # Goal reached?
            if self.get_distance(current, goal) < pcbnew.FromMM(0.01):  # 0.01mm tolerance
                path = self._reconstruct_path(came_from, current, start)
                length = self._calculate_path_length(path)
                return {'length': length, 'nodes': path}
            
            if current_key in closed_set:
                continue
            
            closed_set.add(current_key)
            
            # Generate neighbor nodes
            neighbors = self._get_neighbor_nodes(current, goal, start_pad, goal_pad, obstacles)
            
            for neighbor in neighbors:
                neighbor_key = self._node_key(neighbor)
                
                if neighbor_key in closed_set:
                    continue
                
                # Calculate tentative g_score
                tentative_g = g_score[current_key] + self.get_distance(current, neighbor)
                
                if neighbor_key not in g_score or tentative_g < g_score[neighbor_key]:
                    # This path to neighbor is better
                    came_from[neighbor_key] = current
                    g_score[neighbor_key] = tentative_g
                    f_score = tentative_g + self._heuristic(neighbor, goal)
                    
                    heapq.heappush(open_set, (f_score, counter, neighbor))
                    counter += 1
        
        # No path found
        self.log(f"    A* failed: {iterations} iterations, no path found")
        return None
    
    def _node_key(self, node):
        """Generate hashable key for node (for dict/set operations)"""
        return (node.x, node.y)
    
    def _heuristic(self, node, goal):
        """A* heuristic: Euclidean distance (admissible, guarantees optimality)"""
        return self.get_distance(node, goal)
    
    def _get_neighbor_nodes(self, current, goal, start_pad, goal_pad, obstacles):
        """
        Generate candidate neighbor nodes for A* expansion.
        
        Strategy: Use obstacle corner vertices (visibility graph approach) plus goal.
        
        Args:
            current: pcbnew.VECTOR2I, current position
            goal: pcbnew.VECTOR2I, goal position
            start_pad: pcbnew.PAD, start pad
            goal_pad: pcbnew.PAD, goal pad
            obstacles: list of obstacle dicts
        
        Returns:
            list of pcbnew.VECTOR2I: neighbor nodes
        """
        neighbors = []
        
        # Always try direct path to goal
        if not self._path_crosses_obstacle(current, goal, obstacles):
            neighbors.append(goal)
        
        # Add obstacle corner vertices as potential waypoints
        for obstacle in obstacles:
            poly = obstacle['polygon']
            
            for outline_idx in range(poly.OutlineCount()):
                outline = poly.Outline(outline_idx)
                point_count = outline.PointCount()
                
                # Sample vertices (limit to avoid too many neighbors)
                # Reduced from 8 to 4 vertices per obstacle for better performance
                step = max(1, point_count // 4)  # Sample ~4 vertices per obstacle
                
                for i in range(0, point_count, step):
                    vertex = outline.CPoint(i)
                    
                    # Only add if path from current to vertex is clear
                    if not self._path_crosses_obstacle(current, vertex, obstacles):
                        neighbors.append(vertex)
        
        # Limit total neighbors to avoid exponential explosion
        # Reduced from 50 to 20 for better performance
        if len(neighbors) > 20:
            # Keep closest neighbors
            neighbors.sort(key=lambda n: self.get_distance(current, n))
            neighbors = neighbors[:20]
        
        return neighbors
    
    def _reconstruct_path(self, came_from, current, start):
        """
        Reconstruct path from A* came_from map.
        
        Args:
            came_from: dict, {node_key: previous_node}
            current: pcbnew.VECTOR2I, final node
            start: pcbnew.VECTOR2I, start node
        
        Returns:
            list of pcbnew.VECTOR2I: path nodes from start to current
        """
        path = [current]
        current_key = self._node_key(current)
        
        while current_key in came_from:
            current = came_from[current_key]
            path.append(current)
            current_key = self._node_key(current)
        
        path.reverse()
        return path
    
    def _calculate_path_length(self, path):
        """
        Calculate total length of path.
        
        Args:
            path: list of pcbnew.VECTOR2I, path nodes
        
        Returns:
            float: total length in mm
        """
        total_length = 0
        
        for i in range(len(path) - 1):
            segment_length = self.get_distance(path[i], path[i + 1])
            total_length += segment_length
        
        return pcbnew.ToMM(total_length)
    
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
        msg = f"CREEPAGE: {actual_mm:.2f}mm < {required_mm:.2f}mm\n{domain_a}-{domain_b}\n{start_net} ↔ {end_net}"
        
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
        
        # Draw path segments
        if path and len(path) >= 2:
            for i in range(len(path) - 1):
                self.draw_arrow(self.board, path[i], path[i+1], "", self.marker_layer, violation_group)
        
        # Log to report
        self.log(f"  ❌ CREEPAGE VIOLATION: {domain_a} ({start_net}) ↔ {domain_b} ({end_net})", force=True)
        self.log(f"     Actual: {actual_mm:.2f}mm, Required: {required_mm:.2f}mm", force=True)


# Module metadata
__version__ = "1.0.0"
__author__ = "EMC Auditor Plugin"
__description__ = "Clearance and Creepage checking for IEC60664-1 / IPC2221 compliance"
