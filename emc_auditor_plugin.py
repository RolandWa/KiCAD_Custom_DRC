import pcbnew
import math
import os
import sys
import wx
from datetime import datetime

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

# Import clearance/creepage checking module
try:
    from clearance_creepage import ClearanceCreepageChecker
except ImportError as e:
    print(f"WARNING: Could not import clearance_creepage module: {e}")
    ClearanceCreepageChecker = None

class EMCSimpleDialog(wx.Dialog):
    """Simple dialog for quick audit summary with config file access"""
    def __init__(self, parent, message, violations_count, config_path=None):
        wx.Dialog.__init__(self, parent, -1, "EMC Auditor", size=(420, 180))
        
        self.config_path = config_path
        
        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Icon and message panel
        panel = wx.Panel(self)
        panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Info icon
        icon = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_MESSAGE_BOX, (32, 32))
        icon_bitmap = wx.StaticBitmap(panel, -1, icon)
        panel_sizer.Add(icon_bitmap, 0, wx.ALL, 10)
        
        # Message text
        message_text = wx.StaticText(panel, -1, message)
        panel_sizer.Add(message_text, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        panel.SetSizer(panel_sizer)
        main_sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # Button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Open Config button
        if self.config_path and os.path.exists(self.config_path):
            config_btn = wx.Button(self, -1, "Open Config File")
            config_btn.Bind(wx.EVT_BUTTON, self.OnOpenConfig)
            button_sizer.Add(config_btn, 0, wx.ALL, 5)
        
        # OK button
        ok_btn = wx.Button(self, wx.ID_OK, "OK")
        ok_btn.SetDefault()
        button_sizer.Add(ok_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        self.Centre()
    
    def OnOpenConfig(self, event):
        """Open TOML configuration file in text editor (reused from EMCReportDialog)"""
        if not self.config_path or not os.path.exists(self.config_path):
            wx.MessageBox("Configuration file not found.", 
                         "File Not Found", wx.OK | wx.ICON_ERROR)
            return
        
        try:
            # Try to open with system default application (Windows, Linux, macOS)
            if sys.platform == 'win32':
                # Windows: os.startfile respects file associations
                # If .toml is associated, uses TOML editor; otherwise uses .txt editor
                os.startfile(self.config_path)
            elif sys.platform == 'darwin':
                # macOS: use 'open' command
                import subprocess
                subprocess.run(['open', self.config_path])
            else:
                # Linux: use xdg-open
                import subprocess
                subprocess.run(['xdg-open', self.config_path])
        except Exception as e:
            # Fallback: try to open with notepad on Windows or generic text editor
            try:
                if sys.platform == 'win32':
                    # Fallback to notepad.exe
                    import subprocess
                    subprocess.Popen(['notepad.exe', self.config_path])
                else:
                    # On Linux/macOS, try common text editors
                    import subprocess
                    for editor in ['gedit', 'kate', 'nano', 'vim', 'vi']:
                        try:
                            subprocess.Popen([editor, self.config_path])
                            break
                        except FileNotFoundError:
                            continue
            except Exception as fallback_error:
                wx.MessageBox(f"Could not open config file:\n{str(e)}\n\nFallback error: {str(fallback_error)}\n\nFile location:\n{self.config_path}", 
                             "Open Error", wx.OK | wx.ICON_ERROR)

class EMCReportDialog(wx.Dialog):
    """Dialog to display EMC audit report with copy and save functionality"""
    def __init__(self, parent, report_text, violations_count, config_path=None):
        wx.Dialog.__init__(self, parent, -1, "EMC Audit Report", size=(800, 600))
        
        self.report_text = report_text
        self.violations_count = violations_count
        self.config_path = config_path
        
        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Header label
        header = wx.StaticText(self, -1, f"EMC Audit Complete - Found {violations_count} violation(s)")
        header_font = header.GetFont()
        header_font.PointSize += 2
        header_font = header_font.Bold()
        header.SetFont(header_font)
        main_sizer.Add(header, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        # Text control for report (multiline, read-only)
        self.text_ctrl = wx.TextCtrl(self, -1, report_text, 
                                      style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        # Use monospaced font for better readability
        font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.text_ctrl.SetFont(font)
        main_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        
        # Info text
        info_text = wx.StaticText(self, -1, 
                                  "Tip: Use Ctrl+A to select all, Ctrl+C to copy. Check User.Comments layer for visual markers.")
        info_font = info_text.GetFont()
        info_font.PointSize -= 1
        info_text.SetFont(info_font)
        main_sizer.Add(info_text, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        
        # Button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Open Config button
        if self.config_path and os.path.exists(self.config_path):
            config_btn = wx.Button(self, -1, "Open Config File")
            config_btn.Bind(wx.EVT_BUTTON, self.OnOpenConfig)
            button_sizer.Add(config_btn, 0, wx.ALL, 5)
        
        # Save Report button
        save_btn = wx.Button(self, -1, "Save Report")
        save_btn.Bind(wx.EVT_BUTTON, self.OnSaveReport)
        button_sizer.Add(save_btn, 0, wx.ALL, 5)
        
        # Close button
        close_btn = wx.Button(self, wx.ID_OK, "Close")
        button_sizer.Add(close_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        self.Centre()
        
        # Add keyboard shortcuts (Ctrl+S for save, Escape for close)
        accel_table = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), save_btn.GetId()),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, close_btn.GetId())
        ])
        self.SetAcceleratorTable(accel_table)
    
    def OnSaveReport(self, event):
        """Save report to timestamped text file"""
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"EMC_Audit_Report_{timestamp}.txt"
        
        # Show save file dialog
        wildcard = "Text files (*.txt)|*.txt|All files (*.*)|*.*"
        dlg = wx.FileDialog(self, "Save EMC Audit Report",
                            defaultFile=default_filename,
                            wildcard=wildcard,
                            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        
        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.report_text)
                wx.MessageBox(f"Report saved successfully to:\n{filepath}", 
                             "Save Successful", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Error saving report:\n{str(e)}", 
                             "Save Error", wx.OK | wx.ICON_ERROR)
        
        dlg.Destroy()
    
    def OnOpenConfig(self, event):
        """Open TOML configuration file in text editor"""
        if not self.config_path or not os.path.exists(self.config_path):
            wx.MessageBox("Configuration file not found.", 
                         "File Not Found", wx.OK | wx.ICON_ERROR)
            return
        
        try:
            # Try to open with system default application (Windows, Linux, macOS)
            if sys.platform == 'win32':
                # Windows: os.startfile respects file associations
                # If .toml is associated, uses TOML editor; otherwise uses .txt editor
                os.startfile(self.config_path)
            elif sys.platform == 'darwin':
                # macOS: use 'open' command
                import subprocess
                subprocess.run(['open', self.config_path])
            else:
                # Linux: use xdg-open
                import subprocess
                subprocess.run(['xdg-open', self.config_path])
        except Exception as e:
            # Fallback: try to open with notepad on Windows or generic text editor
            try:
                if sys.platform == 'win32':
                    # Fallback to notepad.exe
                    import subprocess
                    subprocess.Popen(['notepad.exe', self.config_path])
                else:
                    # On Linux/macOS, try common text editors
                    import subprocess
                    for editor in ['gedit', 'kate', 'nano', 'vim', 'vi']:
                        try:
                            subprocess.Popen([editor, self.config_path])
                            break
                        except FileNotFoundError:
                            continue
            except Exception as fallback_error:
                wx.MessageBox(f"Could not open config file:\n{str(e)}\n\nFallback error: {str(fallback_error)}\n\nFile location:\n{self.config_path}", 
                             "Open Error", wx.OK | wx.ICON_ERROR)

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
        
        # Initialize report collection
        self.report_lines = []
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        
        # Add report header with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.report_lines.append("="*70)
        self.report_lines.append("EMC AUDITOR REPORT")
        self.report_lines.append(f"Generated: {timestamp}")
        self.report_lines.append(f"Board: {board.GetFileName()}")
        self.report_lines.append("="*70)
        self.report_lines.append("")
        
        # Load configuration values
        general = self.config.get('general', {})
        marker_layer = board.GetLayerID(general.get('marker_layer', 'Cmts.User'))
        
        violations_found = 0
        
        # 1. Via Stitching Verification (if enabled)
        via_cfg = self.config.get('via_stitching', {})
        if via_cfg.get('enabled', True):
            print("\n" + "="*70)
            print("STARTING VIA STITCHING CHECK")
            print("="*70)
            via_violations = self.check_via_stitching(board, marker_layer, via_cfg)
            violations_found += via_violations
            print(f"\nVia stitching check complete: {via_violations} violation(s) found")
        
        # 2. Decoupling Capacitor Verification (if enabled)
        decap_cfg = self.config.get('decoupling', {})
        if decap_cfg.get('enabled', True):
            print("\n" + "="*70)
            print("STARTING DECOUPLING CAPACITOR CHECK")
            print("="*70)
            decap_violations = self.check_decoupling(board, marker_layer, decap_cfg)
            violations_found += decap_violations
            print(f"\nDecoupling check complete: {decap_violations} violation(s) found")
        
        # 3. Ground Plane Continuity Verification (if enabled)
        ground_cfg = self.config.get('ground_plane', {})
        if ground_cfg.get('enabled', False):
            print("\n" + "="*70)
            print("STARTING GROUND PLANE CHECK")
            print("="*70)
            ground_violations = self.check_ground_plane(board, marker_layer, ground_cfg)
            violations_found += ground_violations
            print(f"\nGround plane check complete: {ground_violations} violation(s) found")
        
        # 4. EMI Filtering Verification (if enabled)
        emi_cfg = self.config.get('emi_filtering', {})
        if emi_cfg.get('enabled', False):
            print("\n" + "="*70)
            print("STARTING EMI FILTERING CHECK")
            print("="*70)
            emi_violations = self.check_emi_filtering(board, marker_layer, emi_cfg)
            violations_found += emi_violations
            print(f"\nEMI filtering check complete: {emi_violations} violation(s) found")
        
        # 5. Clearance & Creepage Verification (if enabled)
        # NOTE: Phase 1 implementation - pad-to-pad clearance only
        clearance_cfg = self.config.get('clearance_creepage', {})
        if clearance_cfg.get('enabled', False):
            print("\n" + "="*70)
            print("STARTING CLEARANCE & CREEPAGE CHECK (Phase 1)")
            print("="*70)
            clearance_violations = self.check_clearance_creepage(board, marker_layer, clearance_cfg)
            violations_found += clearance_violations
            print(f"\nClearance check complete: {clearance_violations} violation(s) found")
        
        # Future rules can be added here:
        # if self.config.get('trace_width', {}).get('enabled', False):
        #     violations_found += self.check_trace_width(board, marker_layer)
        
        pcbnew.Refresh()
        
        # Add report footer
        self.report_lines.append("")
        self.report_lines.append("="*70)
        self.report_lines.append(f"TOTAL VIOLATIONS FOUND: {violations_found}")
        self.report_lines.append("="*70)
        self.report_lines.append("")
        self.report_lines.append("Check the User.Comments layer in KiCad for visual markers.")
        self.report_lines.append("Each violation is grouped for easy selection and deletion.")
        
        # Print to console
        print(f"\n{'='*70}")
        print(f"EMC AUDIT COMPLETE: {violations_found} violation(s)")
        print(f"{'='*70}")
        
        # Get config file path to pass to dialogs
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(plugin_dir, "emc_rules.toml")
        
        # Show appropriate dialog based on verbose_logging setting
        if verbose:
            # Show detailed report dialog with save capability and config file access
            report_text = "\n".join(self.report_lines)
            dlg = EMCReportDialog(None, report_text, violations_found, config_path)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            # Show simple dialog with config file access (when verbose_logging is disabled)
            msg = f"EMC Audit Complete!\n\nFound {violations_found} violation(s).\nCheck User.Comments layer for markers."
            dlg = EMCSimpleDialog(None, msg, violations_found, config_path)
            dlg.ShowModal()
            dlg.Destroy()
    
    def check_via_stitching(self, board, marker_layer, config):
        """Check via stitching rules (GND vias near critical signal vias)"""
        # Check if verbose logging is enabled
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        
        def log(msg, force=False):
            """Log message to console and report (only if verbose enabled or force=True)"""
            if verbose or force:
                print(msg)
                if verbose:
                    self.report_lines.append(msg)
        
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
            """Log message to console and report (only if verbose enabled or force=True)"""
            if verbose or force:
                print(msg)
                if verbose:
                    self.report_lines.append(msg)
        
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
            """Log message to console and report (only if verbose enabled or force=True)"""
            if verbose or force:
                print(msg)
                if verbose:
                    self.report_lines.append(msg)
        
        log("\n=== GROUND PLANE CHECK START ===", force=True)
        
        critical_classes = config.get('critical_net_classes', ['HighSpeed', 'Clock'])
        gnd_patterns = [p.upper() for p in config.get('ground_net_patterns', ['GND'])]
        
        log(f"Looking for net classes: {critical_classes}")
        log(f"Looking for ground patterns: {gnd_patterns}")
        
        check_continuity = config.get('check_continuity_under_trace', True)
        check_clearance = config.get('check_clearance_around_trace', True)
        check_mode = config.get('ground_plane_check_layers', 'adjacent')  # 'adjacent' or 'all'
        check_both = config.get('check_both_sides', True)
        ignore_via_clearance_mm = config.get('ignore_via_clearance', 0.5)  # mm
        ignore_pad_clearance_mm = config.get('ignore_pad_clearance', 0.3)  # mm
        min_area_mm2 = config.get('min_ground_polygon_area_mm2', 10.0)
        
        log(f"Check mode: {check_mode}")
        log(f"Check continuity: {check_continuity}")
        log(f"Check clearance: {check_clearance}")
        log(f"Check both sides: {check_both}")
        log(f"Ignore via clearance: {ignore_via_clearance_mm} mm")
        log(f"Ignore pad clearance: {ignore_pad_clearance_mm} mm")
        log(f"Min ground polygon area: {min_area_mm2} mm²")
        
        max_gap_under = pcbnew.FromMM(config.get('max_gap_under_trace_mm', 0.5))
        sampling_interval = pcbnew.FromMM(config.get('sampling_interval_mm', 0.5))
        clearance_zone = pcbnew.FromMM(config.get('min_clearance_around_trace_mm', 1.0))
        max_gap_clearance = pcbnew.FromMM(config.get('max_ground_gap_in_clearance_zone_mm', 2.0))
        via_clearance_radius = pcbnew.FromMM(ignore_via_clearance_mm)  # Read from config
        pad_clearance_radius = pcbnew.FromMM(ignore_pad_clearance_mm)  # Read from config
        
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
        
        # Get all ground plane polygons/zones and organize by layer for performance
        log("\n--- Scanning all zones ---")
        ground_zones = []
        ground_zones_by_layer = {}  # Pre-filter zones by layer for O(1) lookup
        
        for zone in board.Zones():
            zone_net = zone.GetNetname().upper()
            zone_layer = zone.GetLayer()
            layer_name = board.GetLayerName(zone_layer)
            is_filled = zone.IsFilled()
            log(f"Zone: net='{zone.GetNetname()}', layer={layer_name}, filled={is_filled}")
            
            if any(pat in zone_net for pat in gnd_patterns):
                if not is_filled:
                    log(f"  ⚠️  WARNING: Ground zone NOT FILLED! Press 'B' to fill zones.")
                    continue  # Skip unfilled zones (can't hit test them)
                
                # Check minimum polygon area (filter out small copper islands)
                bbox = zone.GetBoundingBox()
                width_mm = pcbnew.ToMM(bbox.GetWidth())
                height_mm = pcbnew.ToMM(bbox.GetHeight())
                zone_area_mm2 = width_mm * height_mm  # Bounding box area in mm²
                if zone_area_mm2 < min_area_mm2:
                    log(f"  ⚠️  Ground zone too small ({zone_area_mm2:.1f} mm² < {min_area_mm2:.1f} mm²), skipping")
                    continue
                
                ground_zones.append(zone)
                
                # Add to layer-indexed dict for fast lookup
                if zone_layer not in ground_zones_by_layer:
                    ground_zones_by_layer[zone_layer] = []
                ground_zones_by_layer[zone_layer].append(zone)
                log(f"  ✓ Added as ground zone ({zone_area_mm2:.1f} mm²)")
        
        if not ground_zones:
            log(f"\n❌ ERROR: No ground plane zones found!", force=True)
            log(f"Looking for patterns: {gnd_patterns}", force=True)
            log("HINT: Check zone net names contain GND, GROUND, VSS, etc.", force=True)
            return 0
        
        # Apply preferred ground layers if specified
        preferred_layers = config.get('preferred_ground_layers', [])
        if preferred_layers:
            log(f"\nPreferred ground layers: {preferred_layers}")
            # Sort ground zones by preferred layer priority
            # Zones on preferred layers will be checked first
            preferred_layer_names = [name.upper() for name in preferred_layers]
            for layer_id, zones in ground_zones_by_layer.items():
                layer_name = board.GetLayerName(layer_id).upper()
                # Check if this layer matches any preferred pattern
                is_preferred = any(pref in layer_name for pref in preferred_layer_names)
                if is_preferred:
                    log(f"  ✓ Layer {board.GetLayerName(layer_id)} marked as preferred")
        
        log(f"\n✓ Found {len(critical_tracks)} critical tracks and {len(ground_zones)} ground zones", force=True)
        log(f"   Ground zones indexed by {len(ground_zones_by_layer)} layers for fast lookup", force=True)
        log("="*60)
        
        # Create progress dialog for user feedback
        progress = None
        if len(critical_tracks) > 10:  # Only show progress for substantial work
            try:
                progress = wx.ProgressDialog(
                    "Ground Plane Check",
                    "Checking ground plane continuity...",
                    maximum=len(critical_tracks),
                    style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
                )
            except Exception as e:
                log(f"  ⚠️  Could not create progress dialog: {e}")
                progress = None
        
        # Check each critical track
        for track_idx, track in enumerate(critical_tracks):
            # Update progress dialog
            if progress:
                cont, skip = progress.Update(
                    track_idx, 
                    f"Checking track {track_idx+1}/{len(critical_tracks)} on net '{track.GetNetname()}'..."
                )
                if not cont:  # User clicked Cancel
                    log("\n⚠️  Ground plane check CANCELLED by user", force=True)
                    progress.Destroy()
                    return violations
            
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
                    # Use pre-filtered zones by layer for O(1) lookup instead of O(n) iteration
                    has_ground_on_any_layer = False
                    for check_layer in layers_to_check:
                        # Only check zones on this specific layer (much faster)
                        for zone in ground_zones_by_layer.get(check_layer, []):
                            # HitTestFilledArea checks if point is inside filled zone
                            if zone.HitTestFilledArea(check_layer, sample_pos):
                                has_ground_on_any_layer = True
                                break
                        if has_ground_on_any_layer:
                            break
                    
                    if not has_ground_on_any_layer:
                        # Check if violation is near a via or pad (should be ignored)
                        should_ignore = False
                        
                        if ignore_via_clearance_mm > 0 or ignore_pad_clearance_mm > 0:
                            # Check all pads and vias on the board
                            for footprint in board.GetFootprints():
                                for pad in footprint.Pads():
                                    pad_pos = pad.GetPosition()
                                    dist_to_pad = self.get_distance(sample_pos, pad_pos)
                                    
                                    # Ignore if near ground pad
                                    if ignore_pad_clearance_mm > 0 and dist_to_pad < pad_clearance_radius:
                                        pad_net = pad.GetNetname().upper()
                                        if any(gnd in pad_net for gnd in gnd_patterns):
                                            log(f"    ⚠️  Gap near GND pad, ignoring")
                                            should_ignore = True
                                            break
                                
                                if should_ignore:
                                    break
                            
                            # Check vias
                            if not should_ignore and ignore_via_clearance_mm > 0:
                                for via_track in board.GetTracks():
                                    if isinstance(via_track, pcbnew.PCB_VIA):
                                        via_pos = via_track.GetPosition()
                                        dist_to_via = self.get_distance(sample_pos, via_pos)
                                        
                                        if dist_to_via < via_clearance_radius:
                                            via_net = via_track.GetNetname().upper()
                                            if any(gnd in via_net for gnd in gnd_patterns):
                                                log(f"    ⚠️  Gap near GND via, ignoring")
                                                should_ignore = True
                                                break
                        
                        if not should_ignore:
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
                        
                        # Check both sides (or just one if check_both_sides = false)
                        sides = [1, -1] if check_both else [1]
                        for side in sides:
                            check_x = int(sample_x + side * perp_x)
                            check_y = int(sample_y + side * perp_y)
                            check_pos = pcbnew.VECTOR2I(check_x, check_y)
                            
                            # Check if ground plane exists within clearance zone on any layer
                            # Use pre-filtered zones by layer for O(1) lookup
                            has_ground_nearby = False
                            for check_layer in layers_to_check:
                                # Only check zones on this specific layer (much faster)
                                for zone in ground_zones_by_layer.get(check_layer, []):
                                    if zone.HitTestFilledArea(check_layer, check_pos):
                                        has_ground_nearby = True
                                        break
                                if has_ground_nearby:
                                    break
                            
                            if not has_ground_nearby:
                                # Check if violation is near a via or pad (should be ignored)
                                should_ignore = False
                                
                                if ignore_via_clearance_mm > 0 or ignore_pad_clearance_mm > 0:
                                    # Check pads
                                    for footprint in board.GetFootprints():
                                        for pad in footprint.Pads():
                                            pad_pos = pad.GetPosition()
                                            dist_to_pad = self.get_distance(check_pos, pad_pos)
                                            
                                            if ignore_pad_clearance_mm > 0 and dist_to_pad < pad_clearance_radius:
                                                pad_net = pad.GetNetname().upper()
                                                if any(gnd in pad_net for gnd in gnd_patterns):
                                                    should_ignore = True
                                                    break
                                        
                                        if should_ignore:
                                            break
                                    
                                    # Check vias
                                    if not should_ignore and ignore_via_clearance_mm > 0:
                                        for via_track in board.GetTracks():
                                            if isinstance(via_track, pcbnew.PCB_VIA):
                                                via_pos = via_track.GetPosition()
                                                dist_to_via = self.get_distance(check_pos, via_pos)
                                                
                                                if dist_to_via < via_clearance_radius:
                                                    via_net = via_track.GetNetname().upper()
                                                    if any(gnd in via_net for gnd in gnd_patterns):
                                                        should_ignore = True
                                                        break
                                
                                if not should_ignore:
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
        
        # Clean up progress dialog
        if progress:
            progress.Destroy()
        
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
    
    def get_nets_by_class(self, board, class_name):
        """
        Get all nets belonging to a specific Net Class (substring match).
        
        KiCad Net Classes can be:
        - Single class: "HighSpeed"
        - Multiple classes: "HighSpeed,Default" (comma-separated)
        - Wildcard assigned: User uses patterns like "*In*" in Board Setup
        
        This function handles all cases by using substring matching,
        matching the approach used in check_via_stitching().
        
        Args:
            board: pcbnew.BOARD object
            class_name: Net Class name to search for (e.g., 'HIGH_VOLTAGE_DC')
        
        Returns:
            list: Net names (strings) that belong to this class
        
        Example:
            >>> nets = self.get_nets_by_class(board, 'HIGH_VOLTAGE_DC')
            >>> print(nets)  # ['Net-(U5-In)', 'Net-(U7-In)', 'Net-(U8-In)']
        """
        matching_nets = []
        all_nets = board.GetNetInfo().NetsByName().values()
        
        for net in all_nets:
            net_class = net.GetNetClassName()
            net_name = net.GetNetname()
            
            # Substring match (handles comma-separated classes)
            # Example: class_name='HIGH_VOLTAGE_DC' matches 'HIGH_VOLTAGE_DC,Default'
            if class_name in net_class and net_name:
                matching_nets.append(net_name)
        
        return matching_nets

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

    def check_emi_filtering(self, board, marker_layer, config):
        """Check EMI filtering on interface connectors (USB, Ethernet, CAN, etc.)"""
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        
        def log(msg, force=False):
            """Log message to console and report"""
            if verbose or force:
                print(msg)
                if verbose:
                    self.report_lines.append(msg)
        
        log("\n=== EMI FILTERING CHECK START ===", force=True)
        
        # Load configuration
        connector_prefix = config.get('connector_prefix', 'J')
        filter_prefixes = config.get('filter_component_prefixes', ['R', 'L', 'FB', 'C', 'D'])
        max_distance_mm = config.get('max_filter_distance_mm', 10.0)
        min_filter_type = config.get('min_filter_type', 'simple')  # 'simple', 'LC', 'RC', 'T', 'Pi'
        violation_msg = config.get('violation_message', 'MISSING EMI FILTER')
        
        max_distance = pcbnew.FromMM(max_distance_mm)
        
        log(f"Connector prefix: '{connector_prefix}'")
        log(f"Filter component prefixes: {filter_prefixes}")
        log(f"Maximum filter distance: {max_distance_mm} mm")
        log(f"Minimum required filter type: {min_filter_type}")
        
        violations = 0
        
        # Step 1: Find all connectors with specified prefix
        log("\n--- Scanning for connectors ---")
        connectors = self._find_connectors(board, connector_prefix)
        log(f"Found {len(connectors)} connector(s) with prefix '{connector_prefix}'")
        
        if not connectors:
            log("No connectors found - check complete", force=True)
            return 0
        
        # Step 2: For each connector, detect interface type and check for EMI filtering
        for conn_ref, conn_fp in connectors:
            log(f"\n--- Checking connector {conn_ref} ---")
            conn_pos = conn_fp.GetPosition()
            
            # Detect interface type from reference or footprint name
            interface_type = self._detect_interface_type(conn_ref, conn_fp)
            log(f"Interface type: {interface_type}")
            
            # Get all signal pads from connector (exclude GND, VCC, etc.)
            signal_pads = self._get_signal_pads(conn_fp)
            log(f"Found {len(signal_pads)} signal pad(s)")
            
            if not signal_pads:
                log("  ⚠️  No signal pads found (all GND/VCC?) - skipping")
                continue
            
            # Step 3: Check EMI filter on each signal line and track per-pad results
            pad_results = []  # Track (pad, filter_type, distance, topology, sufficient)
            
            for pad in signal_pads:
                net = pad.GetNet()
                if not net:
                    continue
                
                net_name = net.GetNetname()
                pad_num = pad.GetNumber()
                log(f"  Checking net '{net_name}' on pad {pad_num}")
                
                # Find filter components on this net (improved algorithm)
                filter_result = self._classify_filter_topology_improved(
                    board, net, conn_pos, max_distance, filter_prefixes, config
                )
                
                if filter_result:
                    filter_type, distance, topology_description = filter_result
                    log(f"    Found filter: {filter_type}")
                    log(f"    Topology: {topology_description}")
                    log(f"    Distance to first component: {pcbnew.ToMM(distance):.2f} mm")
                    
                    # Check if this filter meets requirement
                    filter_sufficient = self._check_filter_requirement(filter_type, min_filter_type)
                    pad_results.append((pad, filter_type, distance, topology_description, filter_sufficient))
                    
                    if filter_sufficient:
                        log(f"    ✓ Filter OK: {filter_type} at {pcbnew.ToMM(distance):.2f} mm")
                    else:
                        log(f"    ❌ VIOLATION: Filter type '{filter_type}' insufficient (need '{min_filter_type}')", force=True)
                else:
                    log(f"    ❌ VIOLATION: No EMI filter found within {max_distance_mm} mm", force=True)
                    pad_results.append((pad, None, float('inf'), None, False))
            
            # Step 4: Create markers for each pad with violations
            for pad, filter_type, distance, topology, sufficient in pad_results:
                if not sufficient:
                    pad_pos = pad.GetPosition()
                    pad_num = pad.GetNumber()
                    net_name = pad.GetNet().GetNetname() if pad.GetNet() else "NC"
                    
                    if filter_type is None:
                        # No filter found
                        violation_group = pcbnew.PCB_GROUP(board)
                        violation_group.SetName(f"EMC_EMI_{conn_ref}_Pad{pad_num}_NoFilter")
                        board.Add(violation_group)
                        
                        marker_text = f"{violation_msg}\n({interface_type})"
                        self.draw_error_marker(board, pad_pos, marker_text, marker_layer, violation_group)
                        violations += 1
                    else:
                        # Insufficient filter
                        violation_group = pcbnew.PCB_GROUP(board)
                        violation_group.SetName(f"EMC_EMI_{conn_ref}_Pad{pad_num}_WeakFilter")
                        board.Add(violation_group)
                        
                        marker_text = f"WEAK FILTER\n({filter_type}<{min_filter_type})"
                        self.draw_error_marker(board, pad_pos, marker_text, marker_layer, violation_group)
                        violations += 1
        
        log(f"\n=== EMI FILTERING CHECK COMPLETE: {violations} violation(s) ===", force=True)
        return violations
    
    def check_clearance_creepage(self, board, marker_layer, config):
        """Check electrical clearance and creepage distances per IEC60664-1 / IPC2221
        
        This function delegates to the ClearanceCreepageChecker module for implementation.
        Complete configuration is in emc_rules.toml [clearance_creepage] section.
        
        The checker reuses utility functions from this plugin:
        - draw_error_marker(): Draw violation markers on User.Comments layer
        - draw_arrow(): Draw directional arrows between violation points
        - get_distance(): Calculate distance between two points
        
        Returns:
            int: Number of violations found
        """
        # Check if module is available
        if ClearanceCreepageChecker is None:
            self.log("⚠️  Clearance/Creepage checker module not available", force=True)
            self.log("HINT: Ensure clearance_creepage.py is in same directory as plugin", force=True)
            return 0
        
        # Create checker instance with shared report lines
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=marker_layer,
            config=config,
            report_lines=self.report_lines,
            verbose=verbose,
            auditor=self  # Pass auditor instance for utility functions
        )
        
        # Run check with injected utility functions (avoids code duplication)
        violations = checker.check(
            draw_marker_func=self.draw_error_marker,
            draw_arrow_func=self.draw_arrow,
            get_distance_func=self.get_distance
        )
        
        return violations
    
    def _find_connectors(self, board, prefix):
        """Find all footprints with reference starting with specified prefix (e.g., 'J')"""
        connectors = []
        for fp in board.GetFootprints():
            ref = fp.GetReference()
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
        """Get signal pads from connector (exclude GND, VCC, shield, etc.)
        
        Excludes power and ground nets from EMI filtering checks since they're
        not interface signals and have separate decoupling requirements.
        """
        signal_pads = []
        
        # Ground net patterns (same as via stitching check)
        ground_patterns = ['GND', 'GROUND', 'VSS', 'PGND', 'AGND', 'DGND', 'SHIELD', 'SH']
        
        # Power net patterns (same as decoupling check)
        # These are supply rails, not interface signals
        power_patterns = ['VCC', 'VDD', 'PWR', '3V3', '5V', '1V8', '2V5', '12V', '+3V3', '+5V', '+', 'VBUS']
        
        for pad in footprint.Pads():
            net = pad.GetNet()
            if not net:
                continue
            
            net_name = net.GetNetname().upper()
            
            # Exclude ground nets
            is_ground = any(pattern in net_name for pattern in ground_patterns)
            if is_ground:
                continue
            
            # Exclude power supply nets (NOT interface signals)
            is_power = any(pattern in net_name for pattern in power_patterns)
            if is_power:
                continue
            
            # This is a signal pad (data, clock, control lines)
            signal_pads.append(pad)
        
        return signal_pads
    
    def _find_filter_components(self, board, net, connector_pos, max_distance, prefixes):
        """Find filter components (R, L, FB, C, D) on specified net within max_distance"""
        filter_components = []
        
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            
            # Check if component has filter prefix (R, L, FB, C, D)
            if not any(ref.startswith(prefix) for prefix in prefixes):
                continue
            
            # Check if component is connected to the net
            component_on_net = False
            for pad in fp.Pads():
                if pad.GetNet() and pad.GetNet().GetNetCode() == net.GetNetCode():
                    component_on_net = True
                    break
            
            if not component_on_net:
                continue
            
            # Check distance from connector
            comp_pos = fp.GetPosition()
            distance = math.sqrt(
                (comp_pos.x - connector_pos.x)**2 + 
                (comp_pos.y - connector_pos.y)**2
            )
            
            if distance <= max_distance:
                filter_components.append((ref, fp, distance))
        
        return filter_components
    
    def _classify_filter_topology_improved(self, board, net, connector_pos, max_distance, prefixes, config):
        """Improved filter topology detection with series/shunt analysis and differential pair detection.
        
        Algorithm:
        1. Find first filter component within max_filter_distance_mm of connector
        2. Trace signal path from connector through filter components
        3. Classify each component as series (in-line) or shunt (to GND/power)
        4. Build topology description with component references
        5. Detect differential pair filters (common-mode chokes)
        
        Returns: (filter_type, distance, topology_description) or None
        """
        
        # Step 1: Find first component within max_distance
        first_component = self._find_first_filter_component(
            board, net, connector_pos, max_distance, prefixes
        )
        
        if not first_component:
            return None  # No filter within range
        
        first_ref, first_fp, first_distance = first_component
        
        # Step 2: Find all filter components on this net (no distance limit after first)
        all_filter_components = []
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            
            # Check if component has filter prefix
            if not any(ref.startswith(prefix) for prefix in prefixes):
                continue
            
            # Check if component is connected to the net
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
        
        # Step 3: Analyze each component (series vs shunt)
        component_analysis = []
        series_components = []
        shunt_components = []
        
        for ref, fp, distance in all_filter_components:
            comp_type, net_info = self._analyze_component_placement(board, fp, net, config)
            component_analysis.append({
                'ref': ref,
                'type': comp_type,  # 'series' or 'shunt'
                'component_class': ref[0] if ref else '?',  # R, L, C, FB, D
                'distance': distance,
                'nets': net_info
            })
            
            if comp_type == 'series':
                series_components.append(ref)
            elif comp_type == 'shunt':
                shunt_components.append(ref)
        
        # Sort by distance from connector
        component_analysis.sort(key=lambda x: x['distance'])
        
        # Step 4: Detect differential pair filters
        diff_pair_filter = self._detect_differential_pair_filter(board, net, connector_pos, max_distance, config)
        
        # Step 5: Classify topology
        filter_type, topology_desc = self._classify_topology_from_analysis(
            component_analysis, series_components, shunt_components, diff_pair_filter, config
        )
        
        return (filter_type, first_distance, topology_desc)
    
    def _find_first_filter_component(self, board, net, connector_pos, max_distance, prefixes):
        """Find the first filter component within max_distance of connector."""
        nearest_component = None
        nearest_distance = float('inf')
        
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            
            # Check if component has filter prefix
            if not any(ref.startswith(prefix) for prefix in prefixes):
                continue
            
            # Check if component is connected to the net
            component_on_net = False
            for pad in fp.Pads():
                if pad.GetNet() and pad.GetNet().GetNetCode() == net.GetNetCode():
                    component_on_net = True
                    break
            
            if not component_on_net:
                continue
            
            # Check distance from connector
            comp_pos = fp.GetPosition()
            distance = math.sqrt(
                (comp_pos.x - connector_pos.x)**2 + 
                (comp_pos.y - connector_pos.y)**2
            )
            
            if distance <= max_distance and distance < nearest_distance:
                nearest_component = (ref, fp, distance)
                nearest_distance = distance
        
        return nearest_component
    
    def _analyze_component_placement(self, board, footprint, signal_net, config):
        """Determine if component is series (in-line) or shunt (to GND/power).
        
        Series: Component in signal path (at least one pad on signal, no pads on GND/power)
        Shunt: One pad on signal net, other pad on GND or power net (bypass cap, termination)
        
        Returns: ('series' or 'shunt', net_info_dict)
        """
        pads = list(footprint.Pads())
        
        if len(pads) < 2:
            return ('unknown', {})
        
        # Get nets for all pads
        pad_nets = []
        for pad in pads:
            net = pad.GetNet()
            if net:
                pad_nets.append(net.GetNetname())
            else:
                pad_nets.append('NC')
        
        # Get GND/power patterns from config
        ground_patterns = config.get('ground_patterns', ['GND', 'GROUND', 'VSS', 'AGND', 'DGND', 'PGND'])
        power_patterns = config.get('power_patterns', ['VCC', 'VDD', 'PWR', '+', 'VBUS', '3V3', '5V'])
        gnd_power_patterns = ground_patterns + power_patterns
        
        signal_net_name = signal_net.GetNetname()
        signal_net_count = pad_nets.count(signal_net_name)
        
        # Check for GND/power connections (on any pad)
        has_gnd_power = any(
            any(pattern in net_name.upper() for pattern in gnd_power_patterns)
            for net_name in pad_nets if net_name != 'NC'
        )
        
        # Classification logic:
        # Shunt: One pad on signal, any other pad on GND/power
        if signal_net_count >= 1 and has_gnd_power:
            return ('shunt', {'type': 'shunt', 'nets': pad_nets})
        # Series: At least one pad on signal, no GND/power connections (in-line component)
        elif signal_net_count >= 1 and not has_gnd_power:
            return ('series', {'type': 'series', 'nets': pad_nets})
        else:
            # No connection to signal net being analyzed
            return ('unknown', {'type': 'unknown', 'nets': pad_nets})
    
    def _detect_differential_pair_filter(self, board, net, connector_pos, max_distance, config):
        """Detect common-mode choke or differential pair filter.
        
        Looks for inductors/ferrite beads with nets matching differential pair patterns
        configured in TOML (e.g., _P/_N, +/-, DP/DM, TXP/TXN, CANH/CANL).
        """
        net_name = net.GetNetname()
        
        # Get differential pair patterns from config
        diff_config = config.get('differential_pairs', {})
        diff_patterns = diff_config.get('patterns', [
            ['_P', '_N'], ['_p', '_n'], ['+', '-'],
            ['DP', 'DM'], ['dp', 'dm'],
            ['TXP', 'TXN'], ['txp', 'txn'],
            ['RXP', 'RXN'], ['rxp', 'rxn']
        ])
        # Convert to tuples for compatibility
        diff_patterns = [tuple(pair) for pair in diff_patterns]
        
        # Check if current net is part of a differential pair
        pair_net = None
        for pos_suffix, neg_suffix in diff_patterns:
            if pos_suffix in net_name:
                pair_net_name = net_name.replace(pos_suffix, neg_suffix)
                pair_net = board.FindNet(pair_net_name)
                if pair_net:
                    break
            elif neg_suffix in net_name:
                pair_net_name = net_name.replace(neg_suffix, pos_suffix)
                pair_net = board.FindNet(pair_net_name)
                if pair_net:
                    break
        
        if not pair_net:
            return None
        
        # Get minimum pin count for common-mode choke from config
        min_pins = diff_config.get('min_common_mode_choke_pins', 4)
        
        # Get inductor prefixes from component classes config
        component_classes = config.get('component_classes', {})
        inductor_prefixes = component_classes.get('inductor_prefixes', ['L', 'FB'])
        capacitor_prefixes = component_classes.get('capacitor_prefixes', ['C'])
        
        # Look for common-mode choke (inductor/FB with min_pins+ connected to both nets)
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            
            # Check for inductor or ferrite bead using config prefixes
            if not any(ref.startswith(prefix) for prefix in inductor_prefixes):
                continue
            
            # Check if it has enough pads (common-mode choke characteristic)
            pads = list(fp.Pads())
            if len(pads) < min_pins:
                continue
            
            # Check distance from connector
            comp_pos = fp.GetPosition()
            distance = math.sqrt(
                (comp_pos.x - connector_pos.x)**2 + 
                (comp_pos.y - connector_pos.y)**2
            )
            
            if distance > max_distance:
                continue
            
            # Check if both differential pair nets are connected
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
                    'net2': pair_net.GetNetname(),
                    'distance': distance
                }
        
        # Look for common-mode capacitor (capacitor with pads on both differential nets)
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            
            # Check for capacitor using config prefixes
            if not any(ref.startswith(prefix) for prefix in capacitor_prefixes):
                continue
            
            # Check if it has exactly 2 pads (standard capacitor)
            pads = list(fp.Pads())
            if len(pads) != 2:
                continue
            
            # Check distance from connector
            comp_pos = fp.GetPosition()
            distance = math.sqrt(
                (comp_pos.x - connector_pos.x)**2 + 
                (comp_pos.y - connector_pos.y)**2
            )
            
            if distance > max_distance:
                continue
            
            # Check if one pad is on net1 and other pad is on net2
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
                        'net2': pair_net.GetNetname(),
                        'distance': distance
                    }
        
        return None
    
    def _classify_line_filter_type(self, line_components, inductor_prefixes, capacitor_prefixes, resistor_prefixes):
        """Classify filter type for individual differential line components.
        
        Args:
            line_components: List of component dicts (excluding common-mode component)
            inductor_prefixes, capacitor_prefixes, resistor_prefixes: Config-based component class prefixes
            
        Returns: Filter type string ('LC', 'RC', 'C', 'R', simple')
        """
        if not line_components:
            return 'simple'
        
        # Check component types
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
        
        # Count components for Pi/T detection
        series_count = sum(1 for comp in line_components if comp['type'] == 'series')
        shunt_count = sum(1 for comp in line_components if comp['type'] == 'shunt')
        
        # Pi filter: Shunt-C → Series-L/R → Shunt-C
        if shunt_count >= 2 and series_count >= 1 and (has_series_L or has_series_R):
            if (len(line_components) >= 3 and 
                line_components[0]['type'] == 'shunt' and 
                line_components[1]['type'] == 'series' and 
                line_components[2]['type'] == 'shunt'):
                return 'Pi' if has_series_L else 'RC'
        
        # T filter: Series-L/R → Shunt-C → Series-L/R
        if series_count >= 2 and shunt_count >= 1 and has_shunt_C:
            if (len(line_components) >= 3 and 
                line_components[0]['type'] == 'series' and 
                line_components[1]['type'] == 'shunt' and 
                line_components[2]['type'] == 'series'):
                return 'T' if has_series_L else 'RC'
        
        # LC filter: Series L + Shunt C
        if has_series_L and has_shunt_C:
            return 'LC'
        
        # RC filter: Series R + Shunt C
        if has_series_R and has_shunt_C:
            return 'RC'
        
        # Single component filters
        if has_series_L:
            return 'L'
        if has_shunt_C:
            return 'C'
        if has_series_R:
            return 'R'
        
        return 'simple'
    
    def _classify_topology_from_analysis(self, component_analysis, series_components, shunt_components, diff_pair_filter, config):
        """Classify filter topology from component analysis.
        
        Returns: (filter_type, detailed_description)
        """
        
        # Get component class mapping from config
        component_classes = config.get('component_classes', {})
        inductor_prefixes = component_classes.get('inductor_prefixes', ['L', 'FB'])
        capacitor_prefixes = component_classes.get('capacitor_prefixes', ['C'])
        resistor_prefixes = component_classes.get('resistor_prefixes', ['R'])
        
        # If differential pair filter detected, analyze complete topology
        if diff_pair_filter:
            filter_type = diff_pair_filter.get('type', 'common_mode_choke')
            ref = diff_pair_filter['ref']
            net1 = diff_pair_filter['net1']
            net2 = diff_pair_filter['net2']
            
            # Build base description for common-mode component
            if filter_type == 'common_mode_choke':
                cm_desc = f"Differential common-mode choke: {ref} on {net1}/{net2}"
            elif filter_type == 'common_mode_capacitor':
                cm_desc = f"Differential common-mode capacitor: {ref} between {net1}/{net2}"
            else:
                cm_desc = f"Differential filter: {ref} on {net1}/{net2}"
            
            # Analyze remaining components on THIS differential line (exclude common-mode component)
            line_components = [comp for comp in component_analysis if comp['ref'] != ref]
            
            if line_components:
                # Build topology for this line's individual components
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
                
                # Classify individual line filter topology
                line_filter_type = self._classify_line_filter_type(line_components, inductor_prefixes, capacitor_prefixes, resistor_prefixes)
                
                # Combined description: common-mode + line filter
                combined_desc = f"{cm_desc} + Line filter ({line_filter_type}): {line_topology}"
                
                # Return the stronger filter type (Pi/T/LC/RC > Differential)
                if line_filter_type in ['Pi', 'T', 'LC']:
                    return (line_filter_type, combined_desc)
                else:
                    return ('Differential + RC', combined_desc)
            else:
                # Only common-mode component, no additional line filtering
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
        
        # Extract component classes for pattern matching
        series_classes = [comp['component_class'] for comp in component_analysis if comp['type'] == 'series']
        shunt_classes = [comp['component_class'] for comp in component_analysis if comp['type'] == 'shunt']
        
        # Classify topology using config-based component classes
        # Check if any series component starts with inductor prefix
        has_series_L = any(
            any(comp['ref'].startswith(prefix) for prefix in inductor_prefixes)
            for comp in component_analysis if comp['type'] == 'series'
        )
        # Check if any shunt component starts with capacitor prefix
        has_shunt_C = any(
            any(comp['ref'].startswith(prefix) for prefix in capacitor_prefixes)
            for comp in component_analysis if comp['type'] == 'shunt'
        )
        
        # Check for series resistor presence (used in multiple checks below)
        has_series_R = any(
            any(comp['ref'].startswith(prefix) for prefix in resistor_prefixes)
            for comp in component_analysis if comp['type'] == 'series'
        )
        
        # Pi filter: Shunt-C → Series-L/R → Shunt-C
        if len(shunt_components) >= 2 and (has_series_L or has_series_R):
            # Check order: should have shunt, then series, then shunt
            if (len(component_analysis) >= 3 and 
                component_analysis[0]['type'] == 'shunt' and 
                component_analysis[1]['type'] == 'series' and 
                component_analysis[2]['type'] == 'shunt'):
                if has_series_L:
                    return ('Pi', f"Pi filter: {topology_desc}")
                else:
                    return ('RC', f"RC Pi filter: {topology_desc}")
        
        # T filter: Series-L/R → Shunt-C → Series-L/R
        if len(series_components) >= 2 and has_shunt_C:
            if (len(component_analysis) >= 3 and 
                component_analysis[0]['type'] == 'series' and 
                component_analysis[1]['type'] == 'shunt' and 
                component_analysis[2]['type'] == 'series'):
                if has_series_L:
                    return ('T', f"T filter: {topology_desc}")
                else:
                    return ('T', f"RC T filter: {topology_desc}")
        
        # LC filter: Series L + Shunt C (any order)
        if has_series_L and has_shunt_C:
            return ('LC', f"LC filter: {topology_desc}")
        
        # RC filter: Series R + Shunt C (any order, but not T pattern)
        if has_series_R and has_shunt_C:
            return ('RC', f"RC filter: {topology_desc}")
        
        # Single component filters
        if has_series_L:
            return ('L', f"Series inductor: {topology_desc}")
        if has_shunt_C:
            return ('C', f"Shunt capacitor: {topology_desc}")
        if has_series_R:
            return ('R', f"Series resistor: {topology_desc}")
        
        # Fallback: simple filter
        return ('simple', f"Simple filter: {topology_desc}")
    
    def _classify_filter_topology(self, board, net, filter_components, connector_pos):
        """Legacy filter topology classification (kept for backward compatibility).
        
        NOTE: This function uses simplified distance-based sorting.
        Use _classify_filter_topology_improved() for accurate circuit tracing.
        """
        if not filter_components:
            return None, float('inf')
        
        # Sort by distance from connector
        sorted_components = sorted(filter_components, key=lambda x: x[2])
        
        # Extract component types
        refs = [comp[0] for comp in sorted_components]
        types = [ref[0] for ref in refs]  # First letter: R, L, C, F(B), D
        
        # Get nearest distance
        nearest_distance = sorted_components[0][2]
        
        # Classify topology based on component sequence
        if self._is_pi_filter(types):
            return 'Pi', nearest_distance
        elif self._is_t_filter(types):
            return 'T', nearest_distance
        elif 'L' in types and 'C' in types:
            return 'LC', nearest_distance
        elif 'R' in types and 'C' in types:
            return 'RC', nearest_distance
        elif 'L' in types or 'F' in types:  # FB = ferrite bead
            return 'L', nearest_distance
        elif 'C' in types:
            return 'C', nearest_distance
        elif 'R' in types:
            return 'R', nearest_distance
        else:
            return 'simple', nearest_distance
    
    def _is_pi_filter(self, types):
        """Check if component sequence forms Pi filter (C-L-C or C-FB-C)"""
        # Pi filter: Capacitor - Inductor/FB - Capacitor
        types_str = ''.join(types)
        return ('CLC' in types_str or 'CFC' in types_str or 
                'CLF' in types_str or 'FLC' in types_str or 'FCF' in types_str)
    
    def _is_t_filter(self, types):
        """Check if component sequence forms T filter (L-C-L or FB-C-FB)"""
        # T filter: Inductor/FB - Capacitor - Inductor/FB
        types_str = ''.join(types)
        return ('LCL' in types_str or 'FCF' in types_str or 
                'LCF' in types_str or 'FCL' in types_str)
    
    def _check_filter_requirement(self, actual_type, required_type):
        """Check if actual filter meets minimum requirement.
        
        Handles compound types like 'Differential + RC' where differential filtering
        combined with line filtering is evaluated against single-ended requirements.
        
        Differential + X is generally better than X alone because:
        - Common-mode filtering protects against differential-mode EMI
        - Line filtering (X) protects against common-mode EMI
        - Together provides superior overall EMI protection
        """
        if actual_type is None:
            return False
        
        # Filter hierarchy (best to worst)
        hierarchy = ['Pi', 'T', 'LC', 'RC', 'L', 'C', 'R', 'simple']
        
        # Handle compound differential filter types (e.g., "Differential + RC")
        if 'Differential' in actual_type:
            if '+' in actual_type:
                # Extract line filter type after "Differential + "
                parts = actual_type.split('+')
                if len(parts) >= 2:
                    line_filter = parts[1].strip()
                    try:
                        line_rank = hierarchy.index(line_filter)
                        required_rank = hierarchy.index(required_type)
                        
                        # Differential + line filter is one level better than line filter alone
                        # (common-mode filtering bonus moves it up in hierarchy)
                        # Example: "Differential + RC" is treated as equivalent to "LC"
                        effective_rank = max(0, line_rank - 1)
                        
                        return effective_rank <= required_rank
                    except ValueError:
                        pass
            # Pure "Differential" (common-mode only) is considered equivalent to RC
            try:
                actual_rank = hierarchy.index('RC')
                required_rank = hierarchy.index(required_type)
                return actual_rank <= required_rank
            except ValueError:
                return False
        
        # Standard filter type comparison
        try:
            actual_rank = hierarchy.index(actual_type)
            required_rank = hierarchy.index(required_type)
            return actual_rank <= required_rank
        except ValueError:
            # Unknown filter type
            return False

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