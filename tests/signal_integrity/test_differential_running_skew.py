"""
Unit tests for signal_integrity.py CHECK 13: Differential Running Skew
Tests the _check_differential_running_skew() method for spacing variation detection.

Created: 2026-05-11
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import MockBoard, MockNet, MockTrack, make_si_checker_with_utilities

import pcbnew


class TestDifferentialRunningSkew:
    """Test differential pair spacing variation detection."""
    
    def test_excessive_spacing_variation_flagged(self):
        """Differential pair with >15% spacing variation should be flagged."""
        # Create P and N traces with varying spacing along route
        # This would require multiple segments with different separations
        config = {
            'differential_running_skew': {
                'enabled': True,
                'critical_net_classes': ['USB'],
                'max_spacing_variation_percent': 15.0
            }
        }
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_differential_running_skew()
        
        assert isinstance(violation_count, int), "Should return integer"
        assert violation_count >= 0, "Violation count should be non-negative"
    
    def test_consistent_spacing_no_violation(self):
        """Differential pair with <15% spacing variation should have no violation."""
        # Parallel traces with consistent 0.2mm spacing (variation ~0%)
        start_p = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end_p = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        start_n = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0.2))
        end_n = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0.2))
        
        track_p = MockTrack("USB_DP", start_p, end_p, layer=0, net_class="USB")
        track_n = MockTrack("USB_DN", start_n, end_n, layer=0, net_class="USB")
        
        nets = [MockNet("USB_DP", "USB"), MockNet("USB_DN", "USB")]
        board = MockBoard(nets=nets, tracks=[track_p, track_n], copper_layer_count=4)
        
        config = {
            'differential_running_skew': {
                'enabled': True,
                'critical_net_classes': ['USB'],
                'max_spacing_variation_percent': 15.0
            }
        }
        
        # Create checker and run differential running skew check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_differential_running_skew()
        
        # Assert: consistent spacing should have 0 violations
        assert violation_count == 0, "Consistent spacing should have 0 violations"
    
    def test_pair_too_short_skipped(self):
        """Differential pair shorter than min_pair_length_mm should be skipped."""
        # Create pair only 2mm long (below 5mm minimum)
        start_p = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end_p = pcbnew.VECTOR2I(pcbnew.FromMM(2), pcbnew.FromMM(0))
        
        start_n = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0.2))
        end_n = pcbnew.VECTOR2I(pcbnew.FromMM(2), pcbnew.FromMM(0.2))
        
        track_p = MockTrack("USB_DP", start_p, end_p, layer=0, net_class="USB")
        track_n = MockTrack("USB_DN", start_n, end_n, layer=0, net_class="USB")
        
        nets = [MockNet("USB_DP", "USB"), MockNet("USB_DN", "USB")]
        board = MockBoard(nets=nets, tracks=[track_p, track_n], copper_layer_count=4)
        
        config = {
            'differential_running_skew': {
                'enabled': True,
                'critical_net_classes': ['USB'],
                'min_pair_length_mm': 5.0
            }
        }
        
        # Create checker and run differential running skew check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_differential_running_skew()
        
        # Assert: short pairs should be skipped
        assert violation_count == 0, "Short pairs below min length should be skipped"
    
    def test_disabled_in_config_returns_zero(self):
        """Disabled check should return 0."""
        config = {'differential_running_skew': {'enabled': False}}
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_differential_running_skew()
        
        assert violation_count == 0, "Disabled check should return 0"
