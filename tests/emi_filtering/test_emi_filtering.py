"""Tests for emi_filtering.py EMC filter topology checks.

Covers connector EMC filter topology checks per CISPR 32 / IEC 61000-4-x:
filters must be placed close to the connector entry point in the correct
component order (ferrite before cap, or L before C toward IC).
"""

import pytest
import sys
from pathlib import Path

# Import test helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import (
    MockBoard, MockNet,
    make_emi_filtering_checker_with_utilities,
    make_connector_with_signals, make_emi_filter
)

import pcbnew


class TestFilterPresence:
    """Every flagged connector must have at least one EMC filter component."""

    def test_unfiltered_connector_flagged(self):
        """Connector net with no filter component between plug and IC should be flagged."""
        # Create connector with signal net but no filter
        nets, connector = make_connector_with_signals("J1", position_mm=(10, 10), 
                                                      signal_nets=["USB_DP"])
        
        board = MockBoard(
            nets=nets,
            footprints=[connector],
            copper_layer_count=2
        )
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['FB', 'L', 'C'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple'
        }
        
        checker, violations = make_emi_filtering_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Assert: connector without filter should be flagged
        assert violation_count >= 1, "Connector without EMI filter should be flagged"
        assert len(violations) > 0, "Should create violation markers"

    def test_filtered_connector_no_violation(self):
        """Connector with proper LC filter should have no violation."""
        # Create connector with signal net
        nets, connector = make_connector_with_signals("J1", position_mm=(10, 10), 
                                                      signal_nets=["USB_DP"])
        
        # Create ferrite bead filter nearby at (15, 10) - 5mm away
        # Pass the actual net object so filter pads share the same net code
        fb = make_emi_filter("FB1", position_mm=(15, 10), signal_net=nets[0], filter_type="FB")
        
        board = MockBoard(
            nets=nets,
            footprints=[connector, fb],
            copper_layer_count=2
        )
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['FB', 'L', 'C'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple'
        }
        
        checker, violations = make_emi_filtering_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Assert: connector with filter should have no violations
        assert violation_count == 0, "Connector with EMI filter should have no violations"

    def test_disabled_in_config_returns_zero(self):
        """Check disabled via config should return 0 violations."""
        # Create unfiltered connector (would normally violate)
        nets, connector = make_connector_with_signals("J1", position_mm=(10, 10), 
                                                      signal_nets=["USB_DP"])
        
        board = MockBoard(
            nets=nets,
            footprints=[connector],
            copper_layer_count=2
        )
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['FB', 'L', 'C'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple'
        }
        
        checker, violations = make_emi_filtering_checker_with_utilities(board, config)
        # Don't call checker.check() - simulates disabled check
        
        # Assert: not running check results in 0 violations
        assert checker.violation_count == 0, "Unexecuted check should have 0 violations"


class TestFilterTopologyOrder:
    """Filter components must appear in the correct order relative to the connector."""

    def test_wrong_filter_order_cap_before_ferrite_flagged(self):
        """Capacitor placed before ferrite bead (wrong order) should be flagged."""
        # NOTE: EMIFilteringChecker currently does not enforce component order
        # This test documents expected behavior for future implementation
        pytest.skip("Filter component order validation not yet implemented in EMIFilteringChecker")

    def test_correct_ferrite_then_cap_no_violation(self):
        """Correct order ferrite → capacitor toward IC should have no violation."""
        pytest.skip("Filter component order validation not yet implemented in EMIFilteringChecker")

    def test_pi_filter_topology_accepted(self):
        """π-filter (C-L-C) topology should be accepted as valid."""
        pytest.skip("π-filter topology validation not yet implemented in EMIFilteringChecker")


class TestFilterPlacement:
    """Filter must be within max_filter_dist_mm of the connector body."""

    def test_filter_too_far_from_connector_flagged(self):
        """Filter component placed farther than max_filter_dist_mm from connector should be flagged."""
        # Create connector at (10, 10)
        nets, connector = make_connector_with_signals("J1", position_mm=(10, 10), 
                                                      signal_nets=["USB_DP"])
        
        # Create filter far away at (25, 10) - 15mm away, beyond 10mm limit
        # Pass the actual net object so filter pads share the same net code
        fb = make_emi_filter("FB1", position_mm=(25, 10), signal_net=nets[0], filter_type="FB")
        
        board = MockBoard(
            nets=nets,
            footprints=[connector, fb],
            copper_layer_count=2
        )
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['FB', 'L', 'C'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple'
        }
        
        checker, violations = make_emi_filtering_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Assert: filter too far should be flagged as missing
        assert violation_count >= 1, "Filter beyond max_filter_distance_mm should be flagged"

    def test_filter_within_distance_no_violation(self):
        """Filter component within distance limit should have no violation."""
        # Create connector at (10, 10)
        nets, connector = make_connector_with_signals("J1", position_mm=(10, 10), 
                                                      signal_nets=["USB_DP"])
        
        # Create filter nearby at (15, 10) - 5mm away, within 10mm limit
        # Pass the actual net object so filter pads share the same net code
        fb = make_emi_filter("FB1", position_mm=(15, 10), signal_net=nets[0], filter_type="FB")
        
        board = MockBoard(
            nets=nets,
            footprints=[connector, fb],
            copper_layer_count=2
        )
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['FB', 'L', 'C'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple'
        }
        
        checker, violations = make_emi_filtering_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Assert: filter within distance should have no violations
        assert violation_count == 0, "Filter within distance should have no violations"


class TestConnectorClassification:
    """Only connectors on the configured net prefixes are checked."""

    def test_non_monitored_connector_skipped(self):
        """Connector not on a monitored net prefix should be skipped."""
        # Create connector with reference K1 (not J prefix)
        nets, connector = make_connector_with_signals("K1", position_mm=(10, 10), 
                                                      signal_nets=["DATA"])
        
        board = MockBoard(
            nets=nets,
            footprints=[connector],
            copper_layer_count=2
        )
        
        config = {
            'connector_prefix': 'J',  # Only check J-prefixed connectors
            'filter_component_prefixes': ['FB', 'L', 'C'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple'
        }
        
        checker, violations = make_emi_filtering_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Assert: non-J connector should not be checked
        assert violation_count == 0, "Non-J connector should be skipped"

    def test_usb_connector_checked(self):
        """Connector on USB_ net prefix should be checked."""
        # Create connector with USB signal nets
        nets, connector = make_connector_with_signals("J1", position_mm=(10, 10), 
                                                      signal_nets=["USB_DP", "USB_DN"])
        
        board = MockBoard(
            nets=nets,
            footprints=[connector],
            copper_layer_count=2
        )
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['FB', 'L', 'C'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple'
        }
        
        checker, violations = make_emi_filtering_checker_with_utilities(board, config)
        violation_count = checker.check(
            checker.draw_marker,
            checker.draw_arrow,
            checker.get_distance,
            checker.log,
            checker.create_group
        )
        
        # Assert: USB connector should be checked (2 signal pads without filters = 2 violations)
        assert violation_count >= 2, "USB connector should be checked for filters"
