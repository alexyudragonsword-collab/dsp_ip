// sat_shift: rounding arithmetic right shift + saturation.
//
//   y = sat(W_OUT, (x + 2^(SHIFT-1)) >>> SHIFT)      (round-half-up, SHIFT >= 0)
//
// Bit-exact with dspip.fixed.rshift_round_py + saturate_py (SIGNED=1) /
// saturate_u_py (SIGNED=0). Pure combinational; the user registers around it.
// SV `>>>` on a signed operand is an arithmetic shift, matching Python `>>`.
module sat_shift #(
    parameter int W_IN   = 40,
    parameter int SHIFT  = 12,
    parameter int W_OUT  = 16,
    parameter int SIGNED = 1
) (
    input  logic [W_IN-1:0]  x,
    output logic [W_OUT-1:0] y
);
    // one extra bit so the rounding add cannot overflow W_IN
    localparam int WR = W_IN + 1;
    logic signed [WR-1:0] xs, rounded, shifted;
    logic        [WR-1:0] xu, roundedu, shiftedu;

    localparam logic signed [WR-1:0] HALF = (SHIFT > 0) ? (WR'(1) <<< (SHIFT - 1)) : WR'(0);
    localparam logic signed [WR-1:0] S_HI = (WR'(1) <<< (W_OUT - 1)) - 1;
    localparam logic signed [WR-1:0] S_LO = -(WR'(1) <<< (W_OUT - 1));
    localparam logic        [WR-1:0] U_HI = (WR'(1) << W_OUT) - 1;

    always_comb begin
        if (SIGNED == 1) begin
            xs      = WR'(signed'(x));           // sign-extend
            rounded = xs + HALF;
            shifted = rounded >>> SHIFT;
            if (shifted > S_HI)      y = W_OUT'(S_HI);
            else if (shifted < S_LO) y = W_OUT'(S_LO);
            else                     y = W_OUT'(shifted);
            xu = '0; roundedu = '0; shiftedu = '0;
        end else begin
            xu       = WR'(x);                   // zero-extend
            roundedu = xu + WR'(HALF);
            shiftedu = roundedu >> SHIFT;
            if (shiftedu > U_HI) y = W_OUT'(U_HI);
            else                 y = W_OUT'(shiftedu);
            xs = '0; rounded = '0; shifted = '0;
        end
    end
endmodule
