# Upstream export: PA_DPD → dpd_poly (DPA_160MHz)

These files are the **consumer's** hand-off, produced by PA_DPD's own export
script and copied here unchanged (rule 3: vectors come from the consumer, this
library only stores them, their hashes and the command that made them).

| item | value |
|---|---|
| PA_DPD commit | `5718b835f9d6e5cd3680252e5d9046ab08aae7be` (merge of PA_DPD#3; before: `08b9725`) |
| OpenDPD commit (dataset `datasets/DPA_160MHz`) | `a362a8db618cb11249f310e12212a5bf7a6db9f9` |
| command (run twice, byte-identical both times) | see below |
| scipy / numpy used | 1.18.1 / 2.5.3, Python 3.13.16 |

```sh
git clone --depth 1 https://github.com/alexyudragonsword-collab/PA_DPD && git -C PA_DPD checkout 5718b83
git clone --filter=blob:none --sparse --depth 1 https://github.com/lab-emi/OpenDPD && git -C OpenDPD sparse-checkout set datasets/DPA_160MHz
cd PA_DPD
PYTHONPATH=src python3 scripts/export_deploy.py --dataset-dir ../OpenDPD/datasets/DPA_160MHz --w-bits 16 --out <out>
PYTHONPATH=src python3 scripts/export_deploy.py --dataset-dir ../OpenDPD/datasets/DPA_160MHz --w-bits 12 --out <out>
cp <out>/DPA_160MHz/*_coeffs.json <out>/DPA_160MHz/*_refvec.csv ip/dpd_poly/upstream/DPA_160MHz/
```

## What each file is

- `<basis>_w<W>_coeffs.json` — integer coefficient codes (`coeffs_real/imag`,
  one shared `coeff_scale_exp`, value = code·2^exp) plus the model class and
  config. **Used as-is** by the integer reference and the RTL. Since PA_DPD#3 also a
  `fixed_point` section: the input exponent `in_scale_exp`, one `col_scale_exp` per basis
  column and `acc_lsb_exp`, which upstream's `FixedPointPolyModel` picked on the reference
  block. `DpdPolyConfig.derive` re-derives the same values on the integer path;
  `tests/test_config.py` checks they agree (PA_DPD#2 closed).
- `<basis>_w<W>_refvec.csv` — `i_in,q_in,i_out,q_out,i_in_code,q_in_code` (the last two
  since PA_DPD#3: the integer input codes, value = code·2^in_scale_exp), 4096 samples of the
  test split. Only `i_in,q_in` are consumed (as the lockstep stimulus and the
  scale-calibration block). `i_out,q_out` are the *float* output of upstream's
  `FixedPointPolyModel`, kept for the fixed-vs-float comparison; they are not
  a bit-true golden (see `docs/upstream-findings.md`).

## Hash policy (CI `vendor-drift`)

The ILA fit goes through LAPACK, so a re-export on another machine may differ
by ±1 LSB in a coefficient code. CI re-runs the export and compares:

- exact: `i_in`/`q_in` and `i_in_code`/`q_in_code` columns (read by header name),
  `model_class`, `config`, `n_coeffs`, `coeff_scale_exp`, the `fixed_point` section;
- `|Δcode| ≤ 1` per coefficient; `i_out/q_out` within 1e-9 relative.

The lockstep golden always derives from the **committed** JSON, never from a
re-export. sha256 of the committed files is in `../../vectors/vectors.lock.json`.
