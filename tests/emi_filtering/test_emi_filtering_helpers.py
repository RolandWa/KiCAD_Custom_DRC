"""
Unit tests for EMI Filtering helper methods.

Tests individual helper methods in isolation without full board context.
Uses lightweight mock objects for fast execution.
"""

import pytest
import sys
from unittest.mock import MagicMock
import pcbnew


# Import the checker module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "emi_filtering",
    "src/emi_filtering.py"
)
emi_filtering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emi_filtering)
EMIFilteringChecker = emi_filtering.EMIFilteringChecker


# =============================================================================
# Mock Objects
# =============================================================================

class MockNet:
    """Mock pcbnew.NETINFO_ITEM"""
    def __init__(self, name, code=None):
        self._name = name
        self._code = code if code is not None else hash(name)
    
    def GetNetname(self):
        return self._name
    
    def GetNetCode(self):
        return self._code


class MockPad:
    """Mock pcbnew.PAD"""
    def __init__(self, number="1", net_name="", position=(0, 0)):
        self._number = number
        self._net = MockNet(net_name) if net_name else None
        self._position = pcbnew.VECTOR2I(int(position[0]), int(position[1]))
    
    def GetNumber(self):
        return self._number
    
    def GetNet(self):
        return self._net
    
    def GetPosition(self):
        return self._position


class MockFPID:
    """Mock pcbnew.LIB_ID (footprint identifier)"""
    def __init__(self, lib_item_name=""):
        self._lib_item_name = lib_item_name
    
    def GetLibItemName(self):
        return self._lib_item_name


class MockFootprint:
    """Mock pcbnew.FOOTPRINT"""
    def __init__(self, reference="", fpid_name="", pads=None, position=(0, 0)):
        self._reference = reference
        self._fpid = MockFPID(fpid_name)
        self._pads = pads or []
        self._position = pcbnew.VECTOR2I(int(position[0]), int(position[1]))
    
    def GetReference(self):
        return self._reference
    
    def GetFPID(self):
        return self._fpid
    
    def Pads(self):
        return iter(self._pads)
    
    def GetPosition(self):
        return self._position


class MockBoard:
    """Mock pcbnew.BOARD"""
    def __init__(self):
        self._footprints = []
        self._nets = {}
    
    def GetFootprints(self):
        return iter(self._footprints)
    
    def FindNet(self, net_name):
        """Find net by name"""
        return self._nets.get(net_name)
    
    def AddNet(self, net_name, net_code=None):
        """Helper to add nets for testing"""
        net = MockNet(net_name, net_code)
        self._nets[net_name] = net
        return net


# =============================================================================
# Test: _detect_interface_type()
# =============================================================================

class TestDetectInterfaceType:
    """Test interface type detection from reference and footprint name."""
    
    def test_usb_connector_detected_from_reference(self):
        """USB in reference should be detected."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        footprint = MockFootprint(reference="J_USB1", fpid_name="")
        interface_type = checker._detect_interface_type("J_USB1", footprint)
        
        assert interface_type == "USB"
    
    def test_usb_connector_detected_from_footprint(self):
        """USB in footprint name should be detected."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        footprint = MockFootprint(reference="J1", fpid_name="USB_C_Receptacle")
        interface_type = checker._detect_interface_type("J1", footprint)
        
        assert interface_type == "USB"
    
    def test_ethernet_rj45_detected(self):
        """Ethernet RJ45 connector should be detected."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        footprint = MockFootprint(reference="J_ETH1", fpid_name="RJ45_Amphenol")
        interface_type = checker._detect_interface_type("J_ETH1", footprint)
        
        assert interface_type == "Ethernet"
    
    def test_can_connector_detected(self):
        """CAN bus connector should be detected."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        footprint = MockFootprint(reference="J_CAN1", fpid_name="")
        interface_type = checker._detect_interface_type("J_CAN1", footprint)
        
        assert interface_type == "CAN"
    
    def test_hdmi_connector_detected(self):
        """HDMI connector should be detected."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        footprint = MockFootprint(reference="J1", fpid_name="HDMI_TYPE_A")
        interface_type = checker._detect_interface_type("J1", footprint)
        
        assert interface_type == "HDMI"
    
    def test_rs485_connector_detected(self):
        """RS485 connector should be detected."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        footprint = MockFootprint(reference="J_RS485", fpid_name="")
        interface_type = checker._detect_interface_type("J_RS485", footprint)
        
        assert interface_type == "RS485"
    
    def test_unknown_connector_returns_unknown(self):
        """Generic connector should return 'Unknown'."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        footprint = MockFootprint(reference="J1", fpid_name="Generic_Connector")
        interface_type = checker._detect_interface_type("J1", footprint)
        
        assert interface_type == "Unknown"


# =============================================================================
# Test: _get_signal_pads()
# =============================================================================

class TestGetSignalPads:
    """Test signal pad isolation (exclude GND/VCC/shield pads)."""
    
    def test_exclude_ground_pads(self):
        """Pads on GND nets should be excluded."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        pads = [
            MockPad(number="1", net_name="USB_DP", position=(0, 0)),
            MockPad(number="2", net_name="GND", position=(0, 1000)),
            MockPad(number="3", net_name="GROUND", position=(0, 2000)),
            MockPad(number="4", net_name="VSS", position=(0, 3000)),
        ]
        footprint = MockFootprint(reference="J1", pads=pads)
        
        signal_pads = checker._get_signal_pads(footprint)
        
        assert len(signal_pads) == 1
        assert signal_pads[0].GetNet().GetNetname() == "USB_DP"
    
    def test_exclude_power_pads(self):
        """Pads on power nets should be excluded."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        pads = [
            MockPad(number="1", net_name="ETH_TXP", position=(0, 0)),
            MockPad(number="2", net_name="VCC", position=(0, 1000)),
            MockPad(number="3", net_name="+3V3", position=(0, 2000)),
            MockPad(number="4", net_name="VBUS", position=(0, 3000)),
        ]
        footprint = MockFootprint(reference="J1", pads=pads)
        
        signal_pads = checker._get_signal_pads(footprint)
        
        assert len(signal_pads) == 1
        assert signal_pads[0].GetNet().GetNetname() == "ETH_TXP"
    
    def test_exclude_shield_pads(self):
        """Pads on SHIELD nets should be excluded."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        pads = [
            MockPad(number="1", net_name="CAN_H", position=(0, 0)),
            MockPad(number="2", net_name="SHIELD", position=(0, 1000)),
        ]
        footprint = MockFootprint(reference="J1", pads=pads)
        
        signal_pads = checker._get_signal_pads(footprint)
        
        assert len(signal_pads) == 1
        assert signal_pads[0].GetNet().GetNetname() == "CAN_H"
    
    def test_return_only_signal_pads(self):
        """Should return all signal pads (exclude GND/power)."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        pads = [
            MockPad(number="1", net_name="USB_DP", position=(0, 0)),
            MockPad(number="2", net_name="USB_DM", position=(0, 1000)),
            MockPad(number="3", net_name="GND", position=(0, 2000)),
            MockPad(number="4", net_name="VBUS", position=(0, 3000)),
        ]
        footprint = MockFootprint(reference="J1", pads=pads)
        
        signal_pads = checker._get_signal_pads(footprint)
        
        assert len(signal_pads) == 2
        signal_names = [pad.GetNet().GetNetname() for pad in signal_pads]
        assert "USB_DP" in signal_names
        assert "USB_DM" in signal_names
    
    def test_no_net_pads_excluded(self):
        """Pads without net connection should be excluded."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        pads = [
            MockPad(number="1", net_name="USB_DP", position=(0, 0)),
            MockPad(number="2", net_name="", position=(0, 1000)),  # No net
        ]
        footprint = MockFootprint(reference="J1", pads=pads)
        
        signal_pads = checker._get_signal_pads(footprint)
        
        assert len(signal_pads) == 1
        assert signal_pads[0].GetNet().GetNetname() == "USB_DP"


# =============================================================================
# Test: _analyze_component_placement()
# =============================================================================

class TestAnalyzeComponentPlacement:
    """Test series/shunt classification of filter components."""
    
    def test_series_component_both_pads_on_signal(self):
        """Component with both pads on signal net = series."""
        board = MockBoard()
        config = {
            'ground_patterns': ['GND', 'GROUND', 'VSS'],
            'power_patterns': ['VCC', 'VDD', '3V3']
        }
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Resistor R1 with both pads on USB_DP (series in signal path)
        pads = [
            MockPad(number="1", net_name="USB_DP"),
            MockPad(number="2", net_name="USB_DP"),
        ]
        footprint = MockFootprint(reference="R1", pads=pads)
        signal_net = MockNet("USB_DP")
        
        comp_type, net_info = checker._analyze_component_placement(footprint, signal_net)
        
        assert comp_type == "series"
        assert net_info['type'] == "series"
    
    def test_shunt_component_one_pad_to_ground(self):
        """Component with one pad on signal, other on GND = shunt."""
        board = MockBoard()
        config = {
            'ground_patterns': ['GND', 'GROUND', 'VSS'],
            'power_patterns': ['VCC', 'VDD', '3V3']
        }
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Capacitor C1 with one pad on USB_DP, other on GND (shunt to ground)
        pads = [
            MockPad(number="1", net_name="USB_DP"),
            MockPad(number="2", net_name="GND"),
        ]
        footprint = MockFootprint(reference="C1", pads=pads)
        signal_net = MockNet("USB_DP")
        
        comp_type, net_info = checker._analyze_component_placement(footprint, signal_net)
        
        assert comp_type == "shunt"
        assert net_info['type'] == "shunt"
    
    def test_shunt_component_one_pad_to_power(self):
        """Component with one pad on signal, other on VCC = shunt."""
        board = MockBoard()
        config = {
            'ground_patterns': ['GND', 'GROUND', 'VSS'],
            'power_patterns': ['VCC', 'VDD', '3V3']
        }
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Capacitor C1 with one pad on signal, other on VCC (shunt to power)
        pads = [
            MockPad(number="1", net_name="SIGNAL"),
            MockPad(number="2", net_name="VCC"),
        ]
        footprint = MockFootprint(reference="C1", pads=pads)
        signal_net = MockNet("SIGNAL")
        
        comp_type, net_info = checker._analyze_component_placement(footprint, signal_net)
        
        assert comp_type == "shunt"
        assert net_info['type'] == "shunt"
    
    def test_unknown_component_single_pad(self):
        """Component with <2 pads = unknown."""
        board = MockBoard()
        config = {
            'ground_patterns': ['GND'],
            'power_patterns': ['VCC']
        }
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        pads = [MockPad(number="1", net_name="USB_DP")]
        footprint = MockFootprint(reference="TP1", pads=pads)
        signal_net = MockNet("USB_DP")
        
        comp_type, net_info = checker._analyze_component_placement(footprint, signal_net)
        
        assert comp_type == "unknown"


# =============================================================================
# Test: _check_filter_requirement()
# =============================================================================

class TestFilterRequirement:
    """Test filter hierarchy validation."""
    
    def test_pi_filter_meets_lc_requirement(self):
        """Pi filter should meet LC requirement (Pi > LC in hierarchy)."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        sufficient = checker._check_filter_requirement("Pi", "LC")
        
        assert sufficient is True
    
    def test_lc_filter_meets_lc_requirement(self):
        """LC filter should meet LC requirement (exact match)."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        sufficient = checker._check_filter_requirement("LC", "LC")
        
        assert sufficient is True
    
    def test_single_c_insufficient_for_lc(self):
        """Single capacitor insufficient for LC requirement."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        sufficient = checker._check_filter_requirement("C", "LC")
        
        assert sufficient is False
    
    def test_single_l_insufficient_for_lc(self):
        """Single inductor insufficient for LC requirement."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        sufficient = checker._check_filter_requirement("L", "LC")
        
        assert sufficient is False
    
    def test_rc_filter_insufficient_for_lc(self):
        """RC filter insufficient for LC requirement (RC < LC)."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        sufficient = checker._check_filter_requirement("RC", "LC")
        
        assert sufficient is False
    
    def test_t_filter_meets_lc_requirement(self):
        """T filter should meet LC requirement (T > LC in hierarchy)."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        sufficient = checker._check_filter_requirement("T", "LC")
        
        assert sufficient is True
    
    def test_none_filter_always_insufficient(self):
        """None filter always insufficient."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        sufficient = checker._check_filter_requirement(None, "LC")
        
        assert sufficient is False
    
    def test_hierarchy_order_respected(self):
        """Test full hierarchy: Pi > T > LC > RC > L > C > R > simple."""
        board = MockBoard()
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        # Pi meets everything
        assert checker._check_filter_requirement("Pi", "T") is True
        assert checker._check_filter_requirement("Pi", "LC") is True
        assert checker._check_filter_requirement("Pi", "simple") is True
        
        # LC meets RC and below
        assert checker._check_filter_requirement("LC", "RC") is True
        assert checker._check_filter_requirement("LC", "simple") is True
        
        # RC does NOT meet LC
        assert checker._check_filter_requirement("RC", "LC") is False


# =============================================================================
# Test: _find_connectors()
# =============================================================================

class TestFindConnectors:
    """Test connector discovery by reference prefix."""
    
    def test_find_connectors_with_j_prefix(self):
        """Should find all connectors starting with 'J'."""
        board = MockBoard()
        board._footprints = [
            MockFootprint(reference="J1"),
            MockFootprint(reference="J2"),
            MockFootprint(reference="U1"),  # Not a connector
            MockFootprint(reference="C1"),  # Not a connector
        ]
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        connectors = checker._find_connectors("J")
        
        assert len(connectors) == 2
        refs = [ref for ref, fp in connectors]
        assert "J1" in refs
        assert "J2" in refs
    
    def test_no_connectors_found(self):
        """Should return empty list if no connectors."""
        board = MockBoard()
        board._footprints = [
            MockFootprint(reference="U1"),
            MockFootprint(reference="C1"),
        ]
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config={},
            report_lines=[],
            verbose=False,
            auditor=MagicMock()
        )
        
        connectors = checker._find_connectors("J")
        
        assert len(connectors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
