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

在 QoderWork 桌面端（以实际界面版本为准）：

1. 打开「扩展」→「连接器」，或「设置」→「MCP 服务」，点击右上角 **+ 添加**。
2. **推荐：粘贴 JSON 配置**。选择“粘贴 JSON 配置”，把替换好路径的
   `mcp.starplan.json` 内容粘贴进去并点击“导入”。
   也可以选择“手动填写配置”：服务器类型选 **STDIO**，命令填
   `"C:\path\to\python.exe" -X utf8 "C:\path\to\StarPlan\scripts\starplan_mcp_server.py"`，
   环境变量添加 `STARPLAN_MODEL_MODE=offline` 与 `PYTHONIOENCODING=utf-8`。
3. 添加成功后服务名称左侧显示**绿色圆点**（连接成功）；展开服务可看到
   上述 7 个工具。若列表为空或为红色，检查 Python 路径、脚本路径与依赖。
4. 若 QoderWork 用的是旧版 Qoder IDE 路径：设置（`Ctrl+Shift+,`）→ **MCP** →
   **我的服务** → `+`，同样粘贴 JSON 保存。
5. 首次调用 `starplan.run` 需要数秒（导入 Astropy + 确定性计算）；若界面有
   “服务超时时长（Request Timeout）”，建议调到 120 秒以上，避免超时中断。
6. 在**新任务（新对话）**中发起观测任务；任务侧边栏/Task Monitor 会显示
   本任务使用了哪些 Skill 与 MCP 工具，可直接用于录屏凭证。

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
