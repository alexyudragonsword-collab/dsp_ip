"""Vendored (adapted-copy) modules from sibling repositories.

dsp_ip's rule 3 (AGENTS.md) says vectors and reference models come from the
*consumer* repositories, pinned to a full commit SHA, and are never re-invented
here. The Python side of that contract is vendored under this package rather
than installed, so a bare checkout can derive its fixed-point configuration,
regenerate golden vectors and measure fixed-vs-float loss without the
upstream package (and its matplotlib/torch dependencies).

Each file carries a header naming its origin::

    # Vendored from <repo>@<sha>: <upstream/path.py>

and is byte-identical to upstream below the header (``tools/vendor_check.py``
re-derives this against a sibling checkout and fails CI on any undeclared
edit; the same tool scans ``ip/*/rtl/*.sv`` for ``// Vendored from`` headers
so milestone 2 can vendor Halo_Serdes' RTL under the same policy).

``padpd`` — from ``alexyudragonsword-collab/PA_DPD`` @ 08b9725 (the commit
whose ``scripts/export_deploy.py`` produced ``ip/dpd_poly/upstream/``):

- ``pa/{base,memory_polynomial,ddr,gmp,presets}.py``: the DDR-Volterra and
  GMP basis definitions (column order is the contract the integer reference
  reproduces; ``tests/test_terms.py`` asserts it) and the two preset factories;
- ``deploy/fixed_point.py``: the upstream float emulation of quantization
  (``FixedPointPolyModel``, ``quantize_symmetric``, ``_pow2_step``) that the
  integer reference's scale selection mirrors and that rule 2 compares against;
- ``deploy/export.py``: the coefficient / reference-vector export format;
- ``dpd/ila.py``, ``data/*``, ``metrics/opendpd_compat.py``: enough to re-run
  the export and the ACLR metric locally (needs scipy).

Everything else in dspip imports these only through ``dspip.vendor.padpd...``.
"""
