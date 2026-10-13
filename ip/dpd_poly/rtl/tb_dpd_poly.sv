// Lockstep testbench for dpd_poly: load coefficients, stream x_re/x_im.txt through the DUT
// P samples per clock, dump every output sample to rtl_y_re.txt / rtl_y_im.txt.
// No self-check — tools/lockstep.py compares against y_re/y_im.txt (check: python).
//
//   $ verilator --binary --timing +incdir+<vecdir> -GP=2 <rtl...> tb_dpd_poly.sv
//   $ obj_dir/Vtb_dpd_poly +vecdir=<vecdir> +outdir=<outdir>
//   $ iverilog -g2012 -I <vecdir> -Ptb_dpd_poly.P=2 -o sim <rtl...> tb_dpd_poly.sv
//
// Streaming protocol (same as the Python reference): N_SAMPLES + LEAD samples are fed
// (the extra LEAD are zeros, = upstream's zero fill), padded with zeros to a multiple of P;
// the first LEAD outputs are dropped and the next N_SAMPLES written.
`timescale 1ns/1ps
module tb_dpd_poly #(
    `include "dims_params.svh"
);
    `include "dims.svh"

    logic clk = 1'b0;
    always #5 clk = ~clk;
    logic rst_n = 1'b0;

    logic                     in_valid = 1'b0;
    logic [P*W_IN-1:0]        x_re = '0, x_im = '0;
    logic                     coef_we = 1'b0;
    logic [15:0]              coef_addr = '0;
    logic signed [W_COEF-1:0] coef_re = '0, coef_im = '0;
    logic                     out_valid;
    logic [P*W_OUT-1:0]       y_re, y_im;

    dpd_poly #(.P(P)) dut (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .x_re(x_re), .x_im(x_im),
        .coef_we(coef_we), .coef_addr(coef_addr), .coef_re(coef_re), .coef_im(coef_im),
        .out_valid(out_valid), .y_re(y_re), .y_im(y_im));

    localparam int N_IN     = N_SAMPLES + LEAD;
    localparam int N_GROUPS = (N_IN + P - 1) / P;

    string vecdir, outdir;
    int fxr, fxi, fwr, fwi, fyr, fyi, r, i, p, g, n_out, n_skip;
    longint vr, vi;
    logic signed [W_IN-1:0] xr_mem [0:N_GROUPS*P-1];
    logic signed [W_IN-1:0] xi_mem [0:N_GROUPS*P-1];
    bit done = 1'b0;

    // ---- output collector ---------------------------------------------------------------
    always @(posedge clk) begin
        if (out_valid && !done) begin
            for (p = 0; p < P; p++) begin
                if (n_skip < LEAD) begin
                    n_skip++;
                end else if (n_out < N_SAMPLES) begin
                    $fwrite(fyr, "%0d\n", $signed(y_re[p*W_OUT +: W_OUT]));
                    $fwrite(fyi, "%0d\n", $signed(y_im[p*W_OUT +: W_OUT]));
                    n_out++;
                end
            end
        end
    end

    initial begin
        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = ".";
        if (!$value$plusargs("outdir=%s", outdir)) outdir = vecdir;
        fxr = $fopen({vecdir, "/x_re.txt"}, "r");
        fxi = $fopen({vecdir, "/x_im.txt"}, "r");
        fwr = $fopen({vecdir, "/w_re.txt"}, "r");
        fwi = $fopen({vecdir, "/w_im.txt"}, "r");
        fyr = $fopen({outdir, "/rtl_y_re.txt"}, "w");
        fyi = $fopen({outdir, "/rtl_y_im.txt"}, "w");
        if (fxr == 0 || fxi == 0 || fwr == 0 || fwi == 0 || fyr == 0 || fyi == 0)
            $fatal(1, "cannot open vector files in %s / %s", vecdir, outdir);
        for (i = 0; i < N_GROUPS * P; i++) begin
            if (i < N_SAMPLES) begin
                r = $fscanf(fxr, "%d", vr);
                if (r != 1) $fatal(1, "short x_re.txt at line %0d", i);
                r = $fscanf(fxi, "%d", vi);
                if (r != 1) $fatal(1, "short x_im.txt at line %0d", i);
                xr_mem[i] = vr[W_IN-1:0];
                xi_mem[i] = vi[W_IN-1:0];
            end else begin
                xr_mem[i] = '0;
                xi_mem[i] = '0;
            end
        end
        $fclose(fxr);
        $fclose(fxi);
        n_out = 0;
        n_skip = 0;

        // reset, then coefficient load
        repeat (3) @(posedge clk);
        #1 rst_n = 1'b1;
        repeat (2) @(posedge clk);
        for (i = 0; i < N_TERMS; i++) begin
            r = $fscanf(fwr, "%d", vr);
            if (r != 1) $fatal(1, "short w_re.txt at line %0d", i);
            r = $fscanf(fwi, "%d", vi);
            if (r != 1) $fatal(1, "short w_im.txt at line %0d", i);
            @(posedge clk);
            #1;
            coef_we   = 1'b1;
            coef_addr = 16'(i);
            coef_re   = vr[W_COEF-1:0];
            coef_im   = vi[W_COEF-1:0];
        end
        @(posedge clk);
        #1 coef_we = 1'b0;
        $fclose(fwr);
        $fclose(fwi);
        repeat (2) @(posedge clk);

        // stream
        for (g = 0; g < N_GROUPS; g++) begin
            @(posedge clk);
            #1;
            in_valid = 1'b1;
            for (p = 0; p < P; p++) begin
                x_re[p*W_IN +: W_IN] = xr_mem[g*P + p];
                x_im[p*W_IN +: W_IN] = xi_mem[g*P + p];
            end
        end
        @(posedge clk);
        #1 in_valid = 1'b0;
        x_re = '0;
        x_im = '0;

        // drain
        i = 0;
        while (n_out < N_SAMPLES && i < 1000) begin
            @(posedge clk);
            i++;
        end
        @(posedge clk);
        done = 1'b1;
        $fclose(fyr);
        $fclose(fyi);
        if (n_out < N_SAMPLES) $fatal(1, "only %0d of %0d outputs after drain", n_out, N_SAMPLES);
        $display("DPD_POLY DONE n=%0d P=%0d lead=%0d", n_out, P, LEAD);
        $finish;
    end
endmodule
