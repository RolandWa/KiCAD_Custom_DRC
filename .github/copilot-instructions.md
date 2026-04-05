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
# 1. Syntax check (no KiCad needed)
python -c "import ast; ast.parse(open('src/signal_integrity.py', encoding='utf-8').read()); print('OK')"
# Or: python -m py_compile src/emc_auditor_plugin.py

# 2. Deploy to KiCad plugins directory (copies all 9 files + clears __pycache__)
.\sync_to_kicad.ps1
# Note: Python 3.11+ uses built-in tomllib; Python 3.8–3.10 requires: pip install tomli

# 3. Launch KiCad 9.0 — plugin reloads automatically on next run
Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"
# Or with full debug logging + PCB screenshots (uses launch_kicad_debug.ps1 pattern):
$env:ORTHO_DEBUG = '1'; Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"

# 4. In KiCad: open board → PCB Editor → Tools → External Plugins → EMC Auditor
# Full test: baseline = 40 violations (via:0, decoupling:9, ground:4, emi:22, clearance:4, signal:1+)
```

**Deploy workflow (one-liner):**
```powershell
python -c "import ast; ast.parse(open('src/signal_integrity.py',encoding='utf-8').read())" && .\sync_to_kicad.ps1
```

No automated test suite yet. Validation is manual against the baseline board.

### Config files — two copies to keep in sync
| File | Purpose |
|------|---------|
| `emc_rules.toml` (repo) | Source of truth — edit this |
| `plugins/emc_rules.toml` (KiCad) | Live copy — overwritten by `sync_to_kicad.ps1` |

The `PluginsDir` in `sync_to_kicad.ps1` points to:
`C:\Users\<YourUsername>\<OneDrive>\Simulation tools\KiCad\9.0\3rdparty\plugins`

**Never edit the KiCad copy directly** — it will be overwritten on next sync.

## Architecture

**Modular checker pattern with dependency injection.** The main plugin instantiates checker classes, injects utility functions (logging, marker drawing, distance calculation, group creation), and aggregates results.

```
src/emc_auditor_plugin.py      ← Orchestrator: loads config, runs checkers, shows report
├── src/via_stitching.py       ← GND return via proximity (IPC-2221)
├── src/decoupling.py          ← Capacitor-to-IC distance (IPC-2221)
├── src/emi_filtering.py       ← Connector filter topology (CISPR 32, IEC 61000)
├── src/ground_plane.py        ← Return path continuity under traces
├── src/clearance_creepage.py  ← IEC60664-1 / IPC2221 safety distances
├── src/signal_integrity.py    ← Trace/via integrity checks (~2,400 lines; Phases 1–2 implemented, Phases 3–4 partially stubbed)
└── emc_rules.toml             ← All thresholds and enable/disable flags (root)
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
| Size | Module: 150–700 lines (clearance_creepage.py ~2,180 lines and signal_integrity.py ~2,400 lines are documented exceptions). Function: ≤ 50 lines. Line: ≤ 100 chars |

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
| IEC60664-1 tables and domain configuration | [docs/CLEARANCE_CREEPAGE_GUIDE.md](../docs/CLEARANCE_CREEPAGE_GUIDE.md) |
| Controlled impedance calculation | [docs/IMPEDANCE_ALGORITHM.md](../docs/IMPEDANCE_ALGORITHM.md) |
| Via stitching rule | [docs/VIA_STITCHING.md](../docs/VIA_STITCHING.md) |
| Ground plane continuity | [docs/GROUND_PLANE.md](../docs/GROUND_PLANE.md) |
| Power trace width | [docs/TRACE_WIDTH.md](../docs/TRACE_WIDTH.md) |
| Decoupling capacitor proximity | [docs/DECOUPLING.md](../docs/DECOUPLING.md) |
| Clearance quick reference | [docs/CLEARANCE_QUICK_REF.md](../docs/CLEARANCE_QUICK_REF.md) |
| Clearance vs. creepage visual | [docs/CLEARANCE_VS_CREEPAGE_VISUAL.md](../docs/CLEARANCE_VS_CREEPAGE_VISUAL.md) |
| Manufacturer DRU presets | [JLCPCB/](../JLCPCB/), [PCBWAY/](../PCBWAY/) (standalone, not used by plugin) |
