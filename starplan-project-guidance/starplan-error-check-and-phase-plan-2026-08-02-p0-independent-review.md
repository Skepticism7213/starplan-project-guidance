# StarPlan P0 独立复查与纠错阶段计划（2026-08-02）

## 一、复查范围与结论

### 1. 复查基线

- 主线基线：`origin/main@5a45ddd`（`Refocus StarPlan competition execution plan`）
- 待审分支：`origin/feature/competition-p0-runtime-contract@453c9d9`
- 分支关系：相对 `origin/main` ahead 6、behind 0
- 提交范围：`3d0600e` 至 `453c9d9`，共 6 个提交、16 个文件
- 本轮性质：独立审查，不修改业务代码；仅新增本报告

当前工作区另有未提交的历史报告归档移动及 `StarPlan/_check_batch_c.txt`。这些变化不是本轮复查产生的，也未纳入本报告提交。

### 2. 总结论

Qwen 报告中的 Batch A、Batch B 结构化入口、Batch C 可见一致性修复大部分真实存在，新增定向测试也能够通过。但是，当前分支仍不能认定“P0 已完成”，也不建议直接合并到 `main`。原因不是低收益的形式问题，而是仍有数条比赛演示可触发的可信交付缺口：

1. Chat 已获得天文计算结果、但活动包构建失败时，代码仍可能把运行判为 `passed_with_warnings`，并向用户返回包含目标和可观测结论的事实文本。
2. Chat 合同失败时，`validation_status` 可以是 `blocked`，但 `delivery_status` 仍可能保留 `template`；同时没有生成提示用户查看的 `validation_report.md`。
3. Review 只在结构化 runner 的一个调用点显式关闭 Qwen；`review_observation()` 的公共默认值仍为 `True`，Chat 工具入口也没有传 `use_qwen=False`，自由文本归因仍然可达。
4. 模型实际被调用但 ExpressionPlan 被拒绝或回退时，Manifest/RunOutcome 可能记录为“模型未调用”；Chat 又只写一个 `model_call_summary`，没有按真实调用逐条进入 RunOutcome。
5. `claims.json` 的存在会被检查，但文件内容和其中的 `registry_hash` 没有在最终交付合同中与本次内存 Registry 做一致性校验，尚未完成项目计划要求的“损坏 claims.json 必须 BLOCKED”门禁。

因此当前准确状态应为：**P0-1 基本完成、P0-2 未完成、P0-3 部分完成、P0-4 大部分完成；P0 总门禁未通过。**

## 二、Error check

### CRITICAL

#### C-01：Chat 活动包构建失败后仍可能交付事实

**证据位置**：

- `StarPlan/starplan_skills/runner.py:838-858`：强制生成活动包失败后只把 `pack_data` 设为 `None`。
- `StarPlan/starplan_skills/runner.py:868-876`：只要已经有 `target_data` 和 `obs_data`，就生成包含目标与“可观测：是/否”的最小事实回退文本。
- `StarPlan/starplan_skills/runner.py:987-991`：没有活动包或缺少 `render_trace.json` 时，只要旧的数字/坐标检查没有发现问题，就把验证状态设为 `passed_with_warnings`。
- `StarPlan/starplan_skills/runner.py:1002-1008`：只有 `validation_status == blocked` 才替换为无事实说明。因此上述 `passed_with_warnings + not_delivered` 会把最小事实回退交给用户。

**竞争影响**：

比赛演示中，Qwen 编排成功但 Claim 活动包生成失败是现实故障。当前实现会出现“证据链没建成、delivery 是 not_delivered，但用户仍看到事实”的自相矛盾，直接削弱 fail-closed 的核心卖点。

**应如何修改**：

1. 在 Chat finalize 中建立硬不变量：`pack_data is None`、`delivery_status == not_delivered`、合同校验异常、必需证据文件缺失，任一成立都必须设置 `validation_status=blocked`。
2. 一旦 `validation_status=blocked`，同时强制 `delivery_status=not_delivered`，不能保留 `template` 或 `qwen_expression_plan`。
3. 只有完整活动包通过 `validate_delivery_contract()` 后，才允许生成公共 `final_content`。目标解析或可观测性计算成功只能保留在内部审计，不自动获得公共交付资格。
4. 不再使用 `verification["passed"]` 为缺少 Claim 活动包的路径放行；数字检查只能用于审计 Qwen 原文，不能替代交付合同。

**必须新增的测试**：

- Mock `call_qwen_chat()` 正常调用 target/location/observability，再让 `generate_outreach_pack()` 抛异常；断言公共状态为 blocked、delivery 为 not_delivered、final_content 为固定无事实说明，且不含 M31、坐标、高度、可观测结论或模型原文。
- 删除 `rendered_document.json`、`claims.json`、`render_trace.json` 分别运行真实 Chat finalize，均必须得到相同 BLOCKED 公共结果。

#### C-02：Chat 的三轴状态、Manifest、Validation Report 没有统一

**证据位置**：

- `StarPlan/starplan_skills/runner.py:949-986`：先把 delivery 设置为 template/qwen，合同失败时只修改 validation，没有同步改为 not_delivered。
- `StarPlan/starplan_skills/runner.py:1005-1008`：BLOCKED 文案要求用户查看 `validation_report.md`。
- `StarPlan/starplan_skills/runner.py:1010-1030`：Chat 只写 `run_outcome.json` 并返回结果，没有调用 Manifest/Validation Report writer，通常不存在文案所指的报告。

**竞争影响**：

评委若查看运行目录，会看到公共文案、RunOutcome 和交付状态互相冲突，或被引导到不存在的验证报告。这属于演示中高度可见的证据链断裂。

**应如何修改**：

1. 把结构化入口已有的最终化逻辑抽取为一个小型共享 finalize，输入 RunOutcome、run_dir、合同结果和允许交付的公共内容；不要复制第三套状态推断。
2. Chat Outcome 填入真实 `target`、`obs_result` 和 `location` 后，使用同一个 Manifest/Validation Report writer。
3. BLOCKED 终态必须同时满足：`validation=blocked`、`delivery=not_delivered`、公共文本无事实、`run_outcome.json`/`calculation_manifest.json`/`validation_report.md` 状态一致。
4. 如果本批不生成报告，则固定文案不得声称存在 `validation_report.md`；但按当前 project plan，推荐补齐报告而不是降低证据要求。

**必须新增的测试**：

- 对 Chat 合同失败断言三个文件存在，三处状态一致。
- 断言 fixed message 中提到的每一个 artifact 在运行目录真实存在。

#### C-03：Review 自由文本 Qwen 仍可从公共/Chat 入口触发

**证据位置**：

- `StarPlan/starplan_skills/observation_review.py:39-45`：`review_observation(..., use_qwen=True)` 仍是公共默认值。
- `StarPlan/starplan_skills/observation_review.py:193-208`：默认路径会把 Qwen 自由生成的原因与建议追加到用户可见 Review。
- `StarPlan/starplan_skills/runner.py:251-258`：结构化 runner 已显式传 `use_qwen=False`，这一处修复有效。
- `StarPlan/starplan_skills/runner.py:739-770`：Chat 的 `observation_review` tool executor 调用 `review_observation()` 时没有传 `use_qwen=False`，会重新落入不安全默认值。
- `StarPlan/tests/test_failclosed_public_return_b.py:126-187`：两条新增测试都显式传 `use_qwen=False`，没有验证公共默认或 Chat 工具入口。

**竞争影响**：

项目对外是四个可调用 Skills，而不是只有一个结构化 runner。只关闭一个调用点不能证明 Review 在比赛加载/工具调用时安全；无数字的虚构原因和建议正是既有幻觉架构要阻断的内容。

**应如何修改**：

1. 把 `review_observation()` 默认值改为 `use_qwen=False`，让竞赛安全模式成为函数级默认。
2. Chat `_exec_observation_review()` 显式传 `use_qwen=False`，同时传 `run_dir`、`log_path` 和地点时区，保证审计状态可落盘。
3. 保留 `_qwen_assisted_attribution()` 作为未开放的内部 helper，但在 ID-only 协议完成前，任何公开 Skill、runner、Chat executor 都不能传 `True`。
4. 在 `skills.yaml` 中明确当前 Review 是 deterministic-only，Qwen Review ID-only 属 P1，而不是写成 API 不可用时才回退。

**必须新增的测试**：

- Patch `_qwen_available=True`，并让 `_qwen_assisted_attribution` 在被调用时立即失败；不传 `use_qwen` 调用 `review_observation()`，应正常完成且 helper 调用次数为 0。
- 通过 Chat tool executor 触发 Review，Mock Qwen 返回纯文字虚构原因，最终 Review 和确定性基线必须完全一致。

#### C-04：真实模型调用与 RunOutcome/Manifest 记录可能不一致

**证据位置**：

- `StarPlan/starplan_skills/outreach_pack.py:95-131`：Qwen 可能已实际调用，但当 ExpressionPlan 无效、验证失败或异常时，`qwen_used` 保持 false 并走确定性回退。
- `StarPlan/starplan_skills/qwen_client.py:251-252,306-307,471-502`：真实调用会在 `model_call_log.jsonl` 写入 `type=model_call`。
- `StarPlan/starplan_skills/runner.py:328-336`：只有 `outreach.qwen_used=True` 才向 RunOutcome 添加模型事件；把“模型输出被采用”混同为“模型是否实际调用”。
- `StarPlan/starplan_skills/runner.py:559-574`：当模型已调用但结果被拒绝时，还会追加一条“Template mode -- no Qwen call”的合成记录。
- `StarPlan/starplan_skills/runner.py:993-1000`：Chat 把多次真实调用压成一个 `type=model_call_summary` 事件；RunOutcome 统计的是事件列表长度，不是日志中的真实调用数。

**竞争影响**：

“模型被调用但其结果被拒绝”本来是最能展示可信架构的证据。如果 Manifest 错记为未调用，评委无法确认系统确实完成了检测与回退，证据链反而降低可信度。

**应如何修改**：

1. 分离两个字段：`model_called` 表示实际 API 调用，`model_output_accepted` 或现有 `qwen_used` 表示是否采用模型选择结果。
2. finalize 前逐行读取 `model_call_log.jsonl` 中真实的 `type=model_call`，把每条事件加入 RunOutcome；不要根据 `outreach.qwen_used` 猜调用次数。
3. `_write_model_call_log()` 不得在已有真实调用后追加“no Qwen call”的错误说明；可记录 `delivery=deterministic_fallback` 和 `model_output_accepted=false`。
4. Chat 不写 `model_call_summary` 代替真实事件；若需要 summary，只作为派生字段，不能成为唯一事件。
5. Manifest 的 `model.called`、RunOutcome `model_call_count`、公共统计和 JSONL 实际条数必须相等。

**必须新增的测试**：模型调用 0 次、1 次成功、1 次被拒绝、多轮 Chat 调用四种场景，逐项断言日志、Outcome、Manifest 和公共计数一致。

#### C-05：最终交付合同未校验 `claims.json` 的实际内容完整性

**证据位置**：

- `StarPlan/starplan_skills/expression_validator.py:298-313`：D1 只检查 `claims.json` 是否存在。
- `StarPlan/starplan_skills/expression_validator.py:335-365`：Claim ID 与 variant 检查使用调用方传入的内存 `claims_builder`，没有从磁盘 `claims.json` 读取并验证 registry hash、source hashes 或 ID 集合。
- 当前新增测试通过 Mock 整个 `validate_delivery_contract()` 返回失败来验证公共返回，没有真实损坏 `claims.json` 后走完整 runner/Chat 终态。

**竞争影响**：

运行目录是比赛要求的可检查、可复现证据。如果磁盘 Claim Registry 被损坏而合同仍可通过，评委无法确认最终输出与提交证据确实对应。

**应如何修改**：

1. `validate_delivery_contract()` 读取 `claims.json`，验证 JSON/schema、`registry_hash`、source artifact hashes，并确认磁盘 Claim ID/variant allowlist 与当前 sealed builder 一致。
2. 推荐由 `AllowedClaimsBuilder` 提供 `verify_saved_registry(path)` 小函数，避免 validator 自己重写 hash 规则。
3. claims 文件损坏、hash 不匹配、Claim 被删除/新增、source hash 漂移均应产生 error 并 BLOCKED。

**必须新增的测试**：修改 claim value、不更新 hash；修改 value 同时伪造 hash；删除 Claim；新增未授权 Claim；损坏 JSON。结构化入口和 Chat 都不得交付事实。

### WARNING

#### W-01：离线天文运行策略未写入 Manifest

Project plan 要求 Manifest 记录实际离线数据 policy。当前 `astronomy_runtime=offline_bundled_data` 只打印到结构化入口控制台；`CalculationManifest` 和 `RunOutcome` 没有该字段，Chat 也没有相同可见记录。

**修改建议**：把 policy 保存在 RunOutcome，Manifest 至少在 `constraints_applied` 或新增明确字段中记录 `astronomy_runtime_policy=offline_bundled_data`，并测试生成文件而不是只检查 stdout。

#### W-02：单独调用 `observability_plan` 时不保证执行离线策略

`compute_observability()` 是 Skills 包的核心可调用实现，但 `observability_plan.py` 自身不调用 `configure_astronomy_runtime()`。目前 runner 和 Chat 顶层会调用，未来智能体若直接装载四个 Skill 并单独调用 observability skill，可能绕过该策略。

**修改建议**：在公开 observability 适配器或 `compute_observability()` 开头调用幂等配置；增加直接调用该 Skill 的空缓存、禁网子进程测试。

#### W-03：新增测试验证了常量或显式安全参数，没有覆盖真实默认路径

- `test_chat_blocked_final_content_no_facts` 只在测试文件里重新写了一份固定字符串，没有执行 `run_starplan_chat()`，即使生产代码完全删除该分支，测试仍会通过。
- Review 测试都显式传 `use_qwen=False`，无法发现函数默认值和 Chat executor 仍启用 Qwen。
- 结构化 BLOCKED 测试 Patch 掉整个 validator，只断言 `outreach_pack=None`；没有检查磁盘 Manifest/Report 状态、被阻断内容、模型调用计数和真实 artifact 损坏。

**修改建议**：测试必须从公开入口触发真实 finalize；可以 Mock 模型和工具输出，但不能在测试里复制被测常量或直接 Mock 掉需要验证的合同逻辑。

#### W-04：P0 closure 报告存在状态和数量表述偏差

- 报告“立即下一步”写审查 5 个提交，实际分支为 6 个提交。
- 报告称 P0 已完成，但 project plan 的 Chat artifact、真实 model-call 聚合、claims 损坏和 Manifest policy 验收尚未通过。
- “正常入口 30 秒内离线完成”只应指无 API Key 的确定性路径；报告同时给出的真实 Qwen M31/Review 为 34.5 秒/31.7 秒，应明确这是模型延迟，不要混成同一性能承诺。

**修改建议**：修复后更新同一 closure 报告的当前结论或新增 superseding 报告；保留原始测试时间，但分开描述 offline deterministic 与 live Qwen canary。

### INFO

#### I-01：确认有效的修改

1. `astro_runtime.py` 的幂等配置能够让 M31/M42 离线子进程门禁通过，未发现全局 warnings suppression。
2. 结构化 `run_starplan()` 在合同返回 BLOCKED 时已不再返回 `outreach.model_dump()`，而是 `outreach_pack=None`。
3. 结构化案例三已显式使用 `use_qwen=False`，避免 Review 等待真实模型。
4. `skills.yaml`、`starplan_skills.__version__` 和 README 当前能力版本统一为 0.5.0；README 中“自 v0.2.0 起”是历史能力起点，不构成当前版本漂移。
5. “今晚”改为“本次活动”、案例三删除冲突数字、偏差类型中文化、修订表表头移出循环的修改均合理。

#### I-02：本轮独立运行结果

| 检查 | 独立结果 |
|---|---|
| `compileall -q starplan_skills scripts tests` | PASS |
| `scripts/validate_examples.py` | 3 passed, 0 failed；注意该脚本只验证 JSON Schema，不运行完整流水线 |
| `tests/layer23_validation.py` | 150 targets × 10 rounds，0 unique issues |
| P0/交付合同/幻觉定向 pytest | 51 passed in 43.60s |
| `git diff --check origin/main...HEAD` | PASS |

定向 pytest 包含 `test_runtime_offline_policy.py`、`test_failclosed_public_return_b.py`、`test_delivery_contract_gate.py`、`test_mock_qwen_adversarial.py` 和 `test_chat_hallucination_c4.py`。

本轮尝试启动完整 pytest 和额外 Chat 故障注入时，桌面环境的外部 Python 执行审批服务连接中断，命令未触达项目代码。因此本报告不把 Qwen 所述“164 + 8”改写为独立复现结果；该结果暂作为分支作者提供的证据，合并前仍需第二台电脑全量重跑。

## 三、完成状态

| Project plan 项目 | 当前状态 | 说明 |
|---|---|---|
| P0-1：IERS/leap-second 离线运行 | **基本完成，未完全验收** | runner/Chat/cross_validate 已配置，离线子进程通过；Manifest policy 和直接 Skill 调用仍缺 |
| P0-2：公共 fail-closed 和统一终态 | **未完成** | 结构化入口主要缺口已修；Chat 缺包路径、delivery 状态、Manifest/Report、真实模型计数和 claims 文件完整性未关闭 |
| P0-3：Review 安全降级 | **部分完成** | 结构化 runner 已安全；公共函数默认值和 Chat executor 仍可调用自由文本 Qwen |
| P0-4：可见一致性 | **大部分完成** | 版本、措辞、案例数字、中文类型、表头已修；报告口径仍需更新 |
| P1：现实活动时段、分众输出、下一轮输入 | 未开始 | 当前不应启动，先关闭上述 P0 合并门禁 |

分支可以作为继续修复的正确基线，但不应以当前 `453c9d9` 直接合并到 `main`。

## 四、纠错阶段计划

### 修复批次 R1：关闭 Chat 公共失败路径

**修改范围**：`runner.py`、共享 finalize（如确有必要）、Chat 端到端测试。

1. 统一 `validation=blocked -> delivery=not_delivered -> fixed no-fact content` 不变量。
2. pack 缺失、合同异常、artifact 缺失/损坏全部 BLOCKED。
3. Chat 生成真实 Manifest 和 Validation Report，或在共享 finalize 中复用结构化 writer。
4. 用真实 `run_starplan_chat()` + Mock 工具/模型完成故障注入，不复制生产常量。

**验收标准**：

- 五类 Chat 故障：pack exception、claims missing、rendered document missing、trace corrupt、contract exception，全部返回 0 条事实。
- RunOutcome、Manifest、Validation Report 和公共 envelope 四处状态一致。
- BLOCKED 文案所引用的文件真实存在。

### 修复批次 R2：关闭 Review 和模型调用证据边界

**修改范围**：`observation_review.py`、`runner.py`、`run_outcome.py`、`skills.yaml`、相关测试。

1. Review 公共默认改为 `use_qwen=False`，结构化和 Chat 显式关闭。
2. 模型实际调用与模型结果是否采用拆成两个概念。
3. 从 JSONL 真实事件构建 RunOutcome/Manifest，删除错误的“未调用”合成结论和唯一 summary 事件。

**验收标准**：

- 所有公开 Review 入口在 ID-only 前调用 Qwen 次数为 0。
- 0/1/多次/被拒绝四种模型场景，JSONL、Outcome、Manifest、公共计数完全一致。

### 修复批次 R3：补齐证据文件和离线 policy 门禁

**修改范围**：`expression_validator.py`、`claims.py`、`astro_runtime.py`、`observability_plan.py`、Manifest Schema、相关测试。

1. 校验磁盘 `claims.json` 内容、registry hash、source hashes 和 Claim 集合。
2. Manifest 记录 astronomy runtime policy。
3. 直接调用 observability Skill 也执行幂等离线配置。

**验收标准**：

- 五类 claims 篡改全部 BLOCKED。
- 结构化和 Chat Manifest 均记录 `offline_bundled_data`。
- 空缓存、禁网、直接调用 observability Skill 在 30 秒内进入终态。

### 完整回归与合并门禁

R1-R3 每批独立提交，并从最新 feature 分支继续，不覆盖受保护的 Claim/rendering 文件。三批完成后执行：

1. compileall；
2. validate_examples（明确其为 schema gate）；
3. layer23_validation；
4. 全量 `pytest tests/`，包含子进程测试；
5. M31/M42/Review 无 Key 离线运行；
6. 一次低频真实 Qwen canary，验证“调用成功”和“模型结果被拒绝”两种证据状态；
7. 第二台电脑或干净环境从零重跑；
8. `git diff --check`、API Key 扫描和远端分支关系核验。

只有所有 CRITICAL 关闭、完整测试可复现、强制报告更新后，才合并到 `main` 并批准进入 P1 Batch D/E。

## 五、立即下一步

1. 不要把 `feature/competition-p0-runtime-contract@453c9d9` 直接合并到 `main`。
2. Qwen 先按 R1 修复 Chat 缺包/合同失败路径，这是当前最可能在智能体演示中暴露的阻断项。
3. 再按 R2 把 Review 默认值和 model-call 证据链一次关闭。
4. 最后按 R3 补齐 claims 文件完整性、Manifest runtime policy 和直接 Skill 离线入口。
5. 更新 P0 closure 报告，把“P0 已完成”改为实际状态，并提交新测试的命令、数量、时间和故障注入结果。
6. 修复分支 push 后交由独立审查；复查通过前不要回复“继续 P1”。

## 六、给 5.6 Luna 的一次性执行规格

以下内容是执行说明，不是新的产品方向。目标是让一次修复周期直接覆盖当前已知 P0 缺口，避免“修一个、再发现一个、再返工”的循环。

### 6.1 开始前的固定动作

1. 不要在当前有未提交归档移动的工作区直接改代码。建立独立 worktree/分支：

   ```text
   base: origin/feature/competition-p0-runtime-contract@453c9d9
   branch: codex/p0-runtime-contract-closure
   ```

   不要 reset、stash、checkout 覆盖原工作区的未提交文件。

2. 先读取以下文件，再开始修改：

   ```text
   AGENTS.md
   starplan-project-guidance/starplan-loop-project-plan.md
   starplan-project-guidance/starplan-error-check-and-phase-plan-2026-08-02-p0-independent-review.md
   StarPlan/starplan_skills/runner.py
   StarPlan/starplan_skills/observation_review.py
   StarPlan/starplan_skills/run_outcome.py
   StarPlan/starplan_skills/expression_validator.py
   StarPlan/starplan_skills/claims.py
   StarPlan/starplan_skills/observability_plan.py
   StarPlan/tests/test_failclosed_public_return_b.py
   StarPlan/tests/test_chat_hallucination_c4.py
   ```

3. 先执行一次基线检查并保存原始结果，不要修改测试来迁就基线：

   ```text
   python -m compileall -q starplan_skills scripts tests
   python scripts/validate_examples.py
   python tests/layer23_validation.py
   pytest -q tests/test_runtime_offline_policy.py tests/test_failclosed_public_return_b.py tests/test_delivery_contract_gate.py tests/test_mock_qwen_adversarial.py tests/test_chat_hallucination_c4.py
   ```

4. 只允许在本次工作中处理 R1、R2、R3 和本节性能改造；不得同时开始 P1 活动时段、分众模板、前端、行星或联网服务。

### 6.2 R1：Chat 终态和公共返回一次闭合

#### 文件与改动点

**`StarPlan/starplan_skills/runner.py`**

1. 在 `run_starplan_chat()` 的 827-1011 段整理 finalize 顺序，先得到三个事实：

   ```text
   pack_ready
   contract_passed
   artifact_set_complete
   ```

   `pack_ready` 必须同时表示 `pack_data` 非空、`rendered_document.json` 存在、`render_trace.json`/`claims.json`/`sentence_claim_map.json`/`expression_plan.json` 存在。

2. 以下任一条件成立时，直接进入同一个 BLOCKED 分支：

   ```text
   pack_data is None
   generate_outreach_pack() 抛异常
   rendered_document.json 缺失或反序列化失败
   validate_delivery_contract() 抛异常或返回 passed=False
   任一必需证据文件缺失或 JSON 损坏
   ```

3. BLOCKED 分支必须按此顺序执行：

   ```text
   chat_outcome.set_validation(BLOCKED, issues)
   chat_outcome.set_delivery(NOT_DELIVERED)
   final_content = 固定无事实说明
   ```

   不允许再走 868-876 的 `target_data + obs_data` 最小事实回退。

4. 只有 `pack_ready and contract_passed` 才能把 Claim-rendered talking points 写入 `final_content`。Qwen 原文、`blocked_content`、数字核查结果只能进入审计文件。

5. Chat 的 public return 保持稳定 envelope，只返回：

   ```text
   run_id, run_dir, mode, final_content,
   public_output_validation, model_text_accepted_for_delivery,
   tools_called, model_call_count, hallucination_blocked
   ```

   不新增自由文本、原始 messages 或 `pack_data`。

**`StarPlan/starplan_skills/run_outcome.py` 与共享 writer**

1. 复用结构化入口的 Manifest/Validation Report 生成逻辑，或提取最小共享函数；不要在 Chat 中继续维护一套独立状态推断。
2. Chat 必须在写 `run_outcome.json` 前写出 `calculation_manifest.json` 和 `validation_report.md`。
3. fixed message 中引用的文件必须在写出后再返回；如果写文件失败，也必须 BLOCKED，并改用不承诺文件存在的更短错误消息。

**R1 验收测试**

新增真实入口测试，不要在测试中复制生产字符串：

```text
test_chat_pack_exception_is_blocked
test_chat_missing_claims_is_blocked
test_chat_missing_rendered_document_is_blocked
test_chat_corrupt_trace_is_blocked
test_chat_contract_exception_is_blocked
```

每个测试都要：

1. Mock `call_qwen_chat()` 只负责返回合法的 target/location/observability 工具结果；
2. 只注入一个指定故障；
3. 调用真实 `run_starplan_chat()`；
4. 断言 `public_output_validation == "blocked"`、`delivery_status == "not_delivered"`（从 `run_outcome.json` 读取）、`final_content` 不含目标名、坐标、高度、可观测结论、原始 Qwen 文本；
5. 断言 Manifest、Report、Outcome 三者状态一致。

### 6.3 R2：Review 默认安全与模型调用证据一次闭合

#### 文件与改动点

**`StarPlan/starplan_skills/observation_review.py:39-45`**

把 `use_qwen` 默认值改成 `False`。这是 P1 ID-only 完成前的竞赛安全默认，不是永久删除 Qwen helper。

**`StarPlan/starplan_skills/runner.py:739-770`**

Chat `_exec_observation_review()` 显式传入：

```text
use_qwen=False
run_dir=run_dir
log_path=log_path
timezone_name=实际地点时区
```

不要让 Chat 通过省略参数重新打开自由文本归因。

**`StarPlan/skills.yaml`**

将 observation_review 的 failure handling 写成当前真实策略：

```text
当前版本 deterministic-only；Qwen Review ID-only 属 P1，未完成前不会调用
```

不要再用“API 不可用时回退”暗示正常情况下可以自由生成。

**`StarPlan/starplan_skills/runner.py:508-582` 与 `run_outcome.py`**

1. 新增两个明确概念：

   ```text
   model_called: JSONL 中真实 type=model_call 的数量 > 0
   model_output_accepted: Qwen ExpressionPlan 通过验证并被采用
   ```

   现有 `qwen_used` 可作为 `model_output_accepted` 的兼容别名，但不能再用它推断调用次数。

2. finalize 前读取 `model_call_log.jsonl`，逐条导入真实 `type=model_call` 事件；不要只添加一条 `model_call_summary`。
3. 删除或改写 `_write_model_call_log()` 中“Template mode -- no Qwen call”的错误说明。模型被调用但被拒绝时应记录：

   ```text
   model_called=true
   model_output_accepted=false
   delivery=deterministic_fallback
   ```

4. `RunOutcome.to_audit_summary()`、Manifest、公共计数和 JSONL 真实条数必须使用同一个派生结果。

#### R2 验收测试

```text
test_review_default_never_calls_qwen
test_chat_review_tool_never_calls_qwen
test_model_count_zero_is_consistent
test_model_count_one_accepted_is_consistent
test_model_count_one_rejected_is_consistent
test_model_count_multiple_chat_rounds_is_consistent
```

所有测试都从公开入口或真实 finalize 触发；禁止只构造一个局部 dict 来代替入口行为。

### 6.4 R3：Claims 文件、Manifest policy、直接 Skill 入口一次闭合

#### 文件与改动点

**`StarPlan/starplan_skills/expression_validator.py:298-313`**

保留 D1 的存在性检查，并追加磁盘 Registry 校验：

1. UTF-8 JSON 可解析且符合当前 schema；
2. `registry_hash` 与文件中 claims/prohibited 的规范化哈希一致；
3. `source_artifact_hashes` 与本次 target/observability/context snapshot 一致；
4. 磁盘 Claim IDs、Claim 类型、allowed variants 与 sealed `AllowedClaimsBuilder` 完全一致；
5. 缺失、增加、替换、篡改任何 Claim 都产生 error，最终 BLOCKED。

不要在 validator 中复制一套 hash 算法；在 `claims.py` 增加一个小的 `verify_saved_registry(path)`，由 validator 调用。

**`StarPlan/starplan_skills/run_outcome.py` 与 Manifest schema**

将 `configure_astronomy_runtime()` 返回的 policy 保存到 Outcome，并在 Manifest 中记录：

```json
"constraints_applied": {
  "astronomy_runtime_policy": "offline_bundled_data",
  "refraction_policy": "astropy_default (pressure=0, no atmospheric refraction)"
}
```

不得只打印 `astronomy_runtime=...`；控制台是提示，Manifest 才是复现证据。

**`StarPlan/starplan_skills/observability_plan.py`**

在 `compute_observability()` 的第一次 Astropy 对象创建前调用幂等的 `configure_astronomy_runtime()`，或在实际对外暴露的 Skill adapter 中调用。不得修改采样间隔作为这一步的“优化”。

#### R3 验收测试

```text
test_claim_file_value_tamper_blocks
test_claim_file_hash_tamper_blocks
test_claim_file_delete_blocks
test_claim_file_extra_claim_blocks
test_claim_file_invalid_json_blocks
test_manifest_records_astronomy_runtime_policy
test_direct_observability_skill_offline_subprocess
```

### 6.5 一次性完成定义和提交顺序

为了减少反复循环，Luna 应按以下方式推进：

1. 先完成 R1-R3 的代码和测试草稿，再运行一次定向测试；不要每发现一个小问题就提交一轮。
2. 只保留 3 个逻辑提交：

   ```text
   R1: Close Chat fail-closed finalization
   R2: Make Review and model evidence deterministic
   R3: Verify saved Claims and runtime policy
   ```

3. 三个提交完成后再运行一次完整回归。失败时只修复导致失败的当前批次，不重写已通过的 Claim/rendering 架构。
4. 只有下面的清单全部满足才生成新的 closure report：

   ```text
   [ ] Chat 五类故障真实入口均 BLOCKED 且公共返回无事实
   [ ] BLOCKED 时 validation/delivery/Manifest/Report/Outcome 一致
   [ ] 所有公开 Review 入口 Qwen 调用次数为 0
   [ ] 模型 0/1/拒绝/多轮计数一致
   [ ] claims.json 五类篡改均 BLOCKED
   [ ] Manifest 记录 offline_bundled_data
   [ ] 直接 observability Skill 经过离线策略
   [ ] 编译、示例、Layer2/3、全量 pytest、离线案例、API Key 扫描通过
   [ ] 第二台电脑或干净环境成功重跑
   [ ] 报告不再声称 P0 已完成，除非上述复核证据已附上
   ```

5. 不满足清单时停止在 P0，不要启动 P1，也不要用“测试数量通过”替代缺失的行为验收。

## 七、实际运行时间优化方案

性能优化必须建立在 R1-R3 可信终态之上；不允许通过减少 Claim、降低采样精度、跳过合同校验、放宽超时或把模型原文直接交付来提速。

### 7.1 先测再改：加入阶段耗时证据

**建议位置**：`StarPlan/starplan_skills/runner.py`、`run_outcome.py`。

用 `time.perf_counter()` 记录以下阶段，写入 `run_outcome.json` 的非事实审计字段 `stage_timings_ms`，同时打印简短控制台摘要：

```text
runtime_policy
target_resolve
observability_plan
outreach_pack_claim_build
outreach_pack_model_call
outreach_pack_render
observation_review
delivery_contract
manifest_and_report
total
```

先做 3 次 cold run 和 5 次 warm run，分别记录中位数和最大值。没有这组数据前不要凭感觉重写天文算法。

### 7.2 最大确定性瓶颈：减少 Moon/AltAz 重复计算

**现状位置**：`StarPlan/starplan_skills/observability_plan.py:277-318`。

当前每个 15 分钟采样点重复执行：

- target 的 AltAz transform；
- Sun 的 `get_body` + AltAz transform；
- Moon 的 `get_body` + AltAz transform；
- `moon_target_apparent_separation()` 内再次 `get_body("moon")`、再次 transform。

**推荐修改**：

1. 保持 15 分钟时间网格和所有输出字段不变，一次性构造 `Time` 数组和 `AltAz` 数组。
2. 对 target、Sun、Moon 做数组级 transform；Moon-target separation 仍必须在相同 AltAz frame 计算，不能恢复跨 frame `.separation()`。
3. 将当前单值 `moon_target_apparent_separation()` 扩展为内部数组实现，单值测试继续保留；所有 separation 仍经过同一处受保护逻辑。
4. 用同一数组结果填充 `HourlyData`，不得改变 round 精度或窗口判定条件。

**验收**：

- M31/M42 与当前结果的高度、方位、月距、窗口、可观测状态在既有容差内一致；
- `cross_validate.py` 全部通过；
- warm `observability_plan` 阶段耗时至少下降 30%，否则保留原实现，避免无收益重构。

### 7.3 第二个确定性瓶颈：向量化暮光扫描但保留科学精度

**现状位置**：`observability_plan.py:618-699`。

当前 evening/morning twilight 用 5 分钟步长逐点调用 `_sun_altitude()`，每次创建 Time、AltAz 和 Sun 坐标，再用少量二分细化。

**推荐修改**：

1. 5 分钟扫描的时间点保持不变，先批量构造 `Time` 数组并一次性计算 Sun altitude；
2. crossing 检测和 6 次二分逻辑保持不变；
3. 太阳高度阈值仍保持 `[0, -6, -12, -18]`，不把 5 分钟采样改成更粗间隔；
4. 在 `cross_validate.py` 中保持 2 分钟暮光容差，并增加一个极端日期/高纬度测试。

**验收**：暮光时间、推荐窗口和 `not_observable_reason` 不变；warm `observability_plan` 再下降 20% 或至少不回退。

### 7.4 最大用户感知瓶颈：减少 Qwen 模型往返

**现状位置**：`qwen_client.py:312-420` 和 `runner.py:634-819`。

`run_starplan_chat()` 最多进行 5 轮模型调用，通常需要 target、location、observability、final response 多次往返；而这些工具中除最终表达外都应由确定性代码完成。

**比赛演示的首选路径（无需先重写 Chat）**：

1. 使用 Qwen 智能体调用复合入口 `starplan.run`，让一个模型请求完成意图识别/参数收集；内部四个 Skills 仍按顺序执行。
2. 由代码直接返回 Claim-rendered 活动包；不要再让内部 `run_starplan_chat()` 进行四轮工具编排。
3. 观测 Review 继续 deterministic-only。

这条路径通常可把“多轮 Chat + 活动包 Qwen”降为“外层一次调用 + 确定性计算”。它是演示路径选择，不改变四个核心 Skill 的闭环设计。

**如必须保留 Chat 作为主入口**：

1. 将 target_resolve 和 resolve_location 作为同一轮可并行工具调用；observability 只在两者都完成后调用；
2. 限制 `max_tool_rounds` 为 3，并在达到上限时直接进入无事实 BLOCKED，而不是继续猜测；
3. 对已经由外层 Qwen 完成编排的调用，允许内部 `generate_outreach_pack(..., use_qwen=False)`，避免第二次 ExpressionPlan 模型调用；
4. 不允许通过缩短模型超时后把未验证内容交给用户；超时只触发确定性模板或 BLOCKED。

**模型选择建议**：

- 先用现有 `QWEN_MODELS["max"]` 做基线；
- 在同一 prompt、同一输入、无事实自由文本的前提下，对现有 `plus` 做 5 次 canary，比较 p50/p95 延迟、JSON/工具调用成功率和 ExpressionPlan 通过率；
- 只有 plus 在通过率和事实门禁完全不退化时，才把“表达选择”切换到 plus；外层复杂编排仍可保留 max；
- 不要仅因单次更快就永久改默认模型。

### 7.5 低风险运行时优化

这些优化可以与 R1-R3 同批完成，但收益小于模型往返和数组计算：

1. `config.py` 的约束、地点、星表加载可使用进程内只读缓存（以文件修改时间/版本为失效条件），不改变文件内容和 hash 证据。
2. 在 Qwen agent 进程启动阶段完成 Astropy/IERS policy 和 Matplotlib backend 初始化，减少首次调用冷启动；不要在每个 Skill 内重复导入或配置。
3. 保持 CSV/PNG 产物和 Claim/Report 产物不变；不要为了速度默认关闭可复现证据文件。
4. Matplotlib `savefig` 只在阶段耗时证实为主要瓶颈时调整 dpi；推荐先保持 150 dpi，避免演示图片质量下降。

### 7.6 性能验收目标

目标分两层，不把网络模型延迟伪装成确定性算法性能：

| 路径 | 目标 |
|---|---|
| 无 Key、空缓存、冷启动 | M31/M42/Review 各自 ≤ 30 秒进入终态 |
| 无 Key、同一进程 warm run | M31/M42/Review p95 ≤ 15 秒 |
| 复合 `starplan.run` 演示路径 | 外层一次模型调用后，确定性核心 p95 ≤ 15 秒 |
| Chat 备用路径 | 最多 3 轮模型调用；失败时 ≤ 30 秒进入 BLOCKED/模板终态 |
| 科学结果 | 所有既有数值/交叉校验容差保持不变 |

网络模型的真实端到端耗时单独记录 p50/p95，不把 provider capacity、网络抖动或模型响应时间写成代码保证。若模型超过预算，必须回退到确定性输出或 BLOCKED，不能扩大自由文本权限。

## 八、交付前最终检查模板

Luna 完成后只需提交一份新 closure report，按以下顺序附证据：

1. 基线提交、修复提交和工作区状态；
2. R1/R2/R3 每项修改文件与行为前后对比；
3. 五类 Chat 故障、四类模型计数、五类 Claims 篡改的测试结果；
4. 编译、Schema、Layer 2/3、定向 pytest、全量 pytest、三案例 cold/warm 计时；
5. 第二台电脑/干净环境结果；
6. 仅当所有 CRITICAL 为 0 时，才把完成状态写为“P0 已验收”；否则明确列出剩余阻断。

报告完成后再由独立审查者审一次；在此之前不继续增加新功能。
