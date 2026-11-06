# Committed vector set: Halo_Serdes `rtl/vectors/cal/` (halo_adc_dsp_loop / cal)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `32d562e0fb2148f7f317cf4815a7ee9aafeb491d`
(`rtl/vectors/cal/{loop_*.txt, loop_dims.svh}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(pinned at Halo_Serdes PR #148's head (stacked on #147, which adds LOOKAHEAD to the streaming FFE + DFE);
re-pinned to the merge commit once merged; the snapshot itself last changed with #144).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
