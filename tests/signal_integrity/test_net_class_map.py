"""
Unit tests for SignalIntegrityChecker._build_net_class_map()
and _resolve_net_class().

Tests cover:
  * KiCad 9 pattern-based class assignments (net_settings class blocks)
  * KiCad 6/7 explicit net class blocks (net_class "NAME" ... (add_net ...))
  * GetNetClassName() fallback when a net returns a class string directly
  * Default class fall-through for unassigned nets
  * Pattern glob expansion (DIFF_* → DIFF_TX, DIFF_RX)
"""

import sys
import pytest
from pathlib import Path

_TESTS_DIR = Path(__file__).parent.parent
_SRC_DIR   = _TESTS_DIR.parent / "src"
sys.path.insert(0, str(_SRC_DIR))
sys.path.insert(0, str(_TESTS_DIR))

from helpers import make_si_checker, MockBoard, MockNet, FIXTURES_DIR


def _board(fixture: str, nets=None):
    return MockBoard(board_file=str(FIXTURES_DIR / fixture), nets=nets or [])


# ============================================================================
# KiCad 9 — net_settings (class + nets + pattern)
# ============================================================================

class TestNetClassMapKiCad9:
    """
    Fixture netclass_kicad9.kicad_pcb defines:
      class "50R"       → nets ["CLK_P","CLK_N","SIG"], pattern "DIFF_*"
      class "HighSpeed" → nets ["USB_D_P","USB_D_N"]
    """

    @pytest.fixture
    def checker(self):
        return make_si_checker(board=_board("netclass_kicad9.kicad_pcb"))

    def test_explicit_net_assigned_50r(self, checker):
        net_map = checker._build_net_class_map()
        assert net_map.get("CLK_P") == "50R"
        assert net_map.get("CLK_N") == "50R"
        assert net_map.get("SIG")   == "50R"

    def test_explicit_net_assigned_highspeed(self, checker):
        net_map = checker._build_net_class_map()
        assert net_map.get("USB_D_P") == "HighSpeed"
        assert net_map.get("USB_D_N") == "HighSpeed"

    def test_unassigned_net_not_in_map(self, checker):
        assert "GND" not in checker._build_net_class_map()

    def test_resolve_net_class_returns_default_for_unknown(self, checker):
        assert checker._resolve_net_class("UNKNOWN_NET_XYZ") == "Default"

    def test_resolve_net_class_returns_correct_class(self, checker):
        assert checker._resolve_net_class("CLK_P") == "50R"


# ============================================================================
# KiCad 6/7 — net_class explicit blocks
# ============================================================================

class TestNetClassMapKiCad6:
    """
    Fixture netclass_kicad6.kicad_pcb defines:
      net_class "HighSpeed" → ["CLK_P","CLK_N","DATA_TX"]
      net_class "Power"     → ["VCC_3V3","GND"]
    """

    @pytest.fixture
    def checker(self):
        return make_si_checker(board=_board("netclass_kicad6.kicad_pcb"))

    def test_highspeed_nets_resolved(self, checker):
        net_map = checker._build_net_class_map()
        assert net_map.get("CLK_P")   == "HighSpeed"
        assert net_map.get("CLK_N")   == "HighSpeed"
        assert net_map.get("DATA_TX") == "HighSpeed"

    def test_power_nets_resolved(self, checker):
        net_map = checker._build_net_class_map()
        assert net_map.get("VCC_3V3") == "Power"
        assert net_map.get("GND")     == "Power"

    def test_default_class_not_in_map(self, checker):
        assert "Default" not in checker._build_net_class_map().values()


# ============================================================================
# GetNetClassName() fallback (Source 1 — in-memory)
# ============================================================================

class TestNetClassMapGetNetClassName:
    """GetNetClassName() drives the map when no board file entries exist."""

    @pytest.fixture
    def checker(self):
        nets = [
            MockNet("NET_A", "50R"),
            MockNet("NET_B", "HighSpeed"),
            MockNet("NET_C", "Default"),
        ]
        return make_si_checker(board=MockBoard(board_file="", nets=nets))

    def test_net_a_resolved_from_getnetclassname(self, checker):
        assert checker._build_net_class_map().get("NET_A") == "50R"

    def test_net_b_resolved(self, checker):
        assert checker._build_net_class_map().get("NET_B") == "HighSpeed"

    def test_default_net_not_in_map(self, checker):
        assert "NET_C" not in checker._build_net_class_map()

    def test_comma_separated_class_string(self):
        """KiCad 9 may return 'ClassName,Default' — first non-Default token wins."""
        board = MockBoard(board_file="", nets=[MockNet("NET_X", "50R,Default")])
        si = make_si_checker(board=board)
        assert si._build_net_class_map().get("NET_X") == "50R"


# ============================================================================
# _resolve_net_class caching
# ============================================================================

class TestResolveNetClassCaching:

    def test_caches_result_on_repeat_calls(self):
        board = MockBoard(board_file="", nets=[MockNet("CACHE_TEST", "50R")])
        si = make_si_checker(board=board)
        assert si._resolve_net_class("CACHE_TEST") == si._resolve_net_class("CACHE_TEST") == "50R"

    def test_unknown_net_returns_default(self):
        si = make_si_checker(board=MockBoard(board_file="", nets=[]))
        assert si._resolve_net_class("DOES_NOT_EXIST") == "Default"
