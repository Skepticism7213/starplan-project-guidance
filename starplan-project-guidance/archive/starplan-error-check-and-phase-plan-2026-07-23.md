# StarPlan Loop 错误排查报告与阶段安排

日期：2026-07-23
项目起始：2026-07-18 ｜ 截止：2026-09-01 ｜ 当前进度：第 3 周核心 + 星表科学校验已完成（领先原计划约 1 周）
本报告依据 AGENTS.md「强制收尾报告」规则生成，覆盖 2026-07-23 的星表科学验证与数据纠错工作（提交 `fe580d0`、`0f0e4d2`、`0741303`、`6ba3f2d`，该批工作当时未附收尾报告，本次补齐）。

---

## 一、本轮错误排查结论

本轮工作分两部分：(1) 团队对内置目标目录做了 SIMBAD 权威交叉校验与数据纠错；(2) 合并到主环境后做了一次独立的静态 + 运行时复验。

### 1.1 星表数据纠错（团队完成，已修复）

用 astroquery 把全部 150 个目标与 SIMBAD（CDS 权威星表）逐一比对，发现并修复：

| 严重级 | 数量 | 内容 | 状态 |
|---|---|---|---|
| CRITICAL | 29 | 坐标偏差 > 6 角分，最严重 M23 偏 4.37° | ✅ 已替换为 SIMBAD 值 |
| WARNING | 23 | 坐标偏差 0.6~6 角分 | ✅ 已替换为 SIMBAD 值 |
| CRITICAL | 9 | 星座名与 IAU 标准不一致（Ophiuchus→Ophiucus 等） | ✅ 已对齐 Astropy IAU |
| WARNING | 1 | M40 缺角大小 | ✅ 补 [0.9, 0.9] |
| WARNING | 1 | M17 视星等 7.0→6.0（按 NASA Hubble 星表） | ✅ 已修正 |
| INFO | 4 | 删除 4 个不科学别名；补充中文别名变体 | ✅ 已处理 |

修正后 149/150 目标坐标溯源至 SIMBAD（精确到 ~0.36 角秒）。详见 `数据验证日志/catalog_validation_log_round1.md` 与 `round2.md`。

### 1.2 合并后独立复验（本次完成）

| 检查项 | 结果 |
|---|---|
| 全部 .py 编译（starplan_skills + scripts + tests） | ✅ 通过 |
| 案例 1（M31 正常） | ✅ 可观测，推荐 18:58~04:28，坐标为校正值 Dec=41.2688 |
| 案例 2（M42 不可观测） | ✅ 正确判不可观测，RA=83.8201 |
| 案例 3（M31 复盘） | ✅ 识别 3 类偏差，11 个输出文件 |
| layer1 验证（本地，10 轮 × 4 项） | ✅ 0 问题 |
| 幻觉防护单元测试 | ✅ 8/8 通过 |
| 坐标抽查（M23/M31/M58/M42 vs SIMBAD） | ✅ 全部精确吻合 |
| layer23 验证（SIMBAD 交叉比对） | ⚠️ 无法运行（见 WARNING-1） |

**结论：0 个新增 CRITICAL，1 个 WARNING（可复现性缺口），3 个 INFO。3 个案例重新运行均无错误，数据纠错未引入回归。**

### WARNING 级问题

| # | 问题 | 文件 | 状态 |
|---|---|---|---|
| 1 | `layer23_validation.py` 只读取本地中间文件 `simbad_query_results.json` / `simbad_dim_otype.json`，这两个文件未提交进仓库，脚本也无联网重查模式 → 任何人 clone 后都无法复跑 SIMBAD 交叉验证 | tests/layer23_validation.py + data/ | 待修复：提交中间数据，或给脚本加联网重查模式 |
| 2 | 复盘案例未单独导出 `observation_log.csv`（沿用上轮 WARNING，仍未修） | runner.py / observation_review.py | 待修复 |
| 3 | 真实 Qwen 集成测试 `tests/test_qwen_integration.py` 仍缺（沿用上轮 WARNING） | tests/ | 待修复 |

### INFO 级项

- 本轮星表校验工作不在原 6 周计划的显式任务里，属主动加固，直接强化「科学价值（40%）」与「可复现」评分项。
- 第二轮日志中 26 条角大小"警告"经核实为 SIMBAD 与 SEDS 测量定义不同（半光半径 vs D25 等相线直径），非数据错误，保留原值。
- 第二轮坐标比对有 30 个目标因 SIMBAD 接口限流未直查到，但第一轮已覆盖全部 150 个，两轮合计全覆盖。
- 本地无 `DASHSCOPE_API_KEY` 时科普包自动回退模板模式（输出标注 `[template]`），属预期降级。

### 复现命令

```bash
cd StarPlan
# 填入 .env 的 DASHSCOPE_API_KEY 后可跑 Qwen 模式；不填则走模板模式
python scripts/run_case.py examples/case_01_m31_jinan.json
python scripts/run_case.py examples/case_02_unfavorable_window.json
python scripts/run_case.py examples/case_03_observation_review.json
python tests/layer1_validation.py            # 本地，无需联网
python tests/test_hallucination_protection.py
python tests/layer23_validation.py           # 需 data/simbad_*.json（当前未提交，见 WARNING-1）
```

---

## 二、当前完成度对照项目计划

| 计划阶段 | 计划目标 | 实际状态 |
|---|---|---|
| 第 1 周 | 冻结范围、Schema、案例、验证规则 | ✅ 已完成 |
| 第 2 周 | 跑通目标解析 + 本地可观测性计算 | ✅ 已完成 |
| 第 3 周 | 接入 Qwen 编排 + 科普活动包 | ✅ 已完成并真实验证（NL 解析 + Qwen 科普 + 幻觉防护 + 审计） |
| 第 4 周 | 观测日志 + 复盘闭环 | 🟡 规则版复盘已跑通，Qwen 辅助归因待接入 |
| 第 5 周 | 演示入口 + 3 类案例 | ⏳ 待开始（演示技术未定） |
| 第 6 周 | 打磨评测、报告、视频 | ⏳ 待开始 |
| （计划外） | 星表科学交叉校验 | ✅ 已超额完成（SIMBAD 全量校正 + 两轮验证日志 + 可复现脚本） |

**当前领先原计划约 1 周，且科学数据可信度已大幅加固。** 原计划第 6 周才做的"科学交叉校验"已提前完成，可直接作为提交材料里的科学准确性证据。

---

## 三、接下来几周的阶段安排

### 第 4 周（建议提前启动）：复盘闭环接入 Qwen + 补齐遗留 WARNING

核心任务：

1. **Qwen 辅助归因**：让 Qwen 基于观测日志备注做自然语言归因，每条结论必须引用计划/日志具体字段，保留 evidence_based / possible / undetermined 三级分类。
2. **修复 WARNING-1（可复现性）**：提交 `data/simbad_query_results.json` 与 `simbad_dim_otype.json`，或给 `layer23_validation.py` 加联网重查模式，确保 clone 后可复跑交叉验证。
3. **修复 WARNING-2**：复盘案例单独导出 `observation_log.csv`。
4. **修复 WARNING-3**：补 `tests/test_qwen_integration.py`。

阶段验收：复盘归因由 Qwen 辅助且可追溯证据；SIMBAD 交叉验证可在全新环境复跑；`observation_log.csv` 独立导出；集成测试存在并通过。

### 第 5 周：演示入口与案例固化

核心任务：

1. **轻量演示面板**：Streamlit 或 FastAPI（**待团队拍板**），展示输入、工具调用、中间结果、验证报告、复盘结果。
2. **一键复现**：固定命令跑通 3 案例并生成完整运行目录。
3. **失败场景完善**：名称歧义、地点缺失、整晚不可见、强月光、日志信息不足等都要有清楚失败原因。
4. **可解释推荐**：推荐窗口同时显示满足的约束、被淘汰时段及原因。
5. **科学校验入口**：把 layer1/layer23 验证脚本接入演示，作为"科学准确性"的现场证据。

阶段验收：新环境可复跑；失败场景可解释；评委能在有限时间内看懂；交叉验证可现场演示。

### 第 6 周：评测、报告与提交材料

核心任务：

1. **科学交叉校验整理**：把本轮 SIMBAD 校正记录、两轮验证日志整理进技术报告（已基本就绪）。
2. **对照实验**：传统人工流程 vs StarPlan 的时间、遗漏项、可复现性对比。
3. **真实校园小试验**（可选高收益）：组织 5-10 人小规模观测，记录反馈。
4. **提交材料**：PPT/PDF（≤20 页）、技术报告、源码、Skills 清单与流程图、3 类任务运行记录、10 分钟演示视频。

阶段验收：材料齐全；可复现；Qwen 边界与调用证据清楚；科学准确性证据完整。

---

## 四、风险提示

1. **可复现性缺口（WARNING-1）**：SIMBAD 交叉验证目前无法在全新环境复跑，这恰是答辩"可复现"和"科学价值"的关键证据，应优先修复。
2. **演示技术未定**：Streamlit vs FastAPI 需团队尽快拍板，否则影响第 5 周。
3. **时间压力下的范围控制**：闭环已通、科学数据已加固，后续增强须以"不破坏 3 案例跑通"为前提。
4. **被认为"套壳 Astropy"**：本轮 SIMBAD 全量校正 + 两轮验证日志是有力的科学严谨性证据，配合闭环和幻觉防护，可有效回应质疑。
5. **密钥安全**：`.env` 已 gitignore；务必确保真实 Key 不入仓库、不在聊天中明文传递。

---

## 五、立即可做的下一步

1. 修复 WARNING-1：提交 SIMBAD 中间数据或给 layer23 加联网重查模式（最高优先，关乎可复现性）。
2. 团队在本地 `.env` 填入 `DASHSCOPE_API_KEY`，跑一次 Qwen 模式确认全链路。
3. 修复 WARNING-2（导出 `observation_log.csv`）与 WARNING-3（补集成测试）。
4. 团队确认演示技术（Streamlit vs FastAPI）。
5. 启动第 4 周 Qwen 辅助归因增强。
