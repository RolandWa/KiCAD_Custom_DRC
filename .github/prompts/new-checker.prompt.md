---
description: "Scaffold a complete EMC checker module from a specification. Use when adding a new checker to the EMC Auditor Plugin."
name: "New Checker"
argument-hint: "Checker name, EMC standard (e.g. IPC-2221), TOML section name, and what it detects"
agent: "agent"
---

Scaffold a complete EMC checker module for the KiCAD EMC Auditor Plugin.

## Inputs

The user will provide (extract from the argument or ask if missing):
- **Checker name**: PascalCase class name, e.g. `TraceWidthChecker`
- **File name**: snake_case, e.g. `trace_width.py`
- **EMC standard**: e.g. `IPC-2221`, `CISPR 32`, `IEC 61000-4`
- **TOML section**: key to read from `emc_rules.toml`, e.g. `[trace_width]`
- **What it detects**: one-sentence description of the violation

## Steps

1. **Read** [emc_auditor_plugin.py](../emc_auditor_plugin.py) to understand how existing checkers are instantiated and called (search for `DecouplingChecker` or `ViaStitchingChecker` as reference).

2. **Read** [decoupling.py](../decoupling.py) as a canonical simple checker example.

3. **Read** [emc_rules.toml](../emc_rules.toml) to see the existing TOML structure and add the new section.

4. **Create** `<file_name>.py` following the required checker interface:
   - Class constructor accepts: `board`, `marker_layer`, `config`, `report_lines`, `verbose`, `auditor`
   - `check()` accepts the five injected utilities and returns `int` (violation count)
   - All check logic in private `_check_*()` methods, each ≤ 50 lines
   - Use `self.config.get('key', default)` for all thresholds — never hardcode
   - Use `pcbnew.FromMM()` / `pcbnew.ToMM()` — never raw integers
   - Use injected `log_func`, `draw_marker_func`, `create_group_func` — never reimplement
   - Wrap the entire `check()` body in `try/except Exception` returning `0` on failure
   - Google-style docstrings, f-strings only, type hints on all public methods

5. **Update** `emc_rules.toml` — add a new `[<section>]` block with:
   - `enabled = true`
   - All numeric thresholds used by the checker, with sensible defaults and inline comments citing the standard

6. **Update** `emc_auditor_plugin.py` — integrate the new checker:
   - Import the module
   - Instantiate the checker in the same pattern as existing ones
   - Call `checker.check(...)` and add its return value to the violation total
   - Add the checker's count to the summary report line

7. **Verify** syntax: run `python -m py_compile <file_name>.py` and confirm no errors.

## Output

- New file: `<file_name>.py`
- Updated: `emc_rules.toml` (new section)
- Updated: `emc_auditor_plugin.py` (import + instantiation + report)

Do NOT create documentation markdown files unless explicitly asked.
