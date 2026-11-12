# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1 收尾（可选、不阻塞验收）

- [ ] **P=1 整条通路布局后 448 MHz，到不了 640 MSPS**（2026-11-06，`docs/synthesis.md`「Place and route」，`results/pnr/partial/`）。
      理想线网 643.5 MHz，布局代价 43.5 %；关键路径是一个触发器经 7 级缓冲跨片（约 0.9 ns 线）再 1.2 ns 逻辑——是广播距离，不是逻辑深度（4 项切片布局 635 / 布线 612 MHz）。
      全局布线 > 15 GB 本机做不了。要冲 P=1：广播寄存器复制或给广播单独一拍（RTL 改动，lockstep 守着），再跑一次 `--stop-after place`。设计点仍是 P=2。

## 里程碑 2 之后（Halo 五个模块都已进脚手架，只做 lockstep）

- [ ] **Halo `adc_dsp_loop` 的流式形式**（唯一剩下的整块行为模型）。三种 MLSD 已流式化（Halo_Serdes#148，`halo_viterbi_stream` / `halo_sliding_stream` / `halo_dfse_stream`）。
      它是逐码元改自己系数的闭环（FFE / PR 的 LMS、MM CDR + LAT 队列、ADC 校准与延时微调），逐位精确要单独设计；在 Halo 做，本库跟进。
- [ ] **Halo Viterbi 流式块没有综合数字**：16 状态 × 4 的加比选 + 16 选最小，yosys 0.70 的 ABC `sopb` 50 分钟、`nf` 40 分钟都没跑完。可试按状态拆模块走 `--mode hier`，或请 Halo 把归一化移出环。
- [ ] **Halo 流式块的速度**：FFE+DFE 判决环 `LOOKAHEAD=1` 对受控光标变慢（−18 / −6 %），要两级推测或挪出 x[j−2] 项；DFSE 布线后 160 MHz（平方在环里）。都是 Halo ROADMAP P3 #13。

## 候选 IP（未排期）

（无。polar_tx 两点增益 LMS 已作为 `ip/dp_cal_lms` 进库，见下。）

## 推回上游

- [ ] **PA_DPD 与 polar_tx 的 main 已越过本库的 pin**（2026-11-12 发现；本地 `tools/vendor_check.py --strict` 报 4 个 stale pin，CI 按 pin 检出所以不报）。
      - polar_tx `7057738` → `b007e60`：`cal/dp_cal_fixed.py` 改成步进 kernel（+97 / −18 行）；`check_polartx_export.py --polar-tx <main 检出>` 11 组全部逐字节相同 → 改 pin 只是换 SHA 与 vendored 文件。
      - PA_DPD `5718b83` → `a9220d6`：`dpd/ila.py`（ILA keep-best 加 1 dB 容差，74 行）、`pa/gmp.py`（tap_spacing、时域 PA 记忆，#4，36 行）有行为改动；改 pin 可能动 dpd_poly 的系数与向量，要重新导出、lockstep、fixed-vs-float 一起过。
      - 复现：两个兄弟仓库检出各自 main，跑 `python tools/vendor_check.py --strict`。

（无待回应项。PA_DPD#2 由 PA_DPD#3 修复、Halo_Serdes#136 由 Halo_Serdes#142 修复，两者已合并并重新 pin；polar_tx#16（dp_cal_lms 的定点参考）、#17（rtl_vectors 导出、dp_cal 变体）、#18（整条数字链导出）已合并，现 pin 在 `7057738`；Halo_Serdes#145（流式 FFE + DFE）、#147（`LOOKAHEAD`）、#148（三种流式 MLSD）已合并，Halo 现 pin 在 #148 的合并提交 `6516f1c`；过程见 `docs/upstream-findings.md`。新发现照旧：上游修，合并后重新 pin、重新导出、`vendor_check --strict`。）

## 被外部阻塞

- [ ] 删两个已合并的上游 PR 分支：Halo_Serdes `fix/rtl-dsp-ip-findings`（19d104f）、PA_DPD `fix/export-for-integer-rtl`（9d9c4b6）。两者都已是各自 main 的祖先（`git merge-base --is-ancestor`）；本会话 `git push origin --delete <branch>` 回 HTTP 403（git 代理策略），需用户在 GitHub 网页上删。

（其余无。verilator 5.020 / iverilog 12 由 apt 装上；yosys 固定为 OSS CAD Suite 2026-10-25（`tools/get_yosys.sh`，GitHub release 资产经代理可下）；OpenDPD、ORFS liberty 经 git 代理可取。）
