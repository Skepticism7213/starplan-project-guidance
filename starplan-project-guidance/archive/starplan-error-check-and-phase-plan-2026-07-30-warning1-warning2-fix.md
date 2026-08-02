# StarPlan Loop 错误排查报告与阶段安排 — WARNING-1/WARNING-2 修复

日期：2026-07-30
基准 commit：c1ca7c0（修复前）
来源：`starplan-independent-deep-audit-2026-07-30.md` 中发现的 WARNING-1、WARNING-2

---

## 1. 错误排查结论

本轮修复独立深度审查发现的 2 个 WARNING 级问题，均在 `observability_plan.py`。**修复后 110 个测试全过，3 个固定案例端到端跑通，无回归。**

### 已修复的 WARNING 级问题

| # | 问题 | 修复方式 | 验证 |
|---|---|---|---|
| WARNING-1 | 极昼（高纬度夏季太阳整夜不落）被误判可观测：可见窗口判定 `is_good` 只查目标高度/airmass/月光，不查太阳高度；无暮光时走默认 20:00–04:00 回退窗口，白天被当成可观测 | `is_good` 增加 `h.sun_altitude_deg < sun_dark_alt` 条件，`sun_dark_alt` 取自 twilight 配置 `sun_altitude_deg`（默认 −18°，天文暮光阈值） | 北纬70°夏至 M31 由 `is_observable=True` 转为 `False`；正常案例推荐窗口内太阳全程 <−18°，未被误伤 |
| WARNING-2 | 纬度受限目标（理论最大高度 `90−|lat−dec|` 永远低于最低高度）收到误导性"等待更好观测季节"建议，但改期对纬度受限目标无效 | 调用点计算 `latitude_limited = (90−|lat−dec|) < min_alt`；`_generate_alternatives` 对纬度受限目标改给 `alternative_location`（建议换更低纬度地点），仅对日期受限（太阳/月光）目标保留 `alternative_date` | M70@济南（最大21.2°）给 `alternative_location` 不含 `alternative_date`；M42@济南7月（最大48°≥30°，日期受限）仍给 `alternative_date` 不含 `alternative_location` |

### 改动文件

- `starplan_skills/observability_plan.py`：`is_good` 加太阳高度条件；读取 `sun_dark_alt`；调用点计算 `latitude_limited`/`max_alt_theory`；`_generate_alternatives` 增加 `latitude_limited`/`max_alt_theory` 参数与分支。
- `starplan_skills/schemas.py`：`AlternativeSuggestion.suggestion_type` 文档新增 `alternative_location` 类型。
- `tests/test_observability_edge_cases.py`（新增）：5 个测试（极昼不可观测、纬度受限给换地点、日期受限给改期、正常可观测回归、太阳判据不误伤暗夜）。

### 运行时验证

- 新增 5 个边界测试 + 既有测试合计 **110 passed**（含 test_moon_separation_c1、test_not_observable_pack_c3、test_claims_registry_b、test_mock_qwen_adversarial、test_target_confirmation_c2、test_confidence_algorithm、test_hallucination_protection、test_w6_w9_unit、test_chat_hallucination_c4）。
- 3 个固定案例端到端：case_01 可观测（推荐 19:13~04:28，与修复前一致）、case_02 正确不可观测、case_03 复盘识别 3 偏差，分别生成 14/14/18 个文件，无报错。
- 正常案例峰值高度修复前后完全一致（M31 85.04°、织女星 83.24°、M81 57.55°），确认核心计算无回归。

### 仍保留（未修复，已在审计报告记录）

- **LOW-1**：低高度风险标志用整夜最低点而非推荐窗口（织女星峰值83°却因夜末14.49°报 CRITICAL）。体验问题，建议后续优化。
- **INFO-1**：强月光将几何可见目标判"不可观测"（保守设计），建议文档说明，无需改代码。

---

## 2. 完成度对照

| 审计发现 | 状态 |
|---|---|
| WARNING-1 极昼误判可观测 | ✅ 已修复并测试 |
| WARNING-2 纬度受限误导改期建议 | ✅ 已修复并测试 |
| LOW-1 风险标志范围过宽 | ⏳ 记录，建议后续优化 |
| INFO-1 月光设计取舍 | ⏳ 记录，文档说明即可 |

本轮属对独立深度审查发现的修复，对应项目"确定性科学计算可验证"的加固，不在原 6 周主线阶段内，但提升了科学严谨性。

---

## 3. 阶段安排（下一步）

近期：

1. 提交并推送本轮修复（observability_plan.py + schemas.py + 新测试 + 本报告）。
2. 可选：修复 LOW-1（低高度风险限定到推荐窗口）。

中期（回到主线，据独立审查与团队既有计划）：

3. 科学交叉校验：用 Stellarium/KStars 对固定案例的高度角、暮光、月距逐项对账并留痕（科学价值 40%）。
4. 演示面板（Streamlit/FastAPI，待团队选型）+ 3 案例一键复现。
5. 对照实验（传统流程 vs StarPlan）+ 可选校园实测。
6. 提交材料：≤20 页 PPT/PDF、技术报告、10 分钟视频、Skills 清单与流程图。

阻塞项：演示技术选型、百炼账号/模型版本确认、提交平台与格式要求（待团队确认）。

---

## 4. 立即可做的下一步

1. `git add` 本轮改动 → `git commit` → `git push`。
2. 团队确认演示技术选型，启动演示面板与科学交叉校验。
3. 决定是否修 LOW-1（低高度风险标志范围）。
