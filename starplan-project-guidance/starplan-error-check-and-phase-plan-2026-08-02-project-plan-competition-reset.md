# StarPlan 错误检查与阶段计划 - 项目计划竞赛重置（2026-08-02）

日期：2026-08-02

项目起始：2026-07-18

提交截止：2026-09-01 00:00:00（北京时间）

审查基线：本地 `main` 与 GitHub API 返回的远端 `main` 均为 `044e22fe09a00821975a71543d3a58e24252f827`

## 一、本轮错误检查

### 1. 审查范围与结论

本轮根据赛道正式描述、当前代码、最近 Phase A-D 报告、竞赛复查、团队资源和正式提交要求，重新判断项目完成度并更新 source of truth。没有修改业务代码、测试或案例数据。

结论：项目不是“Phase A-D 全部完成”，而是“确定性科学计算、四个 Skills 和可信输出基础已形成；正常运行合同、公共 fail-closed、可执行复盘、分众表达、智能体加载和提交证据仍未完成”。接下来明确需要继续修改代码。

### 2. CRITICAL

| 编号 | 问题 | 当前证据 | 本轮处理 | 后续修改位置 |
|---|---|---|---|---|
| C-01 | 正常入口仍受 IERS/leap-second 联网或缓存状态影响 | 空 API Key 条件下，README 的 M42 案例 45 秒超时，复盘案例 90 秒超时；均未返回最终结果。`conftest.py` 的 IERS 设置只覆盖 pytest | 未改代码；纳入新计划 P0 | 在正常计算入口统一设置 Astropy 离线 policy，并增加空缓存、禁网、限时子进程测试；主要涉及 `observability_plan.py`、runner 初始化和 `cross_validate.py` |
| C-02 | 可信输出 Phase A-C 尚未完成独立验收 | `044e22f` 之后没有业务代码提交；上轮独立复查中的 BLOCKED 公共返回、Claim 语义重放和 Review 自由文本问题没有新的关闭证据 | 明确撤销“Phase A-D 全部完成”的当前效力 | `runner.py`、`run_outcome.py`、`expression_validator.py`、`claims.py`、`rendering.py`、`observation_review.py` 及端到端失败测试 |
| C-03 | 复盘尚未形成可再次运行的下一轮计划 | 当前 `revised_plan.json` 是建议/修改清单，不能直接作为 runner 输入，也没有重新生成 after 活动包 | 提升为竞赛核心闭环阻断项 | 定义 `next_activity_input.json` 或等价 Schema；在 `observation_review.py` 和 runner 中应用 patch 并重跑 |
| C-04 | Skills 包尚无“直接加载到智能体”的已验收路径 | 当前证据主要是 CLI、Python 调用和 Qwen API；未发现从干净环境加载到指定 Qwen 智能体的完整记录 | 纳入新计划 P2，不再以自建网页替代 | 冻结 Skills 包目录、触发条件、依赖、安装和调用适配层；在目标 Qwen/百炼产品中真实加载验证 |
| C-05 | 科学可见窗口被直接当作现实活动时段 | 最近真实 M31 输出将约九小时可见窗口写成通宵活动流程，不适合青少年或新手组织场景 | 纳入新计划 P1 | `schemas.py`、`observability_plan.py`、`claims.py`、`rendering.py`、`outreach_pack.py`：分离 scientific window、activity slot、setup 和 cleanup |

### 3. WARNING

| 编号 | 问题 | 当前证据 | 处理 |
|---|---|---|---|
| W-01 | 完整 pytest 的“155 全过”在本轮环境不可复现 | 正式 `tests/` 收集到 155 项；涉及 `tmp_path` 的测试在当前托管 Windows 环境触发 pytest 临时目录 ACL `PermissionError`，全量运行 180 秒超时 | 不能把环境错误误报为业务失败，也不能继续引用旧全过数字；提交前须在第二台电脑或普通终端完成完整回归 |
| W-02 | Skills 与包版本声明漂移 | `skills.yaml` 为 `0.2.0`，`starplan_skills.__version__` 为 `0.4.0` | 纳入 P0，统一 package、Skills、README、Schema 和能力声明 |
| W-03 | 演示文案和示例存在成品化矛盾 | 已知包括未来日期写“今晚”、M42 不同高度口径、案例三“晚 16 分钟”与备注“迟到 30 分钟”冲突 | 纳入 P0，按结构化字段生成唯一口径并补回归断言 |
| W-04 | 当前受众表达仍不足以证明赛道要求 | 现有 `audience` 可传字符串，但没有组织者、讲解员、学生三类同源 Claims 输出的验收记录 | 纳入 P1；增加角色、年龄/经验和适龄模板，保持事实映射一致 |
| W-05 | 团队缺少天文专业成员，模型互审不能构成外部科学证明 | 当前主要由 GPT/Qwen 交叉审查，八月中旬实地尝试仍在计划阶段 | 纳入 P3；争取物理教师、天文社成员或有经验爱好者留痕复核三个案例 |
| W-06 | Git fetch 传输三次失败 | HTTPS fetch/ls-remote 出现 connection reset；随后 `gh api` 成功确认远端 `main` 与本地同为 `044e22f` | 已确认本轮编辑基线未落后；推送前仍需重新 fetch，并检查 `origin/main...HEAD` |

### 4. INFO 与确认通过项

| 验证项 | 结果 |
|---|---|
| Python 编译检查：`starplan_skills`、`scripts`、`tests` | PASS |
| `tests/layer23_validation.py`：150 个目标、10 轮 Layer 2/3 | 0 unique issues |
| `scripts/validate_examples.py` | 3 passed, 0 failed |
| `tests/test_observability_edge_cases.py` | 5 passed；出现 leap-second 自动更新权限 warning，进一步支持 C-01 |
| `tests/test_moon_separation_c1.py` | 6 passed；出现同类 leap-second warning |
| `tests/test_mock_qwen_adversarial.py` | 14 passed |
| `tests/test_chat_hallucination_c4.py` | 19 passed |
| `git diff --check` | PASS；只有 Git 的 LF/CRLF 提示 |

本轮可以确认代码可编译，目录数据、示例 Schema、月距、已覆盖科学边界和局部幻觉防护测试可运行。不能确认 README 三案例在正常入口无错误运行，也不能确认 155 项完整 pytest 全过，因此项目不能标记为完成。

## 二、完成状态

| 项目计划阶段 | 当前状态 | 判断 |
|---|---|---|
| 第 1 周：范围、Schema、案例 | 基本完成 | 四个 Skills、三个案例和输出基础存在；仍需补分众和下一轮输入 Schema |
| 第 2 周：确定性计算 | 主要功能完成，运行合同未验收 | 科学计算局部验证通过，正常入口的 IERS 阻断仍是 P0 |
| 第 3 周：Qwen 与可信输出 | 基础完成，验收未通过 | Claim Registry、渲染和对抗测试已有；公共终态、语义重放和调用聚合仍需修复 |
| 第 4 周：复盘闭环 | 部分完成 | 能输出偏差和 plan diff，但下一轮不可直接重跑；Review 自由补充仍需关闭或 ID-only |
| 第 5 周：演示和三案例 | 未完成 | 有 CLI 和产物，没有经验证的 Qwen 智能体加载、分众演示和三类完整记录 |
| 第 6 周：提交材料 | 未完成 | 尚需技术报告、许可证、20 页内 PPT/PDF、视频和独立复现包 |

历史 `phase-a-d-completion` 报告不再作为完成证明；`phase-a-d-independent-recheck` 的缺陷仍有效，但按照竞赛可见影响重排；`competition-priority-live-demo-recheck` 的判断继续有效，其中独立网页调整为可选，Qwen 智能体加载和视频成为主展示路径。

## 三、阶段计划

### P0：关闭可见阻断（8 月 2 日至 8 月 8 日）

1. 把 IERS/leap-second 离线 policy 移入正常运行入口。
2. 修复 BLOCKED 公共返回；在 Review ID-only 完成前禁止 Qwen 自由补充进入用户输出。
3. 统一“今晚”、M42 高度口径、案例三延迟量和 Markdown 表格。
4. 统一 `skills.yaml`、package、README、Schema 和能力声明版本。

验收：README 三案例在无 API Key、空用户缓存和禁网条件下连续运行；模型失败仍安全交付；结构化 BLOCKED 返回不含被阻断事实；文案无口径矛盾。

### P1：完成竞赛核心闭环（8 月 5 日至 8 月 13 日）

1. 分离 `scientific_visibility_window`、`recommended_activity_slot`、`setup_time` 和 `cleanup_time`。
2. 从同一 Claims 生成组织者、教师或讲解员、学生三类输出。
3. 增加未成年人活动的场地、监护、交通、设备和取消条件人工确认模板。
4. 输出可执行 `next_activity_input`，应用复盘 patch 并实际重跑生成 before/after 活动包。

验收：M31 不再默认通宵活动；三类输出事实一致；M42 安全失败；案例三下一轮可以再次进入 runner 且变化能追溯到日志证据。

### P2：完成 Qwen 智能体交付（8 月 10 日至 8 月 17 日）

1. 确认比赛采用的 Qwen/百炼智能体产品形态和 Skills 包规范。
2. 冻结四个 Skills 的触发条件、输入、输出、依赖和失败处理。
3. 在干净环境完成安装、加载、自然语言触发和结果返回。
4. 增加模型超时、容量错误和确定性回退的可见状态。

验收：至少一种 Qwen 智能体能够加载并调用 Skills；完整记录触发链；模型不可用不阻塞确定性核心。

### P3：固定三案例与真实证据（8 月 14 日至 8 月 22 日）

1. 保存 M31 正常、M42 不可观测、日志复盘三类完整运行记录。
2. 开展一次小规模实地观测；天气或场地失败也如实记录。无法实地完成时明确标注桌面演练和模拟数据。
3. 争取外部人员对三个案例进行可留痕科学复核。
4. 完成 Astropy/astroplan 等来源、许可证、改造点和智能体调用说明。

验收：三类记录都包含输入、中间结果、模型采用/拒绝、输出、验证和人工入口；真实与模拟边界清楚。

### P4：材料制作与提交冻结（8 月 18 日至 8 月 31 日）

1. 完成应用技术报告、20 页内 PPT/PDF 和 6 至 8 分钟演示视频。
2. 由第三名成员或第二台电脑从零安装并重跑。
3. 8 月 28 日后停止新增功能，只修提交阻断。
4. 检查页数、文件、依赖、许可证、隐私和 API Key。

验收：评委不依赖答辩即可看懂科学准确性、技术深度、闭环价值和复现方式；最终包可打开、可加载、可运行。

## 四、具体实施方案

### 1. 通用实施纪律

每一批修改都按“失败证据 -> 最小实现 -> 定向测试 -> 完整回归 -> 文档与版本同步”的顺序执行。

1. 开始前必须获取远端最新 `main`，确认本地包含远端提交；无法确认就停止，不在旧代码上继续改。
2. 每批只解决一个可观察行为，不把 P0、P1、P2 混成一次大重构。
3. 先提交能复现缺陷的测试。失败测试必须检查用户最终能看到什么，不能只检查内部函数返回。
4. 不新增核心 Skill，不改成多智能体，不引入复杂前端、数据库或新的在线天文依赖。
5. 受保护的 Claim、渲染、runner 和 Review 文件发生冲突时逐行处理，禁止整文件覆盖。
6. `DASHSCOPE_API_KEY` 只从环境读取；测试、日志、报告和 Git diff 中不得出现密钥值。
7. 一批完成后单独生成新的 error-check/phase-plan 报告，记录基线提交、修改文件、测试命令、真实结果和遗留问题；不要回写本报告伪造历史完成状态。

### 2. P0-1：正常入口 IERS/leap-second 离线运行

**目标行为**：README 三案例不依赖用户已有 Astropy 缓存，不主动等待外网更新；离线数据不足时返回清楚的工具状态，而不是长时间无输出。

**建议修改范围**：

- 新增一个很小的运行策略模块，例如 `starplan_skills/astro_runtime.py`；如果现有模块已经有等价公共初始化点，应直接复用，不再造第二套配置。
- `starplan_skills/runner.py`：所有公开入口在第一次创建 `Time`、`Observer` 或 `EarthLocation` 前调用一次幂等初始化。
- `starplan_skills/observability_plan.py`：不得依赖 `conftest.py` 才能正确配置 Astropy。
- `scripts/cross_validate.py`：使用同一运行策略。
- 新增 `tests/test_runtime_offline_policy.py` 或等价端到端测试。

**实施步骤**：

1. 先写子进程测试：创建全新临时缓存目录，清空 API Key，禁止网络或设置不可达代理，运行 M31/M42；当前代码应先复现超时或联网 warning。
2. 把 `conftest.py` 中已经验证过的 `iers.conf.auto_download = False`、`iers.conf.auto_max_age = None` 移入产品运行初始化；同时显式使用 Astropy 随包数据。若 leap-second 仍尝试更新，只允许加载随包 leap-second 文件或 ERFA 内置表，不能把异常吞掉后继续等待网络。
3. 初始化函数必须幂等，不能每个采样点重复设置；建议只在 runner 公共入口和独立交叉校验脚本入口调用。
4. 不使用全局 `warnings.filterwarnings("ignore")` 隐藏所有 Astropy warning。确有无害 warning 时只在已证明安全的局部转换周围屏蔽并写明原因。
5. 在控制台或状态日志中增加早期阶段信息，例如 `astronomy_runtime=offline_bundled_data`，避免用户把正常计算等待理解为卡死。

**验收测试**：

- 空缓存、空 API Key：M31 和 M42 在团队设定的限时内进入终态；P0 先以 30 秒为上限，后续再优化性能。
- 强制网络不可用时不出现远端 IERS 下载等待。
- `test_observability_edge_cases.py` 和 `test_moon_separation_c1.py` 保持通过。
- Manifest 记录 Astropy、astroplan、Python 版本以及使用的离线数据 policy。

### 3. P0-2：公共 fail-closed 和统一终态

**目标行为**：只要最终合同为 BLOCKED，结构化入口和 Chat 的公共返回都不能包含活动包、事实句或被阻断模型文本；磁盘文件、RunOutcome、Manifest、Validation Report 和公共返回保持同一状态。

**建议修改范围**：`runner.py`、`run_outcome.py`、`expression_validator.py`、Manifest/Validation Report writer、`test_delivery_contract_gate.py` 和 Chat 端到端测试。

**结构化入口实施步骤**：

1. 保留现有 `validate_delivery_contract()`，但让它决定公共交付，不只决定是否删除 `outreach_pack.md`。
2. `run_starplan()` 返回值必须由最终 `RunOutcome` 派生。若 `validation_status == blocked` 或 `delivery_status == not_delivered`，`outreach_pack` 应为 `None` 或固定的无事实状态对象，不能继续返回此前构建的 `outreach.model_dump()`。
3. BLOCKED 分支仍要落盘 `run_outcome.json`、`calculation_manifest.json` 和 `validation_report.md`，但不得重新推断为 passed。
4. 将公共结果定义为一个稳定 envelope，例如 `status`、`run_id`、`safe_message`、`artifacts`；不要在本批引入大型 API 框架。

**Chat 实施步骤**：

1. `run_starplan_chat()` 的 `public_output_validation` 必须直接来自 `chat_outcome.validation_status`，不能继续只看 `untraceable` 数字列表。
2. 合同校验抛异常、缺少 `rendered_document.json` 或证据文件损坏时必须 BLOCKED，不能降成 `passed_with_warnings`。
3. BLOCKED 时把 `final_content` 替换为固定无事实说明，例如“本次输出未通过证据校验，请查看验证报告或重试”；不得拼接 `pack_data` 中的 talking points 或替代建议。
4. 将真实模型调用日志按每条 `model_call` 聚合。不要写一个 `model_call_summary` 事件后又让 `RunOutcome` 只统计 `type == model_call`。
5. Chat 是否补 Manifest/Validation Report 可在共享 finalize 中一次完成；不要复制结构化入口的 writer 逻辑形成第三套状态来源。

**必须先写的对抗用例**：

- 删除 `claims.json`、损坏 `expression_plan.json`、清空 sentence map、篡改 variant、插入额外事实。
- 结构化入口和 Chat 各断言：Outcome 为 BLOCKED；公共返回 0 条事实；被阻断原文不出现；Manifest/Report 同为 blocked。
- 模型调用 0 次、1 次、多次、一次被拒绝时，日志、Outcome 和 Manifest 计数一致。

### 4. P0-3：Review 在 ID-only 前的安全降级

**目标行为**：P1 的 Review ID-only 尚未完成时，比赛案例三只使用确定性规则和 Evidence Claims，不为一次可能被拒绝的 Qwen Review 增加等待，也不接受自由原因、证据或建议。

**建议修改范围**：`runner.py`、`observation_review.py`、`schemas.py` 和 Review 对抗测试。

**实施步骤**：

1. 在 `run_starplan()` 调用 `review_observation()` 时显式传 `use_qwen=False`，或将默认策略改为竞赛安全模式；保留 Qwen helper 供后续 ID-only 使用，不删除历史代码。
2. 在结果和审计日志中明确记录 `qwen_status=disabled_pending_id_only`，避免被误认为模型调用失败。
3. 规则原因必须有稳定 `cause_id`、证据来源和证据强度；修订项继续引用 `source_cause_ids`。
4. Mock Qwen 返回“没有数字但完全虚构”的原因和建议时，最终 Review 输出必须与确定性基线完全一致。
5. 完成 ID-only 后再开放 Qwen：模型只选择预定义原因 ID、建议 ID 和允许的分类，不返回用户可见文本；未知 ID、伪证据和越权 certainty 直接丢弃。

### 5. P0-4：低成本高可见度一致性修复

**目标行为**：README、Skills 声明、控制台、Markdown 和 JSON 不再给评委互相冲突的信息。

**实施步骤与位置**：

1. 版本：把 `skills.yaml`、`starplan_skills.__version__`、README 和 Manifest 使用的包版本统一到一个值；版本号由实际已验收能力决定，不为显得先进而跳号。
2. 时间措辞：`templates.py` 中把未来日期通用句式从“今晚”改为“本次活动”或带明确日期；如果确为当前本地日期才允许“今晚”。
3. M42 高度：控制台和活动包统一使用 `max_altitude_deg` 作为“夜间最高高度”；采样点高度必须标注时间，不能与最高高度并列成同一口径。
4. 案例三延迟：结构化时间差是唯一数值来源。删除或修改 `observer_notes` 中冲突的“迟到 30 分钟”，备注只保留非重复事实。
5. Markdown：偏差类型使用中文映射；修订表只输出一次表头；加回归快照或文本断言。

### 6. P1-1：科学窗口与现实活动时段分离

**目标行为**：天文学上整夜可见不等于组织者应安排整夜活动。程序先计算科学窗口，再用确定性活动 policy 选择 60 至 120 分钟现实活动时段。

**建议 Schema**：

- `ActivityPreferences`：`duration_minutes`（默认 90，限制 60-120）、`setup_minutes`、`cleanup_minutes`、可选 `preferred_start_local`、可选 `latest_end_local`、`equipment_precheck`、`expectation_briefing`、`fallback_mode`。
- `RecommendedActivitySlot`：开始/结束、时区、时长、对应 science window、选择规则版本、是否需要人工确认。
- `ObservabilityResult` 保留现有 `recommended_window` 作为科学窗口，新增 `recommended_activity_slot`，不能偷换旧字段语义。

**确定性选择规则**：

1. 只在科学可见窗口内选择活动时段。
2. 用户给出偏好开始时间时，先验证其是否落入科学窗口；不满足时返回可解释调整或要求确认。
3. 未提供偏好时，使用版本化 `activity_slot_policy_v1`：默认 90 分钟；青少年/新手优先当地晚间的合理结束时间；若没有满足条件的时段，不生成活动流程并要求人工确认或改期。
4. setup/cleanup 可超出正式观测段，但必须明确标注，不能被算成目标可观测时间。
5. Qwen 只能从代码生成的候选 slot 中选择，不能自由填写时间。

**主要修改位置**：`schemas.py`、`observability_plan.py`、`claims.py`、`templates.py`、`rendering.py`、`outreach_pack.py`、`skills.yaml`、示例和测试。

**验收**：M31 同时显示完整科学窗口和 90 分钟活动时段；活动 schedule 只覆盖 setup、activity、cleanup；M42 不生成虚假的 activity slot。

### 7. P1-2：同源 Claims 的分众输出与未成年人安全边界

**目标行为**：同一科学结果可以生成组织者、教师或讲解员、学生三种内容，但三者的事实 Claim 集合和数值保持一致。

**最小 Schema 建议**：

- 保留现有 `audience: str` 以兼容旧案例。
- 新增可选 `AudienceProfile`：`age_band` 只支持 `primary`、`middle`、`high`、`adult`；`experience_level` 支持 `beginner`、`intermediate`；`requested_views` 支持 `organizer`、`facilitator`、`learner`。
- 旧字符串输入通过一个确定性适配器映射到默认 profile；映射失败时使用 `adult/beginner` 并要求人工确认，不让 Qwen 猜年龄。

**渲染实施**：

1. `claims.py` 只构建一次科学 Claims；不同 view 选择不同批准句式、解释长度和互动模板。
2. 组织者版输出活动时段、设备、人员、安全确认和回退条件；讲解员版输出讲解顺序、适龄比喻和核对项；学生版输出观察任务和问题，不增加新天文事实。
3. 未成年人安全提示作为版本化 procedural claims 或 policy items，来源标记为 `youth_activity_policy_v1`；场地许可、监护人、交通和现场安全只能是待人工确认状态。
4. 不采集未成年人姓名、联系方式或健康隐私；案例使用匿名人数和汇总反馈。

**验收**：三个 view 的全部科学事实都能映射到相同 Claim IDs；对三个输出提取数字和事实映射后无冲突；删除任一 Claim 时三个 view 中对应句子同时消失或安全降级。

### 8. P1-3：可执行下一轮输入与 before/after

**目标行为**：Review 不再只写建议，而是输出一个符合 `StarPlanInput` 的下一轮输入；该文件可以由 runner 再次读取并生成新活动包。

**最小实现路径**：

1. `review_observation()` 增加原始 `StarPlanInput` 或其规范化副本作为输入；不要只拿 `ObservabilityResult` 反推用户需求。
2. 把可修订字段收敛到白名单：`activity_preferences.duration_minutes`、setup/cleanup、设备预检、预期说明、fallback mode，以及需要人工确认的目标/日期替换建议。
3. 复制原输入后应用白名单 patch，移除 `observation_log`，写出 `next_activity_input.json`。禁止把自由建议字符串直接塞进未知字段，因为 `StarPlanInput(extra="forbid")` 会拒绝。
4. `ObservationReview` 增加 `next_activity_input_path`、`parent_run_id` 和每个 patch 的 `source_cause_ids`；`revised_plan.json` 可保留为人类可读差异，但不能继续冒充可执行输入。
5. 不在 `run_starplan()` 内默认递归重跑，避免隐藏成本和循环。新增明确的 CLI 步骤或测试：读取 `next_activity_input.json`，调用第二次 `run_starplan()`，生成带 `parent_run_id` 的 next run。
6. 输出 before/after 比较只比较批准字段和渲染后的活动流程，每个变化链接回日志 evidence/cause ID。

**验收**：案例三第一次运行生成 `next_activity_input.json`；Schema 校验通过；第二次运行不触发 Review；至少一个活动步骤或时间字段发生变化；删除支撑证据后相应 patch 自动消失或降级为待确认。

### 9. P2：Qwen 智能体加载与提交形态

P0/P1 不因智能体产品形态未确定而停工，但 P2 开始前项目负责人必须指定比赛最终采用的 Qwen/百炼载体。Qwen 不得自行假设是 MCP、OpenAPI、百炼应用或某个未确认平台。

**确认后实施**：

1. 按目标平台官方格式包装现有四个 Skills；包装层只做参数转换、调用 runner 和返回稳定 envelope，不复制天文计算或 Claim 逻辑。
2. 每个 Skill 文档必须写明触发条件、输入 Schema、输出 Schema、依赖、超时、失败状态和人工确认点。
3. 提供一个从干净环境安装/加载的最短路径，固定依赖版本并说明 Python 版本。
4. 至少真实演示一次 Qwen 自然语言解析/Skill 选择；其余案例可使用确定性 runner 或明确标注的已验证运行，避免视频中多次等待模型。
5. 模型调用超时建议 30-35 秒；超时或容量错误进入确定性回退，不返回半截模型文本。
6. 保存平台配置截图或导出文件、模型调用日志和完整运行目录，作为“实际使用 Qwen”的证据。

**验收**：一台未参与开发的电脑或全新环境可以按照 README 加载 Skills；三类请求能触发正确 Skill；模型不可用时核心计算继续；评委能从材料中看出 Qwen 做了什么、没有做什么。

### 10. 推荐合并批次

| 批次 | 内容 | 允许修改范围 | 合并门禁 |
|---|---|---|---|
| Batch A | IERS 正常入口 + 限时离线测试 | runtime policy、observability、runner 初始化、cross validate、测试 | README M31/M42 空缓存限时完成；科学回归通过 |
| Batch B | 公共 fail-closed + Review 安全降级 | runner、RunOutcome、validator、review、端到端测试 | BLOCKED 0 事实泄漏；Review Mock 幻觉不改变用户输出 |
| Batch C | 文案、示例、版本一致性 | templates、rendering、examples、README、skills.yaml、版本 | 指定矛盾全部有回归断言；`git diff --check` 通过 |
| Batch D | activity slot + 分众输出 | schemas、observability、claims、templates、rendering、outreach、测试 | M31 现实活动时段；三 view 同源 Claim；M42 不生成 slot |
| Batch E | next activity input + before/after | schemas、review、runner/CLI、案例、测试 | next input 可重跑；变化有 evidence lineage |
| Batch F | 智能体包装与复现 | 适配层、Skills 描述、README、演示记录 | 干净环境加载并完成三类触发 |

禁止把 Batch A-F 合成一个提交。每批开始前重新同步 `main`，结束时提交代码、测试和该批强制报告。

## 五、阻塞项与风险

1. P0 未关闭前，任何“可一键复现”“Phase A-D 完成”声明都不成立。
2. 三人资源不足以同时做复杂前端、更多天体和可信输出硬化；前端、土星、流星雨和取证级防篡改继续后置。
3. 八月中旬实地活动受天气、场地和人员影响，但失败记录本身可以成为产品失败路径证据，不得伪造成功观测。
4. 初赛无答辩，PPT/PDF 和视频本身必须承担解释责任；不能把关键价值藏在源码或大量 JSON 中。
5. Qwen/GPT 多模型互审只能提高代码审查覆盖，不能替代外部科学复核和干净环境实跑。

## 六、立即下一步

1. 代码负责人先为正常入口 IERS 超时建立可重复失败用例并修复，这是当前最小且最可见的 P0。
2. 同批关闭结构化 BLOCKED 公共返回和 Review 自由补充，重跑相关端到端对抗测试。
3. 项目负责人确认最终 Qwen/百炼智能体加载形态和首个中小学生年龄段，以冻结 P1/P2 Schema。
4. 安排 8 月中旬实地尝试的地点、设备、安全责任和天气取消条件，并联系外部复核人员。

## 七、本轮文件变更

- 更新 `starplan-loop-project-plan.md`：正式定位、当前进度、历史 Phase Plan 效力、三人资源、提交倒排和成功标准。
- 更新 `starplan-qoderwork-transfer-log.md`：同步定位、三人分工、Qwen 智能体演示和下一步代码顺序。
- 更新 `starplan-transfer-log-diff.md`：记录 2026-08-02 赛道复盘后的决策变化。
- 更新 `qwen-project-kickoff-prompt.md`：从早期启动规划 Prompt 改为本轮 P0-P2 可执行操作 Prompt。
- 新增本报告。
- 未修改业务代码、测试、案例数据或 `.env`。
