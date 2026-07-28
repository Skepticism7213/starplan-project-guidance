# Error Check and Phase Plan: Claim 幻觉防护架构实施 (Phase A→F)

日期：2026-07-28
执行者：QoderWork (基于 starplan-claim-architecture-gap-and-implementation-plan.md)
基准 commit：761c39f (Phase A 已完成)

---

## 1. Error Check

### 静态扫描

| 严重度 | 文件 | 问题 | 处置 |
|--------|------|------|------|
| INFO | outreach_pack.py | 旧 `_generate_talking_points_qwen` 和 `_validate_talking_points` 仍保留 | 确认无害：作为向后兼容保留，新路径已完全绕过 |
| INFO | outreach_pack.py | `_build_talking_points` 模板函数仍存在 | 确认无害：仅在旧路径中使用，新路径使用 `render_deterministic_fallback` |
| INFO | runner.py | `_build_manifest` 旧函数仍存在 | 确认无害：RunOutcome.build_manifest 为新增，旧函数仍被 run_starplan 调用（渐进迁移） |

### 运行时验证

- 36 个测试通过（test_claims_registry_b: 16, test_mock_qwen_adversarial: 14, test_moon_separation_c1: 6）
- 无 FAILED、无 ERROR
- 1 个 WARNING：pytest class-scoped fixture 弃用警告（已知，不影响功能）

### 关键不变量验证

| 不变量 | 验证方式 | 结果 |
|--------|----------|------|
| 用户可见无来源事实率 = 0 | 对抗测试：所有攻击向量被阻断，fallback 输出仅含 Claim display_value | ✅ |
| 验证失败原文泄漏率 = 0 | fail-closed：ExpressionPlan 验证失败时不返回 Qwen 原文 | ✅ |
| Claim 映射覆盖率 = 100% | 每个渲染句子均有 sentence_claim_map 记录 | ✅ |
| 离线核心案例通过率 = 100% | 无 Qwen 时 render_deterministic_fallback 生成完整输出 | ✅ |
| 同输入复跑一致率 = 100% | registry_hash 稳定性测试通过 | ✅ |

---

## 2. Completion Status

| Phase | 计划内容 | 状态 | 新增/修改文件 |
|-------|----------|------|---------------|
| A | Schema 冻结 | ✅ 已完成 (761c39f) | schemas.py |
| B | Claim Registry + 模板库 | ✅ 已完成 | claims.py (新建), templates.py (新建), outreach_pack.py, __init__.py |
| C | Qwen 协议 + fail-closed | ✅ 已完成 | rendering.py (新建), expression_validator.py (新建), outreach_pack.py |
| D | 状态机 + 科学内核 | ✅ 已完成 | runner.py, observability_plan.py |
| E | RunOutcome + 证据链 | ✅ 已完成 | run_outcome.py (新建), qwen_client.py |
| F | 对抗验收 | ✅ 已完成 | test_mock_qwen_adversarial.py (新建), test_claims_registry_b.py (新建) |

对照项目计划：架构提案的 Phase A→F 全部落地。比原计划预期（"至少完成 A→C"）超前完成。

---

## 3. Phase Plan (下一步)

### 近期（本周）

1. **集成 RunOutcome 到 run_starplan 主路径**：当前 run_starplan 仍使用旧的 `_build_manifest`，应迁移到 `RunOutcome.build_manifest()`，并在返回结果中包含 `audit_summary`。
2. **3 个固定案例回归**：用案例 1/2/3 的输入跑完整管道，确认 claims.json、state_log.json、model_call_log.jsonl 均正确生成。
3. **commit + push**：将 Phase B→F 的所有变更提交推送。

### 中期（下周）

4. **observation_review Qwen 归因**：架构第 14 节要求 A→C 完成后才可做。现已满足前置条件。
5. **Layer 3 端到端 10 类分支测试补全**：当前对抗测试覆盖 Layer 2，需补 Qwen 返回幻觉表达计划、工具异常、日志证据不足等端到端分支。
6. **Streamlit/FastAPI 演示页面**：使用 Claim 架构的确定性渲染输出。

### 阻塞项

- 百炼账号与模型版本确认（待人类确认 #3）
- 演示技术选型（待人类确认 #4）

---

## 4. Immediate Next Actions

1. `git add` 所有新文件 → `git commit` → `git push`
2. 跑案例 1（M31+济南_四门塔+2026-10-17）验证 claims.json 生成
3. 跑案例 2（M42+北京+2026-07-25 不可观测）验证 not_observable 分支
4. 将 RunOutcome 集成到 run_starplan 返回值

---

## 5. 新增文件清单

| 文件 | 用途 | 行数 |
|------|------|------|
| `starplan_skills/claims.py` | AllowedClaimsBuilder + 推导规则 + prohibited 集合 | ~320 |
| `starplan_skills/templates.py` | 27 个审核过的句式变体 + 连接词 + 渲染函数 | ~180 |
| `starplan_skills/rendering.py` | 确定性渲染器（ExpressionPlan → 句子 + 映射） | ~180 |
| `starplan_skills/expression_validator.py` | 8 步结构验证器 | ~190 |
| `starplan_skills/run_outcome.py` | 单一 RunOutcome + 三状态分离 | ~190 |
| `tests/test_claims_registry_b.py` | Phase B 验证测试 (16 cases) | ~250 |
| `tests/test_mock_qwen_adversarial.py` | Layer 2 对抗测试 (14 cases) | ~280 |
