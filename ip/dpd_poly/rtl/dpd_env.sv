// dpd_env: envelope a = isqrt((re^2 + im^2) << 2*ENV_FRAC), unsigned W_ENV bits.
//
// Bit-exact with dspip.ip.dpd_poly.datapath.envelope (truncating integer sqrt).
// Pipelined restoring square root: one bit-pair of the radicand per stage, W_ENV stages,
// plus one register for the two squares and one for their sum (both in one stage was
// 1789 ps, NanGate45 estimate, a 16x16 multiply alone ~1680). LATENCY = W_ENV + 2 cycles,
// one result per cycle.
module dpd_env #(
    parameter int W_IN     = 16,
    parameter int ENV_FRAC = 0,
    parameter int W_ENV    = 16        // = W_IN + ENV_FRAC
) (
    input  logic                    clk,
    input  logic signed [W_IN-1:0]  x_re,
    input  logic signed [W_IN-1:0]  x_im,
    output logic        [W_ENV-1:0] a
);
    localparam int WR = 2 * W_ENV;     // radicand width: (2^(W_IN-1))^2 * 2 * 2^(2F) < 2^WR
    localparam int WM = W_ENV + 2;     // partial remainder width (see datapath notes)

    // stage 0a: squares; 0b: radicand
    logic [WR-1:0] rad_q;
    logic [2*W_IN:0] sq_re_q, sq_im_q, sq_sum;
    always_ff @(posedge clk) begin
        sq_re_q <= (2*W_IN+1)'(x_re * x_re);
        sq_im_q <= (2*W_IN+1)'(x_im * x_im);
    end
    assign sq_sum = sq_re_q + sq_im_q;
    always_ff @(posedge clk) rad_q <= WR'(sq_sum) << (2 * ENV_FRAC);

    // stages 1..W_ENV: restoring sqrt, MSB pair first
    generate
        for (genvar s = 0; s < W_ENV; s++) begin : S
            localparam int BIT = 2 * (W_ENV - 1 - s);
            logic [WR-1:0]    rad;    // radicand carried along the pipe
            logic [WM-1:0]    rem;    // partial remainder after this stage
            logic [W_ENV-1:0] root;   // root bits decided so far (LSB-aligned)
            logic [WM-1:0]    rem_in, rem_sh, trial;
            logic [W_ENV-1:0] root_in;
            logic [WR-1:0]    rad_in;
            if (s == 0) begin : first
                assign rem_in  = '0;
                assign root_in = '0;
                assign rad_in  = rad_q;
            end else begin : next
                assign rem_in  = S[s-1].rem;
                assign root_in = S[s-1].root;
                assign rad_in  = S[s-1].rad;
            end
            assign rem_sh = {rem_in[WM-3:0], rad_in[BIT+1:BIT]};
            assign trial  = {root_in, 2'b01};
            always_ff @(posedge clk) begin
                rad <= rad_in;
                if (rem_sh >= trial) begin
                    rem  <= rem_sh - trial;
                    root <= {root_in[W_ENV-2:0], 1'b1};
                end else begin
                    rem  <= rem_sh;
                    root <= {root_in[W_ENV-2:0], 1'b0};
                end
            end
        end
    endgenerate
    assign a = S[W_ENV-1].root;
endmodule
