// Lockstep testbench for cfr_clip: one envelope word per clock from env.txt, the registered
// outputs to rtl_env_clip.txt / rtl_clipped.txt (check: python).
`timescale 1ns/1ps
module tb_cfr_clip;
    `include "cfr_dims.svh"      // W THRESHOLD N_VEC
    logic clk = 0;
    logic [W-1:0] env = '0, env_clip;
    logic clipped;
    cfr_clip #(.W(W), .THRESHOLD(THRESHOLD)) dut (.clk(clk), .env(env), .env_clip(env_clip),
                                                  .clipped(clipped));
    always #5 clk = ~clk;
    string vecdir, outdir;
    int fin, fo, fc, i, r;
    longint val;
    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        fin = $fopen({vecdir, "/env.txt"}, "r");
        fo  = $fopen({outdir, "/rtl_env_clip.txt"}, "w");
        fc  = $fopen({outdir, "/rtl_clipped.txt"}, "w");
        if (fin == 0 || fo == 0 || fc == 0) $fatal(1, "cannot open vector files");
        for (i = 0; i < N_VEC; i++) begin
            r = $fscanf(fin, "%d", val);
            if (r != 1) $fatal(1, "short env.txt at line %0d", i);
            env = val[W-1:0];
            @(posedge clk); #1;
            $fwrite(fo, "%0d\n", env_clip);
            $fwrite(fc, "%0d\n", clipped);
        end
        $fclose(fin); $fclose(fo); $fclose(fc);
        $display("CFR_CLIP DONE n=%0d", N_VEC);
        $finish;
    end
endmodule
