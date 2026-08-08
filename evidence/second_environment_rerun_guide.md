# 第二环境重跑操作手册（修复后验收）

> 给第二环境负责人。目标：在**修复后的最新 main** 上重新执行一次干净环境
> 复跑，证明跨环境比较问题已修复，并把结果写回仓库。

## 1. 背景与验收标准

上一轮（2026-08-06）复跑在基线 `b0ee771` 上发现：三案例哈希对比全部失败，
原因包括 JSON 序列化差异、Claim 哈希链级联、案例三输入漂移和三视图缺失。
修复已合入 `main`（提交 `87624af`，改动 `13f02d4`），本次复跑验收标准：

- [ ] 全新环境离线回归 **242 passed / 0 failed / 0 skipped**
- [ ] 三案例哈希对比退出码均为 **0**（案例三含第二轮）
- [ ] evidence 中无本机绝对路径
- [ ] 复跑记录已更新并推送到仓库

## 2. 准备环境

### 2.1 克隆/更新仓库（必须是最新 main）

```bash
git clone https://github.com/Skepticism7213/starplan-project-guidance.git
cd starplan-project-guidance
git checkout main
git pull
git rev-parse HEAD
```

**记录提交号**。当前应为 `87624af`（若主仓库有新提交，以实际为准并记录）。

> 如果克隆时出现 `CRYPT_E_NO_REVOCATION_CHECK` 之类的 TLS 错误，可临时用
> `GIT_SSL_NO_VERIFY=1` 完成本次克隆，并在本地执行
> `git config --local http.sslVerify false`；这只是你机器的临时绕过，
> **不要**把它写进任何脚本或提交配置。

### 2.2 创建全新虚拟环境（不要复用旧 .venv）

```bash
cd StarPlan
python -m venv .venv
# Windows:
.venv\Scripts\pip install -r requirements.txt
# macOS / Linux:
.venv/bin/pip install -r requirements.txt
```

记录环境信息（写入 `evidence/second_environment_repro.md` 第 1 节）：

```bash
python --version
pip --version
.venv\Scripts\pip freeze > StarPlan\second_venv_pip_freeze.txt
```

建议使用与首次复跑接近的 Python 3.14（requirements 范围内均可，版本差异会在
哈希对比中按 TOLERANT 处理，但请如实记录）。

## 3. 离线回归

Windows 可直接用项目自带脚本：

```powershell
cd StarPlan
scripts\run_offline_ci.bat
```

或手动执行（macOS/Linux 用等价命令）：

```bash
.venv\Scripts\python -X utf8 -m compileall starplan_skills scripts tests -q
.venv\Scripts\python -X utf8 scripts/validate_examples.py
STARPLAN_MODEL_MODE=offline .venv\Scripts\python -X utf8 -m pytest tests/ -p no:capture --ignore=tests/test_qwen_integration.py -q --tb=short
```

期望结果：**242 passed / 0 failed / 0 skipped**。把完整输出保存为
`StarPlan/pytest_second_env.log`（PowerShell：`... | Tee-Object -FilePath pytest_second_env.log`）。

## 4. 三案例复跑（全部在离线模式）

```powershell
$env:STARPLAN_MODEL_MODE = "offline"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

.venv\Scripts\python -X utf8 scripts\run_case.py examples\case_01_m31_jinan.json
.venv\Scripts\python -X utf8 scripts\run_case.py examples\case_02_unfavorable_window.json
.venv\Scripts\python -X utf8 scripts\run_case.py examples\case_03_observation_review.json
```

**记下三个新生成的 run 目录名**（例如 `m31_济南-四门塔_20261017_093435`）。
案例三应生成 29 个文件并识别 3 项偏差（开始延迟 + 云量 + 三脚架）。

## 5. 案例三第二轮（补跑）

```powershell
.venv\Scripts\python.exe -X utf8 -c @"
import json, sys
from pathlib import Path
sys.path.insert(0, "StarPlan")
from starplan_skills.runner import run_starplan
p = next(x for x in Path("StarPlan/runs").iterdir()
         if x.name.endswith("_review") and x.is_dir())
nxt = json.loads((p / "next_activity_input.json").read_text(encoding="utf-8"))
res = run_starplan(nxt, run_id="m31_review_20261017_next")
print(res["run_id"], res["validation_status"], res["plan"]["activity_slot"]["start"])
"@
```

期望输出结尾：`m31_review_20261017_next passed 2026-10-17T19:30:00`
（`activity_slot.start` 为 19:30，对应修订后的 `preferred_start`）。

> 注意：该 glob 会匹配第一个 `_review` 目录；如果 runs 里已有旧复盘目录，
> 请先把旧目录移走，或把命令里的 `endswith("_review")` 改为你刚生成的
> 精确目录名（用 `_154934_review` 这类后缀）。

## 6. 哈希对比（关键验收步骤）

```powershell
.venv\Scripts\python.exe -X utf8 StarPlan\scripts\compare_evidence_hashes.py `
  --case case_01_m31_normal --run-dir "StarPlan\runs\<案例一新目录>"

.venv\Scripts\python.exe -X utf8 StarPlan\scripts\compare_evidence_hashes.py `
  --case case_02_m42_unfavorable --run-dir "StarPlan\runs\<案例二新目录>"

.venv\Scripts\python.exe -X utf8 StarPlan\scripts\compare_evidence_hashes.py `
  --case case_03_m31_review_loop `
  --run-dir "StarPlan\runs\<案例三复盘目录>" `
  --second-run-dir "StarPlan\runs\m31_review_20261017_next"
```

结果解读：

- 退出码 **0**：通过（STRICT 字节一致；VALUE 语义/关键字段一致；TOLERANT 差异预期内）。
- 退出码 **1**：必需产物缺失或 STRICT 不一致 → **不要改脚本或 evidence**，
  把完整输出贴回主负责人。
- 退出码 **2**：科学/状态字段不一致 → 同样贴回完整输出。

允许出现的 `[DIFF]`（预期内，不用管）：`validation_report.md`、
`calculation_manifest.json`、`model_call_log.jsonl`、`state_log.json`、
`review_report.md`、`observability.csv`、`visibility_curve.png`。

## 7. 更新复跑记录并提交

### 7.1 填写 `evidence/second_environment_repro.md`

- 第 1 节：复跑日期、操作系统、Python/pip/依赖版本（引用新的
  `second_venv_pip_freeze.txt`）。
- 第 2 节：基线提交号改为本次实际 `git rev-parse HEAD`。
- 第 3 节：测试结果改为 242 passed / 0 failed / 0 skipped。
- 第 4 节：填入三案例实际 run_id、`validation_status`、`activity_slot`；
  4.1 填三案例对比退出码与主要 [OK]/[DIFF] 概况。
- 第 5 节：本次应写“无未说明差异”；如仍有差异，逐条记录原因。
- 第 6 节：勾选“复现成功”，签名改回人工确认（不要写“QoderWork 自动化”）。

### 7.2 提交推送

```bash
git add evidence/second_environment_repro.md StarPlan/pytest_second_env.log StarPlan/second_venv_pip_freeze.txt
git switch -c codex/second-env-rerun-2026-08-08
git commit -m "Second environment rerun on 87624af: 242 passed, compare 0/0/0"
git push -u origin codex/second-env-rerun-2026-08-08
```

推送后把分支名告诉主负责人（由主负责人合入 main，避免直接改主分支）。

## 8. 交回给主负责人的材料清单

- [ ] 更新后的 `evidence/second_environment_repro.md`
- [ ] `StarPlan/pytest_second_env.log`（242 passed 完整日志）
- [ ] `StarPlan/second_venv_pip_freeze.txt`
- [ ] 三案例实际 run_id 列表 + 第二轮 run_id
- [ ] 三案例 compare 命令的退出码（0/0/0）与输出文本（可贴关键行）

## 9. 常见问题

| 现象 | 处理 |
|---|---|
| 克隆 TLS 报错 | 见 2.1 的临时绕过，仅限本机，不进代码 |
| pytest 临时目录权限错误（Windows） | 用 `scripts/run_offline_ci.bat`，或设置 `PYTEST_BASETEMP` 为可写目录 |
| 输出中文乱码 | 已通过 `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` 处理 |
| compare 报 STRICT 失败 | 不要改脚本/evidence；把完整输出发回主负责人 |
| 找不到 `_review` 目录 | 先确认案例三已运行；再按第 5 节备注精确指定目录 |
| 是否需要重建 evidence | **不需要**。第二环境只验证，evidence 由主仓库维护 |
