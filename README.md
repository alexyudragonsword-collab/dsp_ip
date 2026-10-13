# dsp_ip — bit-true DSP IP library

Every IP in this library ships three things that must agree, and CI proves they do:

1. **Python fixed-point reference** — pure-integer, the truth (`src/dspip/ip/<name>/ref.py`);
2. **SystemVerilog implementation** — synthesizable, parameterised bit widths (`ip/<name>/rtl/`);
3. **Lockstep** — `tools/lockstep.py <name>` compiles the RTL, streams the consumer's vectors
   through it and compares every output sample against the reference. Zero mismatches or red.

It generalises the method Halo_Serdes proved on its `rtl/` (Python golden → `.txt` vectors →
iverilog testbench → bit-exact compare → mutation test). First user: PA_DPD's fixed-point DPD
(`ip/dpd_poly`). Second (milestone 2): Halo's own five modules.

Rules, reading order and the six iron rules are in [`AGENTS.md`](AGENTS.md).
Status and open items: [`ROADMAP.md`](ROADMAP.md), [`cairn/LOG.md`](cairn/LOG.md).

## Status

Milestone 1 in progress — phase 0 (skeleton, vendoring, upstream export) done. Tables for
fixed-vs-float ACLR and parallelism-vs-frequency will be generated from `results/*.json`
once phases 1 and 4 land; no numbers are hand-written here.

## Quick start

```sh
tools/toolchain.sh --install        # verilator / iverilog / yosys via apt (Ubuntu)
pip install -e ".[test,upstream]"
pytest -q
python tools/vendor_check.py --strict   # needs a PA_DPD checkout next to this repo
```
