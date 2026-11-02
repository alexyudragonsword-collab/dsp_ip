# ROADMAP（只写没做的；做完即删并在 `cairn/LOG.md` 记一笔）

## 里程碑 1 收尾（可选、不阻塞验收）

- [ ] 加法树的 40 位加法器：yosys 0.33 把 `$add` 映射成行波进位（无 `choices/` 并行前缀加法器），ABC 能否把 40 级进位链平衡好决定了顶层的关键路径（GMP 顶层 `&nf` 下 1441 ps）。
      可选：手写一个 Kogge-Stone / Brent-Kung `$lcu` techmap 放进 `tools/`，或把累加树改成进位保留（CSA）结构。
- [ ] 在能连续跑 3 小时以上的机器上补综合 P=2/4（hier，`&nf -D 1000`），替换 `docs/results.md` 里的 by-construction 行。
- [ ] `lockstep.py` 并发时互删向量目录改为临时目录原子替换。
- [ ] `env_frac`（F）/ `w_pw` 扫描做成 `examples/01` 的可选参数并入表（现在只有默认与 +4 两档）。

## 里程碑 2：Halo_Serdes 的 5 个模块进同一脚手架（试点已完成，余 4 个）

试点 `ip/halo_ffe_dfe`（`ffe_dfe_datapath.sv` + `tb_ffe_dfe.sv` 一字不改，`check: tb`、`source: committed`）两仿真器已绿，mutation 测试覆盖。余下按同一模板：
- [ ] `adc_dsp_loop` + `tb_adc_dsp_loop`（5 个向量目录：`.`、`pr`、`pr4`、`pre`、`cal`，各自 `loop_dims.svh`）
- [ ] `sliding_mlsd`、`viterbi_mlsd`（向量 `mlsd_*`、`vit_*` 已在 Halo 提交集里）
- [ ] `dfse_mlsd`：Halo 已提交集缺 `dfse_*`，要用 Halo 的 `gen_vectors.py` 生成一次并记命令（已在 Halo_Serdes#136 提出）
**只做 lockstep；yosys 估计要等这些整块向量的行为模型改成流式后**（`always_comb`/`task run()` 风格，不可综合）。发现的问题推回 Halo，本库不分叉。

## 候选 IP（未排期）

- polar_tx 两点调制在线增益校准 LMS（vendored `adpll.py` 的 `dp_cal.step`，`SignSignLMS`）：目前是 float64，没有定点参考，先要上游定点化。

## 推回上游（已提交，等上游回应；详情与复现见 `docs/upstream-findings.md`）

- PA_DPD#2：`FixedPointPolyModel` 不是整数 bit-true（scale 未导出、float64 高阶项、无输出量化、refvec 浮点）+ 块自适应非因果 + 2 处文档小错。
- Halo_Serdes#136：`$fscanf` 返回值不检查；已提交向量缺 `dfse_*`；`run_lockstep.sh` 写进被跟踪目录。
- 上游修了之后：重新 pin、重新导出、`vendor_check --update`。

## 被外部阻塞

（无。verilator 5.020 / iverilog 12 / yosys 0.33 都已由 apt 装上；OpenDPD、ORFS liberty 经 git 代理可取。）
