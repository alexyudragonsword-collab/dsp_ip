// Simulator quirk probe (not an IP): Verilator 5.020 constant-folds an arithmetic right
// shift of a longint by a *longint* localparam to 0. `int` shift amounts, logical `>>`,
// and a non-constant left operand are all fine; Icarus 12 is right in every case.
// Halo_Serdes' tb_adc_dsp_loop.sv hits it in `dut.cgsum >>> LANE_SHIFT` (4/5 sets have
// CAL_ON=0, so cgsum is a propagated constant) -> ip/halo_adc_dsp_loop runs iverilog only.
// tests/test_sim_quirks.py runs this and tells you when the restriction can be lifted.
//
//   $ verilator --binary --timing -Wno-WIDTH --top-module t --Mdir obj tools/quirks/verilator_longint_shift.sv && obj/Vt
//   $ iverilog -g2012 -o q.vvp tools/quirks/verilator_longint_shift.sv && vvp -n q.vvp
module t;
    localparam longint SH_L = 4;
    localparam int     SH_I = 4;
    longint a;
    initial begin
        a = 16 <<< 14;   // 262144
        $display("QUIRK a>>>SH_longint=%0d a>>>SH_int=%0d a>>SH_longint=%0d a>>>4=%0d expect=16384",
                 a >>> SH_L, a >>> SH_I, a >> SH_L, a >>> 4);
        $finish;
    end
endmodule
