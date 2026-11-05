# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1 收尾（可选、不阻塞验收）

- [ ] 两级乘法器冲 P=1（用户已选，进行中）。**流程选项已试、无效**（2026-11-05，`docs/synthesis.md` 表，`results/synth/units/flows/`）：`-booth` 让各级慢 95–520 ps，`-arith_tree` 不动 `$mul`、无变化，强制 prefix 末端加法器持平或更慢 → 改 RTL。原始数据：pin 版 yosys 0.70 下 in situ 各级很平：DDR `dpd_term` 1720、`dpd_pow` 1693、加法树 1682、`dpd_env` 1580 ps；GMP `dpd_pow` 1693、树 1633–1684、`dpd_term` 1643–1670（estimate，`docs/results.md`）。
      P=1 达 640 MSPS 要求关键路径 ≤ 1e6/640 − 154 ≈ 1409 ps，即每个乘法器都要拆两拍（部分积分两组相加），加法树（顶层 ~1450）也要再切。复现：`python tools/synth.py --ip dpd_poly --set ddr_r1_w16 --mode unit --module dpd_term`。

## 里程碑 2 之后（Halo 五个模块都已进脚手架，只做 lockstep）

- [ ] **yosys 估计要等这些整块向量的行为模型改成流式后**（`always_comb`/`task run()` 风格，不可综合）。发现的问题推回 Halo，本库不分叉。

## 候选 IP（未排期）

（无。polar_tx 两点增益 LMS 已作为 `ip/dp_cal_lms` 进库，见下。）

## 推回上游

- [ ] **polar_tx#16（定点 sign-sign LMS + 金向量）等用户审阅合并**。CI 24/24 绿（3577685）。`ip/dp_cal_lms` 现在 pin 在 PR 头 `357768536cb0…`；合并后改 pin 到合并提交：
      vendored 头注释、`ci.yml` `POLAR_TX_SHA`、`vectors/ble_5pct/SOURCE.md`、`src/dspip/vendor/__init__.py`、锁（若导出字节变化），然后 `vendor_check --strict` + `tools/check_dp_cal_export.py`。

（其余无待回应项。PA_DPD#2 由 PA_DPD#3 修复、Halo_Serdes#136 由 Halo_Serdes#142 修复，两者已合并并重新 pin；过程见 `docs/upstream-findings.md`。新发现照旧：上游修，合并后重新 pin、重新导出、`vendor_check --strict`。）

## 被外部阻塞

- [ ] 删两个已合并的上游 PR 分支：Halo_Serdes `fix/rtl-dsp-ip-findings`（19d104f）、PA_DPD `fix/export-for-integer-rtl`（9d9c4b6）。两者都已是各自 main 的祖先（`git merge-base --is-ancestor`）；本会话 `git push origin --delete <branch>` 回 HTTP 403（git 代理策略），需用户在 GitHub 网页上删。

（其余无。verilator 5.020 / iverilog 12 由 apt 装上；yosys 固定为 OSS CAD Suite 2026-10-25（`tools/get_yosys.sh`，GitHub release 资产经代理可下）；OpenDPD、ORFS liberty 经 git 代理可取。）
