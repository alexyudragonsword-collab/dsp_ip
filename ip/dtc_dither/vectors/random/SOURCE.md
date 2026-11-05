# Committed vector set: polar_tx export (dtc_dither / random)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `e928557e1d6c77cab891869f7eff3d5d75a7098d`
(head of polar_tx PR #17, which added the export entry points for these sets; re-pinned to the
merge commit once merged) with

    python -m polartx.export.rtl_vectors dtc_random OUTDIR    # in a polar_tx checkout, pip install -e .

Content: 2048 random 19-bit phase words (rng seed 7, the stream polar_tx's own emit_dtc_dither_rtl testbench checks) through efm1_int_golden (11-bit code, 8 fraction bits).

Files: `code.txt`, `dtc_dims.svh`, `dtc_meta.json`, `phase_w.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares byte for byte; sha256 of every file is in
`../vectors.lock.json`.
