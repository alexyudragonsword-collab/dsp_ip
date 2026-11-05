# Committed vector set: polar_tx `dp_cal_vectors` (dp_cal_lms / ble_5pct)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `f43cd4f5ff941583efd974c14c1a3c55e9707e1a`
(the merge of polar_tx PR #16, which added the fixed-point calibrator and this exporter; the tree
equals the PR head 3577685 the set was first exported from, and the re-export is byte-identical) with

    python -m polartx.export.dp_cal_vectors OUTDIR    # in a polar_tx checkout, pip install -e .

The scenario is polar_tx's `tests/test_dp_cal_online.py`: BLE LE-1M, ADPLL two-point event engine,
5 % direct-path gain error (`dp_gain=1.05`), 2000 bits, waveform seed 5, noise seed 3, with
`FixedSignSignLMS` (default `DpCalFixedConfig`) in the loop. One line per reference cycle (104 004):

- `dp_cal_err.txt` — quantized phase error code (E_BITS signed, LSB 2^-12 UI), the RTL input
- `dp_cal_reg.txt` — quantized regressor code (R_BITS signed, LSB 500 Hz), the RTL input
- `dp_cal_value.txt` — value-register code after the step (V_BITS unsigned, LSB 2^-16), the golden output
- `dp_cal_dims.svh` — widths, `V_START` (the code the run starts from) and `N_VEC`
- `dp_cal_meta.json` — scenario, configuration, measured tail mean 0.99842 and EVM 3.178 % of that run

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports at the pinned SHA and compares byte for byte; sha256 of every
file is in `../vectors.lock.json`.
