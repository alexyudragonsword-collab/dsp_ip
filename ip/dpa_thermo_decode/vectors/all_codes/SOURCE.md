# Committed vector set: polar_tx export (dpa_thermo_decode / all_codes)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `b007e60477bac68806138db733cbafd0c0761282`
(polar_tx `main`, after #18 added the datapath and remaining block exports and the
calibrator became a step kernel; every set re-exports byte-identically to its #16 / #17 / #18
export) with

    python -m polartx.export.rtl_vectors thermo OUTDIR    # in a polar_tx checkout, pip install -e .

Content: every code of the 10-bit DPA with 7 thermometer MSBs (127 unary segments) and 3 binary LSBs, through thermo_decode_golden.

Files: `bin.txt`, `code.txt`, `thermo.txt`, `thermo_dims.svh`, `thermo_meta.json`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
