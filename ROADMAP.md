# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1 收尾（可选、不阻塞验收）

- [ ] **P=1 在布线后处于边缘**（2026-11-06，`docs/synthesis.md`「Place and route」）：`dpd_term` 单模块布线后 644 MHz（线网与时钟树代价 11.9 %），在位置上还要慢约 5 % → 估约 610 MHz < 640。
      `repair_timing` 能收回约 5 %。要定论需对整条 P=1 数据通路（1.6 M 单元）做布局布线：`tools/pnr.py` 已能做，但本机内存与时长未试。在此之前稳妥结论是 P=2。

## 里程碑 2 之后（Halo 五个模块都已进脚手架，只做 lockstep）

- [ ] **Halo `adc_dsp_loop` 的流式形式**（唯一剩下的整块行为模型）。三种 MLSD 已流式化（Halo_Serdes#148，`halo_viterbi_stream` / `halo_sliding_stream` / `halo_dfse_stream`）。
      它是逐码元改自己系数的闭环（FFE / PR 的 LMS、MM CDR + LAT 队列、ADC 校准与延时微调），逐位精确要单独设计；在 Halo 做，本库跟进。
- [ ] **Halo 流式块的速度**：FFE+DFE 判决环 `LOOKAHEAD=1` 对受控光标变慢（−18 / −6 %），要两级推测或挪出 x[j−2] 项；DFSE 布线后 160 MHz（平方在环里）。都是 Halo ROADMAP P3 #13。

## 候选 IP（未排期）

（无。polar_tx 两点增益 LMS 已作为 `ip/dp_cal_lms` 进库，见下。）

## 推回上游

- [ ] **Halo_Serdes#147（`LOOKAHEAD`）与 #148（三种流式 MLSD，叠在 #147 上）等用户审阅合并**（先 #147，再把 #148 的 base 改回 `main`）。本库全部 Halo 文件 pin 在 #148 头 `c59c2c8`；合并后改 pin（12 个 `.sv`、13 个 SOURCE.md、`ci.yml` `HALO_SHA`），重锁，`vendor_check --strict`。

（无待回应项。PA_DPD#2 由 PA_DPD#3 修复、Halo_Serdes#136 由 Halo_Serdes#142 修复，两者已合并并重新 pin；polar_tx#16（dp_cal_lms 的定点参考）、#17（rtl_vectors 导出、dp_cal 变体）、#18（整条数字链导出）已合并，现 pin 在 `7057738`；Halo_Serdes#145（流式 FFE + DFE）已合并，Halo 现 pin 在 `acf6220`；过程见 `docs/upstream-findings.md`。新发现照旧：上游修，合并后重新 pin、重新导出、`vendor_check --strict`。）

## 被外部阻塞

- [ ] 删两个已合并的上游 PR 分支：Halo_Serdes `fix/rtl-dsp-ip-findings`（19d104f）、PA_DPD `fix/export-for-integer-rtl`（9d9c4b6）。两者都已是各自 main 的祖先（`git merge-base --is-ancestor`）；本会话 `git push origin --delete <branch>` 回 HTTP 403（git 代理策略），需用户在 GitHub 网页上删。

（其余无。verilator 5.020 / iverilog 12 由 apt 装上；yosys 固定为 OSS CAD Suite 2026-10-25（`tools/get_yosys.sh`，GitHub release 资产经代理可下）；OpenDPD、ORFS liberty 经 git 代理可取。）
