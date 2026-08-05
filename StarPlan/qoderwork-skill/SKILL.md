---
name: starplan-loop
description: "面向 AI 的校园天文观测与科普实训闭环：当用户提出观测目标（如 M31、毕宿五、土星、流星雨等）、观测日期与地点、科普活动策划、观测日志复盘、下一轮观测安排，或提到星程/StarPlan/天文观测计划/可观测性/活动包/复盘等关键词时自动触发。所有天文数值必须通过 MCP 工具计算，禁止模型凭记忆编造。"
version: 0.9.0
---

# 星程 StarPlan Loop：可信天文实训闭环

## 目标

把一次校园/青少年天文活动做成可计划、可执行、可检查、可复现、可改进的闭环：

```text
观测请求
→ 确定性天文计算（目标解析、可观测性、活动时段）
→ 科普活动包（组织者 / 讲解员 / 学习者三视图）
→ 观测日志
→ 证据复盘
→ 修订后的下一轮计划
```

核心原则：**工具算，模型讲，报告验，人员确认，日志促改进。**

## 触发条件

出现以下任一场景即触发本 Skill：

- 用户给出天体/天象名称 + 地点 + 日期，询问“能不能看 / 几点看 / 怎么组织”。
- 用户要求生成观测计划、活动流程、讲解词、设备清单或安全提示。
- 用户导入实际观测记录，要求对比计划、分析偏差、修订下一次活动。
- 用户提到“星程”“StarPlan”“科普观测”“天文社活动”“青少年天文”等主题词。

## Steps

1. **识别闭环入口**
   - 首次规划：调用 `starplan.run`，传入统一输入（target、location 或 location_detail、date_range、audience、equipment、goal、constraints、activity_preferences、audience_profile）。
   - 含观测日志的复盘闭环：在输入中附上 `observation_log` 后调用 `starplan.run`，或直接调用 `starplan.run_loop` 一次完成“计划 → 复盘 → 下一轮 → 二次运行”的 before/after 对比。
   - 只查单个环节时，可调用 `skill.target_resolve`、`skill.resolve_location`、`skill.observability_plan`、`skill.outreach_pack`、`skill.observation_review`。

2. **不要自己计算或凭记忆补数值**
   - 坐标、高度角、方位角、airmass、暮光、月光影响、窗口时间、活动时段、风险等级全部由 MCP 工具返回。
   - 面向用户的事实句必须**原样引用**工具返回的渲染文档（`outreach_pack*.md`）或返回中的内容，不得改写、扩写、概括其中的数值。
   - 模型可以补充的只有非事实性内容：礼貌用语、操作引导、对渲染文档的原文引用。

3. **按返回状态如实转达**
   - `validation_status=passed` 且 `delivery_status=delivered/template`：正常交付，可向用户展示活动包摘要并指出完整产物路径。
   - `is_observable=false`：展示 `not_observable_reason` 与 `alternative_suggestions`，建议改期或换目标，不要自行给出“观测建议数值”。
   - `validation_status=blocked` / `delivery_status=not_delivered`：如实告知用户本次未交付，不得用自身知识补写活动内容。
   - `review` 非空：展示偏差摘要、原因分类与 `next_input_path`，说明下一轮输入已可执行。

4. **复盘与下一轮**
   - 复盘必须引用结构化时间差等证据；原因不足时按 `undetermined` 处理，不要臆断归因。
   - 生成 `next_activity_input.json` 后，如需对比，调用 `starplan.run_loop` 或直接读取该文件作为下一轮输入再次调用 `starplan.run`。

5. **输出规范**
   - 给用户的总结包含：目标、地点、日期、科学窗口/活动时段、关键风险、产物文件路径、需要人工确认的清单（未成年人活动必须确认监护人许可、成人陪同、点名）。
   - 所有数值句保持与工具输出字面一致，保留单位与时区。

## Pitfalls

- **禁止编造任何天文数值**：时间、高度、方位、星等、月相、距离、窗口等一律来自工具。用户直接问“今晚 X 点 Y 高度多少”时，先调用工具再回答。
- **禁止改写渲染结果**：科普包是 Claim 证据链渲染的最终文档，任何数值改写都会破坏可追溯性。
- **不要混淆科学窗口与活动时段**：科学窗口是“目标可见”的区间，活动时段（activity_slot）是含准备/收尾的现实安排，两个都展示但别混为一谈。
- **不要把工具失败当成不可观测**：报错时如实说明“计算失败”，不要给结论。
- **不要要求用户提供 API Key**：本 Skill 通过 MCP 本地确定性工具工作，不需要任何 Key。
- **不要在输出中泄露内部路径或日志细节**：给用户可读摘要和产物路径即可。

## Verification

- 调用 `starplan.run` 后确认返回包含 `run_id`、`validation_status`、`plan_summary`；可观测案例应含 `activity_slot` 与 `outreach_pack`。
- 对照 `runs/<run_id>/` 下的 `plan.json`、`outreach_pack.md`、`validation_report.md` 是否生成。
- 含日志的输入应生成 `review` 与 `next_input_path`；二次运行后应有 before/after 差异。
- 对同一输入重复调用，科学数值应一致（确定性计算）；只有活动时段等策略字段按规则变化。
- 向用户展示前，先人工确认高风险项（天气以现场为准、未成年人安全清单、设备可用性）。
