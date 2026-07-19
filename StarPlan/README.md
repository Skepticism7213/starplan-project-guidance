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
| `calculation_manifest.json` | 计算证据清单（工具版本、约束、中间文件） |
| `observability.csv` | 逐 15 分钟高度角/方位角/airmass 数据 |
| `visibility_curve.png` | 高度-时间曲线图 |
| `plan.json` | 观测计划（推荐窗口、风险、备选方案） |
| `outreach_pack.md` | 科普活动包（流程、讲解词、设备清单） |
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
  skills.yaml                  # Skills 定义文件
  .env.example
  .gitignore
  starplan_skills/
    __init__.py
    schemas.py                 # 统一输入/输出 Pydantic Schema
    config.py                  # 配置加载器
    runner.py                  # 总控入口 (starplan.run)
    target_resolve.py          # Skill 1: 目标解析
    observability_plan.py      # Skill 2: 可观测性计算
    outreach_pack.py           # Skill 3: 科普活动包
    observation_review.py      # Skill 4: 观测复盘
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
| `observability_plan` | 计算可观测性并生成计划 | 坐标、地点、日期、设备 | 可见窗口、高度/方位、airmass、风险 |
| `outreach_pack` | 生成科普活动包 | 事实卡、受众、设备 | 活动流程、讲解词、设备清单 |
| `observation_review` | 复盘偏差并修订计划 | 原计划、观测日志 | 偏差分类、证据、修订计划 |

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

## 赛项信息

- 挑战杯"揭榜挂帅"阿里云榜题
- 赛道三方向三：星语·面向 AI 的天文实训
- 截止日期：2026-09-01
