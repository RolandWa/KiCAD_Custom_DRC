"""
Unit tests for the build.py module.

Tests validate:
  * PLUGIN_IDENTIFIER and PLUGIN_DIR_NAME naming conventions
  * Version string format extracted from setup.py
  * metadata.json structure produced by the build system
  * Package directory assembly (required files present after build)
  * ZIP archive creation
"""

import re
import sys
import json
import pytest
from pathlib import Path

# tests/build/ → go up two levels to reach project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import build as build_module
from build import (
    PLUGIN_DIR_NAME,
    PLUGIN_IDENTIFIER,
    EMCAuditorBuildSystem,
    _read_version,
)


# ============================================================================
# Naming conventions
# ============================================================================

class TestNamingConventions:
    """PLUGIN_DIR_NAME and PLUGIN_IDENTIFIER must satisfy KiCad PCM constraints."""

    KCM_REGEX = re.compile(r'^[a-zA-Z][-a-zA-Z0-9._]{0,98}[a-zA-Z0-9]$')

    def test_plugin_dir_name_is_valid_python_identifier_chars(self):
        assert re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', PLUGIN_DIR_NAME), (
            f"{PLUGIN_DIR_NAME!r} is not a valid Python identifier"
        )

    def test_plugin_dir_name_starts_with_com_github(self):
        assert PLUGIN_DIR_NAME.startswith("com_github_")

    def test_plugin_identifier_matches_pcm_regex(self):
        assert self.KCM_REGEX.match(PLUGIN_IDENTIFIER), (
            f"{PLUGIN_IDENTIFIER!r} does not match KiCad PCM regex"
        )

    def test_identifier_starts_with_com_github(self):
        assert PLUGIN_IDENTIFIER.startswith("com.github.")

    def test_identifier_components_match_dir_name(self):
        """PLUGIN_DIR_NAME must be PLUGIN_IDENTIFIER with dots replaced by underscores."""
        expected_dir = PLUGIN_IDENTIFIER.replace(".", "_")
        assert PLUGIN_DIR_NAME == expected_dir, (
            f"Dir name {PLUGIN_DIR_NAME!r} does not derive from "
            f"identifier {PLUGIN_IDENTIFIER!r} (expected {expected_dir!r})"
        )

    def test_identifier_no_consecutive_dots(self):
        assert ".." not in PLUGIN_IDENTIFIER

    def test_identifier_no_trailing_dot(self):
        assert not PLUGIN_IDENTIFIER.endswith(".")

    def test_identifier_no_leading_dot(self):
        assert not PLUGIN_IDENTIFIER.startswith(".")


# ============================================================================
# Version string
# ============================================================================

class TestVersionString:

    def test_read_version_returns_string(self):
        assert isinstance(_read_version(PROJECT_ROOT), str)

    def test_version_is_semver_like(self):
        version = _read_version(PROJECT_ROOT)
        assert re.match(r'^\d+\.\d+\.\d+', version), (
            f"Version {version!r} does not look like semver (MAJOR.MINOR.PATCH)"
        )

    def test_version_fallback_when_no_setup_py(self, tmp_path):
        """Falls back to '1.0.0' when setup.py is absent."""
        assert _read_version(tmp_path) == "1.0.0"


# ============================================================================
# metadata.json content
# ============================================================================

class TestMetadataJson:
    """Run a build into a temp dir and inspect the generated metadata.json."""

    @pytest.fixture(scope="class")
    def built_pkg(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("build")
        bs = EMCAuditorBuildSystem(project_root=PROJECT_ROOT)
        bs.build_dir   = tmp
        bs.package_dir = tmp / PLUGIN_DIR_NAME
        bs.zip_path    = tmp / f"EMC-Auditor-{bs.version}.zip"
        bs.build()
        return bs.package_dir

    def test_metadata_json_exists(self, built_pkg):
        assert (built_pkg / "metadata.json").exists()

    def test_metadata_schema(self, built_pkg):
        data = json.loads((built_pkg / "metadata.json").read_text())
        assert data["$schema"] == "https://go.kicad.org/pcm/schemas/v1"

    def test_metadata_identifier(self, built_pkg):
        data = json.loads((built_pkg / "metadata.json").read_text())
        assert data["identifier"] == PLUGIN_IDENTIFIER

    def test_metadata_type_plugin(self, built_pkg):
        data = json.loads((built_pkg / "metadata.json").read_text())
        assert data["type"] == "plugin"

    def test_metadata_has_versions(self, built_pkg):
        data = json.loads((built_pkg / "metadata.json").read_text())
        assert isinstance(data.get("versions"), list)
        assert len(data["versions"]) >= 1

    def test_metadata_kicad_version_9(self, built_pkg):
        data = json.loads((built_pkg / "metadata.json").read_text())
        kicad_ver = data["versions"][0].get("kicad_version", "")
        assert kicad_ver.startswith("9"), (
            f"Expected KiCad version 9.x, got {kicad_ver!r}"
        )

    def test_icon_field_set(self, built_pkg):
        data = json.loads((built_pkg / "metadata.json").read_text())
        assert "icon" in data
        assert data["icon"].endswith(".png")


# ============================================================================
# Package directory contents
# ============================================================================

class TestPackageContents:
    """All required plugin files must be present after build."""

    @pytest.fixture(scope="class")
    def built_pkg(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("pkg_contents")
        bs = EMCAuditorBuildSystem(project_root=PROJECT_ROOT)
        bs.build_dir   = tmp
        bs.package_dir = tmp / PLUGIN_DIR_NAME
        bs.zip_path    = tmp / f"EMC-Auditor-{bs.version}.zip"
        bs.build()
        return bs.package_dir

    @pytest.mark.parametrize("filename", [
        "__init__.py",
        "emc_auditor_plugin.py",
        "signal_integrity.py",
        "clearance_creepage.py",
        "decoupling.py",
        "emi_filtering.py",
        "ground_plane.py",
        "via_stitching.py",
        "emc_rules.toml",
        "emc_icon.png",
        "icon-24.png",
        "icon-64.png",
        "metadata.json",
    ])
    def test_required_file_present(self, built_pkg, filename):
        assert (built_pkg / filename).exists(), (
            f"Required file missing from package: {filename}"
        )

    def test_zip_created(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("zip_test")
        bs = EMCAuditorBuildSystem(project_root=PROJECT_ROOT)
        bs.build_dir   = tmp
        bs.package_dir = tmp / PLUGIN_DIR_NAME
        bs.zip_path    = tmp / f"EMC-Auditor-{bs.version}.zip"
        bs.build()
        assert bs.zip_path.exists()
        assert bs.zip_path.stat().st_size > 0
