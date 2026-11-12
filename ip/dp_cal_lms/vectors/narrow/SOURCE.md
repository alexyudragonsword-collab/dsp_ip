# Committed vector set: polar_tx export (dp_cal_lms / narrow)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `b007e60477bac68806138db733cbafd0c0761282`
(polar_tx `main`, after #18 added the datapath and remaining block exports and the
calibrator became a step kernel; every set re-exports byte-identically to its #16 / #17 / #18
export) with

    python -m polartx.export.dp_cal_vectors OUTDIR --variant narrow    # in a polar_tx checkout, pip install -e .

Content: 4-bit phase error (LSB 2^-6 UI), 5-bit regressor (LSB 32 kHz), ema 2^-8: other widths and K through the same RTL; tail 0.99857, EVM 3.81 %.

Files: `dp_cal_dims.svh`, `dp_cal_err.txt`, `dp_cal_meta.json`, `dp_cal_reg.txt`, `dp_cal_value.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
