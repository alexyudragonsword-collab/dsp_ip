// dtc_efm1 — first-order error-feedback (EFM1) dither of a DTC's phase word (bit-true RTL of
// polar_tx export/rtl.py `efm1_int_golden`, vendored as dspip.vendor.polartx.rtl).
//
// Per valid sample, with the phase word x = code.frac (N_BITS integer + FRAC_BITS fraction):
//   s = x + err;  code = (s >> FRAC_BITS) mod 2^N_BITS;  err = s mod 2^FRAC_BITS
// The fraction the DTC cannot resolve is carried into the next sample, so the time average
// of the code is exact and the quantization error is first-order high-passed. `rst` clears
// err. The code is registered: it appears on the clock edge that consumes x (LATENCY = 1).
module dtc_efm1 #(
    parameter int N_BITS    = 11,
    parameter int FRAC_BITS = 8
) (
    input  logic                          clk,
    input  logic                          rst,
    input  logic                          valid,
    input  logic [N_BITS+FRAC_BITS-1:0]   phase_w,
    output logic [N_BITS-1:0]             code
);
    localparam int W = N_BITS + FRAC_BITS;
    logic [FRAC_BITS-1:0] err;
    logic [W:0]           s;        // one carry bit; dropped (mod 2^N_BITS) below
    assign s = {1'b0, phase_w} + {{(W + 1 - FRAC_BITS){1'b0}}, err};
    always_ff @(posedge clk) begin
        if (rst) begin
            err  <= '0;
            code <= '0;
        end else if (valid) begin
            err  <= s[FRAC_BITS-1:0];
            code <= s[W-1:FRAC_BITS];
        end
    end
endmodule
