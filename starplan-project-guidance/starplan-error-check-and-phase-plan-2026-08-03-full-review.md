# StarPlan 错误检查与阶段计划 — Skill 包全面审查（2026-08-03）

日期：2026-08-03
分支：`main`（`d9b1f22`，与 `origin/main` 一致）
范围：对 `StarPlan/` 技能包与规划文档做全面深度审查（对照赛题官方要求），并产出完整审查报告与改进建议；本报告为 AGENTS.md 要求的必交错误检查与阶段计划报告。
审查报告：`starplan-skill-package-full-review-2026-08-03.md`

## 一、Error Check

### 静态 + 运行时扫描结果（本次实际执行）

| 检查 | 结果 |
|---|---|
| `python -m compileall -q starplan_skills scripts tests` | PASS |
| `python -m pytest -q`（离线、无 Key） | 185 passed, 9 skipped, 0 failed（87.0s） |
| `python scripts/validate_examples.py` | 3 passed, 0 failed |
| README 三案例（offline） | M31 / M42 / Review 均正常终态；16 / 16 / 20 个产物 |
| `git diff --check` | PASS |
| 科学抽查 | M31@济南四门塔 2026-10-17 峰值 85.04°、airmass 1.004、窗口 19:13–04:28，与 CSV 及物理预期一致 |
| 官方赛题对照 | 已抓取阿里云官网与 NADC 原文并逐条对照 |

### 发现的问题清单（按严重度；本次审查不修改代码，均为"建议修复"或"确认无害"）

| 编号 | 严重度 | 问题 | 状态 |
|---|---|---|---|
| C-1 | CRITICAL | 闭环未闭合：`revised_plan.json` 不满足 `StarPlanInput`，无 `next_activity_input.json`，复盘结果不能重新进入 runner | 未修复（P1 Batch E 范围） |
| C-2 | CRITICAL | 现实活动时段与三类分众输出未实现；M31 活动流程为 9 小时"通宵"式 | 未修复（P1 Batch D 范围） |
| C-3 | CRITICAL | 真实 Qwen 调用证据为零：9 个在线测试全部跳过；无调用凭证/截图；`.env.example` 缺失 | 未修复（P2 范围；缺失文件应顺手补） |
| C-4 | CRITICAL | 三组完整运行记录未入库（`runs/*/` 被 gitignore），人工确认无签名 | 未修复（P3 范围） |
| C-5 | CRITICAL | 20 页 PDF 技术方案、演示视频、复现包均未制作；计划截止日期 09-01 与官方 09-05 不一致 | 未修复（P4 范围 + 文档修正） |
| W-1 | WARNING | 替代目标建议按静态月份表生成，未做实际可观测性验证 | 未修复（建议 P1 顺带处理） |
| W-2 | WARNING | Review 报告无 Claim/交付门禁，改进建议为自由文本 | 未修复（P1 范围） |
| W-3 | WARNING | Qwen 调用无超时/重试/熔断 | 未修复（P2 范围） |
| W-4 | WARNING | 推荐窗口取最长而非综合最优；无反事实解释 | 未修复（可选增强） |
| W-5 | WARNING | 覆盖范围窄：150 目标/8 城市/仅单晚；行星、天象、遮挡模型缺失 | 已确认无害（MVP 边界，文档已声明；需在技术方案中说明扩展路径） |
| W-6 | WARNING | 文档漂移：README 184→实际 185；`.env.example` 缺失；README 五人分工 vs 计划三角色；`run_outcome.json` 的 `state_transitions` 缺最终 RENDERED；`docs/` 目录不存在；根 README 表述过时 | 未修复（低风险，建议随 P0 收尾一并修） |
| W-7 | WARNING | BLOCKED 时结构化公共返回仍含 target/plan 数值（测试合同仅保证 outreach_pack=None） | 未修复（建议文档明确或收紧合同） |
| W-8 | WARNING | 第二环境复现与真实百炼 canary 仍为遗留项（前轮 W-R2/W-R3 未关闭） | 未修复（P2/P3 范围） |
| W-9 | WARNING | 人工确认机制未落地：歧义以抛异常表达；核对项无确认前/后差异记录 | 未修复（P1 范围） |
| W-10 | WARNING | 派生可见性/设备匹配规则偏乐观（caveat 已写，但"适合观测"可能过度承诺） | 已确认无害（claim 内已标注适用范围）；技术方案需说明假设 |
| I-1 | INFO | Windows 控制台中文乱码（代码页） | 已确认无害（文件 UTF-8 正常）；建议演示时 `chcp 65001` |
| I-2 | INFO | 星座/坐标显示为英文（Andromeda、RA/Dec） | 已确认无害；建议加中文变体 |
| I-3 | INFO | `MoonInfo.moonrise/moonset` 恒为 None；README 产物表缺 `observation_log.json`/`review_trace.json` | 已确认无害；建议实现或删字段、补文档 |
| I-4 | INFO | 审计时间戳硬编码 UTC+8 | 已确认无害（需文档注明） |

**结论**：本次审查未修改任何代码，未引入回归。受检代码与数据均可编译、测试通过、三案例可运行；C/W 类问题为"尚未实现的能力/证据"而非"现有功能出错"。

### 2026-08-03 真实 Qwen 实测补充（三把 Key）

| 编号 | 严重度 | 问题 | 状态 |
|---|---|---|---|
| C-3（更新） | CRITICAL | 三把 Key 实测均只兼容 OpenAI 兼容端点下的特定模型（Key-1 曾可用后失效 401；Key-2=qwen3.8-max、Key-3=qwen3.7-plus 兼容端点可用）；当前 `qwen_client.py` 原生 DashScope 调用方式无法使用这些 Key | 已定位，未修复（P2：新增兼容端点适配层） |
| C-6a（新增） | CRITICAL | Chat 模式真实 Qwen 下地点名不一致（用户原话"济南四门塔" vs 标准化名"四门塔景区观星点"）导致 53 项 Saved registry violation，交付 BLOCKED | 已定位，未修复（P2） |
| C-6b（新增） | CRITICAL | Chat `max_tool_rounds=3` 对真实模型不足（每轮 1 个工具，4 工具需 4 轮+收尾），正常路径触顶阻断；8 轮复测可完成全部工具调用 | 已定位，未修复（P2） |
| W-11（新增） | WARNING | 真实调用延迟 6–15s/次、Chat 4 轮合计 36.4s；无超时/重试配置 | 未修复（P2） |
| I-5（新增） | INFO | 真实 ExpressionPlan 中 `schedule.obs_guide`+`schedule_obs_start_v1` 渲染出"开始观测 引导成员使用星桥法寻找目标"等别扭句子，变体白名单过宽 | 已确认无害（不违反门禁），建议 P1 收紧 |
| I-6（新增） | INFO | 三把 Key 均未写入仓库/运行日志；全文检索无 Key 泄漏 | 确认无害；建议用户轮换对话中明文分享的 Key |

**实测证据**：Key-3 + qwen3.7-plus 兼容端点（临时适配层，未入库）下，NL 全链路、案例 1/2/3 均 passed（qwen_expression_plan / template）；Chat 正常路径被 C-6a/C-6b 阻断；Chat 对抗场景正确 fail-closed（识别 2 个不可溯源数值，0 事实输出）。运行目录：`StarPlan/runs/live_nl_q37p`、`live_case1_q37p`、`live_case2_q37p`、`live_case3_q37p`、`live_chat_q37p`、`live_chat_q37p_r8`、`live_chat_notool_q37p`。

## 二、完成状态

| 项目计划阶段 | 状态 | 说明 |
|---|---|---|
| P0 运行阻断与证据门禁（Batch A-C） | 本机验收完成 | 185 passed / 9 skipped；离线三案例正常终态；Claims 篡改与模型证据故障均 fail-closed |
| P0 独立环境复核（W-R2） | 未完成 | 需第二台电脑/干净 CI |
| P0 真实百炼 canary（W-R3） | 未完成 | 无 API Key 环境无法执行 |
| P1 竞赛核心闭环（Batch D/E） | 未开始 | 现实活动时段、三视图、可执行下一轮均未实现 |
| P2 智能体交付 | 进行中（部分验证） | 结构化/NL 入口在真实 Qwen（兼容端点临时适配）下已跑通；Chat 模式存在 C-6a/C-6b 缺陷；客户端与 Key 不兼容（C-3 升级） |
| P3 三案例与真实证据 | 未开始 | 运行记录未入库、无人工复核签名、无实地/演练 |
| P4 提交材料 | 未开始 | 无 PDF/视频/复现包 |
| P5 冻结提交 | 未开始 | 官方截止 2026-09-05；内部建议 09-01 冻结 |

## 三、Phase Plan（未来四周）

| 时间 | 工作 | 验收标准 | 阻塞项 | 风险 |
|---|---|---|---|---|
| 8/3–8/8 | P1 Batch D：活动时段 + 三视图 + 未成年人安全模板 | M31 同时显示科学窗口与 90 分钟活动 slot；M42 无虚假 slot；三视图共享同一 claim_id；测试全绿 | 无 | 活动时段策略阈值需定稿 |
| 8/5–8/13 | P1 Batch E：`next_activity_input.json` + 二次运行 + before/after | next input 过 Schema；二次运行成功；至少一个字段可见变化；删除证据后 patch 消失 | Batch D 验收 | 与现有 Claim 门禁冲突需逐行处理 |
| 8/10–8/17 | P2：① 新增 OpenAI 兼容端点适配层（base_url/model 可配、60s 超时、1 次重试）；② 修复 Chat 地点名归一化；③ max_tool_rounds≥6；④ 收紧变体白名单；⑤ 真实 canary + 加载演示 | 用团队实际 Key 完成一次真实 NL 触发与一次 Chat 工具链交付，validation 均 passed 且留有调用凭证/截图；无 Key 离线仍可交付 | 需要有效百炼 Key/账号 | 模型名不可用、限流、网络 |
| 8/14–8/22 | P3：三案例固化、runs 入库、第二环境复跑、人工复核、实地/桌面演练 | 新环境零失败；每案例有人工确认签名；外部科学复核 1 名以上 | 第二环境可安装依赖 | Windows ACL、天气/场地 |
| 8/18–8/27 | P4：20 页 PDF、6–8 分钟视频、提交包 | PDF ≤20 页；视频 ≤10 分钟；提交清单逐项打勾；隐私扫描通过 | 视频素材 | 剪辑耗时 |
| 8/28–9/5 | P5：冻结、全量回归、打包提交 | 官网提交成功；网盘链接/截图归档 | 报名状态确认（6/30 已截止，需先核实） | 提交系统变化 |

## 四、立即下一步（最小集）

1. **确认报名状态**：团队是否已在 2026-06-30 前完成挑战杯官网报名并盖章上传（硬门槛，若未报名应立即联系赛事答疑群 162255026342 / 左老师）。
2. **修正文档基线**：把计划/转移日志中的截止日期改为官方 2026-09-05（内部冻结 09-01），并补 `.env.example`、README 测试数（185）与分工描述。
3. **启动 P1 Batch D**：先冻结活动时段策略与三视图 Schema，再写失败测试，再实现（按 kickoff prompt 的批次纪律，逐批提交）。
4. **申请/确认百炼 Key 并跑 canary**：验证 `qwen3.7-max` 等模型名可用性；为在线调用加超时。
5. **决定 runs 交付策略**：将三案例运行记录纳入提交包（建议同时入库），并安排第二台电脑复跑。

6. **P2 前置修复（本会话实测发现）**：新增兼容端点适配层与模型配置；修复 Chat 地点名不一致与轮次上限；建议用户立即轮换在对话中明文分享的三把 Key。

提交纪律：本报告与审查报告一起提交推送；代码修复仍按"每个 Batch 独立 commit + 强制报告"执行，受保护架构文件（claims/rendering/expression_validator/runner/outreach_pack/run_outcome/templates/Layer3 测试）的修改须逐行处理并保持门禁全绿。
