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

**Estimates** — yosys (Yosys 0.70+219 (git sha1 5053d0e26, Release, Clang /usr/bin/clang++ 21.1.8)) + ABC (script `sopb`), NanGate45 (FreePDK45) typical, OpenROAD-flow-scripts@e5cc6e7, no wire load; f_est = 1/(ABC critical path + DFF t_cq + t_setup); method per row in the JSON (see `docs/synthesis.md`).

| set | P | mode | critical path (ps) | f_est (MHz) | throughput (MSPS) | area (mm²) | cells | P for 640 MSPS |
|---|---|---|---|---|---|---|---|---|
| ddr_r1_w16 | 1 | hier | 1313 | 682 | 682 | 2.035 | 1631554 | 1 |
| ddr_r1_w16 | 2 | hier | 1313 | 682 | 1364 | 4.032 | 3252426 | 1 |
| ddr_r1_w16 | 4 | hier | 1313 | 682 | 2727 | 8.026 | 6493770 | 1 |
| gmp510_w16 | 1 | hier | 1174 | 753 | 753 | 3.596 | 2873083 | 1 |
| gmp510_w16 | 2 | hier | 1313 | 682 | 1364 | 7.119 | 5725426 | 1 |
| gmp510_w16 | 4 | hier | 1313 | 682 | 2727 | 14.173 | 11434324 | 1 |

Worst ABC delay per module (ps, hier rows; the largest one is the critical path, `×n` = parameterizations mapped):

| set | P | `dpd_term` | `dpd_poly` | `dpd_pow` | `dpd_env` | `dpd_acc` |
|---|---|---|---|---|---|---|
| ddr_r1_w16 | 1 | 1313 ×15 | 1268 | 1265 | 1114 | 300 |
| ddr_r1_w16 | 2 | 1313 ×15 | 1057 | 1210 | 1114 | 300 |
| ddr_r1_w16 | 4 | 1313 ×15 | 835 | 1169 | 1114 | 300 |
| gmp510_w16 | 1 | 1167 ×5 | 1174 | 1172 | 1114 | 348 |
| gmp510_w16 | 2 | 1313 ×5 | 736 | 1166 | 1114 | 348 |
| gmp510_w16 | 4 | 1313 ×5 | 658 | 1166 | 1114 | 348 |

- **ddr_r1_w16**: f_est ≥ 682 MHz (hier, real term count, estimate) ⇒ **P = 1** reaches 640 MSPS (throughput = f_clk × P).
- **gmp510_w16**: f_est ≥ 682 MHz (hier, real term count, estimate) ⇒ **P = 1** reaches 640 MSPS (throughput = f_clk × P).

Other IPs, each against its own required rate (`target_rate_msps` in its ip.yaml; one sample per clock, estimate, same flow and liberty as above):

| IP | set | mode | critical path (ps) | f_est (MHz) | required (MSPS) | margin | area (µm²) | cells |
|---|---|---|---|---|---|---|---|---|
| `dp_cal_lms` | ble_5pct | full | 1736 | 529 | 32 | 16.5× | 1398 | 1104 |
| `dtc_dither` | ramp | full | 363 | 1936 | 640 | 3.0× | 222 | 141 |
| `polar_dpd_lut` | wifi20 | full | 422 | 1736 | 640 | 2.7× | 645 | 542 |

