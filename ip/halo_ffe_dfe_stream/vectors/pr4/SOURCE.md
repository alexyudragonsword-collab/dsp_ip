# Committed vector set: Halo_Serdes `rtl/vectors/pr4/` (halo_ffe_dfe_stream / pr4)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `6516f1cce0f7da6461b599c7f818b381657b8a64`
(`rtl/vectors/pr4/{codes.txt, w_ffe_int.txt, w_dfe_int.txt, levels_out.txt, dec.txt, v_out.txt, dims.svh, pr_abc.txt, pr_lv.txt}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(Halo_Serdes `main` at PR #148's merge commit; #147 added LOOKAHEAD to the
streaming FFE + DFE, #148 the streaming MLSDs and their edge-case sets; the snapshot itself last changed with #144).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
