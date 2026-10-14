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
| ddr_r1_w16 | 1 | hier | 1837 | 502 | 502 | 1.896 | 1504496 | 2 |
| gmp510_w16 | 1 | hier | 1883 | 491 | 491 | 3.341 | 2645488 | 2 |

P = 2 / 4 rows **by construction** (not synthesized — the user chose to stop after the P = 1 points): same stages, P copies of the term bank and tree, throughput = f_est × P, area ≈ P × area(P=1); window fan-out not modelled.

| set | P | mode | critical path (ps) | f_est (MHz) | throughput (MSPS) | area (mm²) | cells | P for 640 MSPS |
|---|---|---|---|---|---|---|---|---|
| ddr_r1_w16 | 2 | by construction | 1837 | 502 | 1004 | ≈3.792 | ≈3008992 | 2 |
| ddr_r1_w16 | 4 | by construction | 1837 | 502 | 2009 | ≈7.585 | ≈6017984 | 2 |
| gmp510_w16 | 2 | by construction | 1883 | 491 | 982 | ≈6.682 | ≈5290976 | 2 |
| gmp510_w16 | 4 | by construction | 1883 | 491 | 1964 | ≈13.363 | ≈10581952 | 2 |

- **ddr_r1_w16**: f_est ≥ 502 MHz (hier, real term count, estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).
- **gmp510_w16**: f_est ≥ 491 MHz (hier, real term count, estimate) ⇒ **P = 2** reaches 640 MSPS (throughput = f_clk × P).
