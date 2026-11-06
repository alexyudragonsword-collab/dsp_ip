// polar_datapath — the digital polar TX datapath of polar_tx (export/rtl.py emit_datapath),
// wired as polar_tx rtl_vectors.datapath_golden defines it, from this library's block RTL:
//
//   amplitude: env --cfr_clip--> e --(top ADDR_BITS)--> polar_dpd_lut --amp--(top DPA_BITS)-->
//              dpa_thermo_decode --> thermo, bin
//   phase:     finc --dtc_phase_acc--> acc --(align 1)--> acc - (ph << (ACC_W - PH_BITS))
//              --dtc_efm1--> dtc_code          (ph: the LUT's AM-PM correction, subtracted)
//
// One sample per valid clock. Both paths have LATENCY = 3: cfr, lut, decoder registers on the
// amplitude side; accumulator, one alignment register (to meet ph, which needs cfr + lut) and
// the EFM1 output register on the phase side. out_valid is valid delayed by 3; rst clears the
// accumulator and the dither's error register. The ROMs take AMP_INIT / PH_INIT (synthesis) or
// a hierarchical $readmemh into u_lut (testbench).
module polar_datapath #(
    parameter int ENV_BITS  = 12,
    parameter int THRESHOLD = 3071,
    parameter int ADDR_BITS = 8,
    parameter int AMP_BITS  = 12,
    parameter int PH_BITS   = 14,
    parameter int DPA_BITS  = 10,
    parameter int N_THERMO  = 7,
    parameter int ACC_W     = 19,
    parameter int DTC_BITS  = 11,
    parameter     AMP_INIT  = "",
    parameter     PH_INIT   = ""
) (
    input  logic                               clk,
    input  logic                               rst,
    input  logic                               valid,
    input  logic [ENV_BITS-1:0]                env,
    input  logic [ACC_W-1:0]                   finc,
    output logic                               out_valid,
    output logic [(1<<N_THERMO)-2:0]           thermo,
    output logic [DPA_BITS-N_THERMO-1:0]       bin,
    output logic [DTC_BITS-1:0]                dtc_code
);
    localparam int FRAC = ACC_W - DTC_BITS;

    // ---- amplitude path ----------------------------------------------------------------
    logic [ENV_BITS-1:0]       e;
    logic                      clipped;
    logic [AMP_BITS-1:0]       amp;
    logic signed [PH_BITS-1:0] ph;
    cfr_clip #(.W(ENV_BITS), .THRESHOLD(THRESHOLD)) u_cfr (
        .clk(clk), .env(env), .env_clip(e), .clipped(clipped));
    polar_dpd_lut #(.ADDR_BITS(ADDR_BITS), .AMP_BITS(AMP_BITS), .PH_BITS(PH_BITS),
                    .AMP_INIT(AMP_INIT), .PH_INIT(PH_INIT)) u_lut (
        .clk(clk), .addr(e[ENV_BITS-1 -: ADDR_BITS]), .amp(amp), .ph(ph));
    dpa_thermo_decode #(.N_BITS(DPA_BITS), .N_THERMO(N_THERMO)) u_dec (
        .clk(clk), .code(amp[AMP_BITS-1 -: DPA_BITS]), .thermo(thermo), .bin(bin));

    // ---- phase path --------------------------------------------------------------------
    logic [ACC_W-1:0] acc, acc_d, p;
    logic [2:0]       vpipe;
    dtc_phase_acc #(.W(ACC_W)) u_acc (
        .clk(clk), .rst(rst), .valid(valid), .finc(finc), .phase(acc));
    always_ff @(posedge clk) acc_d <= acc;
    // AM-PM correction: pi-scaled PH_BITS signed (one turn = 2^PH_BITS) onto the ACC_W-bit
    // phase word, subtracted modulo 2^ACC_W
    assign p = acc_d - (ACC_W'(ph) << (ACC_W - PH_BITS));
    dtc_efm1 #(.N_BITS(DTC_BITS), .FRAC_BITS(FRAC)) u_efm1 (
        .clk(clk), .rst(rst), .valid(vpipe[1]), .phase_w(p), .code(dtc_code));

    always_ff @(posedge clk) begin
        if (rst) vpipe <= '0;
        else     vpipe <= {vpipe[1:0], valid};
    end
    assign out_valid = vpipe[2];
endmodule
