# Qwen/QoderWork 竞赛收口执行 Prompt（2026-08-02）

使用方式：把下面完整代码块交给 Qwen/QoderWork。首次只执行 P0 的 Batch A-C；完成、验证、提交并生成强制报告后停止，等待项目负责人确认再进入 P1。不要一次性实现全部阶段。

```text
你现在是 StarPlan Loop 项目的代码实施负责人。你的任务不是重新设计项目，而是在最新仓库基础上，按已冻结的竞赛计划逐批关闭阻断项，并保留可验证证据。

一、最终目标

项目名称：

“星程 StarPlan Loop：面向学校与青少年科普活动的可信 AI Ready 天文实训闭环 Skills 包”。

项目面向中小学教师、青少年科普组织者、高校天文社和其他非专业活动组织者。作品主体是可被 Qwen 智能体加载或调用的 4 个 Skills：

1. target_resolve
2. observability_plan
3. outreach_pack
4. observation_review

核心闭环：

自然语言活动需求
-> Qwen 解析或选择 Skill
-> 确定性天文计算
-> 科学可见窗口与现实活动时段
-> 同源 Claims 的组织者/讲解员/学生输出
-> 活动日志
-> 证据复盘
-> 可再次进入 runner 的下一轮输入
-> 重新生成活动包并显示 before/after

截止时间为 2026-09-01 00:00:00（北京时间）。初赛无答辩，最终材料必须自己说明价值和证据。

二、权威文件和读取顺序

开始任何修改前，完整读取以下文件：

1. 根目录 agents.md
2. starplan-project-guidance/starplan-loop-project-plan.md
3. starplan-project-guidance/starplan-error-check-and-phase-plan-2026-08-02-project-plan-competition-reset.md
4. starplan-project-guidance/starplan-error-check-and-phase-plan-2026-08-02-competition-priority-live-demo-recheck.md
5. starplan-project-guidance/starplan-error-check-and-phase-plan-2026-08-02-phase-a-d-independent-recheck.md
6. starplan-project-guidance/starplan-qoderwork-transfer-log.md
7. StarPlan/README.md
8. StarPlan/skills.yaml

如果文档冲突，以 project plan 为准。`phase-a-d-completion` 只作为历史修复记录，不能作为当前已验收证明。

三、Git 和协作前置门禁

1. 执行 git fetch origin，并确认本地基线包含最新 origin/main。
2. 执行 git status 和 git rev-list --left-right --count origin/main...HEAD。
3. 如果无法确认远端、工作区存在与本任务重叠的未提交修改、或受保护文件发生冲突，立即停止并报告，不得覆盖他人工作。
4. 建议从最新 main 创建独立分支，例如 feature/competition-p0-runtime-contract。不要 force push。
5. 修改 claims.py、rendering.py、expression_validator.py、runner.py、outreach_pack.py、run_outcome.py、templates.py 或 Layer 3/对抗测试时，必须逐行处理，不得用旧文件整份覆盖新架构。
6. 每个 Batch 单独 commit；不要把 P0、P1、P2 合成一个提交。

在真正编辑前，先回复一段不超过 15 行的基线确认：

- 当前 commit
- 本地/远端关系
- 工作区是否干净
- 你读过的权威文件
- 本批只解决什么
- 本批明确不解决什么
- 当前失败证据和预期成功行为

四、不可违反的架构边界

1. Qwen 只负责自然语言理解、Skill 选择、调用编排、Claim/批准句式/顺序/语气选择。
2. 高度角、方位角、airmass、暮光、月光、时间窗口和其他科学结果必须由确定性工具产生。
3. 用户可见科学事实必须来自本次运行的 Claim Registry；模型原始自由文本不得直达用户。
4. 验证失败必须 fail-closed：宁可少交付，不得返回被阻断内容。
5. 不新增第 5 个核心 Skill，不做行星、流星雨、望远镜控制、实时天气、复杂前端、模型微调、多智能体或取证级防篡改。
6. 不新增在线天文服务作为核心依赖。
7. 不读取、显示、复制、记录或提交 .env 中的 API Key。日志不得包含密钥、token、私人数据和完整内部提示词。
8. 不把 GPT/Qwen 的互相认可当作科学验证。科学验收依赖确定性计算、固定参考、运行记录和人工复核。

五、本轮只执行 P0：Batch A-C

不要在同一轮进入 P1 或 P2。先完成以下三个 Batch，分别提交。

--------------------------------
Batch A：正常入口 IERS/leap-second 离线运行
--------------------------------

当前失败事实：

- conftest.py 只在 pytest 中关闭 IERS 自动下载。
- 正常 README 入口仍可能联网等待。
- 最近复验中，空 API Key 条件下 M42 45 秒超时，复盘案例 90 秒超时。

目标行为：

- README M31、M42 和复盘案例不依赖用户已有 Astropy 缓存。
- 网络不可用时不等待远端 IERS/leap-second 更新。
- 30 秒内进入明确终态；若确实无法计算，返回 TOOL_ERROR 或安全状态并写清原因，不能无输出挂起。

先写失败测试：

1. 新增 tests/test_runtime_offline_policy.py 或等价测试。
2. 用子进程创建全新临时缓存，清空 DASHSCOPE_API_KEY，设置不可用网络/代理或可靠禁止下载。
3. 对 M31、M42 至少各跑一次，设置明确 timeout。
4. 当前实现必须先出现超时、联网尝试或 warning 失败证据；保存测试输出。

最小实现建议：

1. 如果项目没有公共运行初始化点，新增一个很小的 starplan_skills/astro_runtime.py；不要建立配置框架。
2. 提供幂等函数 configure_astronomy_runtime()，把产品运行需要的 Astropy policy 放在这里。
3. 使用 Astropy 随包 IERS/leap-second 数据，关闭运行时自动下载和缓存新鲜度强制检查。
4. runner 的所有公开入口和 scripts/cross_validate.py 在第一次 Time/Observer/EarthLocation 前调用该函数。
5. observability_plan.py 不得依赖 conftest.py 才能安全运行。
6. 不使用全局 warnings.filterwarnings("ignore")。如果仍有已证明无害的 warning，只在具体调用周围局部处理并写注释。
7. 在 state_log 或早期控制台输出中记录 astronomy_runtime=offline_bundled_data。

Batch A 验收：

- 新增失败测试转为通过。
- python scripts/run_case.py examples/case_01_m31_jinan.json
- python scripts/run_case.py examples/case_02_unfavorable_window.json
- python scripts/run_case.py examples/case_03_observation_review.json
- tests/test_observability_edge_cases.py 全过。
- tests/test_moon_separation_c1.py 全过。
- 不出现远端 IERS 等待；Manifest 记录运行 policy。

--------------------------------
Batch B：公共 fail-closed + Review 安全降级
--------------------------------

当前失败事实：

- 结构化入口合同 BLOCKED 后可能仍在公共 dict 的 outreach_pack 字段返回已构建内容。
- Chat 的 public_output_validation 没有完全从最终 RunOutcome 派生。
- Chat 合同异常或缺证据时可能降成 passed_with_warnings。
- Review Qwen 仍可返回自由原因、证据或建议，尚未完成 ID-only。

目标行为：

- BLOCKED 时，结构化入口和 Chat 的公共返回都是 0 条事实。
- RunOutcome、Manifest、Validation Report、磁盘交付和公共返回状态一致。
- P1 ID-only 完成前，案例三只使用确定性 Review，不调用 Qwen 自由补充。

先写失败测试：

1. 在 test_delivery_contract_gate.py 和 runner/Chat 端到端测试中覆盖：删除 claims.json、损坏 expression_plan.json、空 sentence map、错 variant、改 hash、插入额外事实。
2. 对结构化入口和 Chat 分别断言：validation=blocked、delivery=not_delivered、公共返回不含 talking points/替代建议/模型原文。
3. Mock Qwen 在 Review 返回一条无数字但虚构的原因和建议，断言最终 Review 与 use_qwen=False 的确定性基线一致。
4. 模型调用 0、1、多次和一次被拒绝时，model_call_log、RunOutcome、Manifest 计数一致。

结构化入口最小修复：

1. 保留 validate_delivery_contract()，但让最终 RunOutcome 决定 public return。
2. run_starplan() 在 BLOCKED/NOT_DELIVERED 时，outreach_pack 返回 None 或固定无事实 envelope，不能返回此前的 outreach.model_dump()。
3. BLOCKED 仍写 run_outcome.json、calculation_manifest.json 和 validation_report.md，三者同为 blocked/not_delivered。
4. 不新增大型 Web/API 层，只稳定当前 dict 返回合同。

Chat 最小修复：

1. public_output_validation 直接来自 chat_outcome.validation_status。
2. 合同异常、缺 rendered_document 或证据文件损坏必须 BLOCKED，不得 passed_with_warnings。
3. BLOCKED 时 final_content 使用固定无事实说明，不拼接 pack_data。
4. 共享结构化入口的 finalize/Manifest/Report writer，不复制一套状态推断。
5. 模型调用按真实 model_call 事件聚合；不要用无法被 RunOutcome 统计的 model_call_summary 冒充调用。

Review 临时策略：

1. runner 显式调用 review_observation(..., use_qwen=False)，或提供清楚的 competition_safe 默认策略。
2. 输出和审计中记录 qwen_status=disabled_pending_id_only。
3. 保留现有 Qwen Review helper 供 P1 改成 ID-only，当前不要删除或重写整文件。

Batch B 验收：

- 所有新增 fail-closed 对抗测试通过。
- tests/test_mock_qwen_adversarial.py 通过。
- tests/test_chat_hallucination_c4.py 通过。
- Layer 3/端到端测试通过。
- 任一 BLOCKED 场景公共返回 0 条事实。
- 案例三不再为 Review 额外等待真实模型调用。

--------------------------------
Batch C：文案、示例和版本一致性
--------------------------------

目标行为：评委看到的 README、Skills 声明、控制台、Markdown 和 JSON 使用同一版本、同一时间口径和同一数值来源。

实施项：

1. 统一 skills.yaml、starplan_skills.__version__、README、Manifest 中的软件版本。版本号只能代表已通过验收的能力。
2. templates.py 中把未来日期通用“今晚”改为“本次活动”或具体日期；只有输入日期等于当地当前日期才可写“今晚”。
3. M42 的“夜间最高高度”全部使用 max_altitude_deg；某个采样点高度必须带采样时间，不能与最高高度混写。
4. 案例三结构化时间差是唯一延迟数值来源。删除或改写 observer_notes 中冲突的“迟到30分钟”，备注不重复结构化数字。
5. 偏差类型显示中文；Markdown 修订表只输出一次表头。
6. 更新 README 和 skills.yaml 时只声明当前真实实现，不能提前写 P1 尚未完成的分众/next input 为已完成。

Batch C 验收：

- 为上述四类可见矛盾增加回归断言。
- python scripts/validate_examples.py 为 3 passed, 0 failed。
- rg 检查不再发现旧版本号和冲突措辞。
- git diff --check 通过。

六、P0 完成后的统一回归

至少运行并记录：

1. python -m compileall -q starplan_skills scripts tests
2. python scripts/validate_examples.py
3. python tests/layer23_validation.py
4. python -m pytest -q tests/test_runtime_offline_policy.py
5. python -m pytest -q tests/test_observability_edge_cases.py
6. python -m pytest -q tests/test_moon_separation_c1.py
7. python -m pytest -q tests/test_mock_qwen_adversarial.py
8. python -m pytest -q tests/test_chat_hallucination_c4.py
9. 受影响的 delivery contract、Layer 3、runner、Review 测试
10. README 三案例，记录每个耗时和终态

然后尝试完整 pytest。当前托管 Windows 环境曾因 pytest tmp_path 临时目录 ACL 出现 PermissionError；如果再次发生：

- 不得把它写成业务测试失败；
- 也不得宣称 155 全过；
- 报告已收集数量、通过到哪里、ACL 错误原文；
- 在普通终端或第二台电脑重跑完整 suite，作为合并门禁。

真实 Qwen canary 与离线 merge gate 分开。P0 先保证无 Key、无网络也能安全运行；真实 Qwen 只需低频验证 API 兼容性，不用为了 canary 波动放松测试。

七、P0 强制交付和停止条件

完成 Batch A-C 后必须：

1. 在 starplan-project-guidance/ 新增 UTF-8 Markdown error-check/phase-plan 报告。
2. 报告逐条列出 CRITICAL/WARNING/INFO、修改文件、失败测试转绿证据、README 三案例耗时、完整 pytest 状态和遗留风险。
3. 更新 README、skills.yaml 和项目文档中受本批影响的真实能力声明。
4. 检查 git status、完整 diff、git diff --check 和 origin/main...HEAD。
5. commit 并 push 当前分支；报告必须和代码一起提交。
6. 停止，不要自动进入 P1。等待项目负责人审查 P0 结果。

最终回复使用以下结构：

Assumption：本批采用了哪些明确假设。
Changed：按 Batch 列文件和行为变化。
Verified：列实际命令、通过数、失败数、耗时和终态。
Remaining risk：没有通过或没有运行的内容。
Commit：分支、commit SHA、远端同步关系。
Next approval：进入 P1 前需要负责人确认什么。

八、负责人确认后才执行的 P1

只有用户明确回复“继续 P1”后，才执行以下两个独立 Batch。

Batch D：现实活动时段 + 三类分众输出

1. 保留 recommended_window 的科学窗口语义。
2. 新增 ActivityPreferences 和 RecommendedActivitySlot：默认 90 分钟，限制 60-120 分钟，含 setup/cleanup、可选 preferred start/latest end、规则版本和人工确认状态。
3. 活动 slot 只能由确定性 activity_slot_policy_v1 从科学窗口中选择；Qwen 只能选批准候选，不能自由填时间。
4. 保留 audience 字符串兼容性，新增 AudienceProfile：age_band、experience_level、requested_views。
5. 同一 Claims 生成 organizer、facilitator、learner 三种 view；改变表达，不改变事实。
6. 未成年人安全项来自 youth_activity_policy_v1，并保持“待人工确认”；不采集姓名、联系方式和健康隐私。

Batch D 验收：

- M31 同时显示完整科学窗口和现实 90 分钟活动时段，不再通宵。
- M42 不生成虚假 activity slot。
- 三个 view 的科学句和数字均映射到同一 Claim IDs，无事实冲突。

Batch E：可执行下一轮输入 + before/after

1. review_observation 接收原始 StarPlanInput 的规范化副本，不从 ObservabilityResult 反推用户需求。
2. 可修订字段使用白名单 ActivityPreferences；自由建议不能直接成为 Schema 字段。
3. 复制原输入、应用证据支持的 patch、移除 observation_log，写 next_activity_input.json。
4. ObservationReview 增加 next input path、parent_run_id 和 source_cause_ids。
5. 不在 run_starplan 内默认递归；通过明确 CLI 或测试读取 next input 后再次调用 runner。
6. 生成 before/after，对每项变化引用 Evidence/Cause ID。

Batch E 验收：

- next_activity_input.json 通过 StarPlanInput Schema。
- 第二次 runner 正常运行且不再次触发 Review。
- 至少一个活动步骤或时间字段可见变化。
- 删除证据后对应 patch 消失或降为待确认。

P1 每个 Batch 仍需独立测试、报告、commit 和 push。

九、P2 在人类选择平台前不得开始

项目负责人必须先指定最终用于“直接加载到智能体”的 Qwen/百炼产品形态。你不能自行假设是 MCP、OpenAPI、百炼应用、QoderWork 私有格式或其他平台。

平台确认后：

1. 只写薄适配层：参数转换 -> 调用现有 Skills/runner -> 返回稳定 envelope。
2. 不复制天文计算、Claim、渲染或 Review 逻辑。
3. 为四个 Skills 写触发条件、输入、输出、依赖、超时、失败状态和人工确认点。
4. 在干净环境完成安装、加载、自然语言触发和结果返回。
5. 现场/视频只实时调用一次 Qwen，其余可用确定性运行或明确标记的已验证历史运行。
6. 模型超时建议 30-35 秒；容量、空响应、非法 JSON 后安全回退。
7. 保存平台配置证据、模型调用日志和完整运行目录。

十、任何阶段都禁止的做法

- 不要为了让测试变绿而删除、跳过或放松测试。
- 不要加关键词黑名单替代 Claim/ID-only 架构。
- 不要把 BLOCKED 改成 WARNING 来继续交付。
- 不要用整文件回退覆盖科学修复或可信输出架构。
- 不要把模拟观测写成真实观测。
- 不要在报告里写没有实际运行过的命令或通过数字。
- 不要声称“全部完成”，除非 project plan 的对应验收项逐条有证据。
- 不要开始复杂前端。视频和 Qwen 智能体调用优先。

现在开始：只做基线确认和 P0 Batch A。先展示当前失败测试，再实施最小修复。
```
