// cfr_clip — polar-domain crest-factor reduction: the envelope word is hard-limited,
// env_clip = min(env, THRESHOLD), the phase is untouched (polar_tx export/rtl.py
// `cfr_clip_golden`). Registered (LATENCY = 1); `clipped` flags the limited samples.
module cfr_clip #(
    parameter int W         = 12,
    parameter int THRESHOLD = 3071
) (
    input  logic         clk,
    input  logic [W-1:0] env,
    output logic [W-1:0] env_clip,
    output logic         clipped
);
    localparam logic [W-1:0] T = W'(THRESHOLD);
    always_ff @(posedge clk) begin
        clipped  <= env > T;
        env_clip <= (env > T) ? T : env;
    end
endmodule
