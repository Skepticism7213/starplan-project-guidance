# 循环 before/after 对比

- 案例：M31 复盘闭环：观测日志 → 证据归因 → 可执行下一轮 → 二次运行
- 第一轮（含观测日志）：`StarPlan/runs/m31_济南-四门塔_20261017_184517_review`
- 第二轮（next_activity_input.json 重跑）：`StarPlan/runs/m31_review_20261017_184517_next`
- 归因原因：cause.team_late

## 活动时段变化

| 字段 | 第一轮 | 第二轮 |
|---|---|---|
| activity_slot.start | 2026-10-17T19:13:49.687500 | 2026-10-17T19:45:00 |
- 修订 preparation_step：本次迟到 31 分钟（来源：cause.team_late）
- 修订 activity_preferences.preferred_start：本次实际开始 19:45 晚于计划，将下次活动开始时间调整到实际可用时间（来源：cause.team_late）
