"""dpd_poly: fixed-point polynomial DPD datapath (DDR-Volterra / GMP bases).

- ``terms``    — the basis term table, derived from PA_DPD's column order;
- ``config``   — ``DpdPolyConfig``: every bit width and shift is a configuration value,
                 derived once from the consumer's export and frozen;
- ``datapath`` — pure-integer primitives shared by the reference and the config derivation;
- ``ref``      — the bit-true reference (``DpdPolyRef.run``), the truth the RTL must equal;
- ``floatref`` — comparison against the upstream float model and ACLR (rule 2).
"""
