# Container HDLForge Test Documentation

## Overview

This document describes how to test HDLForge compilation and simulation in the Fabrinetes Docker container without requiring interactive attachment.

## Test Environment

- **Container**: `fabrinetes-fpga-dev-1` (image: `fabrinetes-dev-cocotb-verilator-working-fpga-dev-1:firefox_cocotb_verilator_working`)
- **Test Project**: `examples/addr_32bit` (32-bit Address Generator)
- **HDLForge Location**: `/opt/project_setup/hdlforge`
- **Verilator Version**: 5.020

## How HDLForge Gets Into PATH

### Container Setup Process:

1. **System-wide PATH Setup**: `/etc/profile.d/init_env.sh`
   ```bash
   export PATH="/opt/vivado/bin:/opt/project_setup:$HOME/.local/bin:$PATH"
   export XILINXD_LICENSE_FILE="/home/ykarmon/repos/phy_project/Xilinx.lic"
   ```

2. **HDLForge Executable**: `/opt/project_setup/hdlforge`
   - **Type**: Bash script (executable)
   - **Purpose**: Wrapper script that calls Python tasks
   - **Dependencies**: Requires Python environment and project setup

3. **PATH Resolution**: 
   - `/opt/project_setup` is added to PATH by system profile
   - `hdlforge` script is executable in that directory
   - Available as `hdlforge` command when PATH is properly set

### Why `.bashrc` is Critical:

The `.bashrc` file sources `/etc/profile.d/init_env.sh` which sets up the PATH:
```bash
# ~/.bashrc: executed by bash(1) for non-login shells.
source /etc/profile.d/init_env.sh
```

**Without `.bashrc`**: PATH doesn't include `/opt/project_setup` → `hdlforge` command not found
**With `.bashrc`**: PATH includes `/opt/project_setup` → `hdlforge` command available

## Key Finding: Using `-i` Flag for Interactive Shell

The critical discovery is that **`.bashrc` does NOT run with default `docker exec`** but **DOES run with the `-i` (interactive) flag**.

### Shell Behavior Comparison

| Command | Shell Type | `.bashrc` Runs | Environment Setup |
|---------|------------|----------------|-------------------|
| `docker exec container bash -c "cmd"` | Non-interactive | ❌ No | ❌ No |
| `docker exec -i container bash -c "cmd"` | Non-interactive | ❌ No | ❌ No |
| `docker exec container bash -i -c "cmd"` | Interactive | ✅ Yes | ✅ Yes |
| `docker exec container bash -l -c "cmd"` | Login | ✅ Yes* | ✅ Yes* |

*Login shell runs `.bash_profile` which may source `.bashrc`

## Test Commands

### Basic HDLForge Test
```bash
docker exec -i fabrinetes-fpga-dev-1 bash -c "cd ~/repo/Fabrinetes/examples/addr_32bit && bash -i -c 'hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName basic_test'"
```

### Reset Test
```bash
docker exec -i fabrinetes-fpga-dev-1 bash -c "cd ~/repo/Fabrinetes/examples/addr_32bit && bash -i -c 'hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName reset_test'"
```

## Test Results

### ✅ Successful Execution

**Environment Setup (done by `.bashrc`):**
- `.bashrc` loaded successfully
- `REPO_TOP` set to `/home/ykarmon/repo/Fabrinetes`
- Environment validation passed
- PYTHONPATH configured correctly

**Compilation:**
- Verilator compilation successful
- Executable `addr_32bit_top` created
- Build completed without errors

**Simulation Results:**

| Test Name | Status | Sim Time | Real Time | Performance Ratio |
|-----------|--------|----------|-----------|-------------------|
| `test_basic_functionality` | PASS | 130.00ns | 0.00s | 112,914.42 ns/s |
| `test_reset_behavior` | PASS | 70.00ns | 0.00s | 104,560.35 ns/s |

**Generated Files:**
- VCD trace files: `dump.vcd`
- Results XML: `results.xml`
- Coverage data: `coverage.dat`

## Project Structure

```
examples/addr_32bit/
├── addr_32bit.hdlforge.toml    # HDLForge configuration
├── src/
│   └── addr_32bit.sv           # SystemVerilog source
├── tests/
│   └── test_addr_32bit.py      # Cocotb testbench
└── _verilator/                 # Build directory
    ├── addr_32bit_top          # Compiled executable
    ├── basic_test/              # Test results
    └── reset_test/             # Test results
```

## Configuration Details

### HDLForge Configuration (`addr_32bit.hdlforge.toml`)
- **Project Name**: `addr_32bit`
- **Top Module**: `addr_32bit_top`
- **Build Directory**: `_verilator`
- **Simulation Targets**: 6 different test scenarios
- **Build Args**: `--trace`, `--timing`, `--coverage`

### Test Scenarios
1. `basic_test` - Basic functionality
2. `reset_test` - Reset behavior
3. `enable_test` - Enable/disable functionality
4. `increment_test` - Address increment testing
5. `edge_cases_test` - Boundary conditions
6. `random_test` - Random value testing

## Troubleshooting

### Common Issues

**Issue**: `hdlforge: command not found`
**Solution**: Use full path `/opt/project_setup/hdlforge` or ensure interactive shell with `-i` flag

**Issue**: `REPO_TOP` not set
**Solution**: Use `bash -i -c` to load `.bashrc`

**Issue**: Environment validation fails
**Solution**: Ensure running from correct directory (`~/repo/Fabrinetes/examples/addr_32bit`)

### Warning Messages (Non-Critical)
- `Repository tools not found in PATH` - Expected, tools directory missing
- `Missing /home/ykarmon/repo/Fabrinetes/tools/update_paths.sh` - Expected
- `Missing /home/ykarmon/repo/Fabrinetes/tools/tool_box/tool_box.sh` - Expected

## Best Practices

1. **Always use `-i` flag** for interactive shell when running HDLForge
2. **Change to project directory** before running commands
3. **Use full command structure**: `docker exec -i container bash -c "cd project && bash -i -c 'hdlforge ...'"`
4. **Check environment variables** if commands fail
5. **Verify project structure** matches HDLForge configuration

## Conclusion

HDLForge compilation and simulation works perfectly in the Fabrinetes container when using the correct shell configuration. The key is using the `-i` flag to ensure `.bashrc` runs and sets up the required environment variables.

**Test Status**: ✅ **PASSED** - HDLForge fully functional in container
