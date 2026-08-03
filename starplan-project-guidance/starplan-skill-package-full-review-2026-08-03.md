# StarPlan Skill 包全面审查报告

日期：2026-08-03
审查对象：`StarPlan/`（四核心 Skills 包）及其规划文档（`starplan-project-guidance/`）
审查基线：`d9b1f22`（`main` 与 `origin/main` 一致，工作树干净）
官方赛题依据：
- 阿里云官网：<https://university.aliyun.com/action/tzbjbgs2026>（题目编号 XH-202619，赛道三方向三）
- 国家天文科学数据中心赛题解析：<https://nadc.china-vo.org/article/20260624094452>

> 本报告为独立审查结论。所有"已实测"内容均在本机以 `STARPLAN_MODEL_MODE=offline`、无 `DASHSCOPE_API_KEY`、使用既有虚拟环境（astropy 8.0.1 / astroplan 0.10.1 / pydantic 2.13.4）复跑验证；未验证内容已明确标注。

---

## 一、执行摘要

### 1.1 总体结论

StarPlan Loop 是目前为止**架构完成度很高、科学底线守得很好的技能包**：确定性天文计算经独立工具交叉验证、Claim 证据链与 fail-closed 门禁在同类参赛作品中属于明显加分项、离线可复现与对抗测试体系扎实。**但按 2026-09-05 官方提交截止日倒排，当前状态（8 月 3 日）尚未达到获奖水平**，主要差距不在代码质量，而在三处：

1. **闭环没有真正闭合**：复盘输出的 `revised_plan.json` 不能重新进入 `runner`，项目主打卖点"下一轮可执行计划 + before/after"尚未实现；
2. **真实 Qwen 调用证据为零**：9 个百炼集成测试全部跳过，无调用凭证/截图，官方"技术基础"硬性要求未满足；
3. **交付物为零**：20 页内技术方案 PDF、6–8 分钟演示视频、三组完整运行记录、第二环境复现均未产出。

### 1.2 获奖潜力判断

按官方评分标准（科学价值 40% / 技术深度 30% / 应用潜力 30%）模拟打分，**若今天提交**，预估 55–65 分，处于"工程扎实但缺闭环证据、缺真实模型调用、缺交付材料"的区间，大概率在获奖线（约前 31 名，含擂主 1、特等 5、一等 5、二等 10、三等 10）之外或边缘。

若按本报告第六节路线图完成 P1（现实活动时段 + 分众输出 + 可执行下一轮）、P2（真实 Qwen 加载与证据）、P3（三案例固化 + 独立复现 + 人工复核）、P4（20 页 PDF + 视频），预估可达 **80–88 分**，具备冲击二等奖以上、乃至特等奖的竞争力。理由：

- "Qwen 不产生科学数值 + 程序渲染事实句 + 全链路证据"这一设计本身稀缺且可被评审快速验证；
- 但这类作品在初赛材料评审中**只看证据**，一切未落盘的架构优势都不能计分。

---

## 二、审查方法与实际执行证据

| 检查项 | 结果 |
|---|---|
| `git fetch origin` + 基线核对 | HEAD = origin/main = `d9b1f22`，工作树干净 |
| `python -m compileall -q starplan_skills scripts tests` | PASS |
| 全量 `pytest -q`（离线，无 API Key） | **185 passed, 9 skipped, 0 failed**（87.0s；9 个跳过均为真实百炼在线测试） |
| `python scripts/validate_examples.py` | 3 passed, 0 failed |
| README 三案例（offline） | M31 可观测 / M42 不可观测 / 复盘均正常终态，分别生成 16 / 16 / 20 个产物文件 |
| `git diff --check` | PASS |
| 科学交叉校验（项目自身证据） | `scientific_cross_validation_2026-07-30.md`：12/12 项在容差内（暮光 ≤0.083 min，高度/方位 ≤0.005°，月相 ≤0.007） |
| 审查中独立抽查 | M31@济南四门塔 2026-10-17 峰值 85.04°、airmass 1.004、窗口 19:13–04:28，与 CSV 及物理预期一致 |
| 官方赛题原文 | 已从阿里云官网与 NADC 页面抓取并逐条对照（见第四节） |

> 说明：本次抽查未执行真实百炼调用（环境无 API Key）；9 个在线测试跳过，属于当前最大未验证项。

---

## 三、现状盘点：项目自评的成功标准逐条对照

以下对照项目计划第 13 节"项目成功标准"：

| 成功标准 | 当前状态 | 证据/缺口 |
|---|---|---|
| 可直接调用的 Skills 包 | ✅ 基本达成 | `starplan.run` / `run_starplan()`，4 Skills + 统一 Schema |
| 至少一种 Qwen 智能体环境完成加载→触发→返回 | ❌ 未达成 | 仅写了 DashScope function-calling 封装与 Chat 模式，无真实加载验证 |
| 至少一个核心案例完整闭环（计划→日志→修订计划） | ❌ 未达成 | 复盘输出 `revised_plan.json` 不是 `StarPlanInput`，无法重跑 |
| 至少三类任务可复现运行记录 | ⚠️ 部分 | 代码可跑通，但 `runs/*/` 被 gitignore，仓库内零运行记录 |
| 同一 Claims 生成组织者/讲解员/学生三类输出 | ❌ 未达成 | 仅按 audience 字符串选变体，三类视图未实现（P1 Batch D） |
| 科学可见窗口与现实活动时段分离 | ❌ 未达成 | M31 活动流程直接给出 19:13–04:28 共 555 分钟"观测进行中" |
| Review 下一轮输入可再进 runner 并产生可追差异 | ❌ 未达成 | `next_activity_input.json` 不存在（P1 Batch E） |
| 所有用户可见事实可经 Claim 映射溯源 | ⚠️ outreach 达成 / review 未达成 | outreach 100% 双向覆盖测试通过；`review_report.md` 无 Claim 门禁 |
| 无来源事实率 0、阻断原文泄漏率 0、映射覆盖率 100% | ✅ 离线测试达成 | 对抗测试与交付合同门禁覆盖 |
| 六类终态均有确定性输出 | ⚠️ 部分 | 可观测/不可观测/数据不足/工具错误有确定性路径；`NEEDS_CONFIRMATION` 以抛异常表达，面向 Agent 不够友好 |
| Manifest / Validation Report / 审计 / 公共返回状态一致 | ✅ 基本达成 | 少量瑕疵见 W6 |
| Qwen 作用、边界与调用证据清晰 | ⚠️ 边界清晰 / 证据缺失 | 架构边界文档化充分；真实调用记录为 0 |
| 评委仅读 20 页材料和 10 分钟视频即理解价值 | ❌ 未达成 | 材料与视频均未制作 |
| 团队成员能解释每个模块输入/输出/依赖/失败处理 | 待确认 | 文档充分，但未做人员访谈/演练 |

---

## 四、赛题要求逐条对照（方向三）

官方方向三原文（节选）：

> "鼓励团队开发一个面向具体任务环节的天文 skills 包……把原本分散、老旧或只适合人工操作的天文能力，改造成**可运行、可检查、可复现、可复用**的 AI Ready 组件……技能包应说明**服务对象、任务边界、输入输出、触发条件、依赖来源和失败处理方式**，并**保留关键中间结果**，方便评审复现和判断输出可靠性。"
>
> "初赛评价将关注技能包是否围绕明确任务形成闭环，而不是简单堆叠功能。如能对老旧但常用的天文工具进行接口标准化、运行加速或可复现重构，可考虑加分。"

| 官方要求 | 当前状态 | 证据 | 差距评价 |
|---|---|---|---|
| 可运行 | ✅ | 三案例离线秒级/十秒级跑通；pytest 185 通过 | 达标 |
| 可检查 | ✅ | Claim Registry、render_trace、run_outcome、validation_report、交付合同门禁 | 达标且超出平均 |
| 可复现 | ⚠️ | 离线 IERS 策略、manifest、固定案例可跑；但无第二环境复跑记录、运行记录未入库 | 差"独立复现证据"一步 |
| 可复用 | ⚠️ | 4 个 Skill 可单独调用；但未在任何 Qwen 智能体环境中加载验证 | 差真实加载证据 |
| 服务对象 | ✅ | 中小学教师、科普组织者、高校社团、非专业组织者已明确 | 达标 |
| 任务边界 | ✅ | 单晚观测、深空+亮星、不含行星/天气/望远镜控制，文档清楚 | 达标 |
| 输入输出/触发条件 | ✅ | `schemas.py` + `skills.yaml` 覆盖四 Skill 与总控 | 达标 |
| 依赖来源 | ✅ | requirements + README 许可证表 + catalog_provenance | 达标 |
| 失败处理 | ✅ | 六类业务状态 + fail-closed + 离线回退 | 达标且超出平均 |
| 保留关键中间结果 | ⚠️ | 运行目录 16–20 个产物文件；但未随仓库提交，人工确认项未签名 | 需补齐交付 |
| 围绕明确任务形成闭环 | ❌ | 计划→计算→科普包→日志→复盘已通；复盘→可执行下一轮→新活动包未通 | **最大差距** |
| 基座模型使用 Qwen/百炼并给调用凭证或截图 | ❌ | 无真实调用、无凭证/截图（9 个在线测试全部跳过） | **硬性合规缺口** |
| 技术方案文档 PDF ≤ 20 页（含源码、工作流、上下文工程、数据来源、反馈迭代） | ❌ | 未制作 | 未启动 |
| 附加：可交互前端 / 10 分钟内演示视频 | ❌ | 未制作（视频应为必选项对待） | 未启动 |
| 加分：对旧工具接口标准化/加速/复现重构 | ⚠️ | 已把 Astropy/astroplan 封装为 AI Ready Skill 并离线化（可作加分证据）；但未展示与传统流程对照 | 有素材未整理 |

**官方关键时间与项目文档的差异（必须修正）：**

| 事项 | 项目计划/转移日志 | 官方（阿里云官网 + NADC） | 处理建议 |
|---|---|---|---|
| 作品提交截止 | 2026-09-01 00:00（北京时间） | **2026-09-05 前**（官网与 NADC 一致） | 建议将计划改为 09-01 内部冻结、09-05 官方提交，并把差异记入 transfer diff log |
| 材料形式 | "一份不超过 20 页的 PPT/PDF" | 官方为"技术方案文档（PDF≤20 页）" | 以 PDF 技术方案为准（PPT 可作为答辩用） |
| 报名截止 | 未提及 | 2026-06-30 已截止（报名系统） | 需确认团队是否已完成官网报名（逾期不可补） |
| 初审 | 未提及 | 2026-09-20 前 | 材料需在 9/5 前一次性备齐 |
| 决赛 | 未提及 | 2026-11 擂台赛 | 材料/视频需支撑决赛答辩 |

---

## 五、深度审查发现

### 5.1 值得肯定的部分（当前优势）

1. **确定性计算与模型边界执行得彻底**：`observability_plan.py` 全部数值来自 Astropy/astroplan；Qwen 只产出 `ExpressionPlan`（claim_id + variant_id），最终事实句由程序渲染；12/12 交叉校验通过，我抽查的 M31 数值与物理预期一致。
2. **幻觉防护是三层结构且经过对抗测试**：Claim 准入（8 步验证）→ 确定性渲染（RenderedDocument 双向覆盖）→ 交付合同门禁（7 步 post-render 检查）；`test_mock_qwen_adversarial.py` 覆盖伪造 claim、伪造 variant、prohibited、注入、空响应、冲突等攻击面。
3. **离线策略进入产品入口**：`astro_runtime.configure_astronomy_runtime()` 在 runner 与直接调用 compute_observability 之前生效，README 三案例在无 Key、无缓存、代理不可达条件下正常终态。
4. **可审计状态机**：RunOutcome 三轴状态（业务/验证/交付）正交，manifest、validation report、公共返回同源。
5. **数据治理认真**：150 目标目录带 provenance、SIMBAD 交叉校验、10 轮 Layer 2/3 校验；隐私模块定义了审计文件与导出脱敏。
6. **文档纪律好**：多轮 error-check/phase-plan 报告齐全，README 对未完成项有诚实标注。

### 5.2 CRITICAL（不解决则基本与获奖无缘）

#### C-1 闭环未闭合：复盘结果无法重新进入 runner（最大卖点缺失）

- 位置：`observation_review.py` 的 `_build_revised_plan()` / `revised_plan.json`；`runner.py` 无 next-input 处理。
- 事实：`revised_plan.json` 是自定义结构（`revisions[]`、`suggestions[]`），不是 `StarPlanInput`；项目计划要求的 `next_activity_input.json`、before/after 活动包对比均不存在。
- 影响：方向三评分明确"关注技能包是否围绕明确任务形成闭环"；当前演示只能展示"计划→复盘"，不能展示"复盘→下一轮计划真实变化→重新渲染活动包"，等于把最核心的差异化证明缺失。
- 证据：`review_report.md` / `revised_plan.json`（本次实跑案例 3）与 README"尚未完全闭合的项目"自认一致。

#### C-2 现实活动时段与三类分众输出未实现，活动流程"通宵式"不可用

- 事实：M31 案例（2026-10-17，济南四门塔）活动流程为 18:58 准备 → 19:13 开始 → "19:13–04:28 观测进行中" → 04:54 结束，共约 9 小时；无 60–120 分钟现实活动 slot、无准备/收尾独立安排。
- 事实：`outreach_pack` 只有单一受众表达（按字符串含"新"选 beginner 变体），组织者/讲解员/学生三类视图、未成年人安全确认模板（P1 Batch D）均未实现。
- 影响：直接扣"内容转化清晰度"与"真实场景使用价值"；评审一眼就能看出产物不适合真实校园活动。

#### C-3 真实 Qwen 调用证据为零（官方硬性要求 + 技术深度失分）

- 事实：`tests/test_qwen_integration.py` 共 9 个在线测试全部 skip；仓库无 `.env.example`（README 却让用户 `cp .env.example .env`）；无百炼调用截图/凭证；`qwen_client.py` 默认模型名 `qwen3.7-max` 等未经过任何在线验证；`call_qwen*` 无超时参数。
- 影响：官方"技术基础"要求提供调用凭证或截图；技术深度评分中"模型、智能体、技能设计完整性与结果校验"无法被证明。若提交时仍如此，可能被视为未实际使用阿里云能力。

#### C-4 三组完整运行记录未入库，评审无法直接复现

- 事实：`StarPlan/.gitignore` 忽略 `runs/*/`，仓库内 0 个运行产物；`数据验证日志/` 是过程日志而非"输入+中间结果+最终输出+人工校验"的完整案例包；人工核对项只是清单，无签名/确认记录。
- 影响：官方要求"保留关键中间结果，方便评审复现和判断输出可靠性"；评审需要自己安装运行，或团队在提交包内另附 runs。

#### C-5 提交材料全部未做，且截止日期文档错误

- 事实：无 20 页内 PDF 技术方案、无演示视频、无复现包清单；项目计划把截止写成 09-01，官方为 09-05（若团队按 09-01 倒排会白白损失 4 天，但更危险的是按 09-01 提交前仍做不完）。
- 影响：应用潜力 30% 中的"演示、交互入口与交付完整度"基本只能拿低分。

### 5.3 WARNING（建议在 P1/P2 内关闭）

- **W-1 替代目标建议未经验证**：`_generate_alternatives()` 按月份静态表给 M13/M57 等，未对建议目标在"该地点该日期"实际计算可观测性；`blocking.alternatives` 却以 DERIVED_FACT 输出"当季更适合观测的目标"。建议对每个替代目标真实跑一次可观测性，或降级为"候选目标，需人工复核"。
- **W-2 Review 输出未纳入 Claim/交付门禁**：`review_report.md` 由字符串拼接生成，无 render_trace/双向覆盖/泄漏检查；改进建议是自由文本（虽为规则库产生）。P1 的 Review ID-only 协议未实现。
- **W-3 在线调用无超时/重试/熔断**：Qwen 调用异常会回退模板，但没有 30–35 秒超时控制，演示时网络挂起可能卡死入口；Chat 模式同理。
- **W-4 推荐窗口策略单一**：取"最长可见窗口"而非综合最优（如避开高月光、低空、暮光加权），也无反事实解释（提前/延后 1 小时变化）。可作为 P1 增强。
- **W-5 覆盖范围窄**：150 目标 + 8 城市；`date_range` 多天只算第一晚；无行星、无天象、无地平线遮挡。MVP 可接受，但需在技术方案中明确边界与扩展路径，避免评审按"天文助手"期望扣分。
- **W-6 文档与实现漂移**：README 写 "184 passed"，实跑 185；README 提 `.env.example` 但文件缺失；README 协作规范仍是五人分工（与计划三角色不符）；`run_outcome.json` 的 `state_transitions` 未含最终 RENDERED（写入顺序小瑕疵）；`StarPlan/docs/` 在 README 结构树中列出但不存在；根 README 仍写"仓库仅含规划材料"（已过时）。
- **W-7 BLOCKED 时结构化公共返回仍含 target/plan 数值**：测试合同只保证 `outreach_pack=None`；若评审按"公共返回 0 条事实"字面理解，会质疑合同不一致。建议文档明确约定，或按更严格合同置空。
- **W-8 独立环境复现与真实百炼 canary 仍为遗留项**（前轮报告 W-R2/W-R3 未关闭）。
- **W-9 人工确认机制未真正落地**：目标歧义以抛异常表达而非结构化 `NEEDS_CONFIRMATION` 返回；活动包人工核对无"确认前/后差异"记录。
- **W-10 派生可见性规则偏乐观**：`equipment.match`、肉眼/双筒可见性用简单星等阈值（已在 claim 内加 caveat），但"当前设备适合观测此目标"对初学者仍可能过度承诺，技术方案中应写明假设与限制。

### 5.4 INFO（顺手修）

- Windows 默认代码页下 CLI 中文输出乱码（不影响文件，但影响演示观感），建议 `run_case.py` 输出前设置 UTF-8 或提示 `chcp 65001`。
- 中文受众看到 `Andromeda` 星座英文名与 `RA/Dec` 英文标签，建议增加中文变体。
- `MoonInfo.moonrise/moonset` 恒为 None；`observation_log.json`、`review_trace.json` 未列入 README 产物表。
- 审计时间戳硬编码 UTC+8，若用户使用其它时区地点，时间戳仍为北京时间（可接受但需注明）。
- 目标目录中 M31 Dec 41.2688° 与项目文档示例 41.2692° 有 0.0004° 差异，属正常精度差异，建议统一表述。

---

## 六、改进建议：按 2026-09-05 提交倒排的路线图

原则：**先关闭环，再补证据，最后做材料**。不再加新功能（行星、微调、复杂前端一律后置）。

### P1 Batch D（8/3–8/8，本周）：现实活动时段 + 三类分众输出

- 新增 `activity_slot_policy_v1`：从科学窗口确定性选出 60–120 分钟现实活动时段（含准备/收尾各 15–30 分钟、可选 preferred start、人工确认状态）；`recommended_window` 保持科学窗口语义。
- 新增 `AudienceProfile`（age_band、experience_level、requested_views），同一 Claims 渲染 organizer / facilitator / learner 三视图；科学句与数字映射同一 claim_id。
- 未成年人场景增加 `youth_activity_policy_v1` 安全项与"待人工确认"标记（不采集隐私）。
- **验收标准**：M31 同时展示科学窗口与 90 分钟活动 slot；M42 不生成虚假 slot；三视图无事实冲突；新增测试全绿；更新 README/skills.yaml 只声明已实现能力。

### P1 Batch E（8/5–8/13）：可执行下一轮输入 + before/after

- `review_observation` 接收原始 `StarPlanInput` 规范化副本；白名单修订字段（如 ActivityPreferences、设备准备步骤）；输出符合 `StarPlanInput` 的 `next_activity_input.json`；通过 CLI/测试二次调用 runner 重跑并渲染新活动包；生成 before/after 对比表，每项变化引用 cause_id。
- **验收标准**：`next_activity_input.json` 通过 Schema；二次运行成功且不重复触发 Review；至少一个时间/设备/流程字段可见变化；删除证据后对应 patch 消失或降级为待确认。

### P2（8/10–8/17）：真实 Qwen 接入与智能体加载证据

1. 先跑 `scripts/test_qwen_connection.py` 与在线 canary，确认 `qwen3.7-max` 等模型名真实可用（不可用则改配置并记录）。
2. 为 `call_qwen*` 增加 30–35 秒超时、1 次重试、失败安全回退。
3. 选定一种"直接加载到智能体"的形态（百炼应用 / OpenAPI / MCP / QoderWork），写薄适配层，不复制核心逻辑。
4. 录制一次真实自然语言触发→工具链→Claim 渲染→返回的全过程，保存脱敏调用凭证截图与 `model_call_log.jsonl`（含真实 `type=model_call`）。
- **验收标准**：至少一次真实 Qwen 调用成功并留下审计证据；无 Key/无网络时仍按离线模板交付；四 Skill 的触发/输入/输出/失败说明更新进 `skills.yaml`。

### P3（8/14–8/22）：三案例固化 + 独立复现 + 人工复核

- 固定 M31 正常、M42 不可观测+备选、复盘闭环三类完整运行记录（输入、中间结果、输出、人工确认签名）；把 runs 作为提交包内容（建议同时提交到仓库或 `submission/runs/`）。
- 第二台电脑/干净 CI 复跑三案例并记录差异；完成一次小规模实地观测或明确标注的桌面演练；请 1 名物理教师/天文社成员做外部科学复核。
- **验收标准**：新环境零失败、三案例 <30 秒终态；每份案例包有人工确认记录；无来源事实率 0、泄漏率 0、映射覆盖率 100% 的测试证据随包附上。

### P4（8/18–8/27）：提交材料

- 20 页内 PDF 技术方案（官方要求的章节：问题与方法、架构、上下文工程、测试案例、数据来源、反馈迭代、源码入口）。
- 6–8 分钟演示视频（主线：一次完整闭环 + 一次不可观测 + 一次复盘→新计划）。
- 对照实验证据：裸 Qwen 与 Qwen+StarPlan 对同一问题的回答对比（可在 P2 后补）。
- 提交包清单：源码、requirements、许可证、三案例运行记录、复现脚本、隐私检查结果。
- **验收标准**：PDF ≤ 20 页；视频 ≤ 10 分钟；提交清单逐项打勾；敏感信息扫描通过。

### P5（8/28–9/5）：冻结与提交

- 停止加功能；全量回归；第二环境最终复跑；按官网要求打包（命名：学校-姓名-作品名-联系电话），上传网盘并附链接、提取码、截图；确认报名表盖章与申报系统一致。

### 加分项（仅在 P1–P3 全部完成后选做）

1. 替代目标自动验证：对建议目标实际计算可观测性后再输出。
2. 反事实解释：提前/延后 1 小时、更换目标/日期时各项风险如何变化。
3. 传统人工流程对照实验（完成时间、漏检项、新手解释能力问卷）。
4. 一键复现命令/脚本（当前 `run_offline_ci.bat` 已接近，补一个三案例一键包）。
5. 输出 Stellarium/Aladin 复现链接或脚本（作为人工复核出口，不做自研星图）。

---

## 七、风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| 真实 Qwen 模型名/限额/网络环境未知 | 高 | 8/10 前完成 canary，失败立即换模型名/平台 |
| 闭环功能延期导致卖点缺失 | 高 | 8/13 前必须完成 Batch E；不再插队新功能 |
| 独立复现环境（第二台电脑/CI）Windows ACL 问题 | 中 | 提前安排，参考 W-R2 的临时目录隔离方案 |
| 评审质疑替代目标、推荐窗口等科学细节 | 中 | 技术方案中写明假设、阈值与校验方法 |
| 团队人手（2+1）不足 | 中 | 材料与代码并行：A 做材料、B 做 P1、C 做复现 |
| 未确认是否完成官网报名（6/30 已截止） | 高 | 立即确认报名状态，这是硬门槛 |

---

## 八、结论

StarPlan 的**架构和工程质量已经具备获奖所需的"科学正确性 + 幻觉防护 + 可复现"地基**，这是很多参赛队不具备的。当前主要矛盾是：**地基之上还没有盖出评审能看见的房子**——闭环未闭合、Qwen 未真实调用、案例与材料未交付。

从今天（8/3）到官方截止（9/5）还有约 33 天。按本报告路线图执行，8 月中旬可完成闭环，8 月底可完成全部证据与材料；届时作品处于"能自证闭环 + 能自证低幻觉 + 能自证复现 + 有真实演示"的状态，符合方向三"围绕明确任务形成闭环"的评审核心，具备冲击高奖的现实可能。

---

## 九、真实 Qwen 实测补充（2026-08-03，三把 Key 实测）

> 本节为拿到用户提供的 API Key 后的真实在线审查结果。**Key 仅用于本会话环境变量，未写入仓库任何文件；运行目录与仓库全文检索均未发现 Key 泄漏。** 由于三把 Key 均与当前 `qwen_client.py` 的调用方式不兼容，在线链路通过"临时兼容端点适配层"（仅存在于审查会话内存中，未入库）完成验证。

### 9.1 三把 Key 实测矩阵

| Key | 声称 | 原生 DashScope 端点（当前代码路径） | OpenAI 兼容端点 | 结论 |
|---|---|---|---|---|
| Key-1（qwen3.7） | qwen3.7 | 曾连通 qwen3.7-max（本日早些时候成功）；之后返回 401 Invalid API-key | 401（同） | 已失效/被轮换；失效后 8 个集成测试失败、1 个通过，属 Key 状态而非代码缺陷 |
| Key-2（qwen3.8） | qwen3.8 | qwen3.7-max / qwen3.8-max-preview / qwen3.8-max 全部 403 或 400 | **qwen3.8-max 正常**（单轮与 JSON 均成功） | Key 有效，仅授权 qwen3.8-max，且只走兼容端点 |
| Key-3（qwen3.7） | qwen3.7 | 全部 403/400 | **qwen3.7-plus 正常**（单轮、JSON、工具调用均成功） | Key 有效，仅授权 qwen3.7-plus，且只走兼容端点 |

**核心结论（C-3 升级）**：问题已从"没有真实调用证据"升级为"**即使有 Key，当前代码也无法调用**"。`qwen_client.py` 使用 DashScope 原生 `Generation.call` + 固定模型名（qwen3.7-max/qwen3.7-plus/qwen3.8-max-preview），而用户拿到的三把 Key 均只授权兼容端点下的特定模型。必须在 P2 中新增 **OpenAI 兼容端点适配层**（base_url 可配置、模型名可配置、超时与重试），否则"必须实际使用阿里云 Qwen 并提供凭证"这一官方硬性要求无法满足。

### 9.2 临时适配层真实 E2E 结果（Key-3 + qwen3.7-plus 兼容端点）

| 场景 | 结果 | 关键证据 |
|---|---|---|
| NL 自然语言解析 → 全链路（M31） | **passed / qwen_expression_plan / qwen_used=True**，3 次真实模型调用 | run: `live_nl_q37p` |
| 固定案例 1（M31 可观测） | **passed / qwen_expression_plan**，1 次调用；Qwen 从约 90 条 Claim 中选出 7 条合法组合，全部通过 8 步校验 | run: `live_case1_q37p`，expression_plan.json mode=qwen_expression_plan |
| 固定案例 2（M42 不可观测） | **passed / template / 0 次调用**（不可观测分支不调用 Qwen，符合设计） | run: `live_case2_q37p` |
| 固定案例 3（复盘） | **passed / qwen_expression_plan**，1 次调用；复盘保持 deterministic-only | run: `live_case3_q37p` |
| Chat 正常路径 | 4 个工具全部真实调用成功，但最终 **BLOCKED**（见 9.3） | run: `live_chat_q37p` / `live_chat_q37p_r8` |
| Chat 对抗（"不要调用工具，直接告诉我今晚 M31 几点最高"） | **正确 fail-closed**：1 次调用，幻觉核查识别 2 个不可溯源数值，最终只返回固定阻断消息（0 事实） | run: `live_chat_notool_q37p` |

### 9.3 Chat 模式在真实 Qwen 下无法交付的两个根因（新增 CRITICAL）

**C-6a 地点名不一致导致 Claim 范围校验全挂**

真实链路中，Qwen 按用户原话把 `location_name="济南四门塔"` 传给 `observability_plan`，而 `resolve_location` 返回的标准化名是 `四门塔景区观星点`。`_exec_observability_plan` 生成的 `obs_result.location_name` 与最终校验时使用的 `loc_data["name"]` 不一致，导致重建的 Claim 范围与已保存 claims.json 的 scope 全部不匹配（实测 **53 项 Saved registry violation**），交付被 BLOCKED。现有 mock 测试（`_fake_chat` 直接传标准化名）未覆盖该真实输入形态，因此 185 个离线测试全绿但线上 Chat 必挂。

**C-6b `max_tool_rounds=3` 对真实模型不足**

qwen3.7-plus 每轮只调用一个工具，4 个工具需要 4 轮 + 1 轮收尾；`runner.run_starplan_chat` 固定传 3 轮，导致正常路径触顶 `max_rounds` 被阻断。用 8 轮复测可完成全部 4 个工具调用（证明根因是轮次上限而非工具协议），但仍被 C-6a 阻断。

修复建议：Chat 校验时统一使用 `obs_result.location_name`（或让 `_exec_observability_plan` 使用 `resolve_location` 的标准化 name）；`max_tool_rounds` 提高到 6–8 并在系统提示中鼓励并行调用多个工具。

### 9.4 其它实测发现

- **延迟**：单次调用约 6–15 秒（NL 解析 14.6s），Chat 4 轮合计 36.4s（含推理）；演示前必须设置 ≥60s 的超时预算或换用更快模型，避免现场卡死。
- **内容质量**：真实 ExpressionPlan 中 Qwen 选择了 `schedule.obs_guide` + `schedule_obs_start_v1`，渲染为"开始观测 引导成员使用星桥法寻找目标"（语法别扭）。说明部分 Claim 的 allowed_variant_ids 过宽，P1 应逐条收紧（该组合应禁止）。
- **原生端点不可用性**：三把 Key 在原生端点的失败模式为 403（Key 权限限制）或 400（url error / Model not exist），证明"兼容端点 + 精确模型名"是这类 Key 的唯一可用路径。
- **安全**：运行目录与仓库全文检索（`sk-ws-H.ELR` 前缀）均无 Key 泄漏。**强烈建议用户立即轮换所有在对话中明文分享过的 Key**。

### 9.5 对结论与路线图的更新

- 原 C-3 状态更新为：**已定位（Key 与客户端不兼容），未修复**；新增 C-6a/C-6b（Chat 真实缺陷）。
- P2 范围扩大：新增"兼容端点适配层（base_url/model 可配 + 60s 超时 + 1 次重试）"、"Chat 地点名归一化"、"max_tool_rounds≥6"、"收紧变体白名单"四项，验收标准改为"用团队实际 Key 完成一次真实 NL 触发与一次 Chat 工具链交付，validation 均 passed 且留有调用凭证截图"。
- 好消息：**结构化入口与 NL 入口在真实 Qwen 下已全部跑通**（三案例 + NL 均 passed、qwen_used=True），说明核心架构（Claim 渲染、8 步校验、交付门禁）对真实模型输出是有效的；剩余问题集中在客户端适配与 Chat 一致性上，均是可快速修复的工程问题。

---

## 十、P2 前置修复实施结果（2026-08-03，已完成）

### 10.1 已实施的代码修复（v0.6.0）

| 修复项 | 对应问题 | 改动 |
|---|---|---|
| OpenAI 兼容端点适配层 | C-3 | `qwen_client.py` 新增 `STARPLAN_QWEN_BASE_URL` / `STARPLAN_QWEN_MODEL` / `STARPLAN_QWEN_TIMEOUT` / `STARPLAN_QWEN_RETRIES` 环境变量；兼容模式下 `call_qwen` / `call_qwen_json` / `call_qwen_chat` 走 `chat/completions`（含工具调用、JSON 解析、5xx/网络错误有界重试、60s 默认超时）；原生 DashScope 路径保持默认 |
| Chat 地点名归一化 | C-6a | `runner.py` 的 `_exec_observability_plan` 优先使用 `resolve_location` 返回的标准化地点名，obs 结果与最终 Claim 校验范围一致 |
| Chat 轮次上限 | C-6b | `runner.py` 的 `max_tool_rounds` 从 3 提升到 6，并在系统提示中鼓励并行工具调用 |
| 变体白名单收紧 | I-5 | `claims.py` 中 `schedule.obs_progress/obs_guide/obs_end/obs_descend` 仅允许 `schedule_proc_v1`；`schedule.cleanup` 保留与渲染块共用的 `schedule_twilight_end_v1` |
| 缺失文件补齐 | W-6 | 新增 `StarPlan/.env.example`（含兼容端点/模型/超时/重试说明） |
| 版本一致性 | W-6 | `__version__` / `skills.yaml` / README 统一为 0.6.0 |

### 10.2 验证结果

**离线全量**：`pytest -q` = **195 passed, 9 skipped, 0 failed**（原 185 + 新增 10 个回归测试；9 个跳过仍为需要真实 Key 的在线集成测试）。

新增回归测试：

- `tests/test_qwen_compatible_client.py`（7 项）：兼容端点 JSON 调用与日志、模型环境变量覆盖、超时传递、工具调用循环、5xx 重试、403 不重试、原生路径回退。
- `tests/test_chat_location_normalization.py`（3 项）：真实 Chat 输入形态（用户原话地点名）可交付；轮次上限 ≥6；日程 Claim 变体白名单收紧。

**真实在线（Key-3 + qwen3.7-plus + 兼容端点，适配层为仓库正式代码）**：

| 场景 | 结果 |
|---|---|
| NL 自然语言 → 全链路 | **passed / qwen_expression_plan / qwen_used=True**，2 次真实调用 |
| 固定案例 1（M31） | **passed / qwen_expression_plan**，1 次真实调用 |
| Chat 正常路径 | **passed**，4 个工具全部调用、4 次真实模型调用，最终输出为 Claim 渲染内容 |
| Chat 对抗（拒绝工具） | 正确 fail-closed（blocked），幻觉核查识别 1 个不可溯源数值 |

**Key 状态变化**：Key-1 与 Key-2 在本日后续探测中已返回 401（被轮换/失效）；失效 Key 走适配层时会 fail-closed 回退模板并留下 `finish_reason=error` 审计条目（已在 Key-2 实测中确认）。**请团队用最新有效 Key 重跑一次完整演示并保存调用凭证。**

### 10.3 剩余状态

- 已关闭：C-3（客户端适配）、C-6a、C-6b、I-5、W-6 中 `.env.example` 与版本漂移部分。
- 仍未开始：P1 Batch D（现实活动时段 + 三视图 + 未成年人安全模板）、P1 Batch E（可执行下一轮 + before/after）、P3（三案例入库 + 独立复现 + 人工复核）、P4（PDF + 视频）。
- 遗留：Chat 每轮单工具导致 4–5 次调用（约 40–50s），演示需设置 ≥90s 预算或换更快模型；运行记录仍未入库（`runs/*/` 保持 gitignore，提交包需另附）。

---

## 十一、P1 Batch D 实施结果（2026-08-03，已完成，v0.7.0）

### 11.1 交付内容

| 验收项（项目计划 P1 基线） | 实施结果 |
|---|---|
| 科学窗口与现实活动时段分离 | `activity_slot_policy_v1`：从科学窗口确定性生成 60-120 分钟活动时段（默认 90 分钟，含准备/收尾）；M31 活动流程为 18:58 准备 → 19:13-20:43 观测 → 20:58 收尾，科学窗口 19:13~04:28 仍独立展示；窗口短于活动时长或不可观测时返回无 slot |
| 同一 Claims 的组织者/讲解员/学生三视图 | `AudienceProfile.requested_views` 控制；三视图由同一 Claim Registry 渲染，仅按板块过滤（organizer 全量、facilitator 含设备与核对项、learner 含讲解/安全/日程）；每视图独立 `outreach_pack_<view>.md`、`rendered_document_<view>.json`、`render_trace_<view>.json`、`sentence_claim_map_<view>.json`，并纳入交付合同校验 |
| 未成年人安全与人工确认 | `youth_activity_policy_v1`：受众为中小学生/儿童时追加监护人许可、成人陪同、点名等安全项与人工核对项（待人工确认）；不采集姓名、联系方式等隐私；runner 与校验重建使用同一 youth 标志，避免 saved-registry 漂移 |

### 11.2 验证证据

- 新增 `tests/test_activity_slot_and_views.py` 10 项（slot 策略 5 项 + runner 集成 5 项），全量 **205 passed, 9 skipped, 0 failed**。
- 案例 1（更新后的示例输入）实跑：24 个产物文件，`validation=passed`，三视图文件齐全；学习者视图包含现实活动流程与安全提示，无设备/核对板块。
- 案例 2（M42）：`activity_slot=None`，不生成虚假活动时段；案例 3（复盘）：正常终态。
- 交付合同：额外视图文档/trace 纳入 `validate_delivery_contract`（claim 存在、变体允许、哈希、trace 一致性），任一视图损坏即 BLOCKED。

### 11.3 下一步

- **P1 Batch E（立即）**：复盘输出可再次进入 runner 的 `next_activity_input.json` + before/after 活动包对比——这是闭环的最后一段，也是项目差异化卖点的最终证明。
- P2 收尾：用团队最新有效 Key 录制真实演示（NL 已通、案例 1 已通、Chat 已通）；保存调用凭证截图。
- P3：三案例完整运行记录入库 + 第二环境复跑 + 人工复核签名。
