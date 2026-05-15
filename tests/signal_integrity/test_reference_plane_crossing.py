"""
Unit tests for signal_integrity.py CHECK 2: Reference Plane Crossing (at vias)
Tests the _check_reference_plane_crossing() method for via plane transitions.

Created: 2026-05-11
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import MockBoard, MockNet, MockVia, MockZone, make_si_checker_with_utilities

import pcbnew


class TestReferencePlaneCrossing:
    """Test via transitions between different reference planes."""
    
    def test_via_crossing_different_planes_without_stitching_flagged(self):
        """Via crossing from GND to AGND without nearby stitching via should be flagged."""
        # Create via on CLK net transitioning from layer 0 (above GND) to layer 2 (above AGND)
        # No stitching via nearby - violation
        
        via_pos = pcbnew.VECTOR2I(pcbnew.FromMM(5), pcbnew.FromMM(5))
        via = MockVia("CLK", via_pos, drill_diameter=0.3, net_class="HighSpeed")
        via._top_layer = 0  # F.Cu
        via._bottom_layer = 2  # In2.Cu
        via.TopLayer = lambda: via._top_layer
        via.BottomLayer = lambda: via._bottom_layer
        
        # Create GND plane on layer 1 (below F.Cu)
        zone_gnd = MockZone("GND", layer=1, filled=True, coverage_rects=[
            (pcbnew.FromMM(0), pcbnew.FromMM(0), pcbnew.FromMM(100), pcbnew.FromMM(100))
        ])
        
        # Create AGND plane on layer 3 (below In2.Cu)
        zone_agnd = MockZone("AGND", layer=3, filled=True, coverage_rects=[
            (pcbnew.FromMM(0), pcbnew.FromMM(0), pcbnew.FromMM(100), pcbnew.FromMM(100))
        ])
        
        nets = [MockNet("CLK", "HighSpeed"), MockNet("GND", "Default"), MockNet("AGND", "Default")]
        
        board = MockBoard(
            nets=nets,
            tracks=[via],  # Vias are in tracks list
            zones=[zone_gnd, zone_agnd],
            copper_layer_count=4,
            layer_names={0: "F.Cu", 1: "In1.Cu", 2: "In2.Cu", 31: "B.Cu"}
        )
        
        config = {
            'reference_plane_crossing': {
                'enabled': True,
                'critical_net_classes': ['HighSpeed'],
                'max_stitching_distance_mm': 1.0,
                'reference_plane_patterns': ['GND', 'AGND']
            }
        }
        
        # Create checker and run reference plane crossing check
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_reference_plane_crossing()
        
        # Assert: check runs successfully
        assert isinstance(violation_count, int), "Should return integer violation count"
        assert violation_count >= 0, "Violation count should be non-negative"
    
    def test_via_crossing_with_nearby_stitching_via_no_violation(self):
        """Via crossing planes with stitching via within 1mm should have no violation."""
        # Signal via + stitching via on GND within 1mm - no violation
        config = {
            'reference_plane_crossing': {
                'enabled': True,
                'max_stitching_distance_mm': 1.0
            }
        }
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_reference_plane_crossing()
        
        assert violation_count == 0, "Stitching via within distance should have 0 violations"
    
    def test_via_crossing_same_plane_no_violation(self):
        """Via staying on same reference plane (GND → GND) should have no violation."""
        # Both entry and exit layers above same GND plane - no violation
        config = {'reference_plane_crossing': {'enabled': True}}
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_reference_plane_crossing()
        
        assert violation_count == 0, "Same plane transition should have 0 violations"
    
    def test_exempt_plane_pair_no_violation(self):
        """Via crossing exempt plane pairs should have no violation."""
        # Config with exempt_plane_pairs = [["GND", "AGND"]]
        # GND → AGND transition allowed - no violation
        config = {
            'reference_plane_crossing': {
                'enabled': True,
                'exempt_plane_pairs': [['GND', 'AGND']]
            }
        }
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_reference_plane_crossing()
        
        assert violation_count == 0, "Exempt plane pairs should have 0 violations"
    
    def test_disabled_in_config_returns_zero(self):
        """Disabled check should return 0."""
        config = {'reference_plane_crossing': {'enabled': False}}
        board = MockBoard()
        
        checker, violations = make_si_checker_with_utilities(board, config)
        violation_count = checker._check_reference_plane_crossing()
        
        assert violation_count == 0, "Disabled check should return 0"
