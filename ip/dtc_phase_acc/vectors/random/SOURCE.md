# Committed vector set: polar_tx export (dtc_phase_acc / random)

Exported unchanged from `alexyudragonsword-collab/polar_tx` @ `70577381f678da34da20fcd083c5052afae1c437`
(head of polar_tx PR #18, which added the datapath and remaining block exports; earlier sets
are byte-identical to their #16 / #17 exports; re-pinned to the merge commit once merged) with

    python -m polartx.export.rtl_vectors phase_acc OUTDIR    # in a polar_tx checkout, pip install -e .

Content: 2048 random 16-bit frequency words (polar_tx emit_phase_acc_rtl's stream, seed 11) through phase_acc_golden.

Files: `acc_dims.svh`, `acc_meta.json`, `finc.txt`, `phase.txt`.

dsp_ip does not regenerate them locally (rule 3: the consumer's export, pinned); the CI
`vendor-drift` job re-exports every polar_tx set at the pinned SHA
(`tools/check_polartx_export.py`) and compares: integer files byte for byte, floats in the
`*_meta.json` to 1e-9 relative; sha256 of every file is in
`../vectors.lock.json`.
