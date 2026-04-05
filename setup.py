#!/usr/bin/env python3
"""Setup script for EMC Auditor KiCad Plugin."""

from setuptools import setup, find_packages
from pathlib import Path

readme_file = Path(__file__).parent / "README.md"
if readme_file.exists():
    with open(readme_file, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "EMC/DRC verification plugin for KiCad 9.0+"

setup(
    name="emc-auditor",
    version="1.0.0",
    author="EMC Auditor Team",
    description="EMC/DRC verification plugin for KiCad 9.0+",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/RolandWa/KiCAD_Custom_DRC",
    package_dir={"": "src"},
    py_modules=[
        "emc_auditor_plugin",
        "clearance_creepage",
        "decoupling",
        "emi_filtering",
        "ground_plane",
        "signal_integrity",
        "via_stitching",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    ],
    python_requires=">=3.8",
    install_requires=[
        'tomli>=1.2.0; python_version < "3.11"',
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.0.0",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["emc_rules.toml", "emc_icon.png"],
    },
    zip_safe=False,
)
