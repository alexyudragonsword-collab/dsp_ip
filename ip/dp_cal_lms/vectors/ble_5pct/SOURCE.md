# Committed vector set: polar_tx export (dp_cal_lms / ble_5pct)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `e10bc383877e48aad0b81ba7362a5e7d44796e3a`
(head of polar_tx PR #18, which added the datapath and remaining block exports; earlier sets
are byte-identical to their #16 / #17 exports; re-pinned to the merge commit once merged) with

    python -m polartx.export.dp_cal_vectors OUTDIR    # in a polar_tx checkout, pip install -e .

Content: the BLE 5 % gain-error run (the default set; first exported at polar_tx#16, byte-identical since).

Files: `dp_cal_dims.svh`, `dp_cal_err.txt`, `dp_cal_meta.json`, `dp_cal_reg.txt`, `dp_cal_value.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares byte for byte; sha256 of every file is in
`../vectors.lock.json`.
