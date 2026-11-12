# Committed vector set: Halo_Serdes `rtl/vectors/mlsd_tie/` (halo_sliding_stream / mlsd_tie)

Copied unchanged from `alexyudragonsword-collab/Halo_Serdes` @ `6516f1cce0f7da6461b599c7f818b381657b8a64`
(`rtl/vectors/mlsd_tie/`, the files listed in `../vectors.lock.json`), Halo's committed snapshot of

    PYTHONPATH=src HALO_NO_JIT=1 python rtl/gen_vectors.py rtl/vectors   # in a Halo checkout

(Halo_Serdes `main` at PR #148's merge commit; #147 added LOOKAHEAD to the
streaming FFE + DFE, #148 the streaming MLSDs and their edge-case sets).
dsp_ip does not regenerate them (rule 3: the consumer's export, pinned); sha256 of every
file is in `../vectors.lock.json`.
