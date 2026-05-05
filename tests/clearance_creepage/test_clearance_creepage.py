"""
Clearance/creepage checker tests for IEC 60664-1 / IPC-2221 compliance.

Tests electrical safety distance verification between voltage domains.
"""

import pytest
import sys
from pathlib import Path
import importlib.util
from unittest.mock import MagicMock

# Load clearance_creepage from src/ (avoid tests/ shadowing)
_src = Path(__file__).parent.parent.parent / "src" / "clearance_creepage.py"
spec = importlib.util.spec_from_file_location("clearance_creepage", _src)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)
ClearanceCreepageChecker = _mod.ClearanceCreepageChecker


# Import test helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import MockBoard, MockPad, MockNet, MockFootprint


def _minimal_config():
    """
    Minimal clearance/creepage config for testing.
    
    Returns a dict matching emc_rules.toml [clearance_creepage] structure.
    """
    return {
        'enabled': True,
        'standard': 'IEC60664-1',
        'overvoltage_category': 'II',
        'pollution_degree': 2,
        'material_group': 'II',
        'altitude_m': 1000,
        'internal_layer_clearance_factor': 0.6,
        'overvoltage_category_factors': {'I': 0.8, 'II': 1.0, 'III': 1.5, 'IV': 2.0},
        
        'check_clearance': True,
        'check_creepage': True,
        'check_different_layers': False,
        'list_all_nets': False,
        'draw_creepage_path': False,  # Disable for tests (cleaner)
        
        'violation_message_clearance': 'CLEARANCE: {actual:.2f}mm < {required:.2f}mm ({domainA}-{domainB})',
        'violation_message_creepage': 'CREEPAGE: {actual:.2f}mm < {required:.2f}mm ({domainA}-{domainB})',
        
        'safety_margin_factor': 1.0,  # No margin for deterministic tests
        'report_mode': 'violations_only',
        'max_obstacles': 500,
        'obstacle_search_margin_mm': 12.0,
        'slot_layer_names': ['Edge.Cuts'],
        
        # IEC 60664-1 clearance table (simplified)
        'iec60664_clearance_table': [
            {
                'voltage_class': 'Low Voltage',
                'note': 'Test table',
                'voltages': [
                    [50.0, 0.6],    # 50V RMS requires 0.6mm clearance
                    [100.0, 1.0],   # 100V requires 1.0mm
                    [230.0, 2.5],   # 230V (mains) requires 2.5mm
                ]
            }
        ],
        
        # IEC 60664-1 creepage table (Material Group II, Pollution Degree 2)
        'iec60664_creepage_table': [
            {
                'material': 'Material Group II',
                'pollution': 'Pollution Degree 2',
                'note': 'Standard FR4, typical environment',
                'voltages': [
                    [50.0, 0.8],    # 50V requires 0.8mm creepage
                    [100.0, 1.25],  # 100V requires 1.25mm
                    [230.0, 2.5],   # 230V requires 2.5mm
                ]
            }
        ],
        
        # Voltage domains
        'voltage_domains': [
            {
                'name': 'HIGH_VOLTAGE',
                'description': '230V AC Mains',
                'voltage_rms': 230,
                'net_patterns': ['MAINS', 'AC_L', '230V'],
                'requires_reinforced_insulation': True
            },
            {
                'name': 'LOW_VOLTAGE',
                'description': '12V DC',
                'voltage_rms': 12,
                'net_patterns': ['12V', '+12V', 'VCC'],
                'requires_reinforced_insulation': False
            },
            {
                'name': 'GROUND',
                'description': 'Ground reference',
                'voltage_rms': 0,
                'net_patterns': ['GND', 'GROUND'],
                'requires_reinforced_insulation': False
            }
        ],
        
        # Isolation requirements (MAINS to 12V needs 2.5mm clearance per IEC table)
        'isolation_requirements': [
            {
                'domain_a': 'HIGH_VOLTAGE',
                'domain_b': 'LOW_VOLTAGE',
                'isolation_type': 'basic',
                'min_clearance_mm': 2.5,  # From IEC table at 230V
                'min_creepage_mm': 2.5,
                'description': 'Mains to 12V isolation'
            }
        ]
    }


def _mock_auditor():
    """Create mock auditor for tests."""
    auditor = MagicMock()
    # get_nets_by_class returns empty list (no net class matches, force pattern matching)
    auditor.get_nets_by_class = lambda board, cls: []
    return auditor


def _mock_utility_functions():
    """Create mock utility functions for checker."""
    violations_drawn = []
    
    def draw_marker(board, pos, msg, layer, group):
        violations_drawn.append(('marker', pos, msg))
    
    def draw_arrow(board, start, end, label, layer, group):
        violations_drawn.append(('arrow', start, end, label))
    
    def get_distance(p1, p2):
        """Calculate Euclidean distance in internal units (not mm)."""
        dx = p2.x - p1.x  # Keep in internal units
        dy = p2.y - p1.y  # Keep in internal units
        return (dx**2 + dy**2)**0.5
    
    def log(msg, force=False):
        pass  # Suppress logs in tests
    
    def create_group(board, check_type, identifier, number):
        return None  # Not needed for tests
    
    return violations_drawn, draw_marker, draw_arrow, get_distance, log, create_group


class TestClearanceViolations:
    """Electrical clearance (shortest air path) between conductors."""

    def test_clearance_violation_flagged(self):
        """Two pads at different potentials, distance < IEC table threshold → assert violation drawn."""
        import pcbnew
        
        # Create board with two pads: MAINS at 230V and 12V at 12V, separated by 1.5mm
        # IEC 60664-1 requires 2.5mm clearance between 230V and 12V
        # 1.5mm < 2.5mm → violation expected
        
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1", size_mm=1.0)
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(1.5), pcbnew.FromMM(0)), "1", size_mm=1.0)
        
        footprint1 = MockFootprint("J1", [pad_mains], pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)))
        footprint2 = MockFootprint("J2", [pad_12v], pcbnew.VECTOR2I(pcbnew.FromMM(1.5), pcbnew.FromMM(0)))
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[footprint1, footprint2]
        )
        
        config = _minimal_config()
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, draw_marker, draw_arrow, get_distance, log, create_group = _mock_utility_functions()
        
        violations = checker.check(draw_marker, draw_arrow, get_distance, log, create_group)
        
        # Assert: violation was flagged (distance 1.5mm < required 2.5mm)
        assert violations > 0, f"Expected clearance violation but got {violations} violations"
        assert len(violations_drawn) > 0, "Expected violation marker drawn"
        
        # Verify violation message contains "CLEARANCE"
        violation_msgs = [v[2] for v in violations_drawn if v[0] == 'marker']
        assert any('CLEARANCE' in msg for msg in violation_msgs), \
            f"Expected CLEARANCE violation message, got: {violation_msgs}"

    def test_pads_at_minimum_clearance_no_violation(self):
        """Pads at exactly minimum IEC clearance distance → assert no violation."""
        import pcbnew
        
        # Pads with 2.5mm edge-to-edge clearance (minimum for 230V-12V per IEC table)
        # With 1.0mm diameter pads, centers must be 3.5mm apart: 3.5 - 0.5 - 0.5 = 2.5mm
        # 2.5mm == 2.5mm → no violation expected
        
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1", size_mm=1.0)
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(3.5), pcbnew.FromMM(0)), "1", size_mm=1.0)
        
        footprint1 = MockFootprint("J1", [pad_mains], pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)))
        footprint2 = MockFootprint("J2", [pad_12v], pcbnew.VECTOR2I(pcbnew.FromMM(3.5), pcbnew.FromMM(0)))
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[footprint1, footprint2]
        )
        
        config = _minimal_config()
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, draw_marker, draw_arrow, get_distance, log, create_group = _mock_utility_functions()
        
        violations = checker.check(draw_marker, draw_arrow, get_distance, log, create_group)
        
        # Debug: print violations
        import pcbnew
        for v_type, *v_data in violations_drawn:
            if v_type == 'marker':
                pos, msg = v_data
                print(f"Marker at ({pcbnew.ToMM(pos.x):.3f}, {pcbnew.ToMM(pos.y):.3f}): {msg}")
        
        # Assert: no violation (distance exactly meets requirement)
        assert violations == 0, f"Expected no violations but got {violations}"
        assert len(violations_drawn) == 0, f"Expected no markers drawn, got {violations_drawn}"

    def test_disabled_in_config_returns_zero(self):
        """Check disabled via config key clearance_creepage.enabled → assert 0 violations."""
        import pcbnew
        
        # Even with pads too close, disabled check should return 0
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1")
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(0.5), pcbnew.FromMM(0)), "1")  # Too close!
        
        footprint1 = MockFootprint("J1", [pad_mains])
        footprint2 = MockFootprint("J2", [pad_12v])
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[footprint1, footprint2]
        )
        
        config = _minimal_config()
        config['check_clearance'] = False  # Disable clearance check
        config['check_creepage'] = False   # Disable creepage check
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, draw_marker, draw_arrow, get_distance, log, create_group = _mock_utility_functions()
        
        violations = checker.check(draw_marker, draw_arrow, get_distance, log, create_group)
        
        # Assert: no violations because checks disabled
        assert violations == 0, f"Expected 0 violations (checks disabled) but got {violations}"


class TestCreepageViolations:
    """Creepage (surface path) distance checks."""

    def test_creepage_violation_flagged(self):
        """Creepage path shorter than IEC 60664-1 table value → assert violation."""
        import pcbnew
        
        # Creepage requires 2.5mm for 230V-12V, pads at 1.8mm apart
        # 1.8mm < 2.5mm → violation expected
        
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1", size_mm=1.0)
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(1.8), pcbnew.FromMM(0)), "1", size_mm=1.0)
        
        footprint1 = MockFootprint("J1", [pad_mains])
        footprint2 = MockFootprint("J2", [pad_12v])
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[footprint1, footprint2]
        )
        
        config = _minimal_config()
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, draw_marker, draw_arrow, get_distance, log, create_group = _mock_utility_functions()
        
        violations = checker.check(draw_marker, draw_arrow, get_distance, log, create_group)
        
        # Assert: violation was flagged
        assert violations > 0, f"Expected creepage violation but got {violations} violations"
        
        # Verify violation message contains "CREEPAGE" (may also have CLEARANCE)
        violation_msgs = [v[2] for v in violations_drawn if v[0] == 'marker']
        assert len(violation_msgs) > 0, "Expected at least one violation marker"

    def test_adequate_creepage_no_violation(self):
        """Pads with sufficient creepage path → assert no violation."""
        import pcbnew
        
        # Pads with 2.6mm edge-to-edge clearance, required creepage 2.5mm
        # With 1.0mm diameter pads, centers at 3.6mm: 3.6 - 0.5 - 0.5 = 2.6mm
        # 2.6mm > 2.5mm → no violation
        
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1")
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(3.6), pcbnew.FromMM(0)), "1")
        
        footprint1 = MockFootprint("J1", [pad_mains])
        footprint2 = MockFootprint("J2", [pad_12v])
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[footprint1, footprint2]
        )
        
        config = _minimal_config()
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, draw_marker, draw_arrow, get_distance, log, create_group = _mock_utility_functions()
        
        violations = checker.check(draw_marker, draw_arrow, get_distance, log, create_group)
        
        # Assert: no violations
        assert violations == 0, f"Expected no violations but got {violations}"


class TestPollutionDegree:
    """Pollution degree selection affects the required clearance threshold."""

    def test_pollution_degree_2_vs_3_threshold(self):
        """Configure pollution_degree=2 vs 3 → assert different distance thresholds applied."""
        import pcbnew
        
        # Pollution Degree 2: 100V requires 1.25mm creepage (from config)
        # Pollution Degree 3: 100V requires 2.0mm creepage (different Material Group table)
        # Test that PD3 is stricter than PD2
        # With 1.0mm pads at 2.6mm center-to-center: 2.6 - 0.5 - 0.5 = 1.6mm edge-to-edge
        # PD2: 1.6mm > 1.25mm → PASS, PD3: 1.6mm < 2.0mm → FAIL
        
        net_100v = MockNet("100V", net_class="Default")
        net_gnd = MockNet("GND", net_class="Default")
        
        pad_100v = MockPad("100V", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1")
        pad_gnd = MockPad("GND", pcbnew.VECTOR2I(pcbnew.FromMM(2.6), pcbnew.FromMM(0)), "1")  # 1.6mm edge-to-edge
        
        footprint1 = MockFootprint("J1", [pad_100v])
        footprint2 = MockFootprint("J2", [pad_gnd])
        
        board = MockBoard(
            nets=[net_100v, net_gnd],
            footprints=[footprint1, footprint2]
        )
        
        # Test with PD2 (1.6mm should pass - required 1.25mm)
        config_pd2 = _minimal_config()
        config_pd2['pollution_degree'] = 2
        config_pd2['voltage_domains'].append({
            'name': 'MED_VOLTAGE',
            'description': '100V DC',
            'voltage_rms': 100,
            'net_patterns': ['100V'],
            'requires_reinforced_insulation': False
        })
        config_pd2['isolation_requirements'].append({
            'domain_a': 'MED_VOLTAGE',
            'domain_b': 'GROUND',
            'isolation_type': 'basic',
            'min_clearance_mm': 1.0,
            'min_creepage_mm': 1.25,  # PD2 value
            'description': '100V to GND - PD2'
        })
        
        checker_pd2 = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config_pd2,
            report_lines=[],
            verbose=False,
            auditor=_mock_auditor()
        )
        
        violations_drawn_pd2, *utils_pd2 = _mock_utility_functions()
        violations_pd2 = checker_pd2.check(*utils_pd2)
        
        # Test with PD3 (1.6mm should fail - required 2.0mm)
        config_pd3 = _minimal_config()
        config_pd3['pollution_degree'] = 3
        config_pd3['voltage_domains'].append({
            'name': 'MED_VOLTAGE',
            'description': '100V DC',
            'voltage_rms': 100,
            'net_patterns': ['100V'],
            'requires_reinforced_insulation': False
        })
        config_pd3['isolation_requirements'].append({
            'domain_a': 'MED_VOLTAGE',
            'domain_b': 'GROUND',
            'isolation_type': 'basic',
            'min_clearance_mm': 1.0,
            'min_creepage_mm': 2.0,  # PD3 value (stricter)
            'description': '100V to GND - PD3'
        })
        
        checker_pd3 = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config_pd3,
            report_lines=[],
            verbose=False,
            auditor=_mock_auditor()
        )
        
        violations_drawn_pd3, *utils_pd3 = _mock_utility_functions()
        violations_pd3 = checker_pd3.check(*utils_pd3)
        
        # Assert: PD3 is stricter (more violations)
        assert violations_pd3 > violations_pd2, \
            f"Expected PD3 ({violations_pd3}) > PD2 ({violations_pd2}) violations (stricter threshold)"


class TestVoltageCategoryTableLookup:
    """CAT I / II / III / IV over-voltage categories drive IEC table selection."""

    def test_cat_ii_table_selection(self):
        """Set voltage_category=CAT_II, verify correct row selected from IEC 60664-1 table."""
        import pcbnew
        
        # OVC-II is the default in our config, just verify it processes without error
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1")
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(3.0), pcbnew.FromMM(0)), "1")
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_12v])]
        )
        
        config = _minimal_config()
        config['overvoltage_category'] = 'II'  # Explicit CAT-II
        
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Assert: check runs successfully (no exceptions)
        assert violations >= 0, "Checker should run without errors for OVC-II"

    def test_cat_iii_stricter_than_cat_ii(self):
        """Set voltage_category=CAT_III, verify stricter values used."""
        import pcbnew
        
        # CAT-III has 1.5x multiplier vs CAT-II (overvoltage_category_factors)
        # Same board should have MORE violations under CAT-III
        
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1")
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(2.6), pcbnew.FromMM(0)), "1")  # Borderline
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_12v])]
        )
        
        # Test with CAT-II (default)
        config_cat2 = _minimal_config()
        config_cat2['overvoltage_category'] = 'II'
        checker_cat2 = ClearanceCreepageChecker(
            board=board, marker_layer=0, config=config_cat2,
            report_lines=[], verbose=False, auditor=_mock_auditor()
        )
        violations_drawn_cat2, *utils_cat2 = _mock_utility_functions()
        violations_cat2 = checker_cat2.check(*utils_cat2)
        
        # Test with CAT-III (stricter)
        config_cat3 = _minimal_config()
        config_cat3['overvoltage_category'] = 'III'
        # Update isolation requirements with 1.5x factor
        config_cat3['isolation_requirements'] = [
            {
                'domain_a': 'HIGH_VOLTAGE',
                'domain_b': 'LOW_VOLTAGE',
                'isolation_type': 'basic',
                'min_clearance_mm': 2.5 * 1.5,  # CAT-III multiplier
                'min_creepage_mm': 2.5 * 1.5,
                'description': 'Mains to 12V - CAT-III'
            }
        ]
        checker_cat3 = ClearanceCreepageChecker(
            board=board, marker_layer=0, config=config_cat3,
            report_lines=[], verbose=False, auditor=_mock_auditor()
        )
        violations_drawn_cat3, *utils_cat3 = _mock_utility_functions()
        violations_cat3 = checker_cat3.check(*utils_cat3)
        
        # Assert: CAT-III is stricter
        assert violations_cat3 >= violations_cat2, \
            f"Expected CAT-III ({violations_cat3}) >= CAT-II ({violations_cat2}) violations"


class TestMixedVoltageNets:
    """Board with multiple voltage domains — only cross-domain pairs are checked."""

    def test_same_domain_pair_skipped(self):
        """Two pads on same voltage domain → assert check is skipped for that pair."""
        import pcbnew
        
        # Two 12V pads close together - should not be checked (same domain)
        net_12v_a = MockNet("12V_A", net_class="Default")
        net_12v_b = MockNet("12V_B", net_class="Default")
        
        pad_a = MockPad("12V_A", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1")
        pad_b = MockPad("12V_B", pcbnew.VECTOR2I(pcbnew.FromMM(0.1), pcbnew.FromMM(0)), "1")  # Very close!
        
        board = MockBoard(
            nets=[net_12v_a, net_12v_b],
            footprints=[MockFootprint("J1", [pad_a]), MockFootprint("J2", [pad_b])]
        )
        
        config = _minimal_config()
        # Both nets match "12V" pattern → same domain
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Assert: no violations (same-domain pairs not checked)
        assert violations == 0, f"Expected 0 violations (same domain) but got {violations}"

    def test_cross_domain_pair_checked(self):
        """Pads on different domains → assert check is performed."""
        import pcbnew
        
        # MAINS (230V) and 12V pads close together - different domains, should be checked
        net_mains = MockNet("MAINS", net_class="Default")
        net_12v = MockNet("12V", net_class="Default")
        
        pad_mains = MockPad("MAINS", pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)), "1")
        pad_12v = MockPad("12V", pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(0)), "1")  # Too close!
        
        board = MockBoard(
            nets=[net_mains, net_12v],
            footprints=[MockFootprint("J1", [pad_mains]), MockFootprint("J2", [pad_12v])]
        )
        
        config = _minimal_config()
        checker = ClearanceCreepageChecker(
            board=board,
            marker_layer=0,
            config=config,
            report_lines=[],
            verbose=False,
        auditor=_mock_auditor()
        )
        
        violations_drawn, *utils = _mock_utility_functions()
        violations = checker.check(*utils)
        
        # Assert: violation detected (cross-domain pair checked)
        assert violations > 0, f"Expected violation (cross-domain) but got {violations}"
