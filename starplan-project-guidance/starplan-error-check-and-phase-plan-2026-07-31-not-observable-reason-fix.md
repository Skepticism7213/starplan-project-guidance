# StarPlan Loop 错误排查报告与阶段安排 — 不可观测原因误判修复

日期：2026-07-31
基准 commit：872937f
来源：2026-07-30 五案例审查发现的「问题 1」（不可观测文案不分原因）

---

## 1. 错误排查结论

本轮修复五案例审查发现的 WARNING 级问题：**不可观测目标的原因被张冠李戴**。改动 `schemas.py`、`observability_plan.py`、`outreach_pack.py` 三个文件。**修复后 3 个不可观测案例原因判定正确，59 个既有测试全过，无回归。**

### 已修复的 WARNING 级问题

| # | 问题 | 表现 | 修复方式 |
|---|---|---|---|
| 1 | 不可观测文案恒称"高度角过低"，不区分真实原因 | 案例 M13 满月夜最高高度 88.7°（理想），却被报"最高高度仅 88.7°，不满足 30° 要求""最高高度角过低"——自相矛盾，真实原因是月光 | `compute_observability` 新增 `not_observable_reason` 判定（latitude/moonlight/altitude）并写入 `ObservabilityResult`；`_generate_alternatives` 与 `outreach_pack` 不可观测文案按真实原因表述 |

### 原因判定逻辑

`not_observable_reason` 三态：

- `latitude`：理论最大高度 `90−|纬度−赤纬|` 永久低于最低高度（改期无效）→ 建议换更低纬度地点。
- `moonlight`：目标夜间能达到最低高度，但被月光淘汰（存在高度合格但月光超标的时段）→ 建议改到月光弱的日期（新月前后）。
- `altitude`：目标当夜从未达到最低高度（太阳/季节）→ 建议等待更好观测季节。

### 运行时验证

| 案例 | 目标/日期 | 判定原因 | 备选/文案 | 结论 |
|---|---|---|---|---|
| ②太阳/高度 | M42 / 2026-07-25 | altitude | "夜间最高高度仅 −5.7°，低于 30°…等待更好季节" | PASS |
| ③纬度受限 | M70 / 2026-08-15 | latitude | "最大高度仅 21.2°，永远低于 30°，改期无效…换地点" | PASS |
| ④月光阻挡 | M13 / 2026-05-31 | moonlight | "高度角合适（最高 88.7°），但当晚月光影响严重…改到新月前后" | PASS |

- 既有测试 59 passed（test_observability_edge_cases、test_not_observable_pack_c3、test_claims_registry_b、test_mock_qwen_adversarial、test_hallucination_protection、test_moon_separation_c1），无回归。
- `not_observable_reason` 与 claims.py 既有的 `blocking.reason`（从 eliminated_windows.violated_constraint 推导）语义一致，互相印证。

### INFO 级备注（未修复，记录在案）

- 五案例审查的问题 2（低高度风险标志用整夜最低点而非推荐窗口）、问题 3（月光影响不看目标亮度，亮星被误报）、问题 4（恒星"角大小缺失"待确认项是噪声）仍未处理，属体验/细节优化，非本轮范围。

---

## 2. 完成度对照

| 来源任务 | 状态 |
|---|---|
| 五案例审查·问题 1（不可观测原因误判） | ✅ 已修复并验证 |
| 五案例审查·问题 2/3/4 | ⏳ 记录，建议后续优化 |

本轮属对独立审查发现缺陷的修复，对应"确定性科学计算可验证、表述准确"的加固。

---

## 3. 阶段安排（下一步）

近期：

1. 提交并推送本轮修复（schemas/observability_plan/outreach_pack + 本报告）。
2. 可选修复问题 2（低高度风险限定到推荐窗口）。

中期（回到主线）：

3. 问题 3：月光约束按目标亮度放宽（亮星不受月光影响）。
4. 演示面板（Streamlit/FastAPI，待团队选型）+ 3 案例一键复现。
5. 对照实验 + 可选校园实测；提交材料（≤20 页 PPT/PDF、技术报告、视频、Skills 清单）。

阻塞项：演示技术选型、提交平台与格式要求（待团队确认）。

---

## 4. 立即可做的下一步

1. `git add` 三个改动文件 + 本报告 → `git commit` → `git push`。
2. 决定是否修问题 2/3（风险标志范围、月光按亮度放宽）。
3. 团队确认演示技术选型，启动演示面板。
