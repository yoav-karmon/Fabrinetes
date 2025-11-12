# HDLForge - Verilator Examples

> **📘 Main Documentation:** [HDLForge-Verilator.md](HDLForge-Verilator.md)

This document contains complete, ready-to-use examples for Verilator/Cocotb simulation projects.

---

## 1. Simple Counter Test

A minimal example demonstrating basic Verilator simulation with Python testbench.

### Project Structure
```
my_project/
├── my_project.hdlforge.json
├── sources/
│   └── rtl/
│       └── counter.sv
└── tests/
    └── counter_test.py
```

### Configuration (`my_project.hdlforge.json`)
```json
{
  "settings": {
    "project_name": "counter_project",
    "project_path": "$REPO_TOP/my_project"
  },
  "verilator_settings": {
    "build_dir": "_verilator",
    "includes_paths": [],
    "sim_targets": [
      {
        "name": "counter_test",
        "top_module": "counter",
        "test_name": "test_counter",
        "python_file": "tests/counter_test.py",
        "build_args": ["--trace"],
        "PYTHONPATH": ["tests"]
      }
    ]
  },
  "sources": {
    "files": [
      {
        "verilator": true,
        "relative_to_project_path": true,
        "file": ["sources/rtl/counter.sv"]
      }
    ]
  }
}
```

### SystemVerilog (`sources/rtl/counter.sv`)
```systemverilog
module counter #(
    parameter WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             enable,
    output logic [WIDTH-1:0] count
);

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= '0;
    else if (enable)
        count <= count + 1;
end

endmodule
```

### Python Testbench (`tests/counter_test.py`)
```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_counter(dut):
    """Test counter module"""
    
    # Start clock
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Reset
    dut.rst_n.value = 0
    dut.enable.value = 0
    await Timer(20, units="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    
    # Enable counter
    dut.enable.value = 1
    
    # Check counting
    for expected in range(10):
        await RisingEdge(dut.clk)
        actual = int(dut.count.value)
        cocotb.log.info(f"Count: {actual}")
        assert actual == expected, f"Count mismatch! Expected: {expected}, Got: {actual}"
    
    cocotb.log.info("✓ Counter test passed!")
```

### Run Commands
```bash
cd my_project
hdlforge Verilator --step build --SimTargetName counter_test
hdlforge Verilator --step sim --SimTargetName counter_test

# View waveforms
gtkwave _verilator/counter_test/dump.vcd
```

---

## 2. Advanced FIFO Test with Monitors

Demonstrates advanced Cocotb features including custom monitors and reusable testbench components.

### Project Structure
```
advanced_project/
├── advanced.hdlforge.json
├── sources/
│   └── rtl/
│       ├── fifo.sv
│       └── fifo_pkg.sv
└── tests/
    ├── fifo_test.py
    └── monitors/
        └── fifo_monitor.py
```

### Configuration (`advanced.hdlforge.json`)
```json
{
  "settings": {
    "project_name": "fifo_project",
    "project_path": "$REPO_TOP/advanced_project"
  },
  "verilator_settings": {
    "build_dir": "_verilator",
    "includes_paths": ["sources/rtl"],
    "sim_targets": [
      {
        "name": "fifo_full_test",
        "top_module": "fifo",
        "test_name": "test_fifo_full",
        "python_file": "tests/fifo_test.py",
        "build_args": ["--trace", "--coverage"],
        "parameters": {"DEPTH": 16, "WIDTH": 32},
        "PYTHONPATH": ["tests", "tests/monitors"]
      }
    ]
  },
  "sources": {
    "files": [
      {
        "verilator": true,
        "relative_to_project_path": true,
        "file": [
          "sources/rtl/fifo_pkg.sv",
          "sources/rtl/fifo.sv"
        ]
      }
    ]
  }
}
```

### Monitor (`tests/monitors/fifo_monitor.py`)
```python
import cocotb
from cocotb.triggers import RisingEdge

class FIFOMonitor:
    def __init__(self, dut):
        self.dut = dut
        self.transactions = []
        
    async def monitor_writes(self):
        while True:
            await RisingEdge(self.dut.clk)
            if self.dut.wr_en.value == 1 and self.dut.full.value == 0:
                data = int(self.dut.wr_data.value)
                self.transactions.append(("WRITE", data))
                cocotb.log.debug(f"Write: 0x{data:08x}")
    
    async def monitor_reads(self):
        while True:
            await RisingEdge(self.dut.clk)
            if self.dut.rd_en.value == 1 and self.dut.empty.value == 0:
                data = int(self.dut.rd_data.value)
                self.transactions.append(("READ", data))
                cocotb.log.debug(f"Read: 0x{data:08x}")
```

### Testbench (`tests/fifo_test.py`)
```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from monitors.fifo_monitor import FIFOMonitor

@cocotb.test()
async def test_fifo_full(dut):
    """Test FIFO full operation"""
    
    # Start clock
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Start monitor
    monitor = FIFOMonitor(dut)
    cocotb.start_soon(monitor.monitor_writes())
    cocotb.start_soon(monitor.monitor_reads())
    
    # Reset
    dut.rst_n.value = 0
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    await Timer(20, units="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    
    # Write until full
    write_data = []
    for i in range(20):
        dut.wr_data.value = i
        dut.wr_en.value = 1
        await RisingEdge(dut.clk)
        
        if dut.full.value == 1:
            cocotb.log.info(f"FIFO full after {i} writes")
            break
        write_data.append(i)
    
    dut.wr_en.value = 0
    
    # Read all data
    read_data = []
    dut.rd_en.value = 1
    while dut.empty.value == 0:
        await RisingEdge(dut.clk)
        read_data.append(int(dut.rd_data.value))
    
    # Verify data matches
    assert read_data == write_data, "FIFO data mismatch!"
    cocotb.log.info(f"✓ FIFO test passed! Transferred {len(read_data)} words")
```

### Run Commands
```bash
cd advanced_project
hdlforge Verilator --step build --SimTargetName fifo_full_test
hdlforge Verilator --step sim --SimTargetName fifo_full_test
gtkwave _verilator/fifo_full_test/dump.vcd
```

---

## 3. Additional Example Patterns

### Multiple Test Targets

Use multiple `sim_targets` for different test scenarios:

```json
"sim_targets": [
  {
    "name": "basic_test",
    "top_module": "top",
    "test_name": "test_basic",
    "python_file": "tests/basic_test.py",
    "build_args": ["--trace"],
    "PYTHONPATH": ["tests"]
  },
  {
    "name": "stress_test",
    "top_module": "top",
    "test_name": "test_stress",
    "python_file": "tests/stress_test.py",
    "build_args": ["--trace", "--coverage"],
    "defines": {"FAST_SIM": 1},
    "PYTHONPATH": ["tests", "tests/utils"]
  }
]
```

### Testbench with Assertions

```python
@cocotb.test()
async def test_with_assertions(dut):
    """Example with comprehensive assertions"""
    
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Reset
    dut.rst_n.value = 0
    await Timer(20, units="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    
    # Test with assertions
    dut.input_data.value = 0x1234
    dut.input_valid.value = 1
    await RisingEdge(dut.clk)
    
    # Wait for output with timeout
    timeout_cycles = 100
    for _ in range(timeout_cycles):
        if dut.output_valid.value == 1:
            break
        await RisingEdge(dut.clk)
    else:
        assert False, "Timeout waiting for output_valid"
    
    # Check output
    assert dut.output_data.value == 0x1234, "Data mismatch"
    cocotb.log.info("✓ Test passed")
```

### Testbench with Scoreboard

```python
class Scoreboard:
    def __init__(self):
        self.expected_queue = []
        self.received_queue = []
        
    def add_expected(self, data):
        self.expected_queue.append(data)
        
    def add_received(self, data):
        self.received_queue.append(data)
        self.check()
        
    def check(self):
        if self.expected_queue and self.received_queue:
            expected = self.expected_queue.pop(0)
            received = self.received_queue.pop(0)
            assert expected == received, \
                f"Mismatch: expected {expected:08x}, got {received:08x}"

@cocotb.test()
async def test_with_scoreboard(dut):
    """Example using scoreboard for checking"""
    
    scoreboard = Scoreboard()
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Start monitor that feeds scoreboard
    async def output_monitor():
        while True:
            await RisingEdge(dut.clk)
            if dut.output_valid.value == 1:
                scoreboard.add_received(int(dut.output_data.value))
    
    cocotb.start_soon(output_monitor())
    
    # Test logic...
    # (Add expected values to scoreboard as you send inputs)
```

---

## Additional Resources

- **Cocotb Documentation:** https://docs.cocotb.org/
- **Verilator Manual:** https://verilator.org/guide/latest/
- **Main Verilator Doc:** [HDLForge-Verilator.md](HDLForge-Verilator.md)

---

## Document History

**Last Updated:** Commit `e8ac713cdcf020cde9acfcc3e58270fa519a5ddb` - Consolidate and reorganize HDLForge documentation into hdlforge-doc/ (2025-11-11)

