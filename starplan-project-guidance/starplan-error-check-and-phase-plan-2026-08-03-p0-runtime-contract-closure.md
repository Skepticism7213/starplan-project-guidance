# StarPlan 错误检查与阶段计划 - P0 Runtime Contract Closure（2026-08-03）

日期：2026-08-03

分支：`codex/p0-runtime-contract-closure`

基线：`origin/feature/competition-p0-runtime-contract@76ec13e`（该分支相对 `origin/main` ahead 7、behind 0）

范围：仅完成独立审查报告第六节要求的 R1、R2、R3，以及不改变科学约束的确定性性能改造；未启动 P1 活动时段、分众模板、前端、行星或联网服务。

## 一、错误检查

### CRITICAL

| 编号 | 问题 | 具体修复位置与方式 | 验证结果 |
|---|---|---|---|
| C-R1 | Chat 在活动包生成异常或缺证据时仍可能返回目标名、可观测结论等事实回退文本 | `StarPlan/starplan_skills/runner.py:841+` 重排 Chat finalize，统一计算 `pack_ready`、`artifact_set_complete`、`contract_passed`；移除 `target_data + obs_data` 最小事实回退；所有失败统一设置 `BLOCKED + NOT_DELIVERED`，再生成固定无事实消息 | 新增真实入口覆盖 pack exception、missing claims、missing rendered document、corrupt trace、contract exception；5 类均 `public_output_validation=blocked`，最终文本不含目标名、数字或 Qwen 原文 |
| C-R2 | Chat 只写 `run_outcome.json`，Manifest/Report 缺失或与终态不一致；文件写入异常没有安全回退 | `runner.py` 复用 `_write_validation_report()`，在 `run_outcome.json` 前写 `calculation_manifest.json` 和 `validation_report.md`；写入异常重新设置 BLOCKED，并仅在 Report 确实存在时引用文件名 | 故障注入测试断言 Manifest、Report、Outcome 三者状态一致；正常 Chat 生成完整审计文件 |
| C-R3 | `qwen_used` 被当作模型是否调用，导致“调用但 ExpressionPlan 被拒绝”被记成 0 次 | `run_outcome.py` 新增 `import_model_call_events()`、`model_called`、`model_output_accepted`；`runner.py` finalize 前逐条读取 JSONL 的真实 `type=model_call`，不再添加虚假的 summary event；`_write_model_call_log()` 改写拒绝说明 | 新增 0 次、1 次 accepted、1 次 rejected、2 次多轮计数测试；JSONL 条数、Outcome 计数和 Manifest `model.called` 使用同一来源 |
| C-R4 | 交付合同只检查 `claims.json` 是否存在，磁盘 Claim Registry 被篡改仍可能继续交付 | `claims.py` 新增 `AllowedClaimsBuilder.verify_saved_registry(path)`，验证 UTF-8/JSON/schema、registry hash、source artifact hashes、run scope、Claim ID/type/allowed variants、derivation/template hash；`expression_validator.py` 在 ExpressionPlan 和 delivery contract 阶段调用 | value、hash、delete、extra、invalid JSON 五类磁盘篡改测试全部阻断；正常 Claims 文件仍通过 |
| C-R5 | 直接调用 `compute_observability()` 可以绕过 runner 的离线 IERS policy | `observability_plan.py:compute_observability()` 在首个 Astropy 对象创建前幂等调用 `configure_astronomy_runtime()`；`run_outcome.py` 将 policy 写入 Manifest `constraints_applied.astronomy_runtime_policy` | 直接 Skill 离线子进程通过；Manifest 记录 `offline_bundled_data` 和无折射策略 |

以上 CRITICAL 均已修复；本轮没有遗留的代码级 CRITICAL。

### WARNING

| 编号 | 项目 | 当前状态与影响 |
|---|---|---|
| W-01 | 第二台电脑/干净环境 | 当前已在新 worktree、无 API Key、禁网/离线策略和 fresh subprocess 条件下验证，但没有第二台物理电脑结果；提交前应由另一台机器或 CI 重跑同一命令集。 |
| W-02 | 真实 Qwen provider canary | 本轮使用确定性 mock 验证 Chat 故障边界；未在本轮消耗真实百炼额度做 max/plus 延迟 canary。真实 provider capacity、网络抖动和限流仍是外部风险；调用失败现在会在不泄漏事实的前提下 BLOCKED。 |
| W-03 | Windows ACL | 本机没有复现临时目录 PermissionError；这是环境风险而非当前代码错误，需在第二台机器检查运行目录写权限。 |
| W-04 | Chat 的 `coord_warning`/不可溯源数字 | 原始 Qwen 文本和坐标诊断只进入 `chat_conversation.json` 审计，不降级已经通过合同的 Claim-rendered 文档；如果演示入口要把坐标来源警告视为阻断，应在独立需求中增加对应策略，不在本批次放宽事实边界。 |

### INFO

| 检查 | 结果 |
|---|---|
| `python -m compileall -q starplan_skills scripts tests` | PASS |
| `python scripts/validate_examples.py` | 3 passed, 0 failed |
| `python tests/layer23_validation.py` | 150 targets × 10 rounds，0 unique issues，round consistency 全为 0 |
| `python scripts/cross_validate.py` | 12/12 项在 astroplan 容差内通过 |
| 定向 Review/Layer3/R1-R3 测试 | 78 passed |
| 新增 `tests/test_p0_runtime_contract_closure.py` | 17 passed |
| 全量 `pytest -q` | **180 passed, 9 skipped, 0 failed**（37.20s；跳过项为无可用 API Key 的真实 Qwen 集成） |
| `git diff --check` | PASS；仅有仓库原有的 LF/CRLF 提示 |

## 二、完成状态

| 项目计划阶段 | 本轮状态 |
|---|---|
| Phase 3：Claim 证据链、fail-closed 和可审计终态 | R1/R2/R3 已完成；Chat、Review、Claims、Manifest 和直接 Skill 入口均有行为门禁 |
| P0 Runtime Contract Closure | 本地代码验收完成；所有 CRITICAL 为 0；仍需 W-01 的独立环境复跑作为交付前确认 |
| P1 竞赛核心闭环（活动时段、分众输出、下一轮输入） | 未开始，保持冻结 |
| P2 智能体加载平台/真实活动素材 | 未开始，保持冻结 |

### R1 实施结果

`run_starplan_chat()` 现在先执行工具调用和 Claim 渲染，再验证六类证据文件与 delivery contract。任一异常都会走同一个状态分支：

```text
validation_status = blocked
delivery_status = not_delivered
final_content = fixed no-fact message
public outreach_pack/packs = never exposed
```

成功时公共返回只保留运行标识、固定渲染文本、验证状态、工具列表、模型计数和安全标志；原始 messages、Qwen 文本和 `pack_data` 只在审计目录保存。

### R2 实施结果

- `review_observation(..., use_qwen=False)` 成为默认值。
- Chat Review executor 显式传 `use_qwen=False`、实际 `run_dir`、`model_call_log.jsonl` 和地点时区。
- `model_called` 只表示 JSONL 中存在真实 provider call；`model_output_accepted` 只表示 ExpressionPlan 通过验证并被采用；`qwen_used` 仅作为兼容别名。
- Chat 内部 outreach 使用确定性渲染，避免外层编排之后再产生一次 ExpressionPlan provider round。
- Chat 工具轮次上限从 5 降为 3，达到上限会进入安全终态。

### R3 实施结果

- 磁盘 Claims Registry 由 builder 统一校验，validator 不复制 hash 算法。
- `calculation_manifest.json` 的 `constraints_applied` 保存离线数据 policy 和折射 policy。
- `compute_observability()` 无论从 runner 还是直接 Skill adapter 调用，都先应用离线 runtime policy。

## 三、性能检查与结果

性能优化没有减少 Claim、降低采样精度、跳过合同验证或交付模型原文。

### 确定性算法优化

1. `observability_plan.py` 的 15 分钟采样改为一次性构造 `Time` 数组和 `AltAz` 数组，target/Sun/Moon 均批量 transform；Moon-target separation 仍在同一 AltAz frame 计算。
2. evening/morning twilight 保留原 5 分钟扫描网格和 6 次二分，只把 Sun altitude 扫描改为数组计算。
3. 既有输出字段、round 精度、窗口判定、月距函数和跨实现容差均未改变。

### 实测耗时

独立进程 cold（同一主机、无 Key、offline policy、每次新进程）：

| 案例 | wall time |
|---|---:|
| M31 observable | 2.86s |
| M42 not observable | 2.76s |
| Review | 2.87s |

同一进程 warm，各案例连续 5 次的最大值分别为：M31 1.60s、M42 0.86s、Review 0.85s，均远低于 15s 目标。最终 M31 审计样例的阶段计时为：

```text
observability_plan          1538.970 ms
outreach_pack_claim_build      3.912 ms
outreach_pack_model_call       0.000 ms
outreach_pack_render           3.896 ms
delivery_contract              3.959 ms
manifest_and_report           11.339 ms
total                       1571.406 ms
```

向量化前同一确定性 M31 smoke 的总耗时约 4.97s；当前约 1.57s，约下降 68%，且 `cross_validate.py` 12/12 通过。

## 四、风险与边界

1. 本轮不把真实 Qwen provider 延迟写成代码保证；真实调用超过预算时只能回退到确定性输出或 BLOCKED。
2. 复合 `starplan.run` 仍是竞赛演示优先入口；Chat 是最多 3 轮的备用编排入口，Review 维持 deterministic-only。
3. 当前没有新增 P1 分众模板、现实活动时段或下一轮输入 schema，避免在 P0 证据链关闭前扩大变更面。
4. `claims.json`、`render_trace.json`、`sentence_claim_map.json`、`expression_plan.json` 和 Manifest/Report 是交付证据，不得为了提速删除。

## 五、下一阶段计划

### P0 收尾（独立复跑后关闭）

1. 在第二台电脑或干净 CI 环境执行：compileall、validate_examples、layer23、全量 pytest、三个 offline case 和 `cross_validate.py`。
2. 检查临时运行目录 ACL，确认能创建、读取和删除所有证据文件。
3. 只在上述结果无新增 CRITICAL/WARNING 时合并到 `main`；保留本 closure branch 的三批逻辑提交和报告。

### P1（负责人明确确认后）

1. Batch D：从确定性科学窗口生成 60-120 分钟现实活动时段，并为 organizer/facilitator/learner 生成共享 Claim IDs 的三类视图。验收：M31 不再默认通宵，三类视图数值完全一致。
2. Batch E：从 Review 的 Cause/Evidence 生成符合 `StarPlanInput` 的 `next_activity_input.json`，第二次 runner 可复现运行且变化可追溯到 cause ID。
3. 为 P1 每个新增用户可见路径同时实现 observable/not-observable 和 BLOCKED 分支，并复用同一 Manifest/Report 门禁。

## 六、立即下一步

1. 先把 `codex/p0-runtime-contract-closure` 推送并让独立审查者复查完整 diff；不要在复查前开始 P1。
2. 在另一台机器/干净 CI 重跑本报告的命令清单，重点检查 ACL 和真实证据文件是否完整。
3. 负责人确认 P0 后，再决定是否以 `starplan.run` 作为比赛演示主入口；Chat 只作为备用故障演示路径。
4. 进入 P1 前冻结首个中小学生年龄段、八月实地观测日期和 Qwen 智能体加载载体。

## 七、文件变更清单

| 文件 | 变化 |
|---|---|
| `StarPlan/starplan_skills/runner.py` | Chat fail-closed finalize、统一终态文件、JSONL 模型证据、三轮上限和阶段计时 |
| `StarPlan/starplan_skills/run_outcome.py` | model_called/model_output_accepted、JSONL 导入、runtime policy、stage timings、Manifest 派生 |
| `StarPlan/starplan_skills/claims.py` | `verify_saved_registry()` 磁盘完整性校验 |
| `StarPlan/starplan_skills/expression_validator.py` | 调用保存 Registry 校验并将错误作为阻断项 |
| `StarPlan/starplan_skills/observation_review.py` | deterministic-only 默认值 |
| `StarPlan/starplan_skills/observability_plan.py` | 直接入口 offline policy、批量 AltAz/Moon/暮光计算 |
| `StarPlan/starplan_skills/outreach_pack.py` | ExpressionPlan claims_path 校验、真实 Claim/model/render 阶段计时 |
| `StarPlan/skills.yaml` | 明确 P1 ID-only 前 Review 不调用 Qwen |
| `StarPlan/tests/test_p0_runtime_contract_closure.py` | Chat 五类故障、正常路径、Review 参数、模型证据、五类 Claims 篡改、直接离线 Skill 门禁 |

## 八、提交前检查

- [x] Chat 五类故障真实入口均 BLOCKED 且公共返回无事实
- [x] BLOCKED 时 validation/delivery/Manifest/Report/Outcome 一致
- [x] 所有公开 Review 入口默认不调用 Qwen
- [x] 模型 0/1/拒绝/多轮计数一致
- [x] `claims.json` 五类篡改均 BLOCKED
- [x] Manifest 记录 `offline_bundled_data`
- [x] 直接 observability Skill 经过离线策略
- [x] 编译、示例、Layer2/3、交叉验证、全量 pytest、离线案例通过
- [ ] 第二台电脑或干净环境独立重跑（W-01）

在 W-01 完成前，状态表述为“P0 runtime contract closure 本地验收完成，等待独立环境复核”，不启动 P1。
