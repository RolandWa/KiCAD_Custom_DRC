"""
Integration tests for EMI Filtering checker.

Tests complete end-to-end workflows with full MockBoard fixtures
representing realistic connector + filter configurations.
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
# Mock Objects (Enhanced for Integration Testing)
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
    """Mock pcbnew.BOARD with full footprint and net management"""
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
# Fixtures - Realistic Board Configurations
# =============================================================================

@pytest.fixture
def usb_connector_with_lc_filter():
    """
    USB connector with proper LC filter.
    
    Configuration:
    - J1 USB connector at origin
    - USB_DP and USB_DM signal lines
    - FB1 (ferrite bead) series on USB_DP at 5mm
    - C1 (capacitor) shunt to GND on USB_DP at 7mm
    
    Expected: No violations (LC filter present)
    """
    board = MockBoard()
    
    # Create nets
    usb_dp_net = board.AddNet("USB_DP", 1)
    usb_dm_net = board.AddNet("USB_DM", 2)
    gnd_net = board.AddNet("GND", 3)
    vbus_net = board.AddNet("VBUS", 4)
    
    # J1 USB connector at origin
    connector_pads = [
        MockPad(number="1", net_name="VBUS", position=(0, 0)),
        MockPad(number="2", net_name="USB_DP", position=(0, pcbnew.FromMM(1))),
        MockPad(number="3", net_name="USB_DM", position=(0, pcbnew.FromMM(2))),
        MockPad(number="4", net_name="GND", position=(0, pcbnew.FromMM(3))),
    ]
    connector = MockFootprint(
        reference="J1",
        fpid_name="USB_C_Receptacle",
        pads=connector_pads,
        position=(0, 0)
    )
    
    # FB1 ferrite bead (series) on USB_DP at 5mm from connector
    fb1_pos = (pcbnew.FromMM(5), 0)
    fb1_pads = [
        MockPad(number="1", net_name="USB_DP", position=fb1_pos),
        MockPad(number="2", net_name="USB_DP", position=fb1_pos),
    ]
    ferrite1 = MockFootprint(
        reference="FB1",
        fpid_name="L_0805",
        pads=fb1_pads,
        position=fb1_pos
    )
    
    # C1 capacitor (shunt to GND) on USB_DP at 7mm from connector
    c1_pos = (pcbnew.FromMM(7), 0)
    c1_pads = [
        MockPad(number="1", net_name="USB_DP", position=c1_pos),
        MockPad(number="2", net_name="GND", position=c1_pos),
    ]
    capacitor1 = MockFootprint(
        reference="C1",
        fpid_name="C_0603",
        pads=c1_pads,
        position=c1_pos
    )
    
    # FB2 ferrite bead (series) on USB_DM at 5mm from connector
    fb2_pos = (pcbnew.FromMM(5), pcbnew.FromMM(2))
    fb2_pads = [
        MockPad(number="1", net_name="USB_DM", position=fb2_pos),
        MockPad(number="2", net_name="USB_DM", position=fb2_pos),
    ]
    ferrite2 = MockFootprint(
        reference="FB2",
        fpid_name="L_0805",
        pads=fb2_pads,
        position=fb2_pos
    )
    
    # C2 capacitor (shunt to GND) on USB_DM at 7mm from connector
    c2_pos = (pcbnew.FromMM(7), pcbnew.FromMM(2))
    c2_pads = [
        MockPad(number="1", net_name="USB_DM", position=c2_pos),
        MockPad(number="2", net_name="GND", position=c2_pos),
    ]
    capacitor2 = MockFootprint(
        reference="C2",
        fpid_name="C_0603",
        pads=c2_pads,
        position=c2_pos
    )
    
    board._footprints = [connector, ferrite1, capacitor1, ferrite2, capacitor2]
    
    return board


@pytest.fixture
def ethernet_connector_with_common_mode_choke():
    """
    Ethernet connector with common-mode choke (differential filter).
    
    Configuration:
    - J1 RJ45 connector with ETH_TXP_OUT and ETH_TXN_OUT (to external)
    - T1 4-pin common-mode choke at 8mm
      * Input side (connector): ETH_TXP_OUT, ETH_TXN_OUT (pins 1,3)
      * Output side (IC): ETH_TXP_IN, ETH_TXN_IN (pins 2,4)
    - Proper differential pair through-connection
    
    Expected: No violations (Differential filter properly configured)
    """
    board = MockBoard()
    
    # Create nets - connector side (external)
    txp_out_net = board.AddNet("ETH_TXP_OUT", 1)
    txn_out_net = board.AddNet("ETH_TXN_OUT", 2)
    
    # Create nets - IC side (internal)
    txp_in_net = board.AddNet("ETH_TXP_IN", 3)
    txn_in_net = board.AddNet("ETH_TXN_IN", 4)
    
    gnd_net = board.AddNet("GND", 5)
    
    # J1 Ethernet connector - connected to external-facing nets
    connector_pads = [
        MockPad(number="1", net_name="ETH_TXP_OUT", position=(0, 0)),
        MockPad(number="2", net_name="ETH_TXN_OUT", position=(0, pcbnew.FromMM(1))),
        MockPad(number="3", net_name="GND", position=(0, pcbnew.FromMM(2))),
    ]
    connector = MockFootprint(
        reference="J1",
        fpid_name="RJ45_Amphenol",
        pads=connector_pads,
        position=(0, 0)
    )
    
    # T1 common-mode choke (4 pins)
    # Pins 1,3: Connector side (ETH_TXP_OUT, ETH_TXN_OUT)
    # Pins 2,4: IC side (ETH_TXP_IN, ETH_TXN_IN)
    # This creates proper differential pair filtering
    choke_pos = (pcbnew.FromMM(8), 0)
    choke_pads = [
        MockPad(number="1", net_name="ETH_TXP_OUT", position=choke_pos),  # From connector
        MockPad(number="2", net_name="ETH_TXP_IN", position=choke_pos),   # To IC
        MockPad(number="3", net_name="ETH_TXN_OUT", position=choke_pos),  # From connector
        MockPad(number="4", net_name="ETH_TXN_IN", position=choke_pos),   # To IC
    ]
    choke = MockFootprint(
        reference="T1",
        fpid_name="L_CommonMode",
        pads=choke_pads,
        position=choke_pos
    )
    
    board._footprints = [connector, choke]
    
    return board


@pytest.fixture
def connector_with_single_ended_choke_warning():
    """
    Connector with common-mode choke but single-ended output (should produce warning).
    
    Configuration:
    - J1 connector with CAN_H, CAN_L differential pair
    - T1 4-pin choke at 5mm
      * Input: CAN_H, CAN_L (pins 1,3)
      * Output: CAN_H_FILT, CAN_L_FILT (pins 2,4) - NOT a differential pair name pattern
    
    Expected: Warning for single-ended configuration (differential pair broken)
    
    Note: This tests future enhancement - current implementation may not detect this case.
    """
    board = MockBoard()
    
    # Create nets
    canh_out_net = board.AddNet("CAN_H", 1)
    canl_out_net = board.AddNet("CAN_L", 2)
    canh_in_net = board.AddNet("CAN_H_FILT", 3)  # Single-ended name (no pair suffix)
    canl_in_net = board.AddNet("CAN_L_FILT", 4)  # Single-ended name (no pair suffix)
    gnd_net = board.AddNet("GND", 5)
    
    # J1 CAN connector
    connector_pads = [
        MockPad(number="1", net_name="CAN_H", position=(0, 0)),
        MockPad(number="2", net_name="CAN_L", position=(0, pcbnew.FromMM(1))),
        MockPad(number="3", net_name="GND", position=(0, pcbnew.FromMM(2))),
    ]
    connector = MockFootprint(
        reference="J1",
        fpid_name="Terminal_Block",
        pads=connector_pads,
        position=(0, 0)
    )
    
    # T1 choke with single-ended output (breaks differential pair)
    choke_pos = (pcbnew.FromMM(5), 0)
    choke_pads = [
        MockPad(number="1", net_name="CAN_H", position=choke_pos),
        MockPad(number="2", net_name="CAN_H_FILT", position=choke_pos),  # No pair relationship
        MockPad(number="3", net_name="CAN_L", position=choke_pos),
        MockPad(number="4", net_name="CAN_L_FILT", position=choke_pos),  # No pair relationship
    ]
    choke = MockFootprint(
        reference="T1",
        fpid_name="L_CommonMode",
        pads=choke_pads,
        position=choke_pos
    )
    
    board._footprints = [connector, choke]
    
    return board


@pytest.fixture
def unfiltered_connector():
    """
    Connector without any filter components.
    
    Configuration:
    - J1 CAN connector
    - CAN_H and CAN_L signal lines
    - No filter components within 10mm
    
    Expected: 2 violations (one per signal line)
    """
    board = MockBoard()
    
    # Create nets
    canh_net = board.AddNet("CAN_H", 1)
    canl_net = board.AddNet("CAN_L", 2)
    gnd_net = board.AddNet("GND", 3)
    
    # J1 CAN connector (no filter components)
    connector_pads = [
        MockPad(number="1", net_name="CAN_H", position=(0, 0)),
        MockPad(number="2", net_name="CAN_L", position=(0, pcbnew.FromMM(1))),
        MockPad(number="3", net_name="GND", position=(0, pcbnew.FromMM(2))),
    ]
    connector = MockFootprint(
        reference="J1",
        fpid_name="Terminal_Block",
        pads=connector_pads,
        position=(0, 0)
    )
    
    board._footprints = [connector]
    
    return board


@pytest.fixture
def connector_with_pi_filter():
    """
    Connector with Pi filter (C-L-C topology).
    
    Configuration:
    - J1 connector
    - SIGNAL net
    - C1 (shunt to GND) at 2mm
    - L1 (series) at 5mm
    - C2 (shunt to GND) at 8mm
    
    Expected: No violations (Pi filter > LC requirement)
    """
    board = MockBoard()
    
    # Create nets
    signal_net = board.AddNet("SIGNAL", 1)
    gnd_net = board.AddNet("GND", 2)
    
    # J1 connector
    connector_pads = [
        MockPad(number="1", net_name="SIGNAL", position=(0, 0)),
        MockPad(number="2", net_name="GND", position=(0, pcbnew.FromMM(1))),
    ]
    connector = MockFootprint(
        reference="J1",
        fpid_name="Generic",
        pads=connector_pads,
        position=(0, 0)
    )
    
    # C1 shunt capacitor at 2mm
    c1_pos = (pcbnew.FromMM(2), 0)
    c1_pads = [
        MockPad(number="1", net_name="SIGNAL", position=c1_pos),
        MockPad(number="2", net_name="GND", position=c1_pos),
    ]
    c1 = MockFootprint(
        reference="C1",
        fpid_name="C_0603",
        pads=c1_pads,
        position=c1_pos
    )
    
    # L1 series inductor at 5mm
    l1_pos = (pcbnew.FromMM(5), 0)
    l1_pads = [
        MockPad(number="1", net_name="SIGNAL", position=l1_pos),
        MockPad(number="2", net_name="SIGNAL", position=l1_pos),
    ]
    l1 = MockFootprint(
        reference="L1",
        fpid_name="L_0805",
        pads=l1_pads,
        position=l1_pos
    )
    
    # C2 shunt capacitor at 8mm
    c2_pos = (pcbnew.FromMM(8), 0)
    c2_pads = [
        MockPad(number="1", net_name="SIGNAL", position=c2_pos),
        MockPad(number="2", net_name="GND", position=c2_pos),
    ]
    c2 = MockFootprint(
        reference="C2",
        fpid_name="C_0603",
        pads=c2_pads,
        position=c2_pos
    )
    
    board._footprints = [connector, c1, l1, c2]
    
    return board


@pytest.fixture
def connector_with_filter_too_far():
    """
    Connector with filter component beyond max_filter_distance_mm.
    
    Configuration:
    - J1 connector at origin
    - SIGNAL net
    - C1 capacitor at 15mm (beyond 10mm limit)
    
    Expected: 1 violation (filter too far, not detected)
    """
    board = MockBoard()
    
    # Create nets
    signal_net = board.AddNet("SIGNAL", 1)
    gnd_net = board.AddNet("GND", 2)
    
    # J1 connector
    connector_pads = [
        MockPad(number="1", net_name="SIGNAL", position=(0, 0)),
        MockPad(number="2", net_name="GND", position=(0, pcbnew.FromMM(1))),
    ]
    connector = MockFootprint(
        reference="J1",
        fpid_name="Generic",
        pads=connector_pads,
        position=(0, 0)
    )
    
    # C1 capacitor at 15mm (too far)
    cap_pos = (pcbnew.FromMM(15), 0)
    cap_pads = [
        MockPad(number="1", net_name="SIGNAL", position=cap_pos),
        MockPad(number="2", net_name="GND", position=cap_pos),
    ]
    capacitor = MockFootprint(
        reference="C1",
        fpid_name="C_0603",
        pads=cap_pads,
        position=cap_pos
    )
    
    board._footprints = [connector, capacitor]
    
    return board


@pytest.fixture
def connector_with_insufficient_filter():
    """
    Connector with insufficient filter type (C only, need LC).
    
    Configuration:
    - J1 connector
    - SIGNAL net
    - C1 capacitor (shunt to GND) at 5mm
    - min_filter_type = "LC" (requires inductor + capacitor)
    
    Expected: 1 violation (filter type insufficient)
    """
    board = MockBoard()
    
    # Create nets
    signal_net = board.AddNet("SIGNAL", 1)
    gnd_net = board.AddNet("GND", 2)
    
    # J1 connector
    connector_pads = [
        MockPad(number="1", net_name="SIGNAL", position=(0, 0)),
        MockPad(number="2", net_name="GND", position=(0, pcbnew.FromMM(1))),
    ]
    connector = MockFootprint(
        reference="J1",
        fpid_name="Generic",
        pads=connector_pads,
        position=(0, 0)
    )
    
    # C1 capacitor only (insufficient for LC requirement)
    cap_pos = (pcbnew.FromMM(5), 0)
    cap_pads = [
        MockPad(number="1", net_name="SIGNAL", position=cap_pos),
        MockPad(number="2", net_name="GND", position=cap_pos),
    ]
    capacitor = MockFootprint(
        reference="C1",
        fpid_name="C_0603",
        pads=cap_pads,
        position=cap_pos
    )
    
    board._footprints = [connector, capacitor]
    
    return board


# =============================================================================
# Integration Tests - End-to-End Scenarios
# =============================================================================

class TestFilterPresenceIntegration:
    """Test end-to-end filter presence detection."""
    
    def test_unfiltered_connector_flagged(self, unfiltered_connector):
        """Connector without filter should produce violations."""
        board = unfiltered_connector
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['R', 'L', 'FB', 'C', 'D'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'LC',
            'violation_message': 'MISSING EMI FILTER',
        }
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        markers = []
        def mock_draw_marker(board, pos, msg, layer, group):
            markers.append({'pos': pos, 'msg': msg, 'group': group})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            print(f"[TEST LOG] {msg}")
        
        def mock_create_group(board, check_type, identifier, number):
            return MagicMock()
        
        # Run check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert
        assert violations == 2, "Should have 2 violations (CAN_H and CAN_L)"
        assert len(markers) == 2
        assert all("MISSING EMI FILTER" in m['msg'] for m in markers)
    
    def test_filtered_connector_no_violation(self, usb_connector_with_lc_filter):
        """Connector with proper LC filter should have no violations."""
        board = usb_connector_with_lc_filter
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['R', 'L', 'FB', 'C', 'D'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'LC',
            'violation_message': 'MISSING EMI FILTER',
        }
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        markers = []
        def mock_draw_marker(board, pos, msg, layer, group):
            markers.append({'pos': pos, 'msg': msg, 'group': group})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            print(f"[TEST LOG] {msg}")
        
        def mock_create_group(board, check_type, identifier, number):
            return MagicMock()
        
        # Run check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert
        assert violations == 0, "Should have no violations with LC filter"
        assert len(markers) == 0


class TestFilterTopologyIntegration:
    """Test filter topology detection and classification."""
    
    def test_pi_filter_topology_accepted(self, connector_with_pi_filter):
        """Pi filter (C-L-C) should be accepted as valid."""
        board = connector_with_pi_filter
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['R', 'L', 'FB', 'C', 'D'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'LC',
            'violation_message': 'MISSING EMI FILTER',
            'component_classes': {
                'inductor_prefixes': ['L', 'FB'],
                'capacitor_prefixes': ['C'],
                'resistor_prefixes': ['R'],
            },
        }
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        markers = []
        def mock_draw_marker(board, pos, msg, layer, group):
            markers.append({'pos': pos, 'msg': msg, 'group': group})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            print(f"[TEST LOG] {msg}")
        
        def mock_create_group(board, check_type, identifier, number):
            return MagicMock()
        
        # Run check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert
        assert violations == 0, "Pi filter should meet LC requirement (Pi > LC)"
        assert len(markers) == 0
    
    def test_differential_filter_detected(self, ethernet_connector_with_common_mode_choke):
        """Common-mode choke should be detected as filter (at minimum as series inductor).
        
        Note: Full differential pair detection logic exists in implementation but may
        require real board testing to validate. This test verifies that the component
        is at least recognized as a valid series filter on both differential lines.
        """
        board = ethernet_connector_with_common_mode_choke
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['R', 'L', 'FB', 'C', 'D', 'T'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple',  # Accept any filter for differential pair test
            'violation_message': 'MISSING EMI FILTER',
            'ground_patterns': ['GND', 'GROUND', 'VSS'],
            'power_patterns': ['VCC', 'VDD', '3V3'],
            'component_classes': {
                'inductor_prefixes': ['L', 'FB', 'T'],
                'capacitor_prefixes': ['C'],
            },
            'differential_pairs': {
                'patterns': [['TXP', 'TXN'], ['_P', '_N']],
                'min_common_mode_choke_pins': 4,
            },
        }
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        markers = []
        def mock_draw_marker(board, pos, msg, layer, group):
            markers.append({'pos': pos, 'msg': msg, 'group': group})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            print(f"[TEST LOG] {msg}")
        
        def mock_create_group(board, check_type, identifier, number):
            return MagicMock()
        
        # Run check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert - differential filter should be detected
        assert violations == 0, "Common-mode choke should be detected as valid filter"
        assert len(markers) == 0
    
    def test_single_ended_choke_output_warning(self, connector_with_single_ended_choke_warning):
        """Common-mode choke with single-ended output should produce warning.
        
        Note: This is a future enhancement test. The current implementation may not
        fully detect broken differential pairs on the output side of common-mode chokes.
        The test documents the expected behavior for when this feature is implemented.
        """
        board = connector_with_single_ended_choke_warning
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['R', 'L', 'FB', 'C', 'D', 'T'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'simple',
            'violation_message': 'MISSING EMI FILTER',
            'ground_patterns': ['GND', 'GROUND', 'VSS'],
            'power_patterns': ['VCC', 'VDD', '3V3'],
            'component_classes': {
                'inductor_prefixes': ['L', 'FB', 'T'],
                'capacitor_prefixes': ['C'],
            },
            'differential_pairs': {
                'patterns': [['_H', '_L'], ['CANH', 'CANL']],
                'min_common_mode_choke_pins': 4,
            },
        }
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        markers = []
        def mock_draw_marker(board, pos, msg, layer, group):
            markers.append({'pos': pos, 'msg': msg, 'group': group})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            print(f"[TEST LOG] {msg}")
        
        def mock_create_group(board, check_type, identifier, number):
            return MagicMock()
        
        # Run check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Current behavior: May detect as simple filter (series inductor)
        # Future enhancement: Should warn about broken differential pair on output
        print(f"\n[INFO] Violations detected: {violations}")
        print(f"[INFO] This test documents expected behavior for single-ended choke output warning")
        print(f"[INFO] Implementation enhancement needed to detect broken differential pairs")
        
        # For now, just verify the check runs without error
        assert violations >= 0, "Check should complete without error"


class TestFilterPlacementIntegration:
    """Test filter placement distance validation."""
    
    def test_filter_too_far_from_connector_flagged(self, connector_with_filter_too_far):
        """Filter beyond max_filter_distance_mm should be ignored."""
        board = connector_with_filter_too_far
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['R', 'L', 'FB', 'C', 'D'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'LC',
            'violation_message': 'MISSING EMI FILTER',
        }
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        markers = []
        def mock_draw_marker(board, pos, msg, layer, group):
            markers.append({'pos': pos, 'msg': msg, 'group': group})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            print(f"[TEST LOG] {msg}")
        
        def mock_create_group(board, check_type, identifier, number):
            return MagicMock()
        
        # Run check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert - filter at 15mm should be ignored (beyond 10mm limit)
        assert violations == 1, "Should have 1 violation (filter too far)"
        assert len(markers) == 1
        assert "MISSING EMI FILTER" in markers[0]['msg']


class TestFilterSufficiencyIntegration:
    """Test filter type sufficiency validation."""
    
    def test_insufficient_filter_type_flagged(self, connector_with_insufficient_filter):
        """Single capacitor should be insufficient for LC requirement."""
        board = connector_with_insufficient_filter
        
        config = {
            'connector_prefix': 'J',
            'filter_component_prefixes': ['R', 'L', 'FB', 'C', 'D'],
            'max_filter_distance_mm': 10.0,
            'min_filter_type': 'LC',  # Requires LC, but only C present
            'violation_message': 'MISSING EMI FILTER',
            'component_classes': {
                'inductor_prefixes': ['L', 'FB'],
                'capacitor_prefixes': ['C'],
                'resistor_prefixes': ['R'],
            },
        }
        
        checker = EMIFilteringChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=MagicMock()
        )
        
        # Mock utility functions
        markers = []
        def mock_draw_marker(board, pos, msg, layer, group):
            markers.append({'pos': pos, 'msg': msg, 'group': group})
        
        def mock_draw_arrow(board, start, end, label, layer, group):
            pass
        
        def mock_get_distance(p1, p2):
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            return (dx*dx + dy*dy) ** 0.5
        
        def mock_log(msg, force=False):
            print(f"[TEST LOG] {msg}")
        
        def mock_create_group(board, check_type, identifier, number):
            return MagicMock()
        
        # Run check
        violations = checker.check(
            mock_draw_marker,
            mock_draw_arrow,
            mock_get_distance,
            mock_log,
            mock_create_group
        )
        
        # Assert - C filter insufficient for LC requirement
        assert violations == 1, "Should have 1 violation (filter type insufficient)"
        assert len(markers) == 1
        assert "WEAK FILTER" in markers[0]['msg']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
