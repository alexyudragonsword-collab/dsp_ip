# Committed vector set: Halo_Serdes `rtl/vectors/` (halo_viterbi_mlsd / vit)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `aca61232855e6458109242f984a82d1d3610a806`
(`rtl/vectors/{vit_*.txt, vit_dims.svh}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(the snapshot was refreshed, and the `dfse_*` files added, by Halo_Serdes PR #142, which
closed #136). dsp_ip does not regenerate them (rule 3: the consumer's export, pinned);
sha256 of every file is in `../vectors.lock.json`.
