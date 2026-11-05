// Lockstep testbench for polar_dpd_lut: load the set's ROM images, stream addr.txt one address
// per clock, dump the registered outputs to rtl_amp.txt / rtl_ph.txt (phase as signed). No
// self-check — tools/lockstep.py compares against amp.txt / ph.txt (check: python).
`timescale 1ns/1ps
module tb_polar_dpd_lut;
    `include "dpd_dims.svh"      // ADDR_BITS AMP_BITS PH_BITS N_VEC

    logic clk = 0;
    logic [ADDR_BITS-1:0]      addr = '0;
    logic [AMP_BITS-1:0]       amp;
    logic signed [PH_BITS-1:0] ph;

    polar_dpd_lut #(.ADDR_BITS(ADDR_BITS), .AMP_BITS(AMP_BITS), .PH_BITS(PH_BITS)) dut (
        .clk(clk), .addr(addr), .amp(amp), .ph(ph));

    always #5 clk = ~clk;

    string vecdir, outdir;
    int fin, fa, fp, i, r;
    longint val;

    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        $readmemh({vecdir, "/dpd_amp.memh"}, dut.rom_amp);
        $readmemh({vecdir, "/dpd_ph.memh"}, dut.rom_ph);
        fin = $fopen({vecdir, "/addr.txt"}, "r");
        fa  = $fopen({outdir, "/rtl_amp.txt"}, "w");
        fp  = $fopen({outdir, "/rtl_ph.txt"}, "w");
        if (fin == 0 || fa == 0 || fp == 0) $fatal(1, "cannot open vector files");
        for (i = 0; i < N_VEC; i++) begin
            r = $fscanf(fin, "%d", val);
            if (r != 1) $fatal(1, "short addr.txt at line %0d", i);
            addr = val[ADDR_BITS-1:0];
            @(posedge clk); #1;
            $fwrite(fa, "%0d\n", amp);
            $fwrite(fp, "%0d\n", ph);
        end
        $fclose(fin); $fclose(fa); $fclose(fp);
        $display("POLAR_DPD_LUT DONE n=%0d", N_VEC);
        $finish;
    end
endmodule
