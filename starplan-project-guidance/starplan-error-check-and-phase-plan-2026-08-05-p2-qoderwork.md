# StarPlan Loop 错误排查报告与阶段安排（P2 QoderWork 交付）

日期：2026-08-05
项目起始：2026-07-18 ｜ 官方截止：2026-09-05 00:00（北京时间）｜ 内部硬截止：2026-09-01 00:00（北京时间）｜ 当前阶段：P2 方案 A 交付
基线与分支：本地 `main` 快进至 `origin/main`（`7688a02`）后新建 `codex/p2-qoderwork-delivery`

---

## 一、本轮错误排查结论

**1 个 CRITICAL（已修复）、0 个 WARNING、6 个 INFO（已处理或确认无害）。**
新增代码与既有代码均编译、运行无错误；全量离线回归 **237 passed, 0 failed**；
示例 Schema 校验 **5/5 passed**；密钥扫描无泄漏；`git diff --check` 干净。

### CRITICAL（已修复）

| # | 问题 | 影响 | 修复方式 | 验证 |
|---|---|---|---|---|
| C-1 | StarPlan runner 在每次运行向 stdout 打印进度（`astronomy_runtime=...`、`[1/4]...`），而 MCP stdio 协议要求 stdout 只能承载 JSON-RPC 消息 | 任何完整 `starplan.run` 调用都会把非 JSON 文本混入协议流，Qoder/QoderWork 客户端将解析失败或卡死 | 在 MCP 适配层新增 `_stdout_to_stderr()` 上下文管理器，把全部工具调用期间的 stdout 捕获并转发到 stderr；不改动受保护的 `runner.py` | 新增 `test_stdout_contains_only_json_lines_during_full_run`：完整运行后再次 `ping` 仍返回合法 JSON，且 stderr 中含 `astronomy_runtime=` 标记 |

### INFO（处理或确认无害）

| # | 问题 | 判定 |
|---|---|---|
| I-1 | `mcp.starplan.json` 含 `<路径>` 占位符 | 预期行为，安装文档明确要求替换为本机绝对路径；不含任何 Key |
| I-2 | MCP 冒烟测试最初经 PowerShell 管道把中文按 GBK 编码传给子进程，出现 `??` 乱码 | 环境传参问题，非服务缺陷；已改为 Python 子进程 UTF-8 字节流测试，`test_utf8_chinese_target_round_trip` 验证“毕宿五”往返正确 |
| I-3 | 离线模式下 `delivery_status=template`（模板交付）而非 `delivered` | 符合既有公共契约（离线确定性路径），测试断言已兼容两种状态 |
| I-4 | 未携带 `audience_profile.requested_views` 时只渲染 organizer 视图 | 符合既有设计（三视图由输入显式请求）；测试输入已补全三视图并验证 |
| I-5 | 版本从 0.8.0 升至 0.9.0，README 历史更新日志仍保留 0.8.0 等旧版本号 | 历史记录，按原样保留；当前版本以 `skills.yaml`、`__init__.py`、MCP `serverInfo` 为准 |
| I-6 | 官方截止 09-05 与内部硬截止 09-01 的差异 | 负责人已核验确认官方 2026-09-05 00:00（北京时间）；内部 09-01 00:00 冻结保留，文档基线已统一（见 2026-08-05 截止日期修正提交） |

### 未跟踪验证产物并入批次

`StarPlan/examples/case_08_sirius_sdu_20261219.json`、
`case_10_aldebaran_jinan_20270116.json` 与
`StarPlan/数据验证日志/claim_accuracy_verification_aldebaran_20270116.md`
为 2026-08-05 遗留的 W-1 备选目标验证证据，本轮单独提交，与 P2 交付提交分离。

### 运行验证记录

| 检查项 | 命令 | 结果 |
|---|---|---|
| MCP 握手 | `initialize` + `notifications/initialized` + `tools/list` + `ping` | 通过，7 个工具可列出 |
| MCP 工具调用 | `skill.target_resolve`（毕宿五）/ `starplan.run`（M31 全链路） | 通过，返回标准结果 |
| MCP 回归测试 | `pytest tests/test_mcp_server.py`（离线） | 7 passed |
| 全量离线回归 | `pytest tests/ --ignore=tests/test_qwen_integration.py`（离线） | 237 passed, 0 failed |
| 示例校验 | `scripts/validate_examples.py` | 5 passed, 0 failed |
| 协议纯净性 | 完整运行后 stdout 仅 JSON-RPC；诊断在 stderr | 通过 |
| 密钥扫描 | 仓库全文检索 `sk-ws-` / `DASHSCOPE_API_KEY=` 赋值 | 无完整 Key 泄漏 |
| diff 卫生 | `git diff --check` | 干净 |

### 2026-08-05 补充：QoderWork 演示文档校正（无代码变更）

按 QoderWork 官方文档核实并更新了两份交付文档：
`StarPlan/qoderwork/QODERWORK_MCP.md` 与 `StarPlan/qoderwork-安装演示.md`。
修正点：

- MCP 添加入口统一为「扩展 → 连接器」或「设置 → MCP 服务」→ `+` 添加，
  支持“粘贴 JSON 配置”与“手动填写（STDIO）”两种方式；旧文档中的
  “设置 → MCP → 我的服务”为 Qoder IDE 路径，保留为兼容说明。
- 补充绿色圆点连接验证、工具列表检查、Request Timeout 调整建议。
- 补充 Skill 的三种安装方式（手动复制 / 界面上传 / 对话安装）、`/` 快捷调用、
  工具调用确认（`Ctrl+Enter`）、参数失败时直接粘贴案例 JSON 的兜底方法。
- 补充任务 3 复盘的结构化 observation_log 模板与录屏时 Task Monitor 展示建议。

本轮仅文档改动，无代码与测试变更；`git diff --check` 干净。

---

## 二、当前完成度对照项目计划

| 计划阶段 | 计划目标 | 实际状态 |
|---|---|---|
| P0 关闭可见阻断 | 离线 IERS、BLOCKED 公共返回、Review 停止自由补充等 | ✅ 已完成（2026-08-02/03 批次） |
| P1 竞赛核心闭环 | 现实活动时段、三视图、未成年人安全、可执行下一轮输入 | ✅ 已完成（v0.7.0 / v0.8.0，2026-08-03） |
| **P2 智能体交付** | 冻结 Skills 清单、触发条件、Schema；接入 QoderWork 应用内 Skill + MCP；干净安装 | ✅ **本轮完成（v0.9.0，方案 A）**：SKILL.md + MCP 适配层 + 配置模板 + 安装演示指南 + 7 个回归测试 + 录屏凭证流程 |
| P3 固定三案例与真实证据 | 三类完整运行记录、实地/桌面演练、外部复核、来源许可证 | 🟡 部分：案例/验证日志在积累（本次并入 W-1 证据），完整脱敏提交包未开始 |
| P4 提交材料 | 技术报告、20 页内 PDF、6–8 分钟视频、复现包 | ⏳ 未开始 |
| P5 冻结与提交 | 停止加功能、全新环境重装、全量验证、隐私检查 | ⏳ 未开始 |

**当前略超内部倒排（P2 原定 8 月 10 日至 17 日，现提前完成）；P3/P4 为后续主要压力点。**

---

## 三、接下来几周的阶段安排

### P3：固定三案例与真实证据（8 月 14 日至 8 月 22 日）

**目标：** 把三类典型任务变成可提交的脱敏运行记录包。

核心任务：

1. 在 QoderWork 应用内按 `qoderwork-安装演示.md` 跑通 3 组任务，录屏并导出完整运行目录。
2. 将运行目录整理为“输入、中间结果、输出、验证报告、人工确认入口”五件套，标注真实/模拟边界。
3. 对 M31 正常、M42 不可观测、复盘闭环三案例各留一份 `run_outcome.json` 与 `validation_report.md` 快照。
4. 完成来源与许可证清单（Astropy/astroplan/matplotlib/pydantic/dashscope）。
5. 组织一次小规模实地观测或明确标注的桌面演练，留人工确认签名。

**阶段验收：** 每类任务都有完整且可复现的运行记录；视频可用同一批案例。

### P4：制作提交材料（8 月 18 日至 8 月 27 日）

**目标：** 20 页内 PPT/PDF + 6–8 分钟视频 + 技术报告。

核心任务：

1. 以“可信 AI Ready 天文实训闭环”为主线：痛点 → 架构 → 4 Skills → 防幻觉证据链 → 三案例 → QoderWork 调用凭证 → 应用潜力。
2. 视频主线使用 P3 的 QoderWork 录屏素材，展示 Skill 触发、工具调用、产物核对。
3. 技术报告覆盖统一 Schema、Claim Registry、失败处理、MCP 交付与宿主转达合同。

**阶段验收：** 四项评分（科学价值/技术深度/应用潜力）各有直接证据页。

### P5：冻结与提交（8 月 28 日至 8 月 31 日）

**目标：** 停止加功能，第二环境全新安装复跑，冻结提交包。

**阶段验收：** 提交包可打开、可安装、可运行；页数、依赖、许可证、隐私检查通过。

### 阻塞项与风险

- **官方截止 09-05 与内部 09-01 差异**：已核验确认官方 09-05、内部 09-01 冻结，文档基线统一完成；剩余风险仅为提交平台若出现时间差异需再次复核。
- **QoderWork 实际界面差异**：MCP 设置入口与 JSON 编辑器版本可能不同，安装指南已给出官方文档路径，演示前需按现场版本微调。
- **三视图/在线表达**：MCP 工具层固定离线，科普包为确定性模板渲染；若评委期待 Qwen 实时措辞，可在 P3 演示中说明“QoderWork 本体承担语言层，工具层保证数值可信”的分工。
- **真实环境依赖**：干净安装需 Python 3.10+ 与 astropy/astroplan；P5 前必须做第二环境复跑。

---

## 四、立即可做的下一步

1. 在 QoderWork 中按 `qoderwork-安装演示.md` 完成安装，跑通 3 组任务并录屏（P2 验收的最后一步）。
2. 截止日期基线已确认并统一（官方 09-05、内部冻结 09-01）；如提交平台显示的时间与 09-05 不同，再以官网为准复核。
3. 开始 P3：三案例运行记录脱敏包 + 来源许可证清单 + 人工确认。
4. 合并本分支（`codex/p2-qoderwork-delivery`）至 `main` 后，推送错误检查报告与代码，避免积压。
