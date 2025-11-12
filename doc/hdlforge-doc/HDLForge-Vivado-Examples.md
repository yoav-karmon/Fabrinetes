# HDLForge - Vivado Examples

> **📘 Main Documentation:** [HDLForge-Vivado.md](HDLForge-Vivado.md)

This document contains complete, ready-to-use examples for Vivado FPGA implementation projects.

---

## 1. Simple LED Blinker

A minimal example demonstrating the complete Vivado flow from RTL to bitstream.

### Project Structure
```
led_blinker/
├── led_blinker.hdlforge.json
├── sources/
│   └── rtl/
│       └── led_blinker.sv
└── constraints/
    └── arty_a7.xdc
```

### Configuration (`led_blinker.hdlforge.json`)
```json
{
  "settings": {
    "project_name": "led_blinker",
    "project_path": "$REPO_TOP/led_blinker"
  },
  "vivado_settings": {
    "build_dir": "_vivado",
    "project_name": "led_blinker_vivado",
    "top_module": "led_blinker",
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
          "sources/rtl/led_blinker.sv",
          "constraints/arty_a7.xdc"
        ]
      }
    ]
  }
}
```

### SystemVerilog (`sources/rtl/led_blinker.sv`)
```systemverilog
module led_blinker (
    input  logic clk,
    input  logic rst_n,
    output logic [3:0] led
);

localparam COUNTER_WIDTH = 27;
logic [COUNTER_WIDTH-1:0] counter;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        counter <= '0;
        led <= 4'b0001;
    end else begin
        counter <= counter + 1;
        if (counter == 0) begin
            led <= {led[2:0], led[3]};  // Rotate LEDs
        end
    end
end

endmodule
```

### Constraints (`constraints/arty_a7.xdc`)
```tcl
## Clock
create_clock -period 10.000 -name sys_clk [get_ports clk]
set_property -dict {PACKAGE_PIN E3 IOSTANDARD LVCMOS33} [get_ports clk]

## Reset
set_property -dict {PACKAGE_PIN C2 IOSTANDARD LVCMOS33} [get_ports rst_n]

## LEDs
set_property -dict {PACKAGE_PIN H5  IOSTANDARD LVCMOS33} [get_ports {led[0]}]
set_property -dict {PACKAGE_PIN J5  IOSTANDARD LVCMOS33} [get_ports {led[1]}]
set_property -dict {PACKAGE_PIN T9  IOSTANDARD LVCMOS33} [get_ports {led[2]}]
set_property -dict {PACKAGE_PIN T10 IOSTANDARD LVCMOS33} [get_ports {led[3]}]
```

### Build Commands
```bash
cd led_blinker

# Create project
hdlforge vivado --step new --clean

# Run synthesis
hdlforge vivado --step syn --run-flow default

# Run implementation
hdlforge vivado --step impl --run-flow default

# Generate bitstream
hdlforge vivado --step bit --run-flow default

# Bitstream location: _vivado/led_blinker_vivado/led_blinker_vivado.runs/impl_1/led_blinker.bit
```

---

## 2. Multi-Flow Design with Clock Optimization

Demonstrates using multiple run flows to test different clock frequencies and optimization strategies.

### Configuration
```json
{
  "settings": {
    "project_name": "high_speed_design",
    "project_path": "$REPO_TOP/high_speed_design"
  },
  "vivado_settings": {
    "build_dir": "_vivado",
    "project_name": "hs_design",
    "top_module": "top",
    "part": "xc7k325tffg900-2",
    "runs_flow": {
      "baseline": {
        "synth": "synth_1",
        "impl": [
          {"name": "impl_1", "enabled": true}
        ],
        "generics": ["CLOCK_FREQ=100000000"]
      },
      "high_speed": {
        "synth": "synth_1",
        "impl": [
          {"name": "impl_performance", "enabled": true}
        ],
        "defines": ["HIGH_SPEED_MODE"],
        "generics": ["CLOCK_FREQ=200000000"]
      },
      "explore": {
        "synth": "synth_1",
        "impl": [
          {"name": "impl_1", "enabled": true},
          {"name": "impl_performance", "enabled": true},
          {"name": "impl_area_opt", "enabled": true}
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
          "sources/rtl/datapath.sv",
          "sources/rtl/controller.sv",
          "constraints/pins.xdc",
          "constraints/timing_100mhz.xdc"
        ]
      }
    ]
  }
}
```

### Build Workflow
```bash
cd high_speed_design

# Create project once
hdlforge vivado --step new --clean

# Test baseline (100 MHz)
hdlforge vivado --step syn --run-flow baseline
hdlforge vivado --step impl --run-flow baseline
# Check timing reports in: _vivado/hs_design/hs_design.runs/impl_1/*_timing_summary.rpt

# Test high speed (200 MHz)
hdlforge vivado --step syn --run-flow high_speed
hdlforge vivado --step impl --run-flow high_speed
# Check timing reports...

# Explore multiple strategies (runs 3 implementations in parallel)
hdlforge vivado --step impl --run-flow explore
# Compare results from:
#   - impl_1 (balanced)
#   - impl_performance (speed optimized)
#   - impl_area_opt (area optimized)

# Generate bitstream for best result
hdlforge vivado --step bit --run-flow high_speed
```

---

## 3. Constraint File Examples

### Basic Timing Constraints
```tcl
## Clock constraints
create_clock -period 10.000 -name clk_100mhz [get_ports sys_clk]

## Input delays (relative to clock)
set_input_delay -clock clk_100mhz -max 2.000 [get_ports {data_in[*]}]
set_input_delay -clock clk_100mhz -min 0.500 [get_ports {data_in[*]}]

## Output delays
set_output_delay -clock clk_100mhz -max 2.000 [get_ports {data_out[*]}]
set_output_delay -clock clk_100mhz -min 0.500 [get_ports {data_out[*]}]

## Clock domain crossing
set_clock_groups -asynchronous -group [get_clocks clk_100mhz] -group [get_clocks clk_200mhz]
```

### Pin Assignment Constraints
```tcl
## Differential clock input
set_property -dict {PACKAGE_PIN E19 IOSTANDARD LVDS} [get_ports sys_clk_p]
set_property -dict {PACKAGE_PIN E18 IOSTANDARD LVDS} [get_ports sys_clk_n]

## DDR memory interface
set_property -dict {PACKAGE_PIN M19 IOSTANDARD SSTL15} [get_ports {ddr_addr[0]}]
set_property -dict {PACKAGE_PIN M18 IOSTANDARD SSTL15} [get_ports {ddr_addr[1]}]
# ... more DDR pins ...

## GPIO with pull-ups
set_property -dict {PACKAGE_PIN T16 IOSTANDARD LVCMOS33 PULLUP TRUE} [get_ports gpio_in]
```

### Placement Constraints (Floorplanning)
```tcl
## Place critical logic in specific regions
create_pblock pblock_critical
add_cells_to_pblock pblock_critical [get_cells {critical_module/*}]
resize_pblock pblock_critical -add {SLICE_X50Y50:SLICE_X70Y70}
resize_pblock pblock_critical -add {RAMB36_X3Y10:RAMB36_X4Y14}

## Constrain routing
set_property HD.CLK_SRC BUFGCTRL_X0Y16 [get_ports sys_clk]
```

---

## 4. Multi-Part Design Example

Configuration for projects targeting different FPGA parts:

```json
{
  "vivado_settings": {
    "build_dir": "_vivado",
    "project_name": "multi_target",
    "top_module": "top",
    "part": "xc7a200tfbg484-1",  // Default part
    "runs_flow": {
      "artix7": {
        "synth": "synth_1",
        "impl": [{"name": "impl_1", "enabled": true}],
        "generics": ["FPGA_FAMILY=\"Artix7\""]
      },
      "kintex7": {
        "synth": "synth_1",
        "impl": [{"name": "impl_k7", "enabled": true}],
        "generics": ["FPGA_FAMILY=\"Kintex7\"", "USE_DSP=1"]
      }
    }
  }
}
```

To target different parts, update the `part` field:
- Artix-7: `xc7a200tfbg484-1`
- Kintex-7: `xc7k325tffg900-2`
- Virtex UltraScale+: `xcvu9p-flga2104-2-i`

---

## 5. IP Core Integration Example

```json
{
  "sources": {
    "files": [
      {
        "vivado": true,
        "relative_to_project_path": true,
        "file": [
          "sources/rtl/top.sv",
          "sources/rtl/custom_logic.sv",
          "ip/clk_wizard.xci",           // Clock wizard IP
          "ip/fifo_generator.xci",       // FIFO IP
          "ip/axi_interconnect.xci",     // AXI interconnect
          "constraints/pins.xdc",
          "constraints/timing.xdc"
        ]
      }
    ]
  }
}
```

**Note:** Generate IP cores first using Vivado GUI, then add `.xci` files to your configuration.

---

## 6. Incremental Build Example

For faster iteration on large designs:

```bash
# Initial build
hdlforge vivado --step new --clean
hdlforge vivado --step syn --run-flow default
hdlforge vivado --step impl --run-flow default

# Modify RTL sources (e.g., edit sources/rtl/module.sv)

# Re-run only necessary steps (Vivado auto-detects changes)
hdlforge vivado --step syn --run-flow default  // Only re-synthesizes changed modules
hdlforge vivado --step impl --run-flow default
hdlforge vivado --step bit --run-flow default
```

---

## 7. Analyzing Results

### Check Timing
```bash
# Open Vivado GUI
cd _vivado/<project_name>
vivado <project_name>.xpr

# Or view reports directly
cat _vivado/<project_name>/<project_name>.runs/impl_1/*_timing_summary.rpt
```

### Check Utilization
```bash
cat _vivado/<project_name>/<project_name>.runs/impl_1/*_utilization_routed.rpt
```

### Check Power
```bash
cat _vivado/<project_name>/<project_name>.runs/impl_1/*_power_routed.rpt
```

---

## Additional Resources

- **Vivado TCL Commands:** UG835 - Vivado Design Suite TCL Command Reference
- **Constraints Guide:** UG903 - Using Constraints
- **Timing Closure:** UG906 - Design Analysis and Closure Techniques
- **Main Vivado Doc:** [HDLForge-Vivado.md](HDLForge-Vivado.md)

---

## Document History

**Last Updated:** Commit `e8ac713cdcf020cde9acfcc3e58270fa519a5ddb` - Consolidate and reorganize HDLForge documentation into hdlforge-doc/ (2025-11-11)

