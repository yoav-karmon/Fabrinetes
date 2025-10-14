/**
 * 32-bit Address Generator Module
 * 
 * This module demonstrates a simple 32-bit address generator that can be used
 * as an example for Fabrinetes FPGA development workflow.
 * 
 * Features:
 * - 32-bit address output
 * - Configurable address increment
 * - Enable/disable control
 * - Reset functionality
 * - Clock domain crossing safe
 */

module addr_32bit #(
    parameter int ADDR_WIDTH = 32,
    parameter int INCREMENT = 1
)(
    input  logic                    clk,
    input  logic                    rst_n,
    input  logic                    enable,
    input  logic [ADDR_WIDTH-1:0]   addr_increment,
    output logic [ADDR_WIDTH-1:0]   addr_out,
    output logic                    addr_valid
);

    // Internal registers
    logic [ADDR_WIDTH-1:0] addr_reg;
    logic                  valid_reg;

    // Address generation logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            addr_reg  <= '0;
            valid_reg <= 1'b0;
        end else if (enable) begin
            addr_reg  <= addr_reg + addr_increment;
            valid_reg <= 1'b1;
        end else begin
            addr_reg  <= addr_reg;  // Hold current value
            valid_reg <= 1'b0;
        end
    end

    // Output assignments
    assign addr_out   = addr_reg;
    assign addr_valid = valid_reg;

    // Assertions for verification
    `ifdef SIMULATION
        // Check that address doesn't overflow
        assert property (@(posedge clk) disable iff (!rst_n) 
            (enable && addr_reg + addr_increment < addr_reg) |-> 
            $warning("Address overflow detected!"));
        
        // Check that valid signal follows enable
        assert property (@(posedge clk) disable iff (!rst_n)
            enable |-> ##1 addr_valid);
    `endif

endmodule

/**
 * Top-level module for testing
 */
module addr_32bit_top #(
    parameter int ADDR_WIDTH = 32,
    parameter int INCREMENT = 1
)(
    input  logic                    clk,
    input  logic                    rst_n,
    input  logic                    enable,
    input  logic [ADDR_WIDTH-1:0]   addr_increment,
    output logic [ADDR_WIDTH-1:0]   addr_out,
    output logic                    addr_valid
);

    // Instantiate the address generator
    addr_32bit #(
        .ADDR_WIDTH(ADDR_WIDTH),
        .INCREMENT(INCREMENT)
    ) u_addr_gen (
        .clk             (clk),
        .rst_n           (rst_n),
        .enable          (enable),
        .addr_increment  (addr_increment),
        .addr_out        (addr_out),
        .addr_valid      (addr_valid)
    );

endmodule
