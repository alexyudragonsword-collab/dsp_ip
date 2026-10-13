# dsp_ip — bit-true DSP IP library

Every IP in this library ships three things that must agree, and CI proves they do:

1. **Python fixed-point reference** — pure-integer, the truth (`src/dspip/ip/<name>/ref.py`);
2. **SystemVerilog implementation** — synthesizable, every bit width a parameter (`ip/<name>/rtl/`);
3. **Lockstep** — `tools/lockstep.py <name>` compiles the RTL (Verilator or Icarus), streams the
   consumer's vectors through it and compares every output sample with the reference. Zero
   mismatches or red; flipping one golden sample must turn it red (mutation test).

It generalises the method Halo_Serdes proved on its `rtl/` (Python golden → `.txt` vectors →
testbench → bit-exact compare → mutation test). First user: PA_DPD's fixed-point DPD
(`ip/dpd_poly`). Second (milestone 2): Halo's own five modules.

Rules, reading order and the six iron rules: [`AGENTS.md`](AGENTS.md). Open items:
[`ROADMAP.md`](ROADMAP.md). History and numbers: [`cairn/LOG.md`](cairn/LOG.md).
**All measured numbers live in [`docs/results.md`](docs/results.md)** (generated from
`results/*.json` — never typed by hand; `tests/test_docs_numbers.py` enforces it).

## IPs

| IP | what | reference | vector sets | status |
|---|---|---|---|---|
| `sat_shift` | rounding right shift + saturation (the output stage every IP uses) | `dspip.ip.sat_shift.ref` | 3 (signed/unsigned, corner values) | lockstep green, both simulators |
| `dpd_poly` | polynomial DPD datapath: DDR-Volterra r=1 (140 terms) and GMP-510 (255 terms), W16/W12/W10, P samples/clock | `dspip.ip.dpd_poly.ref` | `ddr_r1_w16 gmp510_w16 ddr_r1_w12 gmp510_w12 rand_w16` × P ∈ {1,2,4} | lockstep green, both simulators; ACLR and synthesis estimates in `docs/results.md` |

### dpd_poly in one paragraph

The consumer (PA_DPD @ `08b9725`) exports integer coefficients and an input block
(`ip/dpd_poly/upstream/`, pinned by SHA and sha256). `DpdPolyConfig.derive` turns them into
a frozen configuration — input scale, per-column shifts with upstream's power-of-two rule,
accumulator width, output shift — and emits the `dims*.svh` the RTL is built with
(`cairn/dpd_poly定点通路.md` has the numeric definition). The streaming RTL computes one
envelope and its powers per input sample, keeps one flat history window, instantiates one
`dpd_term` per (lane, basis term) with a real coefficient load port, and sums with a
pipelined tree. PA_DPD's own `FixedPointPolyModel` is a float emulation and cannot be
matched bit for bit (see `docs/upstream-findings.md`), so the integer reference here is the
truth and its distance to the float model is measured: at W16 it reproduces PA_DPD's
documented ACLR within 0.1 dB (`docs/results.md`).

Throughput: see the parallelism table in `docs/results.md` — it is a yosys + NanGate45
**estimate** (method in `docs/synthesis.md`) and states which P reaches the 640 MSPS target.

## Quick start

```sh
tools/toolchain.sh --install            # verilator / iverilog / yosys via apt (Ubuntu)
pip install -e ".[test,upstream]"
python -m pytest -q                     # Python side (lockstep tests skip without a simulator)
python tools/lockstep.py --all          # every IP, every vector set, every P: 0 mismatches
python examples/00_lockstep.py          # same, dpd_poly only, P=1
python examples/01_bitwidth_aclr.py     # bit width × basis → ACLR (needs torch + OpenDPD)
tools/get_liberty.sh && python tools/synth.py --ip dpd_poly --set ddr_r1_w16 --P 1 --terms 14
python examples/02_parallelism_synth.py # P × f_est × area table + "P = ? reaches 640 MSPS"
python tools/vendor_check.py --strict   # needs a PA_DPD checkout next to this repo
```

## Adding an IP

1. `src/dspip/ip/<name>/ref.py` — the integer reference and a `generate(set_name, out_dir)`
   that writes `.txt` vectors (one integer per line) plus the `dims*.svh` the RTL includes;
   optionally `probe(set_dir, sample)` returning the reference's registers at a sample.
2. `ip/<name>/rtl/*.sv` + a testbench that reads `+vecdir` and writes `rtl_*.txt` to `+outdir`
   (or self-checks Halo-style with `check: tb` and a `pass_pattern`).
3. `ip/<name>/ip.yaml` — that is all the scaffold needs (schema in `src/dspip/ipspec.py`).
4. `python tools/lockstep.py <name> --update-lock` pins the vectors; `tests/test_rtl_lockstep.py`
   picks the IP up automatically, mutation test included.
