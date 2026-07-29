# StarPlan Loop 错误检查与阶段计划 — P1 完成小结

日期：2026-07-29
基线：`357a52c`（P0 提交）+ 本轮未暂存改动
范围：P1（校准科学规则和证据完整性）全部 4 项
性质：实现 + 验证；未提交（待用户确认后 commit）

## 1. P1 完成清单

| 子项 | 要求 | 实现 | 涉及文件 |
|---|---|---|---|
| P1-1 | 肉眼/双筒/新手/设备匹配规则增加前提、目标类型、不足则待确认 | 深空天体角径 < 10' 时标记 UNCONFIRMED；display_value 加注条件限定；derivation_rule 标注 scope/caveat/missing；新手阈值从 5' 提升到 10' | `claims.py` |
| P1-2 | 哈希重新计算，篡改 → blocked | 新增 `registry_hash` 属性；`_compute_registry_hash` 改用 `mode="json"` 与 validator 一致；validator step 8 重算 registry hash 并比对；全零占位哈希 → error；长度异常从 warning 升级为 error | `claims.py`, `expression_validator.py` |
| P1-3 | 去时区硬编码；折射策略写入 Manifest；ExpressionPlan extra=forbid；验证 section/tone/connector | `AllowedClaimsBuilder` 接受 `timezone_name` 参数；`outreach_pack.py` 传入时区；`run_outcome.py` 写入 refraction_policy；`SelectedClaim`/`ExpressionPlan` 均设 `extra="forbid"`；新增 section_order/tone/connector_ids 字段验证器（模块级常量） | `claims.py`, `outreach_pack.py`, `run_outcome.py`, `schemas.py` |
| P1-4 | 同步 skills.yaml、README、示例和工具 Schema | skills.yaml 升级 v0.2.0：outreach_pack 输入改为 Claim Registry、observation_review 增加 log_path/artifacts/失败回退、orchestrator 增加完整产物清单和 limitations；README 新增证据链架构说明、MVP 限制、更新产物表和项目结构 | `skills.yaml`, `README.md` |

## 2. Error Check

### 2.1 静态检查

| 检查 | 结果 |
|---|---|
| `compileall starplan_skills scripts tests` | PASS（0 errors） |
| `validate_examples.py` | 3/3 PASS |

### 2.2 运行检查

| 检查 | 结果 | 备注 |
|---|---|---|
| 离线 pytest（排除 confidence + 在线） | **90 passed**, 22 deselected, 1 warning | warning 为已有的 class-scoped fixture 弃用 |
| confidence 算法脚本 | **150/150** passed | 单独运行 |
| 案例运行（测试中触发） | M31 可观测 / M42 不可观测 / confirmed 路径均正常 | fail-closed 误触发已修复 |

### 2.3 本轮修复的问题

| 问题 | 原因 | 修复 |
|---|---|---|
| `ExpressionPlan 验证失败: argument of type 'ModelPrivateAttr' is not iterable` | Pydantic v2 将 `_` 前缀类属性视为 ModelPrivateAttr，validator 中 `cls._VALID_*` 不可迭代 | 改为模块级常量 `_VALID_SECTIONS` / `_VALID_TONES` / `_VALID_CONNECTORS` |
| `registry_hash` 属性不存在 | validator 引用 `claims_builder.registry_hash` 但 builder 无此公开属性 | 新增 `@property registry_hash` |
| 哈希计算不一致 | builder 用 `model_dump()`，validator 用 `model_dump(mode="json")` | 统一为 `mode="json", default=str` |

### 2.4 残留问题（不阻塞 P1，归入 P2）

| 严重度 | 位置 | 问题 |
|---|---|---|
| WARNING | `tests/test_moon_separation_c1.py` | class-scoped fixture 弃用警告（PytestRemovedIn10） |
| WARNING | `tests/layer23_validation.py` | SIMBAD 快照未入库，Checks 7/11 跳过；M24/M52 精度警告 |
| INFO | `qwen_client.py` TOOL_DEFINITIONS | 工具描述仍写"事实卡"，未提及 Claim Registry（功能不受影响，属文档同步） |
| INFO | `claims.py` 派生规则 | 设备匹配规则（equipment → 目标可达性）尚未实现独立 Claim，当前仅影响模板选择 |

## 3. Phase Status After P1

| 阶段 | 判断 | 变化 |
|---|---|---|
| P0：恢复可信输出边界 | 已完成 | 357a52c |
| P1：校准科学规则和证据完整性 | **已完成** | 本轮 |
| P2：验收和工程卫生 | 未开始 | — |

## 4. P2 前置提醒

P2 的 4 项（Layer 3 端到端用例、SIMBAD 快照、测试工程修复、脱敏/保留期）均不依赖 P1 之后的额外前置。建议优先顺序：

1. 先修 test_confidence_algorithm.py 全局 stdout 替换 + class-scoped fixture → 使默认 pytest 可直接运行。
2. 补 Layer 3 强月光 / 工具异常 / 纯文字幻觉端到端用例。
3. SIMBAD 快照入库或升级为阻断。
4. 脱敏/保留期策略（演示前完成即可）。

## 5. 文件变更摘要

```
AGENTS.md                       | 12 ++  (LOCAL-ONLY, 不提交)
StarPlan/README.md              | 41 ++--
StarPlan/skills.yaml            | 59 ++--
StarPlan/starplan_skills/claims.py           | 70 ++--
StarPlan/starplan_skills/expression_validator.py | 45 ++-
StarPlan/starplan_skills/outreach_pack.py    |  1 +
StarPlan/starplan_skills/run_outcome.py      |  4 +-
StarPlan/starplan_skills/schemas.py          | 41 ++
```

提交时应排除 `AGENTS.md`（LOCAL-ONLY 章节）和 `tests/confidence_test_results.json`（运行产物）。
