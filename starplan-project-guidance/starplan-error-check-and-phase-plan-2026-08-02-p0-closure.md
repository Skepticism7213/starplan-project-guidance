# StarPlan 错误检查与阶段计划 — P0 关闭可见阻断（2026-08-02）

日期：2026-08-02

分支：`feature/competition-p0-runtime-contract`

基线：`5a45ddd`（origin/main）→ HEAD `cea12e8`（5 commits）

## 一、错误检查

### CRITICAL

| 编号 | 问题 | 修复 | 验证 |
|---|---|---|---|
| C-01 | 正常入口 IERS/leap-second 联网等待（M42 超时 45s，复盘超时 90s） | 新增 `astro_runtime.py`，runner/cross_validate 入口调用 `configure_astronomy_runtime()` | `test_runtime_offline_policy.py` 3 条通过；README 三案例空缓存+禁网 30s 内完成 |
| C-02 | BLOCKED 时结构化入口仍返回 `outreach.model_dump()` | `run_starplan()` 返回由 `outcome.validation_status` 决定；BLOCKED → `outreach_pack=None` | `test_failclosed_public_return_b.py::test_blocked_returns_none_outreach_pack` 通过 |
| C-03 | Chat `public_output_validation` 仅检查 untraceable 数字，不从 RunOutcome 派生 | 改为 `chat_outcome.validation_status.value`；异常/缺文件 → BLOCKED | 逻辑验证 + 现有 19 条 chat 测试通过 |
| C-04 | Review 默认 `use_qwen=True`，案例三等待真实模型 | runner 显式传 `use_qwen=False`；`qwen_status=disabled_pending_id_only` 写入 review_trace | 案例三不再等待 Qwen；`test_mock_qwen_fabrication_does_not_alter_result` 通过 |

### WARNING

| 编号 | 问题 | 修复 | 验证 |
|---|---|---|---|
| W-01 | 版本漂移：skills.yaml=0.2.0, __init__=0.4.0 | 统一为 0.5.0 | `rg "0\.[24]\.0"` 在 skills.yaml/__init__/README 中无残留 |
| W-02 | templates.py "今晚" 对未来日期不正确 | `target_name_v1` 改为 "本次活动我们要观测的是" | 全部测试期望同步更新；`rg 今晚` 在 templates.py 用户可见模板中无残留 |
| W-03 | 案例三 observer_notes "迟到30分钟" 与结构化时间差冲突 | 改为 "晚到"（定性），结构化差值为唯一数字来源 | `validate_examples.py` 3/3 通过 |
| W-04 | 偏差类型显示英文（time/environment/equipment） | 增加中文映射：时间/环境/设备 | review_report.md 输出验证 |
| W-05 | 修订表表头每行重复 | 表头移出 for 循环 | review_report.md 输出验证 |

### INFO

| 项目 | 状态 |
|---|---|
| `python -m compileall -q starplan_skills scripts tests` | PASS |
| `python scripts/validate_examples.py` | 3 passed, 0 failed |
| `python tests/layer23_validation.py` | 0 unique issues, 10 rounds consistent |
| `tests/test_runtime_offline_policy.py` | 3 passed (31s) |
| `tests/test_observability_edge_cases.py` | 5 passed |
| `tests/test_moon_separation_c1.py` | 6 passed |
| `tests/test_mock_qwen_adversarial.py` | 14 passed |
| `tests/test_chat_hallucination_c4.py` | 19 passed |
| `tests/test_delivery_contract_gate.py` | 10 passed |
| `tests/test_failclosed_public_return_b.py` | 5 passed |
| 完整 pytest（排除 8 条子进程测试） | **164 passed, 0 failed** (566s) |
| 子进程测试（offline + failclosed） | 8 passed (单独验证) |
| README 案例一 M31 | OK, 34.5s |
| README 案例二 M42 | OK, 5.8s |
| README 案例三 Review | OK, 31.7s |
| `git diff --check` | PASS（仅 LF/CRLF 提示） |

## 二、完成状态

| 项目计划阶段 | 本轮变化 |
|---|---|
| P0：关闭可见阻断 | **已完成**。离线运行、BLOCKED 公共返回、Review 安全降级、文案/版本一致性全部关闭 |
| P1：竞赛核心闭环 | 未开始。等待负责人审查 P0 后确认进入 |
| P2-P5 | 未开始 |

## 三、阶段计划

### P1（待负责人确认后执行）

1. **Batch D：现实活动时段 + 三类分众输出**
   - 新增 `ActivityPreferences` + `RecommendedActivitySlot`
   - 确定性 `activity_slot_policy_v1` 从科学窗口选择 60-120 分钟活动时段
   - 同源 Claims 生成 organizer/facilitator/learner 三种 view
   - 验收：M31 不再通宵；三 view 事实 Claim IDs 一致

2. **Batch E：可执行下一轮输入 + before/after**
   - `next_activity_input.json` 符合 StarPlanInput Schema
   - 第二次 runner 正常运行且不再触发 Review
   - 变化可追溯到 Evidence/Cause ID

### 阻塞项

- P2 智能体交付形态需负责人指定 Qwen/百炼产品载体
- 首个中小学生年龄段需确认以冻结分众模板
- 八月中旬实地观测安排待确认

## 四、立即下一步

1. 负责人审查本分支 5 个 commit 的完整 diff
2. 确认合并到 main 或要求修改
3. 确认后回复"继续 P1"启动 Batch D/E
4. 指定 P2 智能体加载平台

## 五、文件变更清单

| Batch | 文件 | 变化 |
|---|---|---|
| A | `starplan_skills/astro_runtime.py` | 新增：幂等离线 IERS 配置 |
| A | `starplan_skills/runner.py` | 入口调用 configure_astronomy_runtime() |
| A | `scripts/cross_validate.py` | 同上 |
| A | `tests/test_runtime_offline_policy.py` | 新增：3 条子进程离线测试 |
| B | `starplan_skills/runner.py` | BLOCKED 返回 None；Chat 终态派生；Review use_qwen=False |
| B | `starplan_skills/observation_review.py` | qwen_status=disabled_pending_id_only |
| B | `tests/test_failclosed_public_return_b.py` | 新增：5 条 fail-closed 测试 |
| C | `starplan_skills/__init__.py` | 版本 → 0.5.0 |
| C | `skills.yaml` | 版本 → 0.5.0 |
| C | `starplan_skills/templates.py` | "今晚" → "本次活动" |
| C | `starplan_skills/observation_review.py` | 偏差类型中文 + 表头修复 |
| C | `examples/case_03_observation_review.json` | 删除冲突数字 |
| C | `README.md` | 版本引用更新 |
| C | 4 个测试文件 | 模板期望文本同步 |

## 六、遗留风险

1. 完整 pytest 在本托管环境未触发 ACL PermissionError（本轮未复现），但提交前仍建议在第二台电脑重跑确认。
2. 案例一/三耗时 30-35s，主要瓶颈是 Qwen API 调用（outreach_pack use_qwen=True）；离线模式下会更快。
3. Review ID-only 协议（P1）完成前，Qwen Review helper 保留但不调用；若 P1 延期，当前确定性 Review 已可安全用于比赛。
4. `test_confidence_algorithm.py` 无 test_ 函数（python 直接执行），不在 pytest 收集范围内，属已知设计。
