# StarPlan × QoderWork 安装与演示指南（方案 A）

方案 A：**不向仓库/配置写入任何 API Key**，由 QoderWork 应用挂载 StarPlan
Skill 并连接本地 MCP 服务；QoderWork 本体即 Qwen 语言层，MCP 工具层负责
确定性天文计算。录屏展示“应用内加载 Skill → 自然语言发起任务 → 工具调用 →
可追溯产物”的完整触发链，作为赛题要求的调用凭证。

## 0. 前置条件

- Windows / macOS / Linux，Python 3.10+。
- 已安装 QoderWork（或 Qoder 桌面端/CLI）。
- 能访问 GitHub 克隆仓库。

## 1. 克隆并安装依赖

```bash
git clone https://github.com/Skepticism7213/starplan-project-guidance.git
cd starplan-project-guidance/StarPlan
pip install -r requirements.txt
```

Windows 推荐一键初始化（创建项目 venv，处理 UTF-8 与缓存权限）：

```powershell
Set-Location StarPlan
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_windows.ps1
```

## 2. 安装 Skill 到 QoderWork

三种方式任选（推荐第一种，最稳妥）：

### 方式一：手动复制（推荐）

把 `StarPlan/qoderwork-skill/` 整个目录复制到 QoderWork 的 Skills 目录：

- Windows：`%USERPROFILE%\.qoderwork\skills\starplan-loop\`
- macOS/Linux：`~/.qoderwork/skills/starplan-loop/`

目录内容即 `SKILL.md`（YAML frontmatter + Markdown 指令），QoderWork 会根据
`description` 中的关键词自动识别并触发。

### 方式二：QoderWork 界面上传

左侧导航「扩展」→「技能」→「安装技能」，直接上传 `StarPlan/qoderwork-skill/SKILL.md`
及辅助文件，QoderWork 自动识别并加载。

### 方式三：对话安装

在新对话中发送：

```text
请把 E:\learning\阿里云揭榜挂帅\starplan-project-guidance\StarPlan\qoderwork-skill
文件夹安装为 Skill，放到 ~/.qoderwork/skills/starplan-loop/ 目录
```

（或把仓库 GitHub 地址发给它，让它克隆并放置）。

## 3. 添加 MCP 服务

1. 打开 QoderWork 桌面端，进入「扩展」→「连接器」（或「设置」→「MCP 服务」），
   点击右上角 **+ 添加**。
2. 选择“粘贴 JSON 配置”，把 `StarPlan/qoderwork/mcp.starplan.json` 的内容粘贴进去，
   并替换两处占位路径（见 `StarPlan/qoderwork/QODERWORK_MCP.md`），点击“导入”。
   或选择“手动填写配置”：类型选 **STDIO**，命令填完整启动命令，环境变量加
   `STARPLAN_MODEL_MODE=offline`。
3. 导入后服务名称左侧显示**绿色圆点**即连接成功；展开服务可见
   `starplan.run`、`starplan.run_loop` 与 4 个核心 Skill 共 7 个工具。
4. 若界面提供“服务超时时长（Request Timeout）”，建议调到 120 秒以上
   （首次 `starplan.run` 需要导入 Astropy 并完成确定性计算）。

> 不需要在 MCP 配置或仓库中填写任何 API Key。`STARPLAN_MODEL_MODE=offline`
> 确保工具层确定性运行；QoderWork 应用的模型负责自然语言理解与转达。

## 4. 新对话测试（三组典型任务）

### 任务 1：正常可观测活动（M31，济南）

```text
我们天文社 2026-10-17 想在济南四门塔组织一次 M31 新手观测活动，
受众是高中天文社新成员，用双筒望远镜，时长 90 分钟。
请生成观测计划、三视图科普活动包，以及需要人工确认的清单。
```

### 任务 2：不适合观测及备选方案

```text
2026-07-25 在济南四门塔用双筒看 M42 猎户座大星云，适合吗？
如果不适合，给出原因和备选目标或时间。
```

### 任务 3：实际活动复盘与下一轮

```text
上次 M31 活动实际 19:45 才开始（原计划 19:13），22:00 结束，天晴。
请复盘偏差原因并生成下一轮可执行输入。
```

每个任务应展示：QoderWork 自动/手动触发 Skill → 调用 MCP 工具 →
返回结构化结果 → 用户在 `StarPlan/runs/<run_id>/` 核对产物。

### 调用技巧（演示前必读）

- **Skill 触发**：通常自然语言会自动触发；若没有触发，在输入框输入 `/`
  选择 `starplan-loop`，或直接说“使用 starplan-loop skill 处理”。
- **工具确认**：QoderWork 调用 MCP 工具前会请求确认，按 `Ctrl+Enter`
  （macOS 为 `Cmd+Enter`）执行；录屏时不要跳过这一步，这正是调用凭证。
- **参数失败兜底**：若 QoderWork 把自然语言转成工具参数时报 Schema 错误，
  直接在对话中粘贴 `StarPlan/examples/case_01_m31_jinan.json` 的内容，
  让它“原样作为 input 调用 starplan.run”。
- **任务 3 的结构化日志**：为避免复盘参数构造失败，可直接附带以下日志：

```json
{
  "actual_start_time": "2026-10-17T19:45:00",
  "actual_end_time": "2026-10-17T22:00:00",
  "targets_observed": ["M31"],
  "targets_missed": [],
  "equipment_used": "binoculars",
  "cloud_cover": "clear",
  "seeing_conditions": "good",
  "observer_notes": "大家迟到约30分钟",
  "success_rating": 4
}
```

## 5. 录屏作为调用凭证

赛题要求保留“模型实际调用过程”的凭证，方案 A 用录屏代替 API Key 日志：

1. 开始系统录屏（Windows：`Win+Alt+R`；macOS：`Cmd+Shift+5`；或任意录屏软件）。
2. 依次展示：Skill 已安装在 `~/.qoderwork/skills/starplan-loop/`；
   MCP 服务已连接且 7 个工具可见；发起上述 3 组任务；每次展开工具调用详情。
3. 打开任务侧边栏/Task Monitor，展示本任务“使用了 starplan-loop Skill 与
   starplan MCP”的触发链记录。
4. 结束前打开任意 `runs/<run_id>/`，展示 `plan.json`、`outreach_pack*.md`、
   `validation_report.md`、`run_outcome.json` 与 `model_call_log.jsonl`。
5. 视频 6–8 分钟，可直接用于 PPT/提交材料中的“调用凭证”部分。

### 演示前自检（5 分钟）

1. 在终端手动启动一次 MCP 服务确认无报错：
   `StarPlan\.venv\Scripts\python.exe -X utf8 StarPlan\scripts\starplan_mcp_server.py`
   （启动后等待输入即正常，`Ctrl+C` 退出）。
2. 确认 `StarPlan\runs\` 目录可写（MCP 进程会把运行产物写在这里）。
3. 先在不录屏的情况下把三组任务各跑一遍，确认参数与输出稳定，再正式录屏。

## 6. 验收清单

- [ ] 干净环境克隆后按本指南 10 分钟内完成安装。
- [ ] MCP 服务连接成功，7 个工具可列出。
- [ ] 三组任务均跑通，返回 `validation_status=passed`。
- [ ] 任务侧边栏/Task Monitor 显示使用了 starplan-loop Skill 与 starplan MCP。
- [ ] `runs/<run_id>/` 产物齐全，无 API Key 泄漏。
- [ ] 录屏完整记录 Skill 触发链与工具调用链。
- [ ] 断网状态下三组任务仍可运行（确定性离线路径）。
