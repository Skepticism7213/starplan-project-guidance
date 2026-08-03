# StarPlan 错误检查与阶段计划 - P0 Runtime Contract 最终复查（2026-08-03）

日期：2026-08-03
分支：`codex/p0-runtime-contract-closure`
基线：`origin/main@5a45ddd`；复查分支 `0bd77ff`，修复后增加本地提交
范围：复查 Luna 的 P0 Runtime Contract Closure，修复真实时区边界问题；不启动 P1。

## 一、错误检查

### CRITICAL

| 编号 | 问题 | 修复位置与方式 | 验证 |
|---|---|---|---|
| C-01 | 非 `Asia/Shanghai` 的地点会计算成功但在交付合同阶段被阻断。`generate_outreach_pack()` 构建的 Claims 固定使用上海时区，而 runner 按真实地点时区重建 Claims，造成整个 Registry 不一致。 | `StarPlan/starplan_skills/outreach_pack.py:49-77` 新增显式 `timezone_name` 参数；`runner.py:236-247`、`runner.py:812-831`、`runner.py:967-976` 从地点上下文传入。Chat 的 observability executor 同时从已解析地点读取时区（`runner.py:775-783`）。 | 修复前纽约 M31：`observable / blocked / not_delivered`，53 个 Registry 错误；修复后回归用例通过，`passed / template` 且公共 `outreach_pack` 存在。 |

本轮没有遗留代码级 CRITICAL。P0 原有 R1-R3（Chat fail-closed、模型 JSONL 证据、Claims 磁盘完整性和离线 runtime policy）在本轮回归中仍通过。

### WARNING

| 编号 | 项目 | 当前状态、影响和具体后续 |
|---|---|---|
| W-01 | 本机测试解释器环境 | 当前系统没有项目 Python/pytest；临时安装依赖后，全量 pytest 为 `180 passed, 4 failed`，4 个失败均是测试子进程把 `PYTHONPATH` 覆盖为源码目录，找不到临时目录中的 `yaml`，不是业务断言失败。使用完整依赖路径手工运行 direct observability、M31/M42 后均通过。交付前必须在真实 venv 或干净 CI 运行，不要把临时 `PYTHONPATH` 方案写入项目。 |
| W-02 | 第二台电脑、干净 CI 和 Windows ACL | 未完成独立机器复跑；当前 worktree 的临时目录曾出现权限拒绝。需要验证证据目录可创建、读取、删除，不能通过放宽 fail-closed 来绕过。 |
| W-03 | 真实百炼 Qwen canary | 本轮严格 `STARPLAN_MODEL_MODE=offline`，未消耗额度；provider 容量、限流和延迟仍未实测。在线失败必须保持确定性回退或 BLOCKED，不得交付原始 Qwen 文本。 |
| W-04 | `RenderedDocument` 的序列化 `text_hash` | `RenderedDocument.from_dict()` 当前重新从 `final_text` 计算属性，未独立比较 JSON 中保存的 `text_hash` 字段。篡改 `final_text` 仍会被 trace/Markdown 双向校验拦截，但单独篡改该字段不会被发现，属于证据强度缺口。P1 前应让 `from_dict()` 或 validator 显式比较保存值，并增加单字段篡改测试。 |

### INFO：静态与运行时结果

| 检查 | 结果 |
|---|---|
| `python -m compileall -q starplan_skills scripts tests` | PASS |
| `python scripts/validate_examples.py` | 3 passed, 0 failed |
| `python tests/layer23_validation.py` | 150 targets × 10 rounds，0 unique issues |
| `python scripts/cross_validate.py` | 12/12 在 astroplan 容差内通过 |
| P0 closure 定向测试（排除临时依赖子进程项） | 21 passed, 1 deselected |
| 全量业务测试（排除 4 个同一环境原因的子进程项和 Qwen integration） | 181 passed, 4 deselected |
| 离线 M31/M42 正常入口 | 均在约 3 秒内完成，终态和证据文件完整 |
| 纽约 M31 时区回归 | 修复后 `validation_status=passed`、`delivery_status=template` |
| `git diff --check` | PASS；仅有已有的 LF/CRLF 提示 |
| 远端基线 | 通过 `git -c http.proxy=http://127.0.0.1:7897 fetch origin` 验证，`origin/main...HEAD = 0 11`（修复提交前） |

## 二、完成状态

| 项目计划阶段 | 状态 | 说明 |
|---|---|---|
| Phase 3：Claim 证据链、fail-closed、可审计终态 | 已完成并回归 | R1/R2/R3 以及非默认时区交付边界均有代码和测试 |
| P0 Runtime Contract Closure | 本地验收完成，等待 W-01/W-02/W-03 | 代码级 CRITICAL 为 0；独立环境和在线 canary 仍是交付前门禁 |
| P1：现实活动时段、分众输出、下一轮输入 | 未开始 | 保持冻结，避免在演示前扩大变更面 |
| P2：智能体加载、实地观测素材、前端/视频 | 未开始 | 等 P0 负责人确认和素材冻结 |

## 三、为什么这次问题必须修

项目公开声明支持 IANA 时区，`observability_plan` 也已经按地点时区计算暮光和本地时间。若 Claims 仍固定写上海时区，系统会出现“科学计算成功、证据合同失败、用户拿不到结果”的断裂，且错误只在非中国地点出现，常规济南案例无法覆盖。因此这里不是为测试而测试，而是修复输入契约和交付契约不一致。

修复保持最小范围：时区由地点上下文单向传递给 Claims builder；没有改变天文公式、采样间隔、模板、模型权限或公共 fail-closed 规则。

## 四、下一阶段计划

### P0 收尾：独立环境与在线边界

1. 在干净 venv/第二台电脑安装 `StarPlan/requirements.txt`，运行 compileall、示例校验、Layer 2/3、cross validation、全量 pytest 和 `scripts/run_offline_ci.bat`。
2. 在无 API Key、fresh Astropy cache、不可达网络下运行 M31、M42、Review；确认每个 run 都有 `run_outcome.json`、Manifest、Report、Claims、trace、JSONL，且 ACL 可读写删除。
3. 使用额度上限明确的真实 Qwen canary，记录模型调用数、耗时、限流和失败终态；不要把在线 canary 结果混入离线通过结论。
4. 在 `rendering.py` 为保存的 `text_hash` 增加显式校验，并加入“只改 JSON hash 字段必须 BLOCKED”的交付合同测试。

验收标准：独立环境离线 CI 零失败；三案例进入正确终态；非默认时区案例通过；模型证据和 Claims 篡改仍 fail-closed；hash 字段篡改被阻断。

### P1：竞赛核心闭环（负责人确认后启动）

1. Batch D：从确定性窗口生成 60-120 分钟现实活动时段，组织者/带队者/学习者三类视图共享同一 Claim IDs；M31 不再默认通宵。
2. Batch E：从 Review 的 cause/evidence 生成可再次运行的 `next_activity_input.json`，第二次运行的变化可追溯到 cause ID。
3. 每个新增用户可见路径同时实现 observable、not-observable、BLOCKED 三分支，并复用同一 Manifest/Report 门禁。

## 五、立即下一步

1. 提交并推送本次时区修复和本报告到 `codex/p0-runtime-contract-closure`。
2. 由独立环境执行本报告 P0 命令集；在 W-01/W-02/W-03 未关闭前不启动 P1。
3. 负责人确认 P0 后冻结演示入口、三个典型任务和首个中小学生年龄段，再开始 Batch D/E。

## 六、变更清单

| 文件 | 变化 |
|---|---|
| `StarPlan/starplan_skills/outreach_pack.py` | 接受并使用地点 `timezone_name` 构建 Claims |
| `StarPlan/starplan_skills/runner.py` | 结构化/Chat/强制补生成统一传递时区；Chat observability 使用已解析地点时区 |
| `StarPlan/tests/test_p0_runtime_contract_closure.py` | 增加非默认 IANA 时区交付回归用例 |
| `starplan-project-guidance/starplan-error-check-and-phase-plan-2026-08-03-p0-final-review.md` | 本轮错误检查、完成状态和后续阶段计划 |
