# Committed vector set: Halo_Serdes `rtl/vectors/pr4/` (halo_adc_dsp_loop / pr4)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `19d104f3eef921cd7cfa623232fd1015812bc518`
(`rtl/vectors/pr4/{loop_*.txt, loop_dims.svh}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(the snapshot was refreshed, and the `dfse_*` files added, by Halo_Serdes PR #142, which
closed #136). dsp_ip does not regenerate them (rule 3: the consumer's export, pinned);
sha256 of every file is in `../vectors.lock.json`.
