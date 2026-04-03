# EMC Auditor Plugin — Workspace Instructions

> KiCad 9.0+ PCB plugin for EMC/DRC verification. Python 3.8+, MIT license.

## Quick Reference

| Item | Value |
|------|-------|
| Entry point | `emc_auditor_plugin.py` (main orchestrator, ~960 lines) |
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
# Note: Python 3.11+ uses built-in tomllib; Python 3.8–3.10 requires: pip install tomli

# Full test: restart KiCad → open board → run plugin
# Baseline: 40 violations (via:0, decoupling:9, ground:4, emi:22, clearance:4, signal:1)
```

No automated test suite yet. Validation is manual against the baseline board.

## Architecture

**Modular checker pattern with dependency injection.** The main plugin instantiates checker classes, injects utility functions (logging, marker drawing, distance calculation, group creation), and aggregates results.

```
emc_auditor_plugin.py          ← Orchestrator: loads config, runs checkers, shows report
├── via_stitching.py           ← GND return via proximity (IPC-2221)
├── decoupling.py              ← Capacitor-to-IC distance (IPC-2221)
├── emi_filtering.py           ← Connector filter topology (CISPR 32, IEC 61000)
├── ground_plane.py            ← Return path continuity under traces
├── clearance_creepage.py      ← IEC60664-1 / IPC2221 safety distances
├── signal_integrity.py        ← Trace/via integrity checks (stub — all methods empty, returns 0 violations)
└── emc_rules.toml             ← All thresholds and enable/disable flags
```

### Checker Interface Template

Every checker module must follow this pattern. Utilities are **injected** via `check()` parameters — never reimplemented.

```python
class NewChecker:
    """One-line description of what this checker verifies."""

    def __init__(self, board: pcbnew.BOARD, marker_layer: int,
                 config: dict, report_lines: list, verbose: bool,
                 auditor) -> None:
        self.board = board
        self.marker_layer = marker_layer
        self.config = config
        self.report_lines = report_lines
        self.verbose = verbose
        self.auditor = auditor

    def check(self, draw_marker_func, draw_arrow_func,
              get_distance_func, log_func, create_group_func) -> int:
        """Run check and return violation count."""
        log = log_func
        violations = 0
        # ... perform check, draw markers via injected functions ...
        return violations
```

### Five Injected Utilities

| Function | Purpose |
|----------|---------|
| `draw_marker_func(board, pos, msg, layer, group)` | Draw circle + text at violation |
| `draw_arrow_func(board, start, end, label, layer, group)` | Draw directional arrow |
| `get_distance_func(p1, p2) → float` | Euclidean distance (internal units) |
| `log_func(msg, force)` | Centralized verbose logging |
| `create_group_func(board, type, id, num) → PCB_GROUP` | Named group: `EMC_<Type>_<id>_<n>` |

## Key Conventions

| Area | Rule |
|------|------|
| Type hints | Mandatory on all public methods |
| Docstrings | Google style with Args/Returns |
| Strings | f-strings only — no `.format()` or `%` |
| Flow | Early returns; list comprehensions over manual loops |
| Naming | `_private_method`, `UPPER_CASE` constants |
| Config | `self.config.get('key', default)` — always provide defaults |
| Units | Always `pcbnew.FromMM()` / `pcbnew.ToMM()` — never raw integers |
| Markers | Named group `EMC_<CheckType>_<id>_<n>`, circle + optional arrow |
| Errors | Wrap each checker's `check()` in try/except, fail gracefully with `return 0` |
| Size | Module: 150–700 lines (clearance_creepage.py is a documented exception at ~1,440 lines). Function: ≤ 50 lines. Line: ≤ 100 chars |

## Anti-Patterns

- **Do NOT** define a `log()` method inside checker modules — use the injected `log_func`
- **Do NOT** create `PCB_GROUP()` manually — use `create_group_func`
- **Do NOT** use raw integers for coordinates — always convert via `pcbnew.FromMM()`/`pcbnew.ToMM()`
- **Do NOT** hardcode thresholds — read from `self.config` with defaults
- **Do NOT** import `wx` in checker modules — only the main plugin uses GUI

## Security — Pre-Commit Mandatory

Never commit absolute paths, real usernames, company names, or credentials. Use placeholders (`<YourUsername>`, `<repository_path>`). Local-only files (`sync_to_kicad.ps1`, `test_config.py`) must stay gitignored.

```powershell
# Run before every commit
git diff --cached | Select-String -Pattern "C:\\Users\\[^<]|OneDrive - "
git status --ignored | Select-String -Pattern "sync_to_kicad.ps1|test_config.py"
```

## Detailed Guides

| Topic | File |
|-------|------|
| Feature list, installation, changelog | [README.md](../README.md) |
| IEC60664-1 tables and domain configuration | [CLEARANCE_CREEPAGE_GUIDE.md](../CLEARANCE_CREEPAGE_GUIDE.md) |
| Controlled impedance calculation | [IMPEDANCE_ALGORITHM.md](../IMPEDANCE_ALGORITHM.md) |
| Via stitching rule | [VIA_STITCHING.md](../VIA_STITCHING.md) |
| Ground plane continuity | [GROUND_PLANE.md](../GROUND_PLANE.md) |
| Power trace width | [TRACE_WIDTH.md](../TRACE_WIDTH.md) |
| Decoupling capacitor proximity | [DECOUPLING.md](../DECOUPLING.md) |
| Clearance quick reference | [CLEARANCE_QUICK_REF.md](../CLEARANCE_QUICK_REF.md) |
| Clearance vs. creepage visual | [CLEARANCE_VS_CREEPAGE_VISUAL.md](../CLEARANCE_VS_CREEPAGE_VISUAL.md) |
| Manufacturer DRU presets | [JLCPCB/](../JLCPCB/), [PCBWAY/](../PCBWAY/) (standalone, not used by plugin) |
