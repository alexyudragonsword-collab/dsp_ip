# Results (generated — do not edit; `python tools/render_tables.py`)

## Fixed-point vs float: ACLR (rule 2)

Dataset DPA_160MHz; metric ACLR_AVG dBc via PA_DPD DGRU surrogate; upstream numbers from PA_DPD@08b9725 docs/03_roadmap.md:108-117.

| basis | model | float | W16 | W12 | W10 |
|---|---|---|---|---|---|
| ddr_r1 | PA_DPD doc | -51.6 | -51.3 | -40.4 | -29.4 |
| | upstream recomputed (vendored code) | -51.60 | -51.25 | -40.39 | -29.42 |
| | **int ref** (default) | | -51.26 | -40.44 | -29.66 |
| | **int ref** (pw+4) | | -51.27 | -40.39 | -29.49 |
| | NMSE int ref vs upstream (dB) | | -59.6 | -35.6 | – |
| gmp510 | PA_DPD doc | -50.2 | -50.1 | -46.6 | -38.5 |
| | upstream recomputed (vendored code) | -50.16 | -50.10 | -46.57 | -38.54 |
| | **int ref** (default) | | -50.09 | -46.46 | -38.56 |
| | **int ref** (pw+4) | | -50.10 | -46.57 | -38.55 |
| | NMSE int ref vs upstream (dB) | | -69.6 | -45.8 | – |

Max |upstream recomputed − PA_DPD doc| = 0.05 dB; max |int ref W16 (default) − PA_DPD doc W16| = 0.04 dB.

## Parallelism × frequency × area (rule 5)

**Estimates** — yosys (Yosys 0.33 (git sha1 2584903a060)) + ABC, NanGate45 (FreePDK45) typical, OpenROAD-flow-scripts@e5cc6e7, no wire load; f_est = 1/(ABC critical path + DFF t_cq + t_setup); method per row in the JSON (see `docs/synthesis.md`).

| set | P | mode | critical path (ps) | f_est (MHz) | throughput (MSPS) | area (mm²) | cells | P for 640 MSPS |
|---|---|---|---|---|---|---|---|---|
| ddr_r1_w16 | 1 | budget | 1948 | 476 | 476 | 1.864 | 1637506 | 2 |
| ddr_r1_w16 | 2 | budget | 2180 | 428 | 857 | 4.126 | 3920294 | 2 |
| gmp510_w16 | 1 | budget | 1306 | 685 | 685 | 4.041 | 3855190 | 1 |
| gmp510_w16 | 2 | budget | 1461 | 619 | 1238 | 6.104 | 5753243 | 2 |

- **ddr_r1_w16**: f_est ≥ 428 MHz (estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).
- **gmp510_w16**: f_est ≥ 619 MHz (estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).
