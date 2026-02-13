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

# Import ground plane checking module
try:
    from ground_plane import GroundPlaneChecker
except ImportError as e:
    print(f"WARNING: Could not import ground_plane module: {e}")
    GroundPlaneChecker = None

# Import signal integrity checking module
try:
    from signal_integrity import SignalIntegrityChecker
except ImportError as e:
    print(f"WARNING: Could not import signal_integrity module: {e}")
    SignalIntegrityChecker = None

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
        
        # 6. Signal Integrity Verification (if enabled)
        signal_integrity_cfg = self.config.get('signal_integrity', {})
        if signal_integrity_cfg.get('impedance', {}).get('enabled', False):
            print("\n" + "="*70)
            print("STARTING SIGNAL INTEGRITY CHECK")
            print("="*70)
            si_violations = self.check_signal_integrity(board, marker_layer, signal_integrity_cfg)
            violations_found += si_violations
            print(f"\nSignal integrity check complete: {si_violations} violation(s) found")
        
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
        log_func = self.create_logger(verbose, self.report_lines)
        violations = checker.check(
            draw_marker_func=self.draw_error_marker,
            draw_arrow_func=self.draw_arrow,
            get_distance_func=self.get_distance,
            log_func=log_func,
            create_group_func=self.create_violation_group
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
        log_func = self.create_logger(verbose, self.report_lines)
        violations = checker.check(
            draw_marker_func=self.draw_error_marker,
            draw_arrow_func=self.draw_arrow,
            get_distance_func=self.get_distance,
            log_func=log_func,
            create_group_func=self.create_violation_group
        )
        
        return violations

    def check_ground_plane(self, board, marker_layer, config):
        """Check ground plane continuity under and around high-speed traces
        
        This function delegates to the GroundPlaneChecker module for implementation.
        Complete configuration is in emc_rules.toml [ground_plane] section.
        
        The checker reuses utility functions from this plugin:
        - draw_error_marker(): Draw violation markers on User.Comments layer
        - draw_arrow(): Draw directional arrows between violation points
        - get_distance(): Calculate distance between two points
        
        Returns:
            int: Number of violations found
        """
        # Check if module is available
        if GroundPlaneChecker is None:
            print("⚠️  Ground plane checker module not available")
            print("HINT: Ensure ground_plane.py is in same directory as plugin")
            return 0
        
        # Create checker instance with shared report lines
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        checker = GroundPlaneChecker(
            board=board,
            marker_layer=marker_layer,
            config=config,
            report_lines=self.report_lines,
            verbose=verbose,
            auditor=self  # Pass auditor instance for utility functions
        )
        
        # Run check with injected utility functions (avoids code duplication)
        log_func = self.create_logger(verbose, self.report_lines)
        violations = checker.check(
            draw_marker_func=self.draw_error_marker,
            draw_arrow_func=self.draw_arrow,
            get_distance_func=self.get_distance,
            log_func=log_func,
            create_group_func=self.create_violation_group
        )
        
        return violations
    
    def check_signal_integrity(self, board, marker_layer, config):
        """Check signal integrity: controlled impedance, crosstalk, return path, etc.
        
        This function delegates to the SignalIntegrityChecker module for implementation.
        Complete configuration is in emc_rules.toml [signal_integrity] section.
        
        The checker reuses utility functions from this plugin:
        - draw_error_marker(): Draw violation markers on User.Comments layer
        - draw_arrow(): Draw directional arrows between violation points
        - get_distance(): Calculate distance between two points
        
        Returns:
            int: Number of violations found
        """
        # Check if module is available
        if SignalIntegrityChecker is None:
            print("⚠️  Signal integrity checker module not available")
            print("HINT: Ensure signal_integrity.py is in same directory as plugin")
            return 0
        
        # Create checker instance with shared report lines
        verbose = self.config.get('general', {}).get('verbose_logging', True)
        checker = SignalIntegrityChecker(
            board=board,
            marker_layer=marker_layer,
            config=config,
            report_lines=self.report_lines,
            verbose=verbose,
            auditor=self  # Pass auditor instance for utility functions
        )
        
        # Run check with injected utility functions (avoids code duplication)
        log_func = self.create_logger(verbose, self.report_lines)
        violations = checker.check(
            draw_marker_func=self.draw_error_marker,
            draw_arrow_func=self.draw_arrow,
            get_distance_func=self.get_distance,
            log_func=log_func,
            create_group_func=self.create_violation_group
        )
        
        return violations

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

    def create_logger(self, verbose, report_lines):
        """
        Create a logging function for modules to use (eliminates code duplication).
        
        This function returns a logger that conditionally prints to console and appends
        to the shared report_lines list based on the verbose flag. By centralizing this
        logic, we avoid duplicating the same log() method in all 5 checker modules.
        
        Args:
            verbose: bool - Enable detailed logging to console and report
            report_lines: list - Shared report lines array (modified in-place)
        
        Returns:
            function: log(msg, force=False) callable
                - msg: str - Message to log
                - force: bool - Force logging even if verbose=False (for summary messages)
        
        Example:
            log_func = self.create_logger(True, self.report_lines)
            log_func("Starting check...", force=True)  # Always logged
            log_func("Debug: Processing item")  # Only if verbose=True
        """
        def log(msg, force=False):
            """Log message to console and report (only if verbose enabled or force=True)"""
            if verbose or force:
                print(msg)
                if verbose:
                    report_lines.append(msg)
        return log

    def create_violation_group(self, board, check_type, identifier, violation_number=None):
        """
        Create a standardized violation group for visual organization in KiCad.
        
        This function eliminates boilerplate code by providing a single place to create
        violation groups with consistent naming. Each violation gets a PCB_GROUP that
        contains all related visual elements (markers, arrows, labels).
        
        Args:
            board: pcbnew.BOARD object
            check_type: str - Type of check (Via, Decap, GndPlane, EMI, Clearance)
            identifier: str - Unique identifier (net name, component ref, pad number, etc.)
            violation_number: int - Optional violation sequence number for uniqueness
        
        Returns:
            pcbnew.PCB_GROUP: Created and added group object ready for use
        
        Example:
            group = self.create_violation_group(board, "Via", "CLK", 3)
            # Creates group named "EMC_Via_CLK_3"
            self.draw_error_marker(board, pos, msg, layer, group)
        
        Benefits:
            - Consistent naming convention across all checks
            - Single place to modify group creation logic
            - Eliminates 3-line boilerplate repeated 40+ times
        """
        group = pcbnew.PCB_GROUP(board)
        
        if violation_number is not None:
            name = f"EMC_{check_type}_{identifier}_{violation_number}"
        else:
            name = f"EMC_{check_type}_{identifier}"
        
        group.SetName(name)
        board.Add(group)
        return group

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
        log_func = self.create_logger(verbose, self.report_lines)
        violations = checker.check(
            draw_marker_func=self.draw_error_marker,
            draw_arrow_func=self.draw_arrow,
            get_distance_func=self.get_distance,
            log_func=log_func,
            create_group_func=self.create_violation_group
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
        log_func = self.create_logger(verbose, self.report_lines)
        violations = checker.check(
            draw_marker_func=self.draw_error_marker,
            draw_arrow_func=self.draw_arrow,
            get_distance_func=self.get_distance,
            log_func=log_func,
            create_group_func=self.create_violation_group
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