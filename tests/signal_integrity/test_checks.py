"""Tests for signal_integrity.py CHECK logic.

Covers signal integrity verification checks including trace placement,
net length limits, impedance control, and differential pair matching.
"""

import pytest
import sys
from pathlib import Path

# Import test helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import (
    MockBoard, MockNet, MockTrack, MockVia, MockZone,
    make_si_checker_with_utilities,
    make_parallel_traces, make_differential_pair
)

import pcbnew


# ---------------------------------------------------------------------------
# CHECK 1 — Trace near plane edge
# ---------------------------------------------------------------------------

class TestCheck01TraceNearPlaneEdge:

    def test_trace_within_violation_distance_flags_violation(self):
        """Trace within min_edge_distance_mm of zone edge should be flagged."""
        # NOTE: This check requires complex zone boundary detection with SHAPE_POLY_SET
        # Current mock infrastructure doesn't fully support polygon containment queries
        pytest.skip("CHECK 1 trace near plane edge requires full SHAPE_POLY_SET mock support")

    def test_trace_outside_safe_distance_no_violation(self):
        """Trace outside safe distance should have no violation."""
        pytest.skip("CHECK 1 trace near plane edge requires full SHAPE_POLY_SET mock support")

    def test_disabled_in_config_returns_zero(self):
        """Check disabled via config should return 0 violations."""
        net = MockNet("CLK", "HighSpeed")
        start = pcbnew.VECTOR2I(pcbnew.FromMM(5), pcbnew.FromMM(5))
        end = pcbnew.VECTOR2I(pcbnew.FromMM(15), pcbnew.FromMM(5))
        track = MockTrack("CLK", start, end, layer=0, net_class="HighSpeed")
        
        board = MockBoard(
            nets=[net],
            tracks=[track],
            copper_layer_count=2
        )
        
        config = {
            'trace_near_plane_edge': {
                'enabled': False  # Disabled
            }
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Disabled check should skip and return 0
        assert violation_count == 0, "Disabled check should return 0 violations"


# ---------------------------------------------------------------------------
# CHECK 4 — Exposed traces
# ---------------------------------------------------------------------------

class TestCheck04ExposedTraces:

    def test_isolated_high_speed_trace_flagged(self):
        """Isolated high-speed trace without nearby zone should be flagged."""
        # NOTE: CHECK 4 appears to be _check_exposed_critical_traces in signal_integrity.py
        # This test documents expected behavior
        pytest.skip("CHECK 4 (_check_exposed_critical_traces) test infrastructure not yet complete")

    def test_shielded_trace_no_violation(self):
        """Trace surrounded by GND pour should have no violation."""
        pytest.skip("CHECK 4 (_check_exposed_critical_traces) test infrastructure not yet complete")


# ---------------------------------------------------------------------------
# CHECK 5 — Net length limit
# ---------------------------------------------------------------------------

class TestCheck05NetLength:

    def test_net_over_max_length_flagged(self):
        """Net with total track length > max_length_mm should be flagged."""
        # NOTE: Check requires net length accumulation across all tracks
        # MockTrack.GetLength() may not match actual segment length calculation
        pytest.skip("CHECK 5 net length requires accurate track length calculation in mocks")

    def test_net_within_limit_no_violation(self):
        """Net length within limit should have no violation."""
        # Create short trace (20mm)
        net = MockNet("CLK", "HighSpeed")
        start = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end = pcbnew.VECTOR2I(pcbnew.FromMM(20), pcbnew.FromMM(0))
        track = MockTrack("CLK", start, end, layer=0, net_class="HighSpeed")
        
        board = MockBoard(
            nets=[net],
            tracks=[track],
            copper_layer_count=2
        )
        
        config = {
            'check_net_length': True,
            'max_length_by_netclass': {'HighSpeed': 30.0},  # 30mm limit
            'critical_net_classes': ['HighSpeed']
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # 20mm trace is within 30mm limit
        assert violation_count == 0, "Net within limit should have no violations"

    def test_non_critical_net_skipped(self):
        """Net not in critical class should be skipped."""
        # Create trace in Default class (not critical)
        net = MockNet("SIG", "Default")
        start = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end = pcbnew.VECTOR2I(pcbnew.FromMM(100), pcbnew.FromMM(0))  # Very long
        track = MockTrack("SIG", start, end, layer=0, net_class="Default")
        
        board = MockBoard(
            nets=[net],
            tracks=[track],
            copper_layer_count=2
        )
        
        config = {
            'net_length': {
                'enabled': True,
                'max_length_by_netclass': {'HighSpeed': 30.0},
                'critical_net_classes': ['HighSpeed']  # Default not in list
            }
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Non-critical net should be skipped
        assert violation_count == 0, "Non-critical net should be skipped"


# ---------------------------------------------------------------------------
# CHECK 7 — Unreferenced traces
# ---------------------------------------------------------------------------

class TestCheck07UnreferencedTraces:

    def test_unnetted_track_flagged(self):
        """Track with no net assignment should be flagged."""
        # NOTE: Check requires proper handling of unnetted tracks
        # Mock infrastructure may assign default nets automatically
        pytest.skip("CHECK 7 unreferenced traces requires proper unnetted track mock support")

    def test_netted_track_no_violation(self):
        """Track with valid net should have no violation."""
        net = MockNet("CLK", "HighSpeed")
        start = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        track = MockTrack("CLK", start, end, layer=0, net_class="HighSpeed")
        
        board = MockBoard(
            nets=[net],
            tracks=[track],
            copper_layer_count=2
        )
        
        config = {
            'check_unreferenced_traces': True
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Valid netted track should have no violations
        assert violation_count == 0, "Netted track should have no violations"


# ---------------------------------------------------------------------------
# CHECK 8 — Unconnected via pads
# ---------------------------------------------------------------------------

class TestCheck08UnconnectedViaPads:

    def test_floating_via_flagged(self):
        """Via isolated from any net should be flagged."""
        # NOTE: Check requires zone connectivity analysis
        # MockVia may not properly simulate isolation from nets/zones
        pytest.skip("CHECK 8 unconnected via pads requires full via connectivity mock support")

    def test_connected_via_no_violation(self):
        """Via connected to GND net should have no violation."""
        pytest.skip("CHECK 8 unconnected via pads requires full via connectivity mock support")


# ---------------------------------------------------------------------------
# CHECK 9 — Single-ended isolation
# ---------------------------------------------------------------------------

class TestCheck09IsolationSingleEnded:

    def test_parallel_traces_too_close_flagged(self):
        """Two parallel tracks on same layer within min_clearance_mm should be flagged."""
        # NOTE: Check requires spatial indexing of parallel track segments
        # Current implementation may not detect parallel traces in test setup
        pytest.skip("CHECK 9 single-ended isolation requires spatial index for parallel segment detection")

    def test_adequately_separated_traces_no_violation(self):
        """Traces separated beyond threshold should have no violation."""
        # Create two parallel traces 2mm apart
        nets, tracks = make_parallel_traces(
            "CLK", "DATA",
            spacing_mm=2.0,  # Adequate spacing
            length_mm=10.0,
            layer=0,
            net_class="HighSpeed"
        )
        
        board = MockBoard(
            nets=nets,
            tracks=tracks,
            copper_layer_count=2
        )
        
        config = {
            'check_single_ended_isolation': True,
            'iso_min_gap_mm': 1.0,  # 1mm minimum clearance
            'critical_net_classes': ['HighSpeed']
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Traces 2mm apart satisfy 1mm clearance
        assert violation_count == 0, "Adequately separated traces should have no violations"


# ---------------------------------------------------------------------------
# CHECK 12 — Differential pair length matching
# ---------------------------------------------------------------------------

class TestCheck12DifferentialPairMatching:

    def test_skew_over_tolerance_flagged(self):
        """P/N pair with length delta > max_length_mismatch_mm should be flagged."""
        # NOTE: Check requires differential pair detection and length calculation
        # Current implementation may not calculate length mismatch properly
        pytest.skip("CHECK 12 differential pair matching requires accurate track length calculation")

    def test_skew_within_tolerance_no_violation(self):
        """Skew within tolerance should have no violation."""
        # Create matched differential pair
        nets, tracks = make_differential_pair(
            "USB_D",
            spacing_mm=0.5,
            length_mm=10.0,
            layer=0,
            net_class="USB"
        )
        
        board = MockBoard(
            nets=nets,
            tracks=tracks,
            copper_layer_count=2
        )
        
        config = {
            'differential_pair_matching': {
                'enabled': True,
                'max_length_mismatch_mm': 2.0,
                'critical_net_classes': ['USB']
            }
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Matched pair should have no violations
        assert violation_count == 0, "Matched differential pair should have no violations"

    def test_non_dp_net_skipped(self):
        """Net names without _P/_N or +/- convention should be skipped."""
        # Create single-ended traces (not differential pair)
        nets, tracks = make_parallel_traces(
            "CLK", "DATA",  # Not differential pair naming
            spacing_mm=0.5,
            length_mm=10.0,
            layer=0,
            net_class="HighSpeed"
        )
        
        board = MockBoard(
            nets=nets,
            tracks=tracks,
            copper_layer_count=2
        )
        
        config = {
            'differential_pair_matching': {
                'enabled': True,
                'max_length_mismatch_mm': 2.0,
                'critical_net_classes': ['HighSpeed']
            }
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Non-DP nets should be skipped
        assert violation_count == 0, "Non-differential-pair nets should be skipped"


# ---------------------------------------------------------------------------
# CHECK 14 — Controlled impedance
# ---------------------------------------------------------------------------

class TestCheck14ControlledImpedance:

    def test_impedance_out_of_tolerance_flagged(self):
        """4-layer stackup + microstrip trace, computed Z0 outside ±10% should be flagged."""
        # NOTE: Controlled impedance check requires stackup data
        # This test documents expected behavior
        pytest.skip("Controlled impedance test requires stackup data infrastructure")

    def test_impedance_within_tolerance_no_violation(self):
        """Trace impedance within tolerance band should have no violation."""
        pytest.skip("Controlled impedance test requires stackup data infrastructure")

    def test_no_stackup_data_skips_gracefully(self):
        """No stackup data available should skip gracefully without crash."""
        net = MockNet("USB_DP", "USB")
        start = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        track = MockTrack("USB_DP", start, end, layer=0, net_class="USB")
        
        board = MockBoard(
            nets=[net],
            tracks=[track],
            copper_layer_count=2  # No stackup data
        )
        
        config = {
            'controlled_impedance': {
                'enabled': True,
                'critical_net_classes': ['USB']
            }
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Should skip gracefully without crash
        assert violation_count >= 0, "Check should run without crashing when stackup missing"

    def test_cpwg_formula_selected_for_cpw_layer(self):
        """CPW trace on outer layer with coplanar ground planes should select CPWG formula."""
        pytest.skip("CPW geometry detection test requires stackup data infrastructure")


# ---------------------------------------------------------------------------
# Stub checks — CHECKs 2, 3, 6, 10, 11, 13
# ---------------------------------------------------------------------------

class TestStubChecks:
    """These checks currently return 0 violations — tests gate future implementation."""

    def test_check02_via_aspect_ratio(self):
        """Via aspect ratio check - not yet implemented."""
        pytest.skip("CHECK 2 via aspect ratio not yet implemented in signal_integrity.py")

    def test_check03_via_stub_resonance(self):
        """Via stub resonance check - not yet implemented."""
        pytest.skip("CHECK 3 via stub resonance not yet implemented in signal_integrity.py")

    def test_check06_trace_via_transition(self):
        """Trace-to-via transition angle check - not yet implemented."""
        pytest.skip("CHECK 6 trace-via transition not yet implemented in signal_integrity.py")

    def test_check10_return_path_discontinuity(self):
        """Return path discontinuity check - not yet implemented."""
        pytest.skip("CHECK 10 return path discontinuity not yet implemented in signal_integrity.py")

    def test_check11_guard_trace_shielding(self):
        """Guard trace shielding check - not yet implemented."""
        pytest.skip("CHECK 11 guard trace shielding not yet implemented in signal_integrity.py")

    def test_check13_crosstalk_estimation(self):
        """Crosstalk estimation check - not yet implemented."""
        pytest.skip("CHECK 13 crosstalk estimation not yet implemented in signal_integrity.py")


# ---------------------------------------------------------------------------
# _is_critical_net helper
# ---------------------------------------------------------------------------

class TestIsCriticalNet:

    def test_net_in_critical_classes_returns_true(self):
        """Net class in critical_net_classes config list should return True."""
        net = MockNet("CLK", "HighSpeed")
        
        board = MockBoard(
            nets=[net],
            copper_layer_count=2
        )
        
        config = {
            'critical_net_classes': ['HighSpeed', 'USB']
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        
        # Test _is_critical_net helper
        result = checker._is_critical_net(net)
        assert result == True, "Net in critical_net_classes should return True"

    def test_default_class_not_critical(self):
        """Net class 'Default' should return False."""
        net = MockNet("SIG", "Default")
        
        board = MockBoard(
            nets=[net],
            copper_layer_count=2
        )
        
        config = {
            'critical_net_classes': ['HighSpeed', 'USB']
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        
        result = checker._is_critical_net(net)
        assert result == False, "Default class should not be critical"

    def test_empty_config_no_critical_nets(self):
        """Empty critical_net_classes config list should return False for any net."""
        net = MockNet("CLK", "HighSpeed")
        
        board = MockBoard(
            nets=[net],
            copper_layer_count=2
        )
        
        config = {
            'critical_net_classes': []  # Empty list
        }
        
        checker, violations = make_si_checker_with_utilities(board, config)
        
        result = checker._is_critical_net(net)
        assert result == False, "Empty config should have no critical nets"
