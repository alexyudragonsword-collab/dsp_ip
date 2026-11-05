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

**Estimates** — yosys (Yosys 0.70+219 (git sha1 5053d0e26, Release, Clang /usr/bin/clang++ 21.1.8)) + ABC, NanGate45 (FreePDK45) typical, OpenROAD-flow-scripts@e5cc6e7, no wire load; f_est = 1/(ABC critical path + DFF t_cq + t_setup); method per row in the JSON (see `docs/synthesis.md`).

| set | P | mode | critical path (ps) | f_est (MHz) | throughput (MSPS) | area (mm²) | cells | P for 640 MSPS |
|---|---|---|---|---|---|---|---|---|
| ddr_r1_w16 | 1 | hier | 1720 | 534 | 534 | 1.947 | 1529529 | 2 |
| ddr_r1_w16 | 2 | hier | 1720 | 534 | 1067 | 3.856 | 3048384 | 2 |
| ddr_r1_w16 | 4 | hier | 1720 | 534 | 2135 | 7.674 | 6086152 | 2 |
| gmp510_w16 | 1 | hier | 1693 | 541 | 541 | 3.441 | 2693550 | 2 |
| gmp510_w16 | 2 | hier | 1693 | 541 | 1083 | 6.812 | 5367302 | 2 |
| gmp510_w16 | 4 | hier | 1693 | 541 | 2166 | 13.551 | 10709666 | 2 |

Worst ABC delay per module (ps, hier rows; the largest one is the critical path, `×n` = parameterizations mapped):

| set | P | `dpd_term` | `dpd_pow` | `dpd_poly` | `dpd_env` | `dpd_acc` |
|---|---|---|---|---|---|---|
| ddr_r1_w16 | 1 | 1720 ×15 | 1693 | 1682 | 1580 | 532 |
| ddr_r1_w16 | 2 | 1720 ×15 | 1693 | 1682 | 1580 | 532 |
| ddr_r1_w16 | 4 | 1720 ×15 | 1693 | 1682 | 1580 | 532 |
| gmp510_w16 | 1 | 1643 ×5 | 1693 | 1633 | 1580 | 670 |
| gmp510_w16 | 2 | 1649 ×5 | 1693 | 1655 | 1580 | 670 |
| gmp510_w16 | 4 | 1670 ×5 | 1693 | 1684 | 1580 | 670 |

- **ddr_r1_w16**: f_est ≥ 534 MHz (hier, real term count, estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).
- **gmp510_w16**: f_est ≥ 541 MHz (hier, real term count, estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).

Other IPs, each against its own required rate (`target_rate_msps` in its ip.yaml; one sample per clock, estimate, same flow and liberty as above):

| IP | set | mode | critical path (ps) | f_est (MHz) | required (MSPS) | margin | area (µm²) | cells |
|---|---|---|---|---|---|---|---|---|
| `dp_cal_lms` | ble_5pct | full | 2216 | 422 | 32 | 13.2× | 1100 | 794 |

