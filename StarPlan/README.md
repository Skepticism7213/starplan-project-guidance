# 星程 StarPlan Loop

面向 AI 的校园天文观测与科普实训闭环 Skills 包。

StarPlan Loop 将目标解析、可观测性计算、科普活动设计、实际观测记录和偏差复盘封装为 Qwen 智能体可调用的 AI Ready Skills，让一次校园观测活动能够被计划、执行、检查并持续改进。

核心原则：**工具算，模型讲，报告验，人员确认，日志促改进。**

## 快速开始

### 环境要求

- Python >= 3.10
- pip

### 安装

```bash
# 克隆仓库
git clone https://github.com/Skepticism7213/starplan-project-guidance.git
cd starplan-project-guidance/StarPlan

# 安装依赖
pip install -r requirements.txt

# 配置 API Key（用于 Qwen 调用，核心计算不需要）
cp .env.example .env
# 编辑 .env，填入你的 DASHSCOPE_API_KEY

# 若 Key 仅授权 OpenAI 兼容端点下的特定模型（常见于 sk-ws- 开头的 Key），
# 在 .env 中追加：
#   STARPLAN_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
#   STARPLAN_QWEN_MODEL=qwen3.7-plus   # 或 qwen3.8-max 等实际授权模型
#   STARPLAN_QWEN_TIMEOUT=60           # 单次调用超时（秒）
#   STARPLAN_QWEN_RETRIES=1            # 5xx/网络错误重试次数
```

#### Windows 一次性环境初始化

Windows PowerShell 可能把默认 Python 标准输入/输出设为 GBK。项目提供幂等初始化和 UTF-8 运行入口：依赖文件哈希不变时不会重复安装；首次运行会在 `StarPlan/.venv` 创建项目环境。

```powershell
Set-Location StarPlan
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_utf8.ps1 scripts/run_case.py examples/case_01_m31_jinan.json
```

直接调用 Python 做离线检查时也应显式使用 UTF-8 和离线门禁：

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:STARPLAN_MODEL_MODE = "offline"
$env:ASTROPY_CACHE_DIR = Join-Path $env:TEMP "starplan_astropy"
New-Item -ItemType Directory -Force $env:ASTROPY_CACHE_DIR | Out-Null
python -X utf8 -m pytest tests --ignore=tests/test_qwen_integration.py -p no:cacheprovider -q
```

`scripts/run_offline_ci.bat` 已内置同样的代码页、Python UTF-8 和可写临时目录设置。

### 运行案例

```bash
# 案例 1：M31 正常可观测活动（济南四门塔，10月17日）
python scripts/run_case.py examples/case_01_m31_jinan.json

# 案例 2：M42 不适合观测及备选方案（济南四门塔，7月25日）
python scripts/run_case.py examples/case_02_unfavorable_window.json

# 案例 3：实际活动复盘（M31 + 模拟观测日志）
python scripts/run_case.py examples/case_03_observation_review.json

# 完整闭环：计划 → 复盘 → 可执行下一轮输入 → 二次运行 → before/after 对比
python scripts/run_loop.py examples/case_03_observation_review.json
```

每个案例会在 `runs/` 目录下生成独立的输出文件夹，包含：

| 文件 | 内容 |
|---|---|
| `input.json` | 原始输入 |
| `resolved_target.json` | 目标解析结果（坐标、类型、来源） |
| `observability.csv` | 逐 15 分钟高度角/方位角/airmass 数据 |
| `visibility_curve.png` | 高度-时间曲线图 |
| `plan.json` | 观测计划（科学可见窗口 + 现实活动时段 activity_slot、风险、备选方案） |
| `claims.json` | Claim Registry（所有事实声明 + registry_hash） |
| `render_trace.json` | 逐句 provenance trace（schema 2.0，text_hash 对应最终文本） |
| `rendered_document.json` | RenderedDocument 序列化（双向覆盖门禁输入） |
| `sentence_claim_map.json` | 输出句子 → claim_id 映射（覆盖审计） |
| `outreach_pack.md` | 科普活动包-组织者视图（流程、讲解词、设备清单） |
| `outreach_pack_facilitator.md` / `outreach_pack_learner.md` | 讲解员/学习者视图（同一 Claim 来源，按受众筛选板块） |
| `run_outcome.json` | RunOutcome（业务/验证/交付三状态 + 文件哈希） |
| `review_report.md` | 偏差复盘报告（仅案例 3） |
| `revised_plan.json` | 修订后的下一次计划（仅案例 3） |
| `next_activity_input.json` | 可再次进入 runner 的下一轮输入（仅案例 3，通过 StarPlanInput Schema） |
| `loop_before_after.md` | 计划/复盘/二次运行的前后对比（仅 `run_loop.py`） |
| `validation_report.md` | 验证报告 |
| `model_call_log.jsonl` | Qwen 调用审计日志 |

### 验证示例输入

```bash
python scripts/validate_examples.py
```

## 项目结构

```text
StarPlan/
  README.md
  requirements.txt
  skills.yaml                  # Skills 定义文件（v0.8.0 Claim 架构）
  .env.example
  .gitignore
  starplan_skills/
    __init__.py
    encoding.py               # Windows/Python UTF-8 标准输入输出初始化
    schemas.py                 # 统一输入/输出 Pydantic Schema（extra=forbid）
    config.py                  # 配置加载器
    runner.py                  # 总控入口 (starplan.run)
    target_resolve.py          # Skill 1: 目标解析
    observability_plan.py      # Skill 2: 可观测性计算
    outreach_pack.py           # Skill 3: 科普活动包（Claim 渲染）
    observation_review.py      # Skill 4: 观测复盘（Evidence Claim 归因）
    claims.py                  # Claim Registry 构建器
    expression_validator.py    # ExpressionPlan 8 步验证
    templates.py               # 句子变体模板库 + 连接器
    run_outcome.py             # RunOutcome 三状态落盘
    validation.py              # 验证工具
    qwen_client.py             # Qwen/百炼 API 调用封装
  data/
    built_in_catalog_v1.json   # 内置目标目录（110 Messier + 40 亮星）
    locations_v1.json          # 内置地点表（8 个城市）
    constraints_config.yaml    # 观测约束阈值配置
  examples/
    case_01_m31_jinan.json
    case_02_unfavorable_window.json
    case_03_observation_review.json
  scripts/
    bootstrap_windows.ps1     # 幂等创建 .venv，并按 requirements 哈希安装一次
    run_utf8.ps1              # 使用项目环境和 UTF-8 执行 Python 脚本
    run_case.py
    validate_examples.py
  runs/                        # 运行输出（gitignore）
  docs/
```

## 四个核心 Skill

| Skill | 职责 | 输入 | 输出 |
|---|---|---|---|
| `target_resolve` | 解析目标名称为标准坐标 | 目标名称 | 标准名、坐标、类型、置信度 |
| `observability_plan` | 计算可观测性并生成计划 | 坐标、地点、日期、设备 | 可见窗口、高度/方位、airmass、风险、blocking_reasons |
| `outreach_pack` | 基于 Claim Registry 确定性渲染科普活动包 | Claim Registry、受众、设备 | 活动流程、讲解词、设备清单、sentence_claim_map |
| `observation_review` | 复盘偏差并修订计划（Evidence Claim 归因） | 原计划、观测日志、log_path、原始输入 | 偏差分类、证据 Claims、修订计划、可执行下一轮输入 |

## 技术依赖

| 依赖 | 用途 | 许可证 |
|---|---|---|
| Astropy | 天体坐标框架、时间系统 | BSD 3-Clause |
| astroplan | 观测约束计算 | BSD 3-Clause |
| matplotlib | 可视化图表 | PSF (permissive) |
| pydantic | Schema 验证 | MIT |
| dashscope | 阿里云百炼 API | Apache 2.0 |

所有天文计算使用 Astropy/astroplan 离线完成，不依赖在线天文服务。Qwen 仅用于自然语言理解和科普表达，不生成天文数值。

## 证据链架构（Claim Registry）

自 v0.2.0 起，所有用户可见的事实性输出均经过 Claim 证据链门禁：

1. **Claim 构建**：`AllowedClaimsBuilder` 从确定性计算结果（Astropy/astroplan）生成带来源引用的 Claim，每个 Claim 有唯一 ID、作用域、来源哈希和允许的变体列表。文档元数据（标题、受众、日期、地点、状态）也是 Claim。
2. **表达计划**：Qwen 仅返回 `ExpressionPlan`（选择 claim_id + sentence_variant_id），不返回自由文本。`ExpressionPlan` 设为 `extra=forbid`，拒绝协议外字段。
3. **8 步验证**：`expression_validator` 对 ExpressionPlan 做 schema/版本/claim 存在性/变体合法性/作用域/禁用检查/重复冲突/哈希完整性验证。任何错误触发 fail-closed 回退。
4. **确定性渲染**：`render_document()` 从 Claim Registry 生成 `RenderedDocument`（唯一文档出口），每个原子文本为 `RenderedBlock`（claim_ids + variant_id + text_hash）。`serialize_document_md()` 只接受 RenderedDocument，禁止接触原始计算对象。
5. **交付合同门禁**：`validate_delivery_contract()` 在 finalize 前做 7 步 post-render 验证（产物存在/JSON 合法/Claim 存在/variant allowlist/hash 一致/双向覆盖/泄漏检查）。任何失败 → `BLOCKED` + `NOT_DELIVERED`，删除已写 Markdown。
6. **RunOutcome 落盘**：每次运行生成 `run_outcome.json`，包含业务状态、验证状态、交付状态（三者正交）、文件哈希和约束记录。Chat 与结构化入口共享相同合同。
7. **BLOCKED 公共返回合同**：验证失败（`validation_status=blocked` / `delivery_status=not_delivered`）时，结构化入口与 Chat 的公共返回中 `outreach_pack` 为 `None`，即 **0 条交付事实**——没有活动包、事实句或被阻断的模型原文；磁盘上的 `outreach_pack.md` 同时删除。返回值中的 `target` 与 `plan` 保留，它们是确定性工具的**计算中间结果**（输入解析与业务状态判断的依据），不属于"交付给用户的事实内容"；调用方应读取 `validation_status` / `delivery_status` 字段判断本次运行是否实际交付。该口径由项目负责人确认（2026-08-04），对应审查项 W-7。

派生规则（肉眼可见性、双筒可见性、新手友好度）显式标注适用范围和缺失输入。深空天体在角径不足或天空背景数据缺失时标记为 `UNCONFIRMED`，不做过度承诺。

## 当前 MVP 限制

- 仅支持单晚观测：`date_range` 传入多天时只计算第一晚，接口和报告均显式声明此限制。
- 折射策略：`astropy_default`（pressure=0，不启用大气折射），已写入 RunOutcome。
- 不含行星实时历表、实时天气 API、Stellarium/Aladin 集成和复杂前端。
- 可见性派生规则基于视星等阈值 + 角径，未建模天空背景、表面亮度、消光和观测经验。
- 现实活动时段（`activity_slot_policy_v1`）默认 90 分钟（60-120 可配），由科学窗口确定性生成；未成年人活动启用 `youth_activity_policy_v1` 安全项与人工确认清单（监护人许可、成人陪同、点名），不采集任何隐私信息。

## 协作规范

### 分支策略

| 成员 | 分支 | 负责文件 |
|---|---|---|
| A | `feature/validation-cases` | `examples/`、`validation.py` |
| B | `feature/observability` | `observability_plan.py`、规则测试 |
| C | `feature/targets-display` | `target_resolve.py`、目标目录 |
| D | `feature/qwen-runner` | `runner.py`、`outreach_pack.py`、`skills.yaml` |
| E | `feature/review-demo` | `observation_review.py`、`README.md` |

### 规则

- 先冻结 Schema，再分头开发
- 每人只改自己负责的模块
- 输入输出格式变更必须同步 `skills.yaml` 和示例 JSON
- API Key 不进仓库，用 `.env`
- `main` 分支必须始终能跑通 3 个案例
- 每周至少一次集成测试

### 集成验证

```bash
python scripts/run_case.py examples/case_01_m31_jinan.json
python scripts/run_case.py examples/case_02_unfavorable_window.json
python scripts/run_case.py examples/case_03_observation_review.json
```

检查每个 `runs/` 子目录是否包含完整输出文件。

## 架构验收状态（2026-08-03 更新）

基于 2026-08-01 独立审计报告（6 CRITICAL + 4 WARNING），Phase A-D 修复已完成：

| Phase | 关闭项 | 状态 |
|---|---|---|
| A | C-01（100% Claim-to-render 映射 + RenderedDocument）、C-02（fail-closed 运行时门禁）、W-03（trace 排序） | 已验证通过 |
| B | C-03（Chat 统一 Claim 出口）、W-01（model-call 聚合）、W-02（测试契约） | 已验证通过 |
| C | C-04（复盘 Evidence Claim ID + 精确因果链）、W-04（异常审计） | 已验证通过 |
| D | C-05（无天气源禁止具体温度）、C-06（极昼 no_astronomical_night 原因码） | 已验证通过 |

P0 Runtime Contract Closure（R1-R3）已在独立分支完成本地验收：Chat/结构化入口的模型证据损坏会 fail-closed，Claims 磁盘篡改经过交付合同门禁，Review 默认 deterministic-only，直接 `observability_plan` 记录离线运行策略。

离线回归（即使本机存在 `.env` 也禁止联网）应先设置 `STARPLAN_MODEL_MODE=offline`，再执行 `python -m pytest tests --ignore=tests/test_qwen_integration.py -p no:cacheprovider -q`；本机当前结果为 **211 passed, 0 failed，71.61s**。需要真实百炼 API 的在线测试单独执行；无 Key 的环境可能显示 9 skipped，有 Key 但未隔离时会尝试联网。完整复现边界见 `../starplan-project-guidance/starplan-error-check-and-phase-plan-2026-08-03-local-reproducibility-recheck.md`。

**2026-08-03 在线修复（v0.6.0）：**

- 新增 OpenAI 兼容端点适配：`STARPLAN_QWEN_BASE_URL` / `STARPLAN_QWEN_MODEL` / 超时与重试环境变量；兼容模式下 `call_qwen` / `call_qwen_json` / `call_qwen_chat` 走 `chat/completions`，原生 DashScope 路径保持不变。
- Chat 模式地点名归一化：`observability_plan` 优先使用 `resolve_location` 返回的标准化地点名，修复真实 Qwen 传入用户原话导致 Claim 范围校验全挂的问题（原 53 项 Saved registry violation）。
- Chat 工具轮次上限从 3 提升到 6，适配每轮只调用一个工具的真实模型。
- 收紧程序性日程 Claim 的变体白名单（如 `schedule.obs_guide` 不再允许 `schedule_obs_start_v1`），避免"开始观测 引导成员…"式别扭句子。
- 新增 `StarPlan/.env.example` 与 10 个回归测试（兼容客户端 + Chat 地点/轮次）。
- 本机通过代理对 `qwen3.7-plus` / `qwen3.7-max` / `qwen3.8-max` 完成 canary；项目自带在线集成套件在显式可写 `--basetemp` 下为 **9 passed，172.92s**。在线结果依赖 Key、模型权限和网络，不替代离线回归。

**P1 Batch D（v0.7.0，2026-08-03）：**

- 现实活动时段：`activity_slot_policy_v1` 从科学窗口确定性生成 60-120 分钟活动时段（含准备/收尾），M31 案例活动流程为 18:58 准备 → 19:13-20:43 观测 → 20:58 收尾，不再出现"通宵式"安排；科学窗口仍在"推荐观测时段"独立展示。
- 三类分众视图：同一 Claim Registry 生成组织者（`outreach_pack.md`）、讲解员（`outreach_pack_facilitator.md`）、学习者（`outreach_pack_learner.md`）三种视图，事实句与数字映射同一 claim_id；每视图独立 rendered_document/trace/map，并纳入交付合同校验。
- 未成年人安全策略：`youth_activity_policy_v1` 在受众为中小学生/儿童时追加监护人许可、成人陪同、点名等安全项与人工确认清单，不采集隐私字段。
- 新增 10 个 Batch D 回归测试；版本统一为 0.7.0。

**P1 Batch E（v0.8.0，2026-08-03）：**

- 复盘生成可执行下一轮输入：`observation_review` 接收原始 `StarPlanInput`，按白名单（`activity_preferences.*`）应用证据支持的修订（如迟到 → 推迟 `preferred_start`），移除 `observation_log` 后写出 `next_activity_input.json`；自由建议不进入 Schema 字段。
- 二次运行与 before/after：`scripts/run_loop.py` 显式读取下一轮输入并重跑 runner，生成 `loop_before_after.md`（证据修订表 + 活动时段/流程前后对比，每项引用 cause_id）；`run_starplan` 不做隐式递归。
- 证据边界：结构化时间差是唯一延迟证据来源；删除延迟证据后 `preferred_start` 补丁自动消失；无原始输入时不生成下一轮输入。
- 新增 6 个 Batch E 回归测试；离线回归 211 passed；在线测试与离线门禁分开执行；版本统一为 0.8.0。

**关键架构组件：**

- `RenderedDocument`：最终文档级结构，每个原子文本为 `RenderedBlock`（claim_ids + variant_id + text_hash）
- `validate_delivery_contract()`：7 步 post-render 门禁（产物存在/JSON 合法/Claim 存在/variant allowlist/hash 一致/双向覆盖/泄漏检查），失败 → BLOCKED + NOT_DELIVERED
- `not_observable_reason` 优先级：latitude → no_astronomical_night → altitude → moonlight
- 复盘 trace schema 2.0：所有条目使用稳定 ID（cause_id/deviation_id/source_cause_ids）

**尚未完全闭合的项目（诚实标注）：**

- 复盘 Qwen 完整 ID-only 协议（候选原因模板库 + 建议模板库）未实现；当前版本默认不调用 Qwen，保留 helper 仅供 P1 协议实现
- review report 未使用 RenderedDocument + 双向覆盖门禁（outreach 已实现）
- 天气 Claim 接入后需恢复具体温度显示（当前为非事实化操作指令）
- 六类终态参数化 E2E 矩阵仍需在独立环境复跑确认；本地 R1-R3 已有真实入口对抗测试
- 真实在线验证依赖百炼 Key 的授权模型与端点（sk-ws- Key 通常需兼容端点）；现场演示前须用团队实际 Key 复跑并录制调用凭证

## 赛项信息

- 挑战杯"揭榜挂帅"阿里云榜题
- 赛道三方向三：星语·面向 AI 的天文实训
- 截止日期：2026-09-01
