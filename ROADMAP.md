# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1 收尾（可选、不阻塞验收）

- [ ] **P=1 在布线后处于边缘**（2026-11-06，`docs/synthesis.md`「Place and route」）：`dpd_term` 单模块布线后 644 MHz（线网与时钟树代价 11.9 %），在位置上还要慢约 5 % → 估约 610 MHz < 640。
      `repair_timing` 能收回约 5 %。要定论需对整条 P=1 数据通路（1.6 M 单元）做布局布线：`tools/pnr.py` 已能做，但本机内存与时长未试。在此之前稳妥结论是 P=2。

## 里程碑 2 之后（Halo 五个模块都已进脚手架，只做 lockstep）

- [ ] **Halo 其余四个模型的流式形式**（`adc_dsp_loop`、三种 MLSD 仍是整块行为模型，只做 lockstep）。第一个已做：`halo_ffe_dfe_stream`（Halo_Serdes#145，已合并）。
      它的判决环是关键路径（3977–4987 ps）；展开判决环是 Halo ROADMAP P3 #13。发现的问题推回 Halo，本库不分叉。

## 候选 IP（未排期）

（无。polar_tx 两点增益 LMS 已作为 `ip/dp_cal_lms` 进库，见下。）

## 推回上游

（无待回应项。PA_DPD#2 由 PA_DPD#3 修复、Halo_Serdes#136 由 Halo_Serdes#142 修复，两者已合并并重新 pin；polar_tx#16（dp_cal_lms 的定点参考）、#17（rtl_vectors 导出、dp_cal 变体）、#18（整条数字链导出）已合并，现 pin 在 `7057738`；Halo_Serdes#145（流式 FFE + DFE）已合并，Halo 现 pin 在 `acf6220`；过程见 `docs/upstream-findings.md`。新发现照旧：上游修，合并后重新 pin、重新导出、`vendor_check --strict`。）

## 被外部阻塞

- [ ] 删两个已合并的上游 PR 分支：Halo_Serdes `fix/rtl-dsp-ip-findings`（19d104f）、PA_DPD `fix/export-for-integer-rtl`（9d9c4b6）。两者都已是各自 main 的祖先（`git merge-base --is-ancestor`）；本会话 `git push origin --delete <branch>` 回 HTTP 403（git 代理策略），需用户在 GitHub 网页上删。

（其余无。verilator 5.020 / iverilog 12 由 apt 装上；yosys 固定为 OSS CAD Suite 2026-10-25（`tools/get_yosys.sh`，GitHub release 资产经代理可下）；OpenDPD、ORFS liberty 经 git 代理可取。）
