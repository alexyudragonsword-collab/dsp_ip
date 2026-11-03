# Synthesis estimates: what the numbers mean (rule 5)

Area and frequency figures in this repository come from one open flow and are always
labelled **estimate**. They are not vendor numbers, there is no place-and-route, no wire
load and no clock tree. They answer one question honestly: *how many samples per clock (P)
does the datapath need to reach the 640 MSPS target, and roughly how big is it?*

## Flow (`tools/synth.py`, `--mode hier`, what every committed number uses)

```
read_verilog -sv -I <vector set dir> <rtl files>      # the set's dims_params.svh / dims.svh
hierarchy -top dpd_poly -chparam P <P>
proc
setattr -mod -set keep_hierarchy 1 *dpd_env* *dpd_pow* *dpd_term* *dpd_acc*
flatten                                               # helpers (sat_shift) into their parents
synth -top dpd_poly
dfflibmap -liberty <lib>
abc -liberty <lib> -script "strash; &get -n; &fraig -x; &put; scorr; dc2; dretime; strash;
                            &get -n; &dch -f; &nf -D 1000; &put; topo; stime -p"
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
- **Mapping**: the committed numbers use yosys's own liberty flow (`&fraig; scorr; dc2;
  dretime; &dch -f; &nf -D 1000`, i.e. the modern `&nf` mapper with a 1 ns delay target).
  The old area-oriented `map` is kept behind `--legacy-map` for comparison: its delay swung
  by ±40 % with the size of the netlist it was handed (the same DDR RTL mapped to 1783 ps
  flattened and 1278 ps per module; the GMP top module, 167 k gates of adder trees, to
  1969 ps even with `dch` and `map -D`, where `&nf` gives 1441 ps). Treat ±10 % as mapping
  noise: the same module alone and in situ, or two near-identical RTL forms, can differ by
  that much.
- **Which stage sets f_est**: every hier JSON records the worst ABC delay per module
  (`modules`, base name, worst over its parameterizations) and `docs/results.md` prints
  it. *Correction (2026-11-03):* earlier notes here and in ROADMAP/LOG blamed "yosys 0.33's
  ripple-carry `$add`" in the 40-bit accumulation tree. Both halves were wrong: yosys 0.33's
  `synth` maps `$alu` through `_90_lcu`, a Brent-Kung prefix network (an isolated 40-bit add
  has `ltp` 18, not ~80), and the tree (top module) was 1441 ps with ~400 ps of slack while
  `dpd_pow` (1837/1883 ps), `dpd_env` (1789) and `dpd_term` (1734) set the path — the
  multiplier stages. `--mode unit --module <m>` synthesizes one leaf module alone in seconds
  so such a claim can be checked before it is written down.
- **Frequency**: `f_est = 1 / (critical path + t_cq + t_setup)`, the flop terms read from
  the library's `DFF_X1` tables (median entries: 113 ps + 41 ps).
- **Area**: `stat -liberty` total cell area (µm²), flops included.

## Modes: hier (what CI and the committed numbers use), budget, full, unit

**`--mode hier`** is the flow above. **Budget mode** is the older, cheaper approximation
(a flattened subset of terms, area extrapolated) kept for comparison; **full** flattens the
real term count (needs far more memory); **unit** probes one leaf module alone (seconds; its
JSON goes to `results/synth/units/` and never into the tables).

### Budget mode vs full mode

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

`--mode full` synthesizes the real term count flattened and is meant for a machine with
much more memory. **`--mode hier`** is the practical full-count run: the IP's own modules
(`dpd_env`, `dpd_pow`, `dpd_term`, `dpd_acc`) keep their hierarchy (`keep_hierarchy`), the
helper `sat_shift` is flattened into them so no pipeline stage straddles a boundary, and
ABC maps and times each derived module separately (140/255 small `dpd_term` variants
instead of one multi-million-cell netlist). Delay is the maximum over modules; area is the
`stat -liberty` hierarchy total. A hier result is listed next to the budget one in
`docs/results.md` so the extrapolation can be judged.

## P = 1 / 2 / 4: synthesized in CI (`synth-long`)

Every (basis, P) point in `docs/results.md` is a real hier synthesis of that P (the
`synth-long` job: `workflow_dispatch`, a 2 × 3 matrix of runners with a 6 h limit each; the
JSON is printed in the job log and uploaded as an artifact, then committed to
`results/synth/` under its default name and the tables re-rendered). The three P points of a
basis come from the same RTL version. The push-time `synth` job keeps synthesizing the two
P = 1 points as a regression guard. Earlier versions of this table carried P = 2/4 rows
"by construction" (throughput = P × f_est, area ≈ P × area(P=1)) because the development
container could not run long enough; those rows are gone.

## How to read `results/synth/*.json`

Every file has `"kind": "estimate"`, the `method` string, the library name and sha256, the
yosys version and the ABC script, so a number can always be traced to the exact flow that
produced it. `tools/render_tables.py` turns them into `docs/results.md`;
`tests/test_docs_numbers.py` fails if that document is edited by hand or if any document
states a throughput without such a result behind it.
