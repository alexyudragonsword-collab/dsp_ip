# Committed vector set: Halo_Serdes `rtl/vectors/pr/` (halo_adc_dsp_loop / pr)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `56b92c2692e336ab5427d184d5ccf4ecd1342b87`
(`rtl/vectors/pr/{loop_*.txt, loop_dims.svh}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(pinned at Halo_Serdes PR #145's head, which adds the streaming FFE + DFE + slicer;
re-pinned to the merge commit once merged; the snapshot itself last changed with #144).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
