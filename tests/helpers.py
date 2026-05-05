"""
Shared helper utilities for EMC Auditor unit tests.

The pcbnew mock is installed by the root ``conftest.py`` before pytest collects
any test file.  This module only provides helper classes and factory functions.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Minimal pcbnew stub definition (also used by root conftest.py)
# ---------------------------------------------------------------------------
def _make_pcbnew_mock():
    """Return a minimal stub of the pcbnew KiCad module (used by conftest.py)."""
    import types
    mod = types.ModuleType("pcbnew")
    mod.FromMM = lambda x: int(round(x * 1_000_000))
    mod.ToMM   = lambda x: x / 1_000_000
    mod.F_Cu   = 0
    mod.B_Cu   = 31
    mod.In1_Cu = 1
    mod.In2_Cu = 2
    mod.VIATYPE_THROUGH = 0

    class _Stub:
        def __init__(self, *a, **kw): pass
    class PCB_GROUP(_Stub):
        def SetName(self, *a): pass
        def AddItem(self, *a): pass
    class PCB_SHAPE(_Stub):
        def SetShape(self, *a): pass
        def SetStart(self, *a): pass
        def SetEnd(self, *a):   pass
        def SetWidth(self, *a): pass
        def SetLayer(self, *a): pass
    class VECTOR2I:
        def __init__(self, x=0, y=0): self.x = x; self.y = y

    # Base classes for isinstance checks
    class PCB_TRACK(_Stub):
        """Base class for tracks and vias."""
        pass
    
    class PCB_VIA(PCB_TRACK):
        """Via class - inherits from PCB_TRACK for isinstance checks."""
        pass

    mod.BOARD      = _Stub
    mod.PCB_TRACK  = PCB_TRACK
    mod.PCB_VIA    = PCB_VIA
    mod.PCB_GROUP  = PCB_GROUP
    mod.PCB_SHAPE  = PCB_SHAPE
    mod.VECTOR2I   = VECTOR2I
    mod.SHAPE_T_SEGMENT = 0
    return mod


# ---------------------------------------------------------------------------
# Helpers & shared fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class MockNet:
    """Minimal pcbnew.NETINFO_ITEM stub."""

    def __init__(self, name: str, net_class: str = "Default"):
        self._name = name
        self._class = net_class

    def GetNetname(self) -> str:
        return self._name

    def GetNetClassName(self) -> str:
        return self._class


class MockNetInfo:
    """Minimal NetInfo container stub."""

    def __init__(self, nets: list):
        self._nets = nets
        self._by_name = {n.GetNetname(): n for n in nets}

    def GetNetCount(self) -> int:
        return len(self._nets)

    def GetNetItem(self, code: int):
        try:
            return self._nets[code]
        except IndexError:
            return None

    def NetsByName(self):
        return self._by_name
    
    def values(self):
        """Allow iteration over all nets (for clearance/creepage domain scanning)."""
        return self._nets


class MockBoard:
    """
    Minimal pcbnew.BOARD stub for unit-testing checker logic.

    Pass ``board_file`` to simulate GetFileName() returning a real fixture path.
    Pass ``nets`` (list of MockNet) to populate the net class map.
    Pass ``layer_names`` (dict {layer_id: name}) to simulate GetLayerName().
    Pass ``tracks`` (list of MockTrack) to simulate GetTracks().
    Pass ``zones`` (list of MockZone) to simulate Zones().
    Pass ``footprints`` (list of MockFootprint) to simulate GetFootprints().
    """

    def __init__(
        self,
        board_file: str = "",
        nets: list = None,
        layer_names: dict = None,
        tracks: list = None,
        zones: list = None,
        footprints: list = None,
        copper_layer_count: int = 4,
        board_bbox = None,
        drawings: list = None,
    ):
        self._file = board_file
        self._nets = nets or []
        self._layer_names = layer_names or {0: "F.Cu", 31: "B.Cu"}
        self._tracks = tracks or []
        self._zones = zones or []
        self._footprints = footprints or []
        self._copper_layer_count = copper_layer_count
        self._drawings = drawings or []
        # Default board bounding box: 100mm x 100mm
        import pcbnew
        self._board_bbox = board_bbox or MockBoundingBox(
            pcbnew.FromMM(0), pcbnew.FromMM(0), 
            pcbnew.FromMM(100), pcbnew.FromMM(100)
        )

    def GetFileName(self) -> str:
        return self._file

    def GetNetInfo(self) -> MockNetInfo:
        return MockNetInfo(self._nets)

    def GetLayerName(self, layer_id: int) -> str:
        return self._layer_names.get(layer_id, f"In{layer_id}.Cu")

    def GetLayerID(self, name: str) -> int:
        for lid, lname in self._layer_names.items():
            if lname == name:
                return lid
        return -1

    def IsLayerEnabled(self, layer_id: int) -> bool:
        return layer_id in self._layer_names

    def GetCopperLayerCount(self) -> int:
        return self._copper_layer_count

    def GetTracks(self):
        return self._tracks

    def GetZones(self):
        return self._zones

    def Zones(self):
        return self._zones

    def GetFootprints(self):
        return self._footprints
    
    def GetPads(self):
        """Return all pads from all footprints."""
        pads = []
        for fp in self._footprints:
            pads.extend(fp.Pads())
        return pads
    
    def GetDrawings(self):
        """Return graphical drawings (lines, arcs, polygons, etc.)."""
        return self._drawings
    
    def GetBoardEdgesBoundingBox(self):
        """Return bounding box of board edges."""
        return self._board_bbox


class MockBoundingBox:
    """Minimal pcbnew.BOX2I stub."""
    
    def __init__(self, x1, y1, x2, y2):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
    
    def GetWidth(self):
        return abs(self.x2 - self.x1)
    
    def GetHeight(self):
        return abs(self.y2 - self.y1)
    
    def GetLeft(self):
        return min(self.x1, self.x2)
    
    def GetTop(self):
        return min(self.y1, self.y2)
    
    def GetRight(self):
        return max(self.x1, self.x2)
    
    def GetBottom(self):
        return max(self.y1, self.y2)
    
    def GetX(self):
        return self.GetLeft()
    
    def GetY(self):
        return self.GetTop()


class MockZone:
    """
    Minimal pcbnew.ZONE stub for ground plane testing.
    
    Args:
        net_name: Net name (e.g., "GND", "VCC")
        layer: Layer ID (e.g., 0=F.Cu, 31=B.Cu)
        filled: Whether zone is filled (must be True for HitTestFilledArea)
        coverage_rects: List of tuples (x1, y1, x2, y2) defining filled areas in internal units
        bbox: Optional bounding box, auto-calculated from coverage_rects if None
    """
    
    def __init__(self, net_name: str, layer: int, filled: bool = True, 
                 coverage_rects: list = None, bbox: MockBoundingBox = None):
        self._net_name = net_name
        self._layer = layer
        self._filled = filled
        self._coverage_rects = coverage_rects or []
        self._bbox = bbox
        
        # Auto-calculate bounding box if not provided
        if self._bbox is None and self._coverage_rects:
            all_x = [x for rect in self._coverage_rects for x in (rect[0], rect[2])]
            all_y = [y for rect in self._coverage_rects for y in (rect[1], rect[3])]
            self._bbox = MockBoundingBox(min(all_x), min(all_y), max(all_x), max(all_y))
        elif self._bbox is None:
            # Default 10mm x 10mm zone
            import pcbnew
            self._bbox = MockBoundingBox(0, 0, pcbnew.FromMM(10), pcbnew.FromMM(10))
    
    def GetNetname(self) -> str:
        return self._net_name
    
    def GetLayer(self) -> int:
        return self._layer
    
    def IsFilled(self) -> bool:
        return self._filled
    
    def GetBoundingBox(self) -> MockBoundingBox:
        return self._bbox
    
    def GetFilledArea(self) -> int:
        """
        Return the filled area in internal units squared.
        Calculates sum of all coverage rectangles.
        """
        total_area = 0
        for rect in self._coverage_rects:
            x1, y1, x2, y2 = rect
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            total_area += width * height
        return total_area
    
    def HitTestFilledArea(self, layer: int, pos) -> bool:
        """
        Check if a point is inside the filled zone.
        
        Args:
            layer: Layer ID to check
            pos: VECTOR2I position
        
        Returns:
            True if point is inside filled zone on specified layer
        """
        # Must be filled and on correct layer
        if not self._filled or layer != self._layer:
            return False
        
        # Check if point is inside any coverage rectangle
        for x1, y1, x2, y2 in self._coverage_rects:
            if x1 <= pos.x <= x2 and y1 <= pos.y <= y2:
                return True
        
        return False


class MockTrack:
    """
    Minimal pcbnew.PCB_TRACK stub.
    
    Args:
        net_name: Net name (e.g., "CLK", "USB_D+")
        start: VECTOR2I start position
        end: VECTOR2I end position
        layer: Layer ID
        net_class: Net class name (e.g., "HighSpeed", "Default")
        width: Track width in internal units
    
    The __class__ attribute is set dynamically to pcbnew.PCB_TRACK in __init__
    to make isinstance(obj, pcbnew.PCB_TRACK) checks work correctly.
    """
    
    def __init__(self, net_name: str, start, end, layer: int = 0,
                 net_class: str = "Default", width: int = None):
        self._net_name = net_name
        self._start = start
        self._end = end
        self._layer = layer
        self._net_class = net_class
        # Import pcbnew here, not at module level
        import pcbnew
        self._width = width or pcbnew.FromMM(0.2)  # Default 0.2mm
        
        # Dynamically inherit from pcbnew.PCB_TRACK for isinstance checks
        # This must be done per-instance after pcbnew is imported
        if not isinstance(self, pcbnew.PCB_TRACK):
            # Create a new class that inherits from both
            self.__class__ = type('MockTrack', (pcbnew.PCB_TRACK, MockTrack), {})
    
    def GetNetname(self) -> str:
        return self._net_name
    
    def GetNetClassName(self) -> str:
        return self._net_class
    
    def GetStart(self):
        return self._start
    
    def GetEnd(self):
        return self._end
    
    def GetPosition(self):
        """Return track center position."""
        import pcbnew
        center_x = (self._start.x + self._end.x) // 2
        center_y = (self._start.y + self._end.y) // 2
        return pcbnew.VECTOR2I(center_x, center_y)
    
    def GetLayer(self) -> int:
        return self._layer
    
    def GetWidth(self) -> int:
        return self._width


class MockVia:
    """
    Minimal pcbnew.PCB_VIA stub.
    
    Args:
        net_name: Net name (e.g., "GND", "CLK")
        position: VECTOR2I position
        drill_diameter: Via drill diameter in mm (default 0.3mm)
        net_class: Net class name (e.g., "Default", "HighSpeed") - optional
    
    The __class__ attribute is set dynamically to pcbnew.PCB_VIA in __init__
    to make isinstance(obj, pcbnew.PCB_VIA) checks work correctly.
    """
    
    def __init__(self, net_name: str, position, drill_diameter: float = 0.3, net_class: str = "Default"):
        self._net_name = net_name
        self._position = position
        self._net_class = net_class
        self._layer = 0  # Vias span all layers, but we can return F.Cu as default
        # Import pcbnew here after conftest has mocked it
        import pcbnew
        self._drill = pcbnew.FromMM(drill_diameter)
        
        # Dynamically inherit from pcbnew.PCB_VIA for isinstance checks
        # This must be done per-instance after pcbnew is imported
        if not isinstance(self, pcbnew.PCB_VIA):
            # Create a new class that inherits from both
            self.__class__ = type('MockVia', (pcbnew.PCB_VIA, MockVia), {})
    
    def GetNetname(self) -> str:
        return self._net_name
    
    def GetNetClassName(self) -> str:
        return self._net_class
    
    def GetPosition(self):
        return self._position
    
    def GetStart(self):
        """Vias have no start/end - both return the via position."""
        return self._position
    
    def GetEnd(self):
        """Vias have no start/end - both return the via position."""
        return self._position
    
    def GetLayer(self) -> int:
        """Return layer (vias span all layers, but return F.Cu as default)."""
        return self._layer
    
    def GetDrill(self) -> int:
        return self._drill


class MockPad:
    """
    Minimal pcbnew.PAD stub.
    
    Args:
        net_name: Net name (e.g., "GND", "VCC")
        position: VECTOR2I position
        number: Pad number (e.g., "1", "2")
        size_mm: Pad size in mm (for bounding box), default 1.0mm
    """
    
    def __init__(self, net_name: str, position, number: str = "1", size_mm: float = 1.0):
        self._net_name = net_name
        self._position = position
        self._number = number
        self._size_mm = size_mm
        self._net = MockNet(net_name)  # Create MockNet for GetNet()
        self._layer = 0  # Default to F.Cu (layer 0)
    
    def GetNetname(self) -> str:
        return self._net_name
    
    def GetPosition(self):
        return self._position
    
    def GetNumber(self) -> str:
        return self._number
    
    def GetNet(self):
        """Return MockNet for this pad (needed for clearance/creepage checks)."""
        return self._net
    
    def GetBoundingBox(self):
        """Return bounding box for obstacle geometry (clearance/creepage pathfinding)."""
        import pcbnew
        half_size = pcbnew.FromMM(self._size_mm / 2.0)
        return MockBoundingBox(
            self._position.x - half_size,  # x1 (left)
            self._position.y - half_size,  # y1 (top)
            self._position.x + half_size,  # x2 (right)
            self._position.y + half_size   # y2 (bottom)
        )
    
    def GetSize(self):
        """Return pad size as VECTOR2I (width, height) in internal units."""
        import pcbnew
        size_internal = pcbnew.FromMM(self._size_mm)
        return pcbnew.VECTOR2I(size_internal, size_internal)
    
    def GetLayer(self):
        """Return layer (0 = F.Cu)."""
        return self._layer
    
    def IsOnLayer(self, layer):
        """Check if pad is on specified layer."""
        return self._layer == layer
    
    def GetShapePolygonSet(self, layer):
        """Return polygon shape for clearance calculation (simplified to bounding box)."""
        # For simplicity, return empty polygon set - clearance check will use bounding box
        import pcbnew
        ps = pcbnew.SHAPE_POLY_SET()
        # Add bounding box as simple rectangle
        bbox = self.GetBoundingBox()
        ps.NewOutline()
        ps.Append(bbox.GetLeft(), bbox.GetTop())
        ps.Append(bbox.GetRight(), bbox.GetTop())
        ps.Append(bbox.GetRight(), bbox.GetBottom())
        ps.Append(bbox.GetLeft(), bbox.GetBottom())
        ps._pad_ref = self  # Store reference for distance calculations
        return ps
    
    def TransformShapeToPolygon(self, poly_set, layer, clearance, max_error, error_loc):
        """Transform pad shape to polygon (called by clearance checker)."""
        # Add bounding box rectangle to the polygon set
        bbox = self.GetBoundingBox()
        poly_set.NewOutline()
        poly_set.Append(bbox.GetLeft(), bbox.GetTop())
        poly_set.Append(bbox.GetRight(), bbox.GetTop())
        poly_set.Append(bbox.GetRight(), bbox.GetBottom())
        poly_set.Append(bbox.GetLeft(), bbox.GetBottom())
        poly_set._pad_ref = self  # Store reference for distance calculations


class MockFootprint:
    """
    Minimal pcbnew.FOOTPRINT stub.
    
    Args:
        reference: Reference designator (e.g., "U1", "C1")
        pads: List of MockPad objects
        position: VECTOR2I position
    """
    
    def __init__(self, reference: str, pads: list = None, position=None):
        self._reference = reference
        self._pads = pads or []
        import pcbnew
        self._position = position or pcbnew.VECTOR2I(0, 0)
    
    def GetReference(self) -> str:
        return self._reference
    
    def Pads(self):
        return self._pads
    
    def GraphicalItems(self):
        """Return graphical items on the footprint (empty list for testing)."""
        return []
    
    def GetPosition(self):
        return self._position


def make_si_checker(board=None, config=None):
    """Factory: create a SignalIntegrityChecker with minimal wiring."""
    # Use importlib to load from the explicit src/ path, bypassing any
    # tests/signal_integrity/ package that would otherwise shadow it.
    import importlib.util
    _src = Path(__file__).parent.parent / "src" / "signal_integrity.py"
    spec = importlib.util.spec_from_file_location("signal_integrity", _src)
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)
    SignalIntegrityChecker = _mod.SignalIntegrityChecker

    _board  = board  or MockBoard()
    _config = config or {}
    _report = []

    checker = SignalIntegrityChecker(
        board=_board,
        marker_layer=44,   # User.Comments layer
        config=_config,
        report_lines=_report,
        verbose=False,
        auditor=None,
    )
    # Wire a no-op log so methods that call self.log() don't crash
    checker.log = lambda msg, force=False: None
    return checker
