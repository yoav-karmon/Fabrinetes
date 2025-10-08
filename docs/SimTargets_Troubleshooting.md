# SimTargets Troubleshooting Guide

This guide helps you diagnose and fix common issues when working with SimTargets in HDLForge.

## Table of Contents

- [Command Line Issues](#command-line-issues)
- [Configuration Issues](#configuration-issues)
- [Build Issues](#build-issues)
- [Simulation Issues](#simulation-issues)
- [Output Issues](#output-issues)
- [Environment Issues](#environment-issues)

## Command Line Issues

### Error: SimTargetName must be specified

**Symptom:**
```
Available SimTargetNames: main, debug, test
[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>
```

**Cause:** The `--SimTargetName` parameter was not provided.

**Solution:**
```bash
# Add --SimTargetName parameter
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
```

**Prevention:** Always include `--SimTargetName` in your Verilator commands.

---

### Error: SimTargetName 'X' not found

**Symptom:**
```
Available SimTargetNames: main, debug, test
[!x!]  SimTargetName 'typo' not found in verilator_settings['sim_targets']
```

**Cause:** The specified SimTargetName doesn't exist in your configuration file.

**Solution:**
1. Check available targets listed in the error message
2. Verify your `.hdlforge.toml` file:
   ```toml
   [verilator_settings.sim_targets.main]  # This is the SimTargetName
   top_module = "..."
   ```
3. Use one of the available target names

**Common Mistakes:**
- Typo in target name (e.g., `mian` instead of `main`)
- Case mismatch (SimTargets are case-sensitive)
- Target not defined in TOML file

---

### Error: 'Verilator' did not receive required positional arguments: 'project'

**Symptom:**
```
'Verilator' did not receive required positional arguments: 'project'
```

**Cause:** Missing `--project` parameter.

**Solution:**
```bash
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
```

---

## Configuration Issues

### Error: KeyError: 'top_module'

**Symptom:**
```python
KeyError: 'top_module'
```

**Cause:** Required field `top_module` is missing from SimTarget configuration.

**Solution:**
Add the required field to your SimTarget:
```toml
[verilator_settings.sim_targets.main]
top_module = "my_module_name"  # Add this line
python_file = "tests/test_main.py"
```

**Required Fields:**
- `top_module` (string)
- `python_file` (string)

---

### Error: KeyError: 'python_file'

**Symptom:**
```python
KeyError: 'python_file'
```

**Cause:** Required field `python_file` is missing from SimTarget configuration.

**Solution:**
```toml
[verilator_settings.sim_targets.main]
top_module = "my_module"
python_file = "tests/test_main.py"  # Add this line
```

---

### Error: Invalid TOML syntax

**Symptom:**
```
tomllib.TOMLDecodeError: Invalid statement (at line X, column Y)
```

**Cause:** Syntax error in TOML configuration file.

**Common Issues:**
1. Missing quotes around strings
2. Invalid table names
3. Duplicate keys

**Solution:**
Check your TOML syntax:
```toml
# Correct
[verilator_settings.sim_targets.main]
top_module = "my_module"  # String needs quotes

# Incorrect
[verilator_settings.sim_targets.main]
top_module = my_module  # Missing quotes
```

**Tools to Help:**
- Use a TOML validator online
- Check file with `python -m tomllib <file.toml>`

---

## Build Issues

### Error: Verilator compilation failed

**Symptom:**
```
[!x!]  Verilator build/simulation failed!
Error: <verilator error message>
```

**Cause:** HDL source code has syntax errors or compilation issues.

**Solution:**
1. Read the Verilator error message carefully
2. Fix the indicated HDL file
3. Common issues:
   - Missing semicolons
   - Undefined signals/modules
   - Port connection mismatches
   - Include path issues

**Debug Steps:**
1. Enable verbose output (if available)
2. Check all source files are listed
3. Verify include paths are correct
4. Try building a simpler module first

---

### Error: Module not found during compilation

**Symptom:**
```
Error: Cannot find module 'my_submodule'
```

**Cause:** Source file containing the module is not included or include paths are incorrect.

**Solution:**
1. Check `[[sources.files]]` section includes all required files
2. Verify `includes_paths` in `verilator_settings`:
   ```toml
   [verilator_settings]
   includes_paths = ["$REPO_TOP/rtl/includes"]
   ```
3. Ensure source files are marked with `verilator = true`

---

### Error: Build artifacts not found

**Symptom:**
```
Error: Cannot find Verilator executable
```

**Cause:** Build step was not run or failed.

**Solution:**
```bash
# Run build step first
hdlforge Verilator --project myproject.hdlforge.toml --step build --SimTargetName main

# Then run simulation
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
```

---

## Simulation Issues

### Error: Python test file not found

**Symptom:**
```
ModuleNotFoundError: No module named 'test_main'
```

**Cause:** The `python_file` path is incorrect or file doesn't exist.

**Solution:**
1. Verify the file exists:
   ```bash
   ls tests/test_main.py
   ```
2. Check the path in your TOML:
   ```toml
   [verilator_settings.sim_targets.main]
   python_file = "tests/test_main.py"  # Path relative to project directory
   ```
3. Ensure path is relative to the project directory, not absolute

---

### Error: Test function not found

**Symptom:**
```
Error: Test 'test_typo' not found in module
```

**Cause:** The `test_name` doesn't match any test function in the Python file.

**Solution:**
1. Check test functions in your Python file:
   ```python
   @cocotb.test()
   async def test_basic(dut):  # This is the test name
       pass
   ```
2. Update TOML to match:
   ```toml
   [verilator_settings.sim_targets.main]
   test_name = "test_basic"  # Must match function name
   ```
3. Or omit `test_name` to run all tests

---

### Error: PYTHONPATH import errors

**Symptom:**
```
ModuleNotFoundError: No module named 'my_test_utils'
```

**Cause:** Test utility modules are not in PYTHONPATH.

**Solution:**
Add paths to `PYTHONPATH` in SimTarget:
```toml
[verilator_settings.sim_targets.main]
top_module = "my_module"
python_file = "tests/test_main.py"
PYTHONPATH = [
    "$REPO_TOP/tests/lib",
    "$REPO_TOP/tests/utils"
]
```

---

### Error: Simulation hangs or times out

**Symptom:**
Simulation runs indefinitely or times out without completing.

**Possible Causes:**
1. Clock not running
2. Test waiting for condition that never occurs
3. Missing reset logic
4. Deadlock in HDL design

**Debug Steps:**
1. Check clock is started:
   ```python
   clock = Clock(dut.clk, 10, units="ns")
   cocotb.start_soon(clock.start())
   ```
2. Add timeout to test:
   ```python
   await with_timeout(RisingEdge(dut.signal), 1000, 'ns')
   ```
3. Enable waveform tracing to see what's happening
4. Add debug prints to see where test hangs

---

## Output Issues

### Issue: No waveform file generated

**Symptom:**
`dump.vcd` file is not created after simulation.

**Cause:** Waveform generation is not enabled.

**Solution:**
1. Add `--trace` to build_args:
   ```toml
   [verilator_settings.sim_targets.main]
   build_args = ["--trace"]
   ```
2. Ensure `waves=True` in the code (default in HDLForge)

---

### Issue: Cannot find simulation output

**Symptom:**
Cannot locate `dump.vcd` or test results.

**Location:**
Simulation output is in:
```
<build_dir>/<SimTargetName>/
```

**Example:**
```bash
# For SimTargetName "main" with build_dir "_verilator"
ls _verilator/main/dump.vcd
```

**Solution:**
```bash
# Check build directory setting
grep "build_dir" myproject.hdlforge.toml

# List output directory
ls -la _verilator/main/
```

---

### Issue: VCD file is empty or corrupted

**Symptom:**
`dump.vcd` exists but is empty or cannot be opened in GTKWave.

**Possible Causes:**
1. Simulation crashed before writing
2. No signals were traced
3. Simulation didn't run long enough

**Solution:**
1. Check test actually ran:
   ```python
   @cocotb.test()
   async def test_basic(dut):
       dut._log.info("Test started")  # Add logging
       # ... test code ...
       dut._log.info("Test completed")
   ```
2. Add explicit signal tracing if needed
3. Ensure simulation runs for some time:
   ```python
   await Timer(100, units='ns')
   ```

---

## Environment Issues

### Error: REPO_TOP not set

**Symptom:**
```
KeyError: 'REPO_TOP'
```

**Cause:** Required environment variable `REPO_TOP` is not set.

**Solution:**
```bash
# Set REPO_TOP to your repository root
export REPO_TOP=/path/to/your/repo

# Or add to your shell profile
echo 'export REPO_TOP=/path/to/your/repo' >> ~/.bashrc
```

---

### Error: Path expansion failed

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: '$REPO_TOP/rtl/...'
```

**Cause:** Environment variable not expanded or not set.

**Solution:**
1. Ensure REPO_TOP is exported:
   ```bash
   export REPO_TOP=/path/to/repo
   echo $REPO_TOP  # Should print the path
   ```
2. Check TOML uses correct syntax:
   ```toml
   includes_paths = ["$REPO_TOP/rtl/includes"]  # Correct
   # Not: "${REPO_TOP}/..." or other shell expansions
   ```

---

## Diagnostic Commands

### Check Available SimTargets

```bash
# This will fail but show available targets
hdlforge Verilator --project myproject.hdlforge.toml --step sim
```

### Verify Project File

```bash
# Check TOML syntax
python3 -m tomllib myproject.hdlforge.toml

# View SimTargets configuration
grep -A 10 "sim_targets" myproject.hdlforge.toml
```

### Check Build Output

```bash
# List build directory
ls -la _verilator/

# Check for Verilator executable
ls -la _verilator/V*
```

### Check Simulation Output

```bash
# List simulation output for specific target
ls -la _verilator/main/

# View VCD file info
file _verilator/main/dump.vcd
```

### Verify Environment

```bash
# Check required environment variables
echo $REPO_TOP
echo $HDLFORGE_ORIG_PATH

# Check Python environment
which python3
python3 --version
python3 -c "import cocotb; print(cocotb.__version__)"
```

## Getting Help

If you're still stuck after trying these troubleshooting steps:

1. **Check the error message carefully** - It often contains the solution
2. **Review the documentation**:
   - [SimTargets Guide](SimTargets_Guide.md)
   - [SimTargets Quick Reference](SimTargets_Quick_Reference.md)
   - [SimTargets Architecture](SimTargets_Architecture.md)
3. **Enable verbose output** if available
4. **Check the Verilator/Cocotb logs** for detailed error information
5. **Create a minimal reproducer** - Simplify to the smallest example that shows the problem
6. **Open an issue** on GitHub with:
   - Full error message
   - Your `.hdlforge.toml` SimTarget configuration
   - Steps to reproduce
   - Environment information (OS, tool versions)

## Common Patterns for Success

### Pattern 1: Incremental Testing

```bash
# 1. Test build only
hdlforge Verilator --project test.hdlforge.toml --step build --SimTargetName main

# 2. Test simulation separately
hdlforge Verilator --project test.hdlforge.toml --step sim --SimTargetName main

# 3. Combine when both work
hdlforge Verilator --project test.hdlforge.toml --step build sim --SimTargetName main
```

### Pattern 2: Start Simple

```toml
# Start with minimal configuration
[verilator_settings.sim_targets.simple]
top_module = "my_module"
python_file = "tests/test_simple.py"

# Then add complexity
[verilator_settings.sim_targets.advanced]
top_module = "my_module"
python_file = "tests/test_advanced.py"
test_name = "test_scenario_1"
build_args = ["--trace", "-O3"]
defines = {"DEBUG": "1"}
parameters = {"WIDTH": "32"}
PYTHONPATH = ["$REPO_TOP/tests/lib"]
```

### Pattern 3: Use Clean Builds

```bash
# If things are broken, try a clean build
hdlforge Verilator --project test.hdlforge.toml --step build --SimTargetName main --clean
```

## See Also

- [SimTargets Guide](SimTargets_Guide.md) - Complete user guide
- [SimTargets Quick Reference](SimTargets_Quick_Reference.md) - Quick command reference
- [SimTargets Architecture](SimTargets_Architecture.md) - Technical details
