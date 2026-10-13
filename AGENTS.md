# dsp_ip 协作规则

> 本项目使用 Project Cairn：`AGENTS.md` 是规则与导航入口，`cairn/` 是项目知识/状态层。同目录 `CLAUDE.md` 只有一行 `@AGENTS.md`。

## 项目一句话

bit-true 数字信号处理 IP 库：每个 IP 三份一致的东西——Python 定点参考、SystemVerilog 实现、CI 里逐样本对照（lockstep）。把 Halo_Serdes 验证过的做法做成通用脚手架；第一个用户是 PA_DPD 的定点 DPD（`ip/dpd_poly`），第二个是 Halo 自己的五个模块（里程碑 2）。

## Init 配置

- 毕业 provider：暂缓对接。知识库索引 / 毕业目标：尚未配置。

## 进入项目后的阅读顺序

1. 本文件。2. `ROADMAP.md`（只写没做的）。3. `cairn/LOG.md` 最新几条（新条目在顶部）。4. `cairn/dpd_poly定点通路.md`（数值定义与上游差异）。

## 文档职责

| 文件 | 角色 | 维护方式 |
|---|---|---|
| `AGENTS.md` | 规则与导航 | 很少变，≤ 65 行 |
| `ROADMAP.md` | 待办、被外部阻塞、推回上游 | 完成即删并在 LOG 记一笔 |
| `CHANGELOG.md` | 已交付的演进 | 按里程碑追加 |
| `cairn/LOG.md` | 时间序日志 | 新条目加顶部，≤ 20 行，数字原值 + 被推翻的判断 + 下一步 |
| `cairn/<topic>.md` | 知识专题（当前真相） | 就地更新 |
| `ip/<name>/ip.yaml` | IP 契约（端口、位宽、向量、延迟、probe） | 工程资产，留在代码树 |
| `docs/` | 面向使用者（综合口径、上游发现） | 表格由 `results/*.json` 生成，不手写数字 |

## 项目铁律（每条都有测试守着；改动时不要破坏）

1. **Python 定点参考是真值，RTL 只能逐位等于它** —— 每个 IP 的 lockstep 在全部向量上 0 个不匹配，少一个样本也算失败。守卫：`tests/test_rtl_lockstep.py`（含改一位金标必 FAIL 的 mutation 测试）。
2. **定点参考自己要对浮点负责** —— 每个 IP 有"定点对浮点"测试：位宽扫描 + 性能差（DPD 用 ACLR/NMSE，均衡器用 SNR），差值写进文档；位宽是配置不是常数。守卫：`tests/test_fixed_vs_float.py`、`tests/test_config.py::test_bitwidth_is_config`。
3. **向量来自消费方的导出，不在本库手造** —— 上游导出 pin 到完整 SHA（`ip/*/upstream/EXPORT.md`），本库只存哈希与生成命令，CI 重新生成后比对。守卫：`tests/test_vendor_check.py`、`tests/test_vectors_lock.py`、CI `vendor-drift`。
4. **一个 lockstep 脚手架服务所有 IP** —— `tools/lockstep.py <ip>` 统一编译、跑 tb、逐行比对、报第一个不匹配的样本号和寄存器；每个 IP 只提供 `ip.yaml`。改脚手架要让全部 IP 重跑（`--all`）。守卫：`tests/test_lockstep_tool.py`。
5. **综合数字标口径** —— 面积/频率只用开源流（yosys + 公开工艺库）出估计值，标 `estimate`，不写成厂商数字；没有综合结果的 IP 不许声称吞吐。守卫：`tests/test_synth_tool.py`、`tests/test_docs_numbers.py`。
6. **数值指纹** —— 重构用仓库指纹证明逐位不变（`tools/fingerprint.py record/compare`）。守卫：`tests/test_fingerprint.py`。

## 工具链与边界

- 仿真 verilator 优先，没有就 iverilog；综合 yosys。都没有先装（`tools/toolchain.sh`）；装不上写进 ROADMAP "被外部阻塞"，Python 侧照做，**不用 Python 模拟 RTL 凑绿**。厂商工具（Vivado/Quartus/DC）不假设。
- 不做：神经 DPD 的 RTL、板级 FPGA 原型/时序收敛/厂商 IP、改上游算法（定点参考不对就报回 PA_DPD/Halo，本库只做实现和对照）。
- vendor 规矩照 polar_tx：上游 Python 参考 pin 到完整 SHA，`tools/vendor_check.py --strict` + `vendor_manifest.json`；`.sv` 也走同一头注释。

## 冲突仲裁

- 代码事实 > 知识专题文档 > LOG 历史；规则层面的冲突由本文件裁定。

## 文档协作规则

- 动手前判断用户要的是"讨论/建议"还是"直接改"；修正过去的判断时追加更正说明，不静默覆盖；未经确认的判断不写成既定事实。

## 知识沉淀规则

- 每个里程碑结束：`CHANGELOG.md` 一条、`cairn/LOG.md` 一条（数字原值、被推翻的判断、下一步）、`ROADMAP.md` 删做完的、加过程中发现的问题（带复现方式和数字）。
- **完成回复闸门**：任何"已完成/已验证/测试通过"类声明之前，先核对上面三份记录已更新。
