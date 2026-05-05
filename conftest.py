"""
conftest.py — pytest session configuration (project root).

Installs the pcbnew mock into sys.modules before any test module is collected,
ensuring that ``import pcbnew`` in ``signal_integrity.py`` resolves to our stub.
All shared fixtures and helper classes live in ``tests/helpers.py``.
"""

import sys
import types

def _install_pcbnew_mock():
    if "pcbnew" in sys.modules:
        return
    mod = types.ModuleType("pcbnew")
    mod.FromMM = lambda x: int(round(x * 1_000_000))
    mod.ToMM   = lambda x: x / 1_000_000
    # Copper layer constants
    mod.F_Cu   = 0
    mod.In1_Cu = 1
    mod.In2_Cu = 2
    mod.In3_Cu = 3
    mod.In4_Cu = 4
    mod.In5_Cu = 5
    mod.In6_Cu = 6
    mod.In7_Cu = 7
    mod.In8_Cu = 8
    mod.B_Cu   = 31
    mod.VIATYPE_THROUGH = 0
    # Non-copper layer constants
    mod.Edge_Cuts = 44  # Board outline layer
    # User layer constants
    mod.User_1 = 110
    mod.User_2 = 111
    mod.User_3 = 112
    mod.User_4 = 113
    mod.User_Comments = 108
    mod.ERROR_INSIDE = 0  # Curve approximation error location

    class _Stub:
        def __init__(self, *a, **kw): pass
    class PCB_TRACK(_Stub):
        """Base class for tracks."""
        pass
    class PCB_VIA(PCB_TRACK):
        """Via inherits from PCB_TRACK."""
        pass
    class PCB_GROUP(_Stub):
        def SetName(self, *a): pass
        def AddItem(self, *a): pass
    class PCB_SHAPE(_Stub):
        def SetShape(self, *a): pass
        def SetStart(self, *a): pass
        def SetEnd(self, *a):   pass
        def SetWidth(self, *a): pass
        def SetLayer(self, *a): pass
    class PCB_TEXT(_Stub):
        def SetText(self, *a): pass
        def SetPosition(self, *a): pass
        def SetLayer(self, *a): pass
        def SetTextSize(self, *a): pass
        def SetTextThickness(self, *a): pass
    class VECTOR2I:
        def __init__(self, x=0, y=0): self.x = x; self.y = y
    
    class SHAPE_POLY_SET:
        """Mock polygon set for clearance calculations."""
        def __init__(self):
            self._outlines = []
            self._current_outline = []
            self._pad_ref = None  # Store reference to pad for distance calculations
        
        def NewOutline(self):
            if self._current_outline:
                self._outlines.append(self._current_outline)
            self._current_outline = []
        
        def Append(self, x, y):
            self._current_outline.append((x, y))
        
        def OutlineCount(self):
            """Return number of outlines."""
            count = len(self._outlines)
            if self._current_outline:
                count += 1
            return count
        
        def Outline(self, index):
            """Return outline at index."""
            if self._current_outline and index == len(self._outlines):
                return _MockOutline(self._current_outline)
            return _MockOutline(self._outlines[index] if index < len(self._outlines) else [])
        
        def CollideEdge(self, point, threshold):
            """Mock collision detection - returns 0."""
            return 0
        
        def Collide(self, other_point):
            """Mock collision - returns false."""
            return False
        
        def BBox(self):
            """Return bounding box of all polygon outlines."""
            # Get all points from all outlines
            all_points = []
            for outline in self._outlines:
                all_points.extend(outline)
            if self._current_outline:
                all_points.extend(self._current_outline)
            
            if not all_points:
                # Empty polygon, return zero-size box
                class _MockBox:
                    def GetLeft(self): return 0
                    def GetTop(self): return 0
                    def GetRight(self): return 0
                    def GetBottom(self): return 0
                    def GetWidth(self): return 0
                    def GetHeight(self): return 0
                return _MockBox()
            
            # Find min/max coordinates
            xs = [p[0] for p in all_points]
            ys = [p[1] for p in all_points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            # Return mock bounding box
            class _MockBox:
                def __init__(self, x1, y1, x2, y2):
                    self.x1 = x1
                    self.y1 = y1
                    self.x2 = x2
                    self.y2 = y2
                def GetLeft(self): return self.x1
                def GetTop(self): return self.y1
                def GetRight(self): return self.x2
                def GetBottom(self): return self.y2
                def GetWidth(self): return abs(self.x2 - self.x1)
                def GetHeight(self): return abs(self.y2 - self.y1)
            
            return _MockBox(min_x, min_y, max_x, max_y)
    
    class _MockOutline:
        """Mock polygon outline for SHAPE_POLY_SET."""
        def __init__(self, points):
            self._points = points
        
        def PointCount(self):
            return len(self._points)
        
        def CPoint(self, index):
            """Return point at index as VECTOR2I."""
            if index < len(self._points):
                x, y = self._points[index]
                return VECTOR2I(x, y)
            return VECTOR2I(0, 0)

    mod.BOARD      = _Stub
    mod.PCB_TRACK  = PCB_TRACK
    mod.PCB_VIA    = PCB_VIA
    mod.PCB_GROUP  = PCB_GROUP
    mod.PCB_SHAPE  = PCB_SHAPE
    mod.PCB_TEXT   = PCB_TEXT
    mod.VECTOR2I   = VECTOR2I
    mod.SHAPE_POLY_SET = SHAPE_POLY_SET
    mod.SHAPE_T_SEGMENT = 0
    sys.modules["pcbnew"] = mod

_install_pcbnew_mock()
