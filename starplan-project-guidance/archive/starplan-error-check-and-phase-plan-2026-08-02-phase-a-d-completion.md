# StarPlan 错误检查与阶段计划 — Phase A-D 审计响应（2026-08-02）

## 1. 错误检查

### 审查基线

- 起始提交：`0252a35`（Merge teammate science fixes into Claim architecture）
- 权威审计报告：`starplan-error-check-and-phase-plan-2026-08-01-post-merge-independent-audit.md`
- 审计结论：6 CRITICAL + 4 WARNING 全部为真实缺陷，逐条代码验证确认

### 修复结果

| 编号 | 严重度 | 描述 | 状态 | 修复方式 |
|---|---|---|---|---|
| C-01 | CRITICAL | 最终 Markdown 有 19 条直接拼接事实绕过 Claim | 已修复 | RenderedDocument + serialize_document_md 唯一出口 |
| C-02 | CRITICAL | 运行时门禁 fail-open | 已修复 | validate_delivery_contract 7 步门禁，失败→BLOCKED |
| C-03 | CRITICAL | Chat 第二条无 Claim 事实路径 | 已修复 | 强制 generate_outreach_pack + 删除 _build_deterministic_summary 公共路径 |
| C-04 | CRITICAL | 复盘 Qwen 自由写原因 + next(...) 误标 | 已修复 | 稳定 ID + 显式 source_cause_ids + 结构化异常审计 |
| C-05 | CRITICAL | 无天气数据时生成具体气温 | 已修复 | 改为非事实化操作指令 |
| C-06 | CRITICAL | 极昼原因错归 moonlight | 已修复 | no_astronomical_night 原因码 + 优先级链 |
| W-01 | WARNING | 模型调用计数不真实 | 已修复 | 从 model_call_log.jsonl 聚合 |
| W-02 | WARNING | 测试契约漂移 | 已修复 | tools_called 替代 tool_call_log + 产物断言 |
| W-03 | WARNING | trace section 顺序不稳定 | 已修复 | sections_ordered 稳定排序 |
| W-04 | WARNING | 模型异常静默吞掉 | 已修复 | 结构化 model_error 审计事件 + qwen_status 四态 |

### 运行时验证

| 验证项 | 结果 |
|---|---|
| Python 编译检查（全部模块） | PASS |
| 离线 pytest（排除真实 Qwen） | 153 passed, 0 failed |
| 故障注入 7 条（缺 trace/坏 JSON/伪 Claim/删 Claim/错 variant/改 hash/插入额外事实） | 全部 BLOCKED |
| 双向覆盖（M31 可观测 + M42 不可观测） | 100% 覆盖 |
| 极昼 edge case（M31, lat=70, 2026-06-21） | reason=no_astronomical_night |
| 纬度受限 edge case（M70, 济南） | reason=latitude, alternative_location |
| 温度事实检查 | 无天气 Claim 时温度数值为 0 |

### 已知遗留（INFO 级）

- ~~`test_warning2_latitude_limited_gives_location_not_date` 偶发失败~~ → 已确认根因为 astropy IERS 缓存过期 + 无网络 → ValueError 假失败。已新增 `conftest.py` 设置 `iers.conf.auto_download = False`，修复后 5 条 edge case 21s 稳定通过
- 复盘 Qwen 完整 ID-only 协议未实现（当前仍有数字验证 + 分类约束作为防线）
- review report 未使用 RenderedDocument 双向覆盖门禁

## 2. 完成状态

| 工作包 | 项目计划对应 | 状态 | 说明 |
|---|---|---|---|
| Phase A | 第 3 周：100% 映射 + fail-closed | 已完成 | RenderedDocument + validate_delivery_contract |
| Phase B | 第 3 周：Chat 统一出口 | 已完成 | 强制 Claim 渲染 + model-call 聚合 |
| Phase C | 第 4 周：Evidence Claims | 核心已完成 | 稳定 ID + 精确因果链 + 异常审计 |
| Phase D | 科学边界 | 已完成 | no_astronomical_night + 温度非事实化 |
| Phase E | 文档/门禁 | 本次 | README 更新 + 本报告 |

## 3. 阶段计划

### 下周工作

1. **复盘 ID-only 协议**（C-04 完整实现）：定义候选原因模板库 + 建议模板库，Qwen 只返回 ID + 分类
2. **review RenderedDocument**：复盘报告也使用双向覆盖门禁
3. **150 目标置信度测试**：Layer 1/2/3 数据验证 + astroplan 12 项交叉校验
4. **真实百炼 canary**：更新后的 test_qwen_integration 4 条 + 结构化 M31 案例

### 验收标准

- 离线全量 153+ passed 稳定（conftest.py 已消除 IERS 网络依赖）
- 复盘 Mock Qwen 注入无数字虚假因果被阻断
- 真实 canary 不再因旧字段失败
- 完成报告中每个数字可由命令复现

### 风险

- 复盘 ID-only 协议需要设计模板库，体量较大
- 真实模型行为波动可能影响 canary 稳定性

## 4. 立即下一步

1. 确认 latitude test 失败原因（重跑 3 次或读取详细 traceback）
2. 全量回归确认后 commit + push（Phase A+B+C+D+E 一次提交）
3. 更新 `skills.yaml` 版本号为 v0.3.0
4. 开始复盘 ID-only 协议设计

## 5. 修改文件清单

| 文件 | Phase | 改动类型 |
|---|---|---|
| `starplan_skills/rendering.py` | A | 新增 RenderedBlock/RenderedDocument/render_document/serialize_document_md |
| `starplan_skills/claims.py` | A+D | 新增 meta Claims + variant 扩展 + 温度非事实化 + no_astronomical_night 文案 |
| `starplan_skills/templates.py` | A | 新增 meta_passthrough_v1 + recommended_window variants |
| `starplan_skills/outreach_pack.py` | A | 删除旧 Markdown writer，改用 RenderedDocument |
| `starplan_skills/expression_validator.py` | A | 新增 validate_delivery_contract + _extract_atomic_facts |
| `starplan_skills/runner.py` | A+B | finalize BLOCKED 语义 + Chat 强制 Claim 渲染 + model-call 聚合 |
| `starplan_skills/observation_review.py` | C | 稳定 ID + source_cause_ids + 结构化异常 + trace 2.0 |
| `starplan_skills/schemas.py` | C | Deviation/CauseEntry/RevisedPlanDiff 新增 ID 字段 |
| `starplan_skills/observability_plan.py` | D | no_astronomical_night 原因码 + 优先级修复 |
| `tests/test_delivery_contract_gate.py` | A | 新增 10 条（7 故障注入 + 2 双向覆盖 + 1 baseline） |
| `tests/test_qwen_integration.py` | B | 更新到当前 API + 新增产物/泄漏断言 |
| `tests/test_observability_edge_cases.py` | D | 极昼断言 reason code |
| `conftest.py` | E | 新增：禁用 astropy IERS 联网下载，消除离线假失败 |
| `README.md` | E | 架构验收状态 + 证据链 + 产物表更新 |
