/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_uwasic_onboarding_evan_li (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  assign uio_oe = 8'hFF; // Set all IOs to output
  
  // Create wires to refer to the values of the registers
  wire [7:0] en_reg_out_7_0 = 0;
  wire [7:0] en_reg_out_15_8 = 0;
  wire [7:0] en_reg_pwm_7_0 = 0;
  wire [7:0] en_reg_pwm_15_8 = 0;
  wire [7:0] pwm_duty_cycle = 0;

  wire synch_clk;
  wire synch_data;
  wire synch_cs;

  triple_synch triple_synch_inst (
    .clk(clk),
    .in_signal_0(ui_in[0]),
    .in_signal_1(ui_in[1]),
    .in_signal_2(ui_in[2]),
    .out_signal0(synch_clk),
    .out_signal1(synch_data),
    .out_signal2(synch_cs)
  );

  spi_peripheral spi_peripheral_inst (
    .m_clk(clk),
    .s_clk_synch(synch_clk),
    .data_synch(synch_data),
    .cs_synch(synch_cs),
    .rst_n(rst_n),
    .reg_0(en_reg_out_7_0),
    .reg_1(en_reg_out_15_8),
    .reg_2(en_reg_pwm_7_0),
    .reg_3(en_reg_pwm_15_8),
    .reg_4(pwm_duty_cycle)
  );

  // Instantiate the PWM module
  pwm_peripheral pwm_peripheral_inst (
    .clk(clk),
    .rst_n(rst_n),
    .en_reg_out_7_0(en_reg_out_7_0),
    .en_reg_out_15_8(en_reg_out_15_8),
    .en_reg_pwm_7_0(en_reg_pwm_7_0),
    .en_reg_pwm_15_8(en_reg_pwm_15_8),
    .pwm_duty_cycle(pwm_duty_cycle),
    .out({uio_out, uo_out})
  );

  // Add uio_in and ui_in[7:3] to the list of unused signals:
  wire _unused = &{ena, ui_in[7:3], uio_in, 1'b0};

endmodule
