# StarPlan Loop 错误检查与阶段计划 - 2026-07-30 独立复查

日期：2026-07-30
审查基线：`main` / `c6c9f11`（审查开始时与 `origin/main` 一致）
审查范围：团队为落实幻觉预防架构而提交的 P0、P1、P2 代码、测试、报告与固定案例运行产物
审查性质：独立验证；未修改生产代码；本文件仅记录问题、验收差距和修复顺序

## 1. Error Check

### 1.1 结论

当前版本能够编译，示例、Layer 1、Layer 2/3 和三个固定案例的主路径可以运行，但**尚未达到 project plan 的可信输出验收标准**。团队报告中的“RunOutcome 完成”“Evidence Claims 完成”“100% Claim 映射”“隐私导出安全”“离线 CI 可直接运行”等结论均存在与实际代码或运行产物不一致之处。

因此，本次判定为：**运行基线部分通过，架构验收不通过；第 3 周和第 4 周均不能关闭，第 5 周演示入口暂不应启动。**

### 1.2 静态与定向运行问题

| 严重度 | 问题 | 证据 | 状态与应如何修改 |
|---|---|---|---|
| CRITICAL | Claim 篡改保护无效 | `StarPlan/starplan_skills/claims.py:100-105` 的 `registry_hash` 每次访问都从当前 Claim 重算；`StarPlan/starplan_skills/expression_validator.py:230-246` 又用当前 Claim 重算值与该动态值比较。定向反例把视星等 Claim 从 `3.4` 改为 `99.9`，保留旧 `source_hash`，验证仍返回 `passed=true`。 | 未修复。构建 Registry 时冻结 `registry_hash`；验证时从不可变源快照和规则版本重新构建或重算每个 Claim，而不是信任内存中的 Claim 对象。任意 Claim、源快照、规则或 Registry 改动都必须进入 `VALIDATION_BLOCKED`。 |
| CRITICAL | 确定性模板仍绕过 Claim Registry | `StarPlan/starplan_skills/outreach_pack.py:168-190` 根据月份写入无天气数据支持的温度判断，而 `StarPlan/starplan_skills/claims.py:633-643` 明确禁止天气/温度预测；`StarPlan/starplan_skills/outreach_pack.py:220-237` 把流程、设备、安全、核对文本映射到 Registry 中不存在的 `procedural.*` ID。固定可观测案例 35 个映射项中有 20 个使用未注册 ID；其中包括“夜间气温可能降至 10°C 以下”。 | 未修复。删除“代码生成即可信”的例外。流程时间、设备适配、安全事实、温度、地点开放状态等都要使用已注册 Claim；纯命令性文字只能使用无事实的批准模板并具有真实 Registry 条目。最终门禁必须逐个检查输出句子，而不能按前缀豁免。 |
| CRITICAL | 不可观测路径没有 Claim/渲染追踪 | `StarPlan/starplan_skills/outreach_pack.py::_generate_not_observable_pack()` 在 Claim fallback 后继续追加 `_build_not_observable_talking_points()`、替代建议、流程和核对项；固定不可观测案例有 24 个 Markdown 列表项，却没有 `sentence_claim_map.json`、`expression_plan.json`、`render_trace.json` 或 `audit_events.jsonl`。 | 未修复。可观测和不可观测路径必须进入同一个 Output Claim Gate；`blocking_reasons[]`、替代目标、改期建议和核对项均生成 Claim 与逐句 render trace。缺少映射即阻断交付。 |
| CRITICAL | `observation_review` 没有实现 Evidence Claim 闭环 | `StarPlan/starplan_skills/observation_review.py:84-157` 直接生成归因、建议和计划修订，未建立 Evidence Claim 或句子映射；输出自行规定“云量 > 50% 转为室内讲座”、提前 30 分钟、错过高高度窗口等规则。复盘产物也没有 render trace。 | 未修复。把日志原始字段、计算差异、归因类别、建议规则和修订字段分别建模为 Evidence Claim；Qwen 只能选择 Claim/类别。没有规则或证据支持的阈值必须删除或标为人工确认，`possible`/`undetermined` 不能被后续确定性句子重新说成确定事实。 |
| CRITICAL | RunOutcome 不是实际的单一事实来源 | `StarPlan/starplan_skills/runner.py:221-275` 在解析、计算、活动包和复盘完成后才创建 RunOutcome。强制工具异常和目标歧义都在此前抛出，运行目录分别只有 3 个和 2 个文件，没有 `run_outcome.json`；歧义也未落盘 `NEEDS_CONFIRMATION`。`StarPlan/starplan_skills/runner.py:257-258` 独立生成 Validation Report；`StarPlan/starplan_skills/run_outcome.py:186-188` 又把不可观测业务状态覆盖进 Manifest 的验证状态。实测不可观测 run 的 RunOutcome 为 `validation=passed`，Manifest 为 `target_not_observable`。 | 未修复。收到输入后立即创建并增量保存唯一 RunOutcome；所有异常分支捕获为明确业务/验证/交付状态。Manifest、Validation Report、审计事件和返回值只投影 RunOutcome，不得二次推断或覆盖正交状态。 |
| CRITICAL | Chat 仍向调用者暴露被阻断的模型原文 | `StarPlan/starplan_skills/runner.py:814-820` 虽把 `final_content` 换成确定性摘要，但 `StarPlan/starplan_skills/runner.py:854-863` 仍把 `blocked_content` 和含原文的 `messages` 放入公共返回对象。Mock 运行中错误文字“肉眼清晰可见且光污染较低”同时出现在这两个字段；核查还错误标记 `passed=true`。确定性摘要自身也绕过 Claim Registry，并声称所有数字均来自 Astropy。 | 未修复。公共响应 DTO 只能含已验证内容和公开状态；模型原文、messages、prompt 只写入受控审计存储，不得通过普通 API 返回。Chat 也必须生成 Claim Registry、RunOutcome 和 render trace；不能用另一套摘要器代替统一门禁。 |
| WARNING | 证据产物和模型调用记录不完整 | 成功运行没有计划要求的 `expression_plan.json`、`render_trace.json`、`audit_events.jsonl`。Manifest 的模型使用仅根据 `outreach.qwen_used` 手工补一条事件，不能从真实 `model_call_log.jsonl` 反推，可能漏掉复盘调用、失败调用或只审查未交付的调用。 | 未修复。定义固定 artifact contract；运行结束前校验必需文件。模型状态从结构化调用日志聚合，至少记录阶段、模型、调用结果、是否被采用、失败原因和关联审计事件。 |
| WARNING | 隐私导出只过滤文件名，没有字段级脱敏 | `StarPlan/starplan_skills/privacy.py:103-134` 将 `DELIVERABLE_FILES` 原样复制。实测导出仍在 `input.json`、`review_report.md`、`calculation_manifest.json` 中保留完整 observer notes。复用已有导出目录时也不会清除已存在的旧审计文件。 | 未修复。对 JSON/Markdown 使用字段级导出 schema 和渲染器，observer notes 默认删除或摘要化；导出必须写入全新空目录，完成后做敏感字段与审计文件 deny-list 扫描。 |
| WARNING | Layer 3 测试允许错误实现通过 | `StarPlan/tests/test_layer3_e2e.py:130` 的工具异常用例接受抛出任意异常；`StarPlan/tests/test_layer3_e2e.py:331-356` 只要求至少 5 个映射；`StarPlan/tests/test_layer3_e2e.py:369-375` 自动豁免全部 `procedural.*` ID；纯文字幻觉测试只要求存在备用摘要，没有断言验证器识别错误事实。 | 未修复。端到端测试必须断言精确最终状态、完整 artifact contract、100% 输出事实映射、零未注册 ID、零公共 blocked-content 字段；不能把当前实现缺陷写成可接受分支。 |
| WARNING | “离线 CI”并不保证离线 | `StarPlan/scripts/run_offline_ci.bat` 只忽略 `test_qwen_integration.py`，没有覆盖或清除已由 `.env` 加载的 `DASHSCOPE_API_KEY`。本次按官方脚本运行时出现真实 Qwen 调用。 | 未修复。离线入口必须在进程启动前显式禁用网络模型，并用 fake provider/mock transport；若发生任何真实模型调用，CI 立即失败。在线 canary 应使用独立命令。 |
| INFO | 文档和代码契约仍有漂移 | `StarPlan/README.md` / `StarPlan/skills.yaml` 声称完整 Evidence Claims、正交 RunOutcome 和句子覆盖；`StarPlan/starplan_skills/qwen_client.py` 仍描述旧 FactCard 协议。P2 完成报告把部分路径或组件测试通过表述为整体完成。 | 未修复。文档状态只能由可复现验收证据更新；在 P0 修复前把相关条目标记为“部分完成/未验收”，统一 Qwen 工具协议说明。 |

### 1.3 运行验证

| 检查 | 结果 | 解释 |
|---|---|---|
| Python 编译 | PASS | `starplan_skills`、`scripts`、`tests` 均可编译。 |
| 示例 Schema | PASS | 3/3。 |
| Layer 1 | PASS | 0 issues。 |
| Layer 2/3 | PASS | 0 issues；SIMBAD 快照已补齐。 |
| 三个固定案例 | PASS（仅运行层面） | M31 正常案例、M42 不可观测案例、观测复盘案例均退出 0；这不代表事实门禁、失败分支或证据链通过。 |
| 官方 `run_offline_ci.bat` | FAIL | 115 passed，1 failed，3 errors，2 warnings；4 个失败/错误来自当前 Windows 临时目录/缓存权限。同时脚本意外执行了真实 Qwen 调用，因此也不满足“离线”定义。 |
| 受控离线测试集合 | PASS | 显式禁用 Qwen 并排除 4 个依赖受限临时目录的用例后为 115 passed。说明主体单元测试可运行，但不能替代完整 CI 验收。 |
| Claim 篡改反例 | FAIL（防护失效） | 修改 Claim 后表达验证仍 `passed=true`。 |
| 工具异常反例 | FAIL（证据链失效） | 异常抛出，目录无 RunOutcome/Manifest/Validation Report。 |
| 目标歧义反例 | FAIL（状态机失效） | 异常抛出，未形成 `NEEDS_CONFIRMATION` RunOutcome。 |
| Chat 原文泄漏反例 | FAIL（公共边界失效） | 错误模型原文仍从 `blocked_content` 和 `messages` 返回。 |
| 隐私导出反例 | FAIL（脱敏失效） | observer notes 在三个导出文件中原样存在。 |

### 1.4 已确认无回归的部分

- 代码和三个固定案例仍能运行，未发现语法错误。
- Layer 1 与 Layer 2/3 当前均为 0 issues，SIMBAD 本地快照解决了此前不可复现问题。
- 强月光不可观测文案不再错误声称“高度角过低”或“地平线以下”。
- `ExpressionPlan` 的未知 Claim、未知 variant 和额外字段验证较旧版本更严格。
- 本轮未修改生产代码；以上问题均保持原状，等待团队修复。

## 2. Completion Status

| Project plan 阶段 | 当前复查判定 | 原因 |
|---|---|---|
| 第 1 周：范围、Schema、案例、验证规则 | 基本完成但需回补 artifact contract | 核心范围和案例明确，但完整产物集合、公共/审计响应边界仍未冻结。 |
| 第 2 周：目标解析与本地可观测性 | 完成 | 固定案例、Layer 1、Layer 2/3 可复现运行。 |
| 第 3 周：Qwen 编排和活动包 | 未验收 | 模板/不可观测/Chat 仍有 Claim 绕行；阻断原文仍可通过 API 返回；模型调用追踪不完整。 |
| 第 4 周：观测日志与复盘闭环 | 未验收 | 复盘没有 Evidence Claim 与 render trace，规则阈值和修订结论不能逐条追溯。 |
| 第 5 周：演示入口和三类案例 | 阻塞 | 主路径可演示，但工具错误、歧义、验证阻断等失败场景没有确定性 RunOutcome；隐私导出不安全。 |
| 第 6 周：评测、报告和视频 | 未开始 | 必须在第 3/4 周重新验收后再进入，避免把错误完成状态固化进比赛材料。 |

### 本阶段理应做到但没有做到

这些不是新增 enhancement，而是当前项目计划已经要求的基线：

1. **统一事实出口**没有完成：实现以“模型文本”作为风险边界，却默认“确定性代码文本”可信，导致模板、复盘和 Chat 摘要绕过同一 Claim Gate。
2. **失败优先的 RunOutcome**没有完成：RunOutcome 被放在成功路径末端创建，因此最需要证据的工具错误、歧义和验证阻断反而没有结果对象。
3. **Evidence Claim**只停留在文档术语：复盘用结构化 Pydantic 输出不等于证据可追溯；缺少 claim_id、source、rule、scope、render trace 和完整性验证。
4. **测试按验收标准设计**没有完成：部分测试把“抛异常也可以”“至少五条映射”“procedural 全部豁免”写成通过条件，使测试验证了实现现状而不是 project plan。
5. **隐私最小化**没有完成：实现把隐私边界理解为排除 audit 文件，忽略 deliverable 内嵌的原始输入、观察备注和 Manifest 副本。
6. **文档由证据驱动**没有完成：阶段报告按“代码文件已存在/测试退出 0”宣布完成，没有逐项核对用户最终可见内容、失败分支和实际产物。

## 3. Corrective Phase Plan

当前不进入新 enhancement。以下计划用于重新关闭 project plan 第 3 周和第 4 周验收，并且是给实现人员或 Qwen 的直接施工说明。

### 3.1 实施原则和禁止项

1. **先写失败测试，再改实现。** 每个 CRITICAL 至少先加入一个能稳定复现现状的端到端反例；测试必须在修复前失败、修复后通过。
2. **只保留一个事实出口。** Qwen 表达、确定性模板、不可观测通知、Chat 摘要、复盘报告和回退内容都必须进入同一个 Claim/渲染门禁。
3. **不要继续扩充关键词黑名单或数字正则。** 正则只能作为辅助诊断，不能决定一条事实是否可交付。
4. **不要把“代码生成”“procedural 前缀”“结构化 JSON”当成可信证明。** 是否可信只由注册 Claim、来源、规则、作用域、完整性校验和 render trace 决定。
5. **不要在失败路径继续抛普通异常给用户。** 目标歧义、数据不足、工具失败和验证阻断是预期业务终态，必须产生确定性 RunOutcome 和最小安全输出。
6. **不要先改 README 或阶段报告为“完成”。** 必须等本节每个验收命令和对抗用例通过后再同步文档状态。
7. **明确完整性校验的威胁边界。** 本阶段的封存 hash 用于发现运行期对象漂移、错误代码改写和产物不一致，不等同于防御能同时重写文件与 hash 的主动攻击者。若比赛材料需要宣称“防篡改”，必须另行引入仓库外可信根、签名或不可变存储；在此之前只能表述为“篡改可检测/一致性校验”。

### 3.2 文件级修改总表

| 文件 | 具体修改位置 | 应做的修改 | 完成标志 |
|---|---|---|---|
| `StarPlan/starplan_skills/schemas.py` | `ClaimType`、`Claim`、`ObservationReview`、`CalculationManifest` 附近 | 增加受控程序性 Claim、Evidence Claim、公共返回 DTO、审计事件和完整产物状态所需字段；所有模型 `extra="forbid"` | 未知字段无法静默进入；公共 DTO 在 Schema 层不含审计原文 |
| `StarPlan/starplan_skills/claims.py` | `AllowedClaimsBuilder.__init__()`、`build()`、`registry_hash`、`save()`、`_hash_source()` | 保存不可变源快照；构建后封存 hash；为模板、流程、安全、设备、替代建议和复盘规则生成真实 Claim；提供统一完整性校验 | 修改 Claim、源快照、规则版本或模板后校验必定失败 |
| `StarPlan/starplan_skills/expression_validator.py` | `validate_expression_plan()` 第 8 步 | 删除“动态 hash 对动态 hash”和只检查长度的逻辑；调用 Registry 的统一完整性校验；失败必须返回 blocking issue | 篡改反例进入 `VALIDATION_BLOCKED` |
| `StarPlan/starplan_skills/templates.py` | `SENTENCE_VARIANTS` | 删除或拆分模板自身夹带的事实；模板 hash 纳入 Registry；增加可观测、不可观测、程序动作、待确认和复盘的批准句式 | 模板只表达 Claim 值，不自行增加“清晰”“最佳”“完全变暗”等断言 |
| `StarPlan/starplan_skills/rendering.py` | `RenderedSentence`、`RenderResult`、三个 render 函数 | 扩展为所有用户可见 section 的唯一渲染入口；写出字段级 render trace；渲染前后都做完整性与覆盖校验 | Markdown/JSON/Chat/复盘的每个事实字段都有真实 Claim ID |
| `StarPlan/starplan_skills/outreach_pack.py` | `generate_outreach_pack()`、`_generate_not_observable_pack()`、`_build_*()`、`_write_*_markdown()` | 移除自由文本拼接和伪 `procedural.*` 映射；两条业务路径统一生成 Claim-backed document | 可观测与不可观测路径都生成 `render_trace.json`，无未注册 ID |
| `StarPlan/starplan_skills/run_outcome.py` | 三个状态枚举、`RunOutcome.__init__()`、`build_manifest()`、`to_audit_summary()` | 允许在尚未解析目标/计算前创建；状态三轴严格正交；由真实事件和 artifact contract 生成 Manifest/报告 | 工具错误、歧义等失败路径同样有完整 RunOutcome |
| `StarPlan/starplan_skills/runner.py` | `run_starplan()`、`_write_validation_report()`、`_build_manifest()`、`run_starplan_chat()`、`_build_deterministic_summary()` | 在入口创建 Outcome；捕获并落盘所有终态；删除分散状态推断；Chat 复用统一渲染；公共返回与审计返回分离 | 所有路径只由一个 Outcome 驱动，公共返回无模型原文 |
| `StarPlan/starplan_skills/observation_review.py` | `review_observation()`、`_qwen_assisted_attribution()`、`_write_review_markdown()`、`_build_revised_plan()` | 先建 Evidence Claims，再允许 Qwen 选 ID；删除数字正则式自由建议；复盘和修订计划确定性渲染 | 删除证据后相关结论自动降级或消失 |
| `StarPlan/starplan_skills/qwen_client.py` | 模块级 `load_dotenv()`、`call_qwen*()`、`_log_call()` | 支持显式 offline provider；统一产生结构化 model-call 事件；prompt/content 默认只存 hash 和安全摘要 | 离线命令不可能发真实请求，Manifest 可从日志反推调用情况 |
| `StarPlan/starplan_skills/privacy.py` | `DELIVERABLE_FILES`、`SENSITIVE_FIELDS`、`sanitize_run_for_export()`、验证函数 | 改为字段级 allowlist 渲染；拒绝非空目标目录；扫描所有导出文件 | observer notes、prompt、blocked content 和旧审计文件均不在导出包 |
| `StarPlan/tests/test_claims_registry_b.py`、`StarPlan/tests/test_mock_qwen_adversarial.py` | Registry 与表达验证用例 | 增加 Claim/源/规则/模板四类篡改反例 | 四类篡改全部 blocked |
| `StarPlan/tests/test_layer3_e2e.py` | 工具异常、Chat、映射、隐私用例 | 删除宽松异常、数量阈值和 `procedural.*` 豁免；按最终产物和公共响应精确断言 | 测试不再允许当前错误实现“假通过” |
| `StarPlan/scripts/run_offline_ci.bat` | 环境初始化和 pytest 命令 | 设置强制离线模式与可写临时目录；增加网络调用 tripwire | 无 API 调用、无需 deselect、全套零失败零错误 |
| `StarPlan/README.md`、`StarPlan/skills.yaml`、`StarPlan/starplan_skills/qwen_client.py` 文档字符串 | 架构和产物说明 | 在验收通过后同步实际协议、状态和文件清单；此前标注未验收 | 文档描述可由运行产物逐项证明 |

### P0-A：封存 Claim Registry 并修复篡改校验

#### 修改 `StarPlan/starplan_skills/claims.py`

1. 在 `AllowedClaimsBuilder.__init__()` 中保存构建输入的深拷贝规范化快照，而不是只保存可变对象引用：
   - `_target_snapshot = target.model_dump(mode="json")`
   - `_observability_snapshot = obs_result.model_dump(mode="json")`
   - `_context_snapshot = {location_id, audience, equipment, timezone}`
   - `_sealed_registry_hash: Optional[str] = None`
2. `build()` 完成所有 allowed/prohibited/procedural Claim 后，使用规范化 JSON 一次性计算 `_sealed_registry_hash`。规范化内容至少包括：Schema 版本、run scope、全部 Claims、`DERIVATION_RULES`、每个已使用 sentence variant 的模板 hash，以及源快照 hash。
3. `registry_hash` 属性只返回 `_sealed_registry_hash`。未 build 时直接报错；**不得再调用 `_compute_registry_hash()` 动态返回当前值**。
4. `save()` 写入封存值，并在 `claims.json` 增加：
   - `source_artifact_hashes`
   - `derivation_rules_hash`
   - `template_set_hash`
   - `registry_hash`
5. 新增 `verify_integrity()`，集中执行四类检查：
   - 当前 Claims 重算 hash 是否等于封存值；
   - Claim 的 `source_hash` 是否等于其引用源快照的重算值；
   - derived Claim 的 `derivation_rule` 是否存在且版本/hash 未变化；
   - `allowed_variant_ids` 引用的模板是否存在且模板 hash 未变化。
6. observed Claim 的 `source_refs` 应使用可解析引用，例如 `resolved_target.json#/visual_magnitude`、`plan.json#/recommended_window/peak_altitude_deg`。不能只写无法自动定位的说明字符串。
7. derived Claim 的来源 hash 应由“被引用源值 + derivation_rule ID/version + 关键上下文”共同计算。例如设备匹配必须包含目标亮度、角径、设备类型和规则版本，不能只 hash 整个 target 对象后声称已验证推导。

#### 修改 `StarPlan/starplan_skills/expression_validator.py`

1. 将第 8 步替换为一次 `claims_builder.verify_integrity()` 调用。
2. 任何完整性错误均加入 `severity="error"`，不得降级 warning。
3. 移除以下无效判断：
   - 当前 Registry hash 与动态 `registry_hash` 比较；
   - `source_hash` 只检查长度为 16；
   - 非零 hash 即视为可信。
4. 校验失败后禁止调用 `render_from_expression_plan()`；runner 必须记录 `RunState.VALIDATION_BLOCKED` 和具体 tamper reason。

#### 修改测试

在 `StarPlan/tests/test_claims_registry_b.py` 或新建 `StarPlan/tests/test_claim_integrity.py`，至少加入：

1. 修改 `canonical_value: 3.4 -> 99.9`，保留旧 source hash，必须 blocked。
2. 修改 `display_value` 但不改 canonical value，必须 blocked。
3. 修改源快照中的视觉星等，Claim 不变，必须 blocked。
4. 修改 `DERIVATION_RULES` 版本或模板正文，旧 Registry 必须 blocked。
5. 保存再加载 `claims.json` 后重新验证，结果与内存验证一致。

#### P0-A 验收标准

- 四类篡改反例全部失败关闭，并产生明确审计事件。
- 正常 Registry 在重复构建时 hash 稳定；Claims 顺序变化不应改变语义 hash，内容变化必须改变 hash。
- 代码中不存在 `return self._compute_registry_hash()` 形式的动态安全基线。

### P0-B：建立唯一 Output Claim Gate，清除模板绕行

#### 修改 `StarPlan/starplan_skills/schemas.py`

1. 在 `ClaimType` 增加 `PROCEDURAL`，仅表示批准的无事实操作指令；它仍必须具有 claim_id、模板来源和模板 hash。
2. 为 trace 增加结构化模型，建议字段：
   - `artifact`
   - `json_pointer` 或 `section/item_index`
   - `rendered_text_hash`
   - `claim_ids`
   - `variant_ids`
   - `source_refs`
3. 所有新增模型使用 `ConfigDict(extra="forbid")`。

#### 修改 `StarPlan/starplan_skills/templates.py`

逐条审计模板自身的附加事实，至少处理以下现有句式：

1. `naked_eye_v1` 删除“不需要望远镜就能找到”。肉眼可见不等于新手可轻松定位；若确实要表达“易找”，必须另建有星图/定位规则支持的 Claim。
2. `binoculars_v1` 删除“可以清晰地看到它”。当前规则最多支持设备可能匹配，不能承诺清晰度。
3. `beginner_v1` 不要在 `{display_value}` 已包含“适合新手”后再次无条件“推荐作为入门对象”；推荐必须来自单独的版本化规则 Claim。
4. `window_v2` 将“最佳观测时间”改成“本次约束下的推荐观测时间”，避免把采样窗口说成全局最佳。
5. `twilight_v1` 删除“届时天空完全变暗”；天文暮光结束只表示太阳高度达到定义阈值，不保证光污染、月光或天气条件。
6. `equipment_mismatch_v1` 中“建议升级设备或选择更亮目标”拆为 procedural action，不要和设备匹配事实绑在一个模板中。

#### 修改 `StarPlan/starplan_skills/claims.py`

1. 为 schedule、equipment、safety、manual check、unconfirmed item 建立真实 Claim ID，不再在写完文本后伪造映射：
   - `schedule.twilight_end`
   - `schedule.observation_start`
   - `schedule.observation_end`
   - `equipment.requested_type`
   - `equipment.recommendation.*`
   - `safety.night_group_action`
   - `manual_check.site_access`
2. 需要外部确认的“地点夜间开放”“设备电池充足”等必须是 `UNCONFIRMED` 或 `HUMAN_CONFIRMED`，不能当作已验证事实。
3. 纯动作“通知成员改期”“重新运行 StarPlan”可以是 `PROCEDURAL`，来源指向批准模板版本。
4. 对设备规格建立明确规则来源。若当前没有口径/倍率规则依据，删除“7x50 或 10x50”“口径 >= 80mm”等具体推荐，只保留用户输入的设备类型和人工核对项。
5. 删除按月份推测温度的逻辑。没有天气工具时只允许无事实的程序性提示，例如“根据当地临近天气预报准备衣物”；不得输出 0°C、10°C 或“气温适宜”。

#### 修改 `StarPlan/starplan_skills/rendering.py`

1. 将 `RenderResult` 扩展为完整 document，而不只保存 talking points。至少包含 header facts、recommended window、schedule、talking points、equipment、safety、manual checks、alternatives 和 unconfirmed sections。
2. 每个 `RenderedSentence` 必须有非空 `claim_ids` 和 `variant_id`；未注册 Claim、空映射或完整性失败立即停止渲染。
3. 新增 `validate_render_coverage(render_result, registry)`：
   - 所有 claim_id 在 Registry 中存在；
   - 禁止 prohibited Claim；
   - 每个事实字段有 source_refs；
   - rendered text hash 与 trace 一致；
   - 事实句覆盖率必须等于 100%。
4. 以 `render_trace.json` 作为主证据文件；`sentence_claim_map.json` 只可由 render trace 派生用于向后兼容，不能反向手工补写。

#### 修改 `StarPlan/starplan_skills/outreach_pack.py`

1. `generate_outreach_pack()` 先生成完整 Claim Registry，再生成整个 document 的选择计划，最后一次性渲染。不要先写 talking points，再由 `_build_schedule()`、`_build_equipment_checklist()` 和安全数组追加自由文本。
2. 删除 `StarPlan/starplan_skills/outreach_pack.py:168-190` 的月份温度判断。
3. 删除 `StarPlan/starplan_skills/outreach_pack.py:220-237` 手工添加 `procedural.*` 映射的循环。
4. `_build_schedule()` 和 `_build_equipment_checklist()` 改为返回 Claim ID/结构化选择，不直接返回最终事实文本。
5. `_write_outreach_markdown()` 只能接收已经通过 coverage gate 的 `RenderResult`，不得接收 target/obs 等原始对象后再次拼事实。
6. `_generate_not_observable_pack()` 不再执行 `talking_points.extend(_build_not_observable_talking_points(...))`。将 blocking reason、风险、替代目标、改期、室内活动和人工核对全部建成 Claims 后走同一 renderer。
7. `_write_not_observable_markdown()` 不得再次遍历 `eliminated_windows`、`risk_flags` 或 `alternative_suggestions` 拼文案；这些内容应在 Claim Builder 阶段生成并验证。
8. 两条路径都必须写出 `expression_plan.json`：未调用 Qwen 时写入明确的 deterministic selection plan，而不是直接省略该文件。

#### 修改测试

1. 在 `StarPlan/tests/test_not_observable_pack_c3.py` 中把“有取消文案”升级为完整 trace 断言：逐项枚举 Markdown 列表、JSON 输出字段和替代建议，确认每项都能在 `render_trace.json` 找到已注册 Claim。
2. 在 `StarPlan/tests/test_mock_qwen_adversarial.py` 增加缺 Claim、删除被引用 Claim、伪 `procedural.*` ID、模板夹带额外事实四类攻击；四者都必须在渲染前 blocked。
3. 在 `StarPlan/tests/test_layer3_e2e.py` 中删除 `mapped_count >= 5` 和 `procedural.*` 豁免，改为从最终 artifact 反向枚举全部事实字段并精确断言 coverage 为 100%。
4. 增加模板禁语回归：可观测和不可观测固定案例中，无独立 Claim 时不得出现“清晰地看到”“完全变暗”“最佳时间”、具体温度或具体设备规格。

#### P0-B 验收标准

- 可观测与不可观测案例均有 `expression_plan.json`、`render_trace.json` 和由其派生的 `sentence_claim_map.json`。
- `sentence_claim_map.json` 中不存在 Registry 外 ID，不存在 `procedural.*` 特判。
- 输出全文中的 0°C、10°C、“清晰地看到”“完全变暗”“最佳时间”等无独立 Claim 支持的文字为 0。
- 删除任一被引用 Claim 后，输出生成必须 blocked，不能静默少映射后继续交付。

### P0-C：把 RunOutcome 移到入口并覆盖全部失败路径

#### 修改 `StarPlan/starplan_skills/run_outcome.py`

1. `RunOutcome.__init__()` 不应强制要求已有 `ResolvedTarget` 和 `ObservabilityResult`。改为输入接收时可创建，target、location、obs_result 后续增量填充。
2. `BusinessStatus` 增加 `PENDING`；保留 `OBSERVABLE`、`NOT_OBSERVABLE`、`DATA_INSUFFICIENT`、`TOOL_ERROR`、`NEEDS_CONFIRMATION`。
3. 删除 `ValidationStatus.TARGET_NOT_OBSERVABLE`。不可观测是 business status，不是 validation status。
4. `DeliveryStatus` 增加 `NOT_DELIVERED`，失败分支在安全输出尚未生成前不能默认 `TEMPLATE`。
5. 增加 `blocking_reason_codes`、`error_type`、`error_message_safe`、`artifact_status`、`human_confirmations`、`model_call_events`、`audit_events` 等字段。
6. 增加以下单一写出方法：
   - `record_transition()`：同时更新 state log 和 `audit_events.jsonl`；
   - `finalize_artifacts()`：按终态检查必需文件并计算 hash；
   - `build_manifest()`：只读取自身字段；
   - `build_validation_report()`：只读取自身字段；
   - `to_public_result()`：只返回公开字段；
   - `persist()`：原子写出 `run_outcome.json`。
7. `build_manifest()` 删除 `if NOT_OBSERVABLE: validation_status = target_not_observable` 覆盖逻辑。
8. Manifest 中的 `constraints_applied` 从 `StarPlanInput.constraints`、时区、折射策略和实际规则版本完整生成，不得只保留折射说明。
9. `model.called` 和模型名称从真实 `model_call_events` 聚合；调用失败、复盘调用和结果被阻断也计为 called，但另有 `accepted_for_delivery` 字段区分是否采用。

#### 修改 `StarPlan/starplan_skills/schemas.py`

1. 修改 `CalculationManifest`，让失败态可以被真实表达，而不是为通过必填校验伪造空对象：
   - `target` 和 `location` 改为显式可空字段；目标歧义时 `target=null`，并通过 candidates artifact 说明候选项；目标已解析但地点解析失败时只允许 `location=null`。
   - 增加 `business_status`、`validation_status`、`delivery_status` 三个独立字段，并直接复用受控枚举或其序列化值。
   - 增加 `blocking_reason_codes`、`error_type`、`error_message_safe` 和 `artifact_status`；不得把 traceback、API key、原始 prompt 或私人观察备注写入安全错误字段。
   - `artifact_status` 至少逐项记录 `required`、`present`、`sha256` 和 `validation_result`，不能只保存一个可能漏项的文件名数组。
2. 保留原始 `input` 的审计版本时，应与公共 Manifest 分离；公共 Manifest 只保存允许公开的输入摘要和 `input.json` hash，避免与 P1-A 的隐私要求冲突。
3. 将 `schema_version` 从沿用旧结构的 `1.0` 提升到新版本；反序列化器和 verifier 必须按版本分派，未知版本 fail-closed，不能按最新字段猜测解析。
4. 所有新增状态/Manifest 模型使用 `ConfigDict(extra="forbid")`，并为早期失败态加入模型级约束：例如 `business_status=observable` 时必须存在 target、location 和计算产物，而 `needs_confirmation` 时必须存在 candidates artifact。
5. 删除 `qwen_used` 与 `model.called` 的重复事实源，或把前者明确改成由 `model_call_events` 派生的只读兼容字段；两者不允许独立赋值后产生矛盾。

#### 修改 `StarPlan/starplan_skills/runner.py`

1. 在 `run_dir` 创建并写入 `input.json` 后立即创建 `RunOutcome`，时间点应早于 `resolve_target()`。
2. 将 `run_starplan()` 分为明确阶段函数或至少明确 try/except 边界：
   - 目标解析；
   - 地点解析；
   - 天文计算；
   - Claim 构建；
   - 表达计划；
   - 验证和渲染；
   - 复盘；
   - artifact finalize。
3. 对预期失败做精确映射：
   - `TargetConfirmationRequired` -> `business=needs_confirmation`、`RunState.NEEDS_CONFIRMATION`，写 candidates；
   - 目录无目标或必要数据缺失 -> `business=data_insufficient`；
   - Astropy/astroplan/文件计算异常 -> `business=tool_error`、`RunState.TOOL_ERROR`；
   - Claim/Expression/render coverage 失败 -> `validation=blocked`、`RunState.VALIDATION_BLOCKED`；
   - Qwen 调用失败但确定性回退成功 -> business 不变、validation 记录 warning 或 passed、delivery 为 deterministic fallback。
4. 对这些预期状态，`run_starplan()` 应返回 `PublicRunResult`，不应依赖调用者捕获普通异常才能知道发生了什么。仅程序员错误和无法写审计文件等不可恢复错误可以抛异常。
5. 删除或停用 `StarPlan/starplan_skills/runner.py` 中旧 `_build_manifest()`；`_write_validation_report()` 改为只接收 RunOutcome，或者迁入 `StarPlan/starplan_skills/run_outcome.py`。
6. `_write_model_call_log()` 不应根据 outreach 状态补造调用事实。Qwen client 每次实际调用时写事件，runner 只读取/聚合。
7. 在 `finally` 中至少持久化当前 RunOutcome、state log 和 audit event，保证失败不会只留下 input/target 半目录。
8. artifact contract 按终态定义：
   - 所有终态必有 `input.json`、`state_log.json`、`audit_events.jsonl`、`run_outcome.json`、`calculation_manifest.json`、`validation_report.md`；
   - `needs_confirmation` 额外有 candidates；
   - 计算完成路径有 target、plan、claims；
   - 已交付路径有 expression plan、render trace 和用户输出。

#### 修改测试

1. 修改 `StarPlan/tests/test_target_confirmation_c2.py::TestPipelineHaltsOnAmbiguity`：不再把抛出 `TargetConfirmationRequired` 当成最终成功行为；改为断言公共结果为 `needs_confirmation`，candidates 与基础六件 artifact 齐全，且没有进入计算阶段。
2. 修改 `StarPlan/tests/test_layer3_e2e.py::TestToolExceptionE2E`：删除接受任意异常的分支，monkeypatch 天文计算抛出固定异常后，精确断言 `business=tool_error`、`delivery=not_delivered`、安全错误码和 artifact contract。
3. 在 `StarPlan/tests/test_layer3_e2e.py` 增加六终态参数化矩阵：`observable`、`not_observable`、`needs_confirmation`、`data_insufficient`、`tool_error`、`validation_blocked`；逐个比较 PublicRunResult、RunOutcome、Manifest、Validation Report 和最后一个 audit event。
4. 新建 `StarPlan/tests/test_run_outcome_contract.py`，单独测试状态正交性、非法状态组合、早期失败 Manifest round-trip、缺少必需 artifact 时 finalize 失败，以及 `model.called` 从事件聚合而非手工布尔值决定。

#### P0-C 验收标准

- 强制工具异常不抛普通 RuntimeError 给最终调用者，并产生 `business=tool_error`、`delivery=not_delivered` 或最小安全模板及完整基础产物。
- “星云”等歧义目标产生 `needs_confirmation` 和 candidates，不进入天文计算。
- 不可观测运行保持 `business=not_observable`、`validation=passed`，Manifest/Report/RunOutcome 三者一致。
- 验证阻断运行保持原业务状态，同时 `validation=blocked`，不得写成 `passed_with_warnings`。
- 对每个终态比对 artifact contract，缺文件即整次验收失败。
- 对目标歧义和工具异常的 `calculation_manifest.json` 做 Schema round-trip，确认不存在伪造的空 target/location，且安全错误字段不含 traceback 或输入原文。

### P0-D：实现真正的 Evidence Claim 复盘闭环

#### 修改 `StarPlan/starplan_skills/schemas.py`

新增 Evidence Claim 相关 Schema，建议最小字段如下：

1. `EvidenceRef`：`artifact`、`json_pointer`、`value_hash`。
2. `EvidenceClaim`：`claim_id`、`subject`、`predicate`、`value/text`、`classification`、`evidence_refs`、`inference_rule_id`、`validity_scope`、`allowed_variant_ids`。
3. `ReviewExpressionPlan`：只允许 `selected_evidence_claim_ids`、`selected_action_ids`、顺序和批准语气，不允许自由原因或自由建议字段。
4. `CauseEntry`、`RevisedPlanDiff` 增加 `claim_ids` 和 `evidence_refs`，不能只保存已经拼好的 evidence 字符串。

#### 修改 `StarPlan/starplan_skills/observation_review.py`

1. 将 `review_observation()` 拆成四步：
   - `_build_review_evidence_claims(plan, log)`：从 `plan.json`、`observation_log.json` 生成原子证据；
   - `_apply_review_rules(evidence_claims)`：执行版本化规则，生成归因/建议候选 Claim；
   - `_select_review_claims_qwen(...)`：Qwen 只选 ID 和分类，不写事实文本；
   - `_render_review(...)`：从批准模板确定性生成 review/revised plan 和 trace。
2. 处理当前具体规则问题：
   - `delay_minutes > 10`：若保留，登记为 `review.delay_significance@v1`，说明 10 分钟是活动政策阈值而非天文事实；
   - “提前 30 分钟”：必须来自已批准活动 policy Claim，否则改成无具体数字的“提前到场完成设备检查”；
   - “错过早期高高度窗口”：必须计算实际开始时间与推荐窗口/高度曲线的交集后才能生成；仅凭迟到不能断言；
   - “云量 > 50%”：当前日志只有 `clear/partly_cloudy/overcast`，没有百分比，立即删除该阈值；
   - observer notes 含“三脚架不稳”：可作为 human-reported evidence，但“设备准备不足”最多是 `possible`，除非另有检查记录；
   - “成员期望过高”：当前已标 `undetermined`，后续 revised plan 的 reason 也必须保持不确定措辞，不能再次写成确定事实；
   - “目视通常为模糊光斑”：属于天文科普事实，需要受信来源/目标类型规则 Claim，不能从备注直接推出。
3. `_qwen_assisted_attribution()` 改为 ID selection 协议并使用 `extra="forbid"` Schema。删除“允许数字集合 + 正则过滤”的安全主逻辑。
4. Qwen 返回未知 Evidence Claim、未知 action、自由文本字段或更高置信分类时，整份 ReviewExpressionPlan blocked，使用仅基于规则 Claim 的确定性回退。
5. `_write_review_markdown()` 只接收已渲染的 `RenderedSentence`/字段对象；不得从 `log`、`causes`、`suggestions` 再拼事实。
6. `_build_revised_plan()` 的每个 revised field 必须带 `source_claim_ids`、`rule_id`、`classification`。没有证据的 suggestion 可以列入“待人工确认”，不能直接写入已修订计划。
7. 输出 trace 覆盖 `review_report.md` 和 `revised_plan.json` 的字段，可写入统一 `render_trace.json`，并以 `artifact + json_pointer` 区分。

#### 修改 `StarPlan/tests/test_review_evidence_claims.py`（新建）与 `StarPlan/tests/test_layer3_e2e.py`

至少加入以下复盘对抗用例：

1. 只有 `partly_cloudy` 时，输出不得出现 50% 或其他云量百分比。
2. 迟到 16 分钟但仍在推荐窗口内时，不得声称错过窗口。
3. 删除 observer notes 中“三脚架不稳”后，设备原因和相关修订必须消失或降为 undetermined。
4. Qwen 返回新的原因文字或具体数字但无 claim_id 时，最终报告中不得出现。
5. `undetermined` 原因不能在 revised plan reason 中变成确定陈述。
6. 每条建议和每个 revised field 都能从 trace 找到 Evidence Claim 和规则版本。
7. 规则测试和端到端测试分开：前者直接给定 plan/log 固件验证 Claim 与分类，后者 mock Qwen 恶意返回并检查最终用户产物，避免只测试自己的过滤函数。

#### P0-D 验收标准

- `review_report.md` 和 `revised_plan.json` 的事实/归因/建议/修订字段覆盖率为 100%。
- 删除或修改证据会导致关联结论降级、消失或 validation blocked。
- Qwen 返回完全错误的复盘 JSON 时，用户仍只看到确定性 Evidence Claim 输出。

### P0-E：关闭 Chat 公共返回泄漏并复用统一架构

#### 修改 `StarPlan/starplan_skills/runner.py`

1. `run_starplan_chat()` 的 Qwen 自由文本只作为审计输入，不能成为公共返回对象字段。
2. 删除公共返回 dict 中的 `blocked_content` 和 `messages`；`tool_call_log` 也只返回经过筛选的工具名称/状态，不返回参数中的私人内容。
3. 新增 `PublicRunResult` Schema，公共字段限定为 `run_id`、公开状态三轴、`final_content`、公开 artifact 列表和安全问题码。
4. 模型原文、完整 messages 和 prompt 若确需保留，写入权限受控的 audit 文件；普通调用者只收到 audit event ID/hash。
5. Chat 完成工具编排后，从工具结果构建与 structured mode 相同的 Claim Registry 和 RunOutcome，调用同一个 renderer；不要调用独立 `_build_deterministic_summary()`。
6. 删除 `_build_deterministic_summary()`，或将其改造成只选择 Claim ID 的兼容层，不能直接拼 target/location/observability 数字。
7. 删除“以上所有数值均来自 Astropy”笼统声明。目标目录来自 catalog，地点来自输入/地点库，只有天文计算字段来自 Astropy/astroplan，来源应逐 Claim 记录。
8. 将 `hallucination_verification.passed` 拆为：
   - `model_text_accepted_for_delivery=false`；
   - `public_output_validation=passed/blocked`；
   - `untraceable_numbers` 仅作审计诊断。
   无数字幻觉不能再得到容易误读的 `passed=true`。

#### 修改 `StarPlan/starplan_skills/schemas.py` 与测试

1. `PublicRunResult` 使用 `extra="forbid"`，从类型上排除 `blocked_content`、messages、prompt 和原始日志。
2. 在 `StarPlan/tests/test_chat_hallucination_c4.py` 和 `StarPlan/tests/test_layer3_e2e.py` 中 mock Qwen 返回唯一哨兵文本，断言：
   - 哨兵不在 public result 的任何递归字段中；
   - 哨兵不在用户 deliverables；
   - 哨兵只在允许的 audit artifact 中；
   - 最终内容每个事实都存在于 render trace。

#### P0-E 验收标准

- 公共响应 Schema 不包含任何承载模型原文的字段。
- 纯文字幻觉、数字幻觉和无工具调用三种 Chat 反例均产生安全确定性输出或明确阻断。
- Chat 与 structured mode 使用同一 Registry、RunOutcome、renderer 和 artifact contract。

### P1-A：字段级隐私导出和审计保留

#### 修改 `StarPlan/starplan_skills/privacy.py`

1. `sanitize_run_for_export()` 不再 `shutil.copy2()` 整个 deliverable；为每类 JSON/Markdown 定义 allowlist serializer。
2. `input.json` 默认删除 `observation_log.observer_notes`；若演示必须说明，输出受控摘要字段并标记 `redacted=true`。
3. `calculation_manifest.json` 不应嵌入未经脱敏的完整 input；Manifest 使用公开 input 摘要或引用 input artifact hash。
4. `review_report.md` 必须从已脱敏 Evidence Claims 重新渲染，不能复制原报告后做字符串替换。
5. 审查 `claims.json` 中 `HUMAN_CONFIRMED` 和 observer-note Evidence Claims，导出版本只保留必要结论、来源类型和 hash，不保留原始私人文本。
6. export 目标目录必须不存在或为空；若非空就报错，避免旧 `chat_conversation.json`、模型日志或历史报告残留。不要静默删除未知目录内容。
7. 增加 `verify_export_sanitized()`，递归扫描全部 JSON/JSONL/Markdown/TXT：
   - 禁止 audit 文件名；
   - 禁止 `blocked_content`、`messages`、`prompt_preview`、`observer_notes` 字段；
   - 使用测试哨兵确认原始私人文字未出现；
   - 检查导出 Manifest 的 artifact 列表不引用不存在或禁止文件。
8. 当前 `RETENTION_AUDIT_DAYS=90` 只是声明。若比赛演示不实现自动清理，应在 policy 中明确 `enforcement="manual/not implemented"`，不能写成已实施控制。

#### 修改测试

1. 在 `StarPlan/tests/test_layer3_e2e.py::TestPrivacyBoundaryE2E` 的 observer notes、Chat messages 和 blocked content 分别放置不同唯一哨兵，导出后递归读取全部文本文件，三类哨兵出现次数都必须为 0。
2. 新建 `StarPlan/tests/test_privacy_export.py`，覆盖非空目标目录拒绝、源 run 中未知文件不会被导出、Manifest 悬空引用、畸形 JSON fail-closed 和对同一输入导出两次得到相同内容 hash。
3. 测试只允许读取临时 run 副本，不能清理或改写开发者真实 `runs/` 目录。

#### P1-A 验收标准

- 含唯一 observer-note 哨兵的完整复盘 run 导出后，哨兵在所有导出文件中出现次数为 0。
- 对预先放有旧审计文件的 export 目录，函数拒绝执行而不是返回“成功”。
- 导出包通过字段级 allowlist 和全量敏感扫描。

### P1-B：重写 Layer 3 验收，建立真实离线 CI

#### 修改 `StarPlan/tests/test_layer3_e2e.py`

1. 工具异常用例删除 `except Exception` 即通过的逻辑；必须断言返回：
   - `business_status == "tool_error"`；
   - `validation_status` 为明确值；
   - 精确 artifact contract；
   - 无正常观测活动包伪装成功。
2. 映射用例删除 `mapped_count >= 5`；应从结构化 RenderResult 或 trace 枚举全部事实字段，要求 coverage 精确为 100%。
3. 删除 `valid_ids.update(procedural.*)` 和 `startswith("procedural.")` 豁免；所有 ID 必须在 `claims.json`。
4. 纯文字幻觉用例不能只断言 fallback 存在；必须断言错误原文在 public result 和所有 deliverables 中均不存在。
5. 隐私用例不仅检查 audit 文件名，还要在 observer notes 放唯一哨兵并递归搜索导出包。
6. 增加六个终态的参数化 E2E：observable、not_observable、needs_confirmation、data_insufficient、tool_error、validation_blocked。
7. 为每个终态断言 RunOutcome、Manifest、Validation Report、audit events 和 public result 状态完全一致。

#### 修改 `StarPlan/scripts/run_offline_ci.bat` 与 `StarPlan/starplan_skills/qwen_client.py`

1. 引入显式 `STARPLAN_MODEL_MODE=offline|online`。offline 时 `_qwen_available()` 必须为 false，三个 call 函数若被调用立即抛出“offline network call attempted”，不能依赖 API key 是否存在。
2. `run_offline_ci.bat` 开始时设置 `STARPLAN_MODEL_MODE=offline`，即使 `.env` 中有真实 key 也不能调用网络。
3. 为 pytest 指定仓库内可写且唯一的 `--basetemp` 和 cache dir，解决当前 Windows TEMP/pytest cache 权限问题；测试完成后以明确路径清理或按 run ID 保留。
4. 增加网络 tripwire：mock/patch DashScope transport，任何调用都使离线 CI 失败。
5. 真实 Qwen canary 使用单独的 `run_online_canary` 命令，不包含在离线通过率中，也不能成为核心验收前提。
6. CI 顺序保持：compile -> example schema -> Layer 1 -> Layer 2/3 -> offline pytest -> 三固定案例 -> artifact/trace verifier。任一步失败立即非零退出。

#### P1-B 验收标准

- 官方离线命令无需手工排除任何测试，结果为零 failed、零 errors、零真实网络调用。
- 三固定案例和六类终态均通过 artifact/trace verifier。
- 测试在有真实 `.env` key 和无 key 两种环境下产生相同离线结果。

### P1-C：证据文件、模型日志和文档同步

#### 修改证据链

1. 每次已进入 Claim 阶段的运行写出 `expression_plan.json` 和 `render_trace.json`；所有运行写出 `audit_events.jsonl`。
2. `qwen_client._log_call()` 记录 `call_id`、stage、model、result status、error code、request/response hash、是否被采用。prompt/content 原文默认不写，必要时只写已脱敏预览。
3. runner 不再用 `outreach.qwen_used` 推测模型是否调用；从 model-call events 聚合 `called`、`successful`、`accepted_for_delivery`。
4. RunOutcome finalize 时校验 artifact 列表与磁盘一致，并在写 Manifest 后重新计算最终 hash；避免 Manifest 列表遗漏后生成的自身和报告文件。

#### 修改文档

1. `StarPlan/README.md` 和 `StarPlan/skills.yaml` 只描述实际生成的文件和已通过终态。
2. 更新 `StarPlan/starplan_skills/qwen_client.py` 顶部旧 FactCard 协议说明为 Claim/ExpressionPlan 协议。
3. 不改写 `starplan-project-guidance/starplan-error-check-and-phase-plan-2026-07-29-p1-completion.md` 和 `starplan-project-guidance/starplan-error-check-and-phase-plan-2026-07-29-p2-completion.md` 的历史正文。由本独立复查报告明确 supersede 其中与反例冲突的“完成”结论；最终验收通过后，在 project plan 当前状态和 README 中引用旧报告、纠错 commit、固定 run ID 与新验收证据，形成可追踪更正链。
4. 文档更新必须引用最终 CI 命令、commit、固定 run ID 和 artifact verifier 结果。

#### P1-C 验收标准

- README、skills contract、代码 Schema、运行产物和测试期望五者一致。
- 随机抽一个 run，可以从 Manifest 找到所有 Claim/规则/模板/模型调用和输出 hash，并由 verifier 重算。

### 3.3 建议提交顺序

为降低一次性大改风险，团队应按以下顺序独立提交，每个提交包含对应失败测试、实现和当次 error-check 报告：

1. `P0-A claim-integrity`：只处理封存 hash、源快照和篡改测试。
2. `P0-B unified-render-gate`：处理模板、可观测/不可观测完整渲染与 trace。
3. `P0-C runoutcome-cutover`：处理全路径状态和基础 artifacts。
4. `P0-D evidence-review`：处理复盘 Evidence Claims 和修订计划。
5. `P0-E chat-public-boundary`：处理 Chat 统一渲染与公共 DTO。
6. `P1-A privacy-export`：处理字段级脱敏与导出 verifier。
7. `P1-B acceptance-ci`：收紧 Layer 3、离线环境和终态矩阵。
8. `P1-C contract-sync`：最后同步 `StarPlan/README.md`、`StarPlan/skills.yaml` 和阶段状态。

不得把上述八项压成一个大提交，也不得在前一项验收失败时继续宣布后一项完成。

### 3.4 总体验收门槛

只有同时满足以下条件，才能关闭 project plan 第 3/4 周并进入第 5 周：

1. 用户可见无来源事实率为 0。
2. 阻断模型原文在公共响应和交付文件中的泄漏率为 0。
3. 所有用户可见事实字段的 Claim/render trace 覆盖率为 100%。
4. Registry、源快照、规则、模板任一被篡改时均 fail-closed。
5. 六类终态都有一致 RunOutcome、Manifest、Validation Report、审计事件和安全公共结果。
6. 复盘每条归因、建议和修订都能追溯到 Evidence Claim；不确定性不会被升级。
7. 隐私导出不包含 observer notes、prompt、messages、blocked content 或旧审计文件。
8. 官方离线 CI 零失败、零错误、零网络调用；在线 Qwen 仅为独立兼容性 canary。

## 4. Immediate Next Actions

1. Qwen 先在 `StarPlan/tests/test_claims_registry_b.py` 增加 Claim 值、源快照、规则和模板四类篡改失败测试，确认当前版本确实失败。
2. 只修改 `StarPlan/starplan_skills/claims.py` 与 `StarPlan/starplan_skills/expression_validator.py` 完成 P0-A，不同时重构 renderer 或 runner；通过 P0-A 验收后立即提交。
3. 第二个增量审计 `StarPlan/starplan_skills/templates.py` 中所有附加事实，删除温度预测和伪 `procedural.*` 映射，再统一可观测/不可观测 render trace。
4. 第三个增量把 RunOutcome 创建点移动到 `StarPlan/starplan_skills/runner.py::run_starplan()` 入口，优先让工具异常和目标歧义产生完整终态，并同步修改 `StarPlan/starplan_skills/schemas.py::CalculationManifest`。
5. 完成上述三项后再迁移 `StarPlan/starplan_skills/observation_review.py` 和 Chat，避免它们继续建立在不可信 Registry/Outcome 基础上。
6. 最后重写 Layer 3、隐私导出和离线 CI；旧测试通过不得作为新架构验收证据。
7. 总体验收八项全部通过后，才按 project plan 进入第 5 周“演示入口和三类案例”。
