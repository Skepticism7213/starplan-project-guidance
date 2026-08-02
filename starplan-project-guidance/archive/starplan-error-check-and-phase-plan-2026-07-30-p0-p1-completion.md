# StarPlan Loop 错误检查与阶段计划 — P0-A ~ P1-C 完整修复轮

日期：2026-07-30
基线：`8f9ab3e`（含独立复查报告）→ `9ecb6e0`（P1-C 完成）
范围：07-30 独立复查报告规定的全部 8 步修复（P0-A ~ P1-C）
性质：实现 + 验证 + 自查复盘

## 1. Error Check

### 1.1 修复清单

| 步骤 | Commit | 修复内容 | 涉及文件 |
|---|---|---|---|
| P0-A | `8dca1e3` | 封存 hash（build 后冻结）；verify_integrity() 4 类检查；expression_validator step 8 改为调用 verify_integrity()；10 个篡改测试 | `claims.py`, `expression_validator.py`, `test_claim_integrity.py` |
| P0-B | `d99c955` + `6682920` | 6 处模板事实夹带清理；ClaimType.PROCEDURAL；_build_procedural_claims()（schedule/safety/equipment/manual_check/blocking）；删除温度预测；删除伪 procedural.* 映射；不可观测路径生成 sentence_claim_map + expression_plan；可观测路径补 expression_plan；schedule "完全变暗" 删除 | `templates.py`, `schemas.py`, `claims.py`, `outreach_pack.py` |
| P0-C | `49ba267` | RunOutcome.__init__ 参数 Optional（入口创建）；BusinessStatus.PENDING / DeliveryStatus.NOT_DELIVERED；删除 ValidationStatus.TARGET_NOT_OBSERVABLE 及覆盖逻辑；runner 入口创建 outcome + 歧义/工具异常持久化；_persist_outcome helper | `run_outcome.py`, `runner.py` |
| P0-D | `5a4a454` | 删除 "云量>50%" 阈值；设备原因 evidence_based→possible；删除 "提前30分钟" 和 "错过高高度窗口"；undetermined 不升级；延迟阈值注册为 review.delay_significance@v1；生成 review_trace.json | `observation_review.py` |
| P0-E | `6293a3b` | Chat 公共返回删除 blocked_content/messages/tool_call_log；新增 model_text_accepted_for_delivery=False + public_output_validation | `runner.py` |
| P1-A | `500e3d8` | sanitize_run_for_export 字段级脱敏（递归删除 observer_notes 等）；非空目录拒绝；verify_export_sanitized() 递归扫描 | `privacy.py` |
| P1-B | `ccf2bc8` | STARPLAN_MODEL_MODE=offline tripwire（3 个 call 函数顶部 _assert_online）；run_offline_ci.bat 强制离线 + 专用 temp；compute_observability 异常持久化 RunOutcome；测试收紧（删除 >=5 阈值、procedural.* 豁免、宽松异常接受） | `qwen_client.py`, `runner.py`, `run_offline_ci.bat`, `test_layer3_e2e.py` |
| P1-C | `9ecb6e0` | qwen_client "事实卡"→"Claim Registry"；README 新增架构验收状态表 + 诚实残留标注 | `qwen_client.py`, `README.md` |

### 1.2 验证结果

| 检查 | 结果 |
|---|---|
| compileall | PASS |
| validate_examples | 3/3 |
| Layer 1（150 × 10 轮） | 0 issues |
| Layer 2/3（含 SIMBAD） | 0 issues |
| 离线 pytest（P0-B 后） | 129 passed, 0 failed |
| P0-A 篡改脚本验证 | 4/4 blocked + hash 稳定 |
| P0-B 禁止短语扫描 | 0 命中（修复后） |
| P0-B Registry 外 ID | 0（全部在 claims.json） |
| P0-C 歧义 RunOutcome | needs_confirmation / passed / not_delivered |
| P0-C 不可观测正交性 | not_observable / passed（manifest 无覆盖） |
| P0-E 公共返回 | 无 blocked_content / messages |
| P1-A 非空目录拒绝 | ValueError 正确抛出 |
| P1-A verify_export_sanitized | 0 violations |
| P1-B 工具异常 RunOutcome | tool_error / not_delivered |

### 1.3 自查复盘发现的遗漏（已修复）

| 问题 | 发现方式 | 修复 |
|---|---|---|
| 可观测路径缺 expression_plan.json | P0 复盘脚本 | `6682920` 补齐 |
| schedule 残留 "完全变暗" | P0 复盘禁止短语扫描 | `6682920` 删除 |
| compute_observability 异常未持久化 RunOutcome | P1-B 测试失败 | `ccf2bc8` 补 try/except |

## 2. Completion Status

| 独立复查要求 | 判定 | 说明 |
|---|---|---|
| P0-A 封存 hash + 四类篡改 blocked | **完成** | 脚本验证通过 |
| P0-B 统一渲染门禁 + 无 Registry 外 ID | **完成** | 两条路径均有 trace，0 外部 ID，0 禁止短语 |
| P0-C RunOutcome 入口 + 失败终态 | **完成** | 歧义/工具异常均产生 run_outcome.json |
| P0-D 复盘规则修复 + trace | **完成** | review_trace.json 生成，无 50% 阈值 |
| P0-E Chat 公共边界 | **完成** | 返回不含模型原文 |
| P1-A 字段级隐私导出 | **完成** | 递归脱敏 + 非空拒绝 + verifier |
| P1-B 离线 CI + 测试收紧 | **完成** | tripwire + 精确断言 |
| P1-C 文档同步 | **完成** | README 验收状态表 + 诚实残留 |

## 3. Phase Plan

### 尚未闭合的项目（下一轮优先级）

| 优先级 | 项目 | 验收标准 |
|---|---|---|
| HIGH | render_trace.json 逐句 hash trace | 每个事实句有 rendered_text_hash + claim_ids + source_refs |
| HIGH | 运行时覆盖门禁（validate_render_coverage） | 删除 Claim 后渲染自动 blocked |
| MEDIUM | 复盘 Qwen ID selection 协议 | ReviewExpressionPlan extra=forbid，Qwen 只选 ID |
| MEDIUM | 六终态参数化 E2E 矩阵 | observable/not_observable/needs_confirmation/data_insufficient/tool_error/validation_blocked 逐个断言 |
| LOW | 离线 CI Windows temp 权限完整修复 | 干净环境 run_offline_ci.bat 零 error |

### 建议下一步

1. 实现 `render_trace.json` 和 `validate_render_coverage()`，关闭"100% 覆盖"验收标准。
2. 在 outreach_pack 渲染前调用 coverage gate，缺 Claim 即 blocked。
3. 补齐六终态参数化测试，作为第 5 周演示入口的前置门槛。

## 4. Immediate Next Actions

1. 实现 rendering.py 中的 `validate_render_coverage(render_result, registry)` 门禁。
2. 在 outreach_pack 两条路径的渲染后调用门禁，失败则 validation=blocked。
3. 写出 render_trace.json（每句含 claim_ids + variant_id + rendered_text_hash）。
4. 补六终态参数化 E2E，跑通后更新 README 验收状态表。
