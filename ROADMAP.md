# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1：PA_DPD 的定点 DPD 数据通路 `dpd_poly`（进行中）

- [ ] 阶段 1：Python 整数参考 `src/dspip/ip/dpd_poly/{terms,config,ref,floatref}.py` + 定点对浮点（复现 PA_DPD 四个 ACLR 数）
- [ ] 阶段 2：lockstep 脚手架 `tools/lockstep.py` + `ip.yaml` schema + 最小 IP `sat_shift` 跑绿
- [ ] 阶段 3：RTL `ip/dpd_poly/rtl/*.sv`，DDR/GMP × W16/W12 × P=1/2/4 全部 0 不匹配
- [ ] 阶段 4：yosys 综合估计 `tools/synth.py` + 示例 00–02 + "P=? 达到 640 MSPS" 结论
- [ ] 阶段 5：CI 全 job（lint / test / lockstep / synth / vendor-drift / fixed-vs-float），CHANGELOG/LOG 收尾

## 里程碑 2：Halo_Serdes 的 5 个模块进同一脚手架（本轮不做）

把 `rtl/{ffe_dfe_datapath,adc_dsp_loop,sliding_mlsd,viterbi_mlsd,dfse_mlsd}.sv` 及各自 `tb_*.sv` 从 Halo_Serdes vendor 进来（`// Vendored from Halo_Serdes@<sha>` 头，`vendor_check` 已支持 `.sv`），
向量集 `source: committed`（Halo 的 `gen_vectors.py` 要跑整个 halo_serdes 包，本库不重跑，只存向量 + 哈希 + 上游生成命令），`check: tb`（Halo 的 tb 自带 `LOCKSTEP PASS/FAIL` 自检）。
**只做 lockstep；yosys 估计要等这些整块向量的行为模型改成流式后**（它们是 `always_comb`/`task run()` 风格，不可综合）。发现的问题推回 Halo，本库不分叉。

## 候选 IP（未排期）

- polar_tx 两点调制在线增益校准 LMS（vendored `adpll.py` 的 `dp_cal.step`，`SignSignLMS`）：目前是 float64，没有定点参考，先要上游定点化。

## 推回上游（待提交 issue / 待上游确认）

- PA_DPD：`FixedPointPolyModel` 不是整数 bit-true——(1) 输入/每列 scale 按数据块峰值现算且未导出（非因果、不可实现）；(2) `|x|^k` 在 float64 里算，W16 的 `x·|x|^4` 有效位 > 53；(3) 累加是 float64 matmul、输出不量化；(4) `refvec.csv` 是浮点。复现：`docs/upstream-findings.md`。
- Halo_Serdes：`tb_*.sv` 的 `$fscanf` 返回值不检查（截断的向量文件不会报错）；已提交的 `rtl/vectors/` 缺 `dfse_*`；`run_lockstep.sh` 默认写进被跟踪的 `rtl/vectors`。

## 被外部阻塞

（无。verilator 5.020 / iverilog 12 / yosys 0.33 都已由 apt 装上。）
