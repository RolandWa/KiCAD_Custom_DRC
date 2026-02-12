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

# Import via stitching checking module
try:
    from via_stitching import ViaStitchingChecker
except ImportError as e:
    print(f"WARNING: Could not import via_stitching module: {e}")
    ViaStitchingChecker = None

# Import decoupling capacitor checking module
try:
    from decoupling import DecouplingChecker
except ImportError as e:
    print(f"WARNING: Could not import decoupling module: {e}")
    DecouplingChecker = None

# Import EMI filtering checking module
try:
    from emi_filtering import EMIFilteringChecker
except ImportError as e:
    print(f"WARNING: Could not import emi_filtering module: {e}")
    EMIFilteringChecker = None

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
        """Check via stitching rules (GND vias near critical signal vias)
        
        This function delegates to the ViaStitchingChecker module for implementation.
        Complete configuration is in emc_rules.toml [via_stitching] section.
        
        The checker reuses utility functions from this plugin:
        - draw_error_marker(): Draw violation markers on User.Comments layer
        - draw_arrow(): Draw directional arrows between violation points
        - get_distance(): Calculate distance between two points
        
        Returns:
            int: Number of violations found
        """
        # Check if module is available
        if ViaStitchingChecker is None:
            print("⚠️  Via stitching checker module not available")
            print("HINT: Ensure via_stitching.py is in same directory as plugin")
            return 0
        
        # Create checker instance with shared report lines
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        checker = ViaStitchingChecker(
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
    
    def check_decoupling(self, board, marker_layer, config):
        """Check decoupling capacitor proximity to IC power pins
        
        This function delegates to the DecouplingChecker module for implementation.
        Complete configuration is in emc_rules.toml [decoupling] section.
        
        The checker reuses utility functions from this plugin:
        - draw_error_marker(): Draw violation markers on User.Comments layer
        - draw_arrow(): Draw directional arrows between violation points
        - get_distance(): Calculate distance between two points
        
        Returns:
            int: Number of violations found
        """
        # Check if module is available
        if DecouplingChecker is None:
            print("⚠️  Decoupling checker module not available")
            print("HINT: Ensure decoupling.py is in same directory as plugin")
            return 0
        
        # Create checker instance with shared report lines
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        checker = DecouplingChecker(
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
        """Check EMI filtering on interface connectors (USB, Ethernet, CAN, etc.)
        
        This function delegates to the EMIFilteringChecker module for implementation.
        Complete configuration is in emc_rules.toml [emi_filtering] section.
        
        The checker reuses utility functions from this plugin:
        - draw_error_marker(): Draw violation markers on User.Comments layer
        - draw_arrow(): Draw directional arrows between violation points
        - get_distance(): Calculate distance between two points
        
        Returns:
            int: Number of violations found
        """
        # Check if module is available
        if EMIFilteringChecker is None:
            print("⚠️  EMI filtering checker module not available")
            print("HINT: Ensure emi_filtering.py is in same directory as plugin")
            return 0
        
        # Create checker instance with shared report lines
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        checker = EMIFilteringChecker(
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
            print("⚠️  Clearance/Creepage checker module not available")
            print("HINT: Ensure clearance_creepage.py is in same directory as plugin")
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