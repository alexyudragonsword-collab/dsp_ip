# Findings to push back upstream

This library does not change upstream algorithms (AGENTS.md: 不做). What it finds while
implementing them is recorded here with a reproduction, to be raised as issues in the
upstream repositories. Each item stays until upstream has answered.

## PA_DPD @ 08b9725 — filed as alexyudragonsword-collab/PA_DPD#2 (2026-11-02)

**Fixed upstream by PA_DPD#3, merged 2026-11-04 as `5718b83`; dsp_ip is pinned there.**
The export now carries the input / per-column exponents (`fixed_point` in the JSON) and the
integer input codes (two CSV columns appended), the docstrings say "float emulation,
output not quantized", and both doc nits are fixed. The algorithm and the ACLR numbers did
not change. dsp_ip's `DpdPolyConfig.derive` reproduces every exported exponent
(`tests/test_config.py`). Points 1–2 below remain true of the *model* (it is still a float
emulation, still block-adaptive); they are now documented upstream instead of hidden.

### 1. `FixedPointPolyModel` is a float emulation, not an integer datapath

`src/padpd/deploy/fixed_point.py` — the "bit-true" model that `scripts/export_deploy.py`
uses for `*_refvec.csv`:

- **Scales are data-dependent and not exported.** `quantize_symmetric` picks the input step
  from the peak of the block passed to *that call*, and every basis column likewise
  (`_pow2_step(col_peak, W)`). Hardware cannot look at the whole block before quantizing
  the first sample, and none of these exponents reach the JSON/CSV hand-off, so an RTL
  implementer has to re-derive them (this library does, from the same calibration block,
  and documents the rule in `src/dspip/ip/dpd_poly/config.py`).
- **`|x|^k` is computed in float64.** With W = 16 the exact product `x·|x|^4` has ~80
  significant bits; float64 keeps 53, so the "bit-true" reference is itself rounded in a
  way no integer datapath reproduces. Reproduce: `python examples/01_bitwidth_aclr.py`
  reports the integer reference vs this model at −59.6 dB (DDR) / −69.6 dB (GMP) NMSE at
  W16 — both well below the ACLR floor, but not zero, and not reducible to zero.
- **The accumulator is a float64 matmul and the output is not quantized** (the class
  docstring says the output is quantized per call; the code does not do it), so no output
  word width or scale is defined.
- **`refvec.csv` is float** (`%.10e`), so it cannot be compared sample-for-sample with an
  integer implementation: this library quantizes `i_in/q_in` itself and generates its own
  integer golden from its reference.

Suggested upstream change: export `e_in`, the per-column exponents and an output format in
the coefficient JSON; write integer codes in the reference CSV; compute the basis in
integer (or at least document that the float path is an approximation). This library's
`DpdPolyConfig.derive` is a candidate implementation.

### 2. Block-adaptive per-column scaling is non-causal

Because every scale comes from the block peak, the same coefficients give different
`e_c` on `refvec` (4096 samples) than on the ACLR evaluation block (`concat(val.x[-200:],
test.x)`, 98 504 samples). The ACLR table in `docs/03_roadmap.md` is therefore measured
with scales a real-time DPD could not know. The effect is small on this data (peaks ≈ 1
in both blocks, same `e_in`), but it should be stated.

### 3. Documentation nits

- `ddr_volterra_default()` docstring says "~155 complex coefficients"; the model has 140.
- `scripts/export_deploy.py` docstring pairs the `DPA_200MHz_tcn` checkpoint with the
  `DPA_160MHz` dataset.

## Halo_Serdes @ 6e79c4a — filed as alexyudragonsword-collab/Halo_Serdes#136 (2026-11-02)

**Fixed upstream by Halo_Serdes#142, merged 2026-11-04 as `aca6123`** (dsp_ip was pinned
there; since 2026-11-06 it is pinned at Halo_Serdes#145's head `56b92c2`, which adds the
streaming FFE + DFE + slicer, and the vectors are Halo's snapshot as of #144). Every testbench `$fatal`s on a missing file or short read; `rtl/vectors/` carries
`dfse_*` and was refreshed (it had gone stale on Halo's `main` too: 54 files differed from a
regeneration at 82ee2c4); `run_lockstep.sh` builds in a temp dir; shift amounts are
`localparam int`, so `halo_adc_dsp_loop` passes on Verilator 5.020 and its `sims:`
restriction is gone. The Icarus O(N²) note below is an observation, not a Halo bug.

- `rtl/tb_*.sv` never check the return value of `$fscanf`; a truncated vector file reads
  as zeros and the lockstep still passes or fails for the wrong reason. (dsp_ip's
  testbenches `$fatal` on a short read.)
- The committed `rtl/vectors/` has no `dfse_*` files although `gen_vectors.py` and
  `tb_dfse_mlsd.sv` expect them; nothing reads the committed copies, so this is a stale
  snapshot, but it will confuse milestone 2 (`source: committed`).
- `rtl/run_lockstep.sh` writes into the tracked `rtl/vectors` by default and `.gitignore`
  does not exclude it, so running it locally dirties the tree.
- Icarus-specific: an unpacked array or a wide packed bus with many part-select drivers
  is re-resolved on every driver change (O(N²) events per cycle). dsp_ip hit this at 140
  terms (0.9 s/sample → 0.002 s/sample after moving to one wire per node); Halo's
  whole-vector behavioural models are not affected, but a streaming rewrite would be.

## Verilator 5.020 (Debian/Ubuntu apt) — `longint >>> <longint localparam>` folds to 0

Found on 2026-11-03 while bringing Halo's `tb_adc_dsp_loop.sv` into the scaffold: four of the
five vector sets failed under Verilator with `LOOP LOCKSTEP FAIL errors=1` although the
printed values were equal (`offset 0/0 gain 16384/16384`); Icarus 12 passed all five.
Bisected by rewriting the compare (parenthesised, `!=`, split, temp variable, literal
constants): the only change that passes replaces the *shift amount* `LANE_SHIFT`
(`localparam longint`) with a literal. Standalone reproducer
`tools/quirks/verilator_longint_shift.sv` (run by `tests/test_sim_quirks.py`):

| expression (`a = 16 <<< 14`, `longint`) | Verilator 5.020 | Icarus 12 | expected |
|---|---|---|---|
| `a >>> SH_longint` (`localparam longint SH = 4`) | **0** | 16384 | 16384 |
| `a >>> SH_int` (`localparam int`) | 16384 | 16384 | 16384 |
| `a >> SH_longint` (logical) | 16384 | 16384 | 16384 |
| `a >>> 4` | 16384 | 16384 | 16384 |
| `a >>> SH_longint` with `a` from `$value$plusargs` (not constant) | 16384 | 16384 | 16384 |

So it is the constant folder: an arithmetic right shift whose amount is a 64-bit constant
is folded as if the amount were ≥ the operand width. In Halo's tb the affected term is
`dut.cgsum >>> LANE_SHIFT` in the final-calibration check; with `CAL_ON = 0` the DUT never
changes `cgsum`, Verilator propagates it as a constant, and the folded 0 makes the compare
fire (the `$display` evaluates the same expression at run time and prints the right value).
The `cal` set (`CAL_ON = 1`) keeps `cgsum` live and passes. The DUT itself uses the same
construct in its datapath (`ctsum >>> LANE_SHIFT`, `cgsum >>> LANE_SHIFT`), so any Halo
module compiled with Verilator at a configuration where such a sum is constant is at risk.

dsp_ip's handling: `ip/halo_adc_dsp_loop/ip.yaml` carries `sims: [iverilog]` with a
`sims_reason`; `tools/lockstep.py` prints `[SKIP ]` for the excluded simulator,
`tests/test_rtl_lockstep.py` skips those points (and insists the other simulator is
installed), and `tests/test_sim_quirks.py` fails the day Verilator returns 16384 so the
restriction gets lifted. The vendored tb is not edited (rule 3). Halo only runs Icarus,
so nothing is broken upstream today; the note is on Halo_Serdes#136 because a
`localparam int` for shift amounts in `*_dims.svh` would sidestep it for Verilator users.

Upstream status (2026-11-04): **already fixed in Verilator.** The 5.053 development build
shipped in OSS CAD Suite 2026-10-25 (the bundle dsp_ip now pins for yosys) prints 16384 for
all four probe expressions, so no issue was filed (the draft was dropped). The Debian/Ubuntu
apt package is still 5.020. Since 2026-11-05 the lockstep CI job runs both toolchains
(`toolchain: [distro, bundle]`, the bundle via `DSPIP_SIM_BIN`), and `tests/test_sim_quirks.py`
asserts the known behaviour per version (5.020: folds to 0; 5.053: 16384) instead of failing
when the bug goes away.
Halo_Serdes's fix for #136 (shift amounts emitted as `localparam int`) sidesteps it for
every Verilator version.
