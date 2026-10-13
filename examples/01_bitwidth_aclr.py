#!/usr/bin/env python3
"""Example 01 — bit width × basis → ACLR (rule 2: the fixed-point reference answers to float).

Writes ``results/aclr_table.json`` and prints the table that README/docs are generated from:

- ``upstream`` : PA_DPD's own fixed-point emulation, recomputed with its vendored code
                 (must match PA_DPD docs/03_roadmap.md within 0.1 dB);
- ``int ref``  : this library's integer datapath (the RTL's truth), default widths and a
                 variant with a 4-bit wider envelope-power word;
- ``NMSE``     : integer reference vs upstream emulation on the exported 4096-sample block
                 (torch-free; the same number ``pytest`` checks).

Needs torch, the OpenDPD DPA_160MHz dataset and a PA_DPD checkout (DGRU surrogate).
Without them only the NMSE part runs.

    python examples/01_bitwidth_aclr.py [--bits 16 12 10] [--out results/aclr_table.json]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from dspip.ip.dpd_poly import floatref as fr  # noqa: E402
from dspip.ip.dpd_poly.config import DpdPolyConfig  # noqa: E402


def print_table(table: dict) -> None:
    bits = [k for k in table["ddr_r1"]["int_ref"]]
    variants = list(next(iter(table["ddr_r1"]["int_ref"].values())).keys())
    print(f"ACLR_AVG dBc, {table['_meta']['dataset']}, {table['_meta']['metric']}")
    print(f"{'basis':<8}{'model':<22}{'float':>8}" + "".join(f"{'W' + b:>8}" for b in bits))
    for basis in ("ddr_r1", "gmp510"):
        row = table[basis]
        doc = table["_meta"]["upstream_table"][basis]
        print(f"{basis:<8}{'PA_DPD doc':<22}{doc['float']:>8.1f}"
              + "".join(f"{doc[b]:>8.1f}" for b in bits))
        up = row["upstream_recomputed"]
        print(f"{'':<8}{'upstream recomputed':<22}{up['float']:>8.2f}"
              + "".join(f"{up[b]:>8.2f}" for b in bits))
        for v in variants:
            print(f"{'':<8}{'int ref ' + v:<22}{'':>8}"
                  + "".join(f"{row['int_ref'][b][v]:>8.2f}" for b in bits))
        print(f"{'':<8}{'NMSE int vs upstream':<22}{'':>8}"
              + "".join(f"{row['nmse_vs_upstream_db'].get(b, float('nan')):>8.1f}" for b in bits))


def nmse_only() -> None:
    print("torch / dataset / PA_DPD checkout not available: NMSE of the integer reference "
          "against the upstream export only")
    for basis in ("ddr_r1", "gmp510"):
        for w in (16, 12):
            up = fr.load_upstream(basis, w)
            cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis=basis)
            print(f"  {basis} W{w}: NMSE {fr.nmse_db(up.y_upstream, fr.int_ref_output(cfg, up.x)):.1f} dB"
                  f"   [{cfg.summary()}]")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bits", type=int, nargs="+", default=[16, 12, 10])
    ap.add_argument("--out", type=Path, default=REPO / "results" / "aclr_table.json")
    args = ap.parse_args(argv)
    if not fr.surrogate_available():
        nmse_only()
        return 0
    table = fr.build_aclr_table(tuple(args.bits), out=args.out)
    print_table(table)
    print(f"\nwrote {args.out}")
    worst = max(abs(table[b]["upstream_recomputed"][str(k)] - v)
                for b in ("ddr_r1", "gmp510") for k, v in fr.UPSTREAM_TABLE[b].items())
    print(f"max |recomputed - PA_DPD doc| = {worst:.2f} dB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
