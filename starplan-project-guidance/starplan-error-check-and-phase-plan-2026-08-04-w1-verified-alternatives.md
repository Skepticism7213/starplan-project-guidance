# StarPlan Loop 错误检查与阶段计划 — W-1 替代目标真验证（2026-08-04）

日期：2026-08-04
基线：`f8b6d26`（feature/p2-hygiene-fixes，P2 卫生修复）+ 本轮 W-1 修复
范围：2026-08-03 全面审查 WARNING W-1（替代目标建议未经验证）
性质：实现 + 验证（负责人拍板"真算"方案）

## 1. Error Check

### 1.0 修复前状态确认

`observability_plan.py` 的 `_generate_alternatives()` 使用写死的月份对照表（8 个目标），不验证地点、具体日期和不可观测原因，却以 DERIVED_FACT Claim（`blocking.alternatives`）输出"当季更适合观测的目标"。最尖锐的错误场景：月光干扰导致不可观测时，仍把暗弱深空天体推荐到同一个月夜。

### 1.1 修复内容

| 改动 | 说明 |
|---|---|
| 新增 `_coarse_screen_candidates()`（一级粗筛） | 对内置 150 目标目录做批量 AltAz 计算（30 分钟网格），按用户 min_alt 过滤；月光阻断时按 `mag ≤ 5.0` 保留亮星/亮深空、剔除暗弱 DSO；按最高高度排序取前 5 |
| 新增 `_select_verified_alternatives()`（二级精验） | 对粗筛前 5 名逐一跑完整 `compute_observability`（同地点/日期/约束），仅推荐真正 `is_observable=True` 的前 2 个；建议文案携带真实峰值高度与推荐窗口作为证据 |
| `compute_observability` 新增 `_allow_alternatives` 递归防护 | 候选验证调用传 `False`，避免目录扫描无限递归 |
| `_generate_alternatives` 重写 | 删除静态月份表；保留 alternative_date/alternative_location 文案分支；追加已验证的 alternative_target |
| 候选池 | 从 8 个静态目标扩展为完整 150 目标目录（负责人确认） |

### 1.2 验证结果

| 检查 | 结果 |
|---|---|
| 案例二实测 | 推荐 **M29**（最高 75.2°，窗口 01:36–03:21）与 **M57**（56.3°，同窗口），均为真算结果；耗时 0.8s → 2.1~2.7s |
| 新增 `tests/test_verified_alternatives_w1.py`（7 条） | 全过：月光粗筛剔除暗弱 DSO、原目标排除、建议目标独立复算确认可观测、证据文案、确定性、递归防护 |
| 更新 `tests/test_not_observable_pack_c3.py` | 硬编码 M13/M57 断言改为"已验证"合同断言（含独立复算）；10 条全过 |
| 边缘案例 + 月距 + 交付门禁 + 对抗（63 条） | PASS |
| **官方离线 CI 门禁** | **228 passed, 0 failed, 92.66s**（221 + 新增 7） |
| compileall / layer23 / validate_examples | PASS / 0 issues / 3 passed |
| 端到端三案例 + run_loop | 全部 passed（1.7s / 2.1s / 0.9s；二次运行 passed） |

### 1.3 性能与边界说明

- 二级精验最多 5 次完整计算，只在不可观测分支触发，案例二增加约 1.3~1.9s。
- 粗筛的月光星等阈值（5.0）是启发式加速过滤，**最终可观测性由二级精验的完整管线判定**，启发式不影响正确性。
- 无任何候选通过时只保留 alternative_date/location 建议，不编造目标（fail-honest）。

## 2. Phase Plan

### 2.1 完成项

- W-1 关闭：替代目标 100% 来自确定性计算，DERIVED_FACT 口径恢复诚实。
- 竞赛证据点：技术方案可写"替代建议同样经过完整可观测性验证（含月光/暮光/高度约束）"。

### 2.2 遗留项

1. **W-7 文档化**：负责人已拍板"BLOCKED 公共返回保留 target/plan 数值"，需在 README 或合同文档写明口径（下一批顺手处理）。
2. **P3/P4**：三案例脱敏证据包、第二环境复跑、PDF/视频（非代码项，待排期）。
3. 合并窗口：本分支含 P2 卫生修复（f8b6d26）+ W-1 两个提交，建议一并审查合并。

## 3. 验收标准对照

| 标准 | 状态 |
|---|---|
| 每个推荐目标在同地点同日期真实可观测 | ✅ 测试内独立复算断言 |
| 月光阻断不再推荐暗弱深空 | ✅ 粗筛过滤 + 测试 |
| 无递归、无性能爆炸 | ✅ 防护参数 + CI 总耗时 92.66s 可接受 |
| 既有门禁零回退 | ✅ 228 passed / 0 failed |
