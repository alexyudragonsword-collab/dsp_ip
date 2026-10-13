# Synthesis estimates: what the numbers mean (rule 5)

Area and frequency figures in this repository come from one open flow and are always
labelled **estimate**. They are not vendor numbers, there is no place-and-route, no wire
load and no clock tree. They answer one question honestly: *how many samples per clock (P)
does the datapath need to reach the 640 MSPS target, and roughly how big is it?*

## Flow (`tools/synth.py`)

```
read_verilog -sv -I <vector set dir> <rtl files>      # the set's dims_params.svh / dims.svh
hierarchy -top dpd_poly -chparam P <P> [-chparam N_TERMS <T>]
synth -top dpd_poly -flatten
dfflibmap -liberty <lib>
abc -liberty <lib> -script "strash; map; topo; stime -p"   # --dch adds dch -f before map
opt_clean
stat -liberty <lib>
```

- **Tools**: yosys 0.33 (Ubuntu 24.04 apt) with its bundled ABC.
- **Library**: NanGate45 (FreePDK45) typical corner, `NangateOpenCellLibrary_typical.lib`
  from OpenROAD-flow-scripts @ `e5cc6e7`, sha256 `8d540a4d…` (fetched by
  `tools/get_liberty.sh`, pinned and verified). sky130_fd_sc_hd is wired as an alternative
  (`--lib sky130`) but every committed number is NanGate45.
- **Critical path**: ABC `stime` after liberty mapping — the longest combinational path
  between registers with the library's cell delays, **no wire load**.
- **Frequency**: `f_est = 1 / (critical path + t_cq + t_setup)`, the flop terms read from
  the library's `DFF_X1` tables (median entries: 113 ps + 41 ps).
- **Area**: `stat -liberty` total cell area (µm²), flops included.

## Budget mode (what CI runs) vs full mode

The full GMP datapath at P = 1 is ~1000 real multipliers; ABC on millions of cells takes
hours and gigabytes, more than a CI job should spend. Budget mode therefore synthesizes
the *same top module* with the term count reduced (`-chparam N_TERMS T` and `2T`, keeping
the real tables, widths and pipeline) and:

- takes **f_est from the worse of the two points** — the critical path lives inside one
  pipeline stage (a W×W multiplier, two adder levels of the tree, one sqrt step, the
  rounding/saturation of the output) and does not grow with the term count; what budget
  mode under-estimates is fan-out from the shared history window, which has no wire load
  here anyway;
- **extrapolates area linearly** from the two points to the full term count
  (`area_per_term_um2` is recorded), which is accurate for a datapath that is literally
  N copies of one term plus a tree.

**Memory budget.** ABC's `map` on the mapped netlist is the memory hog: the P = 4 points with
28/32 terms (112/128 term instances, ~1.7 M cells before mapping) were OOM-killed at ~9 GB
on a 15 GB machine, so the committed P = 4 points use 7/14 (DDR) and 8/16 (GMP) terms. Keep
a budget point under ~60 term instances unless the machine has more memory.

`--mode full` synthesizes the real term count and is meant for a manual or nightly run;
when a full result exists it is listed next to the budget one in `docs/results.md` so the
extrapolation can be judged.

## How to read `results/synth/*.json`

Every file has `"kind": "estimate"`, the `method` string, the library name and sha256, the
yosys version and the ABC script, so a number can always be traced to the exact flow that
produced it. `tools/render_tables.py` turns them into `docs/results.md`;
`tests/test_docs_numbers.py` fails if that document is edited by hand or if any document
states a throughput without such a result behind it.
