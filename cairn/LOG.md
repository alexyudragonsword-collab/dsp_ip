# LOG（新条目在顶部；每条 ≤ 20 行：摘要 + 数字原值 + 被推翻的判断 + 下一步）

## 2026-10-13 · 里程碑 1 完成：dpd_poly RTL 在两仿真器 × 5 向量集 × P=1/2/4 全部 0 不匹配

- **lockstep**：verilator 18/18（dpd_poly 15 + sat_shift 3），iverilog 18/18；ddr_r1/gmp510 × W16/W12 各 4096 样本，rand_w16 2048 样本（含 `n_sat_phi>0`、`n_sat_out>0`）。
  mutation：改一行金标 → FAIL 且报样本号与参考寄存器；锁文件也抓到（`LOCK`）。
- **定点对浮点**（`results/aclr_table.json`，DGRU 代理，ACLR_AVG dBc）：上游四个数用 vendored 代码复现 DDR −51.60/−51.25/−40.39/−29.42、GMP −50.16/−50.10/−46.57/−38.54，
  与 PA_DPD 文档最大差 0.05；本库整数参考 W16 −51.26（DDR）/ −50.09（GMP），差 ≤ 0.04；W12 −40.44/−46.46，W10 −29.66/−38.56；`w_pw=W+4` 时 W10 DDR −29.49、W12 GMP −46.57。
  NMSE 整数参考 vs 上游浮点：−59.6/−69.6 dB（W16），−35.6/−45.8（W12）。
- **综合估计**（yosys 0.33 + NanGate45 typical，预算模式 N_TERMS=14/28，ABC fast map，无线载）：DDR W16 P=1 关键路径 1948 ps + DFF 154 ps → f_est 476 MHz → **P=2 达 640 MSPS**；
  面积外推 1.86 mm²、1.64 M cells；559 s。GMP W16 P=1：1306 ps → f_est 685 MHz → **P=1 即达 640 MSPS**，面积外推 4.04 mm²（DDR 更慢是因为双因子项那一级：乘 + sat_shift 同级）。P=2/4 点见 `docs/results.md`。单项 `dpd_term`（双因子）1294 ps、16.8 k µm²。
- **被推翻的判断**：① 上游 refvec 可当金标（否，浮点模拟）；② `a^k` 精确整数（W16 要 79 位）；③ `q_pair=W_PW` 固定（清零小包络，NMSE −59.6→−41.8）；
  ④ 每相位各自延迟线（改扁平窗）；⑤ 用 packed 总线汇总 N 项（Icarus O(N²)，0.9 s/样本 → 每节点一根线后 0.002 s/样本）；⑥ yosys 能读 `pkg::param` 端口（0.33 不能，dims 分两份 include）。
- **上游导出**：本地两遍字节一致；`tools/check_upstream_export.py` 重新导出比对 OK（68 s）。
- 测试：`python -m pytest` 108 passed / 1 skipped（含真 lockstep，9 min）；工具链 verilator 5.020 / iverilog 12 / yosys 0.33。
- 下一步：ROADMAP 里程碑 1 收尾三项（full 综合、关键路径流水、F/w_pw 扫描入表）；里程碑 2 Halo 5 模块 vendor。

## 2026-10-13 · 开库：上游"bit-true 参考向量"不能直接当金标，本库自定整数参考

- 探索 PA_DPD@08b9725：`FixedPointPolyModel` 是浮点模拟的量化（块峰值现算 scale 且未导出、float64 算 `|x|^k`、float64 累加、输出不量化、`refvec.csv` 是 `%.10e` 浮点）。
  **被推翻的判断**：prompt 假设 `export_deploy.py` 出的参考向量可直接逐样本比对——不行。决定：本库写整数参考（`ref.py`）为真值，上游只供输入 + 整数系数 JSON；差异写文档、问题推回 PA_DPD。
- 探索 Halo_Serdes@6e79c4a（prompt 写 95e2d12，上游已前进）：模块无端口、tb 层次引用、`$fscanf` 读 `.txt`、比对在 tb 内、只用 iverilog；mutation 测试改一行金标断言 FAIL。里程碑 2 要 `check: tb` + `source: committed`。
- 工具链：环境里三件都没有；`archive.ubuntu.com` 可达，apt 装上 verilator 5.020 / iverilog 12 / yosys 0.33。GitHub release tarball 403，公开仓库 git clone 可用（OpenDPD、sky130、ORFS 已验证）。
- 上游导出：OpenDPD@a362a8d `datasets/DPA_160MHz`（fs 640 MHz，4 载波 40 MHz，nperseg 16384）+ PA_DPD 导出 W16/W12，本地两遍字节一致（8 个文件 sha256 见 `EXPORT.md`）；DDR 系数 scale 2^-11（W16）/ 2^-7（W12）。
- 下一步：阶段 1 整数参考 + 定点对浮点（复现 −51.3/−40.4/−50.1/−46.6 需 torch + DGRU checkpoint）。
