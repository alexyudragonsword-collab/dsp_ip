# Committed vector set: polar_tx export (dp_cal_lms / ble_5pct)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `0e76e3e7e15a7aab33b512daad51784c5a70f228`
(the merge of polar_tx PR #17, which added the export entry points for these sets; first
exported from its head e928557, src/ identical) with

    python -m polartx.export.dp_cal_vectors OUTDIR    # in a polar_tx checkout, pip install -e .

Content: the BLE 5 % gain-error run (the default set; first exported at polar_tx#16, byte-identical here).

Files: `dp_cal_dims.svh`, `dp_cal_err.txt`, `dp_cal_meta.json`, `dp_cal_reg.txt`, `dp_cal_value.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares byte for byte; sha256 of every file is in
`../vectors.lock.json`.
