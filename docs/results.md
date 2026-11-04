# Results (generated — do not edit; `python tools/render_tables.py`)

## Fixed-point vs float: ACLR (rule 2)

Dataset DPA_160MHz; metric ACLR_AVG dBc via PA_DPD DGRU surrogate; upstream numbers from PA_DPD@5718b83 docs/03_roadmap.md:112-121.

| basis | model | float | W16 | W12 | W10 |
|---|---|---|---|---|---|
| ddr_r1 | PA_DPD doc | -51.6 | -51.3 | -40.4 | -29.4 |
| | upstream recomputed (vendored code) | -51.60 | -51.25 | -40.39 | -29.42 |
| | **int ref** (default) | | -51.26 | -40.44 | -29.66 |
| | **int ref** (pw+4) | | -51.27 | -40.39 | -29.49 |
| | **int ref** (pw+8) | | -51.26 | -40.40 | -29.52 |
| | **int ref** (F2) | | -51.26 | -40.45 | -29.68 |
| | **int ref** (pw+4_F2) | | -51.25 | -40.38 | -29.49 |
| | **int ref** (pw+8_F2) | | -51.26 | -40.38 | -29.44 |
| | NMSE int ref vs upstream (dB) | | -59.6 | -35.6 | – |
| gmp510 | PA_DPD doc | -50.2 | -50.1 | -46.6 | -38.5 |
| | upstream recomputed (vendored code) | -50.16 | -50.10 | -46.57 | -38.54 |
| | **int ref** (default) | | -50.09 | -46.46 | -38.56 |
| | **int ref** (pw+4) | | -50.10 | -46.57 | -38.55 |
| | **int ref** (pw+8) | | -50.09 | -46.57 | -38.56 |
| | **int ref** (F2) | | -50.10 | -46.46 | -38.50 |
| | **int ref** (pw+4_F2) | | -50.10 | -46.54 | -38.49 |
| | **int ref** (pw+8_F2) | | -50.10 | -46.56 | -38.50 |
| | NMSE int ref vs upstream (dB) | | -69.6 | -45.8 | – |

Max |upstream recomputed − PA_DPD doc| = 0.05 dB; max |int ref W16 (default) − PA_DPD doc W16| = 0.04 dB.

## Parallelism × frequency × area (rule 5)

**Estimates** — yosys (Yosys 0.52 (git sha1 fee39a3284c90249e1d9684cf6944ffbbcbb8f90)) + ABC, NanGate45 (FreePDK45) typical, OpenROAD-flow-scripts@e5cc6e7, no wire load; f_est = 1/(ABC critical path + DFF t_cq + t_setup); method per row in the JSON (see `docs/synthesis.md`).

| set | P | mode | critical path (ps) | f_est (MHz) | throughput (MSPS) | area (mm²) | cells | P for 640 MSPS |
|---|---|---|---|---|---|---|---|---|
| ddr_r1_w16 | 1 | hier | 1696 | 541 | 541 | 1.977 | 1531474 | 2 |
| ddr_r1_w16 | 2 | hier | 1668 | 549 | 1098 | 3.917 | 3052887 | 2 |
| ddr_r1_w16 | 4 | hier | 1707 | 537 | 2150 | 7.793 | 6090637 | 2 |
| gmp510_w16 | 1 | hier | 1697 | 540 | 540 | 3.493 | 2700301 | 2 |
| gmp510_w16 | 2 | hier | 1639 | 558 | 1116 | 6.924 | 5386983 | 2 |
| gmp510_w16 | 4 | hier | 1639 | 558 | 2231 | 13.777 | 10753924 | 2 |

Worst ABC delay per module (ps, hier rows; the largest one is the critical path, `×n` = parameterizations mapped):

| set | P | `dpd_term` | `dpd_pow` | `dpd_env` | `dpd_poly` | `dpd_acc` |
|---|---|---|---|---|---|---|
| ddr_r1_w16 | 1 | 1696 ×15 | 1614 | 1426 | 1443 | 1041 |
| ddr_r1_w16 | 2 | 1668 ×15 | 1627 | 1435 | 1443 | 556 |
| ddr_r1_w16 | 4 | 1707 ×15 | 1627 | 1477 | 1446 | 1041 |
| gmp510_w16 | 1 | 1697 ×5 | 1623 | 1488 | 1475 | 582 |
| gmp510_w16 | 2 | 1639 ×5 | 1627 | 1549 | 1460 | 582 |
| gmp510_w16 | 4 | 1639 ×5 | 1548 | 1555 | 1449 | 582 |

- **ddr_r1_w16**: f_est ≥ 537 MHz (hier, real term count, estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).
- **gmp510_w16**: f_est ≥ 540 MHz (hier, real term count, estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).
