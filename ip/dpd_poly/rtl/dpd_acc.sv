// dpd_acc: accumulator output stage — y = sat(W_OUT, rshift_round(acc, S_OUT)), registered.
//
// Bit-exact with dspip.ip.dpd_poly.datapath.output. The adder tree that produces ``acc``
// lives in dpd_poly's lane generate block (dpd_poly.sv, "accumulation tree"): it must read
// each term's output wire by hierarchical name, because gathering N_TERMS outputs into one
// packed bus with N_TERMS part-select drivers makes Icarus re-resolve the whole bus on
// every driver change (O(N^2) per cycle; 140 terms ran at ~1 s per sample).
// LATENCY = 1 cycle.
module dpd_acc #(
    parameter int W_ACC = 40,
    parameter int W_OUT = 16,
    parameter int S_OUT = 13
) (
    input  logic                    clk,
    input  logic signed [W_ACC-1:0] acc,
    output logic signed [W_OUT-1:0] y
);
    logic [W_OUT-1:0] y_c;
    sat_shift #(.W_IN(W_ACC), .SHIFT(S_OUT), .W_OUT(W_OUT), .SIGNED(1)) u_out (.x(acc), .y(y_c));
    always_ff @(posedge clk) y <= y_c;
endmodule
