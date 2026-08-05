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

把 `StarPlan/qoderwork-skill/` 整个目录复制到 QoderWork 的 Skills 目录：

- Windows：`%USERPROFILE%\.qoderwork\skills\starplan-loop\`
- macOS/Linux：`~/.qoderwork/skills/starplan-loop/`

目录内容即 `SKILL.md`（YAML frontmatter + Markdown 指令），QoderWork 会根据
`description` 中的关键词自动识别并触发。

## 3. 添加 MCP 服务

1. 打开 QoderWork 设置（`Ctrl+Shift+,`）→ **MCP** → **我的服务** → `+`。
2. 粘贴 `StarPlan/qoderwork/mcp.starplan.json` 的内容，并把两处占位路径
   替换为实际路径（见 `StarPlan/qoderwork/QODERWORK_MCP.md`）。
3. 保存后确认服务状态为已连接，展开可见 `starplan.run` 等 7 个工具。

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

## 5. 录屏作为调用凭证

赛题要求保留“模型实际调用过程”的凭证，方案 A 用录屏代替 API Key 日志：

1. 开始系统录屏（Windows：`Win+Alt+R`；macOS：`Cmd+Shift+5`；或任意录屏软件）。
2. 依次展示：Skill 已安装在 `~/.qoderwork/skills/starplan-loop/`；
   MCP 服务已连接且 7 个工具可见；发起上述 3 组任务；每次展开工具调用详情。
3. 结束前打开任意 `runs/<run_id>/`，展示 `plan.json`、`outreach_pack*.md`、
   `validation_report.md`、`run_outcome.json` 与 `model_call_log.jsonl`。
4. 视频 6–8 分钟，可直接用于 PPT/提交材料中的“调用凭证”部分。

## 6. 验收清单

- [ ] 干净环境克隆后按本指南 10 分钟内完成安装。
- [ ] MCP 服务连接成功，7 个工具可列出。
- [ ] 三组任务均跑通，返回 `validation_status=passed`。
- [ ] `runs/<run_id>/` 产物齐全，无 API Key 泄漏。
- [ ] 录屏完整记录 Skill 触发链与工具调用链。
- [ ] 断网状态下三组任务仍可运行（确定性离线路径）。
