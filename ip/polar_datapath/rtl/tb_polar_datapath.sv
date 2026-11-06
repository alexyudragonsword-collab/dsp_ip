// Lockstep testbench for polar_datapath: load the ROM images, reset, stream (env, finc) one
// sample per clock, drain, and write one line per out_valid cycle to rtl_thermo.txt /
// rtl_bin.txt / rtl_dtc_code.txt (check: python; the order of out_valid samples is the input
// order, so latency never enters the comparison).
`timescale 1ns/1ps
module tb_polar_datapath;
    `include "datapath_dims.svh"
    logic clk = 0, rst = 1, valid = 0, out_valid;
    logic [ENV_BITS-1:0] env = '0;
    logic [ACC_W-1:0] finc = '0;
    logic [(1<<N_THERMO)-2:0] thermo;
    logic [DPA_BITS-N_THERMO-1:0] bin;
    logic [DTC_BITS-1:0] dtc_code;
    polar_datapath #(.ENV_BITS(ENV_BITS), .THRESHOLD(THRESHOLD), .ADDR_BITS(ADDR_BITS),
                     .AMP_BITS(AMP_BITS), .PH_BITS(PH_BITS), .DPA_BITS(DPA_BITS),
                     .N_THERMO(N_THERMO), .ACC_W(ACC_W), .DTC_BITS(DTC_BITS)) dut (
        .clk(clk), .rst(rst), .valid(valid), .env(env), .finc(finc), .out_valid(out_valid),
        .thermo(thermo), .bin(bin), .dtc_code(dtc_code));
    always #5 clk = ~clk;
    string vecdir, outdir;
    int fe, ff, ft, fb, fd, i, re, rf, n_out;
    longint ve, vf;
    always @(posedge clk) #1 if (out_valid) begin
        $fwrite(ft, "%0d\n", thermo);
        $fwrite(fb, "%0d\n", bin);
        $fwrite(fd, "%0d\n", dtc_code);
        n_out++;
    end
    initial begin
        n_out = 0;
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        $readmemh({vecdir, "/dpd_amp.memh"}, dut.u_lut.rom_amp);
        $readmemh({vecdir, "/dpd_ph.memh"}, dut.u_lut.rom_ph);
        fe = $fopen({vecdir, "/env.txt"}, "r");
        ff = $fopen({vecdir, "/finc.txt"}, "r");
        ft = $fopen({outdir, "/rtl_thermo.txt"}, "w");
        fb = $fopen({outdir, "/rtl_bin.txt"}, "w");
        fd = $fopen({outdir, "/rtl_dtc_code.txt"}, "w");
        if (fe == 0 || ff == 0 || ft == 0 || fb == 0 || fd == 0) $fatal(1, "cannot open vector files");
        @(posedge clk); #2;
        rst = 0;
        for (i = 0; i < N_VEC; i++) begin
            re = $fscanf(fe, "%d", ve);
            rf = $fscanf(ff, "%d", vf);
            if (re != 1 || rf != 1) $fatal(1, "short input file at line %0d", i);
            env = ve[ENV_BITS-1:0];
            finc = vf[ACC_W-1:0];
            valid = 1;
            @(posedge clk); #2;
        end
        valid = 0;
        repeat (6) @(posedge clk);
        #2;
        $fclose(fe); $fclose(ff); $fclose(ft); $fclose(fb); $fclose(fd);
        if (n_out != N_VEC) $fatal(1, "out_valid count %0d != %0d", n_out, N_VEC);
        $display("POLAR_DATAPATH DONE n=%0d", N_VEC);
        $finish;
    end
endmodule
