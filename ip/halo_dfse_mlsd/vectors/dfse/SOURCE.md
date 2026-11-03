# Committed vector set: Halo_Serdes DFSE (reduced-state Viterbi) segment

Halo_Serdes does **not** commit this set (its `rtl/vectors/` lacks `dfse_*`; raised as
Halo_Serdes#136). It was generated once by dsp_ip at the pin with Halo's own generator:

    git clone https://github.com/alexyudragonsword-collab/Halo_Serdes && git -C Halo_Serdes checkout 6e79c4a7e32b930a023aca6ee302ac3187eb9022
    pip install numpy scipy scikit-rf pyyaml matplotlib
    cd Halo_Serdes && PYTHONPATH=src HALO_NO_JIT=1 python3 rtl/gen_vectors.py <out>
    cp <out>/dfse_{y,acc,fbt,dec}.txt <out>/dfse_dims.svh ip/halo_dfse_mlsd/vectors/dfse/

Halo's generator writes every segment; the other segments it produced were compared with
Halo's committed `rtl/vectors/` (see cairn/LOG.md 2026-11-03). sha256 of every file is in
`../vectors.lock.json`.
