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


class MockBoard:
    """
    Minimal pcbnew.BOARD stub for unit-testing checker logic.

    Pass ``board_file`` to simulate GetFileName() returning a real fixture path.
    Pass ``nets`` (list of MockNet) to populate the net class map.
    Pass ``layer_names`` (dict {layer_id: name}) to simulate GetLayerName().
    """

    def __init__(
        self,
        board_file: str = "",
        nets: list = None,
        layer_names: dict = None,
    ):
        self._file = board_file
        self._nets = nets or []
        self._layer_names = layer_names or {0: "F.Cu", 31: "B.Cu"}

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

    def GetTracks(self):
        return []

    def GetZones(self):
        return []

    def Zones(self):
        return []


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
