# Findings to push back upstream

This library does not change upstream algorithms (AGENTS.md: 不做). What it finds while
implementing them is recorded here with a reproduction, to be raised as issues in the
upstream repositories. Each item stays until upstream has answered.

## PA_DPD @ 08b9725

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

## Halo_Serdes @ 6e79c4a

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
