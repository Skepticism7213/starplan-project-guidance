# StarPlan Loop 错误排查报告与阶段安排 — 五案例审查问题 2/3/4 修复

日期：2026-07-31
基准 commit：8b5f804
来源：2026-07-30 五案例审查发现的问题 2、3、4（问题 1 已在 8b5f804 修复）

---

## 1. 错误排查结论

本轮修复五案例审查剩余的 3 个问题，改动 `observability_plan.py`、`runner.py`、`outreach_pack.py`、`constraints_config.yaml`。**修复后 8 项针对性验证全过，91 个既有测试全过，无回归；深空目标月光约束未被破坏。**

### 已修复问题

| # | 问题 | 修复方式 | 验证 |
|---|---|---|---|
| 3 | 月光影响不看目标亮度：0.03 等亮星织女星也被报月光 moderate | `compute_observability` 新增 `target_type` 参数与 `moonlight_insensitive` 判定（target_type==star 且视星等 < `bright_star_magnitude_threshold`，默认 2.5）；亮星跳过月光淘汰、月光影响判 none。阈值入 `constraints_config.yaml` | Vega 月影响 none、无月光标志、可观测；深空 M13 满月仍 severe 且不可观测（约束对深空仍生效） |
| 2 | 低高度风险用整夜最低点：峰值 87° 的织女星因夜末西沉被报 low_altitude critical | `_compute_risk_flags` 新增 `recommended_window` 参数，低高度检查限定在推荐窗口内（无推荐窗口时退回整夜） | Vega 推荐窗口峰值 87.4°，无低高度风险标志 |
| 4 | 恒星报"角大小数据缺失"噪声（恒星是点源本无角大小） | `outreach_pack` 待确认项对 `target_type=="star"` 跳过角大小缺失提示 | Vega 无角大小待确认项 |

### 科学依据

- **问题 3**：月光抬高天空背景亮度，主要淹没暗弱/延展天体（星系、星云、星团）；明亮点源恒星（视星等 < 2.5）在满月下仍清晰可见，故对亮星放宽月光约束符合实际。深空天体（即便较亮如 M31）因表面亮度低仍受月光影响，故放宽仅针对 `target_type=="star"`，不针对深空。
- **问题 2**：低高度风险应针对实际推荐的观测时段；推荐时段目标高悬时，夜末西沉的低高度与观测无关。

### 运行时验证

- 针对性验证 8 项全 PASS（Vega 月光 none/无月光标志/可观测；M13 深空满月仍 severe/不可观测；Vega 无低高度风险；Vega 无角大小待确认项）。
- 既有测试 91 passed（含 test_observability_edge_cases、test_not_observable_pack_c3、test_claims_registry_b、test_mock_qwen_adversarial、test_hallucination_protection、test_moon_separation_c1、test_w6_w9_unit、test_target_confirmation_c2、test_confidence_algorithm），无回归。

### INFO 级备注

- `bright_star_magnitude_threshold` 默认 2.5，可在 `constraints_config.yaml` 调整。
- chat 模式工具执行器（runner.py 的 `_exec_observability_plan`）未传 target_type，该路径月光约束保持保守（moonlight_insensitive=False），不影响主流程。

---

## 2. 完成度对照

| 来源任务 | 状态 |
|---|---|
| 五案例审查·问题 1（不可观测原因误判） | ✅ 已修复（8b5f804） |
| 五案例审查·问题 2（低高度风险范围） | ✅ 已修复 |
| 五案例审查·问题 3（月光按亮度放宽） | ✅ 已修复 |
| 五案例审查·问题 4（恒星角大小噪声） | ✅ 已修复 |

五案例审查发现的 4 个问题至此全部修复。对应"确定性科学计算可验证、表述准确、约束合理"的加固。

---

## 3. 阶段安排（下一步）

近期：

1. 提交并推送本轮修复（observability_plan/runner/outreach_pack/config + 本报告）。

中期（回到主线）：

2. 演示面板（Streamlit/FastAPI，待团队选型）+ 3 案例一键复现。
3. 科学交叉校验扩展到更多目标/地点/日期（已有 astroplan 交叉校验脚本与 2 案例记录）。
4. 对照实验（传统流程 vs StarPlan）+ 可选校园实测。
5. 提交材料：≤20 页 PPT/PDF、技术报告、10 分钟视频、Skills 清单与流程图。

阻塞项：演示技术选型、提交平台与格式要求（待团队确认）。

---

## 4. 立即可做的下一步

1. `git add` 四个改动文件 + 本报告 → `git commit` → `git push`。
2. 团队确认演示技术选型，启动演示面板。
3. 可选：扩大交叉校验覆盖（更多目标/地点/日期）。
