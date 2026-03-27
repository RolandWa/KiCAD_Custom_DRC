# EMC Auditor Plugin — Workspace Instructions

> KiCad 9.0+ PCB plugin for EMC/DRC verification. Python 3.8+, MIT license.

## Quick Reference

| Item | Value |
|------|-------|
| Entry point | `emc_auditor_plugin.py` (main orchestrator, ~900 lines) |
| Config file | `emc_rules.toml` (TOML, all rules externally configurable) |
| Deploy script | `sync_to_kicad.ps1` (copy from `.template`, gitignored) |
| KiCad API | `pcbnew` module (KiCad's Python scripting API) |
| Marker layer | `User.Comments` — all violations draw here |

## Build / Test / Deploy

```powershell
# Syntax check (no KiCad needed)
python -m py_compile emc_auditor_plugin.py

# Deploy to KiCad plugins directory
.\sync_to_kicad.ps1

# Full test: restart KiCad → open board → run plugin
# Baseline: 40 violations (via:0, decoupling:9, ground:4, emi:22, clearance:4, signal:1)
```

There is no automated test suite yet. Validation is manual against the baseline board.

## Architecture

**Modular checker pattern with dependency injection.** The main plugin instantiates checker classes, injects utility functions (logging, marker drawing, distance calculation, group creation), and aggregates results.

```
emc_auditor_plugin.py          ← Orchestrator: loads config, runs checkers, shows report
├── via_stitching.py           ← GND return via proximity (IPC-2221)
├── decoupling.py              ← Capacitor-to-IC distance (IPC-2221)
├── emi_filtering.py           ← Connector filter topology (CISPR 32, IEC 61000)
├── ground_plane.py            ← Return path continuity under traces
├── clearance_creepage.py      ← IEC60664-1 / IPC2221 safety distances
├── signal_integrity.py        ← Trace/via integrity checks (partial)
└── emc_rules.toml             ← All thresholds and enable/disable flags
```

**Each checker follows a standard interface** — see `.copilot-instructions.md` for the full template:

- Constructor: `__init__(board, marker_layer, config, report_lines, verbose, auditor)`
- Entry point: `check(draw_marker_func, draw_arrow_func, get_distance_func, log_func, create_group_func) → int`
- Utilities are **injected**, never reimplemented. No `log()` method in modules. No manual `PCB_GROUP()` creation.

## Key Conventions

- **Type hints** on all public methods; **docstrings** (Google style with Args/Returns) required.
- **f-strings** only — no `.format()` or `%`.
- **Early returns** to reduce nesting; **list comprehensions** over manual loops.
- **Private methods** use `_leading_underscore`.
- **Constants** are `UPPER_CASE` at module level.
- **Config access**: `self.config.get('key', default)` — always provide defaults.
- **Unit conversions**: always use `pcbnew.FromMM()` / `pcbnew.ToMM()` — never raw integers.
- **Violation markers**: create a named `EMC_<CheckType>_<id>_<n>` group, draw circle + optional arrow.
- **Error handling**: wrap each checker's `check()` in try/except, fail gracefully with `return 0`.
- **Module size**: 150–700 lines. Extract if larger.
- **Line length**: ≤ 100 chars. Function length: ≤ 50 lines.

## Security — Pre-Commit Mandatory

Never commit absolute paths, real usernames, company names, or credentials. Use placeholders (`<YourUsername>`, `<repository_path>`). Local-only files (`sync_to_kicad.ps1`, `test_config.py`) must stay gitignored.

```powershell
# Run before every commit
git diff --cached | Select-String -Pattern "C:\\Users\\[^<]|OneDrive - "
git status --ignored | Select-String -Pattern "sync_to_kicad.ps1|test_config.py"
```

## Manufacturer DRU Files

`JLCPCB/` and `PCBWAY/` contain KiCad Design Rule (`.kicad_dru`) presets for those fabricators. They are standalone — not used by the plugin.

## Detailed Guides

For full code templates, anti-patterns, and examples, see:
- [.copilot-instructions.md](../.copilot-instructions.md) — complete AI development guide with checker template, anti-patterns, and violation marker patterns
- [README.md](../README.md) — feature list, installation, changelog
- [CLEARANCE_CREEPAGE_GUIDE.md](../CLEARANCE_CREEPAGE_GUIDE.md) — IEC60664-1 tables and domain configuration
- [IMPEDANCE_ALGORITHM.md](../IMPEDANCE_ALGORITHM.md) — controlled impedance calculation details
- [VIA_STITCHING.md](../VIA_STITCHING.md), [GROUND_PLANE.md](../GROUND_PLANE.md), [TRACE_WIDTH.md](../TRACE_WIDTH.md), [DECOUPLING.md](../DECOUPLING.md) — per-rule documentation
