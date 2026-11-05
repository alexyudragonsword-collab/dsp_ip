// polar_dpd_lut — the polar TX's static predistorter: two ROMs indexed by the envelope command,
// the predistorted DPA code (AM-AM inverse, unsigned) and the phase correction (AM-PM, signed,
// pi-scaled). RTL of polar_tx export/rtl.py `quantize_dpd_luts` / `emit_dpd_rtl`.
//
// The ROM contents are the consumer's export (dpd_amp.memh / dpd_ph.memh). The testbench loads
// them by hierarchical $readmemh; synthesis passes their paths as AMP_INIT / PH_INIT, so the
// estimate is for these contents (a ROM maps to logic that depends on what it holds).
// Registered output: data for addr appears on the next clock edge (LATENCY = 1).
module polar_dpd_lut #(
    parameter int    ADDR_BITS = 8,
    parameter int    AMP_BITS  = 12,
    parameter int    PH_BITS   = 14,
    parameter        AMP_INIT  = "",    // untyped: yosys does not take `parameter string`
    parameter        PH_INIT   = ""
) (
    input  logic                       clk,
    input  logic [ADDR_BITS-1:0]       addr,
    output logic [AMP_BITS-1:0]        amp,
    output logic signed [PH_BITS-1:0]  ph
);
    logic [AMP_BITS-1:0] rom_amp [0:(1<<ADDR_BITS)-1];
    logic [PH_BITS-1:0]  rom_ph  [0:(1<<ADDR_BITS)-1];
    initial begin
        if (AMP_INIT != "") $readmemh(AMP_INIT, rom_amp);
        if (PH_INIT != "")  $readmemh(PH_INIT, rom_ph);
    end
    always_ff @(posedge clk) begin
        amp <= rom_amp[addr];
        ph  <= $signed(rom_ph[addr]);
    end
endmodule
