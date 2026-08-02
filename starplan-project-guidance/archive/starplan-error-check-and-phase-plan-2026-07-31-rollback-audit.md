# StarPlan Loop 错误检查与阶段计划 - 2026-07-31 回退核验与架构基线复审

日期：2026-07-31
本地分支：`main`
当前 commit：`7b82318d1d7e62a0ff5b4a03f97541d0b99ac158`
目标架构基线：`c1ca7c0`
工作性质：远端/本地回退核验、静态审查、离线运行验证和协作规则加固；本次不修改业务代码

## 1. 核验结论

### 1.1 GitHub 与本地状态

- GitHub API 返回远端 `main` 为 `7b82318d1d7e62a0ff5b4a03f97541d0b99ac158`，提交说明为 `Revert teammate's code changes to restore Claim architecture (c1ca7c0 baseline)`。
- 本地 `HEAD`、本地远端跟踪引用 `origin/main` 均为 `7b82318d1d7e62a0ff5b4a03f97541d0b99ac158`。
- 因网络连接被重置，`git fetch` 连续 3 次未成功；本次另用 GitHub API 独立核验远端 SHA。结论是 GitHub 和本地当前指向同一提交，但在下一次开工前仍必须重新成功执行 fetch，不能长期把本地跟踪引用当作远端实时证据。

### 1.2 与 `c1ca7c0` 的对应关系

以下幻觉防护核心文件在 `7b82318` 与 `c1ca7c0` 的 Git blob 完全一致：

| 文件 | 核验结果 |
|---|---|
| `StarPlan/starplan_skills/claims.py` | 完全一致 |
| `StarPlan/starplan_skills/rendering.py` | 完全一致 |
| `StarPlan/starplan_skills/expression_validator.py` | 完全一致 |
| `StarPlan/starplan_skills/runner.py` | 完全一致 |
| `StarPlan/starplan_skills/outreach_pack.py` | 完全一致 |
| `StarPlan/starplan_skills/run_outcome.py` | 完全一致 |
| `StarPlan/tests/test_layer3_e2e.py` | 完全一致 |

因此，“回退到最后一版幻觉防护基线”对核心实现成立。仓库整体并不等于 `c1ca7c0`：后续加入的科学交叉校验脚本、科学边界测试、数据日志和阶段报告仍被保留。这种保留是合理的，因为它们可以继续作为后续修复的测试证据，不应再次覆盖可信输出主链路。

同时，回退撤销了 `419bd89` 中把 Claim 构建进一步上移到 `runner.py` 的改动。当前恢复的是 `c1ca7c0` 当时的实现状态，不等于项目计划中的最终完整架构。

## 2. Error Check

### 2.1 静态与运行验证

| 检查 | 结果 | 解释 |
|---|---:|---|
| Python 编译检查 | PASS | `starplan_skills`、脚本和测试可编译 |
| 固定示例验证 | 3/3 | 三个示例通过现有 Schema/结果校验 |
| Layer 1 目录校验 | 10 轮，0 issue | 本地目标目录基础一致性通过 |
| Layer 2/3 来源校验 | 10 轮，0 issue | 离线 provenance 与受信数据快照校验通过 |
| 幻觉与 Mock Qwen 对抗组 | 41/41 | 不可溯源数字、自由文本和恶意表达计划等现有用例通过 |
| Claim 逻辑测试 | 24 passed | 在可写隔离临时目录复跑后通过；此前 1 failure + 1 error 为本机临时目录权限问题 |
| Layer 3 端到端 | 14/14 | `claims.json`、表达计划、映射和模型原文阻断等现有门禁通过 |
| `astroplan` 独立交叉校验 | 12/12 | 当前两个固定案例在既定容差内一致 |
| 完整离线测试集 | 132 passed，2 failed | Claim 架构相关用例通过；两项保留的科学边界回归失败，见 CRITICAL-4 |

本次没有调用真实 Qwen/API；这里证明的是离线确定性链路和 Mock 对抗路径，不是线上模型兼容性。受回退影响的 Claim 核心文件能够编译，现有 Claim/Layer 3 用例能够无错误运行；但完整产品测试集尚未全绿，不能宣称整个项目验证完成。

### 2.2 CRITICAL

#### CRITICAL-1：`render_trace.json` 和全量“先 Claim、后渲染”仍未实现

**证据**：`StarPlan/README.md` 明确说明 `render_trace.json` 尚未实现，当前以 `sentence_claim_map.json` 临时代替。`outreach_pack.py` 先由 `_build_schedule()`、`_build_equipment_checklist()`、安全提示和人工核对列表生成用户可见文本，再在写文件阶段按类别补 Claim ID。不可观测分支也先扩展 `_build_not_observable_talking_points()` 的自由文本，再通过关键词启发式映射到 `blocking.reason` 等通用 Claim。

**影响**：当前映射能证明“一句话被贴了某个 ID”，但不能证明“这句话由该 Claim 和已审核句式确定性产生”。模板文字、回退文字和不可观测原因仍可在 Claim 之外新增事实，然后被事后映射掩盖，尚未达到项目计划要求的 100% Claim-to-render provenance。

**应修改的位置与方式**：

1. 在 `StarPlan/starplan_skills/claims.py` 为流程、设备、安全、人工核对、阻断原因和替代建议建立真实、细粒度、带来源与作用域的 Claims；禁止以一个通用 Claim 覆盖多种不同句子。
2. 在 `StarPlan/starplan_skills/rendering.py` 增加统一的 section renderer，使讲解、流程、设备、安全、核对项、不可观测原因和替代建议都只能由 `Claim + sentence_variant_id` 生成。
3. 在 `StarPlan/starplan_skills/outreach_pack.py` 删除“先拼文本、再猜 Claim”的 `full_trace`/`not_obs_trace` 逻辑；函数只接收渲染结果并组织版式，不再从 `target`/`obs_result` 自由拼事实句。
4. 输出正式 `render_trace.json`，每个用户可见句子至少记录稳定 `sentence_id`、文本 hash、Claim IDs、variant ID、section 和渲染模式。完成迁移后删除临时 `sentence_claim_map.json` 合同。
5. 在 `StarPlan/tests/test_layer3_e2e.py` 增加强制门禁：所有 Markdown 与结构化返回中的事实句均在 trace 中；删除任一必需 Claim 后渲染必须阻断或省略该句；不能通过事后补 ID 获得通过。

**状态**：未修复。当前回退只恢复了中间基线，项目计划第 3 周验收尚未完成。

#### CRITICAL-2：`RunOutcome` 仍不是唯一终态来源

**证据**：`runner.py` 已用 `outcome.build_manifest()` 生成 Manifest，但随后仍调用 `_write_validation_report(run_dir, resolved, obs_result, None)`，报告绕过 RunOutcome 独立推断状态；旧 `_build_manifest()` 也仍完整保留。验证状态仅根据 `outreach.qwen_validation_issues` 设置，尚未验证完整 artifact contract、trace 覆盖率和文件 hash 后再决定是否通过。

**影响**：Manifest、Validation Report、用户输出和 `run_outcome.json` 仍可能给出不一致结论；缺失产物或映射不完整时也可能得到 `passed`。这不满足项目计划中“RunOutcome 是单一事实来源”的要求。

**应修改的位置与方式**：

1. 删除或彻底停用 `StarPlan/starplan_skills/runner.py::_build_manifest()`，避免第二套状态生成逻辑继续被调用。
2. 将 `_write_validation_report()` 改为只接收最终 RunOutcome（或 RunOutcome 生成的只读 validation view），不能重新读取零散对象推断状态。
3. 在 runner 的 finalize 阶段先校验必需产物、trace 覆盖率、Claim hash、模型原文隔离和状态一致性，再一次性确定 business/validation/delivery 三轴并生成 Outcome、Manifest 和 Report。
4. 为 `NEEDS_CONFIRMATION`、`DATA_INSUFFICIENT`、`TOOL_ERROR`、`VALIDATION_BLOCKED` 等早退分支建立相同的终态文件合同和端到端测试。

**状态**：未修复。

#### CRITICAL-3：Chat 模式虽已阻断 Qwen 原文，但仍是第二套事实出口

**证据**：`runner.py::run_starplan_chat()` 总是阻断模型自由文本，这是正确的 fail-closed 行为；但最终内容由 `_build_deterministic_summary(captured)` 直接拼接，而不是复用 Claim Builder、ExpressionPlan validator 和统一 renderer。数字检查 `_check_chat_hallucination()` 只决定审计状态，不约束这套模板本身。

**影响**：主流水线和 Chat 可能对同一工具结果生成不同事实、格式和来源记录；以后修改一条路径时容易漏掉另一条。当前“模型原文泄漏率为 0”并不等于“Chat 所有事实 Claim 映射覆盖率为 100%”。

**应修改的位置与方式**：

1. 让 Chat 工具结果进入与 `run_starplan()` 相同的 Claim Builder 和 renderer；Qwen 只负责工具编排与表达计划 ID 选择。
2. Chat 的 `final_content` 必须来自统一 RenderResult；工具缺失、作用域不一致、表达计划非法或 Claim 不全时返回同一套确定性失败状态。
3. 把 Chat 的 trace、model-call 事件、Outcome、Manifest 和 Validation Report 纳入相同的运行目录合同。
4. 增加同输入的 `run_starplan`/Chat 等价性测试：允许语气和顺序差异，但业务状态、事实集合、数值、Claim 来源和失败语义必须一致。

**状态**：未修复；当前自由文本阻断机制有效，应保留。

#### CRITICAL-4：回退重新暴露两项科学边界错误

**复现**：完整离线测试失败于：

- `test_warning1_polar_day_not_observable`：极昼场景的 M31 被错误判为可观测。
- `test_warning2_latitude_limited_gives_location_not_date`：纬度永久受限的 M70 返回 `alternative_date`，而不是 `alternative_location`。

**影响**：前者忽略没有天文夜的阻断条件，后者给出无法解决问题的改期建议。它们属于产品科学正确性缺陷，不属于 Claim 架构测试失败。

**应修改的位置与顺序**：保留这两个失败测试作为红灯，但不要立即把旧版 `outreach_pack.py` 或整组冲突文件覆盖回来。先完成 CRITICAL-1 至 CRITICAL-3；随后从最新 `main` 新开科学修复分支，仅在 `observability_plan.py`、必要 Schema/约束和相应测试中重新实现最小修复，合并前要求完整幻觉/Layer 3 门禁与科学测试同时全绿。

**状态**：已确认、未修复；按依赖顺序延期到可信输出架构完成之后。

### 2.3 WARNING

#### WARNING-1：模型使用证据仍由结果标志合成

`runner.py` 根据 `outreach.qwen_used` 人工添加一个 `model_call` 事件，`RunOutcome` 再据此判断模型是否调用。这不是从 `model_call_log.jsonl` 的真实调用事件聚合得出。应先落盘规范化事件，再由 finalize 读取事件流计算 model provider、model name、次数、成功/失败和是否有结果被采用。

#### WARNING-2：遗留自由文本函数仍含不受支持的事实

`outreach_pack.py::_build_talking_points()` 仍包含“数十亿颗恒星”等没有当前数据来源的表述。它目前不在 ExpressionPlan 主路径，但保留可调用的旧实现会造成未来误接回归。完成统一 renderer 后应删除该函数及旧 FactCard 文案生成路径，或明确改成只供非用户可见测试使用并加不可调用门禁。

#### WARNING-3：运行环境的临时目录权限会制造假失败

初次 Claim/Layer 3 运行中出现 `tmp_path`/`TemporaryDirectory` 权限错误；换到独立、可写、已做创建-读写-删除预检的临时目录后，Claim 逻辑 24 项和 Layer 3 端到端 14 项通过。离线 CI 应为每次运行创建唯一临时根目录，同时设置 `TEMP`、`TMP`、pytest `--basetemp` 和 cache，并把环境错误与产品失败分开报告。

### 2.4 INFO

- 回退保留了交叉校验脚本和科学测试，后续可以直接把它们作为分支合并门禁。
- `README.md` 对 `render_trace.json` 尚未完成的说明是诚实的，当前不应改成“架构已完成”。
- 真实 Qwen canary 尚未执行；在离线架构门禁全绿之前，它不是阻断项，也不能替代 Mock 对抗测试。

## 3. Completion Status

| 项目计划阶段 | 当前状态 | 判断 |
|---|---|---|
| 第 1 周：范围、Schema、案例和验证规则 | 基本完成 | 核心范围和可信输出规则已写入项目计划；多人协作基线此前缺少强制同步规则，本次补齐 |
| 第 2 周：目标解析和本地可观测性计算 | 部分完成 | 常规案例与两个固定交叉校验案例可运行，但极昼和纬度永久受限两项回归未通过 |
| 第 3 周：Qwen 编排和科普活动包加固 | 进行中、阻断 | Claim/ExpressionPlan/确定性渲染骨架已恢复；全量 render trace、统一 Chat 和 RunOutcome 单一终态尚未完成 |
| 第 4 周：日志与复盘闭环 | 未在本次验收 | 不应在第 3 周可信输出门禁完成前扩展新的用户可见事实路径 |
| 第 5-6 周：演示、评测和材料 | 暂不进入 | 当前先消除架构阻断与科学红灯，避免把不稳定结果固化进演示材料 |

本次工作的完成点是“确认回退并固定协作基线”，不是“幻觉防护架构完成”。相对项目计划，Phase 3 仍落后；在其完成之前，科学性修复应作为独立分支保存。

## 4. Phase Plan

### P0：冻结当前可信输出基线与协作入口

**工作**：以 `7b82318` 为当前 `main` 基线；所有成员开工前 fetch/rebase 或 fast-forward；把科学工作放到独立分支；冲突时逐段审查受保护文件。

**验收标准**：

- 每份阶段报告记录 base commit、changed files、测试结果和目标合并点。
- 推送前 `origin/main...HEAD` 关系可解释，不存在静默丢失远端提交。
- 不再出现用整文件版本覆盖 `claims.py`、`rendering.py`、`runner.py`、`outreach_pack.py` 等架构文件的提交。

**阻塞/风险**：本机网络偶发 connection reset；fetch 失败时必须停止共享分支修改，不能用陈旧的 `origin/main` 猜测远端状态。

### P1：完成全量 Claim 渲染与正式 trace

**工作**：将 Claim Builder 提升到总控层；补齐所有用户可见 section 的 Claims 和模板；统一可观测/不可观测渲染；生成正式 `render_trace.json`。

**验收标准**：

- 用户可见无来源事实率为 0；Claim-to-render 映射覆盖率为 100%。
- 模板、回退、Chat、不可观测和异常分支均不能绕过 renderer。
- 任一未知 Claim、未知 variant、scope 不一致或缺失 Claim 都 fail closed，模型原文泄漏率为 0。
- Mock Qwen 对抗组、Layer 3 和新增 trace 完整性测试全部通过。

**阻塞/风险**：不能沿用“先生成文本再贴通用 ID”的实现方式；否则即使测试文件存在，也无法证明事实来源。

### P2：收口 RunOutcome 与审计证据链

**工作**：用单一 finalize 流程生成 Outcome、Manifest、Validation Report 和用户输出状态；从真实审计事件聚合模型使用；覆盖所有早退状态。

**验收标准**：

- 删除第二套 Manifest/Report 状态推导。
- 六类业务/失败状态均有稳定 artifact contract，文件缺失或 hash/trace 不一致时 validation 必须为 `blocked`。
- Outcome、Manifest、Report、公共返回的三轴状态完全一致。
- 模型未调用、调用失败、输出被拒绝和输出被采用四种情况可由日志独立证明。

**阻塞/风险**：若先继续增加输出格式，会扩大需要收口的事实出口数量。

### P3：统一 Chat 与主流水线

**工作**：Chat 只保留 Qwen 工具编排能力，最终事实输出复用同一 Claim/renderer/finalize 链路。

**验收标准**：

- 同一输入经结构化入口和 Chat 入口得到相同业务状态、事实集合、数值和来源。
- 任何 Qwen 自由文本都只进入受控审计存储，不进入公共返回或公开产物。
- Chat 的 malformed JSON、缺工具、伪造坐标、提示注入和模型异常用例全部确定性回退。

### P4：在独立分支恢复科学边界修复

**工作**：从完成 P1-P3 后的最新 `main` 新开分支，针对极昼和纬度永久受限重新实现最小科学修复；保留并扩展 `astroplan` 交叉验证。

**验收标准**：

- 当前完整离线集由 132/134 提升为至少 134/134，且新增极昼、极夜、高低纬、南天目标、月光阻断和时区跨日反例。
- `astroplan` 交叉校验异常计为失败并返回非零退出，不能吞异常。
- 幻觉/Layer 3/trace/RunOutcome 门禁保持全绿，受保护文件没有无关整文件改写。

**阻塞/风险**：直接 cherry-pick 含大范围 `outreach_pack.py` 重写的旧提交可能再次覆盖架构；应按测试意图重新实现小改动，而不是整提交恢复。

## 5. Immediate Next Actions

1. 所有协作者先同步并确认以 `7b82318` 或其后的最新 `main` 为基线；已有科学修改先保存在独立分支。
2. 下一工作单元只处理 P1：Claim Builder 上移、全量 section renderer 和 `render_trace.json`，不要混入科学性修复。
3. P1 合并前跑 Mock 对抗、Layer 3 和 trace 删除-阻断测试；通过后再处理 P2/P3。
4. P1-P3 全绿后，新开科学修复分支解决当前 2 个失败并跑完整离线集和扩展交叉校验。

## 6. 本次提交边界

本次只应提交：

- 根目录 `AGENTS.md` 的共享协作与分支规则；
- 本报告。

不得提交：`AGENTS.md` 中标记为 LOCAL-ONLY 的会话恢复说明、`StarPlan/tests/confidence_test_results.json` 的用户改动，以及用户正在进行的报告归档移动。
