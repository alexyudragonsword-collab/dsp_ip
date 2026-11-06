# Committed vector set: polar_tx export (dp_cal_lms / sat_top)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `70577381f678da34da20fcd083c5052afae1c437`
(head of polar_tx PR #18, which added the datapath and remaining block exports; earlier sets
are byte-identical to their #16 / #17 exports; re-pinned to the merge commit once merged) with

    python -m polartx.export.dp_cal_vectors OUTDIR --variant sat_top    # in a polar_tx checkout, pip install -e .

Content: a 16-bit value register (largest gain 0.99998): the 1.05 start saturates and the register sits on V_MAX for 39 % of the cycles; tail 0.99778, EVM 2.67 %.

Files: `dp_cal_dims.svh`, `dp_cal_err.txt`, `dp_cal_meta.json`, `dp_cal_reg.txt`, `dp_cal_value.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
