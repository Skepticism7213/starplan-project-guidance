# StarPlan Loop 错误排查报告与阶段安排 — Phase A（Claim 架构设计冻结）

日期：2026-07-28
项目起始：2026-07-18 ｜ 截止：2026-09-01
本轮工作：实施 Claim 幻觉防护架构 Phase A（设计冻结），依据 `starplan-claim-architecture-gap-and-implementation-plan.md`

---

## 一、本轮错误排查结论

本轮改动了 `starplan_skills/schemas.py`（新增 Claim 架构数据结构）和 `requirements.txt`（补 tzdata）。**0 个 CRITICAL，1 个 WARNING（已修复），1 个 INFO。**

### 已修复的 WARNING 级问题

| # | 问题 | 文件 | 修复方式 |
|---|---|---|---|
| 1 | 团队 C-1 重写后的 `observability_plan.py` 使用 `zoneinfo` 处理 IANA 时区，但 `requirements.txt` 未声明 `tzdata`。Windows 上 Python 无内置 IANA 时区库，导致案例运行崩溃：`ValueError: Invalid IANA timezone: 'Asia/Shanghai'`。Linux 因系统自带时区库不受影响，故团队未暴露此问题。 | requirements.txt | 在 venv 安装 `tzdata` 并将 `tzdata>=2024.1` 加入 `requirements.txt`（Utilities 段，注明 Windows zoneinfo 需要）。该问题为团队既有遗漏，非本轮 Phase A 改动引入。 |

### INFO 级项

- Phase A 仅新增数据结构与一个带默认值的 `schema_version` 字段，向后兼容：现有代码创建 `CalculationManifest` 时不传 `schema_version` 会默认 "1.0"，不破坏既有调用。

### 验证与回归结果

- **Schema 验证**：12/12 通过。覆盖导入、ClaimType 五类齐全、RunState 关键状态、Claim 正例（M31 峰值高度角，含 schema_version 默认值与 JSON 序列化）、ExpressionPlan 正例、NUMERIC_DISPLAY_RULES、CalculationManifest 含 schema_version；反例（缺 claim_id、非法 ClaimType、SelectedClaim 缺 sentence_variant_id）均被正确拒绝。
- **运行时回归**：案例 1（M31 + 济南_四门塔 + 2026-10-17）在修复 tzdata 后完整跑通，生成 9 个文件，Qwen 科普包正常。确认 Phase A 改动未破坏现有流水线。

---

## 二、当前完成度对照项目计划

项目计划（2026-07-26 更新）已将 Claim Registry、受限表达协议和 fail-closed 定为第 3 周 Qwen 编排的加固基线。本轮启动该加固的 Phase A（设计冻结）：

| Phase | 目标 | 状态 |
|---|---|---|
| **A 设计冻结** | 冻结 Claim Schema、状态枚举、数值显示规则 | ✅ 本轮完成 |
| B Claim Registry 与模板安全化 | AllowedClaimsBuilder、claims.json、句式模板库 | ⏳ 待开始 |
| C Qwen 协议与 fail-closed | 结构化表达计划、确定性渲染、8 步验证、回退 | ⏳ 待开始 |
| D 状态机与科学内核 | RunState 状态机、坐标内核封装 | ⏳ 待开始 |
| E RunOutcome 与证据链 | 单一 RunOutcome、manifest 哈希、审计事件流 | ⏳ 待开始 |
| F 全量对抗验收 | Mock 对抗、端到端分支、硬指标 | ⏳ 待开始 |

**Phase A 已落地的具体产物**（`schemas.py`）：

- `ClaimType` 枚举：observed_fact / derived_fact / human_confirmed / unconfirmed / prohibited
- `RunState` 枚举：14 个业务状态（received → … → rendered → archived，含 computed_observable / computed_not_observable / data_insufficient / tool_error / needs_confirmation / validation_blocked）
- `ValidityScope` 模型：target / location_id / date / timezone / business_branch
- `Claim` 模型：claim_id、claim_type、subject、predicate、canonical_value、text_value、unit、display_value、display_tolerance、validity_scope、source_refs、derivation_rule、source_hash、allowed_variant_ids、schema_version
- `SelectedClaim` 模型：claim_id + sentence_variant_id（Qwen 只做选择，不产生事实文本）
- `ExpressionPlan` 模型：selected_claims + section_order + tone + connector_ids
- `NUMERIC_DISPLAY_RULES` 常量：冻结高度角/方位角/月距/airmass/月相/时间/视星等的显示精度与容差
- `CalculationManifest` 增加 `schema_version` 字段（默认 "1.0"）

---

## 三、阶段安排

### Phase B（下一步）：Claim Registry 与模板安全化

核心任务：

1. 新建 `starplan_skills/claims.py` 的 `AllowedClaimsBuilder`：从 `ResolvedTarget` + `ObservabilityResult` 构建 Claim 集合，生成稳定 claim_id，跑版本化推导规则生成 derived_fact，缺失信息转 unconfirmed（不静默补值），生成 prohibited 集合，计算来源哈希，输出 `claims.json`。
2. 文字事实（"肉眼可见""适合新手""设备匹配"）由版本化规则生成，输入不足则 unconfirmed。
3. 将 `_build_fact_cards` 迁移为 Claim 构建（FactCard → Claim）。
4. 建立句式变体模板库（每条 Claim 配审核过的 sentence variants，按受众分档）。
5. 审计现有模板（`_build_talking_points`、`safety_notes`、`_generate_not_observable_pack`），删除未经验证的事实性固定文案。

阶段验收：模板输出的每个事实句均能映射 Claim；缺失信息只输出 unconfirmed；不依赖 Qwen 也能生成完整可用输出。

### Phase C–F

见 `starplan-claim-architecture-gap-and-implementation-plan.md` 第 2 节。Phase C（Qwen 协议 + fail-closed）是范式切换的胜负手，须在 B 之后优先完成。

---

## 四、风险提示

1. **范式重构非补丁**：架构第 15 节禁止"只给 `_validate_talking_points` 加正则补丁"。Phase B/C 须真正落地 Claim Registry 与确定性渲染，而非在旧过滤法上打补丁。
2. **不破坏现有跑通**：每个 Phase 结束须保证 3 个固定案例仍可一键复现。Phase A 已确认案例 1 跑通；Phase B 起每阶段须跑全部 3 案例回归。
3. **时间压力**：比赛 2026-09-01 截止。建议至少完成 Phase A→C + Layer 2 核心对抗测试，使"从检测到预防"的叙事有代码支撑。
4. **Windows 环境依赖**：本轮发现 tzdata 遗漏，提示后续新增依赖（尤其涉及系统级数据如时区、星表）须同步更新 requirements.txt 并在干净环境验证。

---

## 五、立即可做的下一步

1. 提交并推送本轮 Phase A 改动（schemas.py + requirements.txt + 本报告），勿积压。
2. 启动 Phase B：实现 `claims.py` 的 `AllowedClaimsBuilder`，先把 M31 案例的 Claim 集合与 `claims.json` 生成出来。
3. 团队确认：句式变体模板库由谁维护、按几档受众划分（Phase B 需要）。
