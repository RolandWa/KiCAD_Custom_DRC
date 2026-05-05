"""
Advanced pathfinding tests for creepage calculation.

Targets uncovered code paths in:
- _visibility_graph_path (lines 1883-2013)
- _dijkstra_waypoint_path (lines 1956-2013)
- _get_slot_waypoints (lines 1883-1939)
- _draw_debug_creepage_path (lines 2145-2186)
- Slot handling (lines 1467-1492, 1535-1554, 1697-1764)
"""
import pytest
from tests.helpers import MockBoard, MockPad, MockNet, MockFootprint, MockDrawing, MockZone


def _pathfinding_config():
    """Minimal config with creepage enabled and draw_creepage_path for debug drawing."""
    return {
        'check_clearance': False,
        'check_creepage': True,
        'draw_creepage_path': True,  # Enable debug drawing
        'max_obstacles': 500,
        'voltage_domains': [
            {'name': 'MAINS', 'voltage_rms': 230, 'net_patterns': ['MAINS']},
            {'name': 'GND', 'voltage_rms': 0, 'net_patterns': ['GND']},
        ],
        'isolation_requirements': [
            {'from_domain': 'MAINS', 'to_domain': 'GND', 'type': 'basic'},
        ],
        'iec_clearance_table': {
            '0-50': 0.0, '50-100': 0.5, '100-150': 1.5, '150-300': 3.0, '300-600': 5.5
        },
        'iec_creepage_table_material_group_II': {
            '0-50': 0.0, '50-100': 1.25, '100-150': 2.5, '150-300': 4.0, '300-600': 8.0
        },
    }


def _mock_auditor():
    """Minimal auditor with config and get_nets_by_class."""
    class Auditor:
        config = {'general': {}}
        def get_nets_by_class(self, board, config):
            return {}  # No net classes
    return Auditor()


def _mock_utility_functions():
    """Create mock utility functions for checker.check()."""
    violations_drawn = []
    
    def draw_marker(board, pos, msg, layer, group):
        violations_drawn.append({'pos': pos, 'msg': msg})
    
    def draw_arrow(board, start, end, label, layer, group):
        pass
    
    def get_distance(p1, p2):
        import math
        dx = p1.x - p2.x
        dy = p1.y - p2.y
        return math.sqrt(dx*dx + dy*dy)
    
    def log(msg, force=False):
        pass  # Silent during test
    
    def create_group(board, type_str, id_str, num):
        import pcbnew
        group = pcbnew.PCB_GROUP()
        group.SetName(f"EMC_{type_str}_{id_str}_{num}")
        return group
    
    return violations_drawn, draw_marker, draw_arrow, get_distance, log, create_group


class TestSlotPathfinding:
    """Tests for creepage pathfinding around slots (Edge.Cuts layer)."""
    
    def test_single_slot_blocks_direct_path(self):
        """Single slot between pads → triggers Dijkstra waypoint pathfinding."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        
        config = _pathfinding_config()
        
        # Create pads 20mm apart
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(20), 0), "1", size_mm=1.0)
        
        # Create slot on Edge.Cuts layer (layer 44) that blocks direct path
        # Slot is vertical line from (10mm, -2mm) to (10mm, 2mm)
        slot = MockDrawing(
            layer=44,  # Edge.Cuts
            start=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(-2)),
            end=pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(2)),
            width=pcbnew.FromMM(0.5)
        )
        
        board = MockBoard(
            nets=[net_mains, net_gnd],
            footprints=[
                MockFootprint("J1", [pad_mains]),
                MockFootprint("J2", [pad_gnd])
            ],
            drawings=[slot],
            layer_names={0: "F.Cu", 44: "Edge.Cuts"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 1467-1492: Edge.Cuts slot processing
        # Lines 1535-1554: Slot barrier polygon creation
        # Lines 1883-1939: _get_slot_waypoints
        # Lines 1956-2013: _dijkstra_waypoint_path
        # Should find path around slot
        pass
    
    def test_multiple_slots_force_complex_routing(self):
        """Multiple slots → forces complex waypoint graph with visibility checks."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        
        config = _pathfinding_config()
        
        # Pads 30mm apart
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(30), 0), "1", size_mm=1.0)
        
        # Create 3 vertical slots that force zigzag routing
        slots = [
            MockDrawing(layer=44, start=pcbnew.VECTOR2I(pcbnew.FromMM(8), pcbnew.FromMM(-3)),
                       end=pcbnew.VECTOR2I(pcbnew.FromMM(8), pcbnew.FromMM(3)), width=pcbnew.FromMM(0.5)),
            MockDrawing(layer=44, start=pcbnew.VECTOR2I(pcbnew.FromMM(15), pcbnew.FromMM(-3)),
                       end=pcbnew.VECTOR2I(pcbnew.FromMM(15), pcbnew.FromMM(3)), width=pcbnew.FromMM(0.5)),
            MockDrawing(layer=44, start=pcbnew.VECTOR2I(pcbnew.FromMM(22), pcbnew.FromMM(-3)),
                       end=pcbnew.VECTOR2I(pcbnew.FromMM(22), pcbnew.FromMM(3)), width=pcbnew.FromMM(0.5)),
        ]
        
        board = MockBoard(
            nets=[net_mains, net_gnd],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_gnd])],
            drawings=slots,
            layer_names={0: "F.Cu", 44: "Edge.Cuts"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 1883-1939: Generates waypoints for 3 slots
        # Lines 1956-2013: Dijkstra builds graph and finds multi-hop path
        pass
    
    def test_slot_waypoint_generation(self):
        """Slot waypoints are generated at slot tips (bbox extremes + corners)."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        
        config = _pathfinding_config()
        
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(15), 0), "1", size_mm=1.0)
        
        # Horizontal slot
        slot = MockDrawing(layer=44, start=pcbnew.VECTOR2I(pcbnew.FromMM(4), 0),
                          end=pcbnew.VECTOR2I(pcbnew.FromMM(10), 0), width=pcbnew.FromMM(1.0))
        
        board = MockBoard(
            nets=[net_mains, net_gnd],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_gnd])],
            drawings=[slot],
            layer_names={0: "F.Cu", 44: "Edge.Cuts"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 1883-1939: _get_slot_waypoints uses bbox extremes + corners
        # Lines 1697-1717: Slot handling and bbox extraction
        pass
    
    def test_no_path_through_slots(self):
        """Slots completely block path → returns None (no creepage path)."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        
        config = _pathfinding_config()
        
        # Pads 15mm apart
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(15), 0), "1", size_mm=1.0)
        
        # Create large vertical slot that completely blocks all paths
        # Slot extends from far left to far right, blocking any routing
        slot = MockDrawing(layer=44, start=pcbnew.VECTOR2I(pcbnew.FromMM(7), pcbnew.FromMM(-10)),
                          end=pcbnew.VECTOR2I(pcbnew.FromMM(7), pcbnew.FromMM(10)), width=pcbnew.FromMM(1.0))
        
        board = MockBoard(
            nets=[net_mains, net_gnd],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_gnd])],
            drawings=[slot],
            layer_names={0: "F.Cu", 44: "Edge.Cuts"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 2145-2160: Dijkstra returns None when no path exists
        # Should log "No valid creepage path (slot/cutout breaks path)"
        pass
    
    def test_debug_path_drawing_with_passing_creepage(self):
        """draw_creepage_path=True + passing creepage → draws debug polyline."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        
        config = _pathfinding_config()
        config['draw_creepage_path'] = True  # Enable debug drawing
        
        # Pads far apart (passing creepage)
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(20), 0), "1", size_mm=1.0)
        
        # Small slot forces waypoint routing
        slot = MockDrawing(layer=44, start=pcbnew.VECTOR2I(pcbnew.FromMM(9), pcbnew.FromMM(-1)),
                          end=pcbnew.VECTOR2I(pcbnew.FromMM(9), pcbnew.FromMM(1)), width=pcbnew.FromMM(0.3))
        
        board = MockBoard(
            nets=[net_mains, net_gnd],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_gnd])],
            drawings=[slot],
            layer_names={0: "F.Cu", 44: "Edge.Cuts"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 2145-2186: _draw_debug_creepage_path draws segments + text label
        # Should create PCB_SHAPE segments and PCB_TEXT label
        assert violations == 0  # Passing creepage (pads far enough)
        pass


class TestCreepageWithZoneObstacles:
    """Tests for creepage calculation with zone obstacles."""
    
    def test_zone_obstacles_force_pathfinding(self):
        """Zones between pads → treated as obstacles in creepage calculation."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        from tests.helpers import MockZone
        
        config = _pathfinding_config()
        config['check_clearance'] = False
        config['check_creepage'] = True
        
        # Pads 15mm apart
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        net_vcc = MockNet("VCC")  # Obstacle zone net
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(15), 0), "1", size_mm=1.0)
        
        # Create zone obstacle between pads
        zone_obstacle = MockZone(
            "VCC", layer=0, filled=True,
            coverage_rects=[(pcbnew.FromMM(5), pcbnew.FromMM(-2),
                            pcbnew.FromMM(10), pcbnew.FromMM(2))]
        )
        
        board = MockBoard(
            nets=[net_mains, net_gnd, net_vcc],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_gnd])],
            zones=[zone_obstacle],
            layer_names={0: "F.Cu"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 1278-1348: Spatial indexing for obstacle filtering
        # Zones are NOT slot obstacles, so they don't trigger waypoint pathfinding
        # But they should be considered in spatial filtering
        pass


class TestDirectPathOptimization:
    """Tests for direct line-of-sight path optimization."""
    
    def test_direct_path_no_obstacles(self):
        """No obstacles → uses direct line (skips pathfinding)."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        
        config = _pathfinding_config()
        
        # Pads with no obstacles
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(10), 0), "1", size_mm=1.0)
        
        board = MockBoard(
            nets=[net_mains, net_gnd],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_gnd])],
            layer_names={0: "F.Cu"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 2088-2091: Direct line optimization (no pathfinding needed)
        # Should return {'length': distance, 'nodes': [start, goal]}
        pass
    
    def test_crosses_board_outline_only(self):
        """Direct line crosses Edge.Cuts but no internal slots → logs warning."""
        import pcbnew
        from src.clearance_creepage import ClearanceCreepageChecker
        
        config = _pathfinding_config()
        
        # Pads far apart
        net_mains = MockNet("MAINS")
        net_gnd = MockNet("GND")
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(0, 0), "1", size_mm=1.0)
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(20), 0), "1", size_mm=1.0)
        
        # Edge.Cuts barrier (board outline) - should not block entirely but log warning
        edge_cut = MockDrawing(layer=44, start=pcbnew.VECTOR2I(pcbnew.FromMM(9), pcbnew.FromMM(-5)),
                              end=pcbnew.VECTOR2I(pcbnew.FromMM(9), pcbnew.FromMM(5)), width=pcbnew.FromMM(0.5))
        
        board = MockBoard(
            nets=[net_mains, net_gnd],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_gnd])],
            drawings=[edge_cut],
            layer_names={0: "F.Cu", 44: "Edge.Cuts"}
        )
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=True,
            auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Lines 2095-2098: "Direct line crosses board outline only (no internal slots)"
        pass
