# CHANGELOG（按里程碑）

## 里程碑 1 — `dpd_poly` 定点 DPD 数据通路 + 通用 lockstep 脚手架（2026-10-13）

### 新增
- **脚手架**：`ip/<name>/ip.yaml` 契约（`src/dspip/ipspec.py`）、`tools/lockstep.py`（verilator / iverilog，逐行比对，报第一个不匹配样本 + 参考寄存器，`--all`、`--update-lock`）、
  `src/dspip/vectors.py`（`.txt` 向量 + sha256 锁）、`tools/fingerprint.py`（Adapted from Halo_Serdes@6e79c4a）、`tools/vendor_check.py`（同上，加 `//` 头与 `.sv`）。
- **IP `sat_shift`**：舍入右移 + 饱和（dpd_poly 的输出级），3 个向量集。
- **IP `dpd_poly`**：DDR r=1（140 项）/ GMP-510（255 项）× W16/W12/W10，P 样本/拍。Python 整数参考（纯 int 真值 + int64 向量化孪生）、
  `DpdPolyConfig`（位宽/scale/移位全由上游导出推导，发 `dims_params.svh`/`dims.svh`）、RTL `dpd_env/dpd_pow/dpd_term/dpd_acc/dpd_poly.sv` + tb。
  lockstep：5 个向量集 × P=1/2/4 × 两个仿真器全部 0 不匹配。
- **上游导出入库**：PA_DPD@08b9725 对 OpenDPD@a362a8d `DPA_160MHz` 的 DDR/GMP × W16/W12 系数 JSON + 输入 CSV（`EXPORT.md`，锁在 `vectors.lock.json`）；
  `tools/check_upstream_export.py` 重新导出比对（输入/配置精确，系数码 ±1 LSB）。
- **定点对浮点**：`floatref.py` + `examples/01_bitwidth_aclr.py` → `results/aclr_table.json`；上游四个 ACLR 数复现（最大差 0.05 dB），整数参考 W16 与文档差 ≤ 0.04 dB。
- **综合估计**：`tools/get_liberty.sh`（NanGate45 pin SHA + sha256）、`tools/synth.py`（yosys + ABC stime，预算/完整模式，`kind: estimate`）、
  `examples/02_parallelism_synth.py`、`tools/render_tables.py` → `docs/results.md`。
- 文档：`docs/synthesis.md`（口径）、`docs/upstream-findings.md`（推回上游）、`cairn/dpd_poly定点通路.md`。
- CI：`lint`、`test`（py3.11/3.12）、`lockstep`（两仿真器 + mutation）、`synth`（artifact）、`vendor-drift`（`--strict` + 重新导出）、`fixed-vs-float`（torch cpu）。

### 被推翻的判断
- "上游 `refvec.csv` 可直接当 RTL 金标"：上游是浮点模拟，本库自定整数参考（见 `cairn/dpd_poly定点通路.md` §1）。
- "`a^k` 精确整数"：W16 要 79 位，改为幂预移位到 W_PW 位。
- "双因子乘积固定右移 W_PW"：会清零小包络（DDR NMSE −59.6 → −41.8 dB），改为按每项上界算 `q_pair`。
- "每相位各自延迟线"：改为一个扁平历史窗 + 静态抽头。
- "用 packed 总线汇总 N 项输出"：Icarus O(N²)（0.9 s/样本），改为每节点一根线 + 层次引用（0.002 s/样本）。

### 阶段 0（2026-10-13）
- 仓库骨架、Cairn 文档、vendor 12 个 PA_DPD 文件 verbatim、工具链 verilator 5.020 / iverilog 12 / yosys 0.33（apt）。
