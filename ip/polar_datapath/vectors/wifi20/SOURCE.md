# Committed vector set: polar_tx export (polar_datapath / wifi20)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `b007e60477bac68806138db733cbafd0c0761282`
(polar_tx `main`, after #18 added the datapath and remaining block exports and the
calibrator became a step kernel; every set re-exports byte-identically to its #16 / #17 / #18
export) with

    python -m polartx.export.rtl_vectors datapath OUTDIR    # in a polar_tx checkout, pip install -e .

Content: a WiFi-20 64-QAM burst (8704 samples: 12-bit envelope, 19-bit frequency words) through datapath_golden: CFR clip -> DPD LUT -> DPA decoder and phase accumulator -> minus AM-PM correction -> EFM1, with the ROM images it reads.

Files: `bin.txt`, `datapath_dims.svh`, `datapath_meta.json`, `dpd_amp.memh`, `dpd_ph.memh`, `dtc_code.txt`, `env.txt`, `finc.txt`, `thermo.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
