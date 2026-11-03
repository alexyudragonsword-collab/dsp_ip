# CHANGELOG（按里程碑）

## 里程碑 1 收尾：乘法级重分级、综合看得见瓶颈、P=1/2/4 真实综合进 CI、脚手架收尾（2026-11-03）

### 变更
- **RTL 重分级（逐位不变，lockstep 两仿真器 × 15 点仍 0 不匹配）**：`dpd_pow` 不再有宽于 W×W 的乘法器——a²=h·2^W+l，a³=(h·a)<<W+l·a、a⁴=(h·h)<<2W+(h·l)<<(W+1)+l·l，五个 W×W 积一级、重组加法一级（LATENCY 3→4）；
  `dpd_env` 平方与相加拆两级（W_ENV+1→W_ENV+2）；`dpd_term` 复乘的四个积与加减拆两级（TERM_LAT 5→6）。单模块探针（NanGate45，ps）：pow 1762→1515、env 1789→1337、term 1949→1488/1511。
- `tools/synth.py`：hier JSON 带 `modules`（每个模块最差 ABC 延迟 + 参数化实例数），`docs/results.md` 多一张"每模块延迟"表；新 `--mode unit --module <m> [--param K=V]` 单叶模块秒级探针，写到 `results/synth/units/`，不进表。
- CI 新 job **`synth-long`**（`workflow_dispatch`，矩阵 2 基 × P∈{1,2,4}，每 runner 6 h 上限，JSON 打印到日志 + artifact）；`tests/test_ci_yaml.py` 跟着改。
- `tools/lockstep.py`：每个 IP 一把 `flock`（`vectors/.lockstep.lock`，跨进程也跨线程），生成、换入、改锁文件、校验都在锁内；生成先写临时目录，内容与活目录相同就丢弃（不碰正在被仿真器读的目录）；`vectors.save_lock` 原子写。4 线程并发测试 + 3 进程实测。
- `examples/01_bitwidth_aclr.py --w-pw-plus 0 4 8 --env-frac 0 2`：`floatref.sweep_variants` 生成变体网格，`build_aclr_table(variants=)`；`results/aclr_table.json` 扩到 6 个变体。
- `docs/synthesis.md` 改写 Flow（hier + `&nf`）、模式说明、P=1/2/4 一节；`docs/verilator-issue-draft.md`（本会话无 verilator/verilator 写权限，待用户手提）。

### 被推翻的判断
- "40 位行波进位加法器是关键路径"：yosys 0.33 的 `$alu→$lcu` 本来就是 Brent-Kung 前缀网络；加法树（顶层）1441 ps 有 ~400 ps 余量，关键路径是 `dpd_pow` 的 32×32 乘（1837/1883 ps），其次 `dpd_env` 1789、`dpd_term` 1734。
- "a⁴ 用 a³·a（48×16）比 32×32 浅"：单模块探针 1988 ps 反而比 1762 差；两个 32×16 半积 1934、两个 48×8 半积 2283 也不行；只有全部拆成 W×W 积（1494）有效。

## 里程碑 2 完成 — Halo_Serdes 五个模块全部进脚手架（2026-11-03）

- **IP `halo_adc_dsp_loop` / `halo_sliding_mlsd` / `halo_viterbi_mlsd` / `halo_dfse_mlsd`**：Halo@6e79c4a 的 `.sv` + `tb_*.sv` 一字不改 vendor（`vendor_check --strict` 22 verbatim），
  `check: tb`、`source: committed`；loop 用 Halo 的 5 个向量目录（`delta pr pr4 pre cal`），mlsd/vit 用 Halo 提交集，dfse 的向量 Halo 没提交，本库在 pin 上用上游 `gen_vectors.py` 生成一次（命令在 `SOURCE.md`）。
  iverilog 全绿（loop 5/5、mlsd、vit、dfse）；verilator mlsd/vit/dfse 绿。
- **`ip.yaml` 新字段 `sims:`（+ `sims_reason`）**：把一个 IP 限制到某个仿真器，只允许用于有探针证明的仿真器 bug；`lockstep.py` 打 `[SKIP ]`、单 IP `auto` 选该 IP 允许的仿真器、
  `test_rtl_lockstep` 跳过并要求另一个仿真器在；`tests/test_sim_quirks.py` 在 bug 修好那天变红提醒去掉限制。
- **发现 Verilator 5.020 bug**：`longint >>> <longint localparam>` 被常量折叠成 0（`tools/quirks/verilator_longint_shift.sv`，`docs/upstream-findings.md`）；
  Halo `tb_adc_dsp_loop` 的终值校准比对在 `CAL_ON=0` 的 4 个集上因此误报。`halo_adc_dsp_loop` 标 `sims: [iverilog]`，tb 不改，已追加到 Halo_Serdes#136。
- 重新生成的 ffe/loop/mlsd/vit 向量与 Halo 提交集逐字节一致（提交集只缺 dfse）。
- **修复**：`.gitignore` 曾把 `source: committed` 的向量集和生成集一起忽略，试点 commit 只推了锁没推向量（CI run 18 `lockstep` 红）；现在 `!ip/halo_*/vectors/*` 再纳入，`test_committed_sets_are_tracked` 守着。

## 里程碑 2 试点 + 对外动作（2026-11-02）

- **IP `halo_ffe_dfe`**：Halo_Serdes@6e79c4a 的 `ffe_dfe_datapath.sv` + `tb_ffe_dfe.sv` 一字不改 vendor（`// Vendored from` 头），向量 `source: committed`（Halo 已提交集，锁哈希），`check: tb`（`LOCKSTEP PASS` + `$fatal`）；两仿真器绿；mutation 测试扩到自检 tb（`ip.yaml: mutation_file`）。
- `tools/vendor_check.py`：只剥离署名头行，保留上游 `.sv` 自己的头注释（否则 verbatim 被判 DRIFT）；`lockstep.py` 从自检 tb 的 PASS 行解析 `n=`。
- CI：修掉自 10-13 起让 workflow 无法解析的一个未加引号的 step name（run 7–14 静默失败）；run 15 **7/7 绿**（synth hier job 36 min）。
- 建 `main` 分支（与开发分支同一 commit）；上游 issue：PA_DPD#2、Halo_Serdes#136。

## 里程碑 1 之后的收尾（2026-10-13）

### 变更
- `dpd_term`：双因子包络级拆成"乘 → 寄存 → 舍入饱和"两级（TERM_LAT 4→5）；累加树每级都打拍（ACC_LAT = clog2(N)+1）。全部 36 个 lockstep 点（两仿真器 × 18）仍 0 不匹配。
- `tools/synth.py --mode hier`：保留 `dpd_term/env/pow/acc` 层次（`sat_shift` 打平进父模块），ABC 逐模块映射——真实项数可在本机跑完（DDR 140 项 ~4 min），不再外推；`--mode full` 打平在 ~9 GB 被 OOM。
- ABC 流程改为 yosys 自带的 `&nf -D 1000`（`--legacy-map` 保留旧 `map` 对比）：旧 `map` 的延迟随网表规模摆动 ±40 %。
- CI `synth` job 改跑 hier 模式；`synth.py --out` 自动建目录（CI 曾因此红）。

### 被推翻的判断
- "预算模式（子集打平 + 线性外推）给的频率与全项数一致"：同一 RTL 打平 1783 ps、分模块 1278 ps；结论改用 hier + `&nf`。
- "累加树两级加法一拍没问题"：GMP 顶层 167 k 门的树在旧 `map` 下映成 29 门 1969 ps 路径；每级打拍后仍要靠 `&nf` 才降到 1441 ps——瓶颈是行波进位加法器的映射，不是级数。

## 里程碑 1 — `dpd_poly` 定点 DPD 数据通路 + 通用 lockstep 脚手架（2026-10-13）

### 新增
- **脚手架**：`ip/<name>/ip.yaml` 契约（`src/dspip/ipspec.py`）、`tools/lockstep.py`（verilator / iverilog，逐行比对，报第一个不匹配样本 + 参考寄存器，`--all`、`--update-lock`）、
  `src/dspip/vectors.py`（`.txt` 向量 + sha256 锁）、`tools/fingerprint.py`（Adapted from Halo_Serdes@6e79c4a）、`tools/vendor_check.py`（同上，加 `//` 头与 `.sv`）。
- **IP `sat_shift`**：舍入右移 + 饱和（dpd_poly 的输出级），3 个向量集。
- **IP `dpd_poly`**：DDR r=1（140 项）/ GMP-510（255 项）× W16/W12/W10，P 样本/拍。Python 整数参考（纯 int 真值 + int64 向量化孪生）、
  `DpdPolyConfig`（位宽/scale/移位全由上游导出推导，发 `dims_params.svh`/`dims.svh`）、RTL `dpd_env/dpd_pow/dpd_term/dpd_acc/dpd_poly.sv` + tb。
  lockstep：5 个向量集 × P=1/2/4 × 两个仿真器全部 0 不匹配。
- **上游导出入库**：PA_DPD@08b9725 对 OpenDPD@a362a8d `DPA_160MHz` 的 DDR/GMP × W16/W12 系数 JSON + 输入 CSV（`EXPORT.md`，锁在 `vectors.lock.json`）；
  `tools/check_upstream_export.py` 重新导出比对（输入/配置精确，系数码 ±1 LSB）。
- **定点对浮点**：`floatref.py` + `examples/01_bitwidth_aclr.py` → `results/aclr_table.json`；上游四个 ACLR 数复现（最大差 0.05 dB），整数参考 W16 与文档差 ≤ 0.04 dB。
- **综合估计**：`tools/get_liberty.sh`（NanGate45 pin SHA + sha256）、`tools/synth.py`（yosys + ABC stime，预算/完整模式，`kind: estimate`）、
  `examples/02_parallelism_synth.py`、`tools/render_tables.py` → `docs/results.md`。
- 文档：`docs/synthesis.md`（口径）、`docs/upstream-findings.md`（推回上游）、`cairn/dpd_poly定点通路.md`。
- CI：`lint`、`test`（py3.11/3.12）、`lockstep`（两仿真器 + mutation）、`synth`（artifact）、`vendor-drift`（`--strict` + 重新导出）、`fixed-vs-float`（torch cpu）。

### 被推翻的判断
- "上游 `refvec.csv` 可直接当 RTL 金标"：上游是浮点模拟，本库自定整数参考（见 `cairn/dpd_poly定点通路.md` §1）。
- "`a^k` 精确整数"：W16 要 79 位，改为幂预移位到 W_PW 位。
- "双因子乘积固定右移 W_PW"：会清零小包络（DDR NMSE −59.6 → −41.8 dB），改为按每项上界算 `q_pair`。
- "每相位各自延迟线"：改为一个扁平历史窗 + 静态抽头。
- "用 packed 总线汇总 N 项输出"：Icarus O(N²)（0.9 s/样本），改为每节点一根线 + 层次引用（0.002 s/样本）。

### 阶段 0（2026-10-13）
- 仓库骨架、Cairn 文档、vendor 12 个 PA_DPD 文件 verbatim、工具链 verilator 5.020 / iverilog 12 / yosys 0.33（apt）。
