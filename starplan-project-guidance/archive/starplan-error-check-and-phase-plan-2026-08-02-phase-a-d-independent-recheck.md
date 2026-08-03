# StarPlan 错误检查与阶段计划 - Phase A-D 独立复查（2026-08-02）

## 1. 审查基线与结论

- 审查提交：`b8c596ba2432b3634a91492a8cae3d114f8e455a`（`Phase A-D: close 6 CRITICAL + 4 WARNING from independent audit`）。
- 远端状态：本地 `HEAD`、`origin/main` 与 GitHub `main` 均为 `b8c596b`；审查开始时工作区干净。
- 对照材料：`starplan-error-check-and-phase-plan-2026-08-02-phase-a-d-completion.md`、`starplan-loop-project-plan.md`、2026-08-01 合并后独立验收报告。
- 验收口径：检查最终用户实际取得的文本和对象，不以“测试退出码为 0”或产物之间哈希一致替代事实语义验证。
- 总结：M31/M42 主路径、极昼/纬度边界、天气文字修复、Layer 1/2/3 数据验证和 astroplan 数值交叉校验均未发现新的科学回归；但 Claim 与最终文本的语义绑定、持久化证据产物完整性、结构化/Chat 的 fail-closed 公共返回、复盘 ID-only 协议仍未实现。Phase A-C 不能验收为完成；Phase D 的科学分类已通过，但离线 IERS 配置只存在于 pytest，正常运行路径仍可能失败。

## 2. 运行验证结果

| 验证项 | 结果 | 说明 |
|---|---:|---|
| Python 编译检查 | PASS | `starplan_skills`、`scripts`、`tests` 可编译 |
| 离线 pytest 全量 | 155 passed | 在有正常临时目录权限的有效运行中完成；完成报告中的 `153 passed` 已过时 |
| Delivery Contract 专项 | 10 passed | 证明现有 7 类注入会被拦截，但没有覆盖联动篡改和证据文件内容损坏 |
| 科学 edge cases | 5 passed | 极昼为 `no_astronomical_night`，纬度受限路径正确 |
| Layer 1 | 150 目标 x 10 轮，0 问题 | 数据范围和冲突检查通过 |
| Layer 2/3 | 150 目标 x 10 轮，0 问题 | 来源、坐标、星等、角大小、别名和类型检查通过 |
| astroplan 交叉校验 | 12/12 passed | 显式设置 `iers.conf.auto_download=False`、`auto_max_age=None` 后约 8 秒完成 |
| `cross_validate.py` 默认直接运行 | FAIL | 304 秒超时；脚本不加载 `conftest.py` 的 IERS 离线设置 |
| 真实百炼集成 | 8 passed + 1 transient fail | 9 条用例中的 NL 日志用例收到一次空响应；独立 canary 和同一用例重试通过（`1 passed in 17.41s`） |
| 真实 M42 Chat | 业务路径 PASS | `not_observable`、合同 passed；但公开状态、调用计数和证据产物不一致 |

说明：首次受限 pytest 运行的 11 failures / 5 errors，以及在线 pytest 结束时的临时目录清理错误，均由 Windows 临时目录权限造成，不计为业务失败。真实百炼密钥只由 `.env` 加载，审查没有显示、复制或提交密钥。

## 3. Error Check

### CRITICAL C-01：Claim ID、variant 和 hash 可以与任意事实文本联动伪造

**位置**：

- `StarPlan/starplan_skills/expression_validator.py:335-427`
- `StarPlan/starplan_skills/rendering.py:742-750`
- `StarPlan/starplan_skills/rendering.py:821-836`
- `StarPlan/starplan_skills/templates.py:352-356`

**复现**：把合法句子“今晚我们要观测的是 M31”替换为虚假事实，保留 `claim_ids=["target.standard_name"]` 和 `variant_id="target_name_v1"`，并同步更新 RenderedDocument、Markdown、trace、sentence map 和 hash。`validate_delivery_contract()` 仍返回 `passed=true`、0 errors、0 warnings。证据目录为 `StarPlan/runs/audit_semantic_binding_20260802` 和 `StarPlan/runs/audit_contract_adversarial_20260802`。

**原因**：门禁只验证 ID 存在、variant 在 allowlist、hash 与当前文本一致、几个产物互相一致；它没有根据 Claim 值和批准模板重新生成期望文本。`RenderedBlock` 允许调用方直接传入任意 `final_text`。例如推荐理由包含峰值高度、airmass、持续时长和约束阈值，却只映射到 display value 为时间窗口的 `obs.recommended_window`。

**状态**：未修复，继续阻断 Phase A 和项目计划第 3 周验收。

**应如何修改**：

1. 在 `rendering.py` 增加唯一的 `render_claim_block(...)` / `render_composite_block(...)` 构造入口；调用方只能传 Claim ID、批准 variant ID 和结构化组合参数，`final_text` 必须由该入口内部生成。
2. 单 Claim 句在 `expression_validator.py` 中重新执行批准模板渲染，并要求结果与 `block.final_text` 精确一致。
3. 多 Claim 句必须使用显式的 composite variant schema，声明每个占位符对应的 Claim ID；不能用一个时间 Claim 为整段推荐理由背书。
4. 为 `obs.recommended_window.reason` 建立独立 Claim，或把峰值高度、airmass、持续时间、约束阈值全部作为 composite Claim 输入；source hash 必须绑定这些实际值。
5. `meta_passthrough_v1` 不能继续同时覆盖“受众: ...”“日期: ...”“地点: ...”等不同前缀句。应为每类元数据定义可重放的批准模板，或让 Claim 的规范显示值就是完整最终句。

**验收标准**：同步修改文本、trace、map 和全部 hash 的联动篡改仍必须 BLOCKED；每个 block 都能由持久化 Claim Registry + variant schema 独立重放得到同一文本；禁止存在接受任意 `final_text` 的公共构造路径。

### CRITICAL C-02：三个必需证据产物内容损坏仍可通过门禁

**位置**：

- `StarPlan/starplan_skills/expression_validator.py:300-313`
- `StarPlan/starplan_skills/expression_validator.py:443-468`
- `StarPlan/starplan_skills/runner.py:288-305`
- `StarPlan/tests/test_delivery_contract_gate.py:100-130`

**复现**：分别把 `claims.json` 写成非法 JSON、把 `expression_plan.json` 写成非法 JSON、把 `sentence_claim_map.json` 写成空对象。三个案例均返回 `passed=true`、0 errors、0 warnings。证据目录为 `StarPlan/runs/audit_required_artifact_integrity_20260802`。

**原因**：D1 只检查文件存在。门禁使用 runner 重新构造的 `AllowedClaimsBuilder`，没有解析和使用本次运行落盘的 `claims.json`；不验证 `expression_plan.json`；sentence map 只检查“恰好存在的 key 是否一致”，缺少 key 不报错。现有“删除 Claim”测试实际修改的是 RenderedDocument 引用，并没有从持久化 Claim Registry 删除 Claim。

**状态**：未修复，证据链不能作为可复现或防篡改证明。

**应如何修改**：

1. `validate_delivery_contract` 必须从 `claims.json` 反序列化并验证 schema、唯一 ID、Claim 类型、source refs、source hash 和 variant allowlist；这个持久化 Registry 才是交付门禁的权威输入。
2. 解析 `expression_plan.json`，验证其 schema、被接受/回退模式、选择项与最终渲染 block 的关系；非法、空或不一致都 BLOCKED。
3. `sentence_claim_map.json` 必须与 RenderedDocument 形成精确双射：缺 key、多 key、重复文本歧义、空 map、非法 JSON都 BLOCKED，不能降级为 warning。
4. 校验 `rendered_document.json` 本身，并让 validator 接收路径或已验证反序列化对象，避免调用者传另一个内存对象绕过落盘产物。
5. 新增三条当前会失败的故障测试，并把“删除 Claim”改为真正删除 `claims.json` 中被引用条目。

**验收标准**：任一必需 JSON 非法、空、缺字段、被引用 Claim 缺失、表达计划与渲染结果不一致时均 BLOCKED 且无公共交付。

### CRITICAL C-03：结构化入口 BLOCKED 后仍通过公共返回泄漏活动包

**位置**：

- `StarPlan/starplan_skills/runner.py:331-342`
- `StarPlan/starplan_skills/runner.py:380-388`

**复现**：强制 validator 返回失败后，`run_outcome.json` 正确记录 `validation_status=blocked`、`delivery_status=not_delivered`，磁盘上的 `outreach_pack.md` 也被删除；但 `run_starplan()` 返回对象仍包含完整 `outreach_pack`、15 条 talking points 和已经失效的 Markdown 路径。证据目录为 `StarPlan/runs/audit_blocked_public_return_20260802`。

**状态**：未修复，项目要求的“原文泄漏率为 0”未满足。

**应如何修改**：

1. `runner.py` 只允许从最终 `RunOutcome` 生成公共返回；当 validation 为 BLOCKED 或 delivery 为 NOT_DELIVERED 时，`outreach_pack`、`review` 和任何事实文本字段必须为 `null` 或完全省略。
2. 返回一个不含天文事实的稳定错误结构，例如 `status`、`run_id`、`error_code=DELIVERY_VALIDATION_BLOCKED`、`safe_message` 和可审计路径。
3. 清除或隔离所有已构造但未交付对象中的导出路径，不能返回一个已经删除的文件路径。
4. 新增 runner 级故障注入：mock validator 失败后同时断言磁盘、返回对象和日志中没有被阻断交付内容。

**验收标准**：结构化入口的 gate 失败时，调用者拿不到任何活动包事实、复盘文本或失效路径；只保留安全错误和审计标识。

### CRITICAL C-04：Chat 的最终文本和终态仍不受同一个交付合同控制

**位置**：

- `StarPlan/starplan_skills/runner.py:841-866`
- `StarPlan/starplan_skills/runner.py:938-970`
- `StarPlan/starplan_skills/runner.py:989-1001`

**复现**：强制 Chat 合同失败后，Outcome 为 blocked，但 delivery 仍是 `template`；`outreach_pack.md` 未删除；公共返回仍包含 335 字 Claim 摘要，并把 `public_output_validation` 标为 passed。Chat 也不生成 `calculation_manifest.json` 和 `validation_report.md`。证据目录为 `StarPlan/runs/audit_chat_blocked_return_20260802`。

真实 M42 Chat 进一步显示：最终 Claim 文本合同 passed、Outcome passed，但因为已被丢弃的 Qwen 原文含不可溯源数字，`public_output_validation` 反而为 blocked。该字段描述的是被阻断模型原文，不是公共输出。

**原因**：合同校验的是 `outreach_pack.md`，公共 `final_content` 又由 talking points 和替代建议重新拼接；合同异常和缺产物被降为 `PASSED_WITH_WARNINGS`；最终返回不检查 RunOutcome。Chat 还没有复用结构化入口的 Manifest/Validation Report finalize 流程。

**状态**：未修复，Phase B 和项目计划第 3 周统一出口未验收。

**应如何修改**：

1. Chat 和结构化入口必须共享同一个 `finalize_delivery(rendered_document, registry, run_dir)`；最终公共文本直接序列化已验收 RenderedDocument，不能再次拼接事实。
2. 若 Chat 需要短摘要，建立独立、可追踪的 `public_summary_document.json` 和对应 trace，并对该文档本身执行同一语义门禁。
3. 合同失败、异常或必需产物缺失统一设置 BLOCKED + NOT_DELIVERED，删除/隔离未交付 Markdown，并返回无事实安全错误。
4. Manifest、Validation Report、RunOutcome 必须由共享 finalize 生成，Chat 不得缺少其中任一项。
5. `public_output_validation` 只表示最终公共输出合同结果；另设 `model_text_status=rejected_untraceable` 记录被丢弃的 Qwen 原文。

**验收标准**：Chat 的 observable、not_observable、API failure、tool failure、contract failure 五条路径与结构化入口具有相同终态和证据产物；Outcome blocked 时公共返回不含事实文本。

### CRITICAL C-05：observation_review 仍接受无数字的自由原因、证据和建议

**位置**：

- `StarPlan/starplan_skills/observation_review.py:188-208`
- `StarPlan/starplan_skills/observation_review.py:328-383`
- `StarPlan/starplan_skills/observation_review.py:404-527`

**复现**：Mock Qwen 返回无数字虚假内容：原因 `Mars caused the cloud cover`、证据 `The stars were angry`、建议 `Replace the telescope because it is cursed`。三者均被接受；原因还被标为 `evidence_based`，并进入 `ObservationReview`、`review_report.md` 和 `revised_plan.json`。证据目录为 `StarPlan/runs/audit_review_text_hallucination_20260802`。

**原因**：当前所谓“ID-based attribution”是在接受自由文本后由代码临时分配 `cause.qwen.N`，不是让模型从允许表中选择稳定 ID。验证只限制分类枚举和部分数字。review report 仍由直接 Markdown writer 生成，没有 Review Claim Registry、RenderedDocument 或双向门禁。

**状态**：未修复，完成报告把该项降为 INFO 不成立；它正是原 C-04 和项目计划第 4 周的核心验收条件。

**应如何修改**：

1. 建立 `ReviewClaimRegistry`：计划事实、日志事实、偏差、候选原因、证据强度、建议模板和修订 diff 全部使用稳定 ID 和版本化来源。
2. Qwen 只能返回 `cause_id`、`suggestion_variant_id`、分类和顺序；禁止返回 cause/evidence/suggestion 自由文本。
3. 分类上限由代码按证据类型决定。例如仅有人类备注时，模型不能把候选原因提升为 `evidence_based`。
4. 每个 plan diff 必须保存自己的 `source_claim_ids` / `source_cause_ids`；删除或降级证据时，相关原因和修订自动消失或降级。
5. review report、review trace 和 revised plan 从同一个已验收 Review RenderedDocument 派生，并执行语义重放和双向覆盖门禁。

**验收标准**：上述三条无数字虚假文本、未知 ID、伪证据、错误分类和自由建议全部被拒绝；Qwen 不能创建任何新的用户可见事实文本。

### CRITICAL C-06：IERS 离线修复只作用于 pytest，正常运行和交叉校验仍会失败

**位置**：

- `StarPlan/conftest.py:1-16`
- `StarPlan/starplan_skills/observability_plan.py`
- `StarPlan/scripts/cross_validate.py`

**复现**：不手工设置 Astropy IERS 配置，直接调用 `compute_observability()` 会因本地 IERS-A 预测数据超过 30 天而抛 `ValueError`；`cross_validate.py` 默认运行在 304 秒后超时。手工设置 `auto_download=False` 和 `auto_max_age=None` 后，同一计算和 12 项交叉校验正常完成。

**原因**：`conftest.py` 只在 pytest 进程加载，不能保护 CLI、Chat、演示应用和独立脚本；这不满足项目计划“无在线天文服务时核心计算仍可复现”。

**状态**：科学数值本身未发现错误，但离线运行合同未修复。

**应如何修改**：

1. 在天文计算包内建立统一的 IERS policy helper，由 `observability_plan`、交叉校验脚本和所有入口在计算前调用；不要把运行时可靠性放在 `conftest.py`。
2. 比赛复现包优先固定一个带版本和 hash 的 IERS / leap-second 数据快照；离线模式显式使用该快照，在线更新作为可选维护动作。
3. 记录本次使用的数据版本、有效期和 degraded-accuracy 状态到 Manifest；不要全局忽略相关 warning。
4. 增加干净缓存、禁网子进程测试，直接运行 `run_case.py` 和 `cross_validate.py`，验证既不下载也不挂起。

**验收标准**：清空/隔离用户 Astropy 缓存并禁网后，三个固定案例和 12 项交叉校验在限定时间内完成；结果记录数据快照版本且无未解释的 IERS 失败。

### WARNING W-01：真实模型调用仍没有正确聚合到 RunOutcome 和 Manifest

**位置**：

- `StarPlan/starplan_skills/runner.py:321-327`
- `StarPlan/starplan_skills/runner.py:869-883`
- `StarPlan/starplan_skills/runner.py:972-979`
- `StarPlan/starplan_skills/run_outcome.py:168-183`
- `StarPlan/starplan_skills/run_outcome.py:228-241`

真实 M42 Chat 的日志有 3 个 `model_call`，公共返回为 3，Outcome 却为 1。四个真实 Chat 目录中，日志计数分别为 16、15、3、3，Outcome 全部为 1；前两个目录还混入同名 run 的旧调用。原因是 Chat 只向 Outcome 加一个 `type=model_call_summary` 事件，`to_audit_summary()` 取事件列表长度，Manifest 又只识别 `type=model_call`。结构化闭环也只手工添加 outreach 事件，未聚合 review 等真实调用。

**修改要求**：以 `model_call_log.jsonl` 的规范化真实事件为单一来源；聚合 called/succeeded/accepted/count/models/stages，失败和未采用调用也计入 called；RunOutcome 和 Manifest 使用同一聚合对象。增加断言 `log model_call count == outcome count`。

### WARNING W-02：Claim source hash 没有绑定实际陈述输入

**位置**：

- `StarPlan/starplan_skills/claims.py:793-900`
- `StarPlan/starplan_skills/claims.py:1064-1106`
- `StarPlan/starplan_skills/rendering.py:821-836`

所有 meta Claims 共用只包含 `{"type":"meta","version":"v1"}` 的 hash，没有绑定目标、受众、日期、地点、可观测状态或模型采用状态。极昼 blocking Claim 的文本使用 reason code、日期、太阳阈值和最大高度，但 source refs/hash 只绑定 eliminated windows 的 constraints。推荐理由也没有绑定其显示的全部数值。

**修改要求**：每条 Claim 的 source hash 必须哈希产生该 display value 的规范化实际输入；复合句保存完整 source Claim ID 集，validator 可重新计算并核对 hash。

### WARNING W-03：百炼容量/空响应缺少有界重试和明确降级

真实 9 条在线套件中，NL parse 一次收到空响应并抛 ValueError；20 秒后独立 canary 和同一测试重试均通过，说明是瞬时模型/API故障，不是固定解析错误。

**修改要求**：`qwen_client.py` 对明确的 capacity、429、可恢复 5xx 和传输错误执行有上限的指数退避；记录 provider error code、attempt、最终状态。重试耗尽后返回结构化 `model_unavailable`，NL/Chat 进入 NEEDS_CONFIRMATION 或安全失败路径，不能把空响应伪装为普通 JSON 解析失败。在线 canary 只做兼容性监控，不作为离线合并门禁。

### WARNING W-04：run_id 可复用导致日志和旧产物跨运行污染

`get_run_dir()` 对已存在目录直接复用，模型日志使用 append。真实 `test_chat_integration` 和 `test_chat_tools` 因固定 run_id 分别累计 16 和 15 条调用，而单次正常 Chat 为 3 条。这会污染模型计数、hash、失败诊断和复现证据。

**修改要求**：生产 run_id 必须唯一且目录不可变；已存在时拒绝、生成新 attempt ID 或创建子目录，禁止静默覆盖/追加。测试使用 pytest 临时唯一 run_id，并断言目录只含本次调用。

### WARNING W-05：Chat 原始审计内容的隐私边界仍未关闭

`chat_conversation.json` 保存完整 `user_input`、messages 和 blocked model content。复盘备注可能包含成员信息或自由文本。完成报告的 W-04 只处理模型异常，没有处理上一轮报告同时指出的日志隐私问题。

**修改要求**：默认只保存 hash、长度、状态、脱敏摘要和必要工具调用；完整 prompt/response 需显式 debug 开关、访问控制和保留期限。测试注入邮箱、手机号、姓名等字段并断言默认日志已脱敏。

### WARNING W-06：完成报告和测试说明已与当前仓库漂移

- 完成报告声称离线 `153 passed`，当前有效结果为 `155 passed`。
- 完成报告写“真实 Qwen 11 条”或后续计划“4 条”，当前 `test_qwen_integration.py` 实际为 9 条。
- 完成报告把 review ID-only / RenderedDocument 缺失列为 INFO，却同时把 Phase C 标为“核心已完成”，与项目计划第 4 周验收条件冲突。

**修改要求**：报告数字由 CI 机器可读摘要生成；阶段状态只由验收 gate 决定，未实现的核心 gate 不得降级为 INFO 后宣告完成。

### INFO：已确认有效的修复

1. 无天气 Claim 时未再生成具体气温事实。
2. 极昼/白夜路径能输出 `no_astronomical_night`，不再误归因 moonlight。
3. 纬度永久受限路径能建议换地点而不是换日期。
4. M31 可观测和 M42 不可观测的主要天文数值与 astroplan 当前固定案例一致。
5. Qwen 原始 Chat 自由总结不会直接作为最终文本返回；当前漏洞在于替代文本和终态没有由同一个合同约束。
6. trace section 排序和 review 模型异常审计已有改进，但不足以替代上述未完成 gate。

## 4. Completion Status

| 工作包 | 完成报告声称 | 独立复查结论 | 阻塞项 |
|---|---|---|---|
| Phase A | 已完成 | 未通过 | 文本可与 Claim 联动伪造；必需证据 JSON 损坏仍 pass |
| Phase B | 已完成 | 未通过 | 结构化/Chat blocked 仍公开事实；Chat 缺 Manifest/Report；调用数失真 |
| Phase C | 核心已完成 | 未通过 | Qwen 仍自由生成原因、证据、建议；review 无 Claim/RenderedDocument gate |
| Phase D | 已完成 | 科学内容通过，运行合同未通过 | IERS 修复仅在 pytest，禁网正常入口可失败/挂起 |
| 项目计划第 3 周 | 已完成 | 未验收 | 原始模型文本已隔离，但 Claim 语义和公共 fail-closed 未达到 0 泄漏 |
| 项目计划第 4 周 | 核心已完成 | 未验收 | Evidence Claims 和 ID-only review 尚未实现 |

当前可准确声明的是：“主要天文计算和已覆盖科学边界通过；可信输出基础结构已搭建，但语义门禁、公共交付终态和复盘证据链仍有阻断缺陷。”不能继续声明“6 CRITICAL + 4 WARNING 全部关闭”或“Phase A-D 全部完成”。

## 5. Phase Plan

### P0：冻结错误完成声明并补失败测试（先做）

**修改范围**：`test_delivery_contract_gate.py`、runner 对抗测试、review 对抗测试、当前完成报告/README 状态说明。

**工作项**：

1. 把 C-01 至 C-06 的复现固化为失败测试，不先改实现让测试假绿。
2. 增加联动篡改、非法 claims、非法 expression plan、空 map、结构化 blocked 返回、Chat blocked 返回、无数字 review 幻觉和禁网 IERS 子进程用例。
3. 文档将 Phase A-C 恢复为“进行中/未验收”，Phase D 标为“科学修复通过、离线运行 gate 待关闭”。

**验收**：每个缺陷都有一个当前失败、修复后通过的端到端断言；报告测试数与收集结果一致。

### P1：完成可重放 Claim 语义门禁

**修改范围**：`claims.py`、`templates.py`、`rendering.py`、`expression_validator.py`、`outreach_pack.py`。

**工作项**：建立单 Claim/composite Claim 的可重放模板协议；持久化 Registry 成为权威输入；所有必需 JSON 做 schema 和一致性验证；source hash 绑定实际输入。

**验收**：联动修改全部文本和 hash 仍被阻断；非法/空证据文件全部阻断；可观测、不可观测、Qwen 成功、Qwen 失败、缺数据五类文档可从 Claim + variant 独立重放。

### P2：统一结构化与 Chat 的公共交付终态

**修改范围**：`runner.py`、`run_outcome.py`、`qwen_client.py`、Manifest/Validation Report writer、Chat tests。

**工作项**：共享 finalize；Outcome 驱动公共返回；blocked 无事实交付；Chat 短摘要本身进入文档门禁；真实模型日志精确聚合；run 目录唯一不可变。

**验收**：五类 Chat 终态和结构化入口一致；blocked 返回 0 事实；每个 Chat run 有 Claims、trace、Manifest、Report、Outcome；日志调用数与 Outcome/Manifest 完全一致。

### P3：完成 Review Claim Registry 和 ID-only 协议

**修改范围**：`observation_review.py`、`schemas.py`、`rendering.py`、review trace/report tests。

**工作项**：预定义候选原因/建议/修订模板；模型只选 ID；证据强度由代码封顶；review report 和 revised plan 由同一已验收文档派生。

**验收**：无数字自由幻觉、未知 ID、伪证据和越权分类均无法进入用户输出；删除证据会自动降级或删除结论和修订。

### P4：关闭离线数据与在线容量运行合同

**修改范围**：统一 Astropy 数据 policy、`cross_validate.py`、CLI/演示入口、`qwen_client.py`。

**工作项**：固定 IERS/leap-second 快照；禁网干净缓存测试；百炼可恢复错误有限重试；重试耗尽的安全状态和可观测日志。

**验收**：禁网新环境下三案例与 12 项交叉校验限时通过；容量错误不会中断为无上下文 ValueError，也不会返回模型原文。

## 6. Blocking Items And Risks

1. C-01/C-02 不关闭时，现有 Claim 证据链只能证明“文件自洽”，不能证明“句子获准”。
2. C-03/C-04 不关闭时，Outcome 的 BLOCKED 状态不能阻止调用者取得事实内容，fail-closed 只是磁盘层局部行为。
3. C-05 不关闭时，比赛案例三仍是模型自由归因，无法回答“模型完全错误时用户看到什么”。
4. 只继续增加关键词、数字正则或 hash 检查会重复事后过滤问题；修复必须落在可重放模板和 ID-only 协议上。
5. 在线 canary 有容量波动，必须与离线确定性 merge gate 分开；不能因 canary 偶发成功而忽略安全回退。

## 7. Immediate Next Actions

1. 先提交 C-01 至 C-06 的失败测试和文档状态更正，禁止继续对外声明 Phase A-D 完成。
2. 按 P1 完成 Claim 语义重放和持久化证据文件验证，这是后续 Chat/review 统一的前置条件。
3. 按 P2 修复两个 BLOCKED 公共返回泄漏，并让 Chat 复用共享 finalize。
4. 按 P3 完成 review ID-only；在此之前关闭真实用户复盘中的 Qwen 自由补充，使用确定性规则结果。
5. 最后关闭 IERS 运行时和百炼容量错误合同，重跑 155+ 离线、全部新增对抗测试、Layer 1/2/3、12 项交叉校验、M31/M42 Chat 和 9 条真实 canary。

## 8. 审查期间的文件处理

- 未修改业务代码、测试或数据。
- 新增本独立复查报告作为本次强制交付物。
- 动态故障注入和真实 canary 产物位于 `StarPlan/runs/`，由现有 `.gitignore` 排除。
- `.env` 密钥未显示、未复制、未写入报告或提交。
