# Committed vector set: Halo_Serdes `rtl/vectors/` (halo_viterbi_mlsd / vit)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `acf622010d706303eaf7c9ef9b69287e0aec5f6d`
(`rtl/vectors/{vit_*.txt, vit_dims.svh}`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(pinned at Halo_Serdes PR #145's head, which adds the streaming FFE + DFE + slicer;
re-pinned to the merge commit once merged; the snapshot itself last changed with #144).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
