# Draft issue for verilator/verilator (not filed from this repository: no write access)

Copy the block below into a new issue at https://github.com/verilator/verilator/issues.
When it is filed, put the issue number in `ROADMAP.md` (推回上游) and
`docs/upstream-findings.md` (Verilator section), and drop this file.

---

**Title:** Constant folding of `>>>` with a 64-bit (`longint`) shift amount yields 0

**Version:** Verilator 5.020 2024-01-01 (Debian/Ubuntu 24.04 package `verilator 5.020-1`),
`--binary --timing`. Icarus Verilog 12 gives the expected values.

**Reproducer** (`t.sv`):

```systemverilog
module t;
    localparam longint SH_L = 4;
    localparam int     SH_I = 4;
    longint a;
    initial begin
        a = 16 <<< 14;   // 262144
        $display("a>>>SH_longint=%0d a>>>SH_int=%0d a>>SH_longint=%0d a>>>4=%0d expect=16384",
                 a >>> SH_L, a >>> SH_I, a >> SH_L, a >>> 4);
        $finish;
    end
endmodule
```

```
$ verilator --binary --timing -Wno-WIDTH --top-module t --Mdir obj t.sv && obj/Vt
a>>>SH_longint=0 a>>>SH_int=16384 a>>SH_longint=16384 a>>>4=16384 expect=16384
$ iverilog -g2012 -o t.vvp t.sv && vvp -n t.vvp
a>>>SH_longint=16384 a>>>SH_int=16384 a>>SH_longint=16384 a>>>4=16384 expect=16384
```

**Observations**

- Only the arithmetic right shift with a `localparam longint` (64-bit) shift amount is wrong;
  an `int` amount, a literal, and the logical `>>` with the same `longint` amount are right.
- It only happens when the left operand is a compile-time constant: reading `a` from
  `$value$plusargs` (or any non-constant source) gives 16384 for the same expression, so the
  simulation-time `VL_SHIFTRS` path is fine and the constant folder (V3Const) is what mis-evaluates
  it, apparently treating a 64-bit shift amount as >= the operand width.
- Found through a third-party testbench (`localparam longint LANE_SHIFT = 4;` ...
  `cgsum >>> LANE_SHIFT` where `cgsum` is a propagated constant in some configurations): the
  compare fired while the `$display` of the same expression printed equal values, because the
  display is evaluated at run time.

**Expected:** `a >>> SH_L` = 16384 (IEEE 1800-2017 11.4.10: the shift amount is treated as
unsigned; its width does not change the result).
