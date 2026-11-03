# LOG（新条目在顶部；每条 ≤ 20 行：摘要 + 数字原值 + 被推翻的判断 + 下一步）

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
