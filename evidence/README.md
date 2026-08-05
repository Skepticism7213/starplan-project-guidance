# 三案例完整运行记录包（P3 证据）

本目录是赛题要求的“三类典型任务完整运行记录”提交快照。所有文件从
`StarPlan/runs/` 中三个标准运行复制而来（`runs/` 被 gitignore，不能直接提交，
因此这里保留可提交版本），并通过 `evidence_manifest.json` 记录每个文件的
SHA-256 前缀，用于完整性核验。

## 包结构

```text
evidence/
  README.md                        # 本指南
  evidence_manifest.json           # 总清单：运行 ID、文件哈希、状态
  source_license_inventory.md      # 来源与许可证清单
  second_environment_repro.md      # 第二环境复跑记录（模板）
  case_01_m31_normal/              # 案例一：M31 正常可观测
  case_02_m42_unfavorable/         # 案例二：M42 不可观测及备选
  case_03_m31_review_loop/         # 案例三：复盘闭环 + 二次运行
```

每个案例目录包含：

| 类别 | 文件 | 说明 |
|---|---|---|
| 输入 | `input.json` | 与运行完全一致的原始输入（含观测日志的为 `observation_log.json`） |
| 中间结果 | `resolved_target.json`、`observability.csv`、`visibility_curve.png`、`claims.json`、`expression_plan.json`、`render_trace*.json`、`sentence_claim_map*.json` | 目标解析、逐 15 分钟数据、曲线、Claim Registry 与渲染追踪 |
| 最终输出 | `plan.json`、`outreach_pack*.md` | 观测计划与三视图活动包（案例二仅有组织者视图，属不可观测设计） |
| 验证 | `validation_report.md`、`run_outcome.json`、`calculation_manifest.json`、`model_call_log.jsonl` | 验证报告、三状态运行结果、计算清单、模型调用审计 |
| 复盘闭环 | `review_report.md`、`review_trace.json`、`revised_plan.json`、`next_activity_input.json`、`loop_before_after.md`、`second_plan.json`、`second_run_outcome.json` | 仅案例三：复盘、归因、下一轮输入、二次运行对比 |
| 人工确认 | `human_confirmation.md` | 待签名的确认清单（重建时不会被覆盖） |

## 一键重建（操作指示）

### 前提

1. 三个标准运行存在于 `StarPlan/runs/`：
   - `m31_济南-四门塔_20261017_170745`
   - `m42_济南-四门塔_20260725_172320`
   - `m31_济南-四门塔_20261017_184517_review`
2. 案例三的二次运行目录存在：`m31_review_20261017_184517_next`
   （不存在时先执行下面的“补跑第二轮”）。

### 补跑案例三第二轮

```powershell
$env:STARPLAN_MODEL_MODE = "offline"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
StarPlan\.venv\Scripts\python.exe -X utf8 -c @"
import json, sys
from pathlib import Path
sys.path.insert(0, "StarPlan")
from starplan_skills.runner import run_starplan
p = next(x for x in Path("StarPlan/runs").iterdir()
         if x.name.endswith("_184517_review") and x.is_dir())
nxt = json.loads((p / "next_activity_input.json").read_text(encoding="utf-8"))
res = run_starplan(nxt, run_id="m31_review_20261017_184517_next")
print(res["run_id"], res["validation_status"], res["plan"]["activity_slot"]["start"])
"@
```

预期输出结尾：`m31_review_20261017_184517_next passed 2026-10-17T19:45:00`。

### 重建证据包

```powershell
StarPlan\.venv\Scripts\python.exe -X utf8 StarPlan\scripts\build_evidence_pack.py
```

- 重复执行是幂等的：产物会被刷新，`human_confirmation.md` 若已存在不会被覆盖。
- 若误删了人工确认模板，加 `--force` 重新生成（会覆盖旧签名，慎用）。
- 脚本对缺失文件会打印 `[WARN]`，并以非零码退出；正常输出为
  `case_01: 18 files / case_02: 16 files / case_03: 25 files`。

## 人工确认流程

1. 打开每个 `case_XX/human_confirmation.md`。
2. 标注确认性质：真实观测 / 模拟演示 / 混合（必须诚实标注，模拟不冒充真实）。
3. 逐项打勾并填写日期、确认人、备注。
4. 未成年人场景（若适用）单独确认监护人许可、成人陪同、点名流程。
5. 确认后保留签名，重新提交仓库。

## 第二环境复跑

在另一台电脑或全新 venv 上按 `StarPlan/README.md` 安装后：

1. 运行 `StarPlan\scripts\run_offline_ci.bat`（或等价离线命令）。
2. 分别运行三个案例：`run_case.py examples/case_01_m31_jinan.json` 等。
3. 用 `evidence/second_environment_repro.md` 模板记录环境、命令、测试数。
4. 哈希对比使用 `StarPlan\scripts\compare_evidence_hashes.py`：

```powershell
StarPlan\.venv\Scripts\python.exe -X utf8 StarPlan\scripts\compare_evidence_hashes.py `
  --case case_01_m31_normal --run-dir "StarPlan\runs\<new_run_dir>"
```

脚本区分三类文件：STRICT（必须字节一致）、TOLERANT（时间戳/绝对路径/图表字节
允许不同）、VALUE（字节可不同但科学字段必须一致）。案例三加
`--second-run-dir`。退出码 0/1/2 分别表示通过/STRICT 失败/数值失败。

## 外部科学复核

请一位非团队成员（老师、学长、天文爱好者）独立核对以下数值：

- 案例一：M31 坐标（RA 10.6847° / Dec 41.2688°）、科学窗口 19:13–04:28、峰值高度 85°。
- 案例二：M42 当晚最高高度 -5.7°、备选 M29/M57 窗口。
- 案例三：延迟 31 分钟、修订后的 preferred_start 19:45。

复核意见记录在对应 `human_confirmation.md` 的备注区。

## 提交前检查清单

- [ ] `evidence_manifest.json` 中三个案例状态均为 `ok`，文件数与预期一致。
- [ ] 每个案例都有 `input / 中间结果 / 输出 / 验证报告 / 人工确认` 五类文件。
- [ ] `human_confirmation.md` 已签名且真实/模拟边界标注清楚。
- [ ] `source_license_inventory.md` 与 `second_environment_repro.md` 已填写。
- [ ] 无 API Key、token、私人数据出现在任何证据文件（提交前跑密钥扫描）。
- [ ] 三案例运行目录、视频录屏与本文档使用的 run_id 一致。
