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

# 2. TOML configuration validation (CRITICAL - prevents plugin load failures)
pytest tests/test_build_system/test_config_validation.py -v
# Or quick check: python -c "import tomllib; f = open('emc_rules.toml', 'rb'); tomllib.load(f); print('✓ Valid')"

# 3. Deploy to KiCad plugins directory (copies all files + clears __pycache__)
.\sync_to_kicad.ps1
# Note: Python 3.11+ uses built-in tomllib; Python 3.8–3.10 requires: pip install tomli

# 4. Launch KiCad 9.0 — plugin reloads automatically on next run
Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"
# Or with full debug logging + PCB screenshots (uses launch_kicad_debug.ps1 pattern):
$env:ORTHO_DEBUG = '1'; Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"

# 5. In KiCad: open board → PCB Editor → Tools → External Plugins → EMC Auditor
# Full test: baseline = 40 violations (via:0, decoupling:9, ground:4, emi:22, clearance:4, signal:1+)
```

**Deploy workflow (one-liner with TOML validation):**
```powershell
python -c "import tomllib; tomllib.load(open('emc_rules.toml', 'rb')); import ast; ast.parse(open('src/signal_integrity.py', encoding='utf-8').read())" && .\sync_to_kicad.ps1
```

### Testing Infrastructure

**Test framework:** pytest with mock `pcbnew` API (see [tests/conftest.py](../tests/conftest.py))  
**Test structure:** Mirror `src/` — one subdirectory per checker module  
**Test status:** Priority 1 & 3 tests passing (5/12), Priority 2 & 4 skipped  
**Test helpers:** [tests/helpers.py](../tests/helpers.py) provides mock factories (MockBoard, MockZone, MockTrack, MockVia, MockPad, MockFootprint)

Run tests:
```powershell
pytest tests/                    # Run all tests (currently all skipped)
pytest tests/via_stitching/     # Run specific module tests
pytest -v                        # Verbose output shows skip reasons
```

**Test stub pattern (serves as specification):**
```python
@pytest.mark.skip(reason="TODO: mock two pads at 1.5mm spacing — assert violation drawn")
def test_clearance_violation(self):
    pass
```

### Unicode Encoding in Tests (CRITICAL)

**Problem:** Windows console (cp1252 encoding) cannot handle Unicode characters used in log messages (✓, ❌, ⚠️, µ). This causes `UnicodeEncodeError: 'charmap' codec can't encode character` when printing logs during test debugging.

**Solution:** When printing logs in tests, always encode to ASCII with replacement:
```python
# ✅ CORRECT - Safe for Windows console
safe_log = log.encode('ascii', 'replace').decode('ascii')
print(safe_log)  # Special chars become '?'

# ❌ WRONG - Will crash on Windows
print(log)  # Fails if log contains ✓, ❌, ⚠️, µ
```

**Additional Unicode Issues:**
- **µ (micro) symbol:** Upper/lowercase use different Unicode code points (U+00B5 vs U+03BC)
- **Box drawing chars:** May not render in console, use ASCII art instead (e.g., `---` instead of `─`)
- **Emoji:** Avoid in production code; Windows console support varies

**When to apply:**
- All test print statements that output checker logs
- Debug logging during test development
- Never needed in production code (KiCad handles UTF-8 natively)

### Config files — two copies to keep in sync
| File | Purpose |
|------|---------|
| `emc_rules.toml` (repo) | Source of truth — edit this |
| `plugins/emc_rules.toml` (KiCad) | Live copy — overwritten by `sync_to_kicad.ps1` |

The `PluginsDir` in `sync_to_kicad.ps1` points to:
`C:\Users\<YourUsername>\<OneDrive>\Simulation tools\KiCad\9.0\3rdparty\plugins`

**Never edit the KiCad copy directly** — it will be overwritten on next sync.

### TOML Configuration Rules (CRITICAL)

**Python's `tomllib` strictly enforces TOML 1.0.0 specification.** Syntax errors prevent plugin from loading entirely.

#### Duplicate Key Rule (Most Common Error)
❌ **FORBIDDEN** — Same key twice in same section:
```toml
[ground_plane]
min_coverage_percent = 30.0
min_coverage_percent = 40.0  # ✗ Error: Cannot overwrite a value
```

✅ **ALLOWED** — Same key in different sections:
```toml
[section1]
key = "value1"

[section2]
key = "value2"  # ✓ Different sections OK
```

#### File Mode Requirement
```python
# ✅ Correct: binary mode required
with open('emc_rules.toml', 'rb') as f:
    config = tomllib.load(f)

# ❌ Wrong: text mode will fail
with open('emc_rules.toml', 'r') as f:
    config = tomllib.load(f)  # TypeError: a bytes-like object is required
```

#### Validation Workflow
**ALWAYS validate TOML before deploying:**
```powershell
# 1. Run TOML validation tests
pytest tests/test_build_system/test_config_validation.py -v

# 2. Quick syntax check
python -c "import tomllib; f = open('emc_rules.toml', 'rb'); tomllib.load(f); print('✓ Valid')"

# 3. Deploy if valid
.\sync_to_kicad.ps1
```

**Tests:** [tests/test_build_system/test_config_validation.py](../tests/test_build_system/test_config_validation.py) (36 tests)
- TOML syntax validation
- Duplicate key detection per section (100% coverage - all 10 sections)
- Required sections/keys presence (100% coverage - all 10 sections)
- Numeric range validation (percentages 0-100, distances > 0)

## Architecture

**Modular checker pattern with dependency injection.** The main plugin instantiates checker classes, injects utility functions (logging, marker drawing, distance calculation, group creation), and aggregates results.

```
src/emc_auditor_plugin.py      ← Orchestrator: loads config, runs checkers, shows report
├── src/via_stitching.py       ← GND return via proximity (IPC-2221)
├── src/decoupling.py          ← Capacitor-to-IC distance (IPC-2221)
├── src/emi_filtering.py       ← Connector filter topology (CISPR 32, IEC 61000)
├── src/ground_plane.py        ← Return path continuity under traces
├── src/clearance_creepage.py  ← IEC60664-1 / IPC2221 safety distances
├── src/signal_integrity.py    ← Trace/via integrity checks (~2,560 lines; Phases 1–2 implemented, Phases 3–4 partially stubbed)
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
- **Do NOT** access config with `self.config['key']` — always use `.get('key', default)` to prevent KeyErrors
- **Do NOT** use VECTOR2I as dict keys — convert to string first (`f"{pos.x}_{pos.y}"`)
- **Do NOT** edit the KiCad copy of `emc_rules.toml` — edit the repo root version
- **Do NOT** print Unicode characters directly in tests — use `.encode('ascii', 'replace').decode('ascii')` for Windows console compatibility
- **Do NOT** create duplicate keys in TOML sections — validate with `pytest tests/test_build_system/test_config_validation.py` before deploying
- **Do NOT** open TOML files in text mode — always use binary mode (`'rb'`) with `tomllib.load()`

## Security — Pre-Commit Mandatory

Never commit absolute paths, real usernames, company names, or credentials. Use placeholders (`<YourUsername>`, `<repository_path>`). Local-only files (`sync_to_kicad.ps1`, `test_config.py`) must stay gitignored.

```powershell
# Run before every commit
git diff --cached | Select-String -Pattern "C:\\Users\\[^<]|OneDrive - "
git status --ignored | Select-String -Pattern "sync_to_kicad.ps1|test_config.py"
```

## Pending Implementation

The following features need implementation to reach 100% completion:

### Signal Integrity Module (16/17 checks complete — 94%)

| File | Method | Line | Effort | Status |
|------|--------|------|--------|--------|
| `signal_integrity.py` | `_check_net_coupling()` | 2020-2035 | 10-12h | ❌ **STUB** — body contains 5 TODO comments, returns 0 |
| `signal_integrity.py` | `_calculate_cpw_impedance()` | 2352 | 4-6h | ⚠️ **APPROXIMATION** — Wen (1969) elliptic integral not implemented |

**Implemented in Phase 3/4:**
- ✅ `_check_net_stubs()` — connectivity graph, stub length calculation
- ✅ `_check_critical_net_isolation_differential()` — DP outer edge detection, 4W rule
- ✅ `_check_differential_pair_matching()` — length matching with skew tolerance
- ✅ `_check_differential_running_skew()` — spacing variation analysis
- ✅ `_check_reference_plane_crossing()` — via plane transitions, stitching via search
- ✅ `_check_reference_plane_changing()` — trace over plane gaps

**Helper functions (all implemented):**
- ✅ `_build_connectivity_graph()` — graph construction for stub detection
- ✅ `_calculate_trace_length()` — net length accumulation
- ✅ `_get_reference_planes()` — stackup layer mapping
- ✅ `_extract_plane_boundaries()` — zone outline extraction
- ✅ `_find_parallel_segments()` — spatial search for crosstalk (helper exists, but _check_net_coupling caller is stub)
- ✅ `_calculate_spacing_along_pair()` — DP spacing sampling

### Trace Width Module (0% complete)

| File | Status | Effort |
|------|--------|--------|
| `src/trace_width.py` | ❌ **MISSING** — file does not exist | 6-8h |
| `emc_auditor_plugin.py` | Lines 434-435 commented out | — |

**What exists:**
- ✅ Configuration section `[trace_width]` in `emc_rules.toml` (line 97)
- ✅ Documentation in `docs/TRACE_WIDTH.md`

**What's needed:**
- Implement `TraceWidthChecker` class following standard checker pattern
- IPC-2221 Table 6-1 current capacity formulas (temperature rise)
- Check power traces against minimum width for current load
- Uncomment integration in main plugin

> See [.github/instructions/signal-integrity.instructions.md](.github/instructions/signal-integrity.instructions.md) for signal integrity implementation details.

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
