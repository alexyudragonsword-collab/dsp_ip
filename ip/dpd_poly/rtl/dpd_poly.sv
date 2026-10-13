// dpd_poly: fixed-point polynomial DPD datapath (DDR-Volterra / GMP bases), P samples/clock.
//
// Streaming implementation of dspip.ip.dpd_poly.ref (the bit-true reference):
//   per input sample : envelope a = isqrt(I^2+Q^2)  ->  powers pw_1..4      (dpd_env, dpd_pow)
//   history windows  : one flat window of x and one of powers, shifted by P every valid cycle;
//                      lane p / term c taps entry (P-1-p) + idx  (idx from dims.svh, pure wiring)
//   per lane, term   : dpd_term  (env product, x*env, column quantization, coefficient multiply)
//   per lane         : dpd_acc   (adder tree, output shift + saturation)
// Every width, shift and tap index comes from the generated dims_params.svh / dims.svh
// (one source with the Python reference). Coefficients are loaded through coef_* (real
// registers, so synthesis keeps real multipliers).
//
// Sample order: x_re[p*W_IN +: W_IN] is sample t+p of the group entering this cycle; the
// output lane p is the DPD output of sample t+p-LEAD (GMP's leading envelope needs one
// future sample, so the output stream runs LEAD samples late: the consumer drops the first
// LEAD outputs). Latency is fixed: out_valid is in_valid delayed by TOTAL_LAT.
module dpd_poly #(
    `include "dims_params.svh"
) (
    input  logic                     clk,
    input  logic                     rst_n,
    input  logic                     in_valid,
    input  logic [P*W_IN-1:0]        x_re,
    input  logic [P*W_IN-1:0]        x_im,
    input  logic                     coef_we,
    input  logic [15:0]              coef_addr,
    input  logic signed [W_COEF-1:0] coef_re,
    input  logic signed [W_COEF-1:0] coef_im,
    output logic                     out_valid,
    output logic [P*W_OUT-1:0]       y_re,
    output logic [P*W_OUT-1:0]       y_im
);
    `include "dims.svh"     // ENV_FRAC S_OUT Q_PW1..4 TF_BITS T_XD T_ED0 T_K0 T_ED1 T_K1 T_QP T_SH T_AL

    localparam int ENV_LAT   = W_ENV + 1;
    localparam int POW_LAT   = 3;
    localparam int FE_LAT    = ENV_LAT + POW_LAT;      // front end: x must be delayed as much
    localparam int TERM_LAT  = 4;
    localparam int LV        = (N_TERMS <= 1) ? 1 : $clog2(N_TERMS);
    localparam int ACC_LAT   = LV / 2 + 1;
    localparam int TOTAL_LAT = FE_LAT + 1 + TERM_LAT + ACC_LAT;   // +1: window register
    localparam int XW        = P + X_DEPTH - 1;        // x window entries
    localparam int EW        = P + ENV_DEPTH - 1;      // power window entries
    localparam int PWB       = 4 * W_PW;               // one power-window entry: pw1..pw4

    // ---- coefficient registers (written through the load port) -------------------------
    // declared per term inside the generate block below (w_re_q / w_im_q)

    // ---- front end per lane -------------------------------------------------------------
    // x and in_valid delayed FE_LAT cycles to meet the powers (stage d holds the input of
    // d cycles ago; a single clocked process so no array mixes drivers)
    logic [P*W_IN-1:0]  xre_d [1:FE_LAT];
    logic [P*W_IN-1:0]  xim_d [1:FE_LAT];
    logic [FE_LAT:1]    vld_d;
    integer d;
    always_ff @(posedge clk) begin
        xre_d[1] <= x_re;
        xim_d[1] <= x_im;
        for (d = 2; d <= FE_LAT; d++) begin
            xre_d[d] <= xre_d[d-1];
            xim_d[d] <= xim_d[d-1];
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) vld_d <= '0;
        else begin
            vld_d[1] <= in_valid;
            for (d = 2; d <= FE_LAT; d++) vld_d[d] <= vld_d[d-1];
        end
    end

    logic [P*PWB-1:0] pw_lane;   // powers of the P new samples, aligned with xre_d[FE_LAT]
    generate
        for (genvar p = 0; p < P; p++) begin : FE
            logic [W_ENV-1:0] a;
            logic [W_PW-1:0] pw1, pw2, pw3, pw4;
            dpd_env #(.W_IN(W_IN), .ENV_FRAC(ENV_FRAC), .W_ENV(W_ENV)) u_env (
                .clk(clk), .x_re(x_re[p*W_IN +: W_IN]), .x_im(x_im[p*W_IN +: W_IN]), .a(a));
            dpd_pow #(.W_ENV(W_ENV), .W_PW(W_PW), .MAX_K(MAX_K),
                      .Q1(Q_PW1), .Q2(Q_PW2), .Q3(Q_PW3), .Q4(Q_PW4)) u_pow (
                .clk(clk), .a(a), .pw1(pw1), .pw2(pw2), .pw3(pw3), .pw4(pw4));
            assign pw_lane[p*PWB +: PWB] = {pw4, pw3, pw2, pw1};
        end
    endgenerate

    // ---- history windows (entry 0 = newest sample) ---------------------------------------
    // packed vectors, entry j at [j*W +: W] (unpacked arrays make Icarus re-evaluate every
    // reader of the array whenever any word changes)
    logic [XW*W_IN-1:0] xw_re, xw_im;
    logic [EW*PWB-1:0]  pww;
    logic               win_valid;
    integer j;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            xw_re <= '0;
            xw_im <= '0;
            pww   <= '0;
            win_valid <= 1'b0;
        end else begin
            win_valid <= vld_d[FE_LAT];
            if (vld_d[FE_LAT]) begin
                for (j = 0; j < XW; j++) begin
                    if (j < P) begin
                        xw_re[j*W_IN +: W_IN] <= xre_d[FE_LAT][(P-1-j)*W_IN +: W_IN];
                        xw_im[j*W_IN +: W_IN] <= xim_d[FE_LAT][(P-1-j)*W_IN +: W_IN];
                    end else begin
                        xw_re[j*W_IN +: W_IN] <= xw_re[(j-P)*W_IN +: W_IN];
                        xw_im[j*W_IN +: W_IN] <= xw_im[(j-P)*W_IN +: W_IN];
                    end
                end
                for (j = 0; j < EW; j++) begin
                    if (j < P) pww[j*PWB +: PWB] <= pw_lane[(P-1-j)*PWB +: PWB];
                    else       pww[j*PWB +: PWB] <= pww[(j-P)*PWB +: PWB];
                end
            end
        end
    end

    // ---- terms and accumulation per lane ------------------------------------------------
    localparam int NP = 1 << LV;    // adder tree leaves (padded)
    generate
        for (genvar p = 0; p < P; p++) begin : LANE
            for (genvar c = 0; c < N_TERMS; c++) begin : T
                localparam int XD = T_XD [c*TF_BITS +: TF_BITS];
                localparam int ED0 = T_ED0[c*TF_BITS +: TF_BITS];
                localparam int K0 = T_K0 [c*TF_BITS +: TF_BITS];
                localparam int ED1 = T_ED1[c*TF_BITS +: TF_BITS];
                localparam int K1 = T_K1 [c*TF_BITS +: TF_BITS];
                localparam int QP = T_QP [c*TF_BITS +: TF_BITS];
                localparam int SH = T_SH [c*TF_BITS +: TF_BITS];
                localparam int AL = T_AL [c*TF_BITS +: TF_BITS];
                localparam int XI = (P - 1 - p) + XD;
                localparam int EI0 = (P - 1 - p) + ED0;
                localparam int EI1 = (P - 1 - p) + ED1;
                // power selection: entry {pw4, pw3, pw2, pw1}, k-th power at [(k-1)*W_PW +: W_PW]
                logic [W_PW-1:0] pw0_sel, pw1_sel;
                if (K0 == 0) begin : nk0
                    assign pw0_sel = '0;
                end else begin : k0
                    assign pw0_sel = pww[EI0*PWB + (K0-1)*W_PW +: W_PW];
                end
                if (K1 == 0) begin : nk1
                    assign pw1_sel = '0;
                end else begin : k1
                    assign pw1_sel = pww[EI1*PWB + (K1-1)*W_PW +: W_PW];
                end
                // coefficient registers
                logic signed [W_COEF-1:0] w_re_q, w_im_q;
                always_ff @(posedge clk or negedge rst_n) begin
                    if (!rst_n) begin
                        w_re_q <= '0;
                        w_im_q <= '0;
                    end else if (coef_we && coef_addr == 16'(c)) begin
                        w_re_q <= coef_re;
                        w_im_q <= coef_im;
                    end
                end
                logic signed [W_ACC-1:0] p_re, p_im;   // this term's aligned product
                dpd_term #(.W_IN(W_IN), .W_PW(W_PW), .W_PHI(W_PHI), .W_COEF(W_COEF), .W_ACC(W_ACC),
                           .K0(K0), .K1(K1), .Q_PAIR(QP), .SH(SH), .AL(AL)) u_term (
                    .clk(clk), .x_re(xw_re[XI*W_IN +: W_IN]), .x_im(xw_im[XI*W_IN +: W_IN]),
                    .pw0(pw0_sel), .pw1(pw1_sel),
                    .w_re(w_re_q), .w_im(w_im_q), .p_re(p_re), .p_im(p_im));
            end

            // ---- accumulation tree: one wire per node, a register every 2 levels ----------
            // (ri = 0: real, 1: imaginary). Reads each term's output by hierarchical name;
            // see dpd_acc.sv for why there is no packed term bus. LATENCY = LV/2 (+1 in dpd_acc).
            for (genvar ri = 0; ri < 2; ri++) begin : RI
                for (genvar l = 0; l <= LV; l++) begin : L
                    localparam int NN = NP >> l;
                    for (genvar i = 0; i < NN; i++) begin : gi
                        logic signed [W_ACC-1:0] s;
                        if (l == 0) begin : leaf
                            if (i < N_TERMS) begin : used
                                if (ri == 0) begin : re
                                    assign s = T[i].p_re;
                                end else begin : im
                                    assign s = T[i].p_im;
                                end
                            end else begin : pad
                                assign s = '0;
                            end
                        end else if ((l % 2) == 0) begin : r
                            always_ff @(posedge clk) s <= L[l-1].gi[2*i].s + L[l-1].gi[2*i+1].s;
                        end else begin : c
                            assign s = L[l-1].gi[2*i].s + L[l-1].gi[2*i+1].s;
                        end
                    end
                end
                logic signed [W_OUT-1:0] y_l;
                dpd_acc #(.W_ACC(W_ACC), .W_OUT(W_OUT), .S_OUT(S_OUT)) u_acc (
                    .clk(clk), .acc(L[LV].gi[0].s), .y(y_l));
            end
            assign y_re[p*W_OUT +: W_OUT] = RI[0].y_l;
            assign y_im[p*W_OUT +: W_OUT] = RI[1].y_l;
        end
    endgenerate

    // ---- valid pipeline through terms + accumulation ------------------------------------
    localparam int BACK_LAT = TERM_LAT + ACC_LAT;
    logic [BACK_LAT-1:0] vpipe;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) vpipe <= '0;
        else        vpipe <= {vpipe[BACK_LAT-2:0], win_valid};
    end
    assign out_valid = vpipe[BACK_LAT-1];
endmodule
