// Lockstep testbench for sat_shift: stream x.txt through the DUT and dump every output to
// rtl_y.txt. No self-check — tools/lockstep.py compares against y.txt (check: python).
//
//   $ verilator --binary --timing +incdir+<vecdir> sat_shift.sv tb_sat_shift.sv
//   $ obj_dir/Vtb_sat_shift +vecdir=<vecdir> +outdir=<outdir>
//   $ iverilog -g2012 -I <vecdir> -o sim sat_shift.sv tb_sat_shift.sv && vvp sim +vecdir=...
`timescale 1ns/1ps
module tb_sat_shift;
    `include "dims.svh"      // W_IN SHIFT W_OUT SIGNED N_SAMPLES

    logic [W_IN-1:0]  x;
    logic [W_OUT-1:0] y;

    sat_shift #(.W_IN(W_IN), .SHIFT(SHIFT), .W_OUT(W_OUT), .SIGNED(SIGNED)) dut (.x(x), .y(y));

    string vecdir, outdir;
    int fin, fout, i, r;
    longint val;

    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        fin  = $fopen({vecdir, "/x.txt"}, "r");
        fout = $fopen({outdir, "/rtl_y.txt"}, "w");
        if (fin == 0 || fout == 0) $fatal(1, "cannot open vector files");
        for (i = 0; i < N_SAMPLES; i++) begin
            r = $fscanf(fin, "%d", val);
            if (r != 1) $fatal(1, "short x.txt at line %0d", i);
            x = val[W_IN-1:0];
            #1;
            if (SIGNED == 1) $fwrite(fout, "%0d\n", $signed(y));
            else             $fwrite(fout, "%0d\n", y);
        end
        $fclose(fin);
        $fclose(fout);
        $display("SAT_SHIFT DONE n=%0d", N_SAMPLES);
        $finish;
    end
endmodule
