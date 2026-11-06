# Committed vector set: Halo_Serdes `rtl/vectors/dfse_k2/` (halo_dfse_stream / dfse_k2)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `c59c2c834cbb226ef9d009f61270ec48eabd4692`
(`rtl/vectors/dfse_k2/`, the files listed in `../vectors.lock.json`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(pinned at Halo_Serdes PR #148's head, which adds the streaming MLSDs and their edge-case
sets; re-pinned to the merge commit once merged).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
