# 星程 StarPlan Loop — 项目全面审视

日期：2026-07-28
撰写：项目负责人 + QoderWork 协作
项目周期：2026-07-18 启动 → 2026-09-01 截止
赛道：挑战杯"揭榜挂帅"阿里云赛道 · 第三赛道方向三"星语·面向 AI 的天文实训"

---

## 一、项目定位与核心命题

### 1.1 赛题要求

阿里云百炼平台要求参赛者构建"AI Ready Skills"——可被 Qwen 大模型调用的结构化技能包，实现天文观测从需求到复盘的完整闭环。核心考察点不是"做一个天文 App"，而是：大模型如何在不编造科学数据的前提下，完成有意义的编排、表达和推理。

### 1.2 我们的回答

星程 StarPlan Loop 是一个 Qwen 可调用的 4-Skill 闭环系统：

```
观测需求 → 确定性天文计算 → 观测计划 + 科普活动包 → 观测日志 → 证据化复盘 → 修订下一轮计划
```

核心原则用一句话概括：**工具算，模型讲，报告验，人员确认，日志促改进。** Qwen 永远不产生天文数值——所有坐标、高度角、时间、月相均由 Astropy 确定性计算，Qwen 只负责理解需求、编排流程、适配表达。

### 1.3 四个核心 Skill

| Skill | 职责 | 计算方式 |
|---|---|---|
| `target_resolve` | 将中/英文、Messier/NGC 编号解析为标准天体 + 坐标 | 本地星表匹配（150 目标），不依赖网络 |
| `observability_plan` | 计算高度角/方位角/大气质量/暮光/月光影响，输出推荐窗口 | Astropy AltAz 坐标系 + 自研暮光二分法 |
| `outreach_pack` | 从已验证事实生成科普讲解包（流程/要点/设备/安全） | Claim Registry + 确定性渲染（Qwen 仅选择表达） |
| `observation_review` | 对比计划与实际日志，识别偏差、归因、建议 | 规则引擎 + Qwen 辅助归因（fail-closed） |

外加一个总控入口 `starplan.run`（三种模式：结构化输入 / 自然语言 / Qwen function calling 编排）。

---

## 二、时间线与关键里程碑

### 第 0 周（07-18）：项目启动

- 读取赛题文档，输出 14 节启动报告（`starplan-loop-kickoff-report.md`）
- 确认技术栈：Python 3.13 + Astropy 8.0.1 + astroplan 0.10.1 + Pydantic 2.x + dashscope
- 确认模型：Qwen3.7-Max / Qwen3.7-Plus（后增 Qwen3.8-Max-Preview）
- 确认地点：济南四门塔（lat 36.49, lon 117.18, elev 300m）
- 建立 GitHub 仓库，设定 AGENTS.md 工作规则

### 第 1 周（07-19 ~ 07-20）：MVP 搭建

- 从零实现 4 个 Skill + 总控 runner
- 建立 Pydantic Schema（StarPlanInput / ObservabilityResult / OutreachPack / ObservationReview）
- 编写 3 个固定案例（M31 可观测 / M42 不可观测 / M31+日志复盘）
- 实现 Layer 1 本地一致性验证（150 目标 × 10 轮 × 4 类检查）
- 修复 Windows 编码（GBK → ASCII 标记）、matplotlib 中文字体、时轴 UTC→CST 等问题
- 首份 error-check 报告

### 第 2 周前半（07-23）：独立审查与 8 项修复

- 外部审查发现 8 个问题（validation_report 误判 / run_id 碰撞 / 暮光精度 / 别名匹配 / 审计日志缺失 / 月相约束未生效 / Astropy 警告 / 案例 3 时间错误）
- 全部验证为真实 bug 并修复
- 追加 9 个 WARNING 级修复（numpy 依赖 / None 崩溃 / CSV 零值 / 月相配置 / prefer_early_night / 设备限制 / 多日范围 / 时区假设 / 未用导入）

### 第 2 周后半（07-23 晚）：独立审计报告

- 另一位审查者（Optius）提交全面独立审计，发现 **5 个 CRITICAL + 11 个 WARNING**
- 最重要的发现：
  - **C-1**：月球角距在 ICRS/GCRS 之间直接 `.separation()`，误差 72°
  - **C-4**：Chat 模式幻觉检查 fail-open（检测到 15 个不可溯源数值但仍返回原文）
  - **C-5**：Manifest 硬编码 `validation_status="passed"`，证据链不可信
- 我逐项验证全部属实，推翻了此前"第 3 周已完成、领先 1 周"的判断

### 第 3 周（07-24 ~ 07-25）：CRITICAL 修复 + WARNING 清理

- 团队（m21m0721）修复 C-1~C-5，新增 54 个回归测试
- 修复 W-1~W-9（layer23 健壮性 / 溯源文件 / NL 日志 / 工具定义 / 文本幻觉防护 / 月相 OR 逻辑 / buffer_minutes / zoneinfo / observation_log Schema）
- 我同步验证：C-1~C-5 全部通过，W-4 半修（定义有但执行器缺失），W-10/W-11 未动
- 我补修 W-4/W-10/W-11/C-2 测试/坐标精度/SIMBAD 脚本/nl_parser null 崩溃

### 第 3 周加固（07-26 ~ 07-28）：幻觉防护架构

这是项目最重要的一次方向升级。

**起因**：我提出预防方案——把 Qwen 从"生成者"降级为"改写者"，用允许声明表 + claim_id 映射替代正则过滤。

**团队响应**：另一位协作者将其升级为完整的架构提案（`starplan-hallucination-prevention-architecture.md`，640 行），定义了：
- Claim Registry 数据模型（5 种 Claim 类型 + 数值显示规则 + 来源哈希）
- Qwen 结构化表达协议（只返回 claim_id + sentence_variant_id + 顺序 + 语气）
- 确定性渲染器（程序从审核过的句式模板渲染最终文本）
- 8 步验证器 + fail-closed 回退
- 14 状态业务状态机
- 单一 RunOutcome + 追加式审计事件流
- 4 层测试矩阵 + 7 项硬性验收指标

**实施**（07-28，5 个 commit）：Phase A→F 一次性落地。新增 6 个核心模块（claims.py / templates.py / rendering.py / expression_validator.py / run_outcome.py）+ 2 个测试文件（claims registry 16 例 + mock adversarial 14 例）。

**验证结果**（本次）：
- 94/94 pytest 通过
- 3 案例端到端正常，claims.json / state_log.json / sentence_claim_map.json 均正确生成
- 发现并修复 1 个回归（不可观测分支误用观测句式）
- 架构硬指标全部满足：无来源事实率=0、原文泄漏率=0、Claim 映射覆盖率=100%

---

## 三、关键技术决策与变动

### 3.1 地点从北京改为济南四门塔

启动报告最初使用"北京某高校"作为示例。团队讨论后改为济南四门塔——一个真实的、有光污染梯度数据的校园周边观测点。这影响了所有案例的经纬度、暮光时间和高度角计算。project-plan 中的引用直到 07-28 才全部更新完毕（W-11）。

### 3.2 模型选择

初始确认 Qwen3.7-Max/Plus。后增加 Qwen3.8-Max-Preview 为可选。代码中 `DEFAULT_MODEL = "qwen3.7-max"`，通过环境变量 `STARPLAN_MODEL` 可切换。

### 3.3 从"事后过滤"到"事前约束"的范式转换

这是项目最核心的架构变动：

| 维度 | 旧范式（07-19 ~ 07-25） | 新范式（07-28 起） |
|---|---|---|
| Qwen 角色 | 自由生成讲解文本 | 只选择 claim_id + 句式变体 |
| 安全边界 | 正则提取数字 → 黑名单过滤 | Claim Registry 白名单 + 8 步验证 |
| 文字事实 | 不检查 | 版本化推导规则生成（肉眼可见/适合新手等） |
| 失败行为 | 检测到问题但仍返回原文 | fail-closed：回退确定性模板，原文进审计 |
| 最终渲染 | Qwen 文本即最终输出 | 程序从 display_value 填充审核过的模板 |
| 证据链 | manifest 硬编码 passed | RunOutcome 三状态分离 + 文件哈希 |

### 3.4 星表数据重建

初始星表 150 目标中 37 条坐标偏差 >2 角分（最差 M23 错 4.4°）。团队通过 SIMBAD TAP 查询重建，并建立 `catalog_provenance.json` 记录数据来源、查询日期和验证历史。

### 3.5 测试策略演进

| 阶段 | 测试内容 | 数量 |
|---|---|---|
| 第 1 周 | Layer 1 本地一致性 + 8 项幻觉过滤 | ~20 |
| 第 3 周 | C-1~C-5 回归 + W-6~W-9 单元 | +75 |
| 架构后 | Claim Registry + Mock Qwen 对抗（14 种攻击向量） | +30 |
| 当前总计 | pytest 94 + 置信度脚本 150 + layer23 10 轮 | ~250+ |

---

## 四、当前系统架构

```
用户请求（结构化 / 自然语言 / Chat）
    │
    ▼
┌─ runner.py ─────────────────────────────────────┐
│  状态机: received → input_validated →            │
│  ready_to_compute → computed_observable /        │
│  computed_not_observable / needs_confirmation /  │
│  data_insufficient / tool_error                  │
│                                                  │
│  ┌─ target_resolve ─┐  ┌─ observability_plan ─┐ │
│  │ 本地星表匹配     │  │ Astropy AltAz 计算   │ │
│  │ 歧义→人工确认   │  │ 暮光二分法           │ │
│  └─────────────────┘  │ 月距同框架           │ │
│                        └──────────────────────┘ │
│  ┌─ claims.py ──────────────────────────────┐   │
│  │ AllowedClaimsBuilder                      │   │
│  │ → claims.json (18+ claims, registry_hash)│   │
│  │ → prohibited 集合                        │   │
│  │ → derived_fact 推导规则                  │   │
│  └──────────────────────────────────────────┘   │
│  ┌─ outreach_pack ──────────────────────────┐   │
│  │ Qwen → ExpressionPlan (claim_id 选择)    │   │
│  │ → expression_validator (8 步)            │   │
│  │ → rendering.py (确定性渲染)              │   │
│  │ → sentence_claim_map.json                │   │
│  │ 失败 → fail-closed 确定性回退           │   │
│  └──────────────────────────────────────────┘   │
│  ┌─ observation_review ─────────────────────┐   │
│  │ 规则引擎偏差识别                         │   │
│  │ + Qwen 辅助归因 (fail-closed)            │   │
│  └──────────────────────────────────────────┘   │
│  ┌─ run_outcome.py ─────────────────────────┐   │
│  │ 单一 RunOutcome → manifest / validation  │   │
│  │ business_status / validation_status /    │   │
│  │ delivery_status 三状态分离               │   │
│  └──────────────────────────────────────────┘   │
│  输出: state_log.json / model_call_log.jsonl /   │
│        claims.json / sentence_claim_map.json     │
└──────────────────────────────────────────────────┘
```

---

## 五、证据链与可审计性

每次运行生成 12~15 个文件，形成完整证据链：

| 文件 | 作用 |
|---|---|
| `input.json` | 原始输入快照 |
| `resolved_target.json` | 目标解析结果 + 置信度 |
| `plan.json` | 完整可观测性计算结果 |
| `observability.csv` | 15 分钟粒度高度/方位/气质量/月距数据 |
| `visibility_curve.png` | 高度角-时间曲线图 |
| `claims.json` | Claim Registry（含 registry_hash） |
| `sentence_claim_map.json` | 每句输出文本 → claim_id 映射 |
| `state_log.json` | 业务状态机流转记录 |
| `model_call_log.jsonl` | 所有 Qwen 调用审计（步骤/模型/是否使用） |
| `outreach_pack.md` | 最终科普活动包 |
| `calculation_manifest.json` | 工具版本/约束/模型状态/验证结论 |
| `validation_report.md` | 输入/目标/计算/总体结论 |
| `observation_log.json` | 观测日志（案例 3） |
| `review_report.md` | 复盘报告（案例 3） |
| `revised_plan.json` | 修订计划（案例 3） |

---

## 六、已知残留问题

| 优先级 | 问题 | 影响 |
|---|---|---|
| 中 | `run_starplan` 主路径仍用旧 `_build_manifest`，未完全迁移到 RunOutcome | 证据链不完整（渐进迁移中） |
| 中 | Layer 3 端到端 10 类分支测试未全覆盖 | 部分失败路径缺少自动化守护 |
| 低 | `simbad_dim_otype.json` 未入库（需运行 `simbad_tap_query.py` 生成） | layer23 的 SIMBAD 交叉检查跳过 |
| 低 | 演示技术未选型（Streamlit vs FastAPI） | 第 5 周阻塞项 |
| 低 | 百炼免费额度有限 | 演示和测试需控制调用次数 |

---

## 七、比赛竞争力评估

### 优势

1. **"从检测到预防"的完整叙事**：不只是做了幻觉过滤，而是经历了"发现问题→独立审计→架构重设计→全量落地"的完整过程，这本身就是工程能力的展示。
2. **证据链可当场审计**：评委点击任何一句输出，都能追溯到 claim_id → source_tool → 计算版本。
3. **失败路径是一等公民**：不可观测、歧义、工具错误、API 断开都有独立的确定性输出，而不是"报错"或"静默跳过"。
4. **确定性可复现**：同一输入多次运行，事实性输出完全一致（registry_hash 稳定）。

### 风险

1. **时间压力**：距截止 34 天。演示页面、视频、PPT 均未开始。
2. **架构复杂度 vs 可解释性**：Claim Registry + 8 步验证 + 状态机对评委来说信息密度很高，演示需要极度精简。
3. **Qwen 依赖**：真实演示需要网络和 API 额度；离线回退虽然存在但"Qwen 参与"是赛题核心。

---

## 八、文档体系现状

`starplan-project-guidance/` 中保留的核心文档：

| 文件 | 角色 |
|---|---|
| `starplan-loop-project-plan.md` | 唯一事实源：范围、Schema、案例、阶段计划 |
| `starplan-hallucination-prevention-architecture.md` | 幻觉防护架构规范（Phase A~F 定义） |
| `starplan-claim-architecture-gap-and-implementation-plan.md` | 代码差距对照 + 实施方案 |
| `starplan-loop-kickoff-report.md` | 启动分析（历史参考） |
| `qwen-project-kickoff-prompt.md` | Qwen 启动指令模板 |
| `starplan-loop-competition-enhancements.md` | 可选增强清单 |
| `starplan-qoderwork-transfer-log.md` | 实施交接上下文 |
| `starplan-transfer-log-diff.md` | 交接变更记录 |
| `starplan-project-full-review-2026-07-28.md` | 本文件 |

已归档（移入 `archive/`）的阶段性小报告：7 份 error-check-and-phase-plan 日志 + 1 份 C-1~C-5 修复报告 + 1 份 Phase A 冻结报告 + 1 份架构 error-check。这些是过程产物，其结论已被本文件和项目计划吸收。

---

## 九、下一步（按优先级）

1. **RunOutcome 主路径集成**：让 `run_starplan` 的 manifest 完全由 RunOutcome 生成，消除旧 `_build_manifest`。
2. **演示入口**：轻量 Streamlit 页面，展示"输入→工具调用→Claim→渲染→验证"全链路，一键跑 3 案例。
3. **Layer 3 端到端分支补全**：Qwen 幻觉表达计划 / 工具异常 / 日志证据不足等。
4. **提交材料准备**：PPT（≤20 页）、技术报告、10 分钟演示视频。
5. **对照实验**：裸 Qwen vs 旧过滤器 vs Claim 架构的无来源事实率对比。
