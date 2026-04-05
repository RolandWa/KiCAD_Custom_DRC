"""
EMC Auditor Build System

Builds a KiCad ActionPlugin package that registers a toolbar button in the
PCB Editor.  When clicked the button runs the EMC/DRC checks on the open board.

Usage:
    python build.py              # build package directory + ZIP
    python build.py --deploy     # build + install to local KiCad
    python build.py --zip        # build ZIP only (no deploy)
    python build.py --clean      # remove build directory

Outputs (in build/):
    com_github_RolandWa_emc_auditor/     Package directory (ready to copy)
    EMC-Auditor-<version>.zip            ZIP for manual install or distribution

ZIP installation:
    1. Open KiCad → Plugin and Content Manager
    2. "Install from File…" → select EMC-Auditor-<version>.zip
    — OR —
    Extract ZIP into:
      Windows:  Documents/KiCad/9.0/3rdparty/plugins/
      macOS:    ~/Documents/KiCad/9.0/3rdparty/plugins/
      Linux:    ~/.local/share/KiCad/9.0/3rdparty/plugins/
"""

import os
import re
import sys
import json
import shutil
import stat
import logging
import platform
import zipfile
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Directory name must match what KiCad's plugin loader expects.
# Using underscore form (not dots) so it's a valid Python identifier for import.
PLUGIN_DIR_NAME = "com_github_RolandWa_emc_auditor"
PLUGIN_IDENTIFIER = "com.github.RolandWa.emc_auditor"

# Python source modules live under src/; assets at repo root.
# Each entry is (repo_relative_path, destination_filename_in_package).
PLUGIN_MODULES = [
    ("src/emc_auditor_plugin.py",  "emc_auditor_plugin.py"),
    ("src/clearance_creepage.py",  "clearance_creepage.py"),
    ("src/decoupling.py",          "decoupling.py"),
    ("src/emi_filtering.py",       "emi_filtering.py"),
    ("src/ground_plane.py",        "ground_plane.py"),
    ("src/signal_integrity.py",    "signal_integrity.py"),
    ("src/via_stitching.py",       "via_stitching.py"),
    ("emc_rules.toml",             "emc_rules.toml"),
    ("emc_icon.png",               "emc_icon.png"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_version(project_root: Path) -> str:
    """Extract version from setup.py."""
    setup_file = project_root / "setup.py"
    if setup_file.exists():
        content = setup_file.read_text(encoding="utf-8")
        match = re.search(r'version\s*=\s*["\']([^"\'\n]+)["\']', content)
        if match:
            return match.group(1)
    return "1.0.0"


def _kicad_3rdparty_plugins_dir() -> Optional[Path]:
    """Return the 3rdparty/plugins directory KiCad actually scans.

    On Windows with OneDrive folder-redirection the shell Documents folder
    may differ from %USERPROFILE%\\Documents.  We parse pcbnew.json to find
    the real path KiCad is using, then fall back to platform defaults.
    """
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        pcbnew_json = Path(appdata) / "kicad" / "9.0" / "pcbnew.json"
        if pcbnew_json.exists():
            try:
                data = json.loads(pcbnew_json.read_text(encoding="utf-8"))
                for entry in data.get("action_plugins", []):
                    if isinstance(entry, dict):
                        for key in entry:
                            if "3rdparty" in key:
                                idx = key.find("3rdparty")
                                raw = key[:idx].replace("\\\\", "\\")
                                return Path(raw) / "3rdparty" / "plugins"
            except Exception:
                pass

    if platform.system() == "Windows":
        docs = Path(os.environ.get("USERPROFILE", "")) / "Documents"
        return docs / "KiCad" / "9.0" / "3rdparty" / "plugins"
    elif platform.system() == "Darwin":
        return Path.home() / "Documents" / "KiCad" / "9.0" / "3rdparty" / "plugins"
    else:
        return Path.home() / ".local" / "share" / "KiCad" / "9.0" / "3rdparty" / "plugins"


def _force_rmtree(path: Path):
    """Remove a directory tree, handling OneDrive locks and read-only files."""
    def _on_error(func, fpath, _exc_info):
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)

    try:
        shutil.rmtree(path, onerror=_on_error)
    except PermissionError:
        import time
        alt = path.with_name(f"{path.name}_old_{int(time.time())}")
        path.rename(alt)
        logger.warning(f"  Renamed locked dir → {alt.name}")


# ---------------------------------------------------------------------------
# Build system
# ---------------------------------------------------------------------------
class EMCAuditorBuildSystem:
    """Build system for EMC Auditor KiCad plugin."""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent
        self.build_dir = self.project_root / "build"
        self.version = _read_version(self.project_root)
        self.package_dir = self.build_dir / PLUGIN_DIR_NAME
        self.zip_path = self.build_dir / f"EMC-Auditor-{self.version}.zip"

    # -- clean --------------------------------------------------------------
    def clean(self):
        """Remove and recreate the package directory inside build/."""
        logger.info("Cleaning build directory...")
        self.build_dir.mkdir(exist_ok=True)
        if self.package_dir.exists():
            _force_rmtree(self.package_dir)
        if self.zip_path.exists():
            try:
                self.zip_path.unlink()
            except PermissionError:
                logger.warning(f"  Cannot remove locked {self.zip_path.name} — will overwrite")
        logger.info("[OK] Build directory ready")

    # -- copy sources -------------------------------------------------------
    def _copy_sources(self):
        """Assemble the plugin tree under build/<PLUGIN_DIR_NAME>/."""
        pkg = self.package_dir
        pkg.mkdir(parents=True, exist_ok=True)

        # Plugin modules (flat layout in deployed package — sources may come from src/)
        for src_rel, dst_name in PLUGIN_MODULES:
            src = self.project_root / src_rel
            if src.exists():
                shutil.copy2(src, pkg / dst_name)
                size_kb = src.stat().st_size / 1024
                logger.info(f"  [OK] {dst_name} ({size_kb:.1f} KB)")
            else:
                logger.warning(f"  [WARN] {src_rel} not found — skipping")

        # __init__.py — KiCad's SWIG loader imports the package via this file.
        # It registers the ActionPlugin so the toolbar button appears.
        init_content = '''\
"""EMC Auditor KiCad Plugin — SWIG ActionPlugin registration.

KiCad's LoadPlugins() imports this package via __init__.py.
The EMCAuditorPlugin().register() call at the bottom of
emc_auditor_plugin.py registers the toolbar button automatically.
"""
import os
import sys

# Ensure the package directory is on sys.path so the flat-layout
# sibling modules (clearance_creepage, signal_integrity, etc.) resolve.
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

from emc_auditor_plugin import EMCAuditorPlugin  # noqa: F401 (side-effect import)
'''
        (pkg / "__init__.py").write_text(init_content, encoding="utf-8")
        logger.info("  [OK] __init__.py  (SWIG ActionPlugin registration)")

        # metadata.json — required by KiCad PCM "Install from File…"
        metadata = {
            "$schema": "https://go.kicad.org/pcm/schemas/v1",
            "name": "EMC Auditor",
            "description": "EMC/DRC verification plugin for KiCad. Checks IEC60664-1 clearance/creepage, signal integrity, controlled impedance, differential pairs, and more.",
            "description_full": (
                "EMC Auditor is a KiCad 9.0+ plugin that runs a comprehensive suite of "
                "EMC and DRC checks on your PCB: IEC60664-1 clearance & creepage with "
                "Dijkstra-based slot-aware creepage pathfinding, controlled impedance "
                "(microstrip/stripline/differential), via stitching, decoupling capacitor "
                "proximity, EMI filter topology, ground plane continuity, and signal "
                "integrity checks. All thresholds are configurable via emc_rules.toml."
            ),
            "identifier": PLUGIN_IDENTIFIER,
            "type": "plugin",
            "author": {
                "name": "EMC Auditor Team",
                "contact": {"github": "https://github.com/RolandWa/KiCAD_Custom_DRC"},
            },
            "license": "MIT",
            "resources": {
                "homepage": "https://github.com/RolandWa/KiCAD_Custom_DRC",
            },
            "versions": [
                {
                    "version": self.version,
                    "status": "stable",
                    "kicad_version": "9.0",
                }
            ],
        }
        (pkg / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        logger.info("  [OK] metadata.json")

        # LICENSE
        lic = self.project_root / "LICENSE"
        if lic.exists():
            shutil.copy2(lic, pkg / "LICENSE")
            logger.info("  [OK] LICENSE")

    # -- validate -----------------------------------------------------------
    def _validate(self) -> bool:
        """Check that all required files exist in the assembled package."""
        required = [
            "__init__.py",
            "emc_auditor_plugin.py",
            "signal_integrity.py",
            "emc_rules.toml",
            "emc_icon.png",
            "metadata.json",
        ]
        missing = [f for f in required if not (self.package_dir / f).exists()]
        if missing:
            logger.error(f"  [FAIL] Missing: {missing}")
            return False
        logger.info("[OK] Validation passed")
        return True

    # -- create ZIP ---------------------------------------------------------
    def _create_zip(self) -> Path:
        """Create a ZIP file suitable for KiCad 'Install from File…'.

        Structure inside the ZIP:
            metadata.json                               ← PCM requires this at root
            plugins/
              com_github_RolandWa_emc_auditor/
                __init__.py
                emc_auditor_plugin.py
                signal_integrity.py
                ...
        """
        logger.info(f"\nCreating ZIP: {self.zip_path.name}")

        import time
        tmp_zip = self.zip_path.with_suffix(f".tmp_{int(time.time())}.zip")
        try:
            with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED):
                pass  # test writability
            zip_target = self.zip_path
        except PermissionError:
            zip_target = tmp_zip
            logger.warning(f"  ZIP locked by OneDrive — writing to {zip_target.name}")

        with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zf:
            # metadata.json at ZIP root (required by PCM)
            zf.write(self.package_dir / "metadata.json", "metadata.json")

            # All package files under plugins/<PLUGIN_DIR_NAME>/
            prefix = f"plugins/{PLUGIN_DIR_NAME}"
            for file_path in sorted(self.package_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                if "__pycache__" in file_path.parts:
                    continue
                rel = file_path.relative_to(self.package_dir)
                zf.write(file_path, f"{prefix}/{rel.as_posix()}")

            file_count = len(zf.namelist())

        if zip_target != self.zip_path:
            try:
                self.zip_path.unlink(missing_ok=True)
                zip_target.rename(self.zip_path)
            except PermissionError:
                self.zip_path = zip_target

        size_kb = self.zip_path.stat().st_size / 1024
        logger.info(f"[OK] {self.zip_path.name}  ({file_count} files, {size_kb:.0f} KB)")
        return self.zip_path

    # -- build (main entry) -------------------------------------------------
    def build(self) -> Path:
        """Build the package directory and ZIP."""
        logger.info(f"Building EMC Auditor {self.version}")
        logger.info(f"  Plugin dir name: {PLUGIN_DIR_NAME}\n")

        self.clean()
        self._copy_sources()
        ok = self._validate()
        if ok:
            self._create_zip()

        logger.info(f"\n{'=' * 60}")
        if ok:
            logger.info("BUILD COMPLETE")
            logger.info(f"  Directory: {self.package_dir}")
            logger.info(f"  ZIP:       {self.zip_path}")
        else:
            logger.error("BUILD FAILED")
        logger.info(f"{'=' * 60}")
        return self.package_dir

    # -- deploy -------------------------------------------------------------
    def deploy(self) -> bool:
        """Copy the built package into KiCad's 3rdparty/plugins directory."""
        plugins_dir = _kicad_3rdparty_plugins_dir()
        if plugins_dir is None:
            logger.error("[FAIL] Cannot determine KiCad 3rdparty plugins path")
            return False

        dest = plugins_dir / PLUGIN_DIR_NAME
        logger.info(f"\nDeploying to: {dest}")

        if dest.exists():
            _force_rmtree(dest)

        shutil.copytree(self.package_dir, dest)
        n = len(list(dest.rglob("*.py")))
        logger.info(f"[OK] Deployed ({n} .py files)")
        logger.info("\n  >>> Restart KiCad to reload the plugin <<<")
        return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EMC Auditor Build System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python build.py              Build package directory + ZIP
  python build.py --deploy     Build + install to local KiCad
  python build.py --zip        Build ZIP only (no deploy)
  python build.py --clean      Remove build directory
""",
    )
    parser.add_argument("--clean", action="store_true", help="Clean build directory only")
    parser.add_argument("--deploy", action="store_true", help="Build and deploy to local KiCad")
    parser.add_argument("--zip", action="store_true", help="Build ZIP only (no deploy)")
    args = parser.parse_args()

    builder = EMCAuditorBuildSystem()

    if args.clean:
        builder.clean()
        return 0

    builder.build()

    if args.deploy:
        if not builder.deploy():
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
