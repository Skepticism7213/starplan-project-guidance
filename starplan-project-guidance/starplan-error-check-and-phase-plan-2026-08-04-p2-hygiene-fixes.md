# StarPlan Loop 错误检查与阶段计划 — P2 卫生修复（2026-08-04）

日期：2026-08-04
基线：`3c902e6`（origin/main）+ 本轮 4 项修复
范围：2026-08-03 全面审查与本机复现复核遗留的 4 项代码级缺陷
性质：实现 + 验证

## 1. Error Check

### 1.0 修复前逐条验证（确认 bug 真实存在）

| # | 问题 | 验证方式 | 结果 |
|---|---|---|---|
| R-01 | 在线测试 skip 不认 offline 模式 | 读 `test_qwen_integration.py`：skipif 仅查 Key，无 `STARPLAN_MODEL_MODE` 引用 | 确认存在 |
| W-04 | text_hash 字段篡改不被发现 | 篡改序列化 dict 的 text_hash 后 `from_dict()` 正常重建 | 确认存在 |
| R-06 | leap-second 权限警告 | 读 astropy 8.0.1 源码：`_check_leapsec()`→`auto_open()` 新鲜度窗口（today+150d）在 2026-08 起不再满足，触发缓存/网络访问 | 确认存在（机制 + 复现报告日志） |
| I-3 | moonrise/moonset 恒 None | `observability_plan.py` 硬编码 `moonrise=None, moonset=None` | 确认存在 |

### 1.1 修复内容

| 问题 | 修复 | 文件 |
|---|---|---|
| R-01 | skipif 增加 `_model_mode_offline()` 检查：`STARPLAN_MODEL_MODE=offline` 时无条件 skip，优先级高于 `.env` Key | `tests/test_qwen_integration.py` |
| W-04 | `RenderedDocument.from_dict()` 显式校验保存的 text_hash：缺失或不匹配 → ValueError，所有调用方（runner/Chat/extra-view validator）已有 fail-closed 异常处理 → BLOCKED | `starplan_skills/rendering.py` |
| R-06 | `configure_astronomy_runtime()` 在首次 Time 创建前预置 `_LEAP_SECONDS_CHECK=DONE`，彻底跳过一次性 leap-second 自动更新路径；附科学安全性论证（2017-01-01 后无闰秒，ERFA 内置表对项目全部日期正确） | `starplan_skills/astro_runtime.py` |
| I-3 | 新增 `_compute_moon_rise_set()`：5 分钟网格 + 二分法精化（~7s 精度）纯 Astropy 数值搜索；语义为"夜间窗口内的升/落事件"，窗口外返回 None 并在 Schema 中注明 | `starplan_skills/observability_plan.py`、`starplan_skills/schemas.py` |

### 1.2 新增测试

| 测试 | 覆盖 |
|---|---|
| `TestHashFieldTamperW04`（4 条，test_delivery_contract_gate.py） | hash 篡改/缺失 → ValueError；篡改落盘文件 → runner 路径降级 BLOCKED；合法文档 roundtrip 不受影响 |
| `TestLeapSecondPolicyR06`（1 条，test_runtime_offline_policy.py） | 子进程验证：flag 预置 DONE + `update_leap_seconds` 调用计数为 0 + 无 leap 警告 |
| `TestMoonRiseSetComputed`（5 条，tests/test_moon_rise_set_i3.py） | moonset 过零方向验证（±5 分钟高度符号）、moonrise=None 的合法性断言、确定性、M42 案例 |

### 1.3 回归验证结果

| 检查 | 结果 |
|---|---|
| `compileall -q starplan_skills scripts tests` | PASS |
| `tests/layer23_validation.py` | 0 unique issues，10 轮一致 |
| `tests/test_confidence_algorithm.py` | 150/150 passed |
| 边缘案例 + C2/C3 + W6-W9（47 条） | PASS |
| 幻觉防护 + Claim 完整性 + Chat + 对抗（67 条） | PASS |
| 交付合同 + fail-closed + P0 closure + Chat 地点（44 条） | PASS |
| slot/三视图 + next input + 兼容客户端 + Layer3 e2e（48 条） | PASS |
| 离线运行策略 + leap second（4 条） | PASS |
| 月距 C-1 + 月升落 I-3（11 条） | PASS |
| **`scripts/run_offline_ci.bat` 官方离线门禁** | **221 passed, 0 failed, 66.54s**（基线 211 + 新增 10） |
| R-01 行为验证 | `STARPLAN_MODEL_MODE=offline` 下在线套件 9 skipped / 0.22s |
| moonset 交叉验证 | 2026-10-17 济南：moonset=21:49:42，该时刻高度 0.0°，前 +0.79°/后 -0.80° |
| 端到端三案例（offline） | Case1 passed/template 1.6s；Case2 passed/template 0.8s；Case3 passed/template 0.9s |
| `run_loop.py` 闭环 | 二次运行 passed，before/after 报告生成 |

## 2. Phase Plan

### 2.1 本阶段完成项

- 2026-08-03 full review / 复现复核中全部 4 项代码级缺陷已关闭并附回归证据。
- 离线测试基线从 211 提升至 221；在线测试在有 Key 机器的离线门禁下正确 skip。
- `plan.json` 的 `moon_info` 现包含真实 moonrise/moonset（仅中间产物，未新增用户可见 Claim——遵守"新事实须走 Claim Registry"边界）。

### 2.2 遗留项 / 下一步（均非代码 bug）

1. **P3 证据包**：三案例脱敏运行包（输入/中间结果/输出/manifest/outcome/validation/trace + SHA-256 清单）、第二环境复跑、人工确认签名。
2. **P4 材料**：≤20 页 PDF 技术方案、≤10 分钟演示视频（结构化入口主线，Chat 补充）。
3. **待决策项**（昨日清单 5、6）：W-7 BLOCKED 公共返回口径（文档说明 vs 收紧合同）；W-1 替代目标真算可观测性 vs 降级措辞。
4. **R-02**：提交包附 pip freeze + Python/OS/时区环境清单（随 P3 一并处理）。
5. **Key 安全**：轮换曾在对话中明文分享的 Key（Key-1/2 已失效）。

## 3. 验收标准对照

| 验收标准（修复前约定） | 状态 |
|---|---|
| 带 `.env` 的机器执行离线命令稳定通过，在线测试 skip | ✅ offline CI 221 passed；9 条在线测试 offline 下 skip |
| 只改 rendered_document.json 的 text_hash 必须 BLOCKED | ✅ from_dict 抛 ValueError → runner/Chat 降级 BLOCKED（4 条测试） |
| 演示日志不再出现 leap-second 警告 | ✅ 更新路径整体跳过（子进程 spy 验证 0 调用） |
| MoonInfo.moonrise/moonset 为真实计算值或可证明的 None | ✅ 独立采样交叉验证 + 5 条回归测试 |
| 不引入架构回退 | ✅ 未改动 claims/表达计划/fail-closed 规则；全部既有门禁测试通过 |
