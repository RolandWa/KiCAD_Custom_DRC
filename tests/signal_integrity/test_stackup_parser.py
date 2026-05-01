"""
Unit tests for SignalIntegrityChecker._parse_stackup_from_file()
and the helper methods that consume the parsed stackup dict.

These tests use real .kicad_pcb fixture files (no pcbnew board object needed).
"""

import sys
import pytest
from pathlib import Path

_TESTS_DIR = Path(__file__).parent.parent
_SRC_DIR   = _TESTS_DIR.parent / "src"
sys.path.insert(0, str(_SRC_DIR))
sys.path.insert(0, str(_TESTS_DIR))

from helpers import make_si_checker, FIXTURES_DIR


# ============================================================================
# _parse_stackup_from_file — 4-layer board
# ============================================================================

class TestParseStackup4Layer:

    @pytest.fixture
    def stackup(self):
        si = make_si_checker()
        return si._parse_stackup_from_file(str(FIXTURES_DIR / "simple_4layer.kicad_pcb"))

    def test_returns_dict(self, stackup):
        assert isinstance(stackup, dict)

    def test_has_layers_key(self, stackup):
        assert "layers" in stackup
        assert len(stackup["layers"]) > 0

    def test_copper_layer_count(self, stackup):
        copper = [l for l in stackup["layers"] if l["type"] == "copper"]
        assert len(copper) == 4

    def test_dielectric_layer_count(self, stackup):
        dielectric = [l for l in stackup["layers"] if l["type"] == "dielectric"]
        assert len(dielectric) == 3

    def test_copper_names_present(self, stackup):
        names = {l["name"] for l in stackup["layers"] if l["type"] == "copper"}
        assert {"F.Cu", "B.Cu", "In1.Cu", "In2.Cu"} <= names

    def test_dielectric_has_epsilon_r(self, stackup):
        for d in [l for l in stackup["layers"] if l["type"] == "dielectric"]:
            assert "epsilon_r" in d
            assert isinstance(d["epsilon_r"], float)
            assert 2.0 < d["epsilon_r"] < 12.0

    def test_copper_thickness_nonzero(self, stackup):
        for c in [l for l in stackup["layers"] if l["type"] == "copper"]:
            assert c["thickness_um"] > 0

    def test_finish_enig(self, stackup):
        assert stackup.get("finish") == "ENIG"

    def test_total_thickness_positive(self, stackup):
        assert stackup.get("total_thickness_mm", 0) > 0


# ============================================================================
# _parse_stackup_from_file — 2-layer board
# ============================================================================

class TestParseStackup2Layer:

    @pytest.fixture
    def stackup(self):
        si = make_si_checker()
        return si._parse_stackup_from_file(str(FIXTURES_DIR / "simple_2layer.kicad_pcb"))

    def test_copper_layer_count(self, stackup):
        copper = [l for l in stackup["layers"] if l["type"] == "copper"]
        assert len(copper) == 2

    def test_finish_hasl(self, stackup):
        assert stackup.get("finish") == "HASL"


# ============================================================================
# _parse_stackup_from_file — missing file
# ============================================================================

class TestParseStackupMissingFile:

    def test_returns_none_on_missing_file(self):
        si = make_si_checker()
        assert si._parse_stackup_from_file("/nonexistent/path.kicad_pcb") is None


# ============================================================================
# _get_layer_dielectric_constant
# ============================================================================

class TestGetLayerDielectricConstant:

    @pytest.fixture
    def si_with_stackup(self):
        si = make_si_checker()
        si._stackup = si._parse_stackup_from_file(str(FIXTURES_DIR / "simple_4layer.kicad_pcb"))
        return si

    def test_returns_float(self, si_with_stackup):
        er = si_with_stackup._get_layer_dielectric_constant(0, si_with_stackup._stackup)
        assert isinstance(er, float)

    def test_default_when_no_stackup(self):
        er = make_si_checker()._get_layer_dielectric_constant(0, None)
        assert er == pytest.approx(4.3)

    def test_reasonable_value_for_fr4(self, si_with_stackup):
        er = si_with_stackup._get_layer_dielectric_constant(0, si_with_stackup._stackup)
        assert 3.5 < er < 5.5


# ============================================================================
# _get_layer_copper_thickness
# ============================================================================

class TestGetLayerCopperThickness:

    def test_default_when_no_stackup(self):
        t = make_si_checker()._get_layer_copper_thickness(0, None)
        assert t == pytest.approx(35.0)

    def test_returns_positive_value(self):
        si = make_si_checker()
        stackup = si._parse_stackup_from_file(str(FIXTURES_DIR / "simple_4layer.kicad_pcb"))
        assert si._get_layer_copper_thickness(0, stackup) > 0


# ============================================================================
# _get_dielectric_height_to_plane
# ============================================================================

class TestGetDielectricHeightToPlane:

    def test_default_when_no_stackup(self):
        h = make_si_checker()._get_dielectric_height_to_plane(0, None)
        assert h == pytest.approx(0.2)

    def test_returns_positive_for_valid_stackup(self):
        si = make_si_checker()
        stackup = si._parse_stackup_from_file(str(FIXTURES_DIR / "simple_4layer.kicad_pcb"))
        h = si._get_dielectric_height_to_plane(0, stackup)
        assert h is not None
        assert h > 0

    def test_height_matches_prepreg_thickness(self):
        """F.Cu on 4-layer board has 0.1 mm prepreg to In1.Cu."""
        si = make_si_checker()
        stackup = si._parse_stackup_from_file(str(FIXTURES_DIR / "simple_4layer.kicad_pcb"))
        h = si._get_dielectric_height_to_plane(0, stackup)
        assert abs(h - 0.1) < 0.01
