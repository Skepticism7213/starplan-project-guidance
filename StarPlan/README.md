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

### 运行案例

```bash
# 案例 1：M31 正常可观测活动（济南四门塔，10月17日）
python scripts/run_case.py examples/case_01_m31_jinan.json

# 案例 2：M42 不适合观测及备选方案（济南四门塔，7月25日）
python scripts/run_case.py examples/case_02_unfavorable_window.json

# 案例 3：实际活动复盘（M31 + 模拟观测日志）
python scripts/run_case.py examples/case_03_observation_review.json
```

每个案例会在 `runs/` 目录下生成独立的输出文件夹，包含：

| 文件 | 内容 |
|---|---|
| `input.json` | 原始输入 |
| `resolved_target.json` | 目标解析结果（坐标、类型、来源） |
| `observability.csv` | 逐 15 分钟高度角/方位角/airmass 数据 |
| `visibility_curve.png` | 高度-时间曲线图 |
| `plan.json` | 观测计划（推荐窗口、风险、备选方案） |
| `claims.json` | Claim Registry（所有事实声明 + registry_hash） |
| `render_trace.json` | 逐句 provenance trace（schema 2.0，text_hash 对应最终文本） |
| `rendered_document.json` | RenderedDocument 序列化（双向覆盖门禁输入） |
| `sentence_claim_map.json` | 输出句子 → claim_id 映射（覆盖审计） |
| `outreach_pack.md` | 科普活动包（流程、讲解词、设备清单） |
| `run_outcome.json` | RunOutcome（业务/验证/交付三状态 + 文件哈希） |
| `review_report.md` | 偏差复盘报告（仅案例 3） |
| `revised_plan.json` | 修订后的下一次计划（仅案例 3） |
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
  skills.yaml                  # Skills 定义文件（v0.6.0 Claim 架构）
  .env.example
  .gitignore
  starplan_skills/
    __init__.py
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
| `observation_review` | 复盘偏差并修订计划（Evidence Claim 归因） | 原计划、观测日志、log_path | 偏差分类、证据 Claims、修订计划 |

## 技术依赖

| 依赖 | 用途 | 许可证 |
|---|---|---|
| Astropy | 天体坐标框架、时间系统 | BSD 3-Clause |
| astroplan | 观测约束计算 | BSD 3-Clause |
| matplotlib | 可视化图表 | PSF (permissive) |
| pandas | CSV 数据处理 | BSD 3-Clause |
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

派生规则（肉眼可见性、双筒可见性、新手友好度）显式标注适用范围和缺失输入。深空天体在角径不足或天空背景数据缺失时标记为 `UNCONFIRMED`，不做过度承诺。

## 当前 MVP 限制

- 仅支持单晚观测：`date_range` 传入多天时只计算第一晚，接口和报告均显式声明此限制。
- 折射策略：`astropy_default`（pressure=0，不启用大气折射），已写入 RunOutcome。
- 不含行星实时历表、实时天气 API、Stellarium/Aladin 集成和复杂前端。
- 可见性派生规则基于视星等阈值 + 角径，未建模天空背景、表面亮度、消光和观测经验。

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

离线测试：195 passed, 9 skipped, 0 failed（跳过需要真实百炼 API 的在线测试；完整证据见 `../starplan-project-guidance/starplan-error-check-and-phase-plan-2026-08-03-p0-runtime-contract-closure-independent-recheck.md`）。

**2026-08-03 在线修复（v0.6.0）：**

- 新增 OpenAI 兼容端点适配：`STARPLAN_QWEN_BASE_URL` / `STARPLAN_QWEN_MODEL` / 超时与重试环境变量；兼容模式下 `call_qwen` / `call_qwen_json` / `call_qwen_chat` 走 `chat/completions`，原生 DashScope 路径保持不变。
- Chat 模式地点名归一化：`observability_plan` 优先使用 `resolve_location` 返回的标准化地点名，修复真实 Qwen 传入用户原话导致 Claim 范围校验全挂的问题（原 53 项 Saved registry violation）。
- Chat 工具轮次上限从 3 提升到 6，适配每轮只调用一个工具的真实模型。
- 收紧程序性日程 Claim 的变体白名单（如 `schedule.obs_guide` 不再允许 `schedule_obs_start_v1`），避免"开始观测 引导成员…"式别扭句子。
- 新增 `StarPlan/.env.example` 与 10 个回归测试（兼容客户端 + Chat 地点/轮次）。

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
