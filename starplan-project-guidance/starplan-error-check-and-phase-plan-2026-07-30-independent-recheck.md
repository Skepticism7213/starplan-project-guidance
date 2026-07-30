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
| CRITICAL | Claim 篡改保护无效 | `claims.py:100-105` 的 `registry_hash` 每次访问都从当前 Claim 重算；`expression_validator.py:230-246` 又用当前 Claim 重算值与该动态值比较。定向反例把视星等 Claim 从 `3.4` 改为 `99.9`，保留旧 `source_hash`，验证仍返回 `passed=true`。 | 未修复。构建 Registry 时冻结 `registry_hash`；验证时从不可变源快照和规则版本重新构建或重算每个 Claim，而不是信任内存中的 Claim 对象。任意 Claim、源快照、规则或 Registry 改动都必须进入 `VALIDATION_BLOCKED`。 |
| CRITICAL | 确定性模板仍绕过 Claim Registry | `outreach_pack.py:168-190` 根据月份写入无天气数据支持的温度判断，而 `claims.py:633-643` 明确禁止天气/温度预测；`outreach_pack.py:220-237` 把流程、设备、安全、核对文本映射到 Registry 中不存在的 `procedural.*` ID。固定可观测案例 35 个映射项中有 20 个使用未注册 ID；其中包括“夜间气温可能降至 10°C 以下”。 | 未修复。删除“代码生成即可信”的例外。流程时间、设备适配、安全事实、温度、地点开放状态等都要使用已注册 Claim；纯命令性文字只能使用无事实的批准模板并具有真实 Registry 条目。最终门禁必须逐个检查输出句子，而不能按前缀豁免。 |
| CRITICAL | 不可观测路径没有 Claim/渲染追踪 | `_generate_not_observable_pack()` 在 Claim fallback 后继续追加 `_build_not_observable_talking_points()`、替代建议、流程和核对项；固定不可观测案例有 24 个 Markdown 列表项，却没有 `sentence_claim_map.json`、`expression_plan.json`、`render_trace.json` 或 `audit_events.jsonl`。 | 未修复。可观测和不可观测路径必须进入同一个 Output Claim Gate；`blocking_reasons[]`、替代目标、改期建议和核对项均生成 Claim 与逐句 render trace。缺少映射即阻断交付。 |
| CRITICAL | `observation_review` 没有实现 Evidence Claim 闭环 | `observation_review.py:84-157` 直接生成归因、建议和计划修订，未建立 Evidence Claim 或句子映射；输出自行规定“云量 > 50% 转为室内讲座”、提前 30 分钟、错过高高度窗口等规则。复盘产物也没有 render trace。 | 未修复。把日志原始字段、计算差异、归因类别、建议规则和修订字段分别建模为 Evidence Claim；Qwen 只能选择 Claim/类别。没有规则或证据支持的阈值必须删除或标为人工确认，`possible`/`undetermined` 不能被后续确定性句子重新说成确定事实。 |
| CRITICAL | RunOutcome 不是实际的单一事实来源 | `runner.py:221-275` 在解析、计算、活动包和复盘完成后才创建 RunOutcome。强制工具异常和目标歧义都在此前抛出，运行目录分别只有 3 个和 2 个文件，没有 `run_outcome.json`；歧义也未落盘 `NEEDS_CONFIRMATION`。`runner.py:257-258` 独立生成 Validation Report；`run_outcome.py:186-188` 又把不可观测业务状态覆盖进 Manifest 的验证状态。实测不可观测 run 的 RunOutcome 为 `validation=passed`，Manifest 为 `target_not_observable`。 | 未修复。收到输入后立即创建并增量保存唯一 RunOutcome；所有异常分支捕获为明确业务/验证/交付状态。Manifest、Validation Report、审计事件和返回值只投影 RunOutcome，不得二次推断或覆盖正交状态。 |
| CRITICAL | Chat 仍向调用者暴露被阻断的模型原文 | `runner.py:814-820` 虽把 `final_content` 换成确定性摘要，但 `runner.py:854-863` 仍把 `blocked_content` 和含原文的 `messages` 放入公共返回对象。Mock 运行中错误文字“肉眼清晰可见且光污染较低”同时出现在这两个字段；核查还错误标记 `passed=true`。确定性摘要自身也绕过 Claim Registry，并声称所有数字均来自 Astropy。 | 未修复。公共响应 DTO 只能含已验证内容和公开状态；模型原文、messages、prompt 只写入受控审计存储，不得通过普通 API 返回。Chat 也必须生成 Claim Registry、RunOutcome 和 render trace；不能用另一套摘要器代替统一门禁。 |
| WARNING | 证据产物和模型调用记录不完整 | 成功运行没有计划要求的 `expression_plan.json`、`render_trace.json`、`audit_events.jsonl`。Manifest 的模型使用仅根据 `outreach.qwen_used` 手工补一条事件，不能从真实 `model_call_log.jsonl` 反推，可能漏掉复盘调用、失败调用或只审查未交付的调用。 | 未修复。定义固定 artifact contract；运行结束前校验必需文件。模型状态从结构化调用日志聚合，至少记录阶段、模型、调用结果、是否被采用、失败原因和关联审计事件。 |
| WARNING | 隐私导出只过滤文件名，没有字段级脱敏 | `privacy.py:103-134` 将 `DELIVERABLE_FILES` 原样复制。实测导出仍在 `input.json`、`review_report.md`、`calculation_manifest.json` 中保留完整 observer notes。复用已有导出目录时也不会清除已存在的旧审计文件。 | 未修复。对 JSON/Markdown 使用字段级导出 schema 和渲染器，observer notes 默认删除或摘要化；导出必须写入全新空目录，完成后做敏感字段与审计文件 deny-list 扫描。 |
| WARNING | Layer 3 测试允许错误实现通过 | `test_layer3_e2e.py:130` 的工具异常用例接受抛出任意异常；`test_layer3_e2e.py:331-356` 只要求至少 5 个映射；`test_layer3_e2e.py:369-375` 自动豁免全部 `procedural.*` ID；纯文字幻觉测试只要求存在备用摘要，没有断言验证器识别错误事实。 | 未修复。端到端测试必须断言精确最终状态、完整 artifact contract、100% 输出事实映射、零未注册 ID、零公共 blocked-content 字段；不能把当前实现缺陷写成可接受分支。 |
| WARNING | “离线 CI”并不保证离线 | `scripts/run_offline_ci.bat` 只忽略 `test_qwen_integration.py`，没有覆盖或清除已由 `.env` 加载的 `DASHSCOPE_API_KEY`。本次按官方脚本运行时出现真实 Qwen 调用。 | 未修复。离线入口必须在进程启动前显式禁用网络模型，并用 fake provider/mock transport；若发生任何真实模型调用，CI 立即失败。在线 canary 应使用独立命令。 |
| INFO | 文档和代码契约仍有漂移 | README/`skills.yaml` 声称完整 Evidence Claims、正交 RunOutcome 和句子覆盖；`qwen_client.py` 仍描述旧 FactCard 协议。P2 完成报告把部分路径或组件测试通过表述为整体完成。 | 未修复。文档状态只能由可复现验收证据更新；在 P0 修复前把相关条目标记为“部分完成/未验收”，统一 Qwen 工具协议说明。 |

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

当前不进入新 enhancement，先按以下顺序重新关闭第 3/4 周验收。

### P0-A：统一可信输出与完整性门禁

1. 冻结 Registry hash，并从不可变源快照、版本化规则和批准模板重新验证 Claim。
2. 建立唯一 Output Claim Gate，覆盖可观测包、不可观测包、Chat、复盘、回退和导出内容。
3. 删除 `procedural.*` 无条件豁免；纯动作模板也要有注册条目，夹带时间、温度、设备能力、地点状态等事实时必须引用 Claim。

验收标准：篡改任一 Claim/源/规则/模板必定 blocked；所有用户可见事实句 100% 映射到 Registry 中真实存在的 Claim；温度等无来源事实为 0。

### P0-B：RunOutcome 全路径切换

1. 输入接收后立即创建并增量持久化 RunOutcome。
2. 为歧义、数据不足、工具异常、不可观测、验证阻断分别实现确定性终态与最小安全输出。
3. Manifest、Validation Report、审计事件、返回 DTO 只从 RunOutcome 生成；删除业务状态覆盖验证状态的逻辑。

验收标准：六类业务/失败分支都有 `run_outcome.json`、一致的报告和审计事件；状态三轴正交；任何异常都不能只留下半个运行目录。

### P0-C：Evidence Claim 复盘闭环

1. 把日志证据、偏差计算、归因规则、建议和修订字段 Claim 化。
2. 对“提前 30 分钟”“云量 50%”“错过高高度窗口”等规则建立来源和适用范围；没有依据则改为人工确认或删除。
3. 生成复盘 render trace，并验证 `possible`/`undetermined` 的措辞不会升级为确定结论。

验收标准：复盘每条事实、原因、建议和计划差异均能追溯；删除任一证据后，相应结论降级或消失。

### P1：公共边界、隐私与真实离线 CI

1. 分离 public result 与 audit record；公共返回中不出现 `blocked_content`、原始 messages 或 prompt。
2. 使用字段级 export schema 脱敏，并只允许导出到新空目录。
3. 离线 CI 注入禁止网络的模型 provider；真实调用即失败。修复 Windows 临时目录用例，使官方命令无需手工 deselect 即全绿。
4. 重写 Layer 3 断言：精确状态、完整 artifacts、100% 映射、零未注册 ID、零隐私泄漏。

验收标准：官方离线命令零网络调用、零失败、零错误；Mock 幻觉只存在于受控审计文件；导出扫描不含 observer notes 和 audit 文件。

## 4. Immediate Next Actions

1. 先修 Claim hash 篡改反例和模板 `procedural.*` 绕行，这是可信输出的根门禁。
2. 随后把 RunOutcome 移到入口，并先完成工具错误与目标歧义两条失败路径。
3. 再把 `observation_review` 迁移到 Evidence Claim，而不是继续补关键词或自由文本规则。
4. 最后重写 Layer 3 与离线 CI；旧测试通过不能作为 P0/P1 完成证据。
5. 上述验收全部通过后，才按 project plan 进入第 5 周“演示入口和三类案例”。
