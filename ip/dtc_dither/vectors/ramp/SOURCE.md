# Committed vector set: polar_tx export (dtc_dither / ramp)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `b007e60477bac68806138db733cbafd0c0761282`
(polar_tx `main`, after #18 added the datapath and remaining block exports and the
calibrator became a step kernel; every set re-exports byte-identically to its #16 / #17 / #18
export) with

    python -m polartx.export.rtl_vectors dtc_ramp OUTDIR    # in a polar_tx checkout, pip install -e .

Content: 4096 words of a modulo-2^19 phase accumulator with a constant frequency word (0.0123456789 cycles/sample, wraps ~50 times), through efm1_int_golden.

Files: `code.txt`, `dtc_dims.svh`, `dtc_meta.json`, `phase_w.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
