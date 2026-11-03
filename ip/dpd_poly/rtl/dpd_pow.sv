// dpd_pow: envelope powers pw_k = sat_u(W_PW, rshift_round(a^k, Q_k)), k = 1..MAX_K (<= 4).
//
// Bit-exact with dspip.ip.dpd_poly.datapath.power. Computed once per input sample (not per
// term). No multiplier wider than W_ENV x W_ENV: with a^2 = h*2^W + l,
//   a^3 = (h*a) << W + l*a                 (two W x W products)
//   a^4 = (h*h) << 2W + (h*l) << (W+1) + l*l   (three W x W products)
// stage 1: a^2; stage 2: the five W x W products; stage 3: the recombining adds;
// stage 4: rounding shifts + saturation. LATENCY = 4 cycles. The previous form
// (a^3 = a^2*a and a^4 = a^2*a^2 in one stage, 32x16 and 32x32) was the whole datapath's
// critical path: 1837/1883 ps in situ, 1762 ps alone vs 1494 ps for this one (NanGate45
// estimates, tools/synth.py --mode unit). Unused powers (k > MAX_K) are tied to zero.
module dpd_pow #(
    parameter int W_ENV = 16,
    parameter int W_PW  = 16,
    parameter int MAX_K = 4,
    parameter int Q1 = 0,
    parameter int Q2 = 16,
    parameter int Q3 = 32,
    parameter int Q4 = 48
) (
    input  logic             clk,
    input  logic [W_ENV-1:0] a,
    output logic [W_PW-1:0]  pw1,
    output logic [W_PW-1:0]  pw2,
    output logic [W_PW-1:0]  pw3,
    output logic [W_PW-1:0]  pw4
);
    localparam int H = W_ENV;
    // stage 1: a^2
    logic [W_ENV-1:0]   a_q1;
    logic [2*W_ENV-1:0] a2_q1;
    always_ff @(posedge clk) begin
        a_q1  <= a;
        a2_q1 <= a * a;
    end
    // stage 2: the W x W products of the halves of a^2
    logic [W_ENV-1:0] h, l;
    assign h = a2_q1[2*H-1:H];
    assign l = a2_q1[H-1:0];
    logic [W_ENV-1:0]   a_q2;
    logic [2*W_ENV-1:0] a2_q2;
    logic [2*W_ENV-1:0] ha_q2, la_q2, hh_q2, hl_q2, ll_q2;
    always_ff @(posedge clk) begin
        a_q2  <= a_q1;
        a2_q2 <= a2_q1;
        ha_q2 <= h * a_q1;
        la_q2 <= l * a_q1;
        hh_q2 <= h * h;
        hl_q2 <= h * l;
        ll_q2 <= l * l;
    end
    // stage 3: recombine (exact: a^3 and a^4 as integers)
    logic [W_ENV-1:0]   a_q3;
    logic [2*W_ENV-1:0] a2_q3;
    logic [3*W_ENV-1:0] a3_q3;
    logic [4*W_ENV-1:0] a4_q3;
    always_ff @(posedge clk) begin
        a_q3  <= a_q2;
        a2_q3 <= a2_q2;
        a3_q3 <= ((3*W_ENV)'(ha_q2) << H) + (3*W_ENV)'(la_q2);
        a4_q3 <= ((4*W_ENV)'(hh_q2) << (2*H)) + ((4*W_ENV)'(hl_q2) << (H+1)) + (4*W_ENV)'(ll_q2);
    end
    // stage 4: rounding shift + unsigned saturation
    logic [W_PW-1:0] s1, s2, s3, s4;
    sat_shift #(.W_IN(W_ENV),   .SHIFT(Q1), .W_OUT(W_PW), .SIGNED(0)) u1 (.x(a_q3),  .y(s1));
    generate
        if (MAX_K >= 2) begin : g2
            sat_shift #(.W_IN(2*W_ENV), .SHIFT(Q2), .W_OUT(W_PW), .SIGNED(0)) u2 (.x(a2_q3), .y(s2));
        end else begin : n2
            assign s2 = '0;
        end
        if (MAX_K >= 3) begin : g3
            sat_shift #(.W_IN(3*W_ENV), .SHIFT(Q3), .W_OUT(W_PW), .SIGNED(0)) u3 (.x(a3_q3), .y(s3));
        end else begin : n3
            assign s3 = '0;
        end
        if (MAX_K >= 4) begin : g4
            sat_shift #(.W_IN(4*W_ENV), .SHIFT(Q4), .W_OUT(W_PW), .SIGNED(0)) u4 (.x(a4_q3), .y(s4));
        end else begin : n4
            assign s4 = '0;
        end
    endgenerate
    always_ff @(posedge clk) begin
        pw1 <= s1;
        pw2 <= s2;
        pw3 <= s3;
        pw4 <= s4;
    end
endmodule
