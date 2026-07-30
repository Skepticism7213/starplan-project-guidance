# StarPlan Loop 错误检查与阶段计划 — P0-A Claim 封存与篡改校验

日期：2026-07-30
基线：`8f9ab3e`（含独立复查报告）+ 本轮改动
范围：P0-A（封存 Claim Registry 并修复篡改校验）
性质：实现 + 验证

## 1. Error Check

### 1.1 修复内容

| 问题（来自 07-30 独立复查 C1） | 修复 | 文件 |
|---|---|---|
| `registry_hash` 每次访问动态重算，篡改后验证仍通过 | `__init__` 保存不可变源快照；`build()` 后封存 hash；`registry_hash` 只返回封存值 | `claims.py` |
| validator step 8 用动态 hash 对动态 hash | 替换为 `verify_integrity()` 调用，4 类检查 | `expression_validator.py` |
| `save()` 缺少源/规则/模板 hash | 新增 `source_artifact_hashes`、`derivation_rules_hash`、`template_set_hash`；schema 升级 1.1 | `claims.py` |

### 1.2 验证结果

| 检查 | 结果 |
|---|---|
| `test_claim_integrity.py`（10 个篡改测试） | **10 passed** |
| 完整离线套件（含新测试） | **129 passed**, 0 failed |
| 篡改反例 1：修改 claim.display_value | verify_integrity() 返回违规，validator blocked |
| 篡改反例 2：修改源 target.visual_magnitude | 检测到 source drift |
| 篡改反例 3：修改 DERIVATION_RULES 版本 | 检测到 rules changed |
| 篡改反例 4：修改模板内容 | save() 中 template_set_hash 变化 |
| 正常构建 hash 稳定性 | 两次相同输入构建 → 相同 sealed hash |
| 封存后 claim 被改 → hash 不变但 integrity 失败 | 确认 sealed hash 不动态重算 |

### 1.3 P0-A 验收标准对照

| 标准 | 判定 |
|---|---|
| 四类篡改反例全部失败关闭 | **通过** |
| 正常 Registry 重复构建 hash 稳定 | **通过** |
| 代码中不存在 `return self._compute_registry_hash()` 动态安全基线 | **通过**（property 只返回 `_sealed_registry_hash`） |

## 2. 文件变更

```
StarPlan/starplan_skills/claims.py              | 封存 hash + 源快照 + verify_integrity()
StarPlan/starplan_skills/expression_validator.py | step 8 改为 verify_integrity()
StarPlan/tests/test_claim_integrity.py          | NEW: 10 个篡改/稳定性测试
StarPlan/tests/test_claims_registry_b.py        | schema_version 1.0 → 1.1
starplan-project-guidance/archive/              | 归档 3 份旧 phase plan
```

## 3. Phase Plan

### 当前进度

| 修复步骤 | 状态 |
|---|---|
| P0-A claim-integrity | **完成** |
| P0-B unified-render-gate | 未开始 |
| P0-C runoutcome-cutover | 未开始 |
| P0-D evidence-review | 未开始 |
| P0-E chat-public-boundary | 未开始 |
| P1-A privacy-export | 未开始 |
| P1-B acceptance-ci | 未开始 |
| P1-C contract-sync | 未开始 |

### 下一步：P0-B

1. 审计 `templates.py` 所有模板附加事实，删除无 Claim 支持的断言
2. 为 schedule/equipment/safety/manual_check 建立真实 Claim ID
3. 删除 `outreach_pack.py` 月份温度预测和伪 `procedural.*` 映射
4. 统一可观测/不可观测渲染路径，生成 render_trace.json
5. 验收：两条路径均有 expression_plan.json + render_trace.json，无 Registry 外 ID

## 4. Immediate Next Actions

1. 提交 P0-A（本次）
2. 开始 P0-B：先审计 templates.py 中的事实夹带
