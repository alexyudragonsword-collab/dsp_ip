# LOG（新条目在顶部；每条 ≤ 20 行：摘要 + 数字原值 + 被推翻的判断 + 下一步）

## 2026-10-13 · 开库：上游"bit-true 参考向量"不能直接当金标，本库自定整数参考

- 探索 PA_DPD@08b9725：`FixedPointPolyModel` 是浮点模拟的量化（块峰值现算 scale 且未导出、float64 算 `|x|^k`、float64 累加、输出不量化、`refvec.csv` 是 `%.10e` 浮点）。
  **被推翻的判断**：prompt 假设 `export_deploy.py` 出的参考向量可直接逐样本比对——不行。决定：本库写整数参考（`ref.py`）为真值，上游只供输入 + 整数系数 JSON；差异写文档、问题推回 PA_DPD。
- 探索 Halo_Serdes@6e79c4a（prompt 写 95e2d12，上游已前进）：模块无端口、tb 层次引用、`$fscanf` 读 `.txt`、比对在 tb 内、只用 iverilog；mutation 测试改一行金标断言 FAIL。里程碑 2 要 `check: tb` + `source: committed`。
- 工具链：环境里三件都没有；`archive.ubuntu.com` 可达，apt 装上 verilator 5.020 / iverilog 12 / yosys 0.33。GitHub release tarball 403，公开仓库 git clone 可用（OpenDPD、sky130、ORFS 已验证）。
- 上游导出：OpenDPD@a362a8d `datasets/DPA_160MHz`（fs 640 MHz，4 载波 40 MHz，nperseg 16384）+ PA_DPD 导出 W16/W12，本地两遍字节一致（8 个文件 sha256 见 `EXPORT.md`）；DDR 系数 scale 2^-11（W16）/ 2^-7（W12）。
- 下一步：阶段 1 整数参考 + 定点对浮点（复现 −51.3/−40.4/−50.1/−46.6 需 torch + DGRU checkpoint）。
