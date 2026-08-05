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

哈希对比方法：`Get-FileHash <file> -Algorithm SHA256`，取前 16 位与
`evidence/evidence_manifest.json` 的 `sha256_prefix` 比对。

## 5. 差异与问题记录

- 发现的问题：____
- 是否影响结果正确性：□ 不涉及　□ 涉及（说明：____）

## 6. 结论

□ 复现成功：新环境可安装、可运行，三案例结果与提交包一致。
□ 复现成功但存在已说明差异（见第 5 节）。
□ 复现失败（阻塞项：____）。

- 签名：____
