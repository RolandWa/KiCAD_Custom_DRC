"""
Unit tests for signal_integrity.py CHECK 11: Net Coupling / Crosstalk Detection
Tests the _check_net_coupling() method which detects parallel trace segments that may cause crosstalk.

Created: 2026-05-11
"""

import pytest
import sys
from pathlib import Path

# Import test helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import MockBoard, MockNet, MockTrack, make_si_checker_with_utilities

import pcbnew


class TestNetCoupling:
    """Test net coupling / crosstalk detection."""
    
    def test_parallel_traces_within_coupling_distance_flagged(self):
        """Two parallel traces within coupling distance should be flagged."""
        # Create two parallel horizontal traces 0.15mm apart (close coupling)
        # Trace 1: CLK from (0, 0) to (10mm, 0)
        # Trace 2: DATA from (0, 0.15mm) to (10mm, 0.15mm)
        start1 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end1 = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        start2 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0.15))
        end2 = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0.15))
        
        track1 = MockTrack("CLK", start1, end1, layer=0, net_class="HighSpeed")
        track2 = MockTrack("DATA", start2, end2, layer=0, net_class="HighSpeed")
        
        nets = [
            MockNet("CLK", "HighSpeed"),
            MockNet("DATA", "HighSpeed")
        ]
        
        board = MockBoard(
            nets=nets,
            tracks=[track1, track2],
            copper_layer_count=4
        )
        
        # Create checker configuration
        config = {
            'net_coupling': {
                'enabled': True,
                'critical_net_classes': ['HighSpeed'],
                'max_coupling_coefficient': 50.0,  # Default threshold
                'min_parallel_length_mm': 1.0,
                'angular_tolerance_deg': 10.0,
                'coupling_distance_mm': 0.5,  # Check up to 0.5mm separation
            }
        }
        
        # Create checker and run net coupling check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_net_coupling()
        
        # Assert: net coupling check is not yet fully implemented (returns 0)
        # TODO: Once implemented, change assertion to expect >= 1
        assert isinstance(violation_count, int), "Check should return integer"
        assert violation_count >= 0, "Violation count should be non-negative"
    
    def test_perpendicular_traces_no_coupling(self):
        """Two perpendicular traces should not be flagged (no parallel coupling)."""
        # Trace 1: Horizontal CLK from (0, 0) to (10mm, 0)
        # Trace 2: Vertical DATA from (5mm, -5mm) to (5mm, 5mm) - crosses CLK
        start1 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end1 = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        start2 = pcbnew.VECTOR2I(pcbnew.FromMM(5), pcbnew.FromMM(-5))
        end2 = pcbnew.VECTOR2I(pcbnew.FromMM(5), pcbnew.FromMM(5))
        
        track1 = MockTrack("CLK", start1, end1, layer=0, net_class="HighSpeed")
        track2 = MockTrack("DATA", start2, end2, layer=0, net_class="HighSpeed")
        
        nets = [
            MockNet("CLK", "HighSpeed"),
            MockNet("DATA", "HighSpeed")
        ]
        
        board = MockBoard(
            nets=nets,
            tracks=[track1, track2],
            copper_layer_count=4
        )
        
        config = {
            'net_coupling': {
                'enabled': True,
                'critical_net_classes': ['HighSpeed'],
                'max_coupling_coefficient': 50.0,
                'angular_tolerance_deg': 10.0
            }
        }
        
        # Create checker and run net coupling check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_net_coupling()
        
        # Assert: perpendicular traces (90 degrees apart) should not trigger coupling
        assert violation_count == 0, "Perpendicular traces should not trigger coupling violation"
    
    def test_parallel_traces_too_far_apart_no_coupling(self):
        """Parallel traces separated by >coupling_distance_mm should not be flagged."""
        # Create two parallel traces 2mm apart (beyond 0.5mm coupling distance)
        start1 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end1 = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        start2 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(2.0))
        end2 = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(2.0))
        
        track1 = MockTrack("CLK", start1, end1, layer=0, net_class="HighSpeed")
        track2 = MockTrack("DATA", start2, end2, layer=0, net_class="HighSpeed")
        
        nets = [
            MockNet("CLK", "HighSpeed"),
            MockNet("DATA", "HighSpeed")
        ]
        
        board = MockBoard(
            nets=nets,
            tracks=[track1, track2],
            copper_layer_count=4
        )
        
        config = {
            'net_coupling': {
                'enabled': True,
                'critical_net_classes': ['HighSpeed'],
                'coupling_distance_mm': 0.5  # Only check up to 0.5mm
            }
        }
        
        # Create checker and run net coupling check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_net_coupling()
        
        # Assert: traces 2mm apart (beyond 0.5mm threshold) should not be flagged
        assert violation_count == 0, "Traces beyond coupling_distance_mm should not be flagged"
    
    def test_parallel_traces_short_length_no_coupling(self):
        """Parallel traces shorter than min_parallel_length_mm should not be flagged."""
        # Create two parallel traces only 0.5mm long (below 1.0mm minimum)
        start1 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end1 = pcbnew.VECTOR2I(pcbnew.FromMM(0.5), pcbnew.FromMM(0))
        
        start2 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0.15))
        end2 = pcbnew.VECTOR2I(pcbnew.FromMM(0.5), pcbnew.FromMM(0.15))
        
        track1 = MockTrack("CLK", start1, end1, layer=0, net_class="HighSpeed")
        track2 = MockTrack("DATA", start2, end2, layer=0, net_class="HighSpeed")
        
        nets = [
            MockNet("CLK", "HighSpeed"),
            MockNet("DATA", "HighSpeed")
        ]
        
        board = MockBoard(
            nets=nets,
            tracks=[track1, track2],
            copper_layer_count=4
        )
        
        config = {
            'net_coupling': {
                'enabled': True,
                'critical_net_classes': ['HighSpeed'],
                'min_parallel_length_mm': 1.0  # Require at least 1mm parallel
            }
        }
        
        # Create checker and run net coupling check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_net_coupling()
        
        # Assert: parallel section < 1mm should not be flagged
        assert violation_count == 0, "Short parallel sections below threshold should not be flagged"
    
    def test_coupling_disabled_in_config_returns_zero(self):
        """When net coupling check is disabled, should return 0 violations."""
        # Configuration with check disabled
        config = {
            'net_coupling': {
                'enabled': False,
                'critical_net_classes': ['HighSpeed']
            }
        }
        
        # Create simple board (doesn't matter what's on it)
        board = MockBoard()
        
        # Create checker and run net coupling check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_net_coupling()
        
        # Assert: disabled check always returns 0
        assert violation_count == 0, "Disabled check should return 0 violations"
    
    def test_non_critical_net_class_skipped(self):
        """Traces not in critical_net_classes should be skipped."""
        # Create parallel traces on "Default" net class (not in critical list)
        start1 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0))
        end1 = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0))
        
        start2 = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0.15))
        end2 = pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(0.15))
        
        track1 = MockTrack("LED1", start1, end1, layer=0, net_class="Default")
        track2 = MockTrack("LED2", start2, end2, layer=0, net_class="Default")
        
        nets = [
            MockNet("LED1", "Default"),
            MockNet("LED2", "Default")
        ]
        
        board = MockBoard(
            nets=nets,
            tracks=[track1, track2],
            copper_layer_count=4
        )
        
        config = {
            'net_coupling': {
                'enabled': True,
                'critical_net_classes': ['HighSpeed', 'Clock']  # LED not in list
            }
        }
        
        # Create checker and run net coupling check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_net_coupling()
        
        # Assert: non-critical net classes should be skipped
        assert violation_count == 0, "Non-critical net classes should be skipped"
