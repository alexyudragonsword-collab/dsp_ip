# Upstream export: PA_DPD → dpd_poly (DPA_160MHz)

These files are the **consumer's** hand-off, produced by PA_DPD's own export
script and copied here unchanged (rule 3: vectors come from the consumer, this
library only stores them, their hashes and the command that made them).

| item | value |
|---|---|
| PA_DPD commit | `08b9725595748b290c76d1b70355f7e6014a709e` |
| OpenDPD commit (dataset `datasets/DPA_160MHz`) | `a362a8db618cb11249f310e12212a5bf7a6db9f9` |
| command (run twice, byte-identical both times) | see below |
| scipy / numpy used | 1.18.1 / 2.5.3, Python 3.13 |

```sh
git clone --depth 1 https://github.com/alexyudragonsword-collab/PA_DPD && git -C PA_DPD checkout 08b9725
git clone --filter=blob:none --sparse --depth 1 https://github.com/lab-emi/OpenDPD && git -C OpenDPD sparse-checkout set datasets/DPA_160MHz
cd PA_DPD
PYTHONPATH=src python3 scripts/export_deploy.py --dataset-dir ../OpenDPD/datasets/DPA_160MHz --w-bits 16 --out <out>
PYTHONPATH=src python3 scripts/export_deploy.py --dataset-dir ../OpenDPD/datasets/DPA_160MHz --w-bits 12 --out <out>
cp <out>/DPA_160MHz/*_coeffs.json <out>/DPA_160MHz/*_refvec.csv ip/dpd_poly/upstream/DPA_160MHz/
```

## What each file is

- `<basis>_w<W>_coeffs.json` — integer coefficient codes (`coeffs_real/imag`,
  one shared `coeff_scale_exp`, value = code·2^exp) plus the model class and
  config. **Used as-is** by the integer reference and the RTL.
- `<basis>_w<W>_refvec.csv` — `i_in,q_in,i_out,q_out`, 4096 samples of the
  test split. Only `i_in,q_in` are consumed (as the lockstep stimulus and the
  scale-calibration block). `i_out,q_out` are the *float* output of upstream's
  `FixedPointPolyModel`, kept for the fixed-vs-float comparison; they are not
  a bit-true golden (see `docs/upstream-findings.md`).

## Hash policy (CI `vendor-drift`)

The ILA fit goes through LAPACK, so a re-export on another machine may differ
by ±1 LSB in a coefficient code. CI re-runs the export and compares:

- exact: `i_in`/`q_in` columns, `model_class`, `config`, `n_coeffs`, `coeff_scale_exp`;
- `|Δcode| ≤ 1` per coefficient; `i_out/q_out` within 1e-9 relative.

The lockstep golden always derives from the **committed** JSON, never from a
re-export. sha256 of the committed files is in `../../vectors/vectors.lock.json`.
