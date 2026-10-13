---
type: project_topic
status: current
summary: dpd_poly 整数数据通路的数值定义、位宽/scale 推导、与 PA_DPD 浮点模型的差异、被推翻的判断
tags: [dpd, fixed-point, lockstep]
contains: [数值定义, 位宽配置, 上游差异, 仿真器坑, 综合口径]
created: 2026-10-13
updated: 2026-10-13
related: [docs/synthesis.md, docs/upstream-findings.md, docs/results.md]
---

# dpd_poly 定点通路（当前真相）

代码事实优先：`src/dspip/ip/dpd_poly/{config,datapath,ref}.py` 是定义，`ip/dpd_poly/rtl/*.sv` 逐位等于它（`tools/lockstep.py dpd_poly`）。本文解释"为什么这样定"。

## 1. 为什么本库自定整数参考（被推翻的判断 #1）

prompt 假设 PA_DPD `export_deploy.py` 出的"bit-true 参考向量"可直接当 RTL 金标。探索发现 `FixedPointPolyModel` 是浮点模拟：
输入/每列 scale 按数据块峰值现算且未导出；`|x|^k` 在 float64 里算（W16 的 `x·|x|^4` 有效位 ≈ 80 > 53）；累加是 float64 matmul；
输出不量化；CSV 是 `%.10e` 浮点。**RTL 不可能逐位等于它**。决定：上游只供输入块 + 整数系数 JSON（pin SHA），本库的整数参考是真值，
与上游浮点模型的差用 NMSE/ACLR 量化并写进 `docs/results.md`；问题推回 PA_DPD（`docs/upstream-findings.md`）。

## 2. 数值定义（value = int · 2^exp；config 用 (int, exp) 追踪每个中间量）

| 量 | 定义 | exp |
|---|---|---|
| x code | `round_half_even(x / 2^e_in)` sat W_IN；`e_in = ceil(log2(peak/qmax))`，peak 取校准块（上游规则） | e_in |
| a | `isqrt((I²+Q²) << 2F)`（截断）| e_in − F |
| pw_k | `sat_u(W_PW, rshift_round(a^k, q_k))`，`q_k = bitlen(a_max^k) − W_PW`（a_max 为满幅码对的包络）| k(e_in−F) + q_k |
| envp（双因子）| `sat_u(W_PW, rshift_round(pw_k0·pw_k1, q_pair))`，**q_pair 按每项的乘积上界算**（见 §5）| 两者之和 + q_pair |
| phi_c | `x · envp` | e_in + exp(envp) |
| code_phi_c | `sat(W_PHI, rshift_round(phi_c, s_c))`，`e_c` 用上游 `_pow2_step` 规则在整数路径的浮点值上算，`s_c = e_c − exp(phi_c)`，`s_c<0` 钳 0 | e_c |
| prod_c | `code_w · code_phi`（4 实乘）| e_w + e_c |
| acc | `Σ prod_c << (e_c − e_min)` | e_w + e_min |
| y | `sat(W_OUT, rshift_round(acc, S_OUT))`，`S_OUT = e_out − e_w − e_min`，`e_out = e_in` | e_in |

舍入：数据通路内一律 half-up（Halo `rshift_round`，`+2^(s−1)` 再 `>>>`）；只有离线输入量化是 half-even（与上游 `np.round` 同）。
边界：历史窗复位为 0 = 上游零填充；GMP 超前项（`a(n+1)`）靠整体延后 LEAD=1 个样本，tb 多送 1 个零样本、丢掉前 1 个输出。
P 并行：一个扁平历史窗每拍移 P，lane p / 项 c 的抽头是静态索引 `(P−1−p)+idx`，P=1/2/4 逐位等于同一金标（已验证）。

实测 scale（DPA_160MHz，信号归一化峰值 ≈ 1）：W16 `e_in=−15`，DDR `e_w=−11`、GMP `e_w=−13`；每列 `e_c ∈ {−16,−15}`，对齐 ≤ 1 位；W_ACC=40（W16）/32（W12）；S_OUT=12/13。

## 3. 位宽是配置（铁律 2）

`DpdPolyConfig.derive(coeffs, x_cal, w_in, w_coef, w_phi, w_pw, w_out, env_frac, in_headroom, out_headroom)`；改任一项，`dims_params.svh` / `dims.svh` 跟着变（测试 `test_bitwidth_is_config`）。
int64 向量化参考在 `a_max^k` 或 `W_ACC` 超 63 位时拒跑（`check_int64`），纯 int 参考无限制。

## 4. 定点对浮点（数字原值见 `results/aclr_table.json` / `docs/results.md`）

- 上游四个数用 vendored 上游代码复现：DDR −51.60/−51.25/−40.39/−29.42，GMP −50.16/−50.10/−46.57/−38.54（文档 −51.6/−51.3/−40.4/−29.4、−50.2/−50.1/−46.6/−38.5），最大差 0.05 dB。
- 本库整数参考（默认 W_PW=W）：DDR W16 −51.26、W12 −40.44、W10 −29.66；GMP W16 −50.09、W12 −46.46、W10 −38.56。
  W16 与文档差 ≤ 0.04 dB（验收 ≤ 0.1 满足）；W10 DDR 差 0.26 dB、W12 GMP 差 0.14 dB——**幂字宽 W_PW = W+4 就回到 ≤ 0.1 dB**（−29.49 / −46.57），这是配置项。
- NMSE（整数参考 vs 上游浮点模型，4096 样本块）：W16 −59.6（DDR）/ −69.6（GMP）dB；W12 −35.6 / −45.8 dB。

## 5. 被推翻的判断 #2：`q_pair = W_PW`

初版两因子乘积固定右移 W_PW 位。`pw_1` 只占 16 位（q_1 = 0），W_PW=24 时乘积 >> 24 把小包络样本清零，DDR W16 NMSE 从 −59.6 恶化到 −41.8 dB。
改为按每项乘积上界 `bitlen(pw_k0,max · pw_k1,max) − W_PW` 算（`datapath.pair_shift`，dims `T_QP`），W_PW 增大后单调变好（−63.0 dB）。

## 6. 仿真器坑（铁律 4 的实现代价）

- **Icarus 对宽总线多驱动是 O(N²)**：把 N 项输出拼成一个 packed 总线（N 个 part-select 驱动）或用 unpacked 数组，每个驱动变化都重解析整条总线；
  140 项时 0.9 s/样本（4096 样本要 1 小时）。改成**每个节点一根线 + generate 层次引用**（`T[c].p_re`、`L[l-1].gi[2i].s`）后 0.002 s/样本（256 样本 0.58 s）。verilator 不受影响。
- yosys 0.33：端口列表里不能用 `pkg::param`，也不读 unpacked 数组 localparam；所以 dims 分两份——`dims_params.svh` 在 `#( ... )` 里 `include`，`dims.svh`（packed 表）在模块体里 `include`。
- verilator 把以 `verilator` 开头的注释当指令（`// verilator ...`）：注释里写命令行要加 `$ `。
- 不要同时跑两个 lockstep sweep：`ensure_vectors` 会删除并重生成向量目录，并发时另一个进程读到一半（本轮 iverilog sweep 3 个 ERROR 即此，单独重跑全 PASS）。

## 7. 综合口径

见 `docs/synthesis.md`。预算模式（N_TERMS=14/28，NanGate45，ABC fast map）：DDR W16 P=1 关键路径 1948 ps + DFF 154 ps → f_est 476 MHz → **P=2 达 640 MSPS**；面积外推 1.86 mm²。其余点见 `docs/results.md`。
