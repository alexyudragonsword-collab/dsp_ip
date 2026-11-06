// dpa_thermo_decode — segmented DPA amplitude decoder (polar_tx export/rtl.py
// `thermo_decode_golden`): code = sel[N_THERMO] . bin[N_BITS - N_THERMO]; thermometer bit g is
// on iff g < sel (2^N_THERMO - 1 unary segments), the low bits drive binary-weighted cells.
// Registered (LATENCY = 1). N_THERMO >= 1 and N_BITS > N_THERMO assumed.
module dpa_thermo_decode #(
    parameter int N_BITS   = 10,
    parameter int N_THERMO = 7
) (
    input  logic                         clk,
    input  logic [N_BITS-1:0]            code,
    output logic [(1<<N_THERMO)-2:0]     thermo,
    output logic [N_BITS-N_THERMO-1:0]   bin
);
    localparam int NSEG = (1 << N_THERMO) - 1;
    localparam int NBIN = N_BITS - N_THERMO;
    logic [N_THERMO-1:0] sel;
    logic [NSEG-1:0]     t;
    assign sel = code[N_BITS-1:NBIN];
    always_comb
        for (int g = 0; g < NSEG; g++) t[g] = (N_THERMO'(g) < sel);
    always_ff @(posedge clk) begin
        thermo <= t;
        bin    <= code[NBIN-1:0];
    end
endmodule
