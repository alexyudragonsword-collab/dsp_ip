# Committed vector set: polar_tx export (cfr_clip / mixed)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `b007e60477bac68806138db733cbafd0c0761282`
(polar_tx `main`, after #18 added the datapath and remaining block exports and the
calibrator became a step kernel; every set re-exports byte-identically to its #16 / #17 / #18
export) with

    python -m polartx.export.rtl_vectors cfr_clip OUTDIR    # in a polar_tx checkout, pip install -e .

Content: 9728 12-bit envelope words (polar_tx emit_cfr_clip_rtl's random stream, seed 3, then a WiFi-20 burst's peak-normalized envelope) through cfr_clip_golden at threshold 3071 (0.75 FS), with the clip flag.

Files: `cfr_dims.svh`, `cfr_meta.json`, `clipped.txt`, `env.txt`, `env_clip.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
