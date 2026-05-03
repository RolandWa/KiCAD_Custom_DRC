# TOML Configuration Best Practices

This document outlines critical rules for editing `emc_rules.toml` to prevent plugin load failures.

## Critical Rule: No Duplicate Keys

**Python's `tomllib` (TOML 1.0.0 parser) strictly prohibits duplicate keys in the same section.**

Duplicate keys are the #1 cause of plugin load failures. When `emc_rules.toml` has duplicate keys, the plugin silently fails to load and doesn't appear in KiCad's Tools → External Plugins menu.

### ❌ INVALID - Will Cause Plugin to Fail

```toml
[ground_plane]
enabled = true
min_coverage_percent = 30.0
check_global_coverage = true
min_coverage_percent = 40.0  # ✗ Error: Cannot overwrite a value
```

**Error:** `tomllib.TOMLDecodeError: Cannot overwrite a value (at line X, column Y)`

### ✅ VALID - Same Key in Different Sections

```toml
[section1]
max_distance_mm = 10.0

[section2]
max_distance_mm = 20.0  # ✓ Different sections OK
```

Keys with the same name can exist in different sections because they map to different namespaces:
- `config['section1']['max_distance_mm'] = 10.0`
- `config['section2']['max_distance_mm'] = 20.0`

## File Mode Requirement

**TOML files MUST be opened in binary mode (`'rb'`).**

### ✅ Correct

```python
import tomllib

with open('emc_rules.toml', 'rb') as f:
    config = tomllib.load(f)
```

### ❌ Wrong

```python
# Missing 'b' flag - will crash
with open('emc_rules.toml', 'r') as f:
    config = tomllib.load(f)  # TypeError: a bytes-like object is required
```

## Validation Workflow

**ALWAYS validate TOML before deploying to KiCad.**

### Step-by-Step

```powershell
# 1. Edit emc_rules.toml in repo root
# 2. Validate configuration
pytest tests/test_build_system/test_config_validation.py -v

# 3. If all tests pass, deploy
.\sync_to_kicad.ps1

# 4. Restart KiCad to reload plugin
```

### One-Liner (validate + deploy)

```powershell
python -c "import tomllib; tomllib.load(open('emc_rules.toml', 'rb')); import ast; ast.parse(open('src/signal_integrity.py', encoding='utf-8').read())" && .\sync_to_kicad.ps1
```

### Quick Syntax Check

```powershell
python -c "import tomllib; f = open('emc_rules.toml', 'rb'); tomllib.load(f); print('✓ TOML syntax valid')"
```

## Test Suite

**Location:** `tests/test_build_system/test_config_validation.py`  
**Tests:** 36 total covering:

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestTOMLSyntax` | 12 | Validates TOML parses + checks all 10 sections for duplicate keys |
| `TestRequiredSections` | 10 | Ensures all 10 sections exist (100% coverage) |
| `TestCriticalKeys` | 10 | Validates critical configuration keys exist |
| `TestNumericRanges` | 3 | Checks numeric values are within valid ranges |
| `TestTOMLCompliance` | 2 | Documents TOML 1.0.0 specification rules |

**Coverage:** 100% of all TOML sections tested for duplicate keys and existence.

### Duplicate Key Detection

The test suite includes per-section duplicate key detection:

```python
def test_no_duplicate_keys_in_ground_plane(self):
    """[ground_plane] section must have unique keys (common error site)."""
    self._check_section_for_duplicates('ground_plane')
```

This parses the TOML file line-by-line to detect duplicate keys within each section, providing clear error messages:

```
Duplicate key 'min_coverage_percent' in [ground_plane] at line 178
TOML 1.0.0 prohibits duplicate keys in same section.
```

## Common Errors

### Error: "Cannot overwrite a value"

**Symptom:** Plugin doesn't appear in KiCad after enabling new checks  
**Cause:** Duplicate key in TOML configuration  
**Solution:**

1. Run validation tests to identify duplicate:
   ```powershell
   pytest tests/test_build_system/test_config_validation.py -v
   ```

2. Check error message for line number:
   ```
   Duplicate key 'min_coverage_percent' in [ground_plane] at line 178
   ```

3. Open `emc_rules.toml` and remove duplicate definition

4. Re-validate and deploy:
   ```powershell
   python -c "import tomllib; tomllib.load(open('emc_rules.toml', 'rb'))" && .\sync_to_kicad.ps1
   ```

5. Restart KiCad

### Error: "TypeError: a bytes-like object is required"

**Symptom:** Python script crashes when loading TOML  
**Cause:** File opened in text mode instead of binary mode  
**Solution:** Change `open('file.toml', 'r')` to `open('file.toml', 'rb')`

### Symptom: Plugin Icon Missing After Config Change

**Cause:** Invalid TOML syntax preventing plugin from loading  
**Diagnosis:**

```powershell
# Check KiCad's deployed copy
cd "C:\Users\<YourUsername>\<OneDrive>\Simulation tools\KiCad\9.0\3rdparty\plugins\com_github_RolandWa_emc_auditor"
python -c "import tomllib; f = open('emc_rules.toml', 'rb'); tomllib.load(f); print('OK')"
```

If this fails, the TOML syntax is invalid and must be fixed in the repo root, then re-deployed.

## Configuration File Workflow

**Two copies of `emc_rules.toml` exist:**

| Location | Purpose | Edit? |
|----------|---------|-------|
| `<repo>/emc_rules.toml` | Source of truth | ✅ YES |
| `<KiCad>/plugins/.../emc_rules.toml` | Live copy | ❌ NO |

**Workflow:**
1. Edit `<repo>/emc_rules.toml`
2. Validate with pytest or quick check
3. Run `sync_to_kicad.ps1` to deploy
4. Restart KiCad to reload plugin

**Never edit the KiCad copy directly** — it will be overwritten on next sync.

## Best Practices Checklist

Before committing changes to `emc_rules.toml`:

- [ ] Run validation tests: `pytest tests/test_build_system/test_config_validation.py -v`
- [ ] Check for duplicate keys in modified sections
- [ ] Verify numeric ranges (percentages 0-100, distances > 0)
- [ ] Test plugin loads in KiCad after deployment
- [ ] Verify all enabled checks appear in EMC Auditor report

## References

- **TOML 1.0.0 Spec:** https://toml.io/en/v1.0.0
- **Python tomllib:** https://docs.python.org/3/library/tomllib.html
- **Test Suite:** [tests/test_build_system/test_config_validation.py](../tests/test_build_system/test_config_validation.py)
- **Copilot Instructions:** [.github/copilot-instructions.md](../.github/copilot-instructions.md)

---

**Last Updated:** 2026-05-03  
**Maintainer:** EMC Auditor Development Team
