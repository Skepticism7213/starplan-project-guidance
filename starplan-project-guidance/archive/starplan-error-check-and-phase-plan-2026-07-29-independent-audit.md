# StarPlan Loop 错误检查与阶段计划 — 2026-07-29 更新同步独立审计

日期：2026-07-29
审计基线：`main` / `7c8213c`（与 `origin/main` 一致）
审计范围：`ef887ec..7c8213c` 新增的 Claim 架构、Qwen 复盘归因、不可观测分支修复、测试、运行产物和项目报告
审计性质：只读复盘；本轮未修改生产代码

## 1. Error Check

### 1.1 静态检查

| 严重度 | 位置 | 问题 | 处置 |
|---|---|---|---|
| CRITICAL | `runner.py`、`outreach_pack.py`、`templates.py` | Claim Registry 只覆盖讲解要点；活动流程、设备、安全、人工核对、不可观测补充文本仍可直接写入用户 Markdown。一次 M31 运行中仅 9 个句子有映射，而 Markdown 有 32 个列表项，至少 23 项没有 Claim 映射。 | 未修复；必须把所有用户可见事实句纳入 Claim/程序性无事实模板，并以 `render_trace.json` 做最终门禁。 |
| CRITICAL | `runner.py:768`、`runner.py:879` | Chat 最终结果仍是 Qwen 自由文本，只做数字正则核查；纯文字反例“肉眼清晰可见、光污染较低、非常适合新手”返回空违规列表并会通过。 | 未修复；Chat 必须改成结构化 ExpressionPlan + 确定性渲染，或在迁移完成前禁用自由文本最终输出。 |
| CRITICAL | `outreach_pack.py:264-265`、`outreach_pack.py:306-346` | 不可观测分支在 Claim 渲染后追加自由文本，固定声称“最高高度角过低”“太阳方向附近/地平线以下”“最佳观测季节”。强月光约束反例中 M31 最高高度角为 `85.05°`，系统却输出“不满足 30.0°”和“地平线以下”。 | 未修复；不可观测原因必须来自结构化 `reason_code`/Evidence Claim，按原因分别渲染，禁止按目标类型猜原因。 |
| CRITICAL | `observation_review.py:323-446`、`runner.py:206-211` | Qwen 复盘归因仍返回自由原因和建议，只做数字过滤；没有 Evidence Claim、句子映射或文字事实校验。runner 未传 `log_path`，复盘模型调用不进入本次 `model_call_log.jsonl`；异常被静默吞掉。 | 未修复；复盘输入、原因、建议和修订字段都要 Claim 化，调用事件必须进入统一审计流，失败必须显式记录并回退。 |
| CRITICAL | `runner.py:217-245` | `run_starplan` 仍调用旧 `_write_validation_report` 和 `_build_manifest`，孤立的 `RunOutcome` 没有接入主流程。运行目录没有 `run_outcome.json`、`audit_events.jsonl`、`expression_plan.json`、`render_trace.json`。 | 未修复；先完成唯一 RunOutcome cutover，再允许报告宣称 Phase E 完成。 |
| WARNING | `expression_validator.py:217-230`、`claims.py:619-623` | 来源哈希只检查“存在且长度为 16”，不重新计算源数据、不校验 registry hash，也不与 Manifest 绑定；任意 `0000000000000000` 哈希反例仍通过。 | 未修复；保存源快照、规则版本和 registry hash，验证时重新计算并对受保护产物做完整性失败闭环。 |
| WARNING | `claims.py:385-501` | “视星等阈值 → 肉眼可见/双筒可见/适合新手/设备匹配”是过度简化规则，未考虑天空背景、光污染、表面亮度、消光、目标类型、口径和观测经验，属于规则层科学过拟合风险。 | 未修复；规则需显式列出适用范围和缺失输入，不能把粗略上限渲染成确定效果承诺。 |
| WARNING | `schemas.py:59-80`、`runner.py:59-241` | 虽声明 14 个 `RunState`，实际状态日志只有 `received → input_validated → ready_to_compute → computed_* → rendered`，没有 `CLAIMS_BUILT`、`EXPRESSION_PLANNED`、`VERIFIED`、`VALIDATION_BLOCKED`、`ARCHIVED`，也没有独立工具错误/数据不足路径。 | 未修复；状态转换、失败原因和交付状态必须在同一 RunOutcome 中落盘。 |
| WARNING | `run_outcome.py:50-57`、`run_outcome.py:186-188` | `TARGET_NOT_OBSERVABLE` 被放进 validation status，随后覆盖验证状态，重新混淆业务结论和验证结论；RunOutcome 的约束、人工覆盖、文件哈希也没有写入 Manifest。 | 未修复；业务状态、验证状态、交付状态保持正交，不可观测不能覆盖验证状态。 |
| WARNING | `skills.yaml:77-93`、`README.md:44-57` | Skills 合约仍写 `FactCard` 和“数值过滤”，没有 Claim Registry、ExpressionPlan、RunOutcome 或完整输出文件；README 也未说明新证据文件和实际状态。 | 未修复；代码 Schema、`skills.yaml`、README、示例和 Qwen 工具定义必须由同一版本契约生成。 |
| WARNING | `observability_plan.py:119-121`、`observability_plan.py:135-142` | `astropy_default` 注释声称使用内置折射，但 `AltAz` 默认通常是 `pressure=0`，实际不启用大气折射；`refraction_policy` 也未写入 Manifest。 | 未修复；明确命名为无折射或显式设置压力，并将策略和参数纳入证据。 |
| WARNING | `claims.py:79`、`observation_review.py:43` | Claim 作用域时区硬编码为 `Asia/Shanghai`，受众几乎不参与 Claim 生成，`HUMAN_CONFIRMED` 没有实际写入路径。 | 未修复；从地点和输入传递 IANA 时区，人工确认必须形成可审计 Claim，受众只影响表达变体而不改变事实。 |
| WARNING | `tests/test_confidence_algorithm.py:20-22` | 测试模块导入时替换全局 stdout/stderr，导致默认 pytest 捕获在清理阶段崩溃；全量默认 pytest 不能作为可靠 CI 命令。 | 未修复；测试脚本不得修改全局流，使用局部输出配置或独立脚本入口。 |
| WARNING | `tests/layer23_validation.py:118-126`、`StarPlan/data/` | `simbad_dim_otype.json` 未入库，Checks 7/11 被跳过；本次 Layer 2/3 退出码为 1，并报告 M24/M52 两个低精度警告。 | 未修复；补充可复现的受信快照，或把“跳过”明确升级为阻断状态，不能称完整通过。 |
| INFO | `observability_plan.py:210-215` | 多日 `date_range` 只计算第一晚，只打印提示；接口和计划仍表现为日期范围。 | 记录为范围边界；若当前 MVP 保持单晚，必须在 Schema、README、报告和验收中明确限制。 |
| INFO | `runner.py:803-812`、`qwen_client.py:464-484` | Chat 会保存完整消息和被阻断原文，复盘提示可能含 observer notes；当前没有脱敏、保留期或隐私字段级策略。 | 未修复；演示前应定义敏感信息最小化、审计保留和导出规则。 |

### 1.2 运行检查

| 检查 | 结果 | 解释 |
|---|---|---|
| `compileall` | PASS | `starplan_skills`、`scripts`、`tests` 编译无错误。 |
| 示例 Schema | PASS | `validate_examples.py`：3/3。 |
| Layer 1 | PASS | 150 目标、10 轮，0 个唯一问题。 |
| Layer 2/3 | FAIL/INCOMPLETE | 退出码 1；缺少 SIMBAD 快照，且 M24/M52 两个精度警告；两类检查跳过。 |
| 离线 pytest | PASS（受限集合） | 排除会修改全局 stdout 的 confidence 脚本和在线 Qwen 文件后，沙箱外 `105 passed, 1 warning`。单独运行 confidence 脚本为 150/150。 |
| 默认全量 pytest | FAIL | 导入 `test_confidence_algorithm.py` 后 pytest 捕获流被关闭；这是测试工程阻断，不是业务断言通过。 |
| 真实 Qwen 集成 | 部分通过 | 首次运行 `6 passed, 1 error`，唯一错误是 `tmp_path` 权限；同一用例在授权环境单独重跑 `1 passed`。 |
| Chat canary | 安全回退但不可用 | 两次真实 Chat 均检测到 13/21 个无法精确匹配的数字并回退；测试只断言 `passed` 字段存在，没有断言为真或验证最终内容。 |
| 固定案例 | 运行完成 | 案例 1/2/3 退出码均为 0，实际产物分别为 12/11/15 个，但均缺计划中的 RunOutcome、审计事件和表达计划/渲染追踪文件。 |

### 1.3 定向反例

1. 纯文字 Chat 幻觉：`_check_chat_hallucination` 对无数字的错误事实返回 `[]`，因此旧 Chat 路径会判定通过。
2. 伪造哈希：把 observed Claim 的 `source_hash` 改成任意 16 字符值，8 步验证仍 `passed=True`。
3. 协议越界：`ExpressionPlan` 接收额外 `free_fact` 字段并静默丢弃，未留下“协议字段越界”审计事件。
4. 强月光失败：M31（2026-10-26，`max_moon_illumination=0.01`）最高高度角 `85.05°`，因满月约束不可观测；最终文案仍声称高度角过低和目标在地平线以下。
5. 映射覆盖：案例 1 的 `sentence_claim_map.json` 只有 9 句，`outreach_pack.md` 有 32 个列表项，映射门槛不能据此宣称 100%。

## 2. Completion Status

| 计划阶段 | 当前判断 | 依据 |
|---|---|---|
| Phase A：Schema 冻结 | 基本完成 | Claim/RunState/ExpressionPlan 模型和数值显示规则已存在，tzdata 已补齐。 |
| Phase B：Claim Registry 与模板安全化 | 部分完成 | Registry 和模板库存在，但模板、流程、设备、安全和不可观测补充文本没有纳入 Registry；派生规则科学边界未冻结。 |
| Phase C：结构化表达与 fail-closed | 仅 outreach 子路径完成 | Qwen 表达计划 → 确定性句子的路径可运行；Chat 和复盘仍自由文本，且 ExpressionPlan 之外的用户输出没有同一门禁。 |
| Phase D：状态机与科学内核 | 部分完成 | 月距函数方向正确并有回归测试；主状态机未覆盖声明的全部状态，失败原因未结构化，折射策略未固化。 |
| Phase E：RunOutcome 与证据链 | 未完成 | `run_outcome.py` 是孤立实现；主流程仍用旧 Manifest/Validation 构建，计划产物和文件哈希没有实际生成。 |
| Phase F：全量对抗验收 | 未完成 | 现有 30 个对抗测试主要直接测 validator/renderer；没有覆盖完整用户输出、RunOutcome、审计事件、10 类 Layer 3 分支和强月光反例。 |

### 本阶段理应做到但没有做到

以下不是后续增强项，而是当前 MVP 和第 3/4 周验收已经要求的基线：

1. **所有用户可见事实统一经过 Claim 门禁**：因为迁移只包住 talking points，旧 Markdown 生成器和不可观测补充仍被保留，造成事实出口分叉。
2. **业务、验证、交付状态统一且可审计**：因为 RunOutcome 先被实现为独立模块，runner 没有完成 cutover，实际运行仍产生旧 Manifest 和 5 段状态。
3. **不可观测原因忠实于实际约束**：因为系统只保存 `is_observable` 和风险文字，没有保存“哪条约束阻断窗口”的结构化原因，模板只能猜“高度过低”。
4. **复盘归因复用 Evidence Claims**：因为复盘 Qwen 被作为独立增强接入，未等待 Claim/RunOutcome 完整闭环，且调用日志参数没有贯通。
5. **科学派生规则可解释、可适用**：因为实现用视星等阈值替代天空背景、表面亮度、设备和目标类型模型，形成“代码生成的规则幻觉”。
6. **契约、文档和代码同步**：因为 `skills.yaml`/README 仍是早期 FactCard 版本，Schema 已变化但没有版本化门禁。
7. **Layer 3 和真实验收口径闭合**：因为测试主要验证组件是否符合自身规则，没有从 Mock Qwen/工具异常一路断言最终 Markdown、状态、审计事件和回退内容。
8. **可重复验证环境可直接运行**：因为 confidence 测试改全局输出流、临时目录依赖宿主权限，默认 pytest 和在线集成命令都不能在当前环境无额外处理地完成。

本次复盘不把行星、实时天气、Stellarium/Aladin、复杂前端等明确后置项列为缺陷；它们不影响当前核心闭环验收。

## 3. Corrective Phase Plan

### P0：恢复可信输出边界（下一轮实现前置）

1. 建立 `OutputClaimGate`：活动流程、设备清单、安全提示、人工核对、替代建议、复盘报告和修订计划的每个事实句都必须带 Claim ID；纯程序动作文字单独标记为 `procedural`，不得夹带未经来源支持的事实。
2. 将不可观测计算输出改为 `blocking_reasons[]`，至少区分高度/airmass、月光、暮光、数据不足、工具错误；原因、阈值和实际值全部从同一计算结果渲染。
3. 在 `runner` 中创建并持有唯一 RunOutcome，按 `RECEIVED → ... → CLAIMS_BUILT → EXPRESSION_PLANNED → VERIFIED/VALIDATION_BLOCKED → RENDERED → ARCHIVED` 写入状态和审计事件；所有报告从它生成。
4. Chat 迁移到同一 Claim/ExpressionPlan 路径。迁移完成前，Chat 只能返回确定性摘要，不得把自由文本作为“通过”结果返回。
5. 复盘将计划字段、日志字段、原因类别和改进建议转为 Evidence Claims；Qwen 只选择已有证据和类别，缺证据强制 `possible`/`undetermined`；传入统一 `log_path`，失败写入审计并回退。

### P1：校准科学规则和证据完整性

1. 对肉眼/双筒/新手/设备匹配规则增加输入前提、目标类型、表面亮度/天空条件和“不足则待确认”分支；为 M31/M42 及边界目标加入负例。
2. 对 Claim 源数据、registry、规则、模板、Manifest 关键文件重新计算哈希；任意篡改必须使验证状态变为 `blocked`，不能只检查字符串长度。
3. 去除 Claim 作用域时区硬编码，明确 AltAz 折射策略并写入 Manifest；将 `ExpressionPlan` 和工具定义设为 `extra=forbid`，验证 section/tone/connector 的实际含义。
4. 同步 `skills.yaml`、README、示例和工具 Schema，增加 Claim、RunOutcome、失败状态和真实产物清单；保留单晚 MVP 限制的显式声明。

### P2：验收和工程卫生

1. 补齐 Layer 3 的 10 类端到端用例，特别是强月光、工具异常、数据不足、Qwen API 不可用、纯文字幻觉和完整 Markdown 映射。
2. 将 SIMBAD 交叉验证快照作为受信测试夹具或明确阻断缺失，修复 M24/M52 精度告警的规则/数据解释。
3. 删除测试脚本对全局 stdout/stderr 的替换，修复 class-scoped fixture 弃用警告，提供一条默认可运行的 offline CI 命令。
4. 为 `chat_conversation.json`、模型 prompt preview 和复盘日志增加脱敏、保留期和导出边界；阻断原文只进审计，不进入演示用户输出。

### 阶段验收标准

- 固定三案例和强月光反例均能生成完整 RunOutcome 目录；缺一个计划产物即失败。
- `render_trace.json` 覆盖 Markdown、JSON、复盘报告和 Chat 最终内容中的 100% 事实句。
- 任意纯文字幻觉、错误单位、错误时区、伪造 Claim、协议额外字段和哈希篡改均不出现在用户输出，且有审计事件和确定性回退。
- `business_status`、`validation_status`、`delivery_status` 互不覆盖；不可观测仍可验证通过，工具失败不得伪装成不可观测。
- 默认离线 pytest、Layer 1/2/3 和三个案例命令在干净环境可直接运行；真实 Qwen canary 只做兼容性检查。

## 4. Immediate Next Actions

1. 暂停继续增加自由文本能力，先把 P0 的统一输出门禁和 RunOutcome cutover 做成一条完整主路径。
2. 用 M31 强月光反例和纯文字 Chat 反例作为第一批阻断回归，不接受只测 validator 的“通过”。
3. 清点并标记所有用户可见字段，生成事实句 → Claim → source → file hash 的覆盖报告。
4. 修复 `skills.yaml`/README 与代码 Schema 的契约漂移，再重新运行完整 Layer 3 验收。
5. 只有上述门槛通过后，才更新项目全面审视报告中的“Phase A→F 全部落地”和“无来源事实率=0”结论。
