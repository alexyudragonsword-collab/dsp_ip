#!/usr/bin/env python3
"""Lockstep: compile an IP's RTL, stream the consumer's vectors through it, compare every
output sample with the Python reference (rule 4: one scaffold for every IP, driven only by
``ip/<name>/ip.yaml``).

    python tools/lockstep.py dpd_poly                 # all vector sets, all params
    python tools/lockstep.py dpd_poly --set ddr_r1_w16 --param P=2
    python tools/lockstep.py --all --sim iverilog     # every IP (after a scaffold change)
    python tools/lockstep.py dpd_poly --update-lock   # re-pin vectors after a reference change

For each (vector set, parameter point):
  1. regenerate the set from the Python reference (``source: generated``) and verify every
     file against ``vectors/vectors.lock.json`` — or verify a committed set;
  2. compile with verilator (``--binary --timing``) or iverilog (``-g2012``), the set's
     directory on the include path so the tb picks up its ``dims.svh``;
  3. run the tb with ``+vecdir=<set> +outdir=<work>``;
  4. ``check: python``: compare each ``compare`` pair line by line (first mismatch: sample
     index, RTL vs golden value, and the reference's internal registers from ``probe``);
     ``check: tb``: the tb self-checks, look for ``pass_pattern`` and a zero exit code.
Exit status is non-zero if any point fails. A JSON report goes to results/lockstep/.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from dspip import vectors as V  # noqa: E402
from dspip.ipspec import IP_ROOT, IpSpec, all_ips, load_ipspec  # noqa: E402

RESULTS = REPO / "results" / "lockstep"
SIM_PREF = ("verilator", "iverilog")


def detect_sim(pref: str = "auto") -> str | None:
    cands = SIM_PREF if pref == "auto" else (pref,)
    for s in cands:
        if shutil.which(s):
            return s
    return None


# --- vectors ----------------------------------------------------------------------------


def ensure_vectors(spec: IpSpec, set_name: str, *, generate: bool = True,
                   update_lock: bool = False) -> tuple[Path, list[str]]:
    """Generate (if the set is generated) and verify the set against the lock.
    Returns (set_dir, problems)."""
    vs = next(s for s in spec.vector_sets if s.name == set_name)
    set_dir = spec.root / vs.dir
    lock = V.load_lock(spec.lock_path)
    if vs.source == "generated" and generate:
        gen = spec.load_callable(spec.generator)
        if set_dir.exists():
            for p in set_dir.iterdir():
                if p.is_file() and not p.name.startswith("rtl_"):
                    p.unlink()
        gen(set_name, set_dir)
    if not set_dir.exists():
        return set_dir, [f"{set_name}: vector directory {set_dir} missing"]
    if update_lock:
        cmd = f"python tools/lockstep.py {spec.name} --set {set_name} --update-lock"
        if vs.source == "committed":
            cmd = "committed (see ip.yaml / EXPORT.md)"
        lock.setdefault("sets", {})[set_name] = V.lock_entry(set_dir, cmd)
        V.save_lock(spec.lock_path, lock)
        return set_dir, []
    return set_dir, V.verify_set(lock, set_name, set_dir)


# --- build & run ------------------------------------------------------------------------


def build(spec: IpSpec, set_dir: Path, sim: str, params: dict, work: Path) -> tuple[list[str], str]:
    """Compile; returns (run command, compile log)."""
    work.mkdir(parents=True, exist_ok=True)
    srcs = [str(p) for p in spec.rtl_paths()] + [str(spec.tb_path)]
    if sim == "verilator":
        obj = work / "obj"
        cmd = ["verilator", "--binary", "--timing", "-Wno-fatal", "-Wno-WIDTH", "-Wno-UNUSED",
               "-Wno-UNOPTFLAT", "--top-module", spec.tb_module, f"+incdir+{set_dir}",
               "--Mdir", str(obj), "-j", str(min(4, os.cpu_count() or 1))]
        cmd += [f"-G{k}={v}" for k, v in params.items()]
        cmd += srcs
        run = [str(obj / f"V{spec.tb_module}")]
    elif sim == "iverilog":
        vvp = work / "sim.vvp"
        cmd = ["iverilog", "-g2012", "-I", str(set_dir), "-o", str(vvp)]
        cmd += [f"-P{spec.tb_module}.{k}={v}" for k, v in params.items()]
        cmd += srcs
        run = ["vvp", "-n", str(vvp)]
    else:
        raise ValueError(sim)
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = " ".join(cmd) + "\n" + r.stdout + r.stderr
    (work / "compile.log").write_text(log)
    if r.returncode != 0:
        raise RuntimeError(f"{sim} compile failed (see {work / 'compile.log'}):\n" + log[-3000:])
    return run, log


def run_sim(run_cmd: list[str], set_dir: Path, work: Path) -> tuple[int, str]:
    cmd = run_cmd + [f"+vecdir={set_dir}", f"+outdir={work}"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(work))
    out = r.stdout + r.stderr
    (work / "sim.log").write_text(" ".join(cmd) + "\n" + out)
    return r.returncode, out


# --- compare ----------------------------------------------------------------------------


def compare_files(golden: Path, rtl: Path) -> dict:
    """Line-by-line integer comparison. The RTL file may be longer (drain) but never
    shorter than the golden; every golden line must match."""
    g = V.read_ints(golden)
    try:
        r = V.read_ints(rtl)
    except FileNotFoundError:
        return {"n": len(g), "n_rtl": 0, "mismatches": len(g), "first": 0,
                "detail": f"{rtl.name} missing"}
    n = len(g)
    mism = [i for i in range(n) if i >= len(r) or r[i] != g[i]]
    first = mism[0] if mism else None
    d = {"n": n, "n_rtl": len(r), "mismatches": len(mism), "first": first}
    if first is not None:
        d["golden"] = g[first]
        d["rtl"] = r[first] if first < len(r) else None
        d["examples"] = [(i, g[i], r[i] if i < len(r) else None) for i in mism[:8]]
    if len(r) < n:
        d["detail"] = f"RTL wrote {len(r)} < {n} samples"
    return d


def run_point(spec: IpSpec, set_name: str, sim: str, params: dict, *, generate: bool = True,
              update_lock: bool = False, verify_lock: bool = True) -> dict:
    t0 = time.time()
    ptag = "_".join(f"{k}{v}" for k, v in params.items()) or "default"
    work = RESULTS / spec.name / f"{set_name}__{ptag}__{sim}"
    rep = {"ip": spec.name, "set": set_name, "sim": sim, "params": params, "work": str(work),
           "status": "ERROR", "mismatches": None}
    try:
        set_dir, problems = ensure_vectors(spec, set_name, generate=generate,
                                           update_lock=update_lock)
        if problems and verify_lock:
            rep["status"] = "LOCK"
            rep["detail"] = problems
            return rep
        run_cmd, _ = build(spec, set_dir, sim, params, work)
        rc, out = run_sim(run_cmd, set_dir, work)
        rep["sim_rc"] = rc
        rep["sim_tail"] = out[-1500:]
        if spec.check == "tb":
            ok = rc == 0 and spec.pass_pattern in out
            rep["status"] = "PASS" if ok else "FAIL"
            rep["mismatches"] = 0 if ok else None
            if not ok:
                rep["detail"] = f"rc={rc}, pattern {spec.pass_pattern!r} {'found' if spec.pass_pattern in out else 'missing'}"
        else:
            total = 0
            pairs = []
            for cp in spec.compare:
                c = compare_files(set_dir / cp.golden, work / cp.rtl)
                c["golden_file"], c["rtl_file"] = cp.golden, cp.rtl
                pairs.append(c)
                total += c["mismatches"]
            rep["pairs"] = pairs
            rep["mismatches"] = total
            rep["n"] = pairs[0]["n"] if pairs else 0
            if rc != 0:
                rep["status"] = "FAIL"
                rep["detail"] = f"simulator exit code {rc}"
            elif total == 0:
                rep["status"] = "PASS"
            else:
                rep["status"] = "FAIL"
                bad = next(p for p in pairs if p["mismatches"])
                rep["first_mismatch"] = {"sample": bad["first"], "file": bad["golden_file"],
                                         "golden": bad.get("golden"), "rtl": bad.get("rtl")}
                probe = spec.load_callable(spec.probe)
                if probe is not None:
                    try:
                        rep["probe"] = probe(set_dir, bad["first"])
                    except Exception as exc:  # noqa: BLE001
                        rep["probe"] = f"probe failed: {exc!r}"
    except Exception as exc:  # noqa: BLE001
        rep["status"] = "ERROR"
        rep["detail"] = str(exc)
    rep["seconds"] = round(time.time() - t0, 1)
    return rep


def param_points(spec: IpSpec, overrides: dict | None) -> list[dict]:
    params = dict(spec.params)
    if overrides:
        for k, v in overrides.items():
            params[k] = v
    if not params:
        return [{}]
    keys = sorted(params)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(params[k] for k in keys))]


def run_ip(spec: IpSpec, sim: str, sets: list[str] | None = None, overrides: dict | None = None,
           **kw) -> list[dict]:
    reports = []
    for vs in spec.vector_sets:
        if sets and vs.name not in sets:
            continue
        for params in param_points(spec, overrides):
            rep = run_point(spec, vs.name, sim, params, **kw)
            reports.append(rep)
            print(format_report(rep), flush=True)
    return reports


def format_report(rep: dict) -> str:
    p = " ".join(f"{k}={v}" for k, v in rep["params"].items())
    head = f"[{rep['status']:5}] {rep['ip']}/{rep['set']} {p} ({rep['sim']})"
    if rep["status"] == "PASS":
        return f"{head}  n={rep.get('n', '?')} mismatches=0  {rep.get('seconds', '')}s"
    lines = [head + f"  mismatches={rep.get('mismatches')}"]
    if rep.get("detail"):
        lines.append(f"    {rep['detail']}")
    fm = rep.get("first_mismatch")
    if fm:
        lines.append(f"    first mismatch: sample {fm['sample']} in {fm['file']}: "
                     f"rtl={fm['rtl']} golden={fm['golden']}")
    if rep.get("probe"):
        lines.append("    reference registers at that sample:")
        lines += ["      " + ln for ln in str(rep["probe"]).splitlines()]
    if rep["status"] in ("ERROR", "FAIL") and rep.get("sim_tail"):
        lines.append("    sim tail: " + rep["sim_tail"].strip().splitlines()[-1][:200]
                     if rep["sim_tail"].strip() else "")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ip", nargs="?", help="IP name under ip/")
    ap.add_argument("--all", action="store_true", help="run every IP")
    ap.add_argument("--sim", default="auto", choices=["auto", "verilator", "iverilog"])
    ap.add_argument("--set", action="append", dest="sets", help="only this vector set")
    ap.add_argument("--param", action="append", default=[], metavar="K=V[,V]",
                    help="override a tb parameter sweep, e.g. P=2 or P=1,4")
    ap.add_argument("--update-lock", action="store_true",
                    help="re-pin the vector sets' hashes (after a deliberate reference change)")
    ap.add_argument("--json", type=Path, help="write the report here (default results/lockstep/)")
    args = ap.parse_args(argv)
    if not args.ip and not args.all:
        ap.error("give an IP name or --all")

    sim = detect_sim(args.sim)
    if sim is None:
        print("no simulator found (verilator or iverilog); see ROADMAP 被外部阻塞", file=sys.stderr)
        return 2
    overrides = {}
    for p in args.param:
        k, v = p.split("=", 1)
        overrides[k] = [x.strip() for x in v.split(",")]

    specs = all_ips() if args.all else [load_ipspec(IP_ROOT / args.ip)]
    reports = []
    for spec in specs:
        reports += run_ip(spec, sim, args.sets, overrides, update_lock=args.update_lock)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = args.json or RESULTS / ("report_all.json" if args.all else f"report_{specs[0].name}.json")
    out.write_text(json.dumps(reports, indent=1))
    n_fail = sum(r["status"] != "PASS" for r in reports)
    print(f"\n{len(reports) - n_fail}/{len(reports)} points PASS ({sim}); report: {out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
