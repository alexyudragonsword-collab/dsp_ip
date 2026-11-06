# Committed vector set: Halo_Serdes `rtl/vectors/pr/` (halo_ffe_dfe_stream / pr)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `c59c2c834cbb226ef9d009f61270ec48eabd4692`
(`rtl/vectors/pr/{codes.txt, w_ffe_int.txt, w_dfe_int.txt, levels_out.txt, dec.txt, v_out.txt, dims.svh, pr_abc.txt, pr_lv.txt}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(pinned at Halo_Serdes PR #148's head (stacked on #147, which adds LOOKAHEAD to the streaming FFE + DFE);
re-pinned to the merge commit once merged; the snapshot itself last changed with #144).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
