# 第二环境复跑记录（模板）

> 目的：证明提交包在干净环境可安装、可运行、可复现。请逐项填写并签名。

## 1. 环境信息

- 复跑日期：____
- 复跑人：____
- 操作系统及版本：____
- Python 版本：`python --version` → ____
- pip 版本：`pip --version` → ____
- 关键依赖版本：`pip show astropy astroplan pydantic dashscope matplotlib` 的结果贴于下方或附件。
- 是否全新环境（未复用本机缓存/venv）：□ 是　□ 否（说明：____）

## 2. 安装复现

```text
git clone https://github.com/Skepticism7213/starplan-project-guidance.git
cd starplan-project-guidance/StarPlan
pip install -r requirements.txt
```

- 安装是否一次成功：□ 是　□ 否（错误信息：____）
- Windows 是否使用 `scripts/bootstrap_windows.ps1`：□ 是　□ 否

## 3. 离线回归

```text
StarPlan\scripts\run_offline_ci.bat
```

- 测试结果：____ passed / ____ failed / ____ skipped
- 与本仓库记录的 237 passed 是否一致：□ 是　□ 否（差异说明：____）

## 4. 三案例复跑

| 案例 | 命令 | validation_status | activity_slot | 与 evidence 哈希对比 |
|---|---|---|---|---|
| 案例一 | `run_case.py examples/case_01_m31_jinan.json` | ____ | ____ | □ 一致 □ 不一致 |
| 案例二 | `run_case.py examples/case_02_unfavorable_window.json` | ____ | ____ | □ 一致 □ 不一致 |
| 案例三 | `run_case.py examples/case_03_observation_review.json` | ____ | ____ | □ 一致 □ 不一致 |

每个案例复跑后会生成新的运行目录（如 `StarPlan/runs/m31_..._<新时间戳>`）。
案例三还需要按 `evidence/README.md` 的“补跑第二轮”步骤生成第二轮目录。

### 4.1 一键哈希对比（推荐）

仓库提供跨平台对比脚本，会自动区分“必须字节一致的文件”与“允许字节差异
但关键字段必须一致的文件”：

```powershell
# 案例一 / 案例二（把 <new_run_dir> 换成新环境实际生成的目录）
StarPlan\.venv\Scripts\python.exe -X utf8 StarPlan\scripts\compare_evidence_hashes.py `
  --case case_01_m31_normal --run-dir "StarPlan\runs\<new_run_dir>"

StarPlan\.venv\Scripts\python.exe -X utf8 StarPlan\scripts\compare_evidence_hashes.py `
  --case case_02_m42_unfavorable --run-dir "StarPlan\runs\<new_run_dir>"

# 案例三（第一轮复盘目录 + 第二轮目录）
StarPlan\.venv\Scripts\python.exe -X utf8 StarPlan\scripts\compare_evidence_hashes.py `
  --case case_03_m31_review_loop `
  --run-dir "StarPlan\runs\<new_review_run_dir>" `
  --second-run-dir "StarPlan\runs\<new_second_run_dir>"
```

输出解读：

- `[OK]`：该文件一致（或字节不同但关键字段一致）。
- `[DIFF]`：字节不同，属于预期内差异（时间戳/绝对路径/图表渲染等），不需处理。
- `[FAIL] STRICT 不一致`：必须排查（输入、星表、代码版本或克隆不完整）。
- `[FAIL] 科学/状态字段不一致`：必须排查（窗口、活动时段、状态等数值不同）。

退出码：`0` 全部通过；`1` STRICT 不一致；`2` 数值字段不一致。

### 4.2 手动核对（可选）

`Get-FileHash <file> -Algorithm SHA256` 取前 16 位，与
`evidence/evidence_manifest.json` 的 `sha256_prefix` 比对；只对
`input.json`、`resolved_target.json`、`observability.csv`、
`outreach_pack*.md` 等确定性产物做字节比对，`plan.json`/`run_outcome.json`
应比较科学字段而非字节。

## 5. 差异与问题记录

- 发现的问题：____
- 是否影响结果正确性：□ 不涉及　□ 涉及（说明：____）

## 6. 结论

□ 复现成功：新环境可安装、可运行，三案例结果与提交包一致。
□ 复现成功但存在已说明差异（见第 5 节）。
□ 复现失败（阻塞项：____）。

- 签名：____
