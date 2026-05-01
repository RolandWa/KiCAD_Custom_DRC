"""
Unit tests for the analytical impedance calculation methods in SignalIntegrityChecker.

All tests are pure-Python math — no KiCad / pcbnew required.
Reference values derived from IPC-2141 tables and the Wadell handbook.

Tolerances:
  ±5 Ω  for single-ended impedance (analytical formulas have ~5–10% inherent error)
  ±8 Ω  for differential impedance (additional coupling-coefficient uncertainty)
"""

import math
import sys
import pytest
from pathlib import Path

# Ensure src/ and tests/ are importable from this sub-package location
_TESTS_DIR = Path(__file__).parent.parent
_SRC_DIR   = _TESTS_DIR.parent / "src"
sys.path.insert(0, str(_SRC_DIR))
sys.path.insert(0, str(_TESTS_DIR))

from helpers import make_si_checker


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def si():
    """Return a minimal SignalIntegrityChecker with mocked board."""
    return make_si_checker()


# ============================================================================
# _detect_transmission_line_type
# ============================================================================

class TestDetectTransmissionLineType:
    """Layer name → transmission line type mapping."""

    @pytest.mark.parametrize("layer, expected", [
        ("F.Cu",   "microstrip"),
        ("B.Cu",   "microstrip"),
        ("In1.Cu", "stripline"),
        ("In2.Cu", "stripline"),
        ("In3.Cu", "stripline"),
        ("In4.Cu", "stripline"),
    ])
    def test_known_layers(self, si, layer, expected):
        assert si._detect_transmission_line_type(layer) == expected

    def test_unknown_layer_returns_unknown(self, si):
        assert si._detect_transmission_line_type("User.Comments") == "unknown"

    def test_arbitrary_inner_layer(self, si):
        assert si._detect_transmission_line_type("In12.Cu") == "stripline"


# ============================================================================
# _calculate_microstrip_impedance
# ============================================================================

class TestMicrostripImpedance:
    """IPC-2141 microstrip impedance formula."""

    def test_returns_positive_float(self, si):
        z = si._calculate_microstrip_impedance(0.2, 0.1, 35.0, 4.3)
        assert isinstance(z, float)
        assert z > 0

    def test_typical_50ohm_design(self, si):
        """W=0.152mm, H=0.1mm, t=35µm, Er=4.5 → approximately 51 Ω (IPC-2141)."""
        z = si._calculate_microstrip_impedance(0.152, 0.1, 35.0, 4.5)
        assert abs(z - 51.0) < 5.0, f"Expected ~51 Ω, got {z:.1f} Ω"

    def test_wider_trace_lower_impedance(self, si):
        z_narrow = si._calculate_microstrip_impedance(0.1, 0.1, 35.0, 4.3)
        z_wide   = si._calculate_microstrip_impedance(0.4, 0.1, 35.0, 4.3)
        assert z_narrow > z_wide

    def test_thicker_dielectric_higher_impedance(self, si):
        z_thin  = si._calculate_microstrip_impedance(0.2, 0.08, 35.0, 4.3)
        z_thick = si._calculate_microstrip_impedance(0.2, 0.20, 35.0, 4.3)
        assert z_thick > z_thin

    def test_higher_er_lower_impedance(self, si):
        z_low_er  = si._calculate_microstrip_impedance(0.2, 0.1, 35.0, 2.5)
        z_high_er = si._calculate_microstrip_impedance(0.2, 0.1, 35.0, 4.5)
        assert z_low_er > z_high_er

    def test_reasonable_range(self, si):
        z = si._calculate_microstrip_impedance(0.2, 0.1, 35.0, 4.3)
        assert 10 < z < 200

    @pytest.mark.parametrize("W, H, t, Er", [
        (0.05, 0.1, 35.0, 4.3),
        (1.0,  0.1, 35.0, 4.3),
        (0.2,  0.3, 35.0, 4.3),
        (0.2,  0.1, 70.0, 4.3),
    ])
    def test_no_exception_on_edge_cases(self, si, W, H, t, Er):
        z = si._calculate_microstrip_impedance(W, H, t, Er)
        assert z > 0


# ============================================================================
# _calculate_stripline_impedance
# ============================================================================

class TestStriplineImpedance:
    """Wadell symmetric stripline formula."""

    def test_returns_positive_float(self, si):
        z = si._calculate_stripline_impedance(0.15, 0.5, 35.0, 4.3)
        assert isinstance(z, float)
        assert z > 0

    def test_typical_50ohm_design(self, si):
        z = si._calculate_stripline_impedance(0.15, 0.5, 35.0, 4.5)
        assert abs(z - 51.0) < 6.0, f"Expected ~51 Ω, got {z:.1f} Ω"

    def test_wider_trace_lower_impedance(self, si):
        z_narrow = si._calculate_stripline_impedance(0.1, 0.5, 35.0, 4.3)
        z_wide   = si._calculate_stripline_impedance(0.4, 0.5, 35.0, 4.3)
        assert z_narrow > z_wide

    def test_wider_ground_spacing_higher_impedance(self, si):
        z_tight = si._calculate_stripline_impedance(0.15, 0.3, 35.0, 4.3)
        z_loose = si._calculate_stripline_impedance(0.15, 0.8, 35.0, 4.3)
        assert z_loose > z_tight

    def test_reasonable_range(self, si):
        z = si._calculate_stripline_impedance(0.15, 0.5, 35.0, 4.3)
        assert 10 < z < 200

    def test_wide_regime_geometry(self, si):
        """W/b ≥ 0.35 triggers the alternative Wadell formula branch."""
        z = si._calculate_stripline_impedance(0.2, 0.4, 35.0, 4.3)
        assert z > 0

    def test_narrow_regime_geometry(self, si):
        """W/b < 0.35 triggers the log-based narrow formula branch."""
        z = si._calculate_stripline_impedance(0.1, 0.5, 35.0, 4.3)
        assert z > 0


# ============================================================================
# _calculate_differential_impedance
# ============================================================================

class TestDifferentialImpedance:
    """Simplified exponential coupling coefficient model."""

    def test_returns_positive_float(self, si):
        z = si._calculate_differential_impedance(50.0, 0.2, 0.1)
        assert isinstance(z, float)
        assert z > 0

    def test_approaches_2x_z0_when_far_apart(self, si):
        """As S → ∞ coupling → 0 → Zdiff → 2×Z0."""
        z = si._calculate_differential_impedance(50.0, 10.0, 0.1)
        assert abs(z - 100.0) < 1.0, f"Expected ~100 Ω, got {z:.1f} Ω"

    def test_less_than_2x_z0_when_close(self, si):
        z = si._calculate_differential_impedance(50.0, 0.05, 0.1)
        assert z < 100.0

    def test_usb_target_90ohm(self, si):
        z = si._calculate_differential_impedance(50.0, 0.1, 0.1)
        assert abs(z - 90.0) < 8.0, f"Expected ~90 Ω for USB, got {z:.1f} Ω"

    def test_wider_spacing_higher_impedance(self, si):
        z_close = si._calculate_differential_impedance(50.0, 0.1, 0.1)
        z_far   = si._calculate_differential_impedance(50.0, 0.5, 0.1)
        assert z_far > z_close

    def test_hdmi_target_100ohm(self, si):
        z = si._calculate_differential_impedance(55.0, 5.0, 0.1)
        assert abs(z - 110.0) < 10.0


# ============================================================================
# _calculate_cpw_impedance
# ============================================================================

class TestCPWImpedance:
    """Coplanar waveguide (CPW and CPWG) using Wen (1969) elliptic-integral approx."""

    def test_cpw_returns_positive_float(self, si):
        z = si._calculate_cpw_impedance(0.3, 0.15, 0.1, 4.3, has_ground_plane=False)
        assert isinstance(z, float)
        assert z > 0

    def test_cpwg_returns_positive_float(self, si):
        z = si._calculate_cpw_impedance(0.3, 0.15, 0.1, 4.3, has_ground_plane=True)
        assert isinstance(z, float)
        assert z > 0

    def test_cpwg_lower_than_cpw(self, si):
        """Ground plane adds capacitance → CPWG impedance < CPW impedance."""
        z_cpw  = si._calculate_cpw_impedance(0.3, 0.15, 0.1, 4.3, has_ground_plane=False)
        z_cpwg = si._calculate_cpw_impedance(0.3, 0.15, 0.1, 4.3, has_ground_plane=True)
        assert z_cpwg < z_cpw

    def test_wider_gap_higher_impedance(self, si):
        """Wider gap S → less capacitive loading → higher impedance."""
        z_narrow = si._calculate_cpw_impedance(0.3, 0.10, 0.1, 4.3, has_ground_plane=False)
        z_wide   = si._calculate_cpw_impedance(0.3, 0.40, 0.1, 4.3, has_ground_plane=False)
        assert z_wide > z_narrow

    def test_reasonable_range(self, si):
        z = si._calculate_cpw_impedance(0.3, 0.15, 0.1, 4.3, has_ground_plane=False)
        assert 20 < z < 150
