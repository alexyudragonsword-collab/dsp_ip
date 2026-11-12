# Committed vector set: polar_tx export (polar_dpd_lut / wifi20)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `b007e60477bac68806138db733cbafd0c0761282`
(polar_tx `main`, after #18 added the datapath and remaining block exports and the
calibrator became a step kernel; every set re-exports byte-identically to its #16 / #17 / #18
export) with

    python -m polartx.export.rtl_vectors dpd_lut OUTDIR    # in a polar_tx checkout, pip install -e .

Content: the polar DPD dual LUT of the DPA polar_tx's RTL export ships (10-bit DPA, Rapp 2.5 / 1.1, AM-PM 2 + 3 deg poly, sigma 1 %): ROM images (8-bit address, 12-bit amplitude, 14-bit signed pi-scaled phase), then 8960 reads (every address, then the 8-bit envelope of a WiFi-20 64-QAM burst) and the looked-up codes; the meta carries the float LUT.

Files: `addr.txt`, `amp.txt`, `dpd_amp.memh`, `dpd_dims.svh`, `dpd_meta.json`, `dpd_ph.memh`, `ph.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
