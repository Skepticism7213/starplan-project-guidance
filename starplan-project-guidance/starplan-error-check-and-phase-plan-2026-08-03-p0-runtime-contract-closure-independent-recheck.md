# StarPlan 错误检查与阶段计划 - P0 Runtime Contract Closure 独立复查（2026-08-03）

日期：2026-08-03
分支：`codex/p0-runtime-contract-closure`
复查基线：`9ea604e`（R1/R2/R3 closure）
远端：`origin/codex/p0-runtime-contract-closure`
范围：只复查并收敛第六节 R1、R2、R3 和已有离线性能改造；不启动 P1 活动时段、分众模板、下一轮输入、前端或联网服务。

## 一、Error Check

### CRITICAL

#### C-R6：模型调用证据损坏时仍可能交付

**复现方式（修复前）**：在结构化入口已经写出的 `model_call_log.jsonl` 末尾追加一行无效 JSON，再调用 `run_starplan()`。原实现会把解析警告放入 `validation_issues`，但仍设置 `validation_status=passed`、`delivery_status=template`，公共返回仍包含完整 `outreach_pack`。这使模型调用次数无法从权威 JSONL 重建，违反 R2 的 fail-closed 证据边界。

**修改位置与方式**：

1. `StarPlan/starplan_skills/run_outcome.py:143-168`
   - `import_model_call_events()` 先清空旧事件，防止重复导入时残留上一份日志。
   - 日志缺失返回明确 warning，不再静默解释为 0 次调用。
   - 无效 JSON、读取错误继续返回 warning，由 finalize 决定终态。
2. `StarPlan/starplan_skills/runner.py:368-398`
   - 结构化入口在模型日志缺失、损坏，或已接受 Qwen 输出却没有真实 `type=model_call` 事件时，统一设置 `BLOCKED + NOT_DELIVERED`，删除 `outreach_pack.md`，公共返回 `outreach_pack=None`。
   - 纯模板运行仍允许合法的 0 次模型调用，但日志文件必须存在且可解析。
3. `StarPlan/starplan_skills/runner.py:1083-1120`
   - Chat 严格解析 JSONL；缺失、无效行和成功响应却没有 `type=model_call` 事件均进入 `artifact_errors`，随后阻断交付。
   - 阻断日志现在计入完整错误数量，避免控制台出现“0 errors”与实际原因不符。

**验证**：新增真实入口故障注入覆盖 Chat 损坏日志、Chat 无模型事件、结构化入口缺失日志和结构化入口损坏日志；均得到 `blocked/not_delivered`，最终公共文本不含目标名或科学事实。

**状态：已修复。**

### WARNING

#### W-R1：原 closure 测试的证据边界不够强

原 `model_called/model_output_accepted` 测试直接构造 `RunOutcome` 和 JSONL，未完全经过公开入口；原 Claims 篡改测试只断言 `verify_saved_registry()` 返回非空列表，不能证明最终交付被阻断。

**本轮收敛**：

- `tests/test_p0_runtime_contract_closure.py` 的 Chat mock 现在写入合法 `type=model_call` 事件，真实 finalize 会读取它。
- Claims 的 value/hash/delete/extra/invalid JSON 五类测试先生成完整活动包，再调用 `validate_delivery_contract()`；删除文件按缺失产物阻断，其余按 saved-registry violation 阻断。
- 新增 Chat/结构化模型日志证据故障矩阵。

**状态：已修复。**

#### W-R2：第二台机器或干净 CI 尚未完成

当前验证在本机独立 worktree 进行。官方离线 CI 在提升权限后通过，但普通 checkout 的 `.git/FETCH_HEAD`、远端 ref lock、部分临时目录仍出现 Windows ACL 拒绝；这不能替代另一台机器或干净 CI 的结果。

**状态：遗留，P0 交付前必须确认。**

#### W-R3：真实百炼在线 canary 未运行

本轮保持 `STARPLAN_MODEL_MODE=offline`，不消耗 API 额度；真实 provider 的限流、容量和网络抖动没有在本轮测量。当前策略是 provider 异常或证据缺失即阻断，不把 mock 结果当成在线稳定性证明。

**状态：遗留，独立在线 canary 与离线 CI 分开运行。**

#### W-R4：本机 Python/代理依赖环境路径

默认终端没有 `python`/`pytest` PATH；bundled Python 缺少项目天文依赖；本机 Python 3.13.7 需要提升权限执行。使用项目指定代理 `127.0.0.1:7897` 后，远端 fetch 可完成。

**状态：环境问题，未修改系统配置；复现命令应明确使用项目 Python 或激活虚拟环境。**

### INFO：运行证据

| 检查 | 结果 |
|---|---|
| `python -m compileall -q starplan_skills scripts tests` | PASS |
| `python scripts/validate_examples.py` | 3 passed, 0 failed |
| `python tests/layer23_validation.py` | 150 targets × 10 rounds，0 unique issues |
| `python scripts/cross_validate.py` | 12/12 在 astroplan 容差内通过 |
| 全量 `pytest -q` | **184 passed, 9 skipped, 0 failed**（39.71s） |
| `scripts/run_offline_ci.bat` | **184 passed, 0 failed；All offline checks passed**（39.4s） |
| README 三案例（offline） | M31/M42/Review 均正常终态，分别生成 16/16/20 个审计文件 |
| Chat 无 Key canary | `blocked/not_delivered`，固定无事实消息，0 次模型调用 |
| Git | `git diff --check` PASS；closure 分支相对 `origin/feature/competition-p0-runtime-contract` ahead 3（本复查提交前） |

## 二、完成状态

| 项目计划阶段 | 状态 | 说明 |
|---|---|---|
| Phase 3：Claim 证据链、fail-closed、可审计终态 | 已完成并补强 | R1 Chat 公共返回、R2 Review/模型证据、R3 Claims/runtime policy 均有真实入口门禁 |
| P0 Runtime Contract Closure | 本机验收完成，等待 W-R2 | 缺失/损坏模型证据不再交付；离线、科学交叉和全量测试通过 |
| P1 竞赛核心闭环 | 未开始 | 活动现实时间段、分众视图、下一轮输入保持冻结 |
| P2 智能体加载与实地素材 | 未开始 | 等负责人确认 P0 和首个中小学生年龄段/观测日期 |

README 的架构验收状态已同步为当前 P0 证据：`184 passed, 9 skipped`，Review 当前默认 deterministic-only，不再描述为正常路径自由生成。

## 三、实施细节与行为边界

### 1. 模型证据门禁

```text
结构化入口：
  template + 可解析 model_call_log（0 个 type=model_call） -> 可交付
  Qwen accepted + 无真实 model_call -> BLOCKED
  日志缺失/损坏 -> BLOCKED

Chat：
  成功响应 + 至少一个 type=model_call + 完整 Claim 证据 -> 继续合同校验
  成功响应但无 model_call / 日志损坏 / 日志缺失 -> BLOCKED
  provider 异常或达到轮次上限 -> BLOCKED
```

原始 Qwen 文本仍只进入审计目录；最终用户只可能看到 Claim-rendered 文档或固定无事实阻断消息。

### 2. Claims 磁盘完整性

`validate_delivery_contract()` 在读取 `claims.json` 后校验 schema、scope、Claim 集合、registry hash、source artifact hashes、derivation rules hash 和 template set hash。任一 value、hash、删除、增加或 JSON 损坏都会在交付合同阶段失败，不依赖关键词过滤。

### 3. 性能与科学边界

- 15 分钟目标采样、5 分钟暮光扫描采用数组计算；采样间隔、舍入、窗口判定和同一 AltAz frame 的月距语义保持不变。
- `cross_validate.py` 的日落、暮光、目标高度/方位、月相和可观测判定全部在容差内。
- 不删除 Claims、trace、表达计划、Manifest 或合同验证，不把性能优化换成减少证据。

## 四、剩余风险与下一阶段计划

### P0 收尾：独立环境复核

**执行内容**：

1. 在另一台电脑或全新 CI 环境安装 `requirements.txt`，按 README 和 `scripts/run_offline_ci.bat` 执行。
2. 在无 API Key、无 Astropy 用户缓存、不可达网络条件下执行三个案例，并保存每个 run 的 `run_outcome.json`、Manifest、Report、Claims、trace 和 JSONL。
3. 检查运行目录 create/write/read/delete 权限；若出现 ACL 错误，修复运行脚本的临时目录隔离，不放宽代码门禁。
4. 单独运行一次有额度上限的真实 Qwen canary；记录 provider 调用数、耗时、限流/异常和最终是否安全回退，不能把它混入离线“全通过”结论。

**验收标准**：

- 离线 CI 零失败、零真实网络模型调用；三案例进入正确终态。
- Chat/结构化模型日志五类故障仍 BLOCKED；Claims 五类篡改仍 BLOCKED。
- 第二环境不再出现无法创建或删除证据文件的权限错误。
- 在线 canary 即使失败，也只能得到确定性回退或 BLOCKED，不得把 Qwen 原文交付。

### P1 启动条件

只有 W-R2 完成并由负责人确认 P0 后，才进入：

1. Batch D：从确定性科学窗口生成 60-120 分钟现实活动时段，并用共享 Claim IDs 渲染组织者、带队者和学习者三类视图。
2. Batch E：从 Review 的 cause/evidence 生成可再次运行的 `next_activity_input.json`，第二次运行可复现且变化可追溯到 cause ID。
3. 每条新增用户可见路径同时实现 observable/not-observable/BLOCKED 三分支，并复用同一 Manifest/Report 门禁。

## 五、立即下一步

1. 将本复查的代码、测试、README 状态和本报告作为一个后续证据门禁提交推送到 `codex/p0-runtime-contract-closure`。
2. 请独立审查者先复核完整 diff 和本报告，再在第二环境执行 P0 命令集；复核前不合并 `main`，不启动 P1。
3. 复核通过后再冻结比赛演示入口（建议 `starplan.run` 为主入口，Chat 作为故障边界演示），并准备三类典型任务运行记录。

## 六、提交前清单

- [x] Chat 活动包异常、证据缺失/损坏、合同异常、轮次超限均 BLOCKED
- [x] Chat/结构化入口模型日志缺失、损坏或无真实事件均 BLOCKED
- [x] BLOCKED 公共返回不含目标名、坐标、高度角、可观测结论或 Qwen 原文
- [x] Review 默认 deterministic-only，Chat Review 显式 `use_qwen=False`
- [x] Claims value/hash/delete/extra/invalid JSON 五类篡改经过交付合同门禁并 BLOCKED
- [x] Manifest 记录 `offline_bundled_data` 和折射策略
- [x] 直接 `compute_observability()` 经过离线策略
- [x] 编译、示例、Layer2/3、全量 pytest、离线 CI、交叉校验通过
- [ ] 第二台机器或干净 CI 复跑
- [ ] 真实 Qwen provider canary（与离线验收分开）

在最后两项完成前，状态应表述为：**P0 runtime contract closure 本机验收完成，等待独立环境和在线 canary 复核；不启动 P1。**
