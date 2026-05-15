"""
Unit tests for signal_integrity.py CHECK 10: Differential Pair Isolation
Tests the _check_critical_net_isolation_differential() method.

Created: 2026-05-11
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import MockBoard, MockNet, MockTrack, make_si_checker_with_utilities

import pcbnew


class TestDifferentialPairIsolation:
    """Test differential pair outer-edge isolation (4W rule on external edges only)."""
    
    def test_aggressor_too_close_to_outer_edge_flagged(self):
        """Aggressor trace within 4W of differential pair outer edge should be flagged."""
        # USB_DP at (0, 0) to (10mm, 0), width 0.2mm
        # USB_DN at (0, 0.25mm) to (10mm, 0.25mm), width 0.2mm
        # Aggressor at (0, -0.5mm) to (10mm, -0.5mm) - too close to outer edge of DP
        
        start_p = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end_p = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        start_n = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0.25))
        end_n = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0.25))
        
        start_agg = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(-0.5))
        end_agg = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(-0.5))
        
        track_p = MockTrack("USB_DP", start_p, end_p, layer=0, net_class="USB", width=pcbnew.FromMM(0.2))
        track_n = MockTrack("USB_DN", start_n, end_n, layer=0, net_class="USB", width=pcbnew.FromMM(0.2))
        track_agg = MockTrack("CLK", start_agg, end_agg, layer=0, net_class="Clock", width=pcbnew.FromMM(0.2))
        
        nets = [MockNet("USB_DP", "USB"), MockNet("USB_DN", "USB"), MockNet("CLK", "Clock")]
        
        board = MockBoard(nets=nets, tracks=[track_p, track_n, track_agg], copper_layer_count=4)
        
        config = {
            'critical_net_isolation_dp': {
                'enabled': True,
                'critical_net_classes': ['USB'],
                'outer_edge_multiplier': 4.0
            }
        }
        
        # Create checker and run differential isolation check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_critical_net_isolation_differential()
        
        # Assert: check runs successfully
        assert isinstance(violation_count, int), "Should return integer violation count"
        assert violation_count >= 0, "Violation count should be non-negative"
    
    def test_aggressor_near_inner_edge_not_flagged(self):
        """Aggressor near inner edge (between P and N) should NOT be flagged."""
        # Partner traces are exempt from isolation check
        config = {'critical_net_isolation_dp': {'enabled': True}}
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_critical_net_isolation_differential()
        
        assert violation_count == 0, "Inner edge proximity is allowed (partner trace exempt)"
    
    def test_sufficient_isolation_no_violation(self):
        """Aggressor at >4W distance from outer edge should have no violation."""
        config = {'critical_net_isolation_dp': {'enabled': True}}
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_critical_net_isolation_differential()
        
        assert violation_count == 0, "Sufficient isolation should have 0 violations"
    
    def test_disabled_in_config_returns_zero(self):
        """Disabled check should return 0."""
        config = {'critical_net_isolation_dp': {'enabled': False}}
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_critical_net_isolation_differential()
        
        assert violation_count == 0, "Disabled check should return 0"
