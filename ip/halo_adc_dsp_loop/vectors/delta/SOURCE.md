# Committed vector set: Halo_Serdes `rtl/vectors/` (halo_adc_dsp_loop / delta)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `5366b7534d921d4cfb2624de0fa1b3f099879818`
(`rtl/vectors/{loop_*.txt, loop_dims.svh}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(pinned at Halo_Serdes PR #147's head, which adds LOOKAHEAD to the streaming FFE + DFE;
re-pinned to the merge commit once merged; the snapshot itself last changed with #144).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
