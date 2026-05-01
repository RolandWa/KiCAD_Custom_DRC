"""
TODO placeholders for clearance_creepage.py.

Covers IEC 60664-1 / IPC-2221 clearance and creepage distance checks between
pads, tracks, and board edges at different voltage potentials.
"""

import pytest


class TestClearanceViolations:
    """Electrical clearance (shortest air path) between conductors."""

    @pytest.mark.skip(reason="TODO: mock two pads at different potentials, distance < IEC table threshold — assert violation drawn")
    def test_clearance_violation_flagged(self):
        pass

    @pytest.mark.skip(reason="TODO: pads at exactly minimum IEC clearance distance — assert no violation")
    def test_pads_at_minimum_clearance_no_violation(self):
        pass

    @pytest.mark.skip(reason="TODO: track-to-board-edge clearance below minimum — assert violation")
    def test_track_near_board_edge_flagged(self):
        pass

    @pytest.mark.skip(reason="TODO: check disabled via config key clearance_creepage.enabled — assert 0 violations")
    def test_disabled_in_config_returns_zero(self):
        pass


class TestCreepageViolations:
    """Creepage (surface path) distance checks."""

    @pytest.mark.skip(reason="TODO: creepage path shorter than IEC 60664-1 table value — assert violation")
    def test_creepage_violation_flagged(self):
        pass

    @pytest.mark.skip(reason="TODO: pads with sufficient creepage path — assert no violation")
    def test_adequate_creepage_no_violation(self):
        pass


class TestPollutionDegree:
    """Pollution degree selection affects the required clearance threshold."""

    @pytest.mark.skip(reason="TODO: configure pollution_degree=2 vs 3 — assert different distance thresholds applied")
    def test_pollution_degree_2_vs_3_threshold(self):
        pass


class TestVoltageCategoryTableLookup:
    """CAT I / II / III / IV over-voltage categories drive IEC table selection."""

    @pytest.mark.skip(reason="TODO: set voltage_category=CAT_II, verify correct row selected from IEC 60664-1 table")
    def test_cat_ii_table_selection(self):
        pass

    @pytest.mark.skip(reason="TODO: set voltage_category=CAT_III, verify stricter values used")
    def test_cat_iii_stricter_than_cat_ii(self):
        pass


class TestMixedVoltageNets:
    """Board with multiple voltage domains — only cross-domain pairs are checked."""

    @pytest.mark.skip(reason="TODO: two pads on same voltage domain — assert check is skipped for that pair")
    def test_same_domain_pair_skipped(self):
        pass

    @pytest.mark.skip(reason="TODO: pads on different domains — assert check is performed")
    def test_cross_domain_pair_checked(self):
        pass
