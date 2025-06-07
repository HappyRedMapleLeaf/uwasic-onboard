# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import FallingEdge
from cocotb.triggers import ClockCycles
from cocotb.triggers import with_timeout
from cocotb.types import LogicArray
from cocotb.utils import get_sim_time

from cocotb.result import SimTimeoutError

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

timeout_us = 1000 # longer than 3kHz period
EDGE_FALLING = 0
EDGE_RISING = 1

# returns True rising edge was hit, False if timeout
async def WaitEdge(signal, bit_index, clk, timeout_us, edge):
    start_time = get_sim_time(units="us")

    prev = (int(signal.value) >> bit_index) & 1

    while get_sim_time(units="us") - start_time < timeout_us:
        await ClockCycles(clk, 1)

        curr = (int(signal.value) >> bit_index) & 1
        if (edge == EDGE_RISING and prev == 0 and curr == 1) or \
           (edge == EDGE_FALLING and prev == 1 and curr == 0):
            return True
        prev = curr

    return False

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    dut._log.info("Start PWM Frequency test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    
    dut._log.info("Set 50% duty cycle - Write 0x80 to addr 0x04")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x80)
    await ClockCycles(dut.clk, 30000)

    for bit in range(8):
        dut._log.info(f"Enable PWM on uo_out pin {bit} - Write {0x01 << bit} to addr 0x02")
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, {0x01 << bit})
        await ClockCycles(dut.clk, 30000)

        dut._log.info(f"Enable output on uo_out pin {bit} - Write {0x01 << bit} to addr 0x00")
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, {0x01 << bit})
        await ClockCycles(dut.clk, 30000)

        if not await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_RISING):
            assert False, "1st rising edge wait timeout"
        t1 = get_sim_time(units="ps")

        if not await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_RISING):
            assert False, "2nd rising edge wait timeout"
        t2 = get_sim_time(units="ps")
        
        if not await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_RISING):
            assert False, "3rd rising edge wait timeout"
        t3 = get_sim_time(units="ps")

        f1 = 1e12 / (t2 - t1)
        f2 = 1e12 / (t3 - t2)

        dut._log.info(f"Measured frequencies: f1={f1:.2f} Hz, f2={f2:.2f} Hz")
        assert f1 > 2970 and f1 < 3030, f"first measured frequency out of expected range: {f1} Hz"
        assert f2 > 2970 and f2 < 3030, f"second measured frequency out of expected range: {f2} Hz"

    dut._log.info("PWM Frequency test completed successfully")

@cocotb.test()
async def test_pwm_duty(dut):
    dut._log.info("Start PWM Duty Cycle test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    for bit in range(8):
        # 50% duty cycle test
        dut._log.info(f"Enable PWM on uo_out pin {bit} - Write {0x01 << bit} to addr 0x02")
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x01 << bit)
        await ClockCycles(dut.clk, 30000)

        dut._log.info(f"Enable output on uo_out pin {bit} - Write {0x01 << bit} to addr 0x00")
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x01 << bit)
        await ClockCycles(dut.clk, 30000)
    
        dut._log.info("Set 50% duty cycle - Write 0x80 to addr 0x04")
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x80)
        await ClockCycles(dut.clk, 30000)

        if not await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_RISING):
            assert False, "1st rising edge wait timeout"
        t_rise_1 = get_sim_time(units="ps")

        if not await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_FALLING):
            assert False, "1st falling edge wait timeout"
        t_fall_1 = get_sim_time(units="ps")

        if not await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_RISING):
            assert False, "2nd rising edge wait timeout"
        t_rise_2 = get_sim_time(units="ps")

        dut._log.info(f"Disable PWM on uo_out pin {bit} - Write 0x00 to addr 0x02")
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)
        await ClockCycles(dut.clk, 30000)

        dut._log.info(f"Disable output on uo_out pin {bit} - Write 0x00 to addr 0x00")
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
        await ClockCycles(dut.clk, 30000)

        duty_cycle = (t_fall_1 - t_rise_1) / (t_rise_2 - t_rise_1)
        dut._log.info(f"Measured duty cycle: {duty_cycle}%")
        assert duty_cycle > 0.49 and duty_cycle < 0.51, f"measured duty cycle out of expected range: {duty_cycle}%"

        # 0% duty cycle test - always low
        dut._log.info(f"Enable PWM on uo_out pin {bit} - Write {0x01 << bit} to addr 0x02")
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x01 << bit)
        await ClockCycles(dut.clk, 30000)
        
        dut._log.info("Set 0% duty cycle - Write 0x00 to addr 0x04")
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)
        await ClockCycles(dut.clk, 30000)

        assert dut.uo_out[0] == 0, f"Expected output low, got output high"

        if await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_RISING):
            assert False, f"Unexpected rising edge detected on uo_out[{bit}] within {timeout_us} us"
        dut._log.info(f"No rising edge detected on uo_out[{bit}] in {timeout_us} us. We good!")

        dut._log.info(f"Disable PWM on uo_out pin {bit} - Write 0x00 to addr 0x02")
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)
        await ClockCycles(dut.clk, 30000)

        dut._log.info(f"Disable output on uo_out pin {bit} - Write 0x00 to addr 0x00")
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
        await ClockCycles(dut.clk, 30000)

        # 100% duty cycle test - always high
        dut._log.info(f"Enable PWM on uo_out pin {bit} - Write {0x01 << bit} to addr 0x02")
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x01 << bit)
        await ClockCycles(dut.clk, 30000)
        
        dut._log.info("Set 100% duty cycle - Write 0xFF to addr 0x04")
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)
        await ClockCycles(dut.clk, 30000)

        assert dut.uo_out[0] == 1, f"Expected output high, got output low"

        if await WaitEdge(dut.uo_out, bit, dut.clk, timeout_us, EDGE_FALLING):
            assert False, f"Unexpected falling edge detected on uo_out[{bit}] within {timeout_us} us"
        dut._log.info(f"No falling edge detected on uo_out[{bit}] in {timeout_us} us. We good!")

        dut._log.info(f"Disable PWM on uo_out pin {bit} - Write 0x00 to addr 0x02")
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)
        await ClockCycles(dut.clk, 30000)

        dut._log.info(f"Disable output on uo_out pin {bit} - Write 0x00 to addr 0x00")
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
        await ClockCycles(dut.clk, 30000)

    dut._log.info("PWM Duty Cycle test completed successfully")
