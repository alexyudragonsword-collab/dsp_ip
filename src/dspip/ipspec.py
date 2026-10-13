"""``ip.yaml`` — the one file an IP provides to the lockstep scaffold (rule 4).

Schema (all paths relative to the IP directory ``ip/<name>/``)::

    name: dpd_poly
    top: dpd_poly                     # DUT module (synthesis top)
    rtl: [rtl/dpd_env.sv, ...]        # DUT sources, in compile order
    tb: rtl/tb_dpd_poly.sv            # testbench module name = file stem
    check: python | tb                # python: the scaffold compares the tb's dump files
                                      # tb: the tb self-checks and prints pass_pattern (Halo style)
    pass_pattern: "LOCKSTEP PASS"     # check: tb only
    params: {P: [1, 2, 4]}            # tb parameters to sweep (overridden on the command line)
    generator: pkg.module:function    # generate(set_name, out_dir) -> None  (source: generated)
    probe: pkg.module:function        # probe(set_dir, sample) -> str  (registers at a mismatch)
    vector_sets:
      - {name: ddr_r1_w16, source: generated}
      - {name: halo_ffe, source: committed, dir: vectors/halo_ffe}
    compare:                          # check: python — golden file vs file the tb writes
      - {golden: y_re.txt, rtl: rtl_y_re.txt}
    rtl_latency_note: "..."           # free text, informational

Vector sets live in ``vectors/<name>/`` (generated ones are git-ignored; every set is pinned
by sha256 in ``vectors/vectors.lock.json``). Each set directory holds its own ``dims.svh``,
which the simulator picks up through ``+incdir``/``-I`` — Halo's convention.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
IP_ROOT = REPO / "ip"


@dataclass(frozen=True)
class VectorSet:
    name: str
    source: str  # generated | committed
    dir: str


@dataclass(frozen=True)
class ComparePair:
    golden: str
    rtl: str


@dataclass(frozen=True)
class IpSpec:
    name: str
    root: Path
    top: str
    rtl: tuple[str, ...]
    tb: str
    check: str
    pass_pattern: str | None
    params: dict
    generator: str | None
    probe: str | None
    vector_sets: tuple[VectorSet, ...]
    compare: tuple[ComparePair, ...]
    extra: dict = field(default_factory=dict)

    @property
    def tb_module(self) -> str:
        return Path(self.tb).stem

    @property
    def vectors_root(self) -> Path:
        return self.root / "vectors"

    @property
    def lock_path(self) -> Path:
        return self.vectors_root / "vectors.lock.json"

    def set_dir(self, name: str) -> Path:
        for s in self.vector_sets:
            if s.name == name:
                return self.root / s.dir
        raise KeyError(f"{self.name}: no vector set {name!r}")

    def rtl_paths(self) -> list[Path]:
        return [self.root / r for r in self.rtl]

    @property
    def tb_path(self) -> Path:
        return self.root / self.tb

    def load_callable(self, spec: str | None):
        if not spec:
            return None
        mod, fn = spec.split(":")
        return getattr(importlib.import_module(mod), fn)


REQUIRED = ("name", "top", "rtl", "tb", "check", "vector_sets")


def load_ipspec(path: Path | str) -> IpSpec:
    path = Path(path)
    if path.is_dir():
        path = path / "ip.yaml"
    raw = yaml.safe_load(path.read_text())
    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing required keys {missing}")
    if raw["check"] not in ("python", "tb"):
        raise ValueError(f"{path}: check must be 'python' or 'tb'")
    if raw["check"] == "tb" and not raw.get("pass_pattern"):
        raise ValueError(f"{path}: check: tb needs pass_pattern")
    if raw["check"] == "python" and not raw.get("compare"):
        raise ValueError(f"{path}: check: python needs compare pairs")
    sets = []
    for s in raw["vector_sets"]:
        if s.get("source", "generated") not in ("generated", "committed"):
            raise ValueError(f"{path}: vector set {s.get('name')}: bad source")
        sets.append(VectorSet(s["name"], s.get("source", "generated"),
                              s.get("dir", f"vectors/{s['name']}")))
    if any(s.source == "generated" for s in sets) and not raw.get("generator"):
        raise ValueError(f"{path}: generated vector sets need a generator")
    known = set(REQUIRED) | {"pass_pattern", "params", "generator", "probe", "compare"}
    extra = {k: v for k, v in raw.items() if k not in known}
    return IpSpec(
        name=raw["name"], root=path.parent, top=raw["top"], rtl=tuple(raw["rtl"]), tb=raw["tb"],
        check=raw["check"], pass_pattern=raw.get("pass_pattern"),
        params={k: list(v) for k, v in (raw.get("params") or {}).items()},
        generator=raw.get("generator"), probe=raw.get("probe"), vector_sets=tuple(sets),
        compare=tuple(ComparePair(c["golden"], c["rtl"]) for c in raw.get("compare") or []),
        extra=extra)


def all_ips(root: Path = IP_ROOT) -> list[IpSpec]:
    """Every IP under ``ip/`` that carries an ip.yaml (what ``lockstep --all`` runs)."""
    return [load_ipspec(p) for p in sorted(root.glob("*/ip.yaml"))]
