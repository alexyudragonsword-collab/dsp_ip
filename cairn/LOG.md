# LOG（新条目在顶部；每条 ≤ 20 行：摘要 + 数字原值 + 被推翻的判断 + 下一步）

## 2026-11-06 · Halo 第一个可综合块（halo_ffe_dfe_stream）；Halo IP 全部改 pin 到 56b92c2

- Halo_Serdes#145：流式 FFE + DFE + 判决器，四种目标 × 两套位宽逐位同（Icarus 12 / 14、Verilator 5.020 / 5.053）。
- 写的时候踩了三个坑：`?:` 的无符号 `'0` 臂让乘法变无符号；上下文位宽造出 23×23 乘法器；15 个积融成 `$macc_v2` 时 ABC `&fraig -x` 四分钟不收敛（积先寄存后 4.6 s）。
- 估计：delta 3977 ps，预编码 4987 ps；关键路径是判决环约 32 级门。**被推翻的判断**：判决器比较链是瓶颈——改成树反而 4.29 ns，已退回。
- vendor_check 报 Halo main 已动（aca6123 之后 61 行 + 向量重生成），六个 Halo IP 一并改 pin 到 `56b92c2`，全部通过。
- 下一步：Halo#145、polar_tx#18 合并后改 pin；Halo 其余四个模型流式化（ROADMAP）。

## 2026-11-06 · polar_tx 数字链：cfr_clip / dtc_phase_acc / dpa_thermo_decode / polar_datapath

- polar_tx#18：`datapath_golden` 第一次写下五个块之间的级间位宽（取高位、AM-PM 校正左移 5 位相减，与 `chain.py` 同号），**请用户在 PR 里审**。
- 四个新 IP 第一次跑就全过（四个仿真器）；整条链两路延迟都是 3，用 out_valid 对齐，tb 不靠延迟数字比较。
- 数字：突发 PAPR 9.20 → 6.73 dB；DPA 码误差 −0.88…+0.12 LSB（截高位偏置 −0.37）；DTC 码 ±1.04 LSB；通路 1573 MHz（ABC）/ 1493 MHz（布线）。
- 级联约定的副作用：CFR 门限 0.75 FS 加取高 8 位，LUT 上 1/4 地址整条链永远不访问（192 / 256），已写进 PR 描述。
- 下一步：Halo 模块流式化；polar_tx#18 合并后改 pin。

## 2026-11-06 · OpenROAD 布局布线：乘法级线网代价 8–12 %，P=1 回到边缘

- 用户选 litex-hub 包。频道依赖要 Anaconda `defaults` 的 libboost 1.73（另有条款，不用），conda-forge 上三者一起无解，Python 3.10 还被解成 GraalPy（没有 libpython）。
  最后用两个 conda-forge 前缀凑齐动态库：`tools/get_openroad.sh`，从零 26 s。
- 第一版比较是 ABC 对布线，`dp_cal_lms` 布线后"更快"（529 → 646 MHz）——**这个比较是错的**：`repair_design` 改了约 2400 个门的尺寸，ABC 的 `stime` 也是另一套延迟模型。改为同一网表、同一计时器的"理想线网 vs 布线"。
- 布线代价：`dpd_term` −11.9 %（721 → 644 MHz）、`dpd_pow` −8.3 %、`dp_cal_lms` −9.3 %；env / acc / LUT 为负（时钟偏斜）。`repair_timing` @1.45 ns：`dpd_term` 674.5 MHz。
- **被推翻的判断**：上一轮"P=1 达 640 MSPS"是无线网结论；带线网后 P=1 在边缘（估约 610 MHz），稳妥是 P=2，已写进 ROADMAP 与 `docs/synthesis.md`。
- 两次运行逐值相同。CI 加 `pnr` job。下一步：polar_tx 数字链 IP；Halo 流式化。

## 2026-11-06 · polar_tx#17 合并（0e76e3e），全部 polar_tx 文件改 pin

- 用户选"合并 #17 并改 pin"。合并提交的 src/ 与 PR 头 `e928557` 相同（PR 头之后只有 Windows 换行的测试修复 `b26e8ae`）。
- 本库改 pin：两个 vendored 头注释、`vendor/__init__.py`、`ci.yml` `POLAR_TX_SHA`、7 个 SOURCE.md；`check_polartx_export` 7/7 逐字节一致，vendor_check 24/24，三个 IP lockstep 全过，重锁。
- 下一步（用户已选）：polar_tx 数字链补齐、Halo 模块流式化、OpenROAD（litex-hub 包）布局布线。

## 2026-11-05 · 新 IP dtc_dither / polar_dpd_lut，dp_cal_lms 加三组，指纹全覆盖；余量不换阶数；sky130 交叉

- polar_tx#17：`export/rtl_vectors.py` + `dp_cal_vectors --variant`，CI 待看，**等用户合并**。本库 pin 在 PR 头 `e928557`。
- 新 IP 第一次跑就全过：dtc_dither 2 组、polar_dpd_lut 1 组、dp_cal_lms 新 3 组，Verilator 5.020/5.053、Icarus 12/14 全 0 不匹配。
- 综合（NanGate45，sopb）：dtc_dither 363 ps / 222 µm²；polar_dpd_lut 422 ps / 645 µm²，ROM 内容经 `chparam -set` 传入（`hierarchy -chparam` 不认字符串、yosys 不认 `parameter string`）。
- **被推翻的判断**：① "余量可以换回阶数" —— 旧版本在 sopb 下 env 1403、pow 1375、term 1543/1770 ps，term 破线，面积只省 1–3 %，不换；② "sky130 早已接好" —— `get_liberty.sh sky130` 指向的仓库没有合并 `.lib`，从未能用，改用 ORFS sky130hd。
- sky130 P=1：DDR / GMP 都是 6850 ps（`dpd_env`）→ 134 MHz → P=5；排序与 NanGate45 不同，开方级最慢。
- 布局布线被阻塞：没有 OpenROAD；litex-hub 预编译包的下载执行被权限策略拒绝，等用户决定（ROADMAP）。
- 下一步：polar_tx#17 合并后改 pin。

## 2026-11-05 · polar_tx#16 合并（f43cd4f），dp_cal_lms 改 pin

- 用户指示"合并到 main"后合并 polar_tx#16（merge 提交 `f43cd4f`，文件树与 PR 头 `3577685` 相同）。
- 本库改 pin：vendored 头注释、`vendor/__init__.py`、`ci.yml` `POLAR_TX_SHA`、`ble_5pct/SOURCE.md`；在合并提交上重新导出逐字节相同，只有 SOURCE.md 的哈希变（重锁）。
- ROADMAP 的"等用户合并"项删除。被外部阻塞仅剩两个上游分支待用户在网页上删。

## 2026-11-05 · P=1 达标：瓶颈是 ABC 的 dc2 把加法器折成链，不是 RTL

- 孤立块测得进位约 37 ps/位（40 位加 1481 ps，24 位 959，20 位 757，16 位 570）——yosys 给的是 Brent-Kung，**被 ABC `dc2` 的面积改写折成了近链式**。
  ABC 脚本试了 9 种：去掉 dc2 1631、`&syn2/&synch2` 更慢；一轮 `&if -g` 1112；**两轮 506**（16×16 乘 1069）；三轮 517。
- 采纳两轮（`--abc sopb`，默认）：DDR P=1 1720 → 1313 ps（682 MHz），GMP 1693 → 1174（753 MHz），面积 +4.5 %，本机各 12 / 9 min。
- **被推翻的判断**：① 11-03 条目与 ROADMAP 说"P=1 要每个乘法器拆两拍、加法树再切"——不需要，RTL 一行没动；② 上一条"P=1 需要改 RTL，不是流程选项"——对 yosys `synth` 选项成立，对 ABC 脚本不成立；③ 11-03 归因"yosys 0.33 的 `$alu→$lcu` 是 Brent-Kung，所以加法树不是瓶颈"只对了一半：yosys 侧是 BK，ABC 之后不是。
- CI `synth-long`（run 41971912703）六点：本机 P=1 两点逐值复现；DDR 1313 ps 各 P，GMP 1174 / 1313 / 1313（P≥2 时 `dpd_term` 同参数映成 1313，映射噪声），面积随 P 1.98× / 3.94×。
- 旧数字在 `results/synth/abc_nf/`。下一步：polar_tx#16 合并后改 pin。

## 2026-11-05 · 新 IP dp_cal_lms（polar_tx#16 头）；P=1 的综合流程选项全无效

- polar_tx#16：`FixedSignSignLMS` + 导出器，CI 24/24 绿，**等用户合并**（我不合）。本库按 PR 头 `3577685` vendor 并提交向量。
- `dp_cal_lms` RTL 第一次跑就 104 004 样本 0 不匹配（四个仿真器）；综合 2216 ps / 422 MHz / 1100 µm²（estimate），要求 32 MHz。
- 规则 2 开环：同步长时定点–浮点最大差 4.4e-4；拿上游浮点自己的 mu=2e-5、ema=1e-3 开环重放会差 0.017——**这不是定点误差**：重放的误差信号是定点增益轨迹产生的，浮点步长大就超调；这种比较只能闭环做（polar_tx 已做）。
- 流程选项（unit 探针，ps）：term 1652 → booth 2086 / arith 1652 / prefix 1652；pow 1693 → 1870 / 1693 / 1719；env 1580 → 1675 / 1580 / 1580。**被推翻的判断**：计划里"先试 `-booth` / `-arith_tree -final prefix`，可能够"——不够，booth 更慢（面积 −6~−23 %），arith_tree 不碰单个 `$mul`。
- 下一步：2b 改 RTL（乘法器拆两拍、树按级收窄/拆加法）；polar_tx#16 合并后改 pin。

## 2026-11-05 · 工具链与 CI 卫生：lockstep 跑两套仿真器、quirk 按版本、sibling 认 pin、Actions 升 node24

- `DSPIP_SIM_BIN` / `lockstep.py --sim-bin`：bundle（Verilator 5.053 devel rev v5.052-586、Icarus 14.0 devel）本机 verilator 27/27、iverilog 27/27 点 0 不匹配；apt（5.020 / 12）照旧。CI lockstep 矩阵 distro + bundle。
- quirk 探针：5.020 `a>>>SH_longint` = 0、5.053 = 16384，按版本写死；不再用"修好就 fail"的方式提醒（没有 IP 还需要 `sims:` 限制）。
- vendor_check：`/home/user/halo_serdes`（PR 克隆，HEAD 19d104f，无 aca6123）排在 pin 克隆前也不再抢；不设 env 22/22 verbatim。
- Actions：checkout v4→v7、setup-python v5→v7、cache v4→v6、upload-artifact v4→v7（tag 上 action.yml 都是 node24）。
- **被推翻的判断**：上一条说"PR 分支合并后删掉即可"——本会话 `git push origin --delete` 对 Halo `fix/rtl-dsp-ip-findings`、PA_DPD `fix/export-for-integer-rtl` 都回 HTTP 403（git 代理策略；两分支已确认是各自 main 的祖先），没删成，留给用户在网页上删（ROADMAP 被外部阻塞）。
- 测试：ruff 干净；非 lockstep 119 passed；quirk 测试 apt/bundle 各 3 passed。
- 下一步：polar_tx 定点 LMS PR（3a）→ 冲 P=1 流程选项（2a）→ dsp_ip `dp_cal_lms`（3b）。

## 2026-11-04 · 两个上游 PR 合并并重新 pin；yosys 固定为 0.70，六点重综合、本机与 CI 可复现

- **PA_DPD#3**（合并 5718b83）：导出带指数与输入码；重新导出后旧 JSON 键 + CSV 前四列逐字节相同，本库推出的 e_in / e_c / 输入码与导出值 4/4 全等 —— PA_DPD#2 闭环。
- **Halo_Serdes#142**（合并 aca6123）：移位量 int、tb 读检查（截断到 100 行 → `short read ... entry 100`、rc 1）、run_lockstep 用临时目录、补 dfse。
  Halo 侧：指纹 986 值逐位相同；全量 JIT 1450 / 3 skip，NO_JIT 1341 / 112 skip；Android 两个 API 与编译版 APK 都绿。本库 loop 在 Verilator 5.020 下 5/5（修前 1/5），`sims` 限制去掉。
- **yosys pin**（OSS CAD Suite 2026-10-25，Yosys 0.70+219）：DDR P=1/2/4 关键路径 1720 ps（`dpd_term`），GMP 1693 ps（`dpd_pow`）；面积 DDR 1.947 / 3.856 / 7.674 mm²，
  GMP 3.441 / 6.812 / 13.551 mm²；单元 1.53 M / 3.05 M / 6.09 M、2.69 M / 5.37 M / 10.71 M（estimate，`docs/results.md`）。同一 RTL 的 P=1：0.33 1554 → 0.52 1696 → 0.70 1720（DDR）。
  本机 vs CI（同一二进制）：关键路径 6/6 相同，面积 / 单元 5/6 相同，GMP P=1 面积 −0.024 %（各自重跑稳定）。runner 每点 6–24 min。
- **被推翻的判断**：① "pin 一个 yosys 只是换个装法" —— 0.70 改了 `stat` 表（≥ 1e7 用 E 记数，CI 的 GMP P=4 报成一个子模块的 10110 单元）和 ABC 输出顺序（逐模块表全记到 dpd_acc 名下），两处都修了、测了两种格式；
  ② "Verilator bug 要去上游报" —— 5.053 已修；③ "Halo 提交集与生成器一致"（只在 6e79c4a 成立，82ee2c4 上已 54 个文件不同，#142 一并刷新）；
  ④ "PR 克隆不影响 vendor_check" —— `/home/user/<repo>` 的新克隆抢在 pin 克隆前面被找到，本地要设 `DSPIP_SIBLING_*`。
- 杂项：重新综合的 sat_shift / units 探针 JSON 混进了 PA_DPD 重新 pin 的提交（bc4d2cd），内容是 pin 版本的正确结果。
- 测试：本库全量 157 passed（loop × verilator 不再跳过）；PA_DPD#3 CI 29 项全绿；Halo#142 CI 见合并记录。
- 下一步：两级乘法器冲 P=1（ROADMAP，可选）；流式化 Halo 模块以便综合（ROADMAP）。

## 2026-11-03 · 瓶颈归因纠错：是乘法级不是加法树；乘法级重分级后单模块 ~1500 ps；P=1/2/4 真实综合交给 CI

- **更正 10-14 / 10-13 条目**：那两条把关键路径归给"40 位行波进位加法器 + ABC 平衡"。本机 hier 日志逐模块 ABC 延迟（ps，DDR/GMP）：`dpd_pow` **1837/1883**、`dpd_env` 1789/1738、`dpd_term` 最差 1734/1679、顶层（加法树）1441/1441、`dpd_acc` 854/981。
  yosys 0.33 `synth` 的 `$alu→$lcu` 是 Brent-Kung（独立 40 位加 `ltp` 18）。1837/1883 这两个数字本身没错，归因错了；那时没有逐模块表，现在 hier JSON 带 `modules`。
- **重分级**（RTL 逐位不变；verilator 15 点、iverilog 15 点 0 不匹配）：pow 全部拆成 W×W 积（a²=h·2^W+l 展开）、env 平方/相加拆级、term 积/加减拆级；总延迟 +3 拍（ENV_LAT W_ENV+2、POW_LAT 4、TERM_LAT 6）。
  单模块探针 `synth.py --mode unit`（NanGate45，默认参数，ps）：pow 1762→1515（中间试过 a³·a 48×16 **1988**、两个 32×16 半积 1934、两个 48×8 半积 2283，都更差）、env 1789→1337、term(K1=1) 1949→1488、term(默认) 1949→1511。
  同一 RTL 在 situ 与单独综合差 ±10 %（老 term 单独 1949、在 situ 1734），ABC 映射噪声照旧。
- **CI `synth-long`**（dispatch run 26，81b31fc，**yosys 0.52**，estimate，见 `docs/results.md`）：DDR P=1/2/4 关键路径 1696/1668/1707 ps → f_est 541/549/537 MHz，面积 1.977/3.917/7.793 mm²，runner 14/19/24 min；
  GMP 1697/1639/1639 ps → 540/558/558 MHz，3.493/6.924/13.777 mm²，6/8/10 min。**两基都是 P=2 达 640 MSPS（estimate）**；面积 P=2 是 P=1 的 1.98 倍、P=4 是 3.94 倍（by-construction 假设成立）；关键路径不随 P 变（±4 % 噪声）。
  in situ 关键路径现在是 `dpd_term` 的乘法级（1639–1707），`dpd_pow` 1548–1627、`dpd_env` 1426–1555、加法树 1443–1475。
- **同版本前后对比**（本机 yosys 0.33，P=1，`results/synth/yosys033/`，estimate）：DDR 1837→1554 ps（502→586 MHz，面积 1.896→1.981 mm²，+4.5 %），GMP 1883→1554 ps（491→586 MHz，3.341→3.504 mm²，+4.9 %）。
  同一 RTL 在 0.52 上是 1696/1697 ps：**工具版本差 ~140 ps（9 %），0.52 更差**。表用 0.52（与 CI 一致），0.33 点只作对照。
- **脚手架收尾**：lockstep 每 IP 一把 `flock` + 临时目录生成、内容相同不碰活目录。第一版只靠两次 rename，4 线程测试 8 次挂 5 次（rename 间隙活目录消失，别的线程校验看到缺文件）→ 加锁后 8/8；锁文件原子写；`examples/01` 变体网格 `default, pw+4, pw+8, F2, pw+4_F2, pw+8_F2`；Verilator issue 文稿（`add_repo verilator/verilator` 被权限层拒绝，待用户手提）。
- **ACLR 变体扫描**（`examples/01 --w-pw-plus 0 4 8 --env-frac 0 2`，dBc，W16/W12/W10）：DDR default −51.26/−40.44/−29.66、pw+4 −51.27/−40.39/−29.49、pw+8 −51.26/−40.40/−29.52、F2 −51.26/−40.45/−29.68；
  GMP default −50.09/−46.46/−38.56、pw+4 −50.10/−46.57/−38.55、pw+8 −50.09/−46.57/−38.56、F2 −50.10/−46.46/−38.50。default/pw+4 与 10-13 逐位相同。**F=2 和 pw+8 都没有可测收益**（≤0.06 dB），pw+4 仍是 W12 GMP / W10 DDR 唯一值得的档；W16+F2 的 a⁴ 约 70 位，超出 int64，自动退回纯整数参考（每变体 <1 min）。
- **被推翻的判断**：① 加法树是瓶颈（见上）；② "48×16 比 32×32 浅"（否，见探针）；③ "单模块探针 ~1500 ps 就是 in situ 数字"——in situ 0.33 是 1554、0.52 是 1639–1707；
  ④ "CI apt 的 yosys 与本机同为 0.33"（runner 已是 0.52，10-13 的 CI 数字与本机同版本是当时成立）；⑤ "P=4 GMP 要 1–3 h"——hier 下 runner 10 min（DDR P=4 最慢 24 min）；⑥ "P=2/4 面积 ≈ P×A(P=1)" 现在有实测，误差 ≤3 %。
- 测试：`python -m pytest` 143 passed / 5 skipped（9 min 32 s）；ruff 绿。CI dispatch run 26 在 81b31fc 上跑 `synth-long`。
- 下一步：P=1 达 640 要关键路径 ≤ ~1409 ps，即乘法器本身拆两拍（ROADMAP，可选）；CI yosys 版本漂移（ROADMAP）；Verilator issue 待用户手提。

## 2026-11-03 · 里程碑 2 完成：Halo 余 4 个模块进脚手架；抓到 Verilator 5.020 一个常量折叠 bug

- **4 个 IP**（Halo@6e79c4a 一字不改，`check: tb`、`source: committed`，锁哈希）：`halo_adc_dsp_loop` 5 集各 n=3000（iverilog 5/5 PASS）、`halo_sliding_mlsd` n=4000、`halo_viterbi_mlsd` n=3000、`halo_dfse_mlsd` n=3000（后三者两仿真器 PASS，verilator 仿真本身 0.1 s）。
  `vendor_check --strict` 22 verbatim；mutation（各 IP 第一个集改一行 `*_pi/*_dec.txt`）→ FAIL + rc≠0 + LOCK。
- **dfse 向量**：Halo 没提交，用 `PYTHONPATH=<halo>/src HALO_NO_JIT=1 python3 rtl/gen_vectors.py <out>`（需 `pip install scikit-rf matplotlib`）在 pin 上生成（N=3000, NS=4, K=1, T=2）；
  同一次重生成的 ffe/loop/mlsd/vit 文件与 Halo 提交集逐字节一致——提交集只缺 dfse，其余不是陈旧快照。
- **Verilator 5.020 bug**：loop 的 delta/pr/pr4/pre 在 verilator 下 `LOOP LOCKSTEP FAIL errors=1` 而打印值相等（`offset 0/0 gain 16384/16384`），cal 集过。
  14 个 tb 改写变体二分：括号/`!=`/拆条件/临时变量都不行，**只有把移位量 `LANE_SHIFT`（`localparam longint`）换成字面量才过**。20 行独立复现：`a=16<<<14; a >>> SH_longint` → 0（`int` 移位量、逻辑 `>>`、非常量 `a` 都对 16384）；iverilog 全对。
  结论：常量折叠把 64 位移位量当成 ≥ 位宽处理；`CAL_ON=0` 时 `cgsum` 是传播常量所以中招，cal 集 `cgsum` 活着所以过。
- **处理**：`ip.yaml` 加 `sims:`/`sims_reason`（`halo_adc_dsp_loop: [iverilog]`），lockstep `[SKIP ]`、pytest skip + 要求另一仿真器在、`tests/test_sim_quirks.py` 在 bug 修好时变红；tb 不改（铁律 3）；`docs/upstream-findings.md` 新节；追加到 Halo_Serdes#136。
- **事故：试点提交 90a2cc5 的 CI run 18/19 `lockstep` 红**（其余 6 job 绿）——`.gitignore` 的 `ip/*/vectors/*` 把 `source: committed` 的 Halo 向量集也吞了，试点只推了锁文件没推向量，runner 上 `LOCK`。
  本地没发现是因为文件就在工作区。修复：`.gitignore` 加 `!ip/halo_*/vectors/*`；新守卫 `test_vectors_lock.py::test_committed_sets_are_tracked`（锁里每个文件必须 `git ls-files` 可见）。
- **被推翻的判断**：⓪ "试点 CI 已绿"（LOG 11-02 写的 7/7 是 run 15/16/17，试点 commit 自己的 run 18 红了，当时没等它跑完就记了）；① "`!==` 与 `||` 的求值顺序/位宽是 Verilator 的问题"（操作符无关，是常量折叠）；② "只有 lane 0 失败说明是循环首次迭代问题"（独立复现无循环也失败，lane 0 是因为 `errors` 后面没再变）。
- 测试：`python -m pytest` 137 passed / 5 skipped（14 min 39 s；skip = loop 5 集 × verilator）；ruff 绿；`render_tables --check` 一致。
- GitHub 默认分支已改为 `main`（用户在 Settings 里改的，`git ls-remote --symref origin HEAD` 确认）；CI run 20：6/7 绿（lockstep 16 min 含 mutation），synth 跑中。
- 下一步：里程碑 2 结束；等上游回应；候选：Verilator 报 bug、ROADMAP 里程碑 1 收尾项。

## 2026-11-02 · CI 7/7 绿；建 main；上游 issue 已提；里程碑 2 试点 halo_ffe_dfe 两仿真器绿

- **CI run 15 全绿**：lint / test×2 / lockstep 10 min / vendor-drift 50 s / fixed-vs-float 2.6 min / **synth 36 min**（hier，DDR+GMP P=1 都在 runner 上跑完）。
- **main**：`git push origin ccr-7ab6764e-mhc0mx:main`，与开发分支同一 commit；GitHub 默认分支仍是开发分支，改默认要在仓库 Settings → Branches 里做（MCP 无此工具）。
- **上游 issue**：PA_DPD#2（不 bit-true 4 点 + 非因果 + 2 处文档小错，附 `DpdPolyConfig.derive`）、Halo_Serdes#136（`$fscanf`、缺 `dfse_*`、写被跟踪目录 + Icarus O(N²) 观察）。
- **里程碑 2 试点 `ip/halo_ffe_dfe`**：Halo@6e79c4a `ffe_dfe_datapath.sv` + `tb_ffe_dfe.sv` 一字不改（`// Vendored from` 头，`vendor_check --strict` 14 verbatim），
  向量 `source: committed`（Halo 提交集 2000 码 / 1985 输出，锁哈希），`check: tb`：iverilog 1.2 s、verilator 7.3 s 均 `LOCKSTEP PASS n=1985`；mutation（改 `dec.txt` 一行）→ `LOCKSTEP FAIL` + `$fatal` rc≠0，锁也抓到。
- **被推翻的判断**：`_strip_header` 剥掉所有前导注释行——上游 `.sv` 自己的头注释被剥掉后 verbatim 判成 DRIFT；改为只剥 `Vendored/Extracted from` + `Adapted-copy policy` 行。
- 脚手架三条路径（`check: python`、`check: tb`、`source: committed`）现在都有真实 IP 走过。
- 下一步：余 4 个 Halo 模块按同一模板（`adc_dsp_loop` 5 个向量目录、`sliding/viterbi`、`dfse` 要先生成向量）；默认分支改 main；等上游回应。

## 2026-11-02 · 体检：本地全绿，CI 自 10-13 起因 YAML 一个冒号静默失败 8 次，已修

- **本地**：`python -m pytest` 109 passed（11 min 50 s，含两仿真器全部 lockstep）；ruff 绿；`vendor_check --strict` 12 verbatim 无漂移；
  `check_upstream_export` 重新导出一致（53 s）；`render_tables --check` 一致；指纹对 10-13 的记录 92 值逐位不变；工具链/liberty/torch/sibling 克隆都在。
- **CI 事故**：`d673f02` 起 step name `Synthesize (hier mode: real term count, ...)` 未加引号，YAML 非法 → run 7–14 全部"0 job 即失败"，GitHub 把 workflow 名显示成文件路径就是信号。
  修复 `5068ff9`；run 15：lint / test×2 / lockstep（10 min）/ vendor-drift（50 s）/ fixed-vs-float（2.6 min）绿，`synth`（hier，预计 ~1 h）跑中。
  **教训**：CI 红要看 job 数，0 job 的"failure"是配置错不是测试错；本地加一条 `yaml.safe_load(ci.yml)` 测试（已记 ROADMAP 小项）。
- **上游漂移**：PA_DPD 08b9725→6241112（7 commits，全是 GUI，vendored 文件无变化）；Halo 6e79c4a→34c3d8d（282 commits，`rtl/` 无变化）；OpenDPD、polar_tx 也前进。pin 不需要动。
- **仓库结构**：GitHub 默认分支就是 `ccr-7ab6764e-mhc0mx`（没有 main）；15 个 commit 全在上面。
- 下一步：等 synth job 结束确认 7/7；建 `main`（或把默认分支改名）；推回上游 issue；里程碑 2 试点。

## 2026-10-14 · 收尾：综合口径定为分层 + `&nf -D 1000`，两种基函数都按 P=2 达 640 MSPS（估计）

- **RTL 改动**：`dpd_term` 双因子级拆两级（TERM_LAT 5）、累加树每级打拍（ACC_LAT clog2(N)+1）；lockstep 两仿真器 × 18 点仍全 0 不匹配。
- **综合口径三次更换的原值**（同一 RTL，NanGate45，无线载，ps）：旧 `map` 分模块 DDR 1278 / GMP 1751；`dch; map -D 1000` 分模块 DDR 1339 / GMP 1969；
  `&nf -D 1000`（yosys 自带流程）分模块 DDR 1837 / GMP 1883。打平预算子集（旧 map）DDR 1783。差距来自 ABC 对 40 位行波进位加法器的平衡好坏，不是逻辑级数。
- **定稿数字**（`&nf -D 1000`，真实项数，`results/synth/*__hier.json`）：DDR W16 P=1 1837 ps + DFF 154 → f_est 502 MHz，1.90 mm²，1.50 M cells（36 min）；
  GMP W16 P=1 1883 ps → 491 MHz，3.34 mm²，2.65 M cells（17 min）。**结论：两种基函数都需 P=2 才达 640 MSPS（≈1000 MSPS，estimate，见 `docs/results.md`）；P=1 只在乐观映射下成立。映射噪声 ±25 %。**
- **被推翻的判断**：① "再切一级流水 DDR 就能 P=1"——瓶颈在加法器映射；② "预算模式外推与全项数一致"——面积差 +10 %、延迟差 ±40 %；③ "`dch`+`map -D` 能稳定延迟"——GMP 顶层仍 1969。
- **过程事故**：P=4 打平在 ~9 GB OOM → 分层模式解决；一条以为已杀掉的旧综合链还在跑并写同名文件（已清）；容器重启一次，分离的综合链随之死亡（已用 `setsid nohup` 可续跑方式重启，P=2/4 点待补）。
- GitHub CI：6/7 job 绿（lockstep 13 min、fixed-vs-float 3 min、vendor-drift 35 s）；`synth` job 的 `--out` 目录 bug 已修。
- **P=2/4 不再综合，按构造说明**（用户决定）：容器空闲即回收，20–40 min 的综合点三次都没活过；P 份项阵列 + 树、共享窗口，吞吐 = f_est × P、面积 ≈ P × A(P=1)，`docs/results.md` 由 P=1 JSON 生成并标注 by construction（DDR P=2 ≈ 1004 MSPS、3.8 mm²；GMP P=2 ≈ 982 MSPS、6.7 mm²，estimate）。
- 下一步：ROADMAP"加法树的 40 位加法器"（并行前缀 `$lcu` techmap 或 CSA 树）；有长时间机器时补综合 P=2/4；里程碑 2。

## 2026-10-13 · 里程碑 1 完成：dpd_poly RTL 在两仿真器 × 5 向量集 × P=1/2/4 全部 0 不匹配

- **lockstep**：verilator 18/18（dpd_poly 15 + sat_shift 3），iverilog 18/18；ddr_r1/gmp510 × W16/W12 各 4096 样本，rand_w16 2048 样本（含 `n_sat_phi>0`、`n_sat_out>0`）。
  mutation：改一行金标 → FAIL 且报样本号与参考寄存器；锁文件也抓到（`LOCK`）。
- **定点对浮点**（`results/aclr_table.json`，DGRU 代理，ACLR_AVG dBc）：上游四个数用 vendored 代码复现 DDR −51.60/−51.25/−40.39/−29.42、GMP −50.16/−50.10/−46.57/−38.54，
  与 PA_DPD 文档最大差 0.05；本库整数参考 W16 −51.26（DDR）/ −50.09（GMP），差 ≤ 0.04；W12 −40.44/−46.46，W10 −29.66/−38.56；`w_pw=W+4` 时 W10 DDR −29.49、W12 GMP −46.57。
  NMSE 整数参考 vs 上游浮点：−59.6/−69.6 dB（W16），−35.6/−45.8（W12）。
- **综合估计**（yosys 0.33 + NanGate45 typical，预算模式 N_TERMS=14/28，ABC fast map，无线载）：DDR W16 P=1 关键路径 1948 ps + DFF 154 ps → f_est 476 MHz → **P=2 达 640 MSPS**；
  面积外推 1.86 mm²、1.64 M cells；559 s。GMP W16 P=1：1306 ps → f_est 685 MHz → **P=1 即达 640 MSPS**，面积外推 4.04 mm²（DDR 更慢是因为双因子项那一级：乘 + sat_shift 同级）。P=2：DDR 2180 ps → 428 MHz（857 MSPS），GMP 1461 ps → 619 MHz（1238 MSPS）；关键路径随 P 变长（无线载下只剩扇出电容）。P=4 用 28/32 项时 ABC 在 ~9 GB 被 OOM 杀掉，改 7/8 项重跑：DDR 1838 ps → 502 MHz（2008 MSPS，面积外推 8.85 mm²），GMP 1726 ps → 532 MHz（2127 MSPS，10.8 mm²）。**结论**：DDR W16 需 P=2（857 MSPS），GMP W16 P=1 即 685 MSPS；按各 P 点最差 f_est 保守算都是 P=2（`docs/results.md`）。单项 `dpd_term`（双因子）1294 ps、16.8 k µm²。
- **被推翻的判断**：① 上游 refvec 可当金标（否，浮点模拟）；② `a^k` 精确整数（W16 要 79 位）；③ `q_pair=W_PW` 固定（清零小包络，NMSE −59.6→−41.8）；
  ④ 每相位各自延迟线（改扁平窗）；⑤ 用 packed 总线汇总 N 项（Icarus O(N²)，0.9 s/样本 → 每节点一根线后 0.002 s/样本）；⑥ yosys 能读 `pkg::param` 端口（0.33 不能，dims 分两份 include）。
- **上游导出**：本地两遍字节一致；`tools/check_upstream_export.py` 重新导出比对 OK（68 s）。
- 测试：`python -m pytest` 108 passed / 1 skipped（含真 lockstep，9 min）；工具链 verilator 5.020 / iverilog 12 / yosys 0.33。
- 下一步：ROADMAP 里程碑 1 收尾三项（full 综合、关键路径流水、F/w_pw 扫描入表）；里程碑 2 Halo 5 模块 vendor。

## 2026-10-13 · 开库：上游"bit-true 参考向量"不能直接当金标，本库自定整数参考

- 探索 PA_DPD@08b9725：`FixedPointPolyModel` 是浮点模拟的量化（块峰值现算 scale 且未导出、float64 算 `|x|^k`、float64 累加、输出不量化、`refvec.csv` 是 `%.10e` 浮点）。
  **被推翻的判断**：prompt 假设 `export_deploy.py` 出的参考向量可直接逐样本比对——不行。决定：本库写整数参考（`ref.py`）为真值，上游只供输入 + 整数系数 JSON；差异写文档、问题推回 PA_DPD。
- 探索 Halo_Serdes@6e79c4a（prompt 写 95e2d12，上游已前进）：模块无端口、tb 层次引用、`$fscanf` 读 `.txt`、比对在 tb 内、只用 iverilog；mutation 测试改一行金标断言 FAIL。里程碑 2 要 `check: tb` + `source: committed`。
- 工具链：环境里三件都没有；`archive.ubuntu.com` 可达，apt 装上 verilator 5.020 / iverilog 12 / yosys 0.33。GitHub release tarball 403，公开仓库 git clone 可用（OpenDPD、sky130、ORFS 已验证）。
- 上游导出：OpenDPD@a362a8d `datasets/DPA_160MHz`（fs 640 MHz，4 载波 40 MHz，nperseg 16384）+ PA_DPD 导出 W16/W12，本地两遍字节一致（8 个文件 sha256 见 `EXPORT.md`）；DDR 系数 scale 2^-11（W16）/ 2^-7（W12）。
- 下一步：阶段 1 整数参考 + 定点对浮点（复现 −51.3/−40.4/−50.1/−46.6 需 torch + DGRU checkpoint）。
