"""
Unit tests for enhanced decoupling checker features.

Tests SMD/THT detection, via counting, value parsing, and warning/error behavior.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Import pcbnew mock before importing decoupling
import pcbnew

from decoupling import DecouplingChecker


class MockPad:
    """Mock pcbnew.PAD with drill size."""
    
    def __init__(self, drill_x=0, drill_y=0, position=(0, 0), net_name=""):
        self.drill_x = drill_x
        self.drill_y = drill_y
        self._position = position
        self._net_name = net_name
    
    def GetDrillSize(self):
        """Return mock drill size."""
        class DrillSize:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        return DrillSize(self.drill_x, self.drill_y)
    
    def GetPosition(self):
        """Return mock position."""
        class Position:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        return Position(*self._position)
    
    def GetNetname(self):
        """Return mock net name."""
        return self._net_name


class MockFootprint:
    """Mock pcbnew.FOOTPRINT with pads and value."""
    
    def __init__(self, reference="C1", value="100nF", pads=None, position=(0, 0)):
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
    """Mock pcbnew.PCB_VIA."""
    
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
    """Mock pcbnew.BOARD."""
    
    def __init__(self):
        self._footprints = []
        self._tracks = []
    
    def GetFootprints(self):
        return self._footprints
    
    def GetTracks(self):
        return self._tracks
    
    def AddNativeGroup(self):
        return MagicMock()


# -----------------------------------------------------------------------------
# Test: _is_smd_footprint()
# -----------------------------------------------------------------------------

class TestIsSmdFootprint:
    """Test SMD vs THT footprint detection."""
    
    def test_smd_footprint_no_drill_holes(self):
        """SMD footprint has no drill holes in any pad."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Create SMD footprint (no drill holes)
        smd_pads = [
            MockPad(drill_x=0, drill_y=0),  # No drill
            MockPad(drill_x=0, drill_y=0)   # No drill
        ]
        smd_footprint = MockFootprint(pads=smd_pads)
        
        # Act
        result = checker._is_smd_footprint(smd_footprint)
        
        # Assert
        assert result is True, "Footprint with no drill holes should be detected as SMD"
    
    def test_tht_footprint_has_drill_holes(self):
        """THT footprint has drill holes in pads."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Create THT footprint (drill holes present)
        tht_pads = [
            MockPad(drill_x=1000000, drill_y=1000000),  # 1mm drill
            MockPad(drill_x=1000000, drill_y=1000000)   # 1mm drill
        ]
        tht_footprint = MockFootprint(pads=tht_pads)
        
        # Act
        result = checker._is_smd_footprint(tht_footprint)
        
        # Assert
        assert result is False, "Footprint with drill holes should be detected as THT"
    
    def test_mixed_smd_one_tht_pad(self):
        """Footprint with at least one THT pad should be classified as THT."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Mixed: one SMD, one THT
        mixed_pads = [
            MockPad(drill_x=0, drill_y=0),             # SMD
            MockPad(drill_x=1000000, drill_y=1000000)  # THT
        ]
        mixed_footprint = MockFootprint(pads=mixed_pads)
        
        # Act
        result = checker._is_smd_footprint(mixed_footprint)
        
        # Assert
        assert result is False, "Footprint with any THT pad should be classified as THT"


# -----------------------------------------------------------------------------
# Test: _get_capacitor_value_uf()
# -----------------------------------------------------------------------------

class TestGetCapacitorValueUf:
    """Test capacitor value parsing from footprint."""
    
    def test_parse_nanofarads(self):
        """Parse nanofarad values (100nF, 10nF)."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Act
        footprint_100nf = MockFootprint(value="100nF")
        result_100nf = checker._get_capacitor_value_uf(footprint_100nf)
        
        footprint_10nf = MockFootprint(value="10nF")
        result_10nf = checker._get_capacitor_value_uf(footprint_10nf)
        
        # Assert
        assert result_100nf == pytest.approx(0.1), "100nF should equal 0.1µF"
        assert result_10nf == pytest.approx(0.01), "10nF should equal 0.01µF"
    
    def test_parse_microfarads(self):
        """Parse microfarad values (100uF, 22µF, 10UF)."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Act
        footprint_100uf = MockFootprint(value="100uF")
        result_100uf = checker._get_capacitor_value_uf(footprint_100uf)
        
        footprint_22uf = MockFootprint(value="22µF")
        result_22uf = checker._get_capacitor_value_uf(footprint_22uf)
        
        footprint_10uf_upper = MockFootprint(value="10UF")
        result_10uf = checker._get_capacitor_value_uf(footprint_10uf_upper)
        
        # Assert
        assert result_100uf == pytest.approx(100.0), "100uF should equal 100µF"
        assert result_22uf == pytest.approx(22.0), "22µF should equal 22µF"
        assert result_10uf == pytest.approx(10.0), "10UF should equal 10µF"
    
    def test_parse_picofarads(self):
        """Parse picofarad values (100pF, 1000PF)."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Act
        footprint_100pf = MockFootprint(value="100pF")
        result_100pf = checker._get_capacitor_value_uf(footprint_100pf)
        
        footprint_1000pf = MockFootprint(value="1000PF")
        result_1000pf = checker._get_capacitor_value_uf(footprint_1000pf)
        
        # Assert
        assert result_100pf == pytest.approx(0.0001), "100pF should equal 0.0001µF"
        assert result_1000pf == pytest.approx(0.001), "1000pF should equal 0.001µF"
    
    def test_parse_farads(self):
        """Parse farad values (1F - supercapacitor)."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Act
        footprint_1f = MockFootprint(value="1F")
        result_1f = checker._get_capacitor_value_uf(footprint_1f)
        
        # Assert
        assert result_1f == pytest.approx(1_000_000), "1F should equal 1,000,000µF"
    
    def test_parse_decimal_values(self):
        """Parse decimal values (0.1uF, 4.7nF)."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Act
        footprint_01uf = MockFootprint(value="0.1uF")
        result_01uf = checker._get_capacitor_value_uf(footprint_01uf)
        
        footprint_47nf = MockFootprint(value="4.7nF")
        result_47nf = checker._get_capacitor_value_uf(footprint_47nf)
        
        # Assert
        assert result_01uf == pytest.approx(0.1), "0.1uF should equal 0.1µF"
        assert result_47nf == pytest.approx(0.0047), "4.7nF should equal 0.0047µF"
    
    def test_parse_invalid_value_returns_none(self):
        """Invalid or unparseable values return None."""
        # Arrange
        checker = DecouplingChecker(
            board=MockBoard(),
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Act
        footprint_invalid = MockFootprint(value="UNKNOWN")
        result_invalid = checker._get_capacitor_value_uf(footprint_invalid)
        
        footprint_text = MockFootprint(value="DNP")
        result_text = checker._get_capacitor_value_uf(footprint_text)
        
        # Assert
        assert result_invalid is None, "Invalid value should return None"
        assert result_text is None, "Text value should return None"


# -----------------------------------------------------------------------------
# Test: _count_vias_near_capacitor()
# -----------------------------------------------------------------------------

class TestCountViasNearCapacitor:
    """Test via counting near capacitor pads."""
    
    def test_count_vias_within_radius(self):
        """Count vias within search radius of capacitor."""
        # Arrange
        import pcbnew  # Mock from conftest.py
        
        board = MockBoard()
        checker = DecouplingChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Inject distance function
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        checker.get_distance = get_distance
        
        # Capacitor at (0, 0) with two pads
        cap_pads = [
            MockPad(position=(0, 0)),
            MockPad(position=(pcbnew.FromMM(2), 0))  # 2mm away
        ]
        cap_footprint = MockFootprint(pads=cap_pads, position=(0, 0))
        
        # Add vias to board
        board._tracks = [
            MockVia(position=(pcbnew.FromMM(0.5), 0)),     # Within 2mm of pad 1
            MockVia(position=(pcbnew.FromMM(1.5), 0)),     # Within 2mm of pad 2
            MockVia(position=(pcbnew.FromMM(5), 0))        # Outside 2mm radius
        ]
        
        # Act
        via_count = checker._count_vias_near_capacitor(cap_footprint, 2.0)
        
        # Assert
        assert via_count == 2, "Should count 2 vias within 2mm radius"
    
    def test_count_vias_none_within_radius(self):
        """No vias within search radius."""
        # Arrange
        import pcbnew
        
        board = MockBoard()
        checker = DecouplingChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        checker.get_distance = get_distance
        
        # Capacitor at (0, 0)
        cap_pads = [MockPad(position=(0, 0))]
        cap_footprint = MockFootprint(pads=cap_pads)
        
        # Vias far away
        board._tracks = [
            MockVia(position=(pcbnew.FromMM(10), 0)),
            MockVia(position=(pcbnew.FromMM(15), 0))
        ]
        
        # Act
        via_count = checker._count_vias_near_capacitor(cap_footprint, 2.0)
        
        # Assert
        assert via_count == 0, "Should count 0 vias when all are outside radius"
    
    def test_count_vias_no_vias_on_board(self):
        """Board has no vias."""
        # Arrange
        board = MockBoard()
        checker = DecouplingChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        def get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        checker.get_distance = get_distance
        
        # Capacitor at (0, 0)
        cap_pads = [MockPad(position=(0, 0))]
        cap_footprint = MockFootprint(pads=cap_pads)
        
        # No vias
        board._tracks = []
        
        # Act
        via_count = checker._count_vias_near_capacitor(cap_footprint, 2.0)
        
        # Assert
        assert via_count == 0, "Should count 0 vias when board has no vias"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
