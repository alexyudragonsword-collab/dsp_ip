// dtc_phase_acc — the open-loop DTC's phase datapath: a modulo-2^W accumulator of the
// frequency word, acc[n] = (acc[n-1] + finc[n]) mod 2^W (polar_tx export/rtl.py
// `phase_acc_golden`). The output is the registered sum after adding finc[n]; `rst` clears it.
module dtc_phase_acc #(
    parameter int W = 16
) (
    input  logic         clk,
    input  logic         rst,
    input  logic         valid,
    input  logic [W-1:0] finc,
    output logic [W-1:0] phase
);
    always_ff @(posedge clk) begin
        if (rst)        phase <= '0;
        else if (valid) phase <= phase + finc;     // wraps: W-bit add
    end
endmodule
