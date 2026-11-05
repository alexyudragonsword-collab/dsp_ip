// Lockstep testbench for dtc_efm1: reset, stream phase_w.txt one word per clock, dump the code
// after every update to rtl_code.txt. No self-check — tools/lockstep.py compares against
// code.txt (check: python).
`timescale 1ns/1ps
module tb_dtc_efm1;
    `include "dtc_dims.svh"      // N_BITS FRAC_BITS N_VEC

    logic clk = 0, rst = 1, valid = 0;
    logic [N_BITS+FRAC_BITS-1:0] phase_w = '0;
    logic [N_BITS-1:0]           code;

    dtc_efm1 #(.N_BITS(N_BITS), .FRAC_BITS(FRAC_BITS)) dut (
        .clk(clk), .rst(rst), .valid(valid), .phase_w(phase_w), .code(code));

    always #5 clk = ~clk;

    string vecdir, outdir;
    int fin, fout, i, r;
    longint val;

    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        fin  = $fopen({vecdir, "/phase_w.txt"}, "r");
        fout = $fopen({outdir, "/rtl_code.txt"}, "w");
        if (fin == 0 || fout == 0) $fatal(1, "cannot open vector files");
        @(posedge clk); #1;
        rst = 0;
        for (i = 0; i < N_VEC; i++) begin
            r = $fscanf(fin, "%d", val);
            if (r != 1) $fatal(1, "short phase_w.txt at line %0d", i);
            phase_w = val[N_BITS+FRAC_BITS-1:0];
            valid = 1;
            @(posedge clk); #1;
            $fwrite(fout, "%0d\n", code);
        end
        valid = 0;
        $fclose(fin); $fclose(fout);
        $display("DTC_EFM1 DONE n=%0d", N_VEC);
        $finish;
    end
endmodule
