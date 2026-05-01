"""
TODO placeholders for decoupling.py.

Covers decoupling capacitor proximity checks per IPC-2221:
each power-pin pad on an IC must have a sufficiently close bypass cap
of appropriate value.
"""

import pytest


class TestCapacitorProximity:
    """Each IC power pin must have a capacitor within max_dist_mm."""

    @pytest.mark.skip(reason="TODO: IC with no capacitor within max_dist_mm — assert violation marker drawn")
    def test_ic_without_nearby_cap_flagged(self):
        pass

    @pytest.mark.skip(reason="TODO: capacitor within distance and correct value range — assert no violation")
    def test_cap_within_distance_no_violation(self):
        pass

    @pytest.mark.skip(reason="TODO: two ICs sharing one cap that is within range of both — assert no duplicate violations")
    def test_shared_cap_not_double_flagged(self):
        pass

    @pytest.mark.skip(reason="TODO: check disabled via config key decoupling.enabled — assert 0 violations")
    def test_disabled_in_config_returns_zero(self):
        pass


class TestCapacitorValue:
    """Capacitor component value must fall within the configured acceptable range."""

    @pytest.mark.skip(reason="TODO: capacitor with value outside [min_cap_nf, max_cap_nf] range — assert violation")
    def test_cap_wrong_value_flagged(self):
        pass

    @pytest.mark.skip(reason="TODO: capacitor value within range — assert no value violation")
    def test_cap_correct_value_no_violation(self):
        pass


class TestMultipleSupplyPins:
    """ICs with multiple VCC pins require one cap per pin."""

    @pytest.mark.skip(reason="TODO: IC with 2 VCC pins, only 1 cap provided — assert violation on unserved pin")
    def test_second_supply_pin_without_cap_flagged(self):
        pass

    @pytest.mark.skip(reason="TODO: IC with 2 VCC pins, 2 caps provided — assert no violation")
    def test_all_supply_pins_served_no_violation(self):
        pass


class TestCapacitorNetConnection:
    """Cap must be connected to the same VCC net as the IC supply pin."""

    @pytest.mark.skip(reason="TODO: cap connected to VCC_5V but IC pin is VCC_3V3 — assert violation (wrong net)")
    def test_cap_on_wrong_net_flagged(self):
        pass
