// Lockstep testbench for dtc_phase_acc: reset, one frequency word per clock from finc.txt,
// the phase after every update to rtl_phase.txt (check: python).
`timescale 1ns/1ps
module tb_dtc_phase_acc;
    `include "acc_dims.svh"      // W N_VEC
    logic clk = 0, rst = 1, valid = 0;
    logic [W-1:0] finc = '0, phase;
    dtc_phase_acc #(.W(W)) dut (.clk(clk), .rst(rst), .valid(valid), .finc(finc), .phase(phase));
    always #5 clk = ~clk;
    string vecdir, outdir;
    int fin, fo, i, r;
    longint val;
    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        fin = $fopen({vecdir, "/finc.txt"}, "r");
        fo  = $fopen({outdir, "/rtl_phase.txt"}, "w");
        if (fin == 0 || fo == 0) $fatal(1, "cannot open vector files");
        @(posedge clk); #1;
        rst = 0;
        for (i = 0; i < N_VEC; i++) begin
            r = $fscanf(fin, "%d", val);
            if (r != 1) $fatal(1, "short finc.txt at line %0d", i);
            finc = val[W-1:0];
            valid = 1;
            @(posedge clk); #1;
            $fwrite(fo, "%0d\n", phase);
        end
        $fclose(fin); $fclose(fo);
        $display("DTC_PHASE_ACC DONE n=%0d", N_VEC);
        $finish;
    end
endmodule
