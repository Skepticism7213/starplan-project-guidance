# QoderWork / Qoder MCP 接入说明

StarPlan 提供纯标准库的 MCP stdio 适配层：
`StarPlan/scripts/starplan_mcp_server.py`。
它不重复实现任何天文计算，只把 MCP 工具调用转交给现有 Skills/runner。
适配层把 runner 的进度日志重定向到 stderr，保证 stdout 只输出 JSON-RPC，
符合 MCP stdio 协议要求。

## 工具清单

| 工具 | 用途 |
|---|---|
| `starplan.run` | 统一入口：目标解析 → 可观测性 → 活动时段 → 科普包 → 可选复盘与下一轮输入 |
| `starplan.run_loop` | 一次完成“含日志运行 → next_activity_input → 二次运行 → before/after” |
| `skill.target_resolve` | 目标名 → 标准坐标/类型/置信度（歧义返回候选） |
| `skill.resolve_location` | 地点名 → 内置地点表经纬度/海拔/时区 |
| `skill.observability_plan` | 坐标+地点+日期 → 科学窗口/activity_slot/月光/风险/备选 |
| `skill.outreach_pack` | 目标+可观测结果 → 三视图科普活动包 |
| `skill.observation_review` | 原计划+观测日志 → 偏差/证据归因/修订/下一轮输入 |

## 配置模板

把 `mcp.starplan.json` 中的占位路径替换为本机实际路径：

- `command`：安装过项目依赖的 Python 解释器绝对路径（建议 `StarPlan/.venv/Scripts/python.exe` 或系统 Python 3.10+）。
- `args[2]`：`StarPlan/scripts/starplan_mcp_server.py` 的绝对路径。
- `env.STARPLAN_MODEL_MODE=offline`：MCP 工具层只做确定性计算，不调用外部模型；
  QoderWork 应用本体就是 Qwen 语言层，负责理解与转达。无需、也不应在此配置任何 API Key。

在 QoderWork / Qoder 中：

1. 打开设置（用户图标或 `Ctrl+Shift+,`）→ **MCP**。
2. **我的服务** → `+` 添加，把 JSON 粘贴到配置编辑器并保存。
3. 保存后服务应显示已连接；展开可看到上述 7 个工具。
4. 在 **智能体模式** 的新对话中发起观测任务。

## 推荐的演示对话

```text
我们天文社 2026-10-17 想在济南四门塔组织一次 M31 新手观测活动，
受众是高中天文社新成员，用双筒望远镜，时长 90 分钟。
请生成观测计划、三视图科普活动包，以及需要人工确认的清单。
```

```text
上次活动大家迟到了 30 分钟，请根据下面的观测日志复盘，
并生成可执行的下一轮活动输入。
（粘贴 observation_log）
```

## 验证

- 服务连接后调用一次 `skill.target_resolve`（如“毕宿五”），返回标准坐标即连通。
- 调用 `starplan.run` 后返回 `validation_status` 与 `run_id`；
  在 `StarPlan/runs/<run_id>/` 检查 `plan.json`、`outreach_pack*.md`、`validation_report.md`。
- 没有网络、没有 Key 也能完整运行（离线确定性路径），这是设计特性而非降级。
