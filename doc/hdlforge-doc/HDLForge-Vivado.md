# HDLForge - Vivado Integration

> **📘 Main Documentation:** [HDLForge.md](HDLForge.md)  
> **📚 Complete Examples:** [HDLForge-Vivado-Examples.md](HDLForge-Vivado-Examples.md)

---

## 1. Overview

### 1.1 What is Vivado Integration?

FPGA synthesis, implementation, and bitstream generation via TCL-based automation.

**Purpose:** Transform SystemVerilog to FPGA programming file

**Key Benefits:**
- **Automated project management** - No manual GUI interactions
- **Reproducible builds** - All settings in JSON
- **Multiple strategies** - Test different optimizations
- **CI/CD friendly** - Batch mode execution

### 1.2 Workflow

```
SystemVerilog + Constraints
    ↓ new (create project)
Vivado Project (.xpr)
    ↓ syn (synthesis)
Netlist (.dcp)
    ↓ impl (place & route)
Placed/Routed Design
    ↓ bit (bitstream generation)
FPGA Bitstream (.bit)
```

---

## 2. Architecture

### 2.1 Technology Stack

| Component | Purpose |
|-----------|---------|
| **Vivado** | FPGA development suite |
| **TCL** | Scripting for automation |
| **Batch Mode** | Non-interactive execution |
| **Design Checkpoints** | `.dcp` files for incremental compilation |

### 2.2 Execution Flow

```
hdlforge vivado --step new
    ↓
Generate/Load TCL script → Add sources → Set part/top → Create .xpr
    ↓
hdlforge vivado --step syn --run-flow <flow>
    ↓
Launch synthesis → Generate netlist (.dcp) → Reports
    ↓
hdlforge vivado --step impl --run-flow <flow>
    ↓
Place & Route → Timing analysis → Reports
    ↓
hdlforge vivado --step bit --run-flow <flow>
    ↓
Generate bitstream (.bit) → Debug probes (.ltx)
```

---

## 3. Configuration Structure

### 3.1 Minimal Example

```json
{
  "settings": {
    "project_name": "my_project",
    "project_path": "$REPO_TOP/my_project"
  },
  "vivado_settings": {
    "build_dir": "_vivado",
    "project_name": "my_vivado_project",
    "top_module": "top",
    "part": "xc7a35ticsg324-1L",
    "runs_flow": {
      "default": {
        "synth": "synth_1",
        "impl": [
          {"name": "impl_1", "enabled": true}
        ]
      }
    }
  },
  "sources": {
    "files": [
      {
        "vivado": true,
        "relative_to_project_path": true,
        "file": [
          "sources/rtl/top.sv",
          "constraints/pins.xdc"
        ]
      }
    ]
  }
}
```

### 3.2 Key Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `build_dir` | string | No | Vivado project directory, default: `_vivado` |
| `project_name` | string | Yes | Vivado project name (`.xpr` filename) |
| `top_module` | string | Yes | Top-level module name |
| `part` | string | Yes | FPGA part number (e.g., `xc7a200tfbg484-1`) |
| `project_tcl` | string | No | Custom TCL script for project creation |
| `runs_flow` | object | Yes | Synthesis and implementation flow definitions |

### 3.3 FPGA Part Numbers

**Format:** `<family><size><package><speed_grade>`

**Examples:**
- `xc7a200tfbg484-1` - Artix-7, 200T, FBG484, speed -1
- `xc7k325tffg900-2` - Kintex-7, 325T, FFG900, speed -2
- `xcvu9p-flga2104-2-i` - Virtex UltraScale+, VU9P, industrial

---

## 4. Basic Usage

### 4.1 Create Project

```bash
hdlforge vivado --step new [--clean]
```

**Output:** `<project_path>/_vivado/<project_name>/<project_name>.xpr`

### 4.2 Synthesis

```bash
hdlforge vivado --step syn --run-flow <flow_name>
```

**Output:** `<project_name>.runs/<synth_run>/<top_module>.dcp`

### 4.3 Implementation

```bash
hdlforge vivado --step impl --run-flow <flow_name>
```

**Output:** `<project_name>.runs/<impl_run>/<top_module>_routed.dcp`

### 4.4 Bitstream Generation

```bash
hdlforge vivado --step bit --run-flow <flow_name>
```

**Output:** `<project_name>.runs/<impl_run>/<top_module>.bit`

### 4.5 Export Project to TCL

```bash
hdlforge vivado --step write_tcl
```

**Purpose:** Export Vivado project to TCL script for version control or manual editing.

**Output:** `<build_dir>/<project_name>.tcl`

**Automatic Updates:**
- After successful export, HDLForge automatically extracts file properties from the `.xpr` file
- Updates the JSON project file with:
  - Individual file records with `hdlforge_properties` and `vivado_properties`
  - Merged records for files with identical properties
  - Compact single-line formatting for properties

### 4.6 Set File Properties

```bash
hdlforge vivado --set-property '<tcl_set_property_command>'
```

**Purpose:** Execute Vivado `set_property` commands to modify file properties in the project.

**Usage:**
```bash
# Remove file from synthesis
hdlforge vivado --set-property 'set file_obj [get_files -of_objects [get_filesets sources_1] [list "*sources/ip/my_ip.xci"]]; set_property -name "used_in_synthesis" -value "0" -objects $file_obj'

# Set file type
hdlforge vivado --set-property 'set file_obj [get_files -of_objects [get_filesets sources_1] [list "*sources/rtl/module.sv"]]; set_property -name "file_type" -value "SystemVerilog" -objects $file_obj'
```

**How it works:**
1. Opens the Vivado project in batch mode
2. Executes the provided `set_property` command
3. Prints Vivado output to screen
4. Captures return value to verify success
5. If successful, automatically updates JSON from `.xpr` file

**Common Properties:**
- `used_in_synthesis` - Set to `"0"` or `"1"` to exclude/include from synthesis
- `used_in_implementation` - Set to `"0"` or `"1"` to exclude/include from implementation
- `used_in_simulation` - Set to `"0"` or `"1"` to exclude/include from simulation
- `file_type` - Set file type (e.g., `"SystemVerilog"`, `"VHDL 2008"`)
- `library` - Set VHDL library name

---

## 5. Run Flows

### 5.1 Purpose

Define different synthesis/implementation strategies for optimization exploration.

### 5.2 Flow Structure

```json
"runs_flow": {
  "flow_name": {
    "synth": "synth_run_name",
    "impl": [
      {"name": "impl_run_name_1", "enabled": true},
      {"name": "impl_run_name_2", "enabled": false}
    ],
    "defines": ["DEFINE_NAME=value"],
    "generics": ["PARAM_NAME=value"]
  }
}
```

### 5.3 Multiple Flows Example

```json
"runs_flow": {
  "default": {
    "synth": "synth_1",
    "impl": [{"name": "impl_1", "enabled": true}]
  },
  "high_performance": {
    "synth": "synth_1",
    "impl": [{"name": "impl_performance", "enabled": true}],
    "generics": ["CLOCK_FREQ=200000000"]
  },
  "explore": {
    "synth": "synth_1",
    "impl": [
      {"name": "impl_1", "enabled": true},
      {"name": "impl_2", "enabled": true},
      {"name": "impl_3", "enabled": true}
    ]
  }
}
```

**Usage:**
```bash
# Run high performance flow
hdlforge vivado --step syn --run-flow high_performance
hdlforge vivado --step impl --run-flow high_performance
hdlforge vivado --step bit --run-flow high_performance

# Explore multiple strategies
hdlforge vivado --step impl --run-flow explore
# Compare results from 3 implementations
```

---

## 6. Source Files

### 6.1 Supported File Types

| Extension | Type | Purpose |
|-----------|------|---------|
| `.sv`, `.v` | SystemVerilog/Verilog | RTL source files |
| `.xdc` | Constraints | Timing, placement, physical |
| `.xci` | IP Core | Vivado IP catalog cores |
| `.bd` | Block Design | Vivado block diagrams |

### 6.2 File Structure and Properties

HDLForge uses an optimized JSON structure where files with identical properties are automatically merged:

**Individual File Record:**
```json
"sources": {
  "files": [
    {
      "file": "sources/rtl/module.sv",
      "hdlforge_properties": {"vivado":true,"verilator":true,"relative_to_project_path":true},
      "vivado_properties": {"Library":"xil_defaultlib","UsedIn":["synthesis","implementation","simulation"]}
    }
  ]
}
```

**Merged File Record (files with identical properties):**
```json
"sources": {
  "files": [
    {
      "file": [
        "sources/rtl/module1.sv",
        "sources/rtl/module2.sv",
        "sources/rtl/module3.sv"
      ],
      "hdlforge_properties": {"vivado":true,"verilator":true,"relative_to_project_path":true},
      "vivado_properties": {"Library":"xil_defaultlib","UsedIn":["synthesis","implementation","simulation"]}
    }
  ]
}
```

**Property Fields:**
- `hdlforge_properties` - HDLForge-specific settings:
  - `vivado` - Include in Vivado builds (boolean)
  - `verilator` - Include in Verilator builds (boolean)
  - `relative_to_project_path` - Path resolution mode (boolean)
- `vivado_properties` - Vivado-specific file properties:
  - `Library` - VHDL library name
  - `UsedIn` - List of usage contexts: `["synthesis", "implementation", "simulation"]`
  - `file_type` - File type (e.g., `"SystemVerilog"`, `"VHDL 2008"`)
  - Other Vivado properties as needed

**Automatic Merging:**
- Files with identical `hdlforge_properties` and `vivado_properties` are automatically merged
- The `file` field becomes a list when multiple files share properties
- Properties are formatted as compact single-line JSON for readability

### 6.3 File Filtering

Only files with `"vivado": true` in `hdlforge_properties` are included in Vivado builds:

```json
"sources": {
  "files": [
    {
      "file": "sources/rtl/fpga_specific.sv",
      "hdlforge_properties": {"vivado":true,"verilator":false,"relative_to_project_path":true},
      "vivado_properties": {"UsedIn":["synthesis","implementation"]}
    }
  ]
}
```

### 6.4 Path Resolution

**Relative paths:**
```json
{"relative_to_project_path": true, "file": ["sources/rtl/top.sv"]}
// Resolves to: <project_path>/sources/rtl/top.sv
```

**Environment variable expansion:**
```json
{"relative_to_project_path": false, "file": ["$REPO_TOP/shared/common.sv"]}
// $REPO_TOP automatically expanded
```

---

## 7. Common Errors & Solutions

### 7.1 Project Creation

**Project Already Exists**
```bash
hdlforge vivado --step new --clean
```

**Missing Source Files**
→ Check `sources.files` array and file paths

**Invalid Part Number**
→ Verify part format and Vivado version support

### 7.2 Synthesis

**Syntax Errors**
→ Check synthesis log: `<synth_run>/runme.log`

**Unresolved References**
→ Add missing files to `sources.files`, ensure correct order

**Resource Over-Utilization**
→ Review utilization report, optimize design, or use larger part

### 7.3 Implementation & Bitstream

**Timing Violations** → Check `*_timing_summary.rpt`, adjust constraints, optimize placement
**Routing Congestion** → Add floorplan constraints, reduce utilization
**DRC Violations** → Review `*_drc.rpt`, fix electrical/pin issues

### 7.5 Debugging Tips

1. **Check logs:** `<build_dir>/<project_name>/vivado.log` and `**/runme.log`
2. **Review reports:** Utilization, Timing, DRC in `<project_name>.runs/<run>/`
3. **Open in GUI:** `cd <build_dir>/<project_name> && vivado <project_name>.xpr`
4. **TCL commands:** `report_timing_summary`, `report_utilization -hierarchical`

---

## 8. Best Practices

- **Project structure:** Organize by rtl/, constraints/, ip/, scripts/
- **Constraint files:** Separate pins.xdc, timing.xdc, physical.xdc
- **Run flows:** Name descriptively (default, high_performance, low_power, explore)
- **Version control:** Include .hdlforge.json, sources, constraints. Exclude _vivado/, *.log
- **Incremental builds:** Vivado auto-detects source changes, re-run only needed steps

---

## 9. Quick Reference

### Common Commands

```bash
# Complete flow
cd <project>
hdlforge vivado --step new --clean
hdlforge vivado --step syn --run-flow default
hdlforge vivado --step impl --run-flow default
hdlforge vivado --step bit --run-flow default

# Export project to TCL (auto-updates JSON from XPR)
hdlforge vivado --step write_tcl

# Set file properties
hdlforge vivado --set-property 'set file_obj [get_files -of_objects [get_filesets sources_1] [list "*file.sv"]]; set_property -name "used_in_synthesis" -value "0" -objects $file_obj'

# Bitstream location
# _vivado/<project_name>/<project_name>.runs/impl_1/<top_module>.bit

# Open in GUI
cd _vivado/<project_name>
vivado <project_name>.xpr
```

### Typical Workflow

```bash
# 1. Create project configuration (my_project.hdlforge.json)
# 2. Write SystemVerilog RTL
# 3. Create constraint files (.xdc)
# 4. Run Vivado flow
hdlforge vivado --step new --clean
hdlforge vivado --step syn --run-flow default
hdlforge vivado --step impl --run-flow default
hdlforge vivado --step bit --run-flow default
# 5. Check reports
cat _vivado/<project>/<project>.runs/impl_1/*_timing_summary.rpt
# 6. Program FPGA with generated .bit file
```

---

## 10. Additional Resources

- **Complete Examples:** [HDLForge-Vivado-Examples.md](HDLForge-Vivado-Examples.md)
- **Vivado TCL Commands:** UG835 - Vivado Design Suite TCL Command Reference
- **Constraints Guide:** UG903 - Using Constraints
- **Timing Closure:** UG906 - Design Analysis and Closure Techniques
- **Architecture Details:** [HDLForge-Architecture.md](HDLForge-Architecture.md)

---

## 11. Project File Management

### 11.1 Automatic JSON Updates

HDLForge automatically maintains synchronization between the Vivado project (`.xpr`) and the JSON configuration file:

**After `write_tcl` command:**
- Extracts file list and properties from `.xpr` XML file
- Updates JSON with individual file records
- Merges files with identical properties
- Formats properties as compact single-line JSON

**After `set_property` command:**
- Executes the property change in Vivado
- Extracts updated properties from `.xpr` file
- Updates JSON to reflect changes

### 11.2 JSON File Structure

The JSON file uses an optimized structure:
- **Merged records:** Files with identical `hdlforge_properties` and `vivado_properties` are grouped
- **Compact formatting:** Properties are stored as single-line JSON for readability
- **Centralized handling:** All JSON read/write operations go through `JSONFileHandler`

**Benefits:**
- Reduced file size (fewer duplicate property records)
- Easier to read (compact property formatting)
- Automatic optimization (merging happens on save)

---

## Document History

**Last Updated:** 2025-11-13 - Added set_property command, automatic XPR extraction, and JSON file optimization with property merging
