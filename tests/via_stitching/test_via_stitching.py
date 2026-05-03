"""
Unit tests for via_stitching.py.

Covers GND return via proximity and stitching density checks per IPC-2221:
high-speed traces require closely spaced GND vias to provide low-inductance
return current paths and reduce EMI radiation.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock
import importlib.util

# Add tests/helpers.py to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import MockBoard, MockVia, MockNet, MockBoundingBox

# Import pcbnew after conftest has mocked it
import pcbnew

# Import ViaStitchingChecker from src/ directory (not tests/via_stitching/)
def _load_via_stitching_checker():
    """Load ViaStitchingChecker from src/via_stitching.py to avoid test directory shadowing."""
    src_path = Path(__file__).parent.parent.parent / "src" / "via_stitching.py"
    spec = importlib.util.spec_from_file_location("via_stitching_module", src_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ViaStitchingChecker

ViaStitchingChecker = _load_via_stitching_checker()


class TestReturnViaProximity:
    """Every high-speed signal via must have a GND via within max_distance_mm."""

    def test_trace_missing_nearby_gnd_via_flagged(self):
        """Critical via with no nearby GND via should create violation marker."""
        # Setup: Critical via at (10, 10), GND via at (15, 10) = 5mm away (exceeds 2mm threshold)
        critical_via = MockVia(
            net_name="USB_DP",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            net_class="HighSpeed"
        )
        gnd_via = MockVia(
            net_name="GND",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(15), pcbnew.FromMM(10)),
            net_class="Default"
        )
        
        # Create board with nets and vias
        nets = [
            MockNet("USB_DP", "HighSpeed"),
            MockNet("GND", "Default")
        ]
        board = MockBoard(
            nets=nets,
            tracks=[critical_via, gnd_via]
        )
        
        # Create checker with standard config
        config = {
            'max_distance_mm': 2.0,
            'critical_net_classes': ['HighSpeed'],
            'ground_net_patterns': ['GND'],
            'violation_message': 'NO GND VIA',
            'draw_arrow_to_nearest_gnd': True
        }
        
        # Mock auditor with get_nets_by_class utility
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: ['USB_DP'] if cls == 'HighSpeed' else []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg, 'layer': layer})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        mock_group_counter = [0]
        def mock_create_group(board, check_type, identifier, number):
            mock_group_counter[0] += 1
            group = pcbnew.PCB_GROUP()
            group.SetName(f"EMC_{check_type}_{identifier}_{number}")
            return group
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert
        assert violations == 1, "Expected 1 violation for critical via without nearby GND via"
        assert len(violations_drawn) == 1, "Expected 1 violation marker drawn"
        assert violations_drawn[0]['msg'] == 'NO GND VIA', "Expected 'NO GND VIA' message"
        assert mock_group_counter[0] == 1, "Expected 1 violation group created"

    def test_gnd_via_within_distance_no_violation(self):
        """Critical via with nearby GND via should NOT create violation."""
        # Setup: Critical via at (10, 10), GND via at (11, 10) = 1mm away (within 2mm threshold)
        critical_via = MockVia(
            net_name="CLK",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            net_class="Clock"
        )
        gnd_via = MockVia(
            net_name="GND",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(11), pcbnew.FromMM(10)),
            net_class="Default"
        )
        
        nets = [
            MockNet("CLK", "Clock"),
            MockNet("GND", "Default")
        ]
        board = MockBoard(
            nets=nets,
            tracks=[critical_via, gnd_via]
        )
        
        config = {
            'max_distance_mm': 2.0,
            'critical_net_classes': ['Clock'],
            'ground_net_patterns': ['GND'],
            'violation_message': 'NO GND VIA'
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: ['CLK'] if cls == 'Clock' else []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        def mock_create_group(board, check_type, identifier, number):
            group = pcbnew.PCB_GROUP()
            return group
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert
        assert violations == 0, "Expected 0 violations when GND via is within threshold"
        assert len(violations_drawn) == 0, "Expected no violation markers drawn"

    def test_disabled_in_config_returns_zero(self):
        """Check disabled in config should return 0 violations without processing."""
        # Note: The enabled flag is checked in emc_auditor_plugin.py before calling this checker
        # This test verifies the checker handles empty config gracefully
        
        critical_via = MockVia(
            net_name="USB_DP",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            net_class="HighSpeed"
        )
        
        nets = [MockNet("USB_DP", "HighSpeed")]
        board = MockBoard(nets=nets, tracks=[critical_via])
        
        # Empty config simulates disabled check (no critical_net_classes)
        config = {
            'max_distance_mm': 2.0,
            'critical_net_classes': [],  # No critical classes = no checks
            'ground_net_patterns': ['GND'],
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        def mock_draw_marker(board, pos, msg, layer, group):
            pass
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            return 0
        
        def mock_log(msg, force=False):
            pass
        
        def mock_create_group(board, check_type, identifier, number):
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert
        assert violations == 0, "Expected 0 violations when no critical net classes configured"

    def test_low_speed_net_skipped(self):
        """Via on non-critical net should be skipped (no check, no violation)."""
        # Setup: Via on "Default" net class (not in critical_net_classes)
        default_via = MockVia(
            net_name="LED_1",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            net_class="Default"
        )
        
        nets = [MockNet("LED_1", "Default")]
        board = MockBoard(nets=nets, tracks=[default_via])
        
        config = {
            'max_distance_mm': 2.0,
            'critical_net_classes': ['HighSpeed', 'Clock'],  # LED_1 not in list
            'ground_net_patterns': ['GND'],
        }
        
        mock_auditor = MagicMock()
        # Return empty list for HighSpeed and Clock classes
        mock_auditor.get_nets_by_class = lambda board, cls: []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            return 0
        
        def mock_log(msg, force=False):
            pass
        
        def mock_create_group(board, check_type, identifier, number):
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert
        assert violations == 0, "Expected 0 violations for non-critical net class"
        assert len(violations_drawn) == 0, "Expected no markers for non-critical via"


class TestStitchingDensity:
    """GND copper pours must have at least min_stitch_count vias per area."""

    def test_insufficient_stitch_density_flagged(self):
        """
        Verify large GND pour with insufficient via density creates violation.
        
        Tests area-based density checking: ensures GND planes have adequate via stitching
        for current distribution and EMI reduction.
        """
        from helpers import MockZone
        
        # Setup: Large 50mm x 50mm GND zone with only 1 stitch via (way too sparse)
        large_gnd_zone = MockZone(
            net_name="GND",
            layer=0,  # F.Cu
            filled=True,
            coverage_rects=[(
                pcbnew.FromMM(0), pcbnew.FromMM(0),
                pcbnew.FromMM(50), pcbnew.FromMM(50)
            )]
        )
        
        single_via = MockVia(
            net_name="GND",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(25), pcbnew.FromMM(25))
        )
        
        nets = [MockNet("GND", "Default")]
        board = MockBoard(
            nets=nets,
            zones=[large_gnd_zone],
            tracks=[single_via]
        )
        
        config = {
            'check_gnd_plane_density': True,  # Enable feature
            'min_stitch_vias_per_cm2': 4.0,  # Typical requirement: 4 vias per cm²
            'ground_net_patterns': ['GND']
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        mock_group_counter = [0]
        def mock_create_group(board, check_type, identifier, number):
            mock_group_counter[0] += 1
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Expected: 2500 mm² / 100 = 25 cm² * 4 vias/cm² = 100 vias needed, only 1 present
        assert violations == 1, f"Expected 1 violation for insufficient via density, got {violations}"
        assert len(violations_drawn) == 1, "Expected 1 violation marker"
        assert "LOW VIA DENSITY" in violations_drawn[0]['msg'], f"Expected 'LOW VIA DENSITY' in message, got: {violations_drawn[0]['msg']}"

    def test_adequate_stitch_density_no_violation(self):
        """
        Verify GND pour with adequate via density creates no violation.
        
        Tests that adequate via density does not create false positives.
        """
        from helpers import MockZone
        
        # Setup: Small 10mm x 10mm GND zone with 4 stitch vias (adequate density)
        small_gnd_zone = MockZone(
            net_name="GND",
            layer=0,
            filled=True,
            coverage_rects=[(
                pcbnew.FromMM(0), pcbnew.FromMM(0),
                pcbnew.FromMM(10), pcbnew.FromMM(10)
            )]
        )
        
        # 4 vias in 1 cm² = 4 vias/cm² (meets requirement)
        vias = [
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(2.5), pcbnew.FromMM(2.5))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(7.5), pcbnew.FromMM(2.5))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(2.5), pcbnew.FromMM(7.5))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(7.5), pcbnew.FromMM(7.5)))
        ]
        
        nets = [MockNet("GND", "Default")]
        board = MockBoard(
            nets=nets,
            zones=[small_gnd_zone],
            tracks=vias
        )
        
        config = {
            'check_gnd_plane_density': True,
            'min_stitch_vias_per_cm2': 4.0,
            'ground_net_patterns': ['GND']
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        def mock_create_group(board, check_type, identifier, number):
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Should return 0 violations (4 vias in 1 cm² = exactly 4 vias/cm²)
        assert violations == 0, f"Expected 0 violations for adequate density, got {violations}"
        assert len(violations_drawn) == 0, "Expected no violation markers"


class TestViaNetAssignment:
    """Only vias connected to GND net are counted as valid stitch vias."""

    def test_non_gnd_via_not_counted(self):
        """Via connected to VCC (non-GND net) should NOT be counted as ground return via."""
        # Setup: Critical via with nearby VCC via (not GND)
        critical_via = MockVia(
            net_name="USB_DP",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            net_class="HighSpeed"
        )
        
        # VCC via nearby (should NOT be counted as GND via)
        vcc_via = MockVia(
            net_name="VCC",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(11), pcbnew.FromMM(10)),
            net_class="Power"
        )
        
        # Actual GND via is far away
        gnd_via = MockVia(
            net_name="GND",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(20), pcbnew.FromMM(10)),
            net_class="Default"
        )
        
        nets = [
            MockNet("USB_DP", "HighSpeed"),
            MockNet("VCC", "Power"),
            MockNet("GND", "Default")
        ]
        board = MockBoard(
            nets=nets,
            tracks=[critical_via, vcc_via, gnd_via]
        )
        
        config = {
            'max_distance_mm': 2.0,
            'critical_net_classes': ['HighSpeed'],
            'ground_net_patterns': ['GND'],  # Only "GND" pattern, not "VCC"
            'violation_message': 'NO GND VIA'
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: ['USB_DP'] if cls == 'HighSpeed' else []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        mock_group_counter = [0]
        def mock_create_group(board, check_type, identifier, number):
            mock_group_counter[0] += 1
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert: VCC via should NOT be counted, so violation should be created
        assert violations == 1, "Expected violation: VCC via should not count as GND via"
        assert len(violations_drawn) == 1, "Expected 1 violation marker"
        assert violations_drawn[0]['msg'] == 'NO GND VIA', "Expected 'NO GND VIA' message"

    def test_unnetted_via_not_counted(self):
        """Via with empty/no net assignment should NOT be counted as ground via."""
        # Setup: Critical via with nearby unnetted via
        critical_via = MockVia(
            net_name="CLK",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            net_class="Clock"
        )
        
        # Unnetted via nearby (should NOT be counted as GND via)
        unnetted_via = MockVia(
            net_name="",  # Empty net name
            position=pcbnew.VECTOR2I(pcbnew.FromMM(11), pcbnew.FromMM(10)),
            net_class="Default"
        )
        
        # Real GND via is far away
        gnd_via = MockVia(
            net_name="GND",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(20), pcbnew.FromMM(10)),
            net_class="Default"
        )
        
        nets = [
            MockNet("CLK", "Clock"),
            MockNet("", "Default"),
            MockNet("GND", "Default")
        ]
        board = MockBoard(
            nets=nets,
            tracks=[critical_via, unnetted_via, gnd_via]
        )
        
        config = {
            'max_distance_mm': 2.0,
            'critical_net_classes': ['Clock'],
            'ground_net_patterns': ['GND'],
            'violation_message': 'NO GND VIA'
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: ['CLK'] if cls == 'Clock' else []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        def mock_create_group(board, check_type, identifier, number):
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert: Unnetted via should NOT be counted, so violation should be created
        assert violations == 1, "Expected violation: unnetted via should not count as GND via"
        assert len(violations_drawn) == 1, "Expected 1 violation marker"
        assert violations_drawn[0]['msg'] == 'NO GND VIA', "Expected 'NO GND VIA' message"


class TestEdgeStitching:
    """Board edge must have GND stitching vias within max_edge_stitch_mm."""

    def test_gap_in_edge_stitching_flagged(self):
        """
        Verify large gap in board edge stitching creates violation.
        
        Tests board edge stitching verification for EMI shielding.
        """
        # Setup: 100mm board edge with only 2 GND vias (20mm and 80mm) = 60mm gap
        board = MockBoard(
            board_bbox=MockBoundingBox(0, 0, pcbnew.FromMM(100), pcbnew.FromMM(100))
        )
        
        # Two GND vias on top edge with large gap
        edge_vias = [
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(20), pcbnew.FromMM(0))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(80), pcbnew.FromMM(0)))
        ]
        
        nets = [MockNet("GND", "Default")]
        board._nets = nets
        board._tracks = edge_vias
        
        config = {
            'check_edge_stitching': True,  # Enable feature
            'max_edge_stitch_spacing_mm': 20.0,  # Max 20mm between edge vias
            'edge_stitch_margin_mm': 2.0,  # Distance from board edge to count as "edge via"
            'ground_net_patterns': ['GND']
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        mock_group_counter = [0]
        def mock_create_group(board, check_type, identifier, number):
            mock_group_counter[0] += 1
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Should create violation for 60mm gap (exceeds 20mm max)
        assert violations == 1, f"Expected 1 violation for edge gap, got {violations}"
        assert len(violations_drawn) == 1, "Expected 1 violation marker"
        assert "EDGE GAP" in violations_drawn[0]['msg'], f"Expected 'EDGE GAP' in message, got: {violations_drawn[0]['msg']}"

    def test_dense_edge_stitching_no_violation(self):
        """
        Verify adequate board edge stitching creates no violation.
        
        Tests that adequate edge stitching does not create false positives.
        """
        # Setup: 100mm board edge with 6 GND vias evenly spaced (every 20mm)
        board = MockBoard(
            board_bbox=MockBoundingBox(0, 0, pcbnew.FromMM(100), pcbnew.FromMM(100))
        )
        
        # Dense edge stitching: vias every 20mm
        edge_vias = [
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(20), pcbnew.FromMM(0))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(40), pcbnew.FromMM(0))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(60), pcbnew.FromMM(0))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(80), pcbnew.FromMM(0))),
            MockVia("GND", pcbnew.VECTOR2I(pcbnew.FromMM(100), pcbnew.FromMM(0)))
        ]
        
        nets = [MockNet("GND", "Default")]
        board._nets = nets
        board._tracks = edge_vias
        
        config = {
            'check_edge_stitching': True,
            'max_edge_stitch_spacing_mm': 20.0,
            'edge_stitch_margin_mm': 2.0,
            'ground_net_patterns': ['GND']
        }
        
        mock_auditor = MagicMock()
        mock_auditor.get_nets_by_class = lambda board, cls: []
        
        checker = ViaStitchingChecker(
            board=board,
            marker_layer=pcbnew.User_Comments,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=mock_auditor
        )
        
        # Mock utility functions
        violations_drawn = []
        def mock_draw_marker(board, pos, msg, layer, group):
            violations_drawn.append({'pos': pos, 'msg': msg})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(pos1, pos2):
            dx = pos1.x - pos2.x
            dy = pos1.y - pos2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            pass
        
        def mock_create_group(board, check_type, identifier, number):
            return pcbnew.PCB_GROUP()
        
        # Execute check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Should return 0 violations (all spacing ≤ 20mm)
        assert violations == 0, f"Expected 0 violations for adequate edge stitching, got {violations}"
        assert len(violations_drawn) == 0, "Expected no violation markers"
