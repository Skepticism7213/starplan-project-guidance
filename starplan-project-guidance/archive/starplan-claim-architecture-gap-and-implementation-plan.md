# Claim 幻觉防护架构：代码差距对照与实施方案

日期：2026-07-27
状态：分析与实施提案（基于当前 main 分支 ef887ec 的代码核查）
对照基准：`starplan-hallucination-prevention-architecture.md`（2026-07-26 提案）

---

## 0. 总体判断

当前代码整体仍处于架构所定义的"旧范式"——**模型自由生成后再过滤**（`_validate_talking_points` 数字溯源 + `_check_chat_hallucination` 核查）。架构要求的范式核心（Claim Registry、Qwen 降级为表达编排者、程序确定性渲染、fail-closed、业务状态机、单一 RunOutcome）**均未在代码中实现**，目前只存在于提案文档。

但团队已完成大量"地基与配套"工作：修复 C-1~C-5 关键 bug、manifest 健壮性改进（validation_status 不再写死 passed、ModelInfo.called、输入 extra=forbid）、不可观测分支包（pack_type）、目录数据对 SIMBAD 的交叉核验（layer1/layer23）、以及一批回归测试。这些为迁移到 Claim 架构打下了基础，但不等于架构本身已落地。

代码中**不存在** `claim_id`、`ClaimRegistry`、`RunOutcome`、`sentence_variant`、`allowed_claims` 任何实现（已全仓 grep 确认）。

---

## 1. 已做 / 待做对照清单

图例：✅ 已实现 ｜ 🟡 部分实现 ｜ ❌ 未实现

| # | 架构组件 | 状态 | 当前代码证据 |
|---|---|---|---|
| 1 | Claim 数据模型（claim_id/claim_type/canonical_value/unit/display_value/source_refs/source_hash/validity_scope） | ❌ | `FactCard` 仅 `key/value/source` 三字段（schemas.py:242-247） |
| 2 | Allowed Claims Builder + `claims.json` | ❌ | 无；`_build_fact_cards` 直接拼 FactCard（outreach_pack.py） |
| 3 | Claim 五类型（observed_fact/derived_fact/human_confirmed/unconfirmed/prohibited） | ❌ | 无类型枚举 |
| 4 | Qwen 结构化表达协议（返回 claim_id+sentence_variant_id+顺序+语气） | ❌ | Qwen 仍自由生成 talking_points（outreach_pack.py:84 `_generate_talking_points_qwen`） |
| 5 | 确定性渲染 + 句式变体模板库 + 句子→Claim 映射 | ❌ | 程序模板 `_build_talking_points` 或 Qwen 自由文本，无映射 |
| 6 | 8 步结构验证（Schema/ID允许集/作用域/来源哈希等） | 🟡 | 仅数字正则溯源 `_validate_talking_points` + 基础 sanity（validation.py），无 ID/作用域/哈希验证 |
| 7 | Fail-closed 回退（验证失败即回退、不泄漏原文） | 🟡 | Qwen 异常回退模板（outreach_pack.py:88-91），但自由文本路径无"验证失败强制回退、原文不落地"硬保证 |
| 8 | 业务状态机（RECEIVED→…→ARCHIVED；可观测/不可观测/数据不足/待确认/工具错误独立状态） | 🟡 | 仅 `is_observable` 布尔 + `pack_type`（observation/not_observable，C-3）；无完整状态枚举，无 DATA_INSUFFICIENT/TOOL_ERROR 独立状态 |
| 9 | 单一 RunOutcome 对象（同时生成 manifest/validation/用户输出） | ❌ | manifest 与 validation_report 分散构建（runner.py `_build_manifest`/`_write_validation_report`） |
| 10 | Manifest 规则（schema_version、model_used 从事件反推、禁止写死 passed、文件哈希） | 🟡 | validation_status 已改 "pending"+validation_issues（非写死）✓、ModelInfo.called ✓；但**无 schema_version、无文件哈希** |
| 11 | 追加式审计事件流（输入/输出哈希、Claim 哈希、提示词哈希、finish reason、工具上游来源） | 🟡 | `model_call_log.jsonl` 存在但字段简单，缺哈希与上游来源 |
| 12 | 坐标科学内核（封装 `moon_target_apparent_separation`、禁全局警告屏蔽、测试警告转错误） | 🟡 | C-1 已修（月距改同框架 AltAz，test_moon_separation_c1.py）；是否封装为统一函数、是否彻底移除全局 `warnings.filterwarnings`、测试是否将坐标警告提升为错误，需逐项确认 |
| 13 | 测试矩阵 Layer 1 离线科学 | ✅ | test_moon_separation_c1 / c2 / c3 / c4、test_confidence_algorithm、test_w6_w9_unit、layer1_validation |
| 14 | 测试矩阵 Layer 2 Mock Qwen 对抗（纯文字幻觉/夹带/错单位/错时区/伪造Claim/提示注入/非法JSON/API失败） | ❌ | `layer23_validation.py` 实为**目录数据对 SIMBAD 的交叉核验**，并非 Mock Qwen 对抗；架构要求的对抗用例均无 |
| 15 | 测试矩阵 Layer 3 端到端分支（架构列 10 类） | 🟡 | 有 not_observable_pack_c3 等分支测试，但 10 类分支未全覆盖（如 Qwen 返回幻觉表达计划、工具异常、日志证据不足等） |
| 16 | 测试矩阵 Layer 4 真实 Qwen canary | ✅ | test_qwen_integration.py |
| 17 | 提示注入防护（用户输入放入数据字段不拼接系统规则 + 对抗测试） | ❌ | 输入虽 `extra=forbid`（W-9），但无明确数据字段隔离与注入对抗测试 |
| 18 | unconfirmed / prohibited 处理 | 🟡 | `unconfirmed_items` 处理缺失数据 ✓；但无 prohibited 集合、无"unconfirmed 不得改写为肯定结论"的验证 |

**统计**：18 项中 ✅ 2 项、🟡 8 项、❌ 8 项。范式核心（#1-#5、#9）全部为 ❌。

---

## 2. 实施方案（修改方案）

按架构第 13 节的 Phase A→F 推进，下面落到具体文件与函数。**Phase A→C 是范式切换的核心，必须先完成；D→F 是加固与验收。** 架构第 14 节明确：完成 A→C 前不做 observation_review 自由归因、复杂演示页面、行星扩展。

### Phase A：设计冻结（先冻 Schema 再动实现）

目标：把 Claim、状态、表达计划的数据结构定死。

- `schemas.py` 新增：
  - `ClaimType` 枚举（observed_fact / derived_fact / human_confirmed / unconfirmed / prohibited）
  - `Claim` 模型（claim_id、claim_type、subject、predicate、canonical_value、unit、display_value、display_tolerance、validity_scope、source_refs、derivation_rule、source_hash、allowed_variant_ids）
  - `RunState` 枚举（RECEIVED / INPUT_VALIDATED / NEEDS_CONFIRMATION / READY_TO_COMPUTE / COMPUTED_OBSERVABLE / COMPUTED_NOT_OBSERVABLE / DATA_INSUFFICIENT / TOOL_ERROR / CLAIMS_BUILT / EXPRESSION_PLANNED / VERIFIED / VALIDATION_BLOCKED / RENDERED / ARCHIVED）
  - `ExpressionPlan` / `SelectedClaim` 模型（Qwen 的结构化输出：claim_id + sentence_variant_id + section_order + tone + connector_ids）
- 定义数值显示规则配置（高度角 0.1°、时间 HH:MM 带时区、airmass 两位小数等，架构 5.3）
- **先更新 `starplan-loop-project-plan.md`**（AGENTS.md 要求决策先改项目计划），再同步 transfer log / diff log
- 验收：Schema 有正例与反例；所有状态有确定性输出定义；团队确认默认采用"Qwen 表达计划 + 程序渲染"

### Phase B：Claim Registry 与模板安全化

目标：让"允许说的事实"由程序从工具输出构建，模板自身也过 Claim 约束。

- 新建 `starplan_skills/claims.py`：
  - `AllowedClaimsBuilder`：读 ResolvedTarget + ObservabilityResult → 固化作用域 → 生成稳定 claim_id → 跑版本化推导规则生成 derived_fact → 缺失信息转 unconfirmed（不静默补值）→ 生成 prohibited 集合 → 算哈希 → 输出 `claims.json`
  - 文字事实（"肉眼可见""适合新手""设备匹配"）由版本化规则生成（如 `derived.visibility.naked_eye`，输入不足则 unconfirmed）
- 将 `_build_fact_cards` 迁移为 Claim 构建（FactCard → Claim）
- 新建句式变体模板库（每条 Claim 配审核过的 sentence variants，按受众分 beginner/general）
- 审计现有模板（`_build_talking_points`、`safety_notes`、`_generate_not_observable_pack`），删除其中未经验证的事实性固定文案
- 验收：模板输出的每个事实句均能映射 Claim；缺失信息只输出 unconfirmed；不依赖 Qwen 也能生成完整可用输出

### Phase C：Qwen 协议与 fail-closed（范式切换的关键）

目标：Qwen 不再提供事实文本，只选择；最终文字由程序渲染；任何失败确定性回退。

- 重写 `_generate_talking_points_qwen` → 改为让 Qwen 返回 `ExpressionPlan`（claim_id + sentence_variant_id + 顺序 + 语气），**不返回自由事实句**
- `qwen_client.py`：新增结构化表达协议调用（JSON mode + Schema 约束 + 仅一次格式纠正重试）
- 新建确定性渲染器 `render_from_claims`：事实槽位只从 Claim 的 display_value 填充；标题/连接词/语气来自审核过的有限集合；保存"句子→Claim ID"映射
- 新建 8 步验证器 `validate_expression_plan`（Schema/版本/ID允许集/作用域/unconfirmed与prohibited误选/重复冲突/来源哈希/渲染对象来源）
- fail-closed：API 失败、JSON 非法、未知 ID、作用域不匹配、超重试上限 → 一律回退确定性模板，**不返回部分原文、不把检测失败仅当警告附在原文旁**
- 验收：原始 Qwen 文本无直接用户输出路径；Mock 夹带文字事实被阻断；API 断开时四个核心 Skill 离线主路径仍可运行

### Phase D：状态机与科学内核

- `runner.py` 实现 `RunState` 状态机，显式拆分 可观测/不可观测/数据不足/待确认/工具错误；不可观测路径禁用正常观测语言；工具失败不得误报为不可观测
- `observability_plan.py` 封装 `moon_target_apparent_separation(target_icrs, obstime, location, refraction_policy)` 统一函数（同 obstime、同 location、同 AltAz frame、明确折射策略并记入 Manifest）；禁止调用方直接跨框架 `.separation()`
- 移除生产代码全局 `warnings.filterwarnings`；测试中把坐标转换警告提升为错误；仅复现旧 bug 的测试局部屏蔽并注明原因
- 验收：每个状态有固定案例；坐标回归测试离线通过

### Phase E：RunOutcome 与证据链

- 新建 `run_outcome.py`：单一 `RunOutcome` 对象，manifest / validation_report / 用户输出 / 测试摘要全部由它渲染；业务状态与验证状态分离（business_status / validation_status / delivery_status）
- `CalculationManifest` 增加 `schema_version`、关键文件哈希；`model_used` 只能从真实 model_call 事件反推，无调用事件必须为 false；禁止构建函数写死 validation_status="passed"
- 升级 `model_call_log.jsonl` 为追加式审计事件流（输入/输出哈希、Claim Registry 哈希、规则版本、提示词哈希、响应哈希、finish reason、用量、工具参数上游来源、产物哈希）；日志不存 API Key
- 验收：模板模式不声称用了 Qwen；验证失败不显示 passed；篡改受保护产物后哈希校验失败

### Phase F：全量对抗验收

- 新建 Mock Qwen 对抗测试（Layer 2）：固定返回 工具没返回的数字 / 无数字的错误事实 / 合法 Claim 后夹带新事实 / 合法值错单位 / 合法时刻错时区跨日 / 伪造·重复·冲突 Claim / unconfirmed 写成确定结论 / 提示注入 / 非法 JSON / 空响应 / 超长响应 / 超最大工具轮次 / 要求跳过地点解析猜坐标。每个用例断言：错误原文未出现在用户输出、生成确定性回退、留下审计事件
- 补端到端 10 类分支测试（Layer 3）
- 真实 Qwen canary（Layer 4，低频手动）
- 对比 裸 Qwen vs 旧过滤器 vs 新架构 的 无来源事实率/阻断率/回退率
- 验收（硬指标）：用户可见无来源事实率=0、验证失败原文泄漏率=0、Claim 映射覆盖率=100%、业务状态分支覆盖率=100%、模型使用记录准确率=100%、离线核心案例通过率=100%、同输入复跑一致率=100%
- 生成 mandatory error-check and phase-plan 报告，与代码一起提交推送

---

## 3. 关键文件改动清单

| 文件 | 改动 | Phase |
|---|---|---|
| `schemas.py` | 新增 Claim/ClaimType/RunState/ExpressionPlan/SelectedClaim；Manifest 加 schema_version | A、E |
| `starplan_skills/claims.py`（新建） | AllowedClaimsBuilder、claims.json、文字事实推导规则 | B |
| 句式模板库（新建，如 `templates/`） | 审核过的 sentence variants | B |
| `outreach_pack.py` | Qwen 改为返回表达计划；接入确定性渲染器与验证器；fail-closed；模板安全化 | B、C |
| `qwen_client.py` | 结构化表达协议调用 | C |
| `starplan_skills/rendering.py`（新建） | render_from_claims 确定性渲染 + 句子→Claim 映射 | C |
| `starplan_skills/expression_validator.py`（新建） | 8 步验证器 | C |
| `runner.py` | RunState 状态机；RunOutcome 接入 | D、E |
| `observability_plan.py` | 封装 moon_target_apparent_separation；移除全局警告屏蔽 | D |
| `run_outcome.py`（新建） | 单一 RunOutcome | E |
| `tests/test_mock_qwen_adversarial.py`（新建） | Layer 2 对抗测试 | F |
| `tests/` 端到端分支测试 | 补 10 类分支 | F |

---

## 4. 风险与范围控制

- **工作量大**：这是一次范式重构，不是补丁。架构第 15 节明确禁止"只给 `_validate_talking_points`/`_check_chat_hallucination` 加关键词正则补丁"。需团队评估在比赛截止（2026-09-01）前能推进到哪个 Phase。
- **优先级建议**：A→B→C 是范式核心（决定"无来源事实率=0"能否成立），应优先；D→E→F 是加固与验收。若时间紧，至少完成 A→C 并补 Layer 2 对抗测试的核心用例。
- **不破坏现有跑通**：每个 Phase 结束须保证 3 个固定案例仍可一键复现，再提交该 Phase 的测试证据与收尾报告（AGENTS.md 强制要求），不得以"命令退出码 0"替代验收结论。
- **保护他人改动**：实施时保护工作区已有修改，不覆盖或回退其他人的变更。

---

## 5. 待团队确认

- 是否默认采用"Qwen 表达计划 + 程序渲染"为唯一比赛演示路径（自由润色仅作非默认实验模式）？
- 句式变体模板库由谁维护、按几档受众划分？
- 在比赛截止前，目标推进到哪个 Phase（建议至少 A→C + Layer 2 核心对抗）？
