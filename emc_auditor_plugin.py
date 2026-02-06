import pcbnew
import math
import os
import sys

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
            violations_found += self.check_via_stitching(board, marker_layer, via_cfg)
        
        # 2. Decoupling Capacitor Verification (if enabled)
        decap_cfg = self.config.get('decoupling', {})
        if decap_cfg.get('enabled', True):
            violations_found += self.check_decoupling(board, marker_layer, decap_cfg)
        
        # Future rules can be added here:
        # if self.config.get('trace_width', {}).get('enabled', False):
        #     violations_found += self.check_trace_width(board, marker_layer)
        
        pcbnew.Refresh()
        print(f"EMC Audit Complete. Found {violations_found} violation(s).")
        print("Check User.Comments layer for markers.")
    
    def check_via_stitching(self, board, marker_layer, config):
        """Check via stitching rules (GND vias near critical signal vias)"""
        max_dist = pcbnew.FromMM(config.get('max_distance_mm', 2.0))
        critical_classes = config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        gnd_patterns = [p.upper() for p in config.get('ground_net_patterns', ['GND'])]
        violation_msg = config.get('violation_message', 'NO GND VIA')
        
        tracks = board.GetTracks()
        vias = [t for t in tracks if isinstance(t, pcbnew.PCB_VIA)]
        critical_vias = [v for v in vias if v.GetNetClassName() in critical_classes]
        gnd_vias = [v for v in vias if any(pat in v.GetNetname().upper() for pat in gnd_patterns)]
        
        violations = 0
        for cv in critical_vias:
            found = False
            for gv in gnd_vias:
                if self.get_distance(cv.GetPosition(), gv.GetPosition()) <= max_dist:
                    found = True
                    break
            if not found:
                # Create individual group for this violation
                violation_group = pcbnew.PCB_GROUP(board)
                violation_group.SetName(f"EMC_Via_{violations+1}")
                board.Add(violation_group)
                
                self.draw_error_marker(board, cv.GetPosition(), violation_msg, marker_layer, violation_group)
                violations += 1
        
        return violations
    
    def check_decoupling(self, board, marker_layer, config):
        """Check decoupling capacitor proximity to IC power pins"""
        max_dist = pcbnew.FromMM(config.get('max_distance_mm', 3.0))
        ic_prefixes = config.get('ic_reference_prefixes', ['U'])
        cap_prefixes = config.get('capacitor_reference_prefixes', ['C'])
        power_patterns = [p.upper() for p in config.get('power_net_patterns', ['VCC', 'VDD'])]
        violation_msg_template = config.get('violation_message', 'CAP TOO FAR ({distance:.1f}mm)')
        draw_arrow = config.get('draw_arrow_to_nearest_cap', True)
        show_label = config.get('show_capacitor_label', True)
        
        violations = 0
        for footprint in board.GetFootprints():
            ref = footprint.GetReference()
            if any(ref.startswith(prefix) for prefix in ic_prefixes):
                for pad in footprint.Pads():
                    net_name = pad.GetNetname().upper()
                    power_net = pad.GetNetname()  # Get actual net name for matching
                    if any(pat in net_name for pat in power_patterns):
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
                        
                        # If violation found, create individual group and draw markers
                        if best_dist > max_dist:
                            # Create individual group for this violation (circle + text + arrow)
                            violation_group = pcbnew.PCB_GROUP(board)
                            violation_group.SetName(f"EMC_Decap_{ref}_{power_net}")
                            board.Add(violation_group)
                            
                            dist_mm = pcbnew.ToMM(best_dist)
                            msg = violation_msg_template.format(distance=dist_mm)
                            self.draw_error_marker(board, pad.GetPosition(), msg, marker_layer, violation_group)
                            
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