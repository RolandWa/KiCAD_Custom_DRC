---
description: "Implement a stubbed checker method marked with TODO. Use when completing phased implementation of signal integrity or other checker modules."
name: "Implement Stub"
argument-hint: "Module name and method name (e.g., 'signal_integrity._check_net_stubs')"
agent: "agent"
---

Implement a stubbed method in a checker module following project conventions and phased roadmap.

## Inputs

Extract from argument or ask:
- **Module**: Checker module name (e.g., `signal_integrity`, `clearance_creepage`)
- **Method**: Method name to implement (e.g., `_check_net_stubs`, `_check_reference_plane_crossing`)

## Steps

1. **Read the stub** in `src/<module>.py` to understand:
   - Method signature and return type
   - TODO comments describing required functionality
   - Any helper methods listed as dependencies
   - Phase number and difficulty estimate

2. **Check dependencies** — if the method requires helper functions (e.g., `_build_connectivity_graph()`):
   - **If helpers are stubs**: Implement helpers first (may require recursive implementation)
   - **If helpers exist**: Verify their signatures and return types

3. **Read related documentation**:
   - Check `docs/<TOPIC>.md` for algorithmic specifications
   - Review `.github/instructions/<module>.instructions.md` for implementation notes
   - Check `emc_rules.toml` for config keys the method should read

4. **Implement following conventions**:
   - Use dependency injection — call `self.log()`, `draw_marker_func()`, etc. (never reimplement)
   - Read all thresholds from `self.config.get('key', default)` with fallback values
   - Convert units with `pcbnew.FromMM()` / `pcbnew.ToMM()` — never raw integers
   - Keep functions ≤ 50 lines — extract helper methods for complex logic
   - Add violations to groups: `create_group_func(board, type, id, num)`
   - Return `int` (violation count)

5. **Add error handling**:
   ```python
   try:
       # Implementation logic
   except Exception as e:
       self.log(f"Error in _check_xxx: {e}", force=True)
       return 0  # Graceful failure
   ```

6. **Update phase tracking** in the module docstring:
   - Change `□` to `✅` for the implemented check
   - Update `[code □]` to `[code ✓]`
   - Change `[test □]` to `[test 🔬]` (tests still needed)

7. **Add TOML config keys** if needed:
   - Add new keys under `[<module>]` or `[<module>.checks]`
   - Include inline comments citing standards (e.g., `# IPC-2221 Section 6.2`)
   - Provide sensible defaults

8. **Verify syntax**:
   ```powershell
   python -m py_compile src/<module>.py
   ```

## Output

- Updated `src/<module>.py` with implemented method
- Updated `emc_rules.toml` if new config keys added
- Syntax validated (no import errors)

Do NOT:
- Create documentation files (link to existing docs instead)
- Implement tests (separate task via `/write-test` prompt)
- Deploy to KiCad (use `sync_to_kicad.ps1` manually after review)
