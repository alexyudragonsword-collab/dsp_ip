// Lockstep testbench for dp_cal_lms: load V_START, stream (dp_cal_err, dp_cal_reg) one
// sample per clock and dump the value register after every update to rtl_value.txt. No
// self-check — tools/lockstep.py compares against dp_cal_value.txt (check: python).
`timescale 1ns/1ps
module tb_dp_cal_lms;
    `include "dp_cal_dims.svh"      // E_BITS R_BITS K V_BITS V_START N_VEC

    logic clk = 0, load = 0, valid = 0;
    logic [V_BITS-1:0]        v_load;
    logic signed [E_BITS-1:0] e;
    logic signed [R_BITS-1:0] r;
    logic [V_BITS-1:0]        v;

    dp_cal_lms #(.E_BITS(E_BITS), .R_BITS(R_BITS), .K(K), .V_BITS(V_BITS)) dut (
        .clk(clk), .load(load), .v_load(v_load), .valid(valid), .e(e), .r(r), .v(v));

    always #5 clk = ~clk;

    string vecdir, outdir;
    int fe, fr, fout, i, re, rr;
    longint ev, rv;

    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        fe   = $fopen({vecdir, "/dp_cal_err.txt"}, "r");
        fr   = $fopen({vecdir, "/dp_cal_reg.txt"}, "r");
        fout = $fopen({outdir, "/rtl_value.txt"}, "w");
        if (fe == 0 || fr == 0 || fout == 0) $fatal(1, "cannot open vector files");
        e = '0; r = '0; v_load = V_BITS'(V_START);
        load = 1;
        @(posedge clk); #1;
        load = 0;
        for (i = 0; i < N_VEC; i++) begin
            re = $fscanf(fe, "%d", ev);
            rr = $fscanf(fr, "%d", rv);
            if (re != 1 || rr != 1) $fatal(1, "short input file at line %0d", i);
            e = ev[E_BITS-1:0];
            r = rv[R_BITS-1:0];
            valid = 1;
            @(posedge clk); #1;
            $fwrite(fout, "%0d\n", v);
        end
        valid = 0;
        $fclose(fe); $fclose(fr); $fclose(fout);
        $display("DP_CAL_LMS DONE n=%0d", N_VEC);
        $finish;
    end
endmodule
