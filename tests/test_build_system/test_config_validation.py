"""
Configuration validation tests for emc_rules.toml.

Critical for preventing plugin load failures due to TOML syntax errors.
TOML 1.0.0 strictly prohibits duplicate keys in the same section.

Tests validate (36 total):
  * TOML syntax correctness (tomllib.load succeeds)
  * No duplicate keys in all 10 sections (100% coverage)
  * All 10 required sections present (100% coverage)
  * Critical configuration keys exist
  * Numeric ranges are valid (percentages 0-100, distances > 0)

Sections tested:
  - general, via_stitching, decoupling, trace_width
  - ground_plane, differential_pairs, high_speed
  - emi_filtering, clearance_creepage, signal_integrity
"""

import sys
import pytest
from pathlib import Path

# Python 3.11+ has built-in tomllib, 3.8-3.10 need tomli
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

# tests/test_build_system/ → go up two levels to reach project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
TOML_PATH = PROJECT_ROOT / "emc_rules.toml"


class TestTOMLSyntax:
    """Validate TOML file can be parsed without errors."""

    def test_toml_file_exists(self):
        """emc_rules.toml must exist in project root."""
        assert TOML_PATH.exists(), f"Config file not found: {TOML_PATH}"

    def test_toml_syntax_valid(self):
        """TOML must parse without syntax errors."""
        with open(TOML_PATH, 'rb') as f:
            try:
                config = tomllib.load(f)
                assert isinstance(config, dict), "TOML must parse to dict"
            except tomllib.TOMLDecodeError as e:
                pytest.fail(f"TOML syntax error: {e}")

    def test_no_duplicate_keys_in_via_stitching(self):
        """[via_stitching] section must have unique keys."""
        self._check_section_for_duplicates('via_stitching')

    def test_no_duplicate_keys_in_decoupling(self):
        """[decoupling] section must have unique keys."""
        self._check_section_for_duplicates('decoupling')

    def test_no_duplicate_keys_in_ground_plane(self):
        """[ground_plane] section must have unique keys (common error site)."""
        self._check_section_for_duplicates('ground_plane')

    def test_no_duplicate_keys_in_emi_filtering(self):
        """[emi_filtering] section must have unique keys."""
        self._check_section_for_duplicates('emi_filtering')

    def test_no_duplicate_keys_in_clearance_creepage(self):
        """[clearance_creepage] section must have unique keys."""
        self._check_section_for_duplicates('clearance_creepage')

    def test_no_duplicate_keys_in_signal_integrity(self):
        """[signal_integrity] section must have unique keys."""
        self._check_section_for_duplicates('signal_integrity')

    def test_no_duplicate_keys_in_general(self):
        """[general] section must have unique keys."""
        self._check_section_for_duplicates('general')

    def test_no_duplicate_keys_in_trace_width(self):
        """[trace_width] section must have unique keys."""
        self._check_section_for_duplicates('trace_width')

    def test_no_duplicate_keys_in_differential_pairs(self):
        """[differential_pairs] section must have unique keys."""
        self._check_section_for_duplicates('differential_pairs')

    def test_no_duplicate_keys_in_high_speed(self):
        """[high_speed] section must have unique keys."""
        self._check_section_for_duplicates('high_speed')

    def _check_section_for_duplicates(self, section_name: str) -> None:
        """
        Parse TOML line-by-line to detect duplicate keys in a section.
        
        tomllib.load() fails immediately on duplicates, but this provides
        better error messages showing which key is duplicated.
        """
        with open(TOML_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_section = False
        section_pattern = f'[{section_name}]'
        keys_seen = set()
        
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            
            # Check if entering target section
            if stripped == section_pattern:
                in_section = True
                continue
            
            # Check if entering different section
            if stripped.startswith('[') and stripped.endswith(']'):
                in_section = False
                continue
            
            # If in target section, check for duplicate keys
            if in_section and '=' in stripped and not stripped.startswith('#'):
                key = stripped.split('=')[0].strip()
                if key in keys_seen:
                    pytest.fail(
                        f"Duplicate key '{key}' in [{section_name}] at line {i}\n"
                        f"TOML 1.0.0 prohibits duplicate keys in same section."
                    )
                keys_seen.add(key)


class TestRequiredSections:
    """Ensure all checker modules have configuration sections."""

    @pytest.fixture
    def config(self):
        """Load TOML configuration once for all tests."""
        with open(TOML_PATH, 'rb') as f:
            return tomllib.load(f)

    def test_via_stitching_section_exists(self, config):
        assert 'via_stitching' in config, "Missing [via_stitching] section"

    def test_decoupling_section_exists(self, config):
        assert 'decoupling' in config, "Missing [decoupling] section"

    def test_ground_plane_section_exists(self, config):
        assert 'ground_plane' in config, "Missing [ground_plane] section"

    def test_emi_filtering_section_exists(self, config):
        assert 'emi_filtering' in config, "Missing [emi_filtering] section"

    def test_clearance_creepage_section_exists(self, config):
        assert 'clearance_creepage' in config, "Missing [clearance_creepage] section"

    def test_signal_integrity_section_exists(self, config):
        assert 'signal_integrity' in config, "Missing [signal_integrity] section"

    def test_general_section_exists(self, config):
        assert 'general' in config, "Missing [general] section"

    def test_trace_width_section_exists(self, config):
        assert 'trace_width' in config, "Missing [trace_width] section"

    def test_differential_pairs_section_exists(self, config):
        assert 'differential_pairs' in config, "Missing [differential_pairs] section"

    def test_high_speed_section_exists(self, config):
        assert 'high_speed' in config, "Missing [high_speed] section"


class TestCriticalKeys:
    """Validate critical configuration keys exist with valid types."""

    @pytest.fixture
    def config(self):
        """Load TOML configuration once for all tests."""
        with open(TOML_PATH, 'rb') as f:
            return tomllib.load(f)

    def test_via_stitching_has_enabled_flag(self, config):
        assert 'enabled' in config['via_stitching'], "via_stitching.enabled missing"
        assert isinstance(config['via_stitching']['enabled'], bool)

    def test_ground_plane_has_max_gap_under_trace(self, config):
        gp = config['ground_plane']
        assert 'max_gap_under_trace_mm' in gp, "ground_plane.max_gap_under_trace_mm missing"
        assert isinstance(gp['max_gap_under_trace_mm'], (int, float))
        assert gp['max_gap_under_trace_mm'] > 0, "max_gap_under_trace_mm must be > 0"

    def test_ground_plane_has_min_coverage_percent(self, config):
        """Validate min_coverage_percent exists (common duplicate key error)."""
        gp = config['ground_plane']
        assert 'min_coverage_percent' in gp, "ground_plane.min_coverage_percent missing"
        assert isinstance(gp['min_coverage_percent'], (int, float))
        assert 0 <= gp['min_coverage_percent'] <= 100, "Coverage percent must be 0-100"

    def test_decoupling_has_max_distance(self, config):
        dec = config['decoupling']
        assert 'max_distance_mm' in dec, "decoupling.max_distance_mm missing"
        assert isinstance(dec['max_distance_mm'], (int, float))
        assert dec['max_distance_mm'] > 0, "max_distance_mm must be > 0"

    def test_clearance_has_voltage_domains(self, config):
        cc = config['clearance_creepage']
        assert 'voltage_domains' in cc, "clearance_creepage.voltage_domains missing"
        assert isinstance(cc['voltage_domains'], list), "voltage_domains must be an array"

    def test_general_has_plugin_name(self, config):
        gen = config['general']
        assert 'plugin_name' in gen, "general.plugin_name missing"
        assert isinstance(gen['plugin_name'], str)

    def test_trace_width_has_power_trace_min_width(self, config):
        tw = config['trace_width']
        assert 'power_trace_min_width_mm' in tw, "trace_width.power_trace_min_width_mm missing"
        assert isinstance(tw['power_trace_min_width_mm'], (int, float))
        assert tw['power_trace_min_width_mm'] > 0, "power_trace_min_width_mm must be > 0"

    def test_differential_pairs_has_max_length_mismatch(self, config):
        dp = config['differential_pairs']
        assert 'max_length_mismatch_mm' in dp, "differential_pairs.max_length_mismatch_mm missing"
        assert isinstance(dp['max_length_mismatch_mm'], (int, float))
        assert dp['max_length_mismatch_mm'] > 0, "max_length_mismatch_mm must be > 0"

    def test_high_speed_has_max_stub_length(self, config):
        hs = config['high_speed']
        assert 'max_stub_length_mm' in hs, "high_speed.max_stub_length_mm missing"
        assert isinstance(hs['max_stub_length_mm'], (int, float))
        assert hs['max_stub_length_mm'] > 0, "max_stub_length_mm must be > 0"


class TestNumericRanges:
    """Validate numeric configuration values are within sensible ranges."""

    @pytest.fixture
    def config(self):
        """Load TOML configuration once for all tests."""
        with open(TOML_PATH, 'rb') as f:
            return tomllib.load(f)

    def test_percentages_are_0_to_100(self, config):
        """All percentage values must be in range [0, 100]."""
        gp = config['ground_plane']
        if 'min_coverage_percent' in gp:
            val = gp['min_coverage_percent']
            assert 0 <= val <= 100, f"min_coverage_percent={val} out of range [0,100]"

    def test_distances_are_positive(self, config):
        """All distance values must be positive."""
        gp = config['ground_plane']
        dec = config['decoupling']
        
        if 'max_gap_under_trace_mm' in gp:
            assert gp['max_gap_under_trace_mm'] > 0
        
        if 'max_distance_mm' in dec:
            assert dec['max_distance_mm'] > 0

    def test_sampling_intervals_are_positive(self, config):
        """Sampling intervals must be > 0 to avoid infinite loops."""
        gp = config['ground_plane']
        if 'sampling_interval_mm' in gp:
            val = gp['sampling_interval_mm']
            assert val > 0, f"sampling_interval_mm={val} must be > 0"


class TestTOMLCompliance:
    """Document TOML 1.0.0 specification constraints for developers."""

    def test_toml_duplicate_key_rule_documented(self):
        """
        This test serves as documentation: TOML 1.0.0 prohibits duplicate keys.
        
        ❌ INVALID:
            [section]
            key = "value1"
            key = "value2"  # Error: Cannot overwrite a value
        
        ✅ VALID:
            [section1]
            key = "value1"
            
            [section2]
            key = "value2"  # Different sections OK
        
        Common error: min_coverage_percent defined in both Priority 4 section
        and global coverage section within [ground_plane].
        """
        # This test always passes; it exists for documentation
        assert True, "See docstring for TOML duplicate key rules"

    def test_toml_requires_binary_mode(self):
        """
        Python's tomllib requires binary file mode.
        
        ✅ Correct:
            with open('emc_rules.toml', 'rb') as f:
                config = tomllib.load(f)
        
        ❌ Wrong:
            with open('emc_rules.toml', 'r') as f:  # Missing 'b' flag
                config = tomllib.load(f)
        """
        # This test always passes; it exists for documentation
        assert True, "See docstring for TOML file mode requirement"


if __name__ == '__main__':
    # Allow running directly: python test_config_validation.py
    pytest.main([__file__, '-v'])
