#!/usr/bin/env python3
# Adapted from Halo_Serdes@6e79c4a: tools/vendor_check.py (itself adapted from
# polar_tx@bfa460c). dspip changes: package path and env-var prefix re-homed; the
# attribution header may start with ``#`` (Python) or ``//`` (SystemVerilog) and
# ``ip/*/rtl/*.sv`` is scanned as well as ``src/dspip/vendor/**/*.py``; the sibling
# lookup also tries the proxy clone layout ``/home/user/<owner>/<repo-lowercase>``.
"""Vendor drift check for ``src/dspip/vendor`` and vendored RTL under ``ip/*/rtl``.

Every vendored file carries an attribution header of the form::

    # Vendored from <repo>@<sha>: <upstream/path.py>
    // Vendored from <repo>@<sha>: <upstream/path.sv>

or, for a partial extraction::

    # Extracted from <repo>@<sha>: <upstream/path.py> (what was taken)

This tool re-derives, for each vendored file, its relationship to the
pinned upstream and classifies it:

* **verbatim**  — byte-identical to upstream after stripping the header.
* **adapted**   — differs only in ``import`` / ``include`` lines and/or lines
  carrying an explicit ``# dspip`` / ``// dspip`` marker (mechanical re-homing).
* **extended** / **extracted** — carries sanctioned local logic changes; the
  vendored body is pinned by ``body_sha256`` in ``vendor_manifest.json`` so an
  *unreviewed* edit to the copy is still caught.

Anything else — a non-import edit with no manifest entry, a missing header, a
manifest entry whose hash no longer matches, an upstream path that vanished —
is reported as **DRIFT** and makes the tool exit non-zero (CI gate).

Independently, for every file the pinned upstream (``@sha``) is compared with
the sibling's current ``HEAD``: if upstream moved on, the pin is flagged as
*stale* (advisory by default, fatal under ``--strict``).

Usage::

    python tools/vendor_check.py                 # check, exit 1 on drift
    python tools/vendor_check.py --strict         # also fail on stale pins / skips
    python tools/vendor_check.py --update         # regenerate the manifest
    python tools/vendor_check.py --siblings PA_DPD=/path

Sibling repos default to ``/home/user/<repo>`` (then
``/home/user/alexyudragonsword-collab/<repo lower-cased>``, the proxy clone
layout) and can be overridden with ``--siblings`` or ``DSPIP_SIBLING_<repo>``.
If a sibling checkout is absent the affected files are *skipped* (reported, not
failed) unless ``--strict`` / ``--fail-on-skip`` is given.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
VENDOR = REPO / "src" / "dspip" / "vendor"
RTL_ROOT = REPO / "ip"
MANIFEST = HERE / "vendor_manifest.json"

HEADER = re.compile(
    r"^(?P<cmt>#|//) (?P<kind>Vendored|Extracted) from (?P<repo>\S+)@(?P<sha>\w+): "
    r"(?P<path>[^\s(]+)"
)
DEFAULT_SIBLING_ROOTS = ("/home/user", "/home/user/alexyudragonsword-collab")
MARKER = "dspip"


def vendored_files() -> list[Path]:
    """All files subject to the policy: vendored python plus any .sv under
    ip/*/rtl whose first line is an attribution header."""
    out = [f for f in sorted(VENDOR.rglob("*.py")) if f.name != "__init__.py"]
    if RTL_ROOT.exists():
        for f in sorted(RTL_ROOT.glob("*/rtl/*.sv")):
            first = f.read_text().splitlines()[:1]
            if first and HEADER.match(first[0]):
                out.append(f)
    return out


def _rel(f: Path) -> str:
    try:
        return str(f.relative_to(VENDOR))
    except ValueError:
        return str(f.relative_to(REPO))


def _is_import(line: str) -> bool:
    s = line.strip()
    return (s.startswith("from ") or s.startswith("import ")
            or s.startswith("`include"))


def _body_sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class FileResult:
    rel: str
    repo: str
    sha: str
    upstream_path: str
    status: str  # verbatim | adapted | extended | extracted | DRIFT | skip
    detail: str = ""
    stale: str = ""  # non-empty if pin is behind sibling HEAD


@dataclass
class Siblings:
    roots: dict = field(default_factory=dict)

    def path(self, repo: str) -> Path | None:
        cands = []
        if repo in self.roots:
            cands.append(self.roots[repo])
        env = os.environ.get(f"DSPIP_SIBLING_{repo}")
        if env:
            cands.append(env)
        for root in DEFAULT_SIBLING_ROOTS:
            cands.append(os.path.join(root, repo))
            cands.append(os.path.join(root, repo.lower()))
        for c in cands:
            p = Path(c)
            if (p / ".git").exists():
                return p
        return None

    def show(self, repo: str, ref: str, path: str) -> str | None:
        root = self.path(repo)
        if root is None:
            return None
        r = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{path}"],
            capture_output=True, text=True,
        )
        return r.stdout if r.returncode == 0 else None

    def has_commit(self, repo: str, sha: str) -> bool:
        """Is the pinned commit object present in this checkout?  A shallow /
        rewritten sibling clone (typical in CI) may not contain a historical
        pin; try a targeted fetch once before giving up."""
        root = self.path(repo)
        if root is None:
            return False

        def _have():
            return subprocess.run(
                ["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"],
                capture_output=True).returncode == 0

        if _have():
            return True
        subprocess.run(["git", "-C", str(root), "fetch", "--quiet",
                        "--depth=1", "origin", sha],
                       capture_output=True)
        return _have()

    def head(self, repo: str) -> str | None:
        root = self.path(repo)
        if root is None:
            return None
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else None


def _strip_header(lines: list[str], cmt: str) -> str:
    """Drop the leading run of ``# ...`` / ``// ...`` attribution comment lines."""
    n = 0
    for ln in lines:
        if ln.startswith(cmt + " "):
            n += 1
        else:
            break
    return "\n".join(lines[n:]).rstrip("\n")


def _classify(body: str, upstream: str) -> tuple[str, str]:
    """Return (kind, detail) where kind in verbatim|adapted|local."""
    if body == upstream:
        return "verbatim", ""
    diff = [
        ln for ln in difflib.unified_diff(
            upstream.splitlines(), body.splitlines(), lineterm="")
        if ln[:1] in "+-" and ln[:3] not in ("---", "+++")
    ]
    nonimport = [
        ln[1:] for ln in diff
        if ln[1:].strip() and not _is_import(ln[1:])
        and f"# {MARKER}" not in ln[1:] and f"// {MARKER}" not in ln[1:]
    ]
    if not nonimport:
        return "adapted", f"{len(diff)} import/marker line(s) re-homed"
    return "local", f"{len(nonimport)} non-import diff line(s)"


def check(siblings: Siblings, manifest: dict) -> list[FileResult]:
    results: list[FileResult] = []
    declared = manifest.get("files", {})
    seen: set[str] = set()

    for f in vendored_files():
        rel = _rel(f)
        seen.add(rel)
        lines = f.read_text().splitlines()
        m = HEADER.match(lines[0]) if lines else None
        if not m:
            results.append(FileResult(rel, "?", "?", "?", "DRIFT",
                                      "missing attribution header"))
            continue
        repo, sha, upath, kind = (m["repo"], m["sha"], m["path"], m["kind"])
        body = _strip_header(lines, m["cmt"])
        entry = declared.get(rel)

        # sibling availability
        if siblings.path(repo) is None:
            results.append(FileResult(rel, repo, sha, upath, "skip",
                                      "sibling repo not present"))
            continue
        if not siblings.has_commit(repo, sha):
            results.append(FileResult(rel, repo, sha, upath, "skip",
                                      f"pinned commit {sha} unreachable here"))
            continue
        upstream = siblings.show(repo, sha, upath)
        if upstream is None:
            results.append(FileResult(rel, repo, sha, upath, "DRIFT",
                                      f"upstream path {upath}@{sha} not found"))
            continue
        upstream = upstream.rstrip("\n")

        # stale-pin (advisory): pinned sha vs sibling HEAD
        stale = ""
        head_body = siblings.show(repo, "HEAD", upath)
        if head_body is not None and head_body.rstrip("\n") != upstream:
            n = sum(1 for ln in difflib.unified_diff(
                upstream.splitlines(), head_body.rstrip("\n").splitlines(),
                lineterm="") if ln[:1] in "+-" and ln[:3] not in ("---", "+++"))
            stale = f"upstream HEAD differs by {n} line(s) since @{sha}"
            if entry and entry.get("pin_frozen"):
                stale = ""

        if kind == "Extracted":
            status, detail = _extracted_or_extended(rel, body, entry, "extracted")
        else:
            klass, detail = _classify(body, upstream)
            if klass in ("verbatim", "adapted"):
                status = klass
            else:
                status, detail = _extracted_or_extended(rel, body, entry, "extended")
        results.append(FileResult(rel, repo, sha, upath, status, detail, stale))

    for rel in declared:
        if rel not in seen:
            results.append(FileResult(rel, declared[rel].get("repo", "?"),
                                      declared[rel].get("sha", "?"),
                                      declared[rel].get("upstream_path", "?"),
                                      "DRIFT", "manifest entry has no vendored file"))
    return results


def _extracted_or_extended(rel, body, entry, mode) -> tuple[str, str]:
    if entry is None:
        return "DRIFT", (f"undeclared {mode} file — sanctioned local changes "
                         f"must be recorded in vendor_manifest.json (--update)")
    if entry.get("body_sha256") != _body_sha(body):
        return "DRIFT", ("vendored body changed since manifest was recorded "
                         "— review, then re-run --update")
    return mode, entry.get("reason", "")


def build_manifest(siblings: Siblings) -> dict:
    """(Re)build the manifest from the current tree. Hash-pins local files."""
    files: dict = {}
    for f in vendored_files():
        rel = _rel(f)
        lines = f.read_text().splitlines()
        m = HEADER.match(lines[0]) if lines else None
        if not m:
            continue
        repo, sha, upath, kind = (m["repo"], m["sha"], m["path"], m["kind"])
        body = _strip_header(lines, m["cmt"])
        if kind == "Extracted":
            files[rel] = _entry(repo, sha, upath, "extracted", body, _existing(rel))
            continue
        upstream = siblings.show(repo, sha, upath)
        if upstream is None:
            raise SystemExit(f"cannot build manifest: {repo}@{sha}:{upath} "
                             f"unavailable (need sibling checkout)")
        klass, _ = _classify(body, upstream.rstrip("\n"))
        if klass == "local":
            files[rel] = _entry(repo, sha, upath, "extended", body, _existing(rel))
    return {
        "_note": ("Auto-generated by tools/vendor_check.py. Only files with "
                  "sanctioned local changes (extended/extracted) are pinned "
                  "here by body_sha256; verbatim/adapted files are verified "
                  "directly against pinned upstream."),
        "files": files,
    }


def _entry(repo, sha, upath, mode, body, prev) -> dict:
    e = {"repo": repo, "sha": sha, "upstream_path": upath, "mode": mode,
         "body_sha256": _body_sha(body),
         "reason": prev.get("reason", "TODO: describe the sanctioned local change")}
    if prev.get("pin_frozen"):
        e["pin_frozen"] = prev["pin_frozen"]
    return e


def _existing(rel: str) -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text()).get("files", {}).get(rel, {})
    return {}


_STATUS_ORDER = ["DRIFT", "extended", "extracted", "adapted", "verbatim", "skip"]


def report(results: list[FileResult], strict: bool,
           fail_on_skip: bool = False) -> int:
    by = {s: [r for r in results if r.status == s] for s in _STATUS_ORDER}
    print("dspip vendor drift check")
    print("=" * 60)
    for s in _STATUS_ORDER:
        rs = by.get(s, [])
        if not rs:
            continue
        print(f"\n[{s}] {len(rs)}")
        for r in rs:
            line = f"  {r.rel}"
            if r.detail:
                line += f"  — {r.detail}"
            print(line)
            if r.stale:
                print(f"      ! stale pin: {r.stale}")
    drift = by.get("DRIFT", [])
    stale = [r for r in results if r.stale]
    skipped = by.get("skip", [])
    print("\n" + "=" * 60)
    print(f"summary: {len(results)} files | "
          f"{len(by.get('verbatim', []))} verbatim, "
          f"{len(by.get('adapted', []))} adapted, "
          f"{len(by.get('extended', []))} extended, "
          f"{len(by.get('extracted', []))} extracted, "
          f"{len(skipped)} skipped")
    if stale:
        print(f"stale pins: {len(stale)} (advisory{'' if strict else '; use --strict to fail'})")
    if drift:
        print(f"DRIFT: {len(drift)} — see above")
        return 1
    if skipped and (strict or fail_on_skip):
        print(f"{len(skipped)} file(s) could not be verified — a skip here is "
              "an unchecked file, not a pass")
        return 1
    if stale and strict:
        print("strict: stale pins present")
        return 1
    print("OK: no drift")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true",
                    help="regenerate vendor_manifest.json from the current tree")
    ap.add_argument("--strict", action="store_true",
                    help="also fail on stale pins or missing sibling repos")
    ap.add_argument("--fail-on-skip", action="store_true",
                    help="fail if any file could not be verified, while still "
                         "tolerating stale pins")
    ap.add_argument("--siblings", nargs="*", default=[], metavar="repo=path",
                    help="override sibling repo locations")
    args = ap.parse_args(argv)

    roots = {}
    for spec in args.siblings:
        if "=" not in spec:
            ap.error(f"--siblings expects repo=path, got {spec!r}")
        k, v = spec.split("=", 1)
        roots[k] = v
    siblings = Siblings(roots)

    if args.update:
        manifest = build_manifest(siblings)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"wrote {MANIFEST.relative_to(REPO)} "
              f"({len(manifest['files'])} pinned file(s))")
        return 0

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    results = check(siblings, manifest)
    return report(results, args.strict, args.fail_on_skip)


if __name__ == "__main__":
    raise SystemExit(main())
