"""
Test suite for ground_plane.py - Priorities 1-3 implemented.

Covers return path continuity checks: slots, splits, and cutouts in reference
planes directly beneath high-speed signal traces degrade the EMC return current
path and must be flagged.

Test Structure:
- Priority 1: Slot/gap detection under traces (TestSlotUnderTrace)
- Priority 2: Split plane crossing detection (TestPlaneSplitCrossing)
- Priority 3: Return via continuity (TestReturnViaContinuity)
"""

import pytest
import sys
from pathlib import Path

# Add parent src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

# Always import mock classes for testing
from tests.helpers import MockBoard, MockZone, MockTrack, MockVia, MockPad, MockFootprint

# pcbnew will be available via conftest.py mock
import pcbnew

from ground_plane import GroundPlaneChecker


# ========================================================================
# PRIORITY 1: SLOT/GAP DETECTION UNDER TRACES
# ========================================================================

class TestSlotUnderTrace:
    """
    PRIORITY 1: Physical slot/cutout in the GND plane beneath a trace breaks the return path.
    
    Tests the check_continuity_under_trace functionality with dynamic zone discovery.
    No layer-to-plane mapping assumptions - zones discovered at runtime.
    """

    def test_slot_under_trace_flagged(self):
        """
        Test Case: Trace over gap in ground plane
        Expected: Violation marker at gap position
        
        Setup:
        - Critical signal trace on F.Cu (net: CLK, class: HighSpeed)
        - Ground zone on In1.Cu with intentional slot/gap under trace
        - Sample point falls on gap
        
        Expected Behavior:
        - Gap detected at sample point
        - Violation marker drawn with message "NO GND PLANE UNDER TRACE"
        - Group name: EMC_GndPlane_CLK_1
        """
        # Create test board
        import pcbnew
        start_pos = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end_pos = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        # Ground zone with gap: coverage only from x=0 to x=4mm, then gap from x=4mm to x=6mm
        zone = MockZone(
            net_name="GND",
            layer=1,  # In1.Cu
            filled=True,
            coverage_rects=[
                (pcbnew.FromMM(0), pcbnew.FromMM(-5), pcbnew.FromMM(4), pcbnew.FromMM(5)),
                (pcbnew.FromMM(6), pcbnew.FromMM(-5), pcbnew.FromMM(10), pcbnew.FromMM(5))
            ]
        )
        
        track = MockTrack(
            net_name="CLK",
            start=start_pos,
            end=end_pos,
            layer=0,  # F.Cu
            net_class="HighSpeed"
        )
        
        board = MockBoard(tracks=[track], zones=[zone], copper_layer_count=4)
        
        # Config
        config = {
            'enabled': True,
            'check_continuity_under_trace': True,
            'ground_plane_check_layers': 'all',  # Check all layers
            'critical_net_classes': ['HighSpeed', 'Clock'],
            'ground_net_patterns': ['GND'],
            'sampling_interval_mm': 0.5,
            'violation_message_no_ground_under_trace': 'NO GND PLANE UNDER TRACE',
            'check_split_plane_crossing': False,
            'check_return_via_continuity': False
        }
        
        report_lines = []
        checker = GroundPlaneChecker(
            board=board,
            marker_layer=pcbnew.User_1,
            config=config,
            report_lines=report_lines,
            verbose=True,
            auditor=None
        )
        
        # Run check
        violations = checker.check(
            draw_marker_func=lambda *args: None,
            draw_arrow_func=lambda *args: None,
            get_distance_func=lambda p1, p2: ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5,
            log_func=lambda msg, force=False: None,
            create_group_func=lambda board, typ, id, num: None
        )
        
        # Assert violation detected
        assert violations >= 1, "Expected at least 1 violation for gap under trace"

    def test_solid_plane_no_violation(self):
        """
        Test Case: Trace over solid ground plane (no gaps)
        Expected: No violations
        
        Setup:
        - Critical signal trace on F.Cu
        - Solid ground zone on In1.Cu (HitTestFilledArea always True)
        
        Expected Behavior:
        - All sample points have ground coverage
        - No violations
        """
        # Create test board
        import pcbnew
        start_pos = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end_pos = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        # Solid ground zone (covers entire area)
        zone = MockZone(
            net_name="GND",
            layer=1,  # In1.Cu
            filled=True,
            coverage_rects=[
                (pcbnew.FromMM(-10), pcbnew.FromMM(-10), pcbnew.FromMM(20), pcbnew.FromMM(10))
            ]
        )
        
        track = MockTrack(
            net_name="CLK",
            start=start_pos,
            end=end_pos,
            layer=0,  # F.Cu
            net_class="HighSpeed"
        )
        
        board = MockBoard(tracks=[track], zones=[zone], copper_layer_count=4)
        
        # Config
        config = {
            'enabled': True,
            'check_continuity_under_trace': True,
            'critical_net_classes': ['HighSpeed', 'Clock'],
            'ground_net_patterns': ['GND'],
            'sampling_interval_mm': 0.5,
            'check_split_plane_crossing': False,
            'check_return_via_continuity': False
        }
        
        report_lines = []
        checker = GroundPlaneChecker(
            board=board,
            marker_layer=pcbnew.User_1,
            config=config,
            report_lines=report_lines,
            verbose=True,
            auditor=None
        )
        
        # Run check
        violations = checker.check(
            draw_marker_func=lambda *args: None,
            draw_arrow_func=lambda *args: None,
            get_distance_func=lambda p1, p2: ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5,
            log_func=lambda msg, force=False: None,
            create_group_func=lambda board, typ, id, num: None
        )
        
        # Assert no violations
        assert violations == 0, "Expected 0 violations for solid ground plane"

    def test_disabled_in_config_returns_zero(self):
        """
        Test Case: Ground plane check disabled via config
        Expected: 0 violations (check skipped)
        
        Setup:
        - Same as test_slot_under_trace_flagged but check_continuity_under_trace=False
        
        Expected Behavior:
        - Check skipped entirely
        - violations == 0
        """
        # Create test board (same as test_slot_under_trace_flagged)
        import pcbnew
        start_pos = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end_pos = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        # Ground zone with gap
        zone = MockZone(
            net_name="GND",
            layer=1,  # In1.Cu
            filled=True,
            coverage_rects=[
                (pcbnew.FromMM(0), pcbnew.FromMM(-5), pcbnew.FromMM(4), pcbnew.FromMM(5)),
                (pcbnew.FromMM(6), pcbnew.FromMM(-5), pcbnew.FromMM(10), pcbnew.FromMM(5))
            ]
        )
        
        track = MockTrack(
            net_name="CLK",
            start=start_pos,
            end=end_pos,
            layer=0,  # F.Cu
            net_class="HighSpeed"
        )
        
        board = MockBoard(tracks=[track], zones=[zone], copper_layer_count=4)
        
        # Config with check DISABLED
        config = {
            'enabled': True,
            'check_continuity_under_trace': False,  # DISABLED
            'check_clearance_around_trace': False,  # Also disable clearance check
            'critical_net_classes': ['HighSpeed', 'Clock'],
            'ground_net_patterns': ['GND'],
            'sampling_interval_mm': 0.5,
            'check_split_plane_crossing': False,
            'check_return_via_continuity': False
        }
        
        report_lines = []
        checker = GroundPlaneChecker(
            board=board,
            marker_layer=pcbnew.User_1,
            config=config,
            report_lines=report_lines,
            verbose=True,
            auditor=None
        )
        
        # Run check
        violations = checker.check(
            draw_marker_func=lambda *args: None,
            draw_arrow_func=lambda *args: None,
            get_distance_func=lambda p1, p2: ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5,
            log_func=lambda msg, force=False: None,
            create_group_func=lambda board, typ, id, num: None
        )
        
        # Assert no violations (check was skipped)
        assert violations == 0, "Expected 0 violations when check is disabled"


# ========================================================================
# PRIORITY 2: SPLIT PLANE CROSSING DETECTION
# ========================================================================

class TestPlaneSplitCrossing:
    """
    PRIORITY 2: Trace crossing a split between two copper pours must be flagged.
    
    Tests dynamic zone discovery and split detection without layer-to-plane assumptions.
    Handles various board strategies:
    - Split planes on certain layers (GND/VCC splits)
    - Ground alignment under specific signals
    - Double tracks for high-current paths
    """

    @pytest.mark.skip(reason="TODO: implement MockZone for two adjacent zones (GND and VCC)")
    def test_trace_crossing_split_boundary_flagged(self):
        """
        Test Case: Trace crosses from GND zone to VCC zone
        Expected: Violation marker at split crossing
        
        Setup:
        - Signal trace on F.Cu crossing split boundary
        - In1.Cu has two zones: GND (left half) and VCC (right half)
        - Trace starts over GND, ends over VCC
        
        Expected Behavior:
        - Split crossing detected: GND→VCC
        - Violation marker at crossing point
        - Message: "SPLIT PLANE CROSSING: GND→VCC"
        - Group name: EMC_GndPlaneSplit_SIGNAL_1
        """
        if MOCK_PCBNEW:
            pytest.skip("Requires MockZone with boundary detection")
        
        # TODO: Create MockBoard with:
        # - MockTrack (signal net, crossing split)
        # - MockZone (GND net, left half of board)
        # - MockZone (VCC net, right half of board)
        # - Config: check_split_plane_crossing=True
        
        # TODO: Run checker.check()
        # TODO: Assert violations == 1
        # TODO: Assert marker message contains "SPLIT PLANE CROSSING"

    @pytest.mark.skip(reason="TODO: implement MockZone for single zone coverage")
    def test_trace_within_single_pour_no_violation(self):
        """
        Test Case: Trace stays entirely within one zone
        Expected: No violations
        
        Setup:
        - Signal trace entirely over GND zone
        - No split crossing
        
        Expected Behavior:
        - No zone transitions detected
        - violations == 0
        """
        if MOCK_PCBNEW:
            pytest.skip("Requires MockZone implementation")

    @pytest.mark.skip(reason="TODO: implement net class filtering")
    def test_low_speed_net_over_split_skipped(self):
        """
        Test Case: Low-frequency net crosses split (should be ignored)
        Expected: No violation (not in critical_net_classes)
        
        Setup:
        - Trace on "Default" net class (not HighSpeed/Clock)
        - Crosses GND→VCC split
        
        Expected Behavior:
        - Trace not in critical_net_classes
        - Check skipped
        - violations == 0
        """
        if MOCK_PCBNEW:
            pytest.skip("Requires net class filtering")


# ========================================================================
# PRIORITY 3: RETURN VIA CONTINUITY
# ========================================================================

class TestReturnViaContinuity:
    """
    PRIORITY 3: Layer transitions (vias) must have nearby GND vias to maintain return path.
    
    IPC-2221 / High-Speed Design Guidelines:
    - Return vias should be within 3mm (default) of signal vias
    - Closer is better for high-speed signals (<1mm)
    """

    def test_signal_via_without_return_via_flagged(self):
        """
        Test Case: Signal via with no ground via nearby
        Expected: Violation marker at signal via
        
        Setup:
        - Signal via (CLK net) at position (10, 10)
        - Ground via (GND net) at position (20, 20) - distance > 3mm
        - Config: return_via_max_distance_mm=3.0
        
        Expected Behavior:
        - Distance check: >3mm
        - Violation marker at signal via position
        - Message: "NO RETURN VIA: 14.1mm" (or actual distance)
        - Group name: EMC_ReturnVia_CLK_1
        """
        # Create test board with vias far apart
        import pcbnew
        
        # Signal via at (10, 10) mm
        signal_via = MockVia(
            net_name="CLK",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            drill_diameter=0.3,
            net_class="HighSpeed"  # Critical net class
        )
        
        # Ground via at (20, 20) mm - distance = sqrt((20-10)^2 + (20-10)^2) = 14.14mm
        ground_via = MockVia(
            net_name="GND",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(20), pcbnew.FromMM(20)),
            drill_diameter=0.3,
            net_class="Default"  # Ground via doesn't need critical class
        )
        
        # Add a dummy track to satisfy critical_tracks check
        dummy_track = MockTrack(
            net_name="CLK",
            start=pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)),
            end=pcbnew.VECTOR2I(pcbnew.FromMM(1), pcbnew.FromMM(0)),
            layer=0,
            net_class="HighSpeed"
        )
        
        # Add a dummy zone to prevent early bailout (must be >= 10mm² to pass min area check)
        dummy_zone = MockZone(
            net_name="GND",
            layer=1,
            filled=True,
            coverage_rects=[(pcbnew.FromMM(0), pcbnew.FromMM(0), pcbnew.FromMM(10), pcbnew.FromMM(10))]
        )
        
        board = MockBoard(tracks=[signal_via, ground_via, dummy_track], zones=[dummy_zone], copper_layer_count=4)
        
        # Config
        config = {
            'enabled': True,
            'check_continuity_under_trace': False,
            'check_clearance_around_trace': False,
            'check_split_plane_crossing': False,
            'check_return_via_continuity': True,  # ENABLED
            'return_via_max_distance_mm': 3.0,
            'ground_plane_check_layers': 'all',  # Avoid early bailouts
            'critical_net_classes': ['HighSpeed', 'Clock'],
            'ground_net_patterns': ['GND'],
            'violation_message_no_return_via': 'NO RETURN VIA'
        }
        
        report_lines = []
        checker = GroundPlaneChecker(
            board=board,
            marker_layer=pcbnew.User_1,
            config=config,
            report_lines=report_lines,
            verbose=True,
            auditor=None
        )
        
        # Run check
        all_logs = []
        violations = checker.check(
            draw_marker_func=lambda *args: None,
            draw_arrow_func=lambda *args: None,
            get_distance_func=lambda p1, p2: ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5,
            log_func=lambda msg, force=False: all_logs.append(msg),
            create_group_func=lambda board, typ, id, num: None
        )
        
        # Assert violation detected
        if violations == 0:
            print(f"\\n===  ALL LOGS ===")
            for i, log in enumerate(all_logs):
                # Encode to ASCII, replacing special chars to avoid Windows console errors
                safe_log = log.encode('ascii', 'replace').decode('ascii')
                print(f"{i}: {safe_log}")
        print(f"\\nDEBUG: Got {violations} violations, expected 1")
        assert violations >= 1, f"Expected at least 1 violation for signal via without return via, got {violations}"

    def test_signal_via_with_return_via_no_violation(self):
        """
        Test Case: Signal via with ground via within max_distance
        Expected: No violations
        
        Setup:
        - Signal via (USB_D+ net) at position (10, 10)
        - Ground via (GND net) at position (11, 10) - distance = 1mm
        - Config: return_via_max_distance_mm=3.0
        
        Expected Behavior:
        - Distance check: 1mm < 3mm → PASS
        - violations == 0
        """
        # Create test board with vias close together
        import pcbnew
        
        # Signal via at (10, 10) mm
        signal_via = MockVia(
            net_name="USB_D+",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(10)),
            drill_diameter=0.3,
            net_class="HighSpeed"  # Critical net class
        )
        
        # Ground via at (11, 10) mm - distance = 1mm (well within limit)
        ground_via = MockVia(
            net_name="GND",
            position=pcbnew.VECTOR2I(pcbnew.FromMM(11), pcbnew.FromMM(10)),
            drill_diameter=0.3,
            net_class="Default"  # Ground via doesn't need critical class
        )
        
        # Add a dummy track to satisfy critical_tracks check
        dummy_track = MockTrack(
            net_name="USB_D+",
            start=pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)),
            end=pcbnew.VECTOR2I(pcbnew.FromMM(1), pcbnew.FromMM(0)),
            layer=0,
            net_class="HighSpeed"
        )
        
        # Add a dummy zone to prevent early bailout (must be >= 10mm² to pass min area check)
        dummy_zone = MockZone(
            net_name="GND",
            layer=1,
            filled=True,
            coverage_rects=[(pcbnew.FromMM(0), pcbnew.FromMM(0), pcbnew.FromMM(10), pcbnew.FromMM(10))]
        )
        
        board = MockBoard(tracks=[signal_via, ground_via, dummy_track], zones=[dummy_zone], copper_layer_count=4)
        
        # Config
        config = {
            'enabled': True,
            'check_continuity_under_trace': False,
            'check_clearance_around_trace': False,
            'check_split_plane_crossing': False,
            'check_return_via_continuity': True,  # ENABLED
            'return_via_max_distance_mm': 3.0,
            'ground_plane_check_layers': 'all',  # Avoid early bailouts
            'critical_net_classes': ['HighSpeed', 'Clock'],
            'ground_net_patterns': ['GND']
        }
        
        report_lines = []
        checker = GroundPlaneChecker(
            board=board,
            marker_layer=pcbnew.User_1,
            config=config,
            report_lines=report_lines,
            verbose=True,
            auditor=None
        )
        
        # Run check
        violations = checker.check(
            draw_marker_func=lambda *args: None,
            draw_arrow_func=lambda *args: None,
            get_distance_func=lambda p1, p2: ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5,
            log_func=lambda msg, force=False: None,
            create_group_func=lambda board, typ, id, num: None
        )
        
        # Assert no violations
        assert violations == 0, f"Expected 0 violations for signal via with nearby return via, got {violations}"


# ========================================================================
# PRIORITY 4: MINIMUM PLANE AREA (Future)
# ========================================================================

class TestMinimumPlaneArea:
    """
    PRIORITY 4 (Future): The GND copper pour must cover a minimum fraction of the board area.
    
    Ensures adequate ground plane coverage for EMC compliance.
    Typical minimums: 30% (low-speed), 60% (high-speed), 90% (RF).
    """

    @pytest.mark.skip(reason="TODO: implement board area calculation")
    def test_insufficient_plane_coverage_flagged(self):
        """
        Test Case: Ground plane covers < min_coverage_percent
        Expected: Global violation marker
        
        Setup:
        - Board area: 100mm x 100mm = 10,000mm²
        - Ground zone area: 2,000mm² (20%)
        - Config: min_coverage_percent=30.0
        
        Expected Behavior:
        - Coverage: 20% < 30% → VIOLATION
        - Global marker drawn (center of board?)
        - Message: "GND COVERAGE: 20% < 30%"
        """
        if MOCK_PCBNEW:
            pytest.skip("Requires board area calculation")

    @pytest.mark.skip(reason="TODO: implement board area calculation")
    def test_adequate_plane_coverage_no_violation(self):
        """
        Test Case: Ground plane exceeds minimum coverage
        Expected: No violations
        
        Setup:
        - Board area: 10,000mm²
        - Ground zone area: 8,000mm² (80%)
        - Config: min_coverage_percent=30.0
        
        Expected Behavior:
        - Coverage: 80% > 30% → PASS
        - violations == 0
        """
        if MOCK_PCBNEW:
            pytest.skip("Requires board area calculation")


# ========================================================================
# INTEGRATION TESTS
# ========================================================================

class TestGroundPlaneIntegration:
    """Integration tests combining multiple checks."""

    @pytest.mark.skip(reason="TODO: implement full integration test")
    def test_all_checks_combined(self):
        """
        Test Case: Board with multiple violations across all priority checks
        Expected: All violations detected and marked correctly
        
        Setup:
        - Trace with gap under it (Priority 1)
        - Trace crossing split plane (Priority 2)
        - Signal via without return via (Priority 3)
        
        Expected Behavior:
        - Total violations: 3
        - Each violation correctly identified and marked
        """
        if MOCK_PCBNEW:
            pytest.skip("Requires full mock implementation")

    @pytest.mark.skip(reason="TODO: implement performance test")
    def test_performance_large_board(self):
        """
        Test Case: Large board with 100+ tracks and zones
        Expected: Completes within reasonable time (<5s)
        
        Setup:
        - 100 critical tracks
        - 50 zones
        - All checks enabled
        
        Expected Behavior:
        - Check completes
        - Progress dialog shown
        - Performance: <5s for 100 tracks
        """
        if MOCK_PCBNEW:
            pytest.skip("Requires performance benchmarking")
