#!/usr/bin/env python3
"""
Cocotb testbench for 32-bit Address Generator Module

This testbench demonstrates how to use Cocotb for verification
in the Fabrinetes FPGA development workflow.

Test scenarios:
- Basic functionality test
- Reset behavior test
- Enable/disable test
- Address increment test
- Edge case testing
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb.result import TestFailure
import random

# Test parameters
CLOCK_PERIOD = 10  # ns
ADDR_WIDTH = 32
INCREMENT = 1

@cocotb.test()
async def test_basic_functionality(dut):
    """Test basic address generation functionality"""
    
    # Start clock
    clock = Clock(dut.clk, CLOCK_PERIOD, units="ns")
    cocotb.start_soon(clock.start())
    
    # Initialize signals
    dut.rst_n.value = 0
    dut.enable.value = 0
    dut.addr_increment.value = INCREMENT
    
    # Reset sequence
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    
    # Check initial state after reset
    assert dut.addr_out.value == 0, f"Expected addr_out=0 after reset, got {dut.addr_out.value}"
    assert dut.addr_valid.value == 0, f"Expected addr_valid=0 after reset, got {dut.addr_valid.value}"
    
    # Enable address generation
    dut.enable.value = 1
    await RisingEdge(dut.clk)
    
    # Wait one more cycle for valid signal to be asserted (SystemVerilog needs one cycle)
    await RisingEdge(dut.clk)
    
    # Check that valid signal is asserted
    assert dut.addr_valid.value == 1, f"Expected addr_valid=1 when enabled, got {dut.addr_valid.value}"
    
    # Test address increment
    # After enabling and waiting for valid, the address should be 2*INCREMENT (0 + INCREMENT + INCREMENT)
    expected_addr = 2 * INCREMENT
    for i in range(10):
        await RisingEdge(dut.clk)
        assert dut.addr_out.value == expected_addr, f"Expected addr_out={expected_addr}, got {dut.addr_out.value}"
        expected_addr += INCREMENT
    
    print("✓ Basic functionality test passed")

@cocotb.test()
async def test_reset_behavior(dut):
    """Test reset functionality"""
    
    # Start clock
    clock = Clock(dut.clk, CLOCK_PERIOD, units="ns")
    cocotb.start_soon(clock.start())
    
    # Initialize and enable
    dut.rst_n.value = 1
    dut.enable.value = 1
    dut.addr_increment.value = INCREMENT
    
    # Let it run for a few cycles
    for _ in range(5):
        await RisingEdge(dut.clk)
    
    # Assert reset
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    
    # Check reset state
    assert dut.addr_out.value == 0, f"Expected addr_out=0 after reset, got {dut.addr_out.value}"
    assert dut.addr_valid.value == 0, f"Expected addr_valid=0 after reset, got {dut.addr_valid.value}"
    
    # Release reset and check it starts counting again
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    
    # Wait one more cycle for the address to increment (SystemVerilog needs one cycle)
    await RisingEdge(dut.clk)
    
    assert dut.addr_out.value == INCREMENT, f"Expected addr_out={INCREMENT} after reset release, got {dut.addr_out.value}"
    assert dut.addr_valid.value == 1, f"Expected addr_valid=1 after reset release, got {dut.addr_valid.value}"
    
    print("✓ Reset behavior test passed")

@cocotb.test()
async def test_enable_disable(dut):
    """Test enable/disable functionality"""
    
    # Start clock
    clock = Clock(dut.clk, CLOCK_PERIOD, units="ns")
    cocotb.start_soon(clock.start())
    
    # Initialize
    dut.rst_n.value = 1
    dut.enable.value = 0
    dut.addr_increment.value = INCREMENT
    
    # Reset sequence
    await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    
    # Enable and count
    dut.enable.value = 1
    await RisingEdge(dut.clk)
    addr_before_disable = dut.addr_out.value
    
    # Disable
    dut.enable.value = 0
    await RisingEdge(dut.clk)
    
    # Check that address is held and valid is deasserted
    assert dut.addr_out.value == addr_before_disable, f"Address should be held when disabled"
    assert dut.addr_valid.value == 0, f"Expected addr_valid=0 when disabled, got {dut.addr_valid.value}"
    
    # Re-enable
    dut.enable.value = 1
    await RisingEdge(dut.clk)
    
    # Check that counting resumes
    assert dut.addr_out.value == addr_before_disable + INCREMENT, f"Address should resume counting"
    assert dut.addr_valid.value == 1, f"Expected addr_valid=1 when re-enabled, got {dut.addr_valid.value}"
    
    print("✓ Enable/disable test passed")

@cocotb.test()
async def test_address_increment(dut):
    """Test different address increment values"""
    
    # Start clock
    clock = Clock(dut.clk, CLOCK_PERIOD, units="ns")
    cocotb.start_soon(clock.start())
    
    # Initialize
    dut.rst_n.value = 1
    dut.enable.value = 1
    
    # Test different increment values
    test_increments = [1, 2, 4, 8, 16, 32, 100, 1000]
    
    for increment in test_increments:
        # Reset
        dut.rst_n.value = 0
        await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        
        # Set increment
        dut.addr_increment.value = increment
        await RisingEdge(dut.clk)
        
        # Test counting
        expected_addr = increment
        for i in range(5):
            await RisingEdge(dut.clk)
            assert dut.addr_out.value == expected_addr, f"Increment {increment}: Expected addr_out={expected_addr}, got {dut.addr_out.value}"
            expected_addr += increment
    
    print("✓ Address increment test passed")

@cocotb.test()
async def test_edge_cases(dut):
    """Test edge cases and boundary conditions"""
    
    # Start clock
    clock = Clock(dut.clk, CLOCK_PERIOD, units="ns")
    cocotb.start_soon(clock.start())
    
    # Initialize
    dut.rst_n.value = 1
    dut.enable.value = 1
    
    # Test zero increment
    dut.addr_increment.value = 0
    await RisingEdge(dut.clk)
    initial_addr = dut.addr_out.value
    
    await RisingEdge(dut.clk)
    assert dut.addr_out.value == initial_addr, f"Address should not change with zero increment"
    
    # Test maximum increment
    dut.addr_increment.value = (2**ADDR_WIDTH) - 1
    await RisingEdge(dut.clk)
    addr_before_max = dut.addr_out.value
    
    await RisingEdge(dut.clk)
    # Note: This will cause overflow, but we're testing the behavior
    expected_addr = (addr_before_max + ((2**ADDR_WIDTH) - 1)) & ((2**ADDR_WIDTH) - 1)
    assert dut.addr_out.value == expected_addr, f"Max increment test failed"
    
    print("✓ Edge cases test passed")

@cocotb.test()
async def test_random_values(dut):
    """Test with random increment values"""
    
    # Start clock
    clock = Clock(dut.clk, CLOCK_PERIOD, units="ns")
    cocotb.start_soon(clock.start())
    
    # Initialize
    dut.rst_n.value = 1
    dut.enable.value = 1
    
    # Test with random increments
    random.seed(42)  # For reproducible results
    
    for test_iteration in range(10):
        # Reset
        dut.rst_n.value = 0
        await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        
        # Random increment
        increment = random.randint(1, 1000)
        dut.addr_increment.value = increment
        
        # Test counting
        expected_addr = increment
        for i in range(3):
            await RisingEdge(dut.clk)
            assert dut.addr_out.value == expected_addr, f"Random test {test_iteration}: Expected addr_out={expected_addr}, got {dut.addr_out.value}"
            expected_addr += increment
    
    print("✓ Random values test passed")

# Additional utility functions for debugging
async def monitor_signals(dut):
    """Monitor all signals for debugging"""
    while True:
        await RisingEdge(dut.clk)
        print(f"clk={dut.clk.value}, rst_n={dut.rst_n.value}, enable={dut.enable.value}, "
              f"addr_increment={dut.addr_increment.value}, addr_out={dut.addr_out.value}, "
              f"addr_valid={dut.addr_valid.value}")

# Uncomment the line below to enable signal monitoring during tests
# cocotb.start_soon(monitor_signals(dut))
