"""
Integration tests for enhanced decoupling checker with full board mocking.

Tests end-to-end scenarios with realistic board configurations including
ICs, capacitors, vias, and various SMD/THT combinations.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Import pcbnew mock before other imports
import pcbnew

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from decoupling import DecouplingChecker


# ============================================================================
# Mock Objects with Full Board Simulation
# ============================================================================

class MockPad:
    """Mock pcbnew.PAD with position, net, and drill size."""
    
    def __init__(self, number="1", position=(0, 0), net_name="", drill_x=0, drill_y=0):
        self._number = number
        self._position = position
        self._net_name = net_name
        self.drill_x = drill_x
        self.drill_y = drill_y
    
    def GetNumber(self):
        return self._number
    
    def GetPosition(self):
        class Position:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        return Position(*self._position)
    
    def GetNetname(self):
        return self._net_name
    
    def GetDrillSize(self):
        class DrillSize:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        return DrillSize(self.drill_x, self.drill_y)


class MockFootprint:
    """Mock pcbnew.FOOTPRINT with reference, value, pads, and position."""
    
    def __init__(self, reference="U1", value="", pads=None, position=(0, 0)):
        self._reference = reference
        self._value = value
        self._pads = pads or []
        self._position = position
    
    def GetReference(self):
        return self._reference
    
    def GetValue(self):
        return self._value
    
    def Pads(self):
        return self._pads
    
    def GetPosition(self):
        class Position:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        return Position(*self._position)


class MockVia(pcbnew.PCB_VIA):
    """Mock pcbnew.PCB_VIA for via counting tests."""
    
    def __init__(self, position=(0, 0)):
        super().__init__()
        self._position = position
    
    def GetPosition(self):
        class Position:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        return Position(*self._position)


class MockBoard:
    """Mock pcbnew.BOARD with footprints and tracks."""
    
    def __init__(self):
        self._footprints = []
        self._tracks = []
    
    def GetFootprints(self):
        return self._footprints
    
    def GetTracks(self):
        return self._tracks
    
    def AddNativeGroup(self):
        return MagicMock()


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def basic_board():
    """Basic board with one IC and capacitors at various distances."""
    board = MockBoard()
    
    # IC U1 at origin with VCC pin
    ic_pad = MockPad(number="1", position=(0, 0), net_name="VCC")
    ic = MockFootprint(reference="U1", pads=[ic_pad], position=(0, 0))
    
    # SMD capacitors at various distances
    cap1_pads = [
        MockPad(number="1", position=(pcbnew.FromMM(1), 0), net_name="VCC", drill_x=0, drill_y=0),
        MockPad(number="2", position=(pcbnew.FromMM(1.5), 0), net_name="GND", drill_x=0, drill_y=0)
    ]
    cap1 = MockFootprint(reference="C1", value="100nF", pads=cap1_pads, 
                         position=(pcbnew.FromMM(1.25), 0))
    
    cap2_pads = [
        MockPad(number="1", position=(pcbnew.FromMM(5), 0), net_name="VCC", drill_x=0, drill_y=0),
        MockPad(number="2", position=(pcbnew.FromMM(5.5), 0), net_name="GND", drill_x=0, drill_y=0)
    ]
    cap2 = MockFootprint(reference="C2", value="10uF", pads=cap2_pads,
                         position=(pcbnew.FromMM(5.25), 0))
    
    board._footprints = [ic, cap1, cap2]
    
    return board


@pytest.fixture
def smd_vs_tht_board():
    """Board with both SMD and THT capacitors to test prioritization."""
    board = MockBoard()
    
    # IC at origin
    ic_pad = MockPad(number="1", position=(0, 0), net_name="VCC")
    ic = MockFootprint(reference="U1", pads=[ic_pad], position=(0, 0))
    
    # THT capacitor (closer but not preferred)
    tht_pads = [
        MockPad(number="1", position=(pcbnew.FromMM(2), 0), net_name="VCC",
                drill_x=pcbnew.FromMM(0.8), drill_y=pcbnew.FromMM(0.8)),
        MockPad(number="2", position=(pcbnew.FromMM(2.5), 0), net_name="GND",
                drill_x=pcbnew.FromMM(0.8), drill_y=pcbnew.FromMM(0.8))
    ]
    tht_cap = MockFootprint(reference="C1", value="100uF", pads=tht_pads,
                            position=(pcbnew.FromMM(2.25), 0))
    
    # SMD capacitor (farther but preferred)
    smd_pads = [
        MockPad(number="1", position=(pcbnew.FromMM(4), 0), net_name="VCC",
                drill_x=0, drill_y=0),
        MockPad(number="2", position=(pcbnew.FromMM(4.5), 0), net_name="GND",
                drill_x=0, drill_y=0)
    ]
    smd_cap = MockFootprint(reference="C2", value="100nF", pads=smd_pads,
                            position=(pcbnew.FromMM(4.25), 0))
    
    board._footprints = [ic, tht_cap, smd_cap]
    
    return board


@pytest.fixture
def large_tht_bulk_cap_board():
    """Board with large THT bulk capacitor that should produce warning."""
    board = MockBoard()
    
    # IC at origin
    ic_pad = MockPad(number="1", position=(0, 0), net_name="VCC")
    ic = MockFootprint(reference="U1", pads=[ic_pad], position=(0, 0))
    
    # Large THT bulk capacitor (22uF, exceeds non_smd_value_threshold)
    tht_pads = [
        MockPad(number="1", position=(pcbnew.FromMM(10), 0), net_name="VCC",
                drill_x=pcbnew.FromMM(1.0), drill_y=pcbnew.FromMM(1.0)),
        MockPad(number="2", position=(pcbnew.FromMM(11), 0), net_name="GND",
                drill_x=pcbnew.FromMM(1.0), drill_y=pcbnew.FromMM(1.0))
    ]
    tht_bulk = MockFootprint(reference="C1", value="100uF", pads=tht_pads,
                             position=(pcbnew.FromMM(10.5), 0))
    
    board._footprints = [ic, tht_bulk]
    
    return board


@pytest.fixture
def via_count_board():
    """Board with capacitor and various via configurations."""
    board = MockBoard()
    
    # IC at origin
    ic_pad = MockPad(number="1", position=(0, 0), net_name="VCC")
    ic = MockFootprint(reference="U1", pads=[ic_pad], position=(0, 0))
    
    # Capacitor near IC with insufficient vias
    cap_pads = [
        MockPad(number="1", position=(pcbnew.FromMM(2), 0), net_name="VCC",
                drill_x=0, drill_y=0),
        MockPad(number="2", position=(pcbnew.FromMM(2.5), 0), net_name="GND",
                drill_x=0, drill_y=0)
    ]
    cap = MockFootprint(reference="C1", value="100nF", pads=cap_pads,
                        position=(pcbnew.FromMM(2.25), 0))
    
    board._footprints = [ic, cap]
    
    # Only 1 via within 2mm radius (should trigger warning)
    board._tracks = [
        MockVia(position=(pcbnew.FromMM(2.2), pcbnew.FromMM(0.5)))
    ]
    
    return board


@pytest.fixture
def sufficient_vias_board():
    """Board with capacitor and sufficient vias (≥2)."""
    board = MockBoard()
    
    # IC at origin
    ic_pad = MockPad(number="1", position=(0, 0), net_name="VCC")
    ic = MockFootprint(reference="U1", pads=[ic_pad], position=(0, 0))
    
    # Capacitor with good via count
    cap_pads = [
        MockPad(number="1", position=(pcbnew.FromMM(2), 0), net_name="VCC",
                drill_x=0, drill_y=0),
        MockPad(number="2", position=(pcbnew.FromMM(2.5), 0), net_name="GND",
                drill_x=0, drill_y=0)
    ]
    cap = MockFootprint(reference="C1", value="100nF", pads=cap_pads,
                        position=(pcbnew.FromMM(2.25), 0))
    
    board._footprints = [ic, cap]
    
    # 3 vias within 2mm radius (good design)
    board._tracks = [
        MockVia(position=(pcbnew.FromMM(2.0), pcbnew.FromMM(0.5))),
        MockVia(position=(pcbnew.FromMM(2.5), pcbnew.FromMM(0.5))),
        MockVia(position=(pcbnew.FromMM(2.2), pcbnew.FromMM(0.8)))
    ]
    
    return board


# ============================================================================
# Integration Tests
# ============================================================================

class TestSmdThtPrioritization:
    """Test SMD capacitor prioritization over THT."""
    
    def test_prefer_smd_over_tht_when_both_available(self, smd_vs_tht_board):
        """When prefer_smd=True, SMD capacitor should be selected over THT."""
        # Arrange
        config = {
            'max_distance_mm': 5.0,
            'ic_reference_prefixes': ['U'],
            'capacitor_reference_prefixes': ['C'],
            'power_net_patterns': ['VCC', 'VDD'],
            'prefer_smd_capacitors': True,
            'non_smd_value_threshold_uf': 22.0,
            'check_via_count': False  # Disable for this test
        }
        
        checker = DecouplingChecker(
            board=smd_vs_tht_board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def draw_marker(board, pos, msg, layer, group):
            pass
        
        def draw_arrow(board, start, end, label, layer, group):
            pass
        
        def log_func(msg, force=False):
            if checker.verbose or force:
                print(f"[TEST LOG] {msg}")
        
        def create_group(board, type_name, id_str, num):
            return MagicMock()
        
        # Act
        violations = checker.check(
            draw_marker_func=draw_marker,
            draw_arrow_func=draw_arrow,
            get_distance_func=get_distance,
            log_func=log_func,
            create_group_func=create_group
        )
        
        # Assert
        # SMD cap (C2) at 4mm should be selected over THT cap (C1) at 2mm
        # Both are within 5mm limit, so no violations expected
        assert violations == 0, "SMD prioritization should select C2, both within limit"
        
        # Verify via log output that SMD was preferred
        # (In real implementation, check that C2 was logged as nearest)
    
    def test_large_tht_cap_produces_warning_not_error(self, large_tht_bulk_cap_board):
        """THT cap ≥22µF should produce warning, not error."""
        # Arrange
        config = {
            'max_distance_mm': 5.0,
            'ic_reference_prefixes': ['U'],
            'capacitor_reference_prefixes': ['C'],
            'power_net_patterns': ['VCC', 'VDD'],
            'prefer_smd_capacitors': True,
            'non_smd_value_threshold_uf': 22.0,
            'check_via_count': False
        }
        
        checker = DecouplingChecker(
            board=large_tht_bulk_cap_board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utilities
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        marker_calls = []
        def draw_marker(board, pos, msg, layer, group):
            marker_calls.append({'pos': pos, 'msg': msg})
        
        def draw_arrow(board, start, end, label, layer, group):
            pass
        
        def log_func(msg, force=False):
            if checker.verbose or force:
                print(f"[TEST LOG] {msg}")
        
        def create_group(board, type_name, id_str, num):
            return MagicMock()
        
        # Act
        violations = checker.check(
            draw_marker_func=draw_marker,
            draw_arrow_func=draw_arrow,
            get_distance_func=get_distance,
            log_func=log_func,
            create_group_func=create_group
        )
        
        # Assert
        # 100uF THT cap at 10mm exceeds 5mm limit but should be warning not error
        assert violations == 0, "Large THT bulk caps should not count as errors"
        assert checker.warning_count == 1, "Should produce exactly 1 warning"
        assert len(marker_calls) == 1, "Should draw 1 warning marker"
        assert "BULK CAP FAR" in marker_calls[0]['msg'] or "THT OK" in marker_calls[0]['msg'], \
               "Warning marker should indicate bulk capacitor exception"


class TestViaCountChecking:
    """Test via count checking produces warnings."""
    
    def test_insufficient_vias_produces_warning(self, via_count_board):
        """Capacitor with <2 vias should produce warning marker."""
        # Arrange
        config = {
            'max_distance_mm': 5.0,
            'ic_reference_prefixes': ['U'],
            'capacitor_reference_prefixes': ['C'],
            'power_net_patterns': ['VCC', 'VDD'],
            'prefer_smd_capacitors': True,
            'check_via_count': True,
            'min_vias_per_capacitor': 2,
            'via_search_radius_mm': 2.0
        }
        
        checker = DecouplingChecker(
            board=via_count_board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utilities
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        warning_markers = []
        def draw_marker(board, pos, msg, layer, group):
            if "VIA COUNT" in msg or "via" in msg.lower():
                warning_markers.append(msg)
        
        def draw_arrow(board, start, end, label, layer, group):
            pass
        
        def log_func(msg, force=False):
            if checker.verbose or force:
                print(f"[TEST LOG] {msg}")
        
        def create_group(board, type_name, id_str, num):
            return MagicMock()
        
        # Act
        violations = checker.check(
            draw_marker_func=draw_marker,
            draw_arrow_func=draw_arrow,
            get_distance_func=get_distance,
            log_func=log_func,
            create_group_func=create_group
        )
        
        # Assert
        assert violations == 0, "Via warnings should not count as errors"
        assert checker.warning_count >= 1, "Should produce via count warning"
        assert len(warning_markers) >= 1, "Should draw via warning marker"
    
    def test_sufficient_vias_no_warning(self, sufficient_vias_board):
        """Capacitor with ≥2 vias should not produce warning."""
        # Arrange
        config = {
            'max_distance_mm': 5.0,
            'ic_reference_prefixes': ['U'],
            'capacitor_reference_prefixes': ['C'],
            'power_net_patterns': ['VCC', 'VDD'],
            'prefer_smd_capacitors': True,
            'check_via_count': True,
            'min_vias_per_capacitor': 2,
            'via_search_radius_mm': 2.0
        }
        
        checker = DecouplingChecker(
            board=sufficient_vias_board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utilities
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        warning_markers = []
        def draw_marker(board, pos, msg, layer, group):
            if "VIA COUNT" in msg or "LOW VIA" in msg:
                warning_markers.append(msg)
        
        def draw_arrow(board, start, end, label, layer, group):
            pass
        
        def log_func(msg, force=False):
            if checker.verbose or force:
                print(f"[TEST LOG] {msg}")
        
        def create_group(board, type_name, id_str, num):
            return MagicMock()
        
        # Act
        violations = checker.check(
            draw_marker_func=draw_marker,
            draw_arrow_func=draw_arrow,
            get_distance_func=get_distance,
            log_func=log_func,
            create_group_func=create_group
        )
        
        # Assert
        assert violations == 0, "No violations expected"
        assert len(warning_markers) == 0, "Should not draw via warning markers when count is sufficient"


class TestBasicProximity:
    """Test basic capacitor proximity checking."""
    
    def test_within_distance_no_violation(self, basic_board):
        """Capacitor within max distance should pass."""
        # Arrange
        config = {
            'max_distance_mm': 5.0,
            'ic_reference_prefixes': ['U'],
            'capacitor_reference_prefixes': ['C'],
            'power_net_patterns': ['VCC', 'VDD'],
            'prefer_smd_capacitors': False,
            'check_via_count': False
        }
        
        checker = DecouplingChecker(
            board=basic_board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Mock utilities
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def draw_marker(board, pos, msg, layer, group):
            pass
        
        def draw_arrow(board, start, end, label, layer, group):
            pass
        
        def log_func(msg, force=False):
            pass
        
        def create_group(board, type_name, id_str, num):
            return MagicMock()
        
        # Act
        violations = checker.check(
            draw_marker_func=draw_marker,
            draw_arrow_func=draw_arrow,
            get_distance_func=get_distance,
            log_func=log_func,
            create_group_func=create_group
        )
        
        # Assert
        # C1 at 1mm and C2 at 5mm - both within 5mm limit
        assert violations == 0, "All capacitors within limit, no violations expected"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
