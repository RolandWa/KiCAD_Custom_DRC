---
description: "Build, deploy, and test the EMC Auditor plugin. Handles syntax validation, packaging, installation to KiCad, and launching KiCad for testing."
name: "Build and Deploy"
argument-hint: "Action: 'build', 'deploy', 'test', or 'full' (build+deploy+launch KiCad)"
agent: "none"
---

Build, package, and deploy the EMC Auditor plugin to KiCad.

## Available Actions

### Quick Deploy (Fast Iteration)
Use `sync_to_kicad.ps1` for rapid iteration during development:
```powershell
.\sync_to_kicad.ps1
```
- Copies 9 files from `src/` to KiCad plugins directory
- Clears `__pycache__` to force reload
- Fastest option (no ZIP creation, no metadata generation)
- **Requires local setup** — file is `.gitignored`, must copy from `.template` and configure

### Full Build (Packaging)
Use `build.py` for creating distributable packages:
```powershell
python build.py              # Build package directory + ZIP
python build.py --deploy     # Build + install to local KiCad
python build.py --clean      # Remove build directory
```
- Creates `build/com_github_RolandWa_emc_auditor/` directory
- Generates `metadata.json` (KiCad PCM manifest)
- Creates `com_github_RolandWa_emc_auditor.zip` for "Install from File…"
- Handles OneDrive path resolution via `pcbnew.json`

## Deployment Workflow

### 1. Syntax Validation (Always First)
```powershell
# Validate single file
python -m py_compile src/signal_integrity.py

# Validate all modules
python -m py_compile src/*.py
```
**Why**: Catches syntax errors before deployment — KiCad's error messages are cryptic.

### 2. Choose Deployment Method

**During active development** (making frequent changes):
```powershell
python -m py_compile src/*.py && .\sync_to_kicad.ps1
```

**For distribution** (creating package for others):
```powershell
python build.py
# Output: build/com_github_RolandWa_emc_auditor.zip
```

**For local install + testing**:
```powershell
python build.py --deploy
```

### 3. Launch KiCad

**Standard launch**:
```powershell
Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"
```

**Debug mode** (enables verbose logging + PCB screenshots):
```powershell
$env:ORTHO_DEBUG = '1'
Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"
```

### 4. Test in KiCad
1. Open board → PCB Editor
2. Tools → External Plugins → EMC Auditor
3. Check console output for errors
4. Verify violations drawn on User.Comments layer
5. Expected baseline: 40 violations (via:0, decoupling:9, ground:4, emi:22, clearance:4, signal:1+)

## One-Liner Workflows

**Deploy and test** (full cycle):
```powershell
python -m py_compile src/*.py && .\sync_to_kicad.ps1 && Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"
```

**Deploy with debug mode**:
```powershell
python -m py_compile src/*.py && .\sync_to_kicad.ps1 && ($env:ORTHO_DEBUG = '1'; Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe")
```

**Build package for distribution**:
```powershell
python build.py --clean && python build.py
```

## Troubleshooting

### "Module not found" in KiCad
**Cause**: Missing file in deployment or import error
**Fix**:
1. Check all 9 files copied: `ls "C:\Users\<User>\<OneDrive>\Simulation tools\KiCad\9.0\3rdparty\plugins\com_github_RolandWa_emc_auditor"`
2. Clear `__pycache__`: `Remove-Item -Recurse -Force <plugins_dir>\__pycache__`
3. Re-deploy: `.\sync_to_kicad.ps1`

### "KeyError: 'some_config_key'"
**Cause**: Config key accessed with `self.config['key']` instead of `.get('key', default)`
**Fix**: Use `self.config.get('key', default_value)` in checker module

### Changes Not Reflected in KiCad
**Cause**: KiCad cached old plugin code
**Fix**:
1. Close KiCad completely
2. Clear `__pycache__`: `Remove-Item -Recurse -Force <plugins_dir>\__pycache__`
3. Re-deploy and relaunch

### OneDrive Sync Conflicts
**Cause**: build.py or sync script writing during OneDrive sync
**Fix**: build.py handles this — retries with rename fallback

## Pre-Deployment Checklist

Before deploying:
- [ ] Syntax validated: `python -m py_compile src/*.py`
- [ ] Config keys use `.get()` with defaults
- [ ] No absolute paths (use `<YourUsername>` placeholder)
- [ ] All imports use try/except fallback pattern
- [ ] Unit conversion uses `pcbnew.FromMM()` / `pcbnew.ToMM()`
- [ ] Error handling wraps check methods
- [ ] Phase tracking updated (if implementing stubs)

## Post-Deployment Validation

After deploying:
1. **Plugin appears in menu**: Tools → External Plugins → EMC Auditor ✅
2. **No import errors**: Check KiCad console (View → Console)
3. **Baseline violations match**: Run on test board → 40 expected violations
4. **Report dialog opens**: Ctrl+S saves, Escape closes
5. **Markers visible**: User.Comments layer shows circles + text

## Files Deployed

When you deploy, these files must be present in the KiCad plugins directory:
```
com_github_RolandWa_emc_auditor/
├── __init__.py                 (KiCad ActionPlugin registration)
├── emc_auditor_plugin.py       (main orchestrator)
├── via_stitching.py            (checker module)
├── decoupling.py               (checker module)
├── emi_filtering.py            (checker module)
├── ground_plane.py             (checker module)
├── clearance_creepage.py       (checker module)
├── signal_integrity.py         (checker module)
├── emc_rules.toml              (configuration)
└── icon.png / metadata.json    (optional, for PCM)
```

## Security Note

**Never commit** `sync_to_kicad.ps1` (contains absolute paths) — it's `.gitignored`.  
Copy from `sync_to_kicad.ps1.template` and configure for your environment.

---

## Quick Reference

| Task | Command |
|------|---------|
| Syntax check | `python -m py_compile src/*.py` |
| Fast deploy | `.\sync_to_kicad.ps1` |
| Build package | `python build.py` |
| Deploy + test | `python build.py --deploy` |
| Launch KiCad | `Start-Process "C:\Program Files\KiCad\9.0\bin\kicad.exe"` |
| Debug mode | `$env:ORTHO_DEBUG = '1'; Start-Process ...` |
| Full cycle | `python -m py_compile src/*.py && .\sync_to_kicad.ps1 && Start-Process ...` |
