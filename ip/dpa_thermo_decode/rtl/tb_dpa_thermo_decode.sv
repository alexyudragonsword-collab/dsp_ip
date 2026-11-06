// Lockstep testbench for dpa_thermo_decode: one code per clock from code.txt, the registered
// thermometer word (decimal, up to 127 bits) and binary cells to rtl_thermo.txt / rtl_bin.txt.
`timescale 1ns/1ps
module tb_dpa_thermo_decode;
    `include "thermo_dims.svh"   // N_BITS N_THERMO N_VEC
    logic clk = 0;
    logic [N_BITS-1:0] code = '0;
    logic [(1<<N_THERMO)-2:0] thermo;
    logic [N_BITS-N_THERMO-1:0] bin;
    dpa_thermo_decode #(.N_BITS(N_BITS), .N_THERMO(N_THERMO)) dut (
        .clk(clk), .code(code), .thermo(thermo), .bin(bin));
    always #5 clk = ~clk;
    string vecdir, outdir;
    int fin, ft, fb, i, r;
    longint val;
    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        fin = $fopen({vecdir, "/code.txt"}, "r");
        ft  = $fopen({outdir, "/rtl_thermo.txt"}, "w");
        fb  = $fopen({outdir, "/rtl_bin.txt"}, "w");
        if (fin == 0 || ft == 0 || fb == 0) $fatal(1, "cannot open vector files");
        for (i = 0; i < N_VEC; i++) begin
            r = $fscanf(fin, "%d", val);
            if (r != 1) $fatal(1, "short code.txt at line %0d", i);
            code = val[N_BITS-1:0];
            @(posedge clk); #1;
            $fwrite(ft, "%0d\n", thermo);
            $fwrite(fb, "%0d\n", bin);
        end
        $fclose(fin); $fclose(ft); $fclose(fb);
        $display("DPA_THERMO_DECODE DONE n=%0d", N_VEC);
        $finish;
    end
endmodule
