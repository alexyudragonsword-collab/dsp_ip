# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1 收尾（可选、不阻塞验收）

- [ ] 加法树的 40 位加法器：yosys 0.33 把 `$add` 映射成行波进位（无 `choices/` 并行前缀加法器），ABC 能否把 40 级进位链平衡好决定了顶层的关键路径（GMP 顶层 `&nf` 下 1441 ps）。
      可选：手写一个 Kogge-Stone / Brent-Kung `$lcu` techmap 放进 `tools/`，或把累加树改成进位保留（CSA）结构。
- [ ] `env_frac`（F）/ `w_pw` 扫描做成 `examples/01` 的可选参数并入表（现在只有默认与 +4 两档）。

## 里程碑 2：Halo_Serdes 的 5 个模块进同一脚手架（本轮不做）

把 `rtl/{ffe_dfe_datapath,adc_dsp_loop,sliding_mlsd,viterbi_mlsd,dfse_mlsd}.sv` 及各自 `tb_*.sv` 从 Halo_Serdes vendor 进来（`// Vendored from Halo_Serdes@<sha>` 头，`vendor_check` 已支持 `.sv`），
向量集 `source: committed`（Halo 的 `gen_vectors.py` 要跑整个 halo_serdes 包，本库不重跑，只存向量 + 哈希 + 上游生成命令），`check: tb`（Halo 的 tb 自带 `LOCKSTEP PASS/FAIL` 自检；`ipspec` 已有这两个字段）。
**只做 lockstep；yosys 估计要等这些整块向量的行为模型改成流式后**（它们是 `always_comb`/`task run()` 风格，不可综合）。发现的问题推回 Halo，本库不分叉。

## 候选 IP（未排期）

- polar_tx 两点调制在线增益校准 LMS（vendored `adpll.py` 的 `dp_cal.step`，`SignSignLMS`）：目前是 float64，没有定点参考，先要上游定点化。

## 推回上游（待提交 issue；详情与复现见 `docs/upstream-findings.md`）

- PA_DPD：`FixedPointPolyModel` 不是整数 bit-true——(1) 输入/每列 scale 按数据块峰值现算且未导出（非因果、不可实现）；(2) `|x|^k` 在 float64 里算，W16 的 `x·|x|^4` 有效位 > 53；(3) 累加是 float64 matmul、输出不量化；(4) `refvec.csv` 是浮点。
  数字：本库整数参考 vs 它 NMSE −59.6/−69.6 dB（W16 DDR/GMP）；ACLR 差 ≤ 0.04 dB（W16）。
- PA_DPD 文档小错：`ddr_volterra_default` docstring "~155" 实为 140；`export_deploy.py` 示例把 200MHz checkpoint 配 160MHz 数据集。
- Halo_Serdes：`tb_*.sv` 的 `$fscanf` 返回值不检查；已提交的 `rtl/vectors/` 缺 `dfse_*`；`run_lockstep.sh` 默认写进被跟踪的 `rtl/vectors`。

## 被外部阻塞

（无。verilator 5.020 / iverilog 12 / yosys 0.33 都已由 apt 装上；OpenDPD、ORFS liberty 经 git 代理可取。）
