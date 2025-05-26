/*
 * Copyright (c) 2024 Evan Li
 * SPDX-License-Identifier: Apache-2.0
 */
 
 `default_nettype none

module triple_synch (
    input  wire       clk,
    input  wire       in_signal_0,
    input  wire       in_signal_1,
    input  wire       in_signal_2,
    output  reg       out_signal0,
    output  reg       out_signal1,
    output  reg       out_signal2
);

reg inter_0 = 0;
reg inter_1 = 0;
reg inter_2 = 0;

always @(posedge clk) 
begin
    // dff stage 1
    inter_0 <= in_signal_0;
    inter_1 <= in_signal_1;
    inter_2 <= in_signal_2;

    // dff stage 2
    out_signal0 <= inter_0;
    out_signal1 <= inter_1;
    out_signal2 <= inter_2;
end

endmodule


module spi_peripheral (
    input  wire       clk,      // spi clock, not master clock
    input  wire       data,
    input  wire       cs,
    input  wire       rst_n,    // reset_n - low to reset
    output reg [7:0]  reg_0,
    output reg [7:0]  reg_1,
    output reg [7:0]  reg_2,
    output reg [7:0]  reg_3,
    output reg [7:0]  reg_4,
);

reg [4:0] rx_bit_count = 0;
reg [15:0] rx_data = 0;

always @(negedge rst_n)
begin
    reg_0 <= 8'h00;
    reg_1 <= 8'h00;
    reg_2 <= 8'h00;
    reg_3 <= 8'h00;
    reg_4 <= 8'h00;

    rx_bit_count <= 0;
    rx_data <= 0;
end

always @(posedge clk)
begin
    if (rx_bit_count < 16 && !cs) begin
        rx_bit_count <= rx_bit_count + 1;
        rx_data = (rx_data << 1) | data;
    end
end

always @(negedge cs)
begin
    rx_bit_count <= 0;
    rx_data <= 0;
end

always @(posedge cs)
begin
    // ignore invalid length transaction and reads
    if (rx_bit_count == 16 && rx_data[15] == 1) begin
        // Process the received data
        case (rx_data[14:8])
            7'b0000000: reg_0 <= rx_data[7:0];
            7'b0000001: reg_1 <= rx_data[7:0];
            7'b0000010: reg_2 <= rx_data[7:0];
            7'b0000011: reg_3 <= rx_data[7:0];
            7'b0000100: reg_4 <= rx_data[7:0];
            default: ; // Ignore other addresses
        endcase
    end
end

endmodule