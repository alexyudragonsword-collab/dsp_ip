// dpd_term: one basis term of one output lane.
//
//   envp = 1                                  (K0 == 0: the linear term)
//        = pw0                                (one envelope factor)
//        = sat_u(W_PW, rshift_round(pw0*pw1, Q_PAIR))   (two factors, DDR r=1 envelope terms)
//   phi  = x * envp                           (complex x real)
//   code = sat(W_PHI, rshift_round(phi, SH))  (column quantization to the exported grid)
//   prod = code * w                           (complex, 4 real multiplies)
//   out  = prod << AL                         (alignment to the common accumulator exponent)
//
// Bit-exact with dspip.ip.dpd_poly.datapath (env_product, term_phi, quantize_phi, cmul).
// The tap selection (which window entry, which power) is done by the parent; this module
// only sees the already-selected x and pw values. Five register stages (LATENCY = 5) so
// every term has the same latency whatever its K0/K1.
module dpd_term #(
    parameter int W_IN   = 16,
    parameter int W_PW   = 16,
    parameter int W_PHI  = 16,
    parameter int W_COEF = 16,
    parameter int W_ACC  = 40,
    parameter int K0     = 1,     // 0: no envelope factor
    parameter int K1     = 0,     // 0: single factor
    parameter int Q_PAIR = 0,
    parameter int SH     = 0,
    parameter int AL     = 0
) (
    input  logic                     clk,
    input  logic signed [W_IN-1:0]   x_re,
    input  logic signed [W_IN-1:0]   x_im,
    input  logic        [W_PW-1:0]   pw0,
    input  logic        [W_PW-1:0]   pw1,
    input  logic signed [W_COEF-1:0] w_re,
    input  logic signed [W_COEF-1:0] w_im,
    output logic signed [W_ACC-1:0]  p_re,
    output logic signed [W_ACC-1:0]  p_im
);
    localparam int W_PHIW = W_IN + W_PW + 1;        // x (signed) * envp (unsigned, +1 sign bit)
    localparam int W_PROD = W_COEF + W_PHI + 1;     // a*b +/- c*d

    // ---- stage 1a/1b: envelope product (multiply, register, then round/saturate) --------
    // Two stages so the W_PW x W_PW multiply and the rounding adder + saturation compare
    // are not in one path: that single stage was the DDR critical path (1948 ps vs 1306 ps
    // for GMP, NanGate45 estimate). Terms without a second factor just delay twice.
    logic [W_PW-1:0] envp;
    generate
        if (K0 == 0) begin : lin
            assign envp = W_PW'(1);
        end else if (K1 == 0) begin : one
            logic [W_PW-1:0] pw0_q;
            always_ff @(posedge clk) pw0_q <= pw0;
            assign envp = pw0_q;
        end else begin : two
            logic [2*W_PW-1:0] pp_q;
            always_ff @(posedge clk) pp_q <= pw0 * pw1;
            sat_shift #(.W_IN(2*W_PW), .SHIFT(Q_PAIR), .W_OUT(W_PW), .SIGNED(0)) u_pair (.x(pp_q), .y(envp));
        end
    endgenerate
    logic [W_PW-1:0]        envp_q;
    logic signed [W_IN-1:0] xre_d1, xim_d1, xre_q, xim_q;
    always_ff @(posedge clk) begin
        xre_d1 <= x_re;
        xim_d1 <= x_im;
        envp_q <= envp;
        xre_q  <= xre_d1;
        xim_q  <= xim_d1;
    end

    // ---- stage 2: phi = x * envp ------------------------------------------------------
    logic signed [W_PHIW-1:0] phi_re_q, phi_im_q;
    always_ff @(posedge clk) begin
        phi_re_q <= xre_q * $signed({1'b0, envp_q});
        phi_im_q <= xim_q * $signed({1'b0, envp_q});
    end

    // ---- stage 3: column quantization ---------------------------------------------------
    logic [W_PHI-1:0] code_re_c, code_im_c;
    sat_shift #(.W_IN(W_PHIW), .SHIFT(SH), .W_OUT(W_PHI), .SIGNED(1)) u_qre (.x(phi_re_q), .y(code_re_c));
    sat_shift #(.W_IN(W_PHIW), .SHIFT(SH), .W_OUT(W_PHI), .SIGNED(1)) u_qim (.x(phi_im_q), .y(code_im_c));
    logic signed [W_PHI-1:0] code_re_q, code_im_q;
    always_ff @(posedge clk) begin
        code_re_q <= code_re_c;
        code_im_q <= code_im_c;
    end

    // ---- stage 4: complex multiply with the coefficient ---------------------------------
    logic signed [W_PROD-1:0] pr_q, pi_q;
    always_ff @(posedge clk) begin
        pr_q <= (W_PROD)'(code_re_q * w_re) - (W_PROD)'(code_im_q * w_im);
        pi_q <= (W_PROD)'(code_re_q * w_im) + (W_PROD)'(code_im_q * w_re);
    end

    // ---- alignment (wiring) -----------------------------------------------------------
    assign p_re = W_ACC'(pr_q) <<< AL;
    assign p_im = W_ACC'(pi_q) <<< AL;
endmodule
