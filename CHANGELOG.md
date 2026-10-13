# CHANGELOG（按里程碑）

## [未发布] — 里程碑 1：`dpd_poly` 定点 DPD 数据通路 + lockstep 脚手架（进行中）

### 阶段 0（2026-10-13）
- 仓库骨架：`dspip` 包（src 布局）、Cairn 文档、ruff/pytest 配置。
- vendor：PA_DPD@08b9725 的 12 个 Python 文件 verbatim 进 `src/dspip/vendor/padpd/`；`tools/vendor_check.py` 从 Halo_Serdes@6e79c4a 改（支持 `//` 头与 `.sv`）。
- 上游导出入库：`ip/dpd_poly/upstream/DPA_160MHz/` 的 DDR/GMP × W16/W12 系数 JSON + 参考向量 CSV（`EXPORT.md` 记命令与 SHA；本地跑两遍字节一致）。
- 工具链：verilator 5.020 / iverilog 12 / yosys 0.33（apt，`tools/toolchain.sh`）。
