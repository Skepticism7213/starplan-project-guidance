# StarPlan Error Check & Phase Plan - 合并后独立验收（2026-08-01）

## 1. 审查基线与结论

- 审查基线：`0252a35a36086373ba8f80d3a72314ed2762f01c`（`Merge teammate science fixes into Claim architecture`）。
- 远端状态：审查前重新 fetch；本地 `HEAD` 与 `origin/main` 一致，`origin/main...HEAD = 0 0`。
- 审查范围：Claim Registry、确定性渲染、运行时门禁、Chat、观测复盘、科学边界、离线测试、真实百炼 canary、运行产物与项目计划验收条件。
- 总结：Qwen 报告的 `5` 个 edge-case、`25` 个 Layer 3 测试和 M31/M42 主 smoke case 均可复现；但“P1-P4 全部完成、所有 CRITICAL 均关闭”不成立。当前是“主要天文计算基线通过，可信输出架构和复盘证据链仍为部分完成”。

项目计划要求“用户可见无来源事实率为 0、验证失败原文泄漏率为 0、事实 Claim 映射覆盖率为 100%”。当前实际产物尚不满足其中的 Claim 映射覆盖率和完整 fail-closed 门禁，因此不得把 Phase 3 标记为最终验收完成。

## 2. 运行验证结果

| 验证项 | 结果 | 说明 |
|---|---:|---|
| Python 编译检查 | PASS | `starplan_skills`、`scripts`、`tests` 可编译 |
| 示例 Schema | 3 passed | 三个案例结构均合法 |
| 完整离线 pytest（排除真实 Qwen） | 145 passed | `STARPLAN_MODEL_MODE=offline`，无测试失败 |
| Edge cases | 5 passed | 与团队声称一致；但极昼用例只检查布尔值，未检查原因和用户文案 |
| Layer 3 E2E | 25 passed | 与团队声称一致；当前 trace 测试没有验证最终 Markdown 的逐句对应 |
| Layer 1 数据验证 | 150 个目标，10 轮 0 问题 | 范围、星座、类型属性、别名冲突通过 |
| Layer 2/3 数据验证 | 150 个目标，10 轮 0 问题 | 来源、坐标、星等、角大小、NGC、别名、中文名、类型通过 |
| astroplan 交叉校验 | 12/12 passed | M31/M42 的暮光、位置、月相和可观测判定均在容差内 |
| M31 离线 smoke | PASS | 2026-10-17 可观测，峰值高度约 85.0 度 |
| M42 离线 smoke | PASS | 2026-07-25 不可观测，主案例原因表现为 altitude |
| 百炼连通性 | 2/2 passed | `qwen3.7-max` 单轮与 JSON 模式均成功；未输出或写入 API key |
| 真实 Qwen 集成测试 | 5 passed, 2 failed | 两个 Chat 测试仍读取已从公共返回删除的 `tool_call_log`，测试契约过期 |
| 真实 M31 结构化案例 | PASS（仅运行层面） | Qwen ExpressionPlan 成功，业务结果正确；但 trace 覆盖和天气 Claim 仍不合格 |
| 真实闭环复盘案例 | PASS（仅运行层面） | 报告成功生成；但模型归因来源、修订因果映射和调用计数不真实 |

说明：首次在受限沙箱中运行 pytest 时，pytest 临时目录被系统拒绝访问，产生环境性假错误。改用正常文件权限后得到上表中的有效结果。

## 3. Error Check

### CRITICAL C-01：最终用户文档没有实现 100% Claim-to-render 映射

**位置**：

- `StarPlan/starplan_skills/outreach_pack.py:422-488`
- `StarPlan/starplan_skills/outreach_pack.py:491-523`
- `StarPlan/starplan_skills/outreach_pack.py:304-330`
- `StarPlan/tests/test_layer3_e2e.py:424-491`

**现象**：`outreach_pack.md` 的标题、受众、日期、地点、可观测状态、生成方式、推荐时间、峰值高度、推荐理由和设备数量由 Markdown writer 直接拼接；`render_trace.json` 只遍历 `sections.all_sentences`。Qwen 验证错误还在 `outreach_pack.py:158-160` 被直接追加到 `unconfirmed_items`，也不进入 trace。

对真实 M31 Qwen run 做逐条核对时，在去除 Markdown 列表/粗体标记并排除空行和二级标题后，共得到 39 条用户可见原子内容；只有 20 条与 trace 文本精确一致，19 条不一致。未覆盖内容包括 6 条头部事实、3 条推荐时段事实、部分最终格式化日程，以及全部带数量/备注的设备行。另有 9 条 trace 文本没有以相同最终文本出现在 Markdown 中。

当前 Layer 3 测试只证明 trace 内部条目有 Claim ID、Claim ID 在另一项测试中存在，以及 trace 与 `sentence_claim_map` 大致重叠；它没有把最终 Markdown 与 trace 做逐句/逐 hash 双向核对。因此 `25 passed` 不能证明项目计划要求的 100% 覆盖。

**状态**：未修复，阻断 Phase 3 验收。

**应如何修改**：

1. 在 `rendering.py` 增加最终文档级结构，例如 `RenderedDocument` / `RenderedBlock`。标题、元数据、推荐窗口、日程、设备数量、核对项和待确认项都必须先生成带 `claim_ids`、`variant_id`、`section`、`final_text` 的渲染对象。
2. `outreach_pack.py` 只能把这些渲染对象序列化为 Markdown，禁止再次从 `target`、`obs_result` 或 schema 对象拼事实文本。
3. `render_trace.json` 必须从最终渲染对象生成，`text_hash` 对应用户实际看到的最终原子文本，而不是格式化前的半成品。
4. 新增双向验收：每条可见事实必须恰好对应 trace；每条 trace 必须确实被交付；Claim ID 必须存在且未被禁止；variant 必须属于该 Claim 的 allowlist；hash 必须与最终文本一致。
5. 设备数量、备注等不是“纯格式”，应进入 Claim 或版本化政策 Claim；不能只给设备名称做 trace。

**验收标准**：可观测、不可观测、Qwen 成功、Qwen 失败、缺数据五类输出的双向覆盖均为 100%；任意增加一条未映射 Markdown 事实都会使测试和运行时门禁失败。

### CRITICAL C-02：运行时门禁仍然 fail-open

**位置**：`StarPlan/starplan_skills/runner.py:267-309`

**现象**：finalize 只检查必要文件是否存在，以及 trace 条目的 `claim_ids` 是否为空；不检查 Claim ID 是否真实存在、不检查 variant allowlist、不检查 hash、不检查最终文档覆盖。发现缺少必要产物或 Qwen 验证问题时，仍设置 `PASSED_WITH_WARNINGS` 并正常返回交付物。

对 `_write_render_trace` 做运行时故障注入后，系统在 `render_trace.json` 完全不存在的情况下仍返回成功，`run_outcome.json` 为 `validation_status=passed_with_warnings`、`delivery_status=template`。这与项目计划中的 fail-closed 不一致。

**状态**：未修复，阻断 Phase 3 验收。

**应如何修改**：

1. 在 `runner.py` finalize 前调用独立的 `validate_delivery_contract(run_dir, rendered_document, claims_registry)`。
2. 缺必要产物、trace 非法 JSON、未知/禁止 Claim、非法 variant、hash 不一致、可见事实未覆盖或 blocked 原文泄漏时，统一设置 `ValidationStatus.BLOCKED`。
3. 被阻断时不得返回原交付文档；`DeliveryStatus` 应为 `NOT_DELIVERED`，或只交付一个同样经过 Claim 渲染的安全错误/回退文档。
4. `PASSED_WITH_WARNINGS` 只用于不影响事实可信度的可恢复提示，不能用于证据链缺失。

**验收标准**：对缺 trace、伪造 Claim ID、删除被引用 Claim、修改 final text、修改 variant、插入额外事实、破坏 JSON 的故障注入全部得到 `validation=blocked`，且原文不在公共返回和导出目录中。

### CRITICAL C-03：Chat 仍有第二条无 Claim 事实路径，且没有完整运行合同

**位置**：

- `StarPlan/starplan_skills/runner.py:719-735`
- `StarPlan/starplan_skills/runner.py:766-835`

**现象**：Chat system prompt 要求 Qwen 调用目标、地点、可观测性三个工具后直接总结，没有强制调用 `outreach_pack`。两次真实 Chat canary 均只调用 `target_resolve`、`resolve_location`、`observability_plan`。由于没有 `pack_data`，代码走 `_build_deterministic_summary(captured)`，而不是 Claim renderer。

这两次运行都没有 `claims.json`、`render_trace.json`、`calculation_manifest.json` 或 `validation_report.md`。虽然 Qwen 原始自由文本被阻断是正确的，但最终公开文本仍来自第二条无 Claim 的事实路径。Chat 的 `run_outcome.json` 还把真实模型调用记录成 `qwen_used=false`、`model_call_count=0`。

**状态**：未修复，P3 只能标记部分完成。

**应如何修改**：

1. Chat 的 Qwen 只负责意图/工具编排；一旦目标、地点和可观测结果具备，runner 必须由代码调用 Claim builder 和统一文档 renderer，不让模型决定是否进入可信交付路径。
2. 删除 `_build_deterministic_summary` 作为公共事实输出路径，或把它改造成对统一 `RenderedDocument` 的纯展示适配器。
3. Chat 与结构化入口生成相同的 Claims、ExpressionPlan、render trace、Manifest、Validation Report 和 RunOutcome；公共返回只引用已验收交付物。
4. 目标只解析但未完成可观测计算时，不能把 `business_status` 设为 `observable`；应为 `data_insufficient` 或相应未完成状态。

**验收标准**：Chat 可观测/不可观测/API 失败/工具失败四条路径与结构化入口具有相同事实、Claim ID 和终态；不存在 `_build_deterministic_summary` 的独立事实输出；真实调用发生时 Outcome 必须记录 `called=true`。

### CRITICAL C-04：observation_review 仍允许 Qwen 自由写原因和建议，trace 来源会误标

**位置**：

- `StarPlan/starplan_skills/observation_review.py:167-184`
- `StarPlan/starplan_skills/observation_review.py:201-226`
- `StarPlan/starplan_skills/observation_review.py:350-473`

**现象**：Qwen 仍返回自由 `cause`、`evidence` 和 `suggestions`；验证主要依赖分类枚举和数字正则。无数字的因果幻觉可以通过。`review_trace.json` 依据 classification 推断 source，而不是记录真实来源。

真实闭环 canary 中，Qwen 新增“迟到引发的连锁准备仓促”，trace 却标记为 `human_report`。三个 `plan_diffs` 的 `source_cause` 使用“第一个 evidence_based/possible 原因”，导致设备检查和期望管理修订也错误指向“团队迟到”。这说明复盘 trace 是事后标签，不是可验证证据链。

**状态**：未修复，项目计划第 4 周 Evidence Claims 闭环未验收。

**应如何修改**：

1. 为复盘建立独立 `ReviewClaimRegistry`：日志事实、计划事实、偏差、候选原因、证据强度、建议和修订 diff 都要有稳定 ID 与来源。
2. Qwen 只能返回候选原因 ID、建议模板 ID、顺序和分类，不得返回原因/证据/建议自由文本。
3. 每个 `RevisedPlanDiff` 显式保存自己的 `source_claim_ids` / `source_cause_ids`，不得通过 `next(...)` 取第一个原因。
4. 模型异常不得静默 `except Exception: pass`；应写审计事件并确定性回退。
5. review report 和 review trace 从同一个最终渲染对象生成，使用与 outreach 相同的双向覆盖门禁。

**验收标准**：Mock Qwen 注入无数字的虚假因果、伪证据、自由建议、未知 ID 和错误分类时全部被阻断或降级；删除任一 Evidence Claim 后相关原因和修订自动消失或降级为 `undetermined`。

### CRITICAL C-05：无天气数据时仍生成具体气温事实

**位置**：`StarPlan/starplan_skills/claims.py:869-895`

**现象**：代码仅根据月份生成“0°C 以下”“约 5-15°C”“10°C 以下”等温度陈述，来源只标为 `approved_template.v2`。运行输入没有天气观测或预报；模板版本不能成为当地具体温度事实的证据。真实 M31 输出包含“秋季夜间气温可能降至 10°C 以下”，属于此前回退审查已要求移除、合并后重新引入的无来源事实。

**状态**：未修复，直接违反“用户可见无来源事实率为 0”。

**应如何修改**：在没有可信天气输入时只输出非事实化操作指令，例如“出发前查看当地天气预报，并按预报准备保暖/防雨物品”。只有接入带地点、时刻、来源和有效期的天气 Claim 后，才允许显示具体温度。

**验收标准**：无天气 Claim 的所有输出不含温度数值和当地天气判断；注入可信天气 Claim 后，数值、来源和有效期可追溯且过期自动失效。

### CRITICAL C-06：极昼不可观测的原因仍被错误归为 moonlight

**位置**：

- `StarPlan/starplan_skills/observability_plan.py:446-462`
- `StarPlan/tests/test_observability_edge_cases.py:26-33`

**现象**：当前原因逻辑只判断目标是否理论上达到高度/大气质量阈值；达到就归为 `moonlight`，没有判断是否存在天文黑夜。手工运行 M31、纬度 70 度、2026-06-21 时，结果为：`is_observable=false`，太阳最低高度 `+3.44°`，但 `not_observable_reason=moonlight`，建议文案也错误声称“月光影响严重”。

现有 edge test 只断言 `is_observable is False` 和太阳在地平线上，没有断言 `not_observable_reason` 与用户文案，所以 `5 passed` 掩盖了错误归因。

**状态**：未修复，科学边界 P4 只能标记部分完成。

**应如何修改**：

1. 增加 `no_astronomical_night`（或 `daylight/twilight`）原因码。
2. 原因优先级至少为：纬度永久受限 -> 无天文黑夜 -> 高度/大气质量 -> 月光；月光只能在存在暗夜且目标本可满足几何约束时成立。
3. 对无暗夜场景输出“该日期没有满足阈值的天文黑夜”，建议换日期，不得提月光。
4. 扩展 edge test，精确断言 reason code、blocking Claim 和最终取消/改期文案。

**验收标准**：极昼、白夜、月光阻断、季节性低高度、永久纬度受限五种案例的 reason code 和公开文案各自正确且互不混淆。

### WARNING W-01：模型调用事实没有从真实事件聚合

**位置**：`StarPlan/starplan_skills/runner.py:294-300`、`StarPlan/starplan_skills/runner.py:825-833`

真实复盘 run 的 `model_call_log.jsonl` 有 2 个 `model_call`（`expression_plan`、`review_attribution`），Outcome 只记 1；真实 Chat 有多轮调用，Outcome 记 0。runner 仍根据最终 `outreach.qwen_used` 手工推断调用事实。

**修改要求**：统一 model-call 事件 schema，由 `qwen_client` 每次真实请求追加事件；finalize 从日志聚合 `called/successful/accepted_for_delivery/count/models/stages`。失败调用和未采用调用也必须计入 `called`。

### WARNING W-02：真实 Qwen 集成测试与公共 API 契约漂移

**位置**：`StarPlan/tests/test_qwen_integration.py:150-174`

公共 API 已用 `tools_called` 取代原始 `tool_call_log`，测试仍读取旧字段，导致真实 canary 固定失败。测试也只检查 verification 中存在 `passed` 字段，没有验证其值、最终内容来源或 Claim artifacts。

**修改要求**：公共断言使用 `tools_called`、`model_text_accepted_for_delivery` 和 `public_output_validation`；需要审计细节时读取受控 run artifact。必须增加“最终公开文本逐句在 render trace 中”“blocked 原文不在公共返回/导出中”的断言。

### WARNING W-03：trace section 顺序不稳定

**位置**：`StarPlan/starplan_skills/outreach_pack.py:326`

`sections` 从 Python `set` 直接序列化，不同进程可能产生不同顺序，影响产物复现和 hash。

**修改要求**：按固定 section order 输出，未知 section 排到末尾并按名称排序。

### WARNING W-04：模型异常和隐私审计仍不完整

- `observation_review.py:183-184` 静默吞掉模型异常，Outcome 无法区分未调用、调用失败和结果被拒绝。
- `qwen_client.py:482-500` 默认保存 prompt/content preview；复盘 prompt 可能包含用户自由备注。当前示例无私人数据，但真实使用需要字段级脱敏、保留期和受控导出策略。

**修改要求**：异常写结构化安全事件；日志默认保存 hash、长度、状态和脱敏摘要，不保存完整自由备注或内部提示词。

### INFO：已确认有效的部分

1. M31/M42 主案例天文计算与 astroplan 独立实现一致。
2. 月距、目标高度、暮光和月相的当前固定案例未发现数值回归。
3. 离线模型 tripwire 有效，真实 Qwen 原始总结在 Chat 中不会直接返回用户。
4. 可观测与不可观测的业务状态已分离，不可观测案例可以合法 `validation=passed`。
5. 150 个内置目标的数据验证和来源快照当前可复现。

## 4. Completion Status

| 工作包 | 团队声称 | 独立验收结论 | 主要未完成项 |
|---|---|---|---|
| P1 Claim-first rendering | 完成 | 部分完成 | 最终 Markdown 仍有直接拼接事实；trace 非双向覆盖 |
| P2 RunOutcome/finalize | 完成 | 部分完成 | 证据链缺失只 warning；模型调用计数不真实 |
| P3 Chat 统一 | 完成 | 部分完成 | 未强制 outreach/Claims；第二事实路径和完整 artifacts 缺失 |
| P4 科学边界 | 完成 | 部分完成 | M31/M42 主案例通过；极昼原因仍错误 |
| 项目计划第 3 周 | 已完成 | 未通过最终 gate | 100% 映射和 fail-closed 未实现 |
| 项目计划第 4 周 | 已完成/已合入 | 未通过 | ReviewExpressionPlan/Evidence Claims 未实现，复盘来源误标 |

当前没有发现 M31/M42 主案例的基础天文计算错误，但可信交付和复盘证据链的剩余问题足以影响比赛演示的可辩护性。不能以 `145 passed` 或真实 API 可用替代架构验收。

## 5. Phase Plan

### Phase A：冻结最终渲染合同并修复运行时门禁（最高优先级）

**修改范围**：`claims.py`、`rendering.py`、`outreach_pack.py`、`expression_validator.py`、`runner.py`、Layer 3/adversarial tests。

**工作项**：

1. 定义 `RenderedDocument`、原子文本边界、Markdown 序列化规则和双向 trace 规则。
2. 把头部、推荐理由、设备数量、回退/待确认文本全部纳入 Claim 与最终渲染对象。
3. 实现 `validate_delivery_contract`，将证据链错误统一升级为 BLOCKED。
4. 先写 7 个故障注入测试：缺 trace、坏 JSON、伪 Claim、删 Claim、错 variant、改 hash、插入额外事实。

**验收**：可观测/不可观测/Qwen 成功/Qwen 失败/缺数据输出全部双向覆盖 100%；7 个故障注入全部 blocked；完整离线套件无回归。

**风险**：如果继续在 Markdown writer 上补正则或关键词，将再次形成不完备的事后过滤。必须以最终渲染对象为唯一事实出口。

### Phase B：统一 Chat 与结构化入口

**修改范围**：`runner.py`、`qwen_client.py`、`test_qwen_integration.py`、Chat 对抗测试。

**工作项**：

1. Chat 工具调用完成后由代码强制构建 Claims 和交付物。
2. 删除第二事实路径，补齐完整运行目录合同。
3. 从真实 model-call 事件聚合 Outcome。
4. 更新真实 canary 到当前公共 API，并增加产物/泄漏断言。

**验收**：结构化和 Chat 对同一输入得到相同核心 Claim 集、相同业务状态和相同公开事实；Chat 四条终态都有完整 Outcome/Manifest/Report；真实 canary 不再因旧字段失败。

### Phase C：完成复盘 Evidence Claim 架构

**修改范围**：`observation_review.py`、`schemas.py`、`rendering.py`、`run_outcome.py`、复盘测试。

**工作项**：建立 Review Claims 与 ID-only ExpressionPlan；修订项保存精确因果 ID；统一 review trace；记录模型失败/拒绝/采用状态。

**验收**：无数字因果幻觉也会被阻断；Qwen 不能创建新原因文本；删除证据后结论自动降级；真实复盘 run 的来源和调用数与日志一致。

### Phase D：关闭科学和事实边界回归

**修改范围**：`observability_plan.py`、`claims.py`、edge tests、not-observable tests。

**工作项**：新增无天文黑夜原因码与优先级；移除无天气输入的具体温度；增加极昼最终文案测试。

**验收**：五类不可观测原因分类准确；无天气 Claim 时温度事实为 0；astroplan 12 项交叉校验和 5 个 edge cases 继续通过。

### Phase E：统一证据、文档和合并门禁

**修改范围**：`run_offline_ci.bat`、README、`skills.yaml`、项目完成报告、CI/合并规则。

**工作项**：把离线 145、Layer 1/2/3、故障注入、三案例和低频在线 canary 分层；文档只声明已通过的 gate；强制科学分支以最新 main 为基线。

**验收**：一条离线命令可在干净环境完成所有阻断 gate；在线 canary 独立运行；任何受保护文件冲突必须逐行处理；完成报告中的每个数字可由命令复现。

## 6. Blocking Items And Risks

1. **阻塞项**：C-01 至 C-05 关闭前，不得宣告幻觉防护架构完成；C-06 关闭前，不得宣告全部科学边界完成。
2. **合并风险**：科学修改再次直接改 `claims.py`/`outreach_pack.py` 时，容易重新引入无来源模板事实。必须在独立分支上通过 Claim/Layer 3 gate 后再合并。
3. **测试假阳性风险**：只验证 trace 自身、只断言输出存在或只断言 `is_observable`，会继续掩盖最终交付和原因归因错误。
4. **真实模型波动风险**：在线 canary 可能受容量、速率和模型行为变化影响，只能证明兼容性；离线 Mock 和确定性 gate 才是合并阻断依据。
5. **隐私风险**：真实观察备注进入 prompt preview 前需要脱敏策略；API key 必须继续只通过 `.env` 加载且不得出现在产物、日志和提交中。

## 7. Immediate Next Actions

1. 先新增 C-01/C-02 的失败测试，冻结最终文档原子文本和 BLOCKED 语义。
2. 完成统一 `RenderedDocument` 与运行时 gate，再改 Chat；不要先继续增加科学特性或新输出格式。
3. 让 Chat 无条件进入 Claim renderer，并更新两个过期真实集成测试。
4. 完成 Review Claims/ID-only 归因，修复 source 和 plan-diff 因果映射。
5. 最后处理极昼原因与天气事实，重跑：编译、3 个 Schema、145+ 离线测试、Layer 1/2/3、故障注入、三案例、astroplan 交叉校验和一次真实 canary。

## 8. 审查期间的文件处理

- 未修改任何业务代码、测试或数据。
- 新增本报告作为本次有意义审查工作的强制交付物。
- 保留工作区中原有的 `confidence_test_results.json` 修改和 guidance 归档移动；这些不属于本次审查提交范围。
- `.env` 中的 key 仅由进程读取；审查未显示、复制或写入 key。
