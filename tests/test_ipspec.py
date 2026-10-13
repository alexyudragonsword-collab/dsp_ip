"""ip.yaml schema (rule 4): every IP is described by one file, and the loader rejects
incomplete or inconsistent descriptions."""

import textwrap

import pytest

from dspip.ipspec import IP_ROOT, all_ips, load_ipspec


def _write(tmp_path, body):
    p = tmp_path / "ip.yaml"
    p.write_text(textwrap.dedent(body))
    return p


GOOD = """
    name: x
    top: x
    rtl: [rtl/x.sv]
    tb: rtl/tb_x.sv
    check: python
    generator: dspip.ip.sat_shift.ref:generate
    vector_sets:
      - {name: a, source: generated}
    compare:
      - {golden: y.txt, rtl: rtl_y.txt}
"""


def test_loads_good_spec(tmp_path):
    s = load_ipspec(_write(tmp_path, GOOD))
    assert s.name == "x" and s.tb_module == "tb_x" and s.check == "python"
    assert s.set_dir("a") == tmp_path / "vectors" / "a"
    assert s.lock_path == tmp_path / "vectors" / "vectors.lock.json"
    assert callable(s.load_callable(s.generator))


def test_rejects_missing_required(tmp_path):
    with pytest.raises(ValueError, match="missing required keys"):
        load_ipspec(_write(tmp_path, GOOD.replace("    top: x\n", "")))


def test_rejects_bad_check_mode(tmp_path):
    with pytest.raises(ValueError, match="check must be"):
        load_ipspec(_write(tmp_path, GOOD.replace("check: python", "check: maybe")))


def test_tb_check_needs_pattern_and_python_needs_compare(tmp_path):
    with pytest.raises(ValueError, match="pass_pattern"):
        load_ipspec(_write(tmp_path, GOOD.replace("check: python", "check: tb")))
    body = GOOD.replace("check: python", "check: tb\n    pass_pattern: 'LOCKSTEP PASS'")
    s = load_ipspec(_write(tmp_path, body))
    assert s.pass_pattern == "LOCKSTEP PASS"
    with pytest.raises(ValueError, match="compare"):
        load_ipspec(_write(tmp_path, GOOD.split("    compare:")[0]))


def test_generated_set_needs_generator_and_committed_does_not(tmp_path):
    with pytest.raises(ValueError, match="generator"):
        load_ipspec(_write(tmp_path, GOOD.replace("    generator: dspip.ip.sat_shift.ref:generate\n", "")))
    body = GOOD.replace("    generator: dspip.ip.sat_shift.ref:generate\n", "").replace(
        "source: generated", "source: committed, dir: vectors/halo")
    s = load_ipspec(_write(tmp_path, body))
    assert s.vector_sets[0].source == "committed" and s.set_dir("a") == tmp_path / "vectors/halo"


def test_every_ip_in_tree_loads():
    specs = all_ips(IP_ROOT)
    names = [s.name for s in specs]
    assert "sat_shift" in names
    for s in specs:
        assert s.tb_path.exists(), s.tb
        for r in s.rtl_paths():
            assert r.exists(), r
