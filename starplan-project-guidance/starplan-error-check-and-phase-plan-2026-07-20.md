# StarPlan Loop 错误排查报告与阶段安排

日期：2026-07-20
项目起始：2026-07-18 ｜ 截止：2026-09-01 ｜ 当前进度：第 3 周核心已真实验证跑通（领先原计划约 1 周）
本报告依据 AGENTS.md「强制收尾报告」规则生成，同时追溯覆盖第 3 周提交 `fe1384d`（该提交当时未附收尾报告）。

---

## 一、本轮错误排查结论

本轮工作：在本地 `E:\learning\阿里云揭榜挂帅\starplan-project-guidance` 完成环境搭建（Python 3.13.5 虚拟环境 `.venv` + 8 个依赖安装），首次接入真实百炼 Qwen，并将 3 个案例端到端全部跑通。

**0 个 CRITICAL，3 个 WARNING，6 个 INFO。3 个案例重新运行均无错误。**

### 运行时扫描结果（真实跑通记录）

| 案例 | 输入 | 验证结论 | 关键输出 |
|---|---|---|---|
| 案例 1 | M31 + 济南_四门塔 + 2026-10-17（自然语言入口） | `[PASS] PASSED` | 可观测，推荐窗口 18:58~04:28，峰值高度 85.0°，Qwen 生成 8 条讲解要点，幻觉防护 0 拦截 |
| 案例 2 | M42 + 济南_四门塔 + 2026-07-25 | `[PASS] EXPECTED_FAILURE` | 正确判不可观测（夜间最高高度 −5.7°），3 条备选建议（M13/M57/等待季节），未编造最佳时间 |
| 案例 3 | M31 + 济南_四门塔 + 2026-10-17 + 观测日志 | 复盘通过 | 识别 3 类偏差，原因正确分级（有证据/可能/无法判断），修订计划 3 处字段变化 |

幻觉防护单元测试 `tests/test_hallucination_protection.py`：**8 passed, 0 failed**。

Qwen 连通性测试 `scripts/test_qwen_connection.py`（本次新增）：单轮调用与 JSON 结构化输出均通过，默认模型 qwen3.7-max。

天文正确性抽查：M31 济南峰值高度 85.0° 与理论值 90−|36.49−41.27|≈85.2° 一致；M42 在 7 月底夜间最高高度为负，符合其与太阳同升落的季节规律。

### WARNING 级问题

| # | 问题 | 文件 | 状态 |
|---|---|---|---|
| 1 | 复盘案例未单独导出 `observation_log.csv`，观测日志嵌在 `input.json` 中，与启动报告 4.2 节列出的 12 文件清单不符 | runner.py / observation_review.py | 待修复：复盘案例应将日志另存为 `observation_log.csv` |
| 2 | `test_hallucination_protection.py` 注释引用的 `test_qwen_integration.py` 不存在，真实 Qwen 集成测试缺失 | tests/ | 部分缓解：已新增 `scripts/test_qwen_connection.py`，但 tests/ 下集成测试仍缺 |
| 3 | Qwen 工具调用编排模式 `run_starplan_chat`（function calling）从未实测，阶段报告点名「最可能失控」的风险仍未验证 | runner.py / qwen_client.py | 待验证：需专门测试百炼 function calling 稳定性 |

### INFO 级项（确认无害或属设计取舍）

- 阶段计划文档（07-19）已过期，称「第 3 周待开始」，但第 3 周代码已提交；本报告取代其进度描述。
- `observation_review` 为规则版（关键词匹配），第 4 周任务 5「Qwen 辅助归因」尚未实现，属计划内延期。
- Windows GBK 控制台直接运行会中文乱码，需 `PYTHONIOENCODING=utf-8`；纯展示问题，写入文件均为 UTF-8 正常。
- 幻觉防护已知边界：0–10 的小数字恒通过、只校验数字不校验定性表述。属设计取舍，答辩需说明边界。
- `observability_plan` 核心计算用纯 Astropy，astroplan 已安装并用于版本记录但未用其 Observer/约束 API；技术栈口径需统一。
- 案例 1、2 输出 9 文件、案例 3 输出 11 文件（多 review_report.md、revised_plan.json），均符合「无复盘/有复盘」预期。

### 复现命令

```bash
cd StarPlan
source .venv/Scripts/activate            # Windows cmd: .venv\Scripts\activate
python scripts/test_qwen_connection.py   # 需先在 .env 填入有效 DASHSCOPE_API_KEY
python scripts/run_case.py examples/case_01_m31_jinan.json
python scripts/run_case.py examples/case_02_unfavorable_window.json
python scripts/run_case.py examples/case_03_observation_review.json
python tests/test_hallucination_protection.py
```

---

## 二、当前完成度对照项目计划

| 计划阶段 | 计划目标 | 实际状态 |
|---|---|---|
| 第 1 周 | 冻结范围、Schema、案例、验证规则 | ✅ 已完成 |
| 第 2 周 | 跑通目标解析 + 本地可观测性计算 | ✅ 已完成 |
| 第 3 周 | 接入 Qwen 编排 + 科普活动包 | ✅ 代码已提交且本次**首次真实验证跑通**（NL 解析 + Qwen 科普生成 + 幻觉防护 + 审计日志全链路） |
| 第 4 周 | 观测日志 + 复盘闭环 | 🟡 规则版复盘已验证跑通（案例 3），Qwen 辅助归因待接入 |
| 第 5 周 | 演示入口 + 3 类案例 | ⏳ 待开始（演示技术尚未选定） |
| 第 6 周 | 打磨评测、报告、视频 | ⏳ 待开始 |

**当前领先原计划约 1 周。** 原计划第 3 周为 07-25~08-01，实际 07-20 已完成第 3 周核心验证。3 个案例（正常/不可观测/复盘）已全部端到端真实跑通，证据链（manifest、validation_report、model_call_log）齐全。

---

## 三、接下来几周的阶段安排

### 第 4 周增强（建议提前启动）：复盘闭环接入 Qwen

核心任务：

1. **Qwen 辅助归因**：让 Qwen 基于观测日志备注做自然语言归因，但每条结论必须引用计划/日志的具体字段，保留 evidence_based / possible / undetermined 三级分类。
2. **补齐 `observation_log.csv` 导出**（修复 WARNING-1）。
3. **补真实 Qwen 集成测试** `tests/test_qwen_integration.py`（修复 WARNING-2）。

阶段验收：复盘归因由 Qwen 辅助生成且可追溯证据；`observation_log.csv` 独立导出；集成测试存在并通过。

### 第 5 周：演示入口与案例固化

核心任务：

1. **轻量演示面板**：Streamlit 或 FastAPI（**待团队确认**），展示输入、工具调用、中间结果、验证报告、复盘结果。
2. **一键复现**：固定命令跑通 3 案例并生成完整运行目录（现已基本具备，需打包成清晰入口）。
3. **失败场景完善**：名称歧义、地点缺失、整晚不可见、强月光、日志信息不足等都要有清楚失败原因。
4. **可解释推荐**：推荐窗口同时显示满足的约束、被淘汰时段及原因。

阶段验收：新环境可复跑；失败场景可解释；评委能在有限时间内看懂。

### 第 6 周：评测、报告与提交材料

核心任务：

1. **科学交叉校验**：用 Stellarium/KStars 对固定案例交叉校验高度角、暮光时间，保存差异记录。
2. **对照实验**：传统人工流程 vs StarPlan 的时间、遗漏项、可复现性对比。
3. **真实校园小试验**（可选高收益）：组织 5-10 人小规模观测，记录反馈。
4. **提交材料**：PPT/PDF（≤20 页）、技术报告、源码、Skills 清单与流程图、3 类任务运行记录、10 分钟演示视频。

阶段验收：材料齐全；可复现；Qwen 边界与调用证据清楚。

---

## 四、风险提示

1. **Qwen function calling 稳定性仍未实测**（WARNING-3）：目前只验证了 NL 解析模式与 JSON 模式，`run_starplan_chat` 的原生工具调用尚未跑过。这是阶段报告点名的头号风险，应尽快验证；若不稳定，备选方案是 structured output（JSON mode）+ 手动解析。
2. **时间压力下的范围控制**：最大风险不是做不完，而是每个模块都做 80% 但没有完整闭环。当前闭环已通，后续增强须以「不破坏 3 案例跑通」为前提。
3. **被认为「套壳 Astropy」**：须反复强调闭环（计划→执行→复盘）、证据链（manifest）、Qwen 分工与幻觉防护。对照实验和真实校园实测是最有力回应。
4. **演示技术未定**：Streamlit vs FastAPI 需团队尽快拍板，否则影响第 5 周。
5. **密钥安全**：本次有一把 API Key 曾在对话中明文暴露，已建议作废重生成；务必确保 `.env` 不入仓库（已在 `.gitignore`）。

---

## 五、立即可做的下一步

1. 测试 `run_starplan_chat`（Qwen function calling 编排模式），验证头号风险（WARNING-3）。
2. 修复 WARNING-1：复盘案例导出独立 `observation_log.csv`。
3. 补齐 WARNING-2：`tests/test_qwen_integration.py`。
4. 团队确认演示技术（Streamlit vs FastAPI）与提交平台/格式要求。
5. 启动第 4 周 Qwen 辅助归因增强。
6. 提交本报告 + 新增的 `scripts/test_qwen_connection.py` + `.gitignore` 改动（`.venv/` 排除），勿积压。
