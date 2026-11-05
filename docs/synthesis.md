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
abc -liberty <lib> -script "strash; &get -n; &fraig -x; &put; scorr; dc2; strash; &get -n;
                            &st; &if -g -K 6; &st; &if -g -K 6; &st; &dch -f; &nf -D 1000;
                            &put; topo; stime -p"                  # --abc sopb (default)
opt_clean
stat -liberty <lib>
```

- **Tools**: **pinned** yosys + its bundled ABC from OSS CAD Suite `2026-10-25`
  (`Yosys 0.70+219 (git sha1 5053d0e26)`), fetched by `tools/get_yosys.sh` (tarball sha256
  checked) and used by `tools/synth.py` before anything on PATH, locally and in CI. Every
  JSON records the version string and `yosys_pin`; `tests/test_synth_tool.py` refuses a
  committed estimate from any other build. Why: the runner's apt yosys moved 0.33 → 0.52
  between two runs and the same RTL mapped ~9 % slower. With the pin, the same point gives
  the same critical path on a laptop and on the runner (6/6 points), and the same area and
  cell count on 5 of 6 (GMP P = 1 differs by 0.024 % in area, run-to-run stable on each
  machine). Same-RTL points from 0.33 stay in `results/synth/yosys033/` for comparison.
  yosys 0.70 also changed two report formats the tool reads: the `stat` table (counts ≥ 1e7
  in E-notation, so totals come from `stat -json` now) and the order of per-module ABC
  output (all extractions first, then the ABC runs in the same order).
- **Library**: NanGate45 (FreePDK45) typical corner, `NangateOpenCellLibrary_typical.lib`
  from OpenROAD-flow-scripts @ `e5cc6e7`, sha256 `8d540a4d…` (fetched by
  `tools/get_liberty.sh`, pinned and verified). sky130_fd_sc_hd is wired as an alternative
  (`--lib sky130`) but every committed number is NanGate45.
- **Critical path**: ABC `stime` after liberty mapping — the longest combinational path
  between registers with the library's cell delays, **no wire load**.
- **ABC script `sopb`** (`--abc`, the default since 2026-11-05): yosys's liberty flow below
  plus two rounds of SOP balancing (`&if -g -K 6`) between the area rewriting and the
  mapping. Why: `dc2` (AIG rewriting for node count) folds yosys's Brent-Kung `$lcu` into a
  near-ripple carry chain, ~37 ps/bit. In isolation (registered in/out, NanGate45), a 40-bit
  add mapped to 1481 ps, a 24-bit one to 959 and a 16 × 16 multiply to 1668. Balancing
  restores the log-depth structure before `&dch`/`&nf` map it: 506, 423 and 1069 ps. On the
  whole design at P = 1:

  | set | `nf` critical path | `sopb` critical path | f_est | area | cells |
  |---|---|---|---|---|---|
  | ddr_r1_w16 | 1720 ps | **1313 ps** | 534 → **682 MHz** | 1.947 → 2.035 mm² (+4.5 %) | +6.7 % |
  | gmp510_w16 | 1693 ps | **1174 ps** | 541 → **753 MHz** | 3.441 → 3.596 mm² (+4.5 %) | +6.7 % |

  So **P = 1 reaches 640 MSPS** with the RTL unchanged (estimate). The plan to split every
  multiplier and adder into two cycles was not needed. One balancing round gave about
  three quarters of the gain on the blocks (40-bit add 1112 ps, 16 × 16 multiply 1412); a
  third round added little (517 / 1040). Every number the `nf` script produced is kept in
  `results/synth/abc_nf/` for comparison and is not rendered. The test requires one ABC
  script across `results/synth/*.json`.
- **Mapping**: the `nf` script (the default until 2026-11-05) is yosys's own liberty flow (`&fraig; scorr; dc2;
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
- **Coarse arithmetic flow** (`--flow`, 2026-11-05): `default` is plain `synth`, and every
  committed number uses it (the test requires one flow). The alternatives are 0.70's
  `synth -booth` (radix-4 Booth multipliers) and `-arith_tree` (carry-save trees of adder
  chains / `$macc`); the `*_prefix` variants run synth's coarse stage by hand with
  `arith_tree -final prefix`. Tried on the P = 1 critical stages as unit probes, with
  the `nf` ABC script (`results/synth/units/flows/`, NanGate45, ps / µm²):

  | module | default | booth | arith | arith_prefix | booth_arith | booth_arith_prefix |
  |---|---|---|---|---|---|---|
  | `dpd_term` (K1=1, Q_PAIR=15, SH=14) | 1652 / 14165 | 2086 / 11109 | 1652 / 14165 | 1652 / 14165 | 2086 / 11109 | 2086 / 11109 |
  | `dpd_term` (defaults) | 1604 / 12820 | 2126 / 9925 | 1604 / 12820 | 1604 / 12820 | 2126 / 9925 | 2126 / 9925 |
  | `dpd_pow` (Q2=15, Q3=31, Q4=46) | 1693 / 9911 | 1870 / 9353 | 1693 / 9976 | 1719 / 9981 | 1898 / 9399 | 1960 / 9423 |
  | `dpd_env` | 1580 / 7255 | 1675 / 6721 | 1580 / 7255 | 1580 / 7255 | 1675 / 6721 | 1675 / 6721 |

  None helps the critical path: Booth trades 6–23 % area for 95–520 ps more delay;
  `arith_tree` finds no adder chain to compress (each stage is one `$mul` plus one add,
  and `$mul` is left alone), and forcing a prefix final adder is equal or slower. A yosys
  prefix adder does not survive ABC's `dc2` anyway, which is what the `sopb` script fixes.
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
container could not run long enough; those rows are gone. The measured points confirmed the
assumption: area grows linearly in P within a few percent and the critical path does not
depend on P (the stages are the same; only mapping noise moves it). On the runner a hier
point takes 6–24 min, not hours: identically parameterized modules are mapped once.
With the `sopb` script (CI run 41971912703 on `8121937`, 4–8 min per point), CI reproduced both
local P = 1 points exactly (delay, area, cell count). Every point is ≤ 1313 ps, so P = 1
already reaches 640 MSPS. One oddity is recorded: GMP's `dpd_term` maps to 1313 ps at P = 2 / 4
but 1167 ps at P = 1, with the same five parameterizations — exactly DDR's 1312.79 ps. This is
mapping noise within the ±10 % noted above, and it moves GMP's f_est from 753 to 682 MHz at
P > 1.

**Tool version and script matter.** The same RTL at P = 1 maps to a longer critical path
with newer yosys and the `nf` script: DDR 1554 ps (0.33) → 1696 (0.52) → 1720 (0.70, pinned);
GMP 1554 → 1697 → 1693 (`results/synth/yosys033/`, `cairn/LOG.md`). Area moves by under 2 %.
The pinned 0.70 with the `sopb` script then gives 1313 / 1174 ps (`results/synth/abc_nf/` holds
the `nf` points). Compare rows only within one version and one script — which is why both
are pinned.

## How to read `results/synth/*.json`

Every file has `"kind": "estimate"`, the `method` string, the library name and sha256, the
yosys version and the ABC script, so a number can always be traced to the exact flow that
produced it. `tools/render_tables.py` turns them into `docs/results.md`;
`tests/test_docs_numbers.py` fails if that document is edited by hand or if any document
states a throughput without such a result behind it.
