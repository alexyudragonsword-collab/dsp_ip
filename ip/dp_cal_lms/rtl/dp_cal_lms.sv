// dp_cal_lms — sign-sign LMS gain calibrator of an ADPLL two-point modulator (bit-true RTL of
// polar_tx cal/dp_cal_fixed.py, vendored as dspip.vendor.polartx.dp_cal_fixed).
//
// One update per `valid` cycle (one per reference cycle, 32 MHz for BLE):
//   A_r += r - (A_r >>> K);   d_r = (r << K) - A_r      (regressor, centred)
//   A_e += e - (A_e >>> K);   d_e = (e << K) - A_e      (phase error, centred)
//   V   += sgn(d_e) * sgn(d_r), saturated to [0, 2^V_BITS - 1]
// The signs use the *updated* accumulators, compared at full precision (no truncation of the
// mean), and sgn(0) = 0 — exactly the reference's `step_codes`. `load` restarts the
// calibrator: V <= v_load, both accumulators <= 0 (the reference's `.value = ...`).
//
// Accumulator width: |A| < 2^(W-1+K) + 2^K for any W-bit input stream (tests/test_dp_cal_lms.py
// checks the bound on saturating streams), so W+K+1 bits hold it; d needs one more.
module dp_cal_lms #(
    parameter int E_BITS = 10,   // phase-error input, signed
    parameter int R_BITS = 12,   // regressor input, signed
    parameter int K      = 10,   // centering EMA = 2^-K
    parameter int V_BITS = 18    // value register, unsigned (LSB = step)
) (
    input  logic                     clk,
    input  logic                     load,
    input  logic [V_BITS-1:0]        v_load,
    input  logic                     valid,
    input  logic signed [E_BITS-1:0] e,
    input  logic signed [R_BITS-1:0] r,
    output logic [V_BITS-1:0]        v
);
    localparam int AE = E_BITS + K + 1;
    localparam int AR = R_BITS + K + 1;
    localparam logic [V_BITS-1:0] V_MAX = '1;

    logic signed [AE-1:0] acc_e, acc_e_n;
    logic signed [AR-1:0] acc_r, acc_r_n;
    logic signed [AE:0]   d_e;
    logic signed [AR:0]   d_r;
    logic                 up, down;

    always_comb begin
        acc_r_n = acc_r + AR'(r) - (acc_r >>> K);
        acc_e_n = acc_e + AE'(e) - (acc_e >>> K);
        d_r     = ((AR+1)'(r) <<< K) - (AR+1)'(acc_r_n);
        d_e     = ((AE+1)'(e) <<< K) - (AE+1)'(acc_e_n);
        // sgn(d_e) * sgn(d_r): +1 when both non-zero with equal signs, -1 when opposite
        up      = (d_e != 0) && (d_r != 0) && (d_e[AE] == d_r[AR]);
        down    = (d_e != 0) && (d_r != 0) && (d_e[AE] != d_r[AR]);
    end

    always_ff @(posedge clk) begin
        if (load) begin
            v     <= v_load;
            acc_e <= '0;
            acc_r <= '0;
        end else if (valid) begin
            acc_e <= acc_e_n;
            acc_r <= acc_r_n;
            if (up && v != V_MAX)   v <= v + 1'b1;
            else if (down && v != '0) v <= v - 1'b1;
        end
    end
endmodule
