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
    mod.F_Cu   = 0
    mod.B_Cu   = 31
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

    mod.BOARD      = _Stub
    mod.PCB_TRACK  = _Stub
    mod.PCB_VIA    = _Stub
    mod.PCB_GROUP  = PCB_GROUP
    mod.PCB_SHAPE  = PCB_SHAPE
    mod.VECTOR2I   = VECTOR2I
    mod.SHAPE_T_SEGMENT = 0
    sys.modules["pcbnew"] = mod

_install_pcbnew_mock()
