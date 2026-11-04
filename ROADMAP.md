# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1 收尾（可选、不阻塞验收）

- [ ] 两级乘法器冲 P=1（可选，用户未选）：pin 版 yosys 0.70 下 in situ 各级很平：DDR `dpd_term` 1720、`dpd_pow` 1693、加法树 1682、`dpd_env` 1580 ps；GMP `dpd_pow` 1693、树 1633–1684、`dpd_term` 1643–1670（estimate，`docs/results.md`）。
      P=1 达 640 MSPS 要求关键路径 ≤ 1e6/640 − 154 ≈ 1409 ps，即每个乘法器都要拆两拍（部分积分两组相加），加法树（顶层 ~1450）也要再切。复现：`python tools/synth.py --ip dpd_poly --set ddr_r1_w16 --mode unit --module dpd_term`。

## 里程碑 2 之后（Halo 五个模块都已进脚手架，只做 lockstep）

- [ ] **yosys 估计要等这些整块向量的行为模型改成流式后**（`always_comb`/`task run()` 风格，不可综合）。发现的问题推回 Halo，本库不分叉。
- [ ] `halo_adc_dsp_loop` 的 `sims: [iverilog]`：等 Verilator 修掉 `longint >>> longint-localparam` 常量折叠 bug（`tests/test_sim_quirks.py` 会变红提醒），或 Halo 把 `*_dims.svh` 的移位量改成 `localparam int`（已在 Halo_Serdes#136 提出）后去掉。
  Verilator issue 文稿见 `docs/verilator-issue-draft.md`（推回上游一节）。

## 候选 IP（未排期）

- polar_tx 两点调制在线增益校准 LMS（vendored `adpll.py` 的 `dp_cal.step`，`SignSignLMS`）：目前是 float64，没有定点参考，先要上游定点化。

## 推回上游（已提交，等上游回应；详情与复现见 `docs/upstream-findings.md`）

- PA_DPD#2：`FixedPointPolyModel` 不是整数 bit-true（scale 未导出、float64 高阶项、无输出量化、refvec 浮点）+ 块自适应非因果 + 2 处文档小错。
- Halo_Serdes#136：`$fscanf` 返回值不检查；已提交向量缺 `dfse_*`；`run_lockstep.sh` 写进被跟踪目录；移位量 `localparam longint` 触发 Verilator 5.020 折叠 bug。
- 上游修了之后：重新 pin、重新导出、`vendor_check --update`。

## 被外部阻塞

（无。verilator 5.020 / iverilog 12 由 apt 装上；yosys 固定为 OSS CAD Suite 2026-10-25（`tools/get_yosys.sh`，GitHub release 资产经代理可下）；OpenDPD、ORFS liberty 经 git 代理可取。）
