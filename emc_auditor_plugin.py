import pcbnew
import math
import os
import sys
import wx

# TOML configuration support (Python 3.11+ has tomllib built-in)
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python
    except ImportError:
        try:
            import toml as tomllib  # Alternative fallback
        except ImportError:
            print("ERROR: No TOML library found. Install tomli or toml: pip install tomli")
            tomllib = None

class EMCAuditorPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "EMC Auditor"
        self.category = "Verification"
        self.description = "Checks EMC rules from emc_rules.toml configuration"
        self.show_toolbar_button = True
        
        # Set icon path (same directory as plugin) - KiCad 9.x requires PNG
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(plugin_dir, "emc_icon.png")
        if os.path.exists(icon_path):
            self.icon_file_name = icon_path
        
        # Load configuration
        self.config = self.load_config()
    
    def load_config(self):
        """Load EMC rules from TOML configuration file"""
        if tomllib is None:
            print("WARNING: TOML library not available. Using default values.")
            return self.get_default_config()
        
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(plugin_dir, "emc_rules.toml")
        
        if not os.path.exists(config_path):
            print(f"WARNING: Config file not found: {config_path}")
            print("Using default EMC rules.")
            return self.get_default_config()
        
        try:
            with open(config_path, 'rb') as f:
                config = tomllib.load(f)
            print(f"EMC config loaded: {config['general']['plugin_name']} v{config['general']['version']}")
            return config
        except Exception as e:
            print(f"ERROR loading config: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """Fallback configuration if TOML file cannot be loaded"""
        return {
            'general': {
                'marker_layer': 'Cmts.User',
                'marker_circle_radius_mm': 0.8,
                'marker_line_width_mm': 0.1,
                'marker_text_offset_mm': 1.2,
                'marker_text_size_mm': 0.5
            },
            'via_stitching': {
                'enabled': True,
                'max_distance_mm': 2.0,
                'critical_net_classes': ['HighSpeed', 'Clock'],
                'ground_net_patterns': ['GND', 'GROUND', 'VSS'],
                'violation_message': 'NO GND VIA'
            },
            'decoupling': {
                'enabled': True,
                'max_distance_mm': 3.0,
                'ic_reference_prefixes': ['U'],
                'capacitor_reference_prefixes': ['C'],
                'power_net_patterns': ['VCC', 'VDD', 'PWR', '3V3', '5V'],
                'violation_message': 'CAP TOO FAR ({distance:.1f}mm)'
            }
        }

    def Run(self):
        board = pcbnew.GetBoard()
        # Clear previous markers to avoid duplication
        self.clear_previous_markers(board)
        
        # Load configuration values
        general = self.config.get('general', {})
        marker_layer = board.GetLayerID(general.get('marker_layer', 'Cmts.User'))
        
        violations_found = 0
        
        # 1. Via Stitching Verification (if enabled)
        via_cfg = self.config.get('via_stitching', {})
        if via_cfg.get('enabled', True):
            sys.stderr.write("\n" + "="*70 + "\n")
            sys.stderr.write("STARTING VIA STITCHING CHECK\n")
            sys.stderr.write("="*70 + "\n")
            sys.stderr.flush()
            via_violations = self.check_via_stitching(board, marker_layer, via_cfg)
            violations_found += via_violations
            sys.stderr.write(f"\nVia stitching check complete: {via_violations} violation(s) found\n")
            sys.stderr.flush()
        
        # 2. Decoupling Capacitor Verification (if enabled)
        decap_cfg = self.config.get('decoupling', {})
        if decap_cfg.get('enabled', True):
            sys.stderr.write("\n" + "="*70 + "\n")
            sys.stderr.write("STARTING DECOUPLING CAPACITOR CHECK\n")
            sys.stderr.write("="*70 + "\n")
            sys.stderr.flush()
            decap_violations = self.check_decoupling(board, marker_layer, decap_cfg)
            violations_found += decap_violations
            sys.stderr.write(f"\nDecoupling check complete: {decap_violations} violation(s) found\n")
            sys.stderr.flush()
        
        # 3. Ground Plane Continuity Verification (if enabled)
        ground_cfg = self.config.get('ground_plane', {})
        if ground_cfg.get('enabled', False):
            sys.stderr.write("\n" + "="*70 + "\n")
            sys.stderr.write("STARTING GROUND PLANE CHECK\n")
            sys.stderr.write("="*70 + "\n")
            sys.stderr.flush()
            ground_violations = self.check_ground_plane(board, marker_layer, ground_cfg)
            violations_found += ground_violations
            sys.stderr.write(f"\nGround plane check complete: {ground_violations} violation(s) found\n")
            sys.stderr.flush()
        
        # Future rules can be added here:
        # if self.config.get('trace_width', {}).get('enabled', False):
        #     violations_found += self.check_trace_width(board, marker_layer)
        
        pcbnew.Refresh()
        
        # Show completion dialog
        msg = f"EMC Audit Complete!\n\nFound {violations_found} violation(s).\nCheck User.Comments layer for markers."
        wx.MessageBox(msg, "EMC Auditor", wx.OK | wx.ICON_INFORMATION)
        
        sys.stderr.write(f"\n{'='*70}\n")
        sys.stderr.write(f"EMC AUDIT COMPLETE: {violations_found} violation(s)\n")
        sys.stderr.write(f"{'='*70}\n")
        sys.stderr.flush()
    
    def check_via_stitching(self, board, marker_layer, config):
        """Check via stitching rules (GND vias near critical signal vias)"""
        # Check if verbose logging is enabled
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        
        def log(msg, force=False):
            """Log message to console (only if verbose enabled or force=True)"""
            if verbose or force:
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
        
        log("\n=== VIA STITCHING CHECK START ===", force=True)
        
        max_dist = pcbnew.FromMM(config.get('max_distance_mm', 2.0))
        critical_classes = config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        gnd_patterns = [p.upper() for p in config.get('ground_net_patterns', ['GND'])]
        violation_msg = config.get('violation_message', 'NO GND VIA')
        
        log(f"Max distance: {config.get('max_distance_mm', 2.0)} mm")
        log(f"Critical net classes: {critical_classes}")
        log(f"Ground patterns: {gnd_patterns}")
        
        tracks = board.GetTracks()
        vias = [t for t in tracks if isinstance(t, pcbnew.PCB_VIA)]
        
        # Filter critical vias (handle comma-separated class names)
        critical_vias = []
        for v in vias:
            net_class = v.GetNetClassName()
            is_critical = any(crit_class in net_class for crit_class in critical_classes)
            if is_critical:
                critical_vias.append(v)
                log(f"Critical via: net='{v.GetNetname()}', class='{net_class}'")
        
        gnd_vias = [v for v in vias if any(pat in v.GetNetname().upper() for pat in gnd_patterns)]
        
        log(f"\n✓ Found {len(critical_vias)} critical vias and {len(gnd_vias)} ground vias", force=True)
        
        violations = 0
        for cv in critical_vias:
            net_name = cv.GetNetname()
            pos = cv.GetPosition()
            log(f"\n>>> Checking via on net '{net_name}' at ({pcbnew.ToMM(pos.x):.2f}, {pcbnew.ToMM(pos.y):.2f}) mm")
            
            found = False
            nearest_dist = float('inf')
            for gv in gnd_vias:
                dist = self.get_distance(cv.GetPosition(), gv.GetPosition())
                if dist < nearest_dist:
                    nearest_dist = dist
                if dist <= max_dist:
                    found = True
                    log(f"    ✓ GND via found at {pcbnew.ToMM(dist):.2f} mm")
                    break
            
            if not found:
                log(f"    ❌ NO GND VIA within {config.get('max_distance_mm', 2.0)} mm (nearest: {pcbnew.ToMM(nearest_dist):.2f} mm)")
                # Create individual group for this violation
                violation_group = pcbnew.PCB_GROUP(board)
                violation_group.SetName(f"EMC_Via_{violations+1}")
                board.Add(violation_group)
                
                self.draw_error_marker(board, cv.GetPosition(), violation_msg, marker_layer, violation_group)
                violations += 1
                log(f"    ✓ Violation marker created at ({pcbnew.ToMM(pos.x):.2f}, {pcbnew.ToMM(pos.y):.2f}) mm", force=True)
        
        return violations
    
    def check_decoupling(self, board, marker_layer, config):
        """Check decoupling capacitor proximity to IC power pins"""
        # Check if verbose logging is enabled
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        
        def log(msg, force=False):
            """Log message to console (only if verbose enabled or force=True)"""
            if verbose or force:
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
        
        log("\n=== DECOUPLING CAPACITOR CHECK START ===", force=True)
        
        max_dist_mm = config.get('max_distance_mm', 3.0)
        max_dist = pcbnew.FromMM(max_dist_mm)
        ic_prefixes = config.get('ic_reference_prefixes', ['U'])
        cap_prefixes = config.get('capacitor_reference_prefixes', ['C'])
        power_patterns = [p.upper() for p in config.get('power_net_patterns', ['VCC', 'VDD'])]
        violation_msg_template = config.get('violation_message', 'CAP TOO FAR ({distance:.1f}mm)')
        draw_arrow = config.get('draw_arrow_to_nearest_cap', True)
        
        log(f"Max distance: {max_dist_mm} mm")
        log(f"IC prefixes: {ic_prefixes}")
        log(f"Capacitor prefixes: {cap_prefixes}")
        log(f"Power net patterns: {power_patterns}")
        show_label = config.get('show_capacitor_label', True)
        
        violations = 0
        for footprint in board.GetFootprints():
            ref = footprint.GetReference()
            if any(ref.startswith(prefix) for prefix in ic_prefixes):
                log(f"\n>>> Found IC: {ref}")
                for pad in footprint.Pads():
                    net_name = pad.GetNetname().upper()
                    power_net = pad.GetNetname()  # Get actual net name for matching
                    if any(pat in net_name for pat in power_patterns):
                        pad_pos = pad.GetPosition()
                        pad_x_mm = pcbnew.ToMM(pad_pos.x)
                        pad_y_mm = pcbnew.ToMM(pad_pos.y)
                        log(f"    Checking power pad '{power_net}' at ({pad_x_mm:.2f}, {pad_y_mm:.2f}) mm")
                        best_dist = float('inf')
                        nearest_cap_pos = None
                        nearest_cap_ref = None
                        
                        # Find nearest capacitor CONNECTED TO THE SAME POWER NET
                        for cap in board.GetFootprints():
                            cap_ref = cap.GetReference()
                            if any(cap_ref.startswith(prefix) for prefix in cap_prefixes):
                                # Check if capacitor is connected to this power net
                                cap_connected = False
                                for cap_pad in cap.Pads():
                                    if cap_pad.GetNetname() == power_net:
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
                            log(f"        ✓ Nearest capacitor ({nearest_cap_ref}): {dist_mm:.2f} mm - OK")
                        else:
                            log(f"        ❌ Nearest capacitor ({nearest_cap_ref if nearest_cap_ref else 'NONE'}): {dist_mm:.2f} mm - EXCEEDS {max_dist_mm} mm limit")
                        
                        # If violation found, create individual group and draw markers
                        if best_dist > max_dist:
                            # Create individual group for this violation (circle + text + arrow)
                            violation_group = pcbnew.PCB_GROUP(board)
                            violation_group.SetName(f"EMC_Decap_{ref}_{power_net}")
                            board.Add(violation_group)
                            
                            dist_mm = pcbnew.ToMM(best_dist)
                            msg = violation_msg_template.format(distance=dist_mm)
                            self.draw_error_marker(board, pad.GetPosition(), msg, marker_layer, violation_group)
                            pad_x_mm = pcbnew.ToMM(pad.GetPosition().x)
                            pad_y_mm = pcbnew.ToMM(pad.GetPosition().y)
                            log(f"        ✓ Violation marker created at ({pad_x_mm:.2f}, {pad_y_mm:.2f}) mm", force=True)
                            
                            # Draw arrow showing where the nearest capacitor is
                            if draw_arrow and nearest_cap_pos:
                                label = f"→ {nearest_cap_ref}" if show_label else ""
                                self.draw_arrow(
                                    board, 
                                    pad.GetPosition(), 
                                    nearest_cap_pos,
                                    label,
                                    marker_layer,
                                    violation_group
                                )
                            
                            violations += 1
        
        return violations

    def check_ground_plane(self, board, marker_layer, config):
        """Check ground plane continuity under and around high-speed traces"""
        # Check if verbose logging is enabled (from main config or ground_plane section)
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        
        def log(msg, force=False):
            """Log message to console (only if verbose enabled or force=True)"""
            if verbose or force:
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
        
        log("\n=== GROUND PLANE CHECK START ===", force=True)
        
        critical_classes = config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        gnd_patterns = [p.upper() for p in config.get('ground_net_patterns', ['GND'])]
        
        log(f"Looking for net classes: {critical_classes}")
        log(f"Looking for ground patterns: {gnd_patterns}")
        
        check_continuity = config.get('check_continuity_under_trace', True)
        check_clearance = config.get('check_clearance_around_trace', True)
        check_mode = config.get('ground_plane_check_layers', 'adjacent')  # 'adjacent' or 'all'
        
        log(f"Check mode: {check_mode}")
        log(f"Check continuity: {check_continuity}")
        log(f"Check clearance: {check_clearance}")
        
        max_gap_under = pcbnew.FromMM(config.get('max_gap_under_trace_mm', 0.5))
        sampling_interval = pcbnew.FromMM(config.get('sampling_interval_mm', 0.5))
        clearance_zone = pcbnew.FromMM(config.get('min_clearance_around_trace_mm', 1.0))
        max_gap_clearance = pcbnew.FromMM(config.get('max_ground_gap_in_clearance_zone_mm', 2.0))
        
        violation_msg_no_gnd = config.get('violation_message_no_ground', 'NO GND PLANE UNDER TRACE')
        violation_msg_clearance = config.get('violation_message_insufficient_clearance', 'INSUFFICIENT GND AROUND TRACE')
        
        violations = 0
        
        # Get all tracks on critical net classes
        log("\n--- Scanning all tracks ---")
        critical_tracks = []
        for track in board.GetTracks():
            if isinstance(track, pcbnew.PCB_TRACK):
                net_name = track.GetNetname()
                net_class = track.GetNetClassName()
                # Check if any critical class name is in the net class string
                # (KiCad may return "HighSpeed,Default" for nets in multiple classes)
                is_critical = any(crit_class in net_class for crit_class in critical_classes)
                
                # Debug output for CLK or if already marked critical
                if is_critical or 'CLK' in net_name.upper():
                    log(f"Track: net='{net_name}', class='{net_class}'")
                    if is_critical:
                        critical_tracks.append(track)
                        log(f"  ✓ Added to critical check")
        
        if not critical_tracks:
            log(f"\n❌ ERROR: No tracks found in critical net classes!", force=True)
            log(f"Expected classes: {critical_classes}", force=True)
            log("HINT: Check your KiCad net classes (Edit → Board Setup → Net Classes)", force=True)
            return 0
        
        # Get all ground plane polygons/zones
        log("\n--- Scanning all zones ---")
        ground_zones = []
        for zone in board.Zones():
            zone_net = zone.GetNetname().upper()
            zone_layer = zone.GetLayer()
            layer_name = board.GetLayerName(zone_layer)
            is_filled = zone.IsFilled()
            log(f"Zone: net='{zone.GetNetname()}', layer={layer_name}, filled={is_filled}")
            
            if any(pat in zone_net for pat in gnd_patterns):
                if not is_filled:
                    log(f"  ⚠️  WARNING: Ground zone NOT FILLED! Press 'B' to fill zones.")
                ground_zones.append(zone)
                log(f"  ✓ Added as ground zone")
        
        if not ground_zones:
            log(f"\n❌ ERROR: No ground plane zones found!", force=True)
            log(f"Looking for patterns: {gnd_patterns}", force=True)
            log("HINT: Check zone net names contain GND, GROUND, VSS, etc.", force=True)
            return 0
        
        log(f"\n✓ Found {len(critical_tracks)} critical tracks and {len(ground_zones)} ground zones", force=True)
        log("="*60)
        
        # Check each critical track
        for track in critical_tracks:
            net_name = track.GetNetname()
            start = track.GetStart()
            end = track.GetEnd()
            track_layer = track.GetLayer()
            track_layer_name = board.GetLayerName(track_layer)
            
            log(f"\n>>> Checking track on net '{net_name}', layer {track_layer_name}")
            log(f"    Start: ({pcbnew.ToMM(start.x):.2f}, {pcbnew.ToMM(start.y):.2f}) mm")
            log(f"    End: ({pcbnew.ToMM(end.x):.2f}, {pcbnew.ToMM(end.y):.2f}) mm")
            
            # Determine which layers to check
            if check_mode == 'all':
                # Check all ground zones on all layers
                layers_to_check = list(set([zone.GetLayer() for zone in ground_zones]))
                layer_names = [board.GetLayerName(l) for l in layers_to_check]
                log(f"    Checking ground on ALL layers: {layer_names}")
            else:
                # Check only adjacent layer
                adjacent_layer = self.get_adjacent_ground_layer(board, track_layer)
                if adjacent_layer is None:
                    log(f"    ⚠️  No adjacent layer found, skipping")
                    continue
                layers_to_check = [adjacent_layer]
                log(f"    Checking ground on adjacent layer: {board.GetLayerName(adjacent_layer)}")
            
            # Sample points along the track
            track_length = self.get_distance(start, end)
            if track_length == 0:
                log(f"    ⚠️  Zero-length track, skipping")
                continue
            
            num_samples = max(2, int(track_length / sampling_interval))
            log(f"    Track length: {pcbnew.ToMM(track_length):.2f} mm, samples: {num_samples}")
            
            # Check continuity under trace
            if check_continuity:
                gap_found = False
                gap_position = None
                
                for i in range(num_samples + 1):
                    t = i / num_samples
                    sample_x = int(start.x + (end.x - start.x) * t)
                    sample_y = int(start.y + (end.y - start.y) * t)
                    sample_pos = pcbnew.VECTOR2I(sample_x, sample_y)
                    
                    # Check if ground plane exists at this point on ANY of the layers to check
                    has_ground_on_any_layer = False
                    for check_layer in layers_to_check:
                        for zone in ground_zones:
                            if zone.GetLayer() == check_layer:
                                # HitTestFilledArea checks if point is inside filled zone
                                if zone.IsFilled() and zone.HitTestFilledArea(check_layer, sample_pos):
                                    has_ground_on_any_layer = True
                                    break
                        if has_ground_on_any_layer:
                            break
                    
                    if not has_ground_on_any_layer:
                        gap_found = True
                        gap_position = sample_pos
                        log(f"    ❌ GAP FOUND at sample {i}/{num_samples}:")
                        log(f"       Position: ({pcbnew.ToMM(sample_x):.2f}, {pcbnew.ToMM(sample_y):.2f}) mm")
                        break
                
                if gap_found and gap_position:
                    # Create violation marker
                    violation_group = pcbnew.PCB_GROUP(board)
                    violation_group.SetName(f"EMC_GndPlane_{net_name}_{violations+1}")
                    board.Add(violation_group)
                    
                    self.draw_error_marker(board, gap_position, violation_msg_no_gnd, marker_layer, violation_group)
                    violations += 1
                    log(f"    ✓ Violation marker created at ({pcbnew.ToMM(gap_position.x):.2f}, {pcbnew.ToMM(gap_position.y):.2f}) mm", force=True)
                else:
                    log(f"    ✓ No gaps found - ground plane continuous")
            
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
                        
                        # Check both sides
                        for side in [1, -1]:
                            check_x = int(sample_x + side * perp_x)
                            check_y = int(sample_y + side * perp_y)
                            check_pos = pcbnew.VECTOR2I(check_x, check_y)
                            
                            # Check if ground plane exists within clearance zone on any layer
                            has_ground_nearby = False
                            for check_layer in layers_to_check:
                                for zone in ground_zones:
                                    if zone.GetLayer() == check_layer:
                                        if zone.HitTestFilledArea(check_layer, check_pos):
                                            has_ground_nearby = True
                                            break
                                if has_ground_nearby:
                                    break
                            
                            if not has_ground_nearby:
                                clearance_violation = True
                                clearance_pos = check_pos
                                break
                    
                    if clearance_violation:
                        break
                
                if clearance_violation and clearance_pos:
                    # Create violation marker
                    violation_group = pcbnew.PCB_GROUP(board)
                    violation_group.SetName(f"EMC_GndPlane_{net_name}_clearance_{violations+1}")
                    board.Add(violation_group)
                    
                    # Draw marker at track position (not at clearance check point)
                    track_center_x = (start.x + end.x) // 2
                    track_center_y = (start.y + end.y) // 2
                    track_center = pcbnew.VECTOR2I(track_center_x, track_center_y)
                    
                    self.draw_error_marker(board, track_center, violation_msg_clearance, marker_layer, violation_group)
                    
                    # Draw arrow pointing to ground gap
                    self.draw_arrow(board, track_center, clearance_pos, "GND GAP", marker_layer, violation_group)
                    violations += 1
        
        return violations
    
    def get_adjacent_ground_layer(self, board, signal_layer):
        """Get the adjacent layer that typically contains ground plane"""
        layer_count = board.GetCopperLayerCount()
        
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
                return board.GetLayerID(f"In{layer_count-2}.Cu")
        
        return None

    def get_distance(self, p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

    def draw_error_marker(self, board, pos, message, layer, marker_group):
        """Draw visual marker (circle + text) at violation location"""
        general = self.config.get('general', {})
        
        # Get marker dimensions from config
        radius = pcbnew.FromMM(general.get('marker_circle_radius_mm', 0.8))
        line_width = pcbnew.FromMM(general.get('marker_line_width_mm', 0.1))
        text_offset = pcbnew.FromMM(general.get('marker_text_offset_mm', 1.2))
        text_size = pcbnew.FromMM(general.get('marker_text_size_mm', 0.5))
        
        # Draw circle around violation
        circle = pcbnew.PCB_SHAPE(board)
        circle.SetShape(pcbnew.SHAPE_T_CIRCLE)
        circle.SetFilled(False)
        circle.SetStart(pos)
        circle.SetEnd(pcbnew.VECTOR2I(pos.x + radius, pos.y))
        circle.SetLayer(layer)
        circle.SetWidth(line_width)
        board.Add(circle)
        marker_group.AddItem(circle)

        # Add text label
        txt = pcbnew.PCB_TEXT(board)
        txt.SetText(message)
        txt.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y + text_offset))
        txt.SetLayer(layer)
        txt.SetTextSize(pcbnew.VECTOR2I(text_size, text_size))
        board.Add(txt)
        marker_group.AddItem(txt)

    def draw_arrow(self, board, start_pos, end_pos, label, layer, marker_group):
        """Draw arrow line from start to end position with optional label"""
        general = self.config.get('general', {})
        line_width = pcbnew.FromMM(general.get('marker_line_width_mm', 0.1))
        text_size = pcbnew.FromMM(general.get('marker_text_size_mm', 0.5))
        
        # Draw line from start to end
        line = pcbnew.PCB_SHAPE(board)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(start_pos)
        line.SetEnd(end_pos)
        line.SetLayer(layer)
        line.SetWidth(line_width)
        board.Add(line)
        marker_group.AddItem(line)
        
        # Draw arrowhead at end point (simple triangle)
        arrow_length = pcbnew.FromMM(0.5)  # 0.5mm arrowhead
        
        # Calculate arrow direction
        dx = end_pos.x - start_pos.x
        dy = end_pos.y - start_pos.y
        length = math.sqrt(dx*dx + dy*dy)
        
        if length > 0:
            # Normalize direction
            dx_norm = dx / length
            dy_norm = dy / length
            
            # Perpendicular vector for arrowhead wings
            perp_x = -dy_norm
            perp_y = dx_norm
            
            # Calculate arrowhead points
            arrow_back_x = end_pos.x - dx_norm * arrow_length
            arrow_back_y = end_pos.y - dy_norm * arrow_length
            
            wing_offset = arrow_length * 0.4
            wing1_x = int(arrow_back_x + perp_x * wing_offset)
            wing1_y = int(arrow_back_y + perp_y * wing_offset)
            wing2_x = int(arrow_back_x - perp_x * wing_offset)
            wing2_y = int(arrow_back_y - perp_y * wing_offset)
            
            # Draw arrowhead wings
            wing1 = pcbnew.PCB_SHAPE(board)
            wing1.SetShape(pcbnew.SHAPE_T_SEGMENT)
            wing1.SetStart(end_pos)
            wing1.SetEnd(pcbnew.VECTOR2I(wing1_x, wing1_y))
            wing1.SetLayer(layer)
            wing1.SetWidth(line_width)
            board.Add(wing1)
            marker_group.AddItem(wing1)
            
            wing2 = pcbnew.PCB_SHAPE(board)
            wing2.SetShape(pcbnew.SHAPE_T_SEGMENT)
            wing2.SetStart(end_pos)
            wing2.SetEnd(pcbnew.VECTOR2I(wing2_x, wing2_y))
            wing2.SetLayer(layer)
            wing2.SetWidth(line_width)
            board.Add(wing2)
            marker_group.AddItem(wing2)
        
        # Add label at midpoint if provided
        if label:
            mid_x = (start_pos.x + end_pos.x) // 2
            mid_y = (start_pos.y + end_pos.y) // 2
            
            txt = pcbnew.PCB_TEXT(board)
            txt.SetText(label)
            txt.SetPosition(pcbnew.VECTOR2I(mid_x, mid_y))
            txt.SetLayer(layer)
            txt.SetTextSize(pcbnew.VECTOR2I(text_size, text_size))
            board.Add(txt)
            marker_group.AddItem(txt)

    def clear_previous_markers(self, board):
        """Remove old markers from the marker layer to refresh the report"""
        general = self.config.get('general', {})
        layer_name = general.get('marker_layer', 'Cmts.User')
        layer_id = board.GetLayerID(layer_name)
        
        # Remove all EMC violation groups (individual and master)
        for group in board.Groups():
            group_name = group.GetName()
            if group_name.startswith("EMC_"):
                board.Remove(group)
        
        # Also remove any ungrouped markers from previous versions
        for drawing in board.GetDrawings():
            if drawing.GetLayer() == layer_id:
                board.Remove(drawing)

EMCAuditorPlugin().register()