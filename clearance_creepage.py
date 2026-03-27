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


class ObstacleSpatialIndex:
    """
    Grid-based spatial index for fast obstacle queries.
    Dramatically reduces obstacle checks from O(N) to O(1) average case.
    """
    
    def __init__(self, obstacles, cell_size_mm=5.0):
        """
        Build spatial grid index.
        
        Args:
            obstacles: list of obstacle dicts with 'polygon' and 'bbox' keys
            cell_size_mm: grid cell size in mm (smaller = more precise, more memory)
        """
        self.grid = {}  # {(grid_x, grid_y): [obstacle_indices]}
        self.obstacles = obstacles
        self.cell_size = pcbnew.FromMM(cell_size_mm)
        
        # Insert each obstacle into all grid cells it overlaps
        for idx, obstacle in enumerate(obstacles):
            bbox = obstacle['bbox']
            min_cell_x = bbox.GetLeft() // self.cell_size
            max_cell_x = bbox.GetRight() // self.cell_size
            min_cell_y = bbox.GetTop() // self.cell_size
            max_cell_y = bbox.GetBottom() // self.cell_size
            
            for cx in range(min_cell_x, max_cell_x + 1):
                for cy in range(min_cell_y, max_cell_y + 1):
                    key = (cx, cy)
                    if key not in self.grid:
                        self.grid[key] = []
                    self.grid[key].append(idx)
    
    def get_obstacles_near_line(self, p1, p2):
        """
        Return only obstacles near line segment (p1, p2).
        
        Args:
            p1, p2: pcbnew.VECTOR2I, line endpoints
        
        Returns:
            list: subset of obstacles that might intersect line
        """
        # Get all grid cells the line passes through
        cells = self._get_line_cells(p1, p2)
        
        # Collect unique obstacle indices
        obstacle_indices = set()
        for cell in cells:
            if cell in self.grid:
                obstacle_indices.update(self.grid[cell])
        
        return [self.obstacles[i] for i in obstacle_indices]
    
    def _get_line_cells(self, p1, p2):
        """Bresenham-like algorithm to find all grid cells intersecting line"""
        cells = set()
        
        x1, y1 = p1.x // self.cell_size, p1.y // self.cell_size
        x2, y2 = p2.x // self.cell_size, p2.y // self.cell_size
        
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        
        x, y = x1, y1
        
        while True:
            cells.add((x, y))
            if x == x2 and y == y2:
                break
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
        
        return cells


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
        self.obstacle_search_margin_mm = self.config.get('obstacle_search_margin_mm', 20.0)  # Spatial filtering margin
    
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
        check_creepage_enabled = self.config.get('check_creepage', False)
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
        if show_inventory or domain_map:
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
        # Configuration - AGGRESSIVE limits to prevent hangs
        max_iterations = 200  # A* iterations per pad pair (typical path: 20-50 iterations)
        max_pairs_to_check = 3  # Only check closest pad pairs (reduced for speed)
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
            return voltages[-1][1]

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
            bbox = obstacle.get('bbox')  # Use cached bbox if available
            
            # Check if line segment intersects polygon (with bbox fast rejection)
            if self._line_intersects_polygon(point_a, point_b, poly, bbox):
                return True
        
        return False
    
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
    
    def _get_key_vertices(self, polygon, max_vertices_per_polygon=3):
        """
        Extract key vertices (corners with significant angle changes) from polygon.
        Aggressively limits vertices to prevent graph explosion.
        
        Args:
            polygon: SHAPE_POLY_SET
            max_vertices_per_polygon: maximum vertices to extract per polygon
        
        Returns:
            list of pcbnew.VECTOR2I: corner vertices (limited)
        """
        vertices = []
        angle_threshold = 30  # degrees - increased from 20 for more aggressive filtering
        
        for outline_idx in range(polygon.OutlineCount()):
            outline = polygon.Outline(outline_idx)
            point_count = outline.PointCount()
            
            if point_count < 3:
                continue
            
            # Collect corners with their angles
            corners = []
            for i in range(point_count):
                prev = outline.CPoint((i - 1) % point_count)
                curr = outline.CPoint(i)
                next_pt = outline.CPoint((i + 1) % point_count)
                
                # Calculate angle change at this vertex
                angle = self._angle_between_vectors(prev, curr, next_pt)
                
                # Only include significant corners
                if abs(angle) > angle_threshold:
                    corners.append((abs(angle), curr))
            
            # Sort by angle (most significant corners first) and take top N
            corners.sort(reverse=True)
            vertices.extend([v for _, v in corners[:max_vertices_per_polygon]])
        
        return vertices
    
    def _angle_between_vectors(self, p1, p2, p3):
        """
        Calculate angle (in degrees) at vertex p2 formed by vectors (p1→p2) and (p2→p3).
        
        Args:
            p1, p2, p3: pcbnew.VECTOR2I
        
        Returns:
            float: angle in degrees (-180 to 180)
        """
        # Vector from p2 to p1
        v1_x = p1.x - p2.x
        v1_y = p1.y - p2.y
        
        # Vector from p2 to p3
        v2_x = p3.x - p2.x
        v2_y = p3.y - p2.y
        
        # Calculate angle using atan2
        angle1 = math.atan2(v1_y, v1_x)
        angle2 = math.atan2(v2_y, v2_x)
        
        angle_diff = math.degrees(angle2 - angle1)
        
        # Normalize to -180 to 180
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360
        
        return angle_diff
    
    def _full_visibility_graph_path(self, start, goal, obstacles):
        """
        Full visibility-graph + Dijkstra (used as last-resort fallback).

        Args:
            start: pcbnew.VECTOR2I (pad edge point)
            goal:  pcbnew.VECTOR2I (pad edge point)
            obstacles: list of obstacle dicts

        Returns:
            dict: {'length': float (mm), 'nodes': [VECTOR2I, ...]} or None
        """
        if len(obstacles) > 300:
            self.log(f"        Full VG skipped: too many obstacles ({len(obstacles)})")
            return None

        self.log(f"        Building spatial index for full VG...")
        spatial_index = ObstacleSpatialIndex(obstacles, cell_size_mm=5.0)

        self.log(f"        Building visibility graph...")
        vertices, graph = self._build_visibility_graph(start, goal, obstacles, spatial_index)

        self.log(f"        Running Dijkstra...")
        return self._dijkstra(graph, 0, 1, vertices)

    def _build_visibility_graph(self, start, goal, obstacles, spatial_index):
        """
        Build visibility graph connecting visible vertices.
        Nodes are obstacle corners + start + goal.
        Edges exist where line-of-sight is clear.
        
        Uses aggressive vertex limiting to prevent O(V²) explosion.
        
        Args:
            start: pcbnew.VECTOR2I, start position
            goal: pcbnew.VECTOR2I, goal position
            obstacles: list of obstacle dicts
            spatial_index: ObstacleSpatialIndex for fast obstacle queries
        
        Returns:
            tuple: (vertices list, adjacency dict {vertex_idx: [(neighbor_idx, distance)]})
        """
        # Collect all vertices with AGGRESSIVE LIMITS
        vertices = [start, goal]
        
        # Hard limit on total vertices to prevent O(V²) explosion
        max_total_vertices = 150  # With 150 vertices: 150² = 22,500 checks (manageable)
        max_vertices_per_obstacle = 3  # Only 3 most significant corners per obstacle
        
        # --- HIGH-PRIORITY: Slot / Edge.Cuts barrier vertices -----------------
        # Extract only the key corners (slot tips / sharp bends), not every polygon
        # approximation point.  Slot polygons can have 20-50 vertices per segment
        # due to curve tessellation — dumping them all explodes the VG.
        slot_key_vertices = []
        regular_obstacles = []
        for obstacle in obstacles:
            if obstacle.get('type') == 'edge_cut':
                # Use _get_key_vertices with a generous per-polygon budget
                kvs = self._get_key_vertices(obstacle['polygon'], max_vertices_per_polygon=6)
                slot_key_vertices.extend(kvs)
            else:
                regular_obstacles.append(obstacle)
        
        # Deduplicate slot vertices (many segments share endpoints)
        seen = set()
        unique_slot_verts = []
        for sv in slot_key_vertices:
            key = (sv.x, sv.y)
            if key not in seen:
                seen.add(key)
                unique_slot_verts.append(sv)
        
        # Add small offsets around each slot key vertex to create "go-around"
        # waypoints the pathfinder can use to skirt slot tips.
        offset_iu = pcbnew.FromMM(0.5)
        go_around_verts = []
        for sv in unique_slot_verts:
            go_around_verts.append(pcbnew.VECTOR2I(sv.x + offset_iu, sv.y))
            go_around_verts.append(pcbnew.VECTOR2I(sv.x - offset_iu, sv.y))
            go_around_verts.append(pcbnew.VECTOR2I(sv.x, sv.y + offset_iu))
            go_around_verts.append(pcbnew.VECTOR2I(sv.x, sv.y - offset_iu))
        
        # Add slot vertices first (guaranteed inclusion)
        vertices.extend(unique_slot_verts)
        vertices.extend(go_around_verts)
        slot_vertex_count = len(unique_slot_verts) + len(go_around_verts)
        
        # Budget remaining for regular obstacle corners
        remaining_budget = max(max_total_vertices - len(vertices), 20)
        
        # Extract key corners from regular obstacles (non-slot)
        all_obstacle_vertices = []
        for obstacle in regular_obstacles:
            poly = obstacle['polygon']
            key_vertices = self._get_key_vertices(poly, max_vertices_per_obstacle)
            all_obstacle_vertices.extend(key_vertices)
        
        # If too many regular vertices, sample them
        if len(all_obstacle_vertices) > remaining_budget:
            self.log(f"        Sampling {len(all_obstacle_vertices)} regular vertices to {remaining_budget} (slot vertices preserved: {slot_vertex_count})")
            step = len(all_obstacle_vertices) // remaining_budget
            all_obstacle_vertices = all_obstacle_vertices[::max(1, step)]
        
        vertices.extend(all_obstacle_vertices[:remaining_budget])
        
        self.log(f"        Visibility graph: {len(vertices)} vertices (2 endpoints + {slot_vertex_count} slot waypoints + {len(vertices)-2-slot_vertex_count} obstacle corners)")
        
        # Build adjacency graph with progress logging
        graph = {i: [] for i in range(len(vertices))}
        edges_added = 0
        total_pairs = len(vertices) * (len(vertices) - 1) // 2
        
        self.log(f"        Checking {total_pairs} vertex pairs for visibility...")
        
        # Check visibility between all vertex pairs
        for i in range(len(vertices)):
            for j in range(i + 1, len(vertices)):
                v_i = vertices[i]
                v_j = vertices[j]
                
                # Use spatial index to get only nearby obstacles
                nearby_obstacles = spatial_index.get_obstacles_near_line(v_i, v_j)
                
                # Check if line-of-sight is clear
                if not self._path_crosses_obstacle_fast(v_i, v_j, nearby_obstacles):
                    dist = self.get_distance(v_i, v_j)
                    graph[i].append((j, dist))
                    graph[j].append((i, dist))
                    edges_added += 1
        
        self.log(f"        Visibility graph complete: {edges_added} edges (clear line-of-sight connections)")
        
        return vertices, graph
    
    def _path_crosses_obstacle_fast(self, point_a, point_b, obstacles):
        """
        Fast version of _path_crosses_obstacle using pre-filtered obstacles.
        
        Args:
            point_a, point_b: pcbnew.VECTOR2I
            obstacles: list of obstacle dicts (pre-filtered by spatial index)
        
        Returns:
            bool: True if path crosses any obstacle
        """
        for obstacle in obstacles:
            poly = obstacle['polygon']
            bbox = obstacle.get('bbox')
            
            if self._line_intersects_polygon(point_a, point_b, poly, bbox):
                return True
        
        return False
    
    def _dijkstra(self, graph, start_idx, goal_idx, vertices):
        """
        Dijkstra's shortest path algorithm on visibility graph.
        
        Args:
            graph: adjacency dict {vertex_idx: [(neighbor_idx, distance)]}
            start_idx: int, index of start vertex
            goal_idx: int, index of goal vertex
            vertices: list of pcbnew.VECTOR2I
        
        Returns:
            dict: {'length': float (mm), 'nodes': [VECTOR2I, ...]} or None
        """
        # Priority queue: (distance, vertex_idx)
        pq = [(0, start_idx)]
        distances = {start_idx: 0}
        previous = {}
        visited = set()
        
        while pq:
            current_dist, current_idx = heapq.heappop(pq)
            
            if current_idx in visited:
                continue
            
            visited.add(current_idx)
            
            # Goal reached?
            if current_idx == goal_idx:
                # Reconstruct path
                path = []
                idx = goal_idx
                while idx in previous:
                    path.append(vertices[idx])
                    idx = previous[idx]
                path.append(vertices[start_idx])
                path.reverse()
                
                length = pcbnew.ToMM(distances[goal_idx])
                self.log(f"        Dijkstra found path: {length:.2f}mm ({len(path)} nodes)")
                return {'length': length, 'nodes': path}
            
            # Explore neighbors
            for neighbor_idx, edge_dist in graph.get(current_idx, []):
                if neighbor_idx in visited:
                    continue
                
                new_dist = current_dist + edge_dist
                
                if neighbor_idx not in distances or new_dist < distances[neighbor_idx]:
                    distances[neighbor_idx] = new_dist
                    previous[neighbor_idx] = current_idx
                    heapq.heappush(pq, (new_dist, neighbor_idx))
        
        # No path found
        self.log(f"        Dijkstra: No path found")
        return None
    
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

    def _recursive_detour(self, start, goal, slot_obstacles, slot_wp_map,
                          depth, max_depth, best_so_far,
                          call_counter, memo):
        """
        Recursively find the shortest path from start to goal that avoids
        all slot obstacles.  Only slots (physical gaps/cutouts) are barriers;
        pads and zones are surface features the creepage path travels along.

        Safety guarantees against hanging:
        - call_counter[0] tracks total recursive calls; aborts at budget (5000).
        - memo caches results for (start, goal) pairs to avoid redundant work.
        - max_depth caps recursion depth (one level per slot crossing).

        Args:
            start:  pcbnew.VECTOR2I
            goal:   pcbnew.VECTOR2I
            slot_obstacles: list of edge_cut obstacle dicts (slots only)
            slot_wp_map: {id(obs): [waypoints]} from _get_slot_waypoints
            depth:  current recursion depth
            max_depth: max recursion depth
            best_so_far: float, best total path length found so far (IU), for pruning
            call_counter: list [count, max_budget] — mutable counter shared across calls
            memo: dict {(sx, sy, gx, gy): result} — memoization cache

        Returns:
            dict: {'length_iu': int, 'nodes': [VECTOR2I, ...]} or None
        """
        # Budget check — hard limit on total recursive calls
        call_counter[0] += 1
        if call_counter[0] > call_counter[1]:
            return None

        # Memoization lookup
        memo_key = (start.x, start.y, goal.x, goal.y)
        if memo_key in memo:
            return memo[memo_key]

        # Base case: direct line doesn't cross any slot → straight distance
        if not self._path_crosses_slot(start, goal, slot_obstacles):
            result = {'length_iu': self.get_distance(start, goal),
                      'nodes': [start, goal]}
            memo[memo_key] = result
            return result

        if depth >= max_depth:
            memo[memo_key] = None
            return None

        # Find all slots that block start→goal
        blockers = self._find_blocking_slots(start, goal, slot_obstacles)
        if not blockers:
            # No slot blocks the line — path is clear
            result = {'length_iu': self.get_distance(start, goal),
                      'nodes': [start, goal]}
            memo[memo_key] = result
            return result

        # Depth-0 diagnostics: log which slots block and waypoint reachability
        if depth == 0 and hasattr(self, 'log'):
            for bi, blk in enumerate(blockers):
                bbox = blk.get('bbox')
                lname = blk.get('layer_name', '?')
                if bbox:
                    self.log(f"          Blocker {bi}: bbox ({pcbnew.ToMM(bbox.GetLeft()):.1f}, "
                             f"{pcbnew.ToMM(bbox.GetTop()):.1f})-"
                             f"({pcbnew.ToMM(bbox.GetRight()):.1f}, "
                             f"{pcbnew.ToMM(bbox.GetBottom()):.1f})mm "
                             f"layer={lname}")
            # Count total reachable waypoints across ALL slots
            all_wps = [wp for wps in slot_wp_map.values() for wp in wps]
            reachable_from_start = []
            for wp in all_wps:
                if not self._path_crosses_slot(start, wp, slot_obstacles):
                    reachable_from_start.append(wp)
            reachable_to_goal = []
            for wp in all_wps:
                if not self._path_crosses_slot(wp, goal, slot_obstacles):
                    reachable_to_goal.append(wp)
            self.log(f"          Total waypoints: {len(all_wps)}, "
                     f"{len(reachable_from_start)} reachable from start, "
                     f"{len(reachable_to_goal)} reachable to goal")
            # Log positions of reachable waypoints
            for i, wp in enumerate(reachable_from_start[:8]):
                self.log(f"            from_start[{i}]: ({pcbnew.ToMM(wp.x):.2f}, {pcbnew.ToMM(wp.y):.2f})")
            for i, wp in enumerate(reachable_to_goal[:8]):
                self.log(f"            to_goal[{i}]: ({pcbnew.ToMM(wp.x):.2f}, {pcbnew.ToMM(wp.y):.2f})")
            # Check if any from_start can reach any to_goal directly
            connected = 0
            for ws in reachable_from_start[:20]:
                for wg in reachable_to_goal[:20]:
                    if not self._path_crosses_slot(ws, wg, slot_obstacles):
                        connected += 1
            self.log(f"          Direct from_start→to_goal connections: {connected}")

        # Try waypoints from ALL slots, not just the blockers.
        # The correct detour often goes around the end of a slot chain,
        # which is a waypoint of a DIFFERENT slot segment than the one
        # directly blocking the line.
        best_result = None
        best_length = best_so_far

        tried_wps = set()
        all_waypoints = [(wp, obs_id) for obs_id, wps in slot_wp_map.items() for wp in wps]

        for wp, _ in all_waypoints:
            wp_key = (wp.x, wp.y)
            if wp_key in tried_wps:
                continue
            tried_wps.add(wp_key)

            # Budget exhausted?
            if call_counter[0] > call_counter[1]:
                break

            # Quick pruning: straight-line lower bound can't beat current best
            lower_bound = self.get_distance(start, wp) + self.get_distance(wp, goal)
            if lower_bound >= best_length:
                continue

            # Recursively solve start→wp (may cross other slots)
            leg1 = self._recursive_detour(
                start, wp, slot_obstacles, slot_wp_map,
                depth + 1, max_depth, best_length,
                call_counter, memo)
            if leg1 is None:
                continue

            remaining_budget = best_length - leg1['length_iu']
            if remaining_budget <= 0:
                continue

            # Recursively solve wp→goal (may cross other slots)
            leg2 = self._recursive_detour(
                wp, goal, slot_obstacles, slot_wp_map,
                depth + 1, max_depth, remaining_budget,
                call_counter, memo)
            if leg2 is None:
                continue

            total = leg1['length_iu'] + leg2['length_iu']
            if total < best_length:
                best_length = total
                # Merge paths: leg1 nodes + leg2 nodes (skip duplicate wp)
                best_result = {
                    'length_iu': total,
                    'nodes': leg1['nodes'] + leg2['nodes'][1:]
                }

        memo[memo_key] = best_result
        return best_result

    def _visibility_graph_path(self, start_pad, goal_pad, obstacles, layer):
        """
        Find shortest surface path using a recursive slot-detour algorithm.

        For creepage, only physical slots/cutouts are barriers that the surface
        path must go around.  Pads, zones, and other copper features are on the
        board surface — the creepage path travels along them, not around them.

        Strategy:
        1. Direct line — if no slot blocks it, return straight distance.
        2. Recursive slot detour — identify the blocking slot, try waypoints
           around its tips, recursively solve each sub-leg.
        3. Full visibility-graph + Dijkstra fallback (rare, complex geometry).

        Returns:
            dict: {'length': float (mm), 'nodes': [VECTOR2I, ...]} or None
        """
        # IEC 60664-1: measure from conductive EDGE, not pad centre
        start = self._get_pad_edge_point(start_pad, goal_pad.GetPosition(), layer)
        goal  = self._get_pad_edge_point(goal_pad,  start_pad.GetPosition(), layer)

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
    
    def _astar_surface_path_fast(self, start_pad, goal_pad, obstacles, layer):
        """
        Ultra-fast A* for dense boards (100+ obstacles).
        Uses aggressive limits to prevent hang.
        
        Args:
            start_pad: pcbnew.PAD
            goal_pad: pcbnew.PAD
            obstacles: list of obstacle dicts
            layer: pcbnew layer ID
        
        Returns:
            dict: {'length': float (mm), 'nodes': [VECTOR2I, ...]} or None
        """
        # BUG FIX: use pad boundary points (not centres) — IEC 60664-1 measures
        # creepage between conductive edges, not conductor centroids.
        start = self._get_pad_edge_point(start_pad, goal_pad.GetPosition(), layer)
        goal  = self._get_pad_edge_point(goal_pad,  start_pad.GetPosition(), layer)

        # Fast path: if direct line is clear, use it
        if not self._path_crosses_obstacle(start, goal, obstacles):
            distance = pcbnew.ToMM(self.get_distance(start, goal))
            return {'length': distance, 'nodes': [start, goal]}

        # Iteration budget — large enough for complex boards with 200+ obstacles
        max_iterations = 5000
        max_neighbors = 12
        
        # Build spatial index for fast queries
        spatial_index = ObstacleSpatialIndex(obstacles, cell_size_mm=10.0)
        
        # Initialize A* data structures
        open_set = []  # Priority queue: (f_score, counter, node)
        closed_set = set()
        came_from = {}
        g_score = {self._node_key(start): 0}
        
        counter = 0
        heapq.heappush(open_set, (self._heuristic(start, goal), counter, start))
        counter += 1
        
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            # Progress logging every 500 iterations to reduce log spam
            if iterations % 500 == 0:
                self.log(f"        Fast A* iteration {iterations}/{max_iterations}, open_set size: {len(open_set)}")
            
            current_f, _, current = heapq.heappop(open_set)
            current_key = self._node_key(current)
            
            # Goal reached?
            if self.get_distance(current, goal) < pcbnew.FromMM(0.01):  # 0.01mm tolerance (consistent with clearance check)
                path = self._reconstruct_path(came_from, current, start)
                length = self._calculate_path_length(path)
                self.log(f"        Fast A* found path: {length:.2f}mm in {iterations} iterations")
                return {'length': length, 'nodes': path}
            
            if current_key in closed_set:
                continue
            
            closed_set.add(current_key)
            
            # Generate very limited neighbors
            neighbors = self._get_fast_neighbors(current, goal, obstacles, spatial_index, max_neighbors)
            
            # Debug: log if no neighbors found
            if len(neighbors) == 0 and iterations == 1:
                self.log(f"        WARNING: No neighbors found on first iteration ({len(obstacles)} obstacles)")
                self.log(f"        This may indicate a PCB slot/cutout or extremely dense routing")
            
            for neighbor in neighbors:
                neighbor_key = self._node_key(neighbor)
                
                if neighbor_key in closed_set:
                    continue
                
                tentative_g = g_score[current_key] + self.get_distance(current, neighbor)
                
                if neighbor_key not in g_score or tentative_g < g_score[neighbor_key]:
                    came_from[neighbor_key] = current
                    g_score[neighbor_key] = tentative_g
                    f_score = tentative_g + self._heuristic(neighbor, goal)
                    
                    heapq.heappush(open_set, (f_score, counter, neighbor))
                    counter += 1
        
        # Loop ended — distinguish timeout from exhausted search space
        if open_set:
            self.log(f"        Fast A* timed out after {iterations} iterations — increase max_obstacles limit or simplify board")
        else:
            self.log(f"        Fast A* exhausted search space after {iterations} iterations — no surface path exists (slot/cutout barrier?)")
        return None
    
    def _get_fast_neighbors(self, current, goal, obstacles, spatial_index, max_neighbors):
        """
        Generate minimal neighbor set for fast A*.
        Uses radial sampling and obstacle vertices for better connectivity.
        
        Args:
            current: pcbnew.VECTOR2I
            goal: pcbnew.VECTOR2I
            obstacles: list of obstacle dicts
            spatial_index: ObstacleSpatialIndex
            max_neighbors: int, max neighbors to return
        
        Returns:
            list of pcbnew.VECTOR2I
        """
        neighbors = []
        
        # Always try goal first
        nearby_obstacles = spatial_index.get_obstacles_near_line(current, goal)
        if not self._path_crosses_obstacle_fast(current, goal, nearby_obstacles):
            return [goal]  # Direct path found!
        
        # STRATEGY 1: Radial waypoints (helps escape starting point obstacles)
        # Cast rays in multiple directions at various distances
        search_distances_mm = [2.0, 5.0, 10.0, 20.0, 50.0]  # mm - added shorter and longer ranges
        angles = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]  # degrees - 12 directions

        radial_attempts = 0
        radial_blocked = 0
        for dist_mm in search_distances_mm:
            dist_iu = pcbnew.FromMM(dist_mm)
            for angle_deg in angles:
                radial_attempts += 1
                angle_rad = math.radians(angle_deg)
                dx = int(dist_iu * math.cos(angle_rad))
                dy = int(dist_iu * math.sin(angle_rad))
                waypoint = pcbnew.VECTOR2I(current.x + dx, current.y + dy)
                
                # Check if path is clear
                test_obstacles = spatial_index.get_obstacles_near_line(current, waypoint)
                if not self._path_crosses_obstacle_fast(current, waypoint, test_obstacles):
                    neighbors.append(waypoint)
                    if len(neighbors) >= max_neighbors:
                        return neighbors[:max_neighbors]
                else:
                    radial_blocked += 1
        
        # STRATEGY 2: Goal-directed offsets (if some neighbors found, add more toward goal)
        # Try points along the line to goal, with perpendicular offsets
        if len(neighbors) < max_neighbors:
            goal_dist = self.get_distance(current, goal)
            if goal_dist > 0:
                # Unit vector toward goal
                dx_goal = (goal.x - current.x) / goal_dist
                dy_goal = (goal.y - current.y) / goal_dist
                
                # Perpendicular vector
                dx_perp = -dy_goal
                dy_perp = dx_goal
                
                # Try steps along goal direction with lateral offsets
                for step_mm in [5.0, 10.0, 20.0]:
                    step_iu = pcbnew.FromMM(step_mm)
                    for offset_mm in [-3.0, -1.0, 0, 1.0, 3.0]:  # Lateral offsets
                        offset_iu = pcbnew.FromMM(offset_mm)
                        waypoint_x = int(current.x + dx_goal * step_iu + dx_perp * offset_iu)
                        waypoint_y = int(current.y + dy_goal * step_iu + dy_perp * offset_iu)
                        waypoint = pcbnew.VECTOR2I(waypoint_x, waypoint_y)
                        
                        test_obstacles = spatial_index.get_obstacles_near_line(current, waypoint)
                        if not self._path_crosses_obstacle_fast(current, waypoint, test_obstacles):
                            neighbors.append(waypoint)
                            if len(neighbors) >= max_neighbors:
                                return neighbors[:max_neighbors]
        
        # STRATEGY 3: Obstacle vertices (if above strategies failed)
        # Get nearby obstacles using spatial index
        search_radius_cells = 5  # Increased from 3
        current_cell_x = current.x // spatial_index.cell_size
        current_cell_y = current.y // spatial_index.cell_size
        
        nearby_obstacle_indices = set()
        for dx in range(-search_radius_cells, search_radius_cells + 1):
            for dy in range(-search_radius_cells, search_radius_cells + 1):
                cell_key = (current_cell_x + dx, current_cell_y + dy)
                if cell_key in spatial_index.grid:
                    nearby_obstacle_indices.update(spatial_index.grid[cell_key])
        
        nearby_obstacles_list = [obstacles[i] for i in list(nearby_obstacle_indices)[:50]]
        
        # Sample obstacle corners
        for obstacle in nearby_obstacles_list:
            poly = obstacle['polygon']
            if poly.OutlineCount() == 0:
                continue
            
            outline = poly.Outline(0)
            point_count = outline.PointCount()
            if point_count == 0:
                continue
            
            # Sample corners closest to goal
            candidates = []
            for i in range(0, point_count, max(1, point_count // 6)):  # Sample 6 points
                vertex = outline.CPoint(i)
                dist_to_goal = self.get_distance(vertex, goal)
                candidates.append((dist_to_goal, vertex))
            
            # Sort by distance to goal, take top 3
            candidates.sort()
            for _, vertex in candidates[:3]:
                test_obstacles = spatial_index.get_obstacles_near_line(current, vertex)
                if not self._path_crosses_obstacle_fast(current, vertex, test_obstacles):
                    neighbors.append(vertex)
                    if len(neighbors) >= max_neighbors * 3:  # Collect extras
                        break
            
            if len(neighbors) >= max_neighbors * 3:
                break
        
        # Sort by heuristic (distance to current + distance to goal) and limit
        if len(neighbors) > max_neighbors:
            neighbors.sort(key=lambda n: self.get_distance(current, n) + self.get_distance(n, goal))
            neighbors = neighbors[:max_neighbors]
        
        return neighbors
    
    def _astar_surface_path(self, start_pad, goal_pad, obstacles, layer, max_iterations=10000):
        """
        DEPRECATED: Old A* pathfinding algorithm (kept for reference).
        Now using _visibility_graph_path() instead for 100× better performance.
        
        Args:
            start_pad: pcbnew.PAD, starting pad
            goal_pad: pcbnew.PAD, goal pad
            obstacles: list of obstacle dicts
            layer: pcbnew layer ID
            max_iterations: int, maximum A* iterations
        
        Returns:
            dict: {'length': float (mm), 'nodes': [VECTOR2I, ...]} or None if no path
        """
        # Redirect to new visibility graph implementation
        return self._visibility_graph_path(start_pad, goal_pad, obstacles, layer)
    
    def _astar_surface_path_old(self, start_pad, goal_pad,obstacles, layer, max_iterations=10000):
        """
        OLD A* implementation - kept for debugging/comparison only.
        
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
        best_distance = float('inf')  # Track progress for early termination
        stalled_count = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            # Progress logging every 50 iterations
            if iterations % 50 == 0:
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
            
            # Early termination: check if making progress
            current_dist = self.get_distance(current, goal)
            if current_dist < best_distance:
                best_distance = current_dist
                stalled_count = 0
            else:
                stalled_count += 1
                if stalled_count > 50:  # No progress in 50 iterations
                    self.log(f"        A* stalled after {iterations} iterations, terminating")
                    break
            
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
                # Reduced from 8 to 2 vertices per obstacle for better performance
                step = max(1, point_count // 2)  # Sample ~2 vertices per obstacle
                
                for i in range(0, point_count, step):
                    vertex = outline.CPoint(i)
                    
                    # Only add if path from current to vertex is clear
                    if not self._path_crosses_obstacle(current, vertex, obstacles):
                        neighbors.append(vertex)
        
        # Limit total neighbors to avoid exponential explosion
        # Reduced from 50 to 5 for better performance
        if len(neighbors) > 5:
            # Keep closest neighbors
            neighbors.sort(key=lambda n: self.get_distance(current, n))
            neighbors = neighbors[:5]
        
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
