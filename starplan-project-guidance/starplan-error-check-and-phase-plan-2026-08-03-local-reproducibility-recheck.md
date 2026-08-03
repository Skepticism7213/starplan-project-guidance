# StarPlan 错误检查与阶段计划 - 本机复现与报告合并复核（2026-08-03）

## 1. 复核范围与有效基线

本报告把本机刚刚完成的验证结果与 `starplan-skill-package-full-review-2026-08-03.md` 第 10--12 节的 v0.6--v0.8 更新合并对照。它是当前运行状态的补充结论；旧报告第 1--8 节仍保留其当时的历史快照，不应再用其中的 `d9b1f22`、`185 passed` 或“P1 未完成”描述当前代码。

当前有效代码基线：

- 本地 `HEAD`：`6d2bbbb8a841cac9f9ddf8446ce49a999d586c90`。
- `origin/main` 本地引用与 `HEAD` 一致；只读 `git ls-remote` 也确认远端 `main` 为同一 commit。
- `origin/main...HEAD = 0 0`。
- 当前分支为 `feature/competition-p0-runtime-contract`。远端同名旧分支仍为 `76ec13e`，不能把它误当成当前主线。
- `git fetch` 在本机无法写入 `.git/FETCH_HEAD`（Windows 权限），所以本轮用 `git ls-remote` 做了远端核对；这不是代码差异，但在提交前应由有写权限的终端再执行一次 fetch。

本机运行时：Python 3.12.13、astropy 8.0.1、astroplan 0.10.1、pydantic 2.13.4、numpy 2.3.5、pytest 9.1.1、dashscope 1.26.5、python-dotenv 1.2.2。测试使用 Codex bundled Python；项目代码和 `requirements.txt` 未被测试过程修改。

## 2. Error Check

### 2.1 静态与离线运行检查

| 检查 | 命令/隔离条件 | 结果 | 耗时 |
|---|---|---:|---:|
| Python 编译 | `python -m compileall -q starplan_skills scripts tests` | PASS | 114.2 ms |
| 三个固定示例 | `python scripts/validate_examples.py` | 3 passed, 0 failed | 1,017.4 ms |
| Layer 2/3 科学与 Claim 检查 | `python tests/layer23_validation.py` | 0 unique issues | 115.7 ms |
| 工具交叉校验 | `python scripts/cross_validate.py` | 12/12 PASS | 3,276.1 ms |
| 离线全量回归 | `STARPLAN_MODEL_MODE=offline`，`--ignore=tests/test_qwen_integration.py`，basetemp 和 Astropy cache 均在系统 Temp，`-p no:cacheprovider` | **211 passed, 0 failed** | **71.61 s** |

离线回归没有业务断言失败。M31、M42、案例三和二次闭环也按 README/脚本入口分别运行成功：

| 入口 | 终态/产物 | 耗时 |
|---|---|---:|
| `scripts/run_case.py examples/case_01_m31_jinan.json` | observable，24 个产物，模板回退 | 3.27 s |
| `scripts/run_case.py examples/case_02_unfavorable_window.json` | not_observable，16 个产物，无虚假活动时段 | 3.48 s |
| `scripts/run_case.py examples/case_03_observation_review.json` | review，21 个产物，3 个偏差 | 3.06 s |
| `scripts/run_loop.py examples/case_03_observation_review.json` | 第二次运行 passed，生成 `loop_before_after.md` | 4.22 s |

上述结果支持其他报告对 v0.8 P1 Batch D/E 的判断：现实活动时段、三类视图、可执行下一轮输入和 before/after 在当前 commit 中可离线运行。

### 2.2 真实 Qwen 集成检查

本机的 `.env` 存在 API Key，因此直接执行未排除在线集成文件的 `pytest tests` 时，测试没有 skip，而是尝试真实网络：

```text
212 passed, 8 failed, 3 warnings in 75.90s
```

8 个失败全部来自 `tests/test_qwen_integration.py`。第一次执行时底层错误是 `WinError 10013`，当时的 Codex 沙箱禁止 Python 建立到 `dashscope.aliyuncs.com:443` 的外连；Chat 的“没有工具调用/没有 outreach_pack”断言是 API 不通后进入 blocked fallback 的级联结果，不是离线计算或 Claim 渲染断言失败。

权限开放后，本机通过 `127.0.0.1:7897` 代理和兼容端点完成了真实模型切换与端到端复测（在线日志在北京时间 2026-08-04 00:00 后生成）：

| 场景 | 模型 | 结果 | 模型调用 | 总耗时 |
|---|---|---|---:|---:|
| 最小单轮 canary | `qwen3.7-plus` | `finish_reason=stop` | 1 | 9.997 s |
| 最小单轮 canary | `qwen3.7-max` | `finish_reason=stop` | 1 | 10.413 s |
| 最小单轮 canary | `qwen3.8-max` | `finish_reason=stop` | 1 | 10.434 s |
| M31 结构化入口 | `qwen3.7-plus` | observable / passed / qwen_expression_plan | 1 | 27.923 s |
| M31 结构化入口 | `qwen3.8-max` | observable / passed / qwen_expression_plan | 1 | 26.432 s |
| M42 不可观测入口 | `qwen3.7-plus` | not_observable / passed / template | 0 | 0.822 s |
| 案例三复盘入口 | `qwen3.7-plus` | observable / passed / qwen_expression_plan；review 与 `next_activity_input.json` 存在 | 1 | 26.688 s |
| Chat（正确 UTF-8 输入） | `qwen3.7-plus` | 4 个工具、4 轮；observable / passed / template | 4 | 31.300 s |
| 项目自带 `tests/test_qwen_integration.py`（显式可写 basetemp） | `qwen3.7-plus` | **9 passed / 0 failed** | 多用例 | 172.92 s |

对应运行目录：`live_recheck_m31_q37plus`、`live_recheck_m31_q38max`、`live_recheck_m42_q37plus`、`live_recheck_case3_q37plus`、`live_recheck_chat_q37plus_utf8`。这些目录只用于本机审计，仍由 `.gitignore` 排除；P3 交付时应复制脱敏产物，而不是直接提交含运行环境路径的目录。

Chat 的第一次失败是测试脚本的 PowerShell 中文编码污染（模型收到 `????`），不代表产品输入失败；改用 Python Unicode 转义后工具链完整通过。Chat 审计里 `hallucination_blocked=true` 的语义是“自由文本永不直接交付”，最终 `public_output_validation=passed`、Claim 渲染文本正常交付；原始 Qwen 摘要只保存在审计文件中。

这组结果与其他电脑报告的“兼容端点 + 指定模型成功”相互印证，并完成了本机的最小真实证据；但百炼权限、代理和模型配额仍是外部运行条件，不能把在线通过当成无网络环境的可复现保证。

### 2.3 发现的问题

#### WARNING R-01：在线测试的 skip 条件不包含离线模式

`tests/test_qwen_integration.py` 只根据 `.env` 中是否有 `DASHSCOPE_API_KEY` 决定 skip，不检查 `STARPLAN_MODEL_MODE=offline`。所以同一份仓库在“没有 Key”的电脑上会得到报告中的 `211 passed, 9 skipped`，在本机有 Key 但明确设置 offline 时仍会尝试网络，得到 8 个失败。

这会让团队误报离线可复现结果，也会让带有本地 `.env` 的 CI 被外部网络状态影响。建议把在线测试标成 `online`，并令 `STARPLAN_MODEL_MODE=offline` 无条件 skip；离线验收固定使用 `-m "not online"` 或显式排除在线文件。此项本轮只记录，未改业务代码。

#### WARNING R-02：依赖只写下限，没有锁定环境

`requirements.txt` 使用 `>=`，仓库没有 lock 文件或经过验证的 Python/OS 矩阵。当前环境通过不等于另一台电脑必然得到同样的数值和耗时。至少应在交付包中保存一次 `pip freeze`、Python 版本、操作系统、时区和测试命令；更稳妥的做法是提供锁定依赖或 CI 镜像。

#### WARNING R-03：在线证据依赖外部服务条件

当前代码支持 `STARPLAN_QWEN_BASE_URL`、`STARPLAN_QWEN_MODEL`、超时和重试配置，本机已完成三个模型 canary、两个结构化 M31、M42 回退、案例三复盘和一条正确 UTF-8 Chat。仍需把脱敏日志/截图放入 P3 交付包，并记录 Key 权限、代理和模型配额；Key 本身不能进入报告或仓库。在线服务不可达时，演示必须切换到离线模板或已验证运行。

#### INFO R-04：仓库内历史报告时点不一致

`starplan-skill-package-full-review-2026-08-03.md` 前半部分仍保留 d9 快照，末尾第 10--12 节才记录 v0.6--v0.8。历史记录不应删除，但当前提交材料必须引用本报告作为最新复现结论，或在正式材料中只引用更新后的汇总表。

#### INFO R-05：运行目录默认被忽略

本轮运行目录在 `StarPlan/runs/`，由 `.gitignore` 排除；代码可重跑，但仓库本身不包含三组运行证据。P3 交付包需要另存脱敏的固定输入、关键中间结果、最终输出、`run_outcome`、验证报告和人工确认记录，并明确这些是“复现样例”而不是实时结果。

#### WARNING R-06：真实运行仍出现 Astropy leap-second 缓存权限警告

在线和离线案例均可能看到 `leap-second auto-update failed: PermissionError`。本次运行的 `astronomy_runtime=offline_bundled_data`、状态和数值均通过，警告没有改变结果；但演示日志不应把它留给评委自行解释。建议在正式入口初始化天文运行策略前关闭该更新路径，或在报告中明确这是使用内置数据的已知环境警告，并在第二环境确认不升级为异常。

#### WARNING R-07：pytest 默认临时目录可能触发 Windows ACL 假失败

在线套件第一次未指定 `--basetemp` 时为 `8 passed, 1 error`，唯一错误是 `tmp_path` 无法扫描 `AppData\\Local\\Temp\\pytest-of-...`；改用系统 Temp 下新建的唯一可写目录后为 `9 passed`。交付文档和 CI 命令必须显式设置 `--basetemp`，否则不同电脑的权限差异会被误报成测试失败。

### 2.4 本轮本地未提交内容

已确认并处理：

- 删除 `StarPlan/_check_batch_c.txt`。内容只是旧的 Batch C 表格检查输出，没有源码、测试或提交价值。

保留且未擅自清理：

- `starplan-project-guidance/archive/` 中的旧报告副本，以及主目录中对应的四个删除状态：这是现有的报告归档动作，不是测试垃圾。
- 其他未提交内容中没有发现业务源码修改；本轮没有改 `claims.py`、`rendering.py`、`runner.py` 或测试实现。

本轮按负责人要求清理了旧工作树：

- 已移除 `.worktrees/starplan-p0-runtime-contract-closure/`（HEAD `d9b1f225`，仅有未跟踪 `.ci_tmp/`，没有受跟踪代码改动）。
- 保留分支引用 `codex/p0-runtime-contract-closure`，没有删除历史提交。

## 3. 与更新报告的合并结论

| 更新报告中的说法 | 本机核对 | 当前有效解释 |
|---|---|---|
| 基线已到 v0.8 / commit `6d2bbbb` | PASS | 代码基线和 `origin/main` 一致，前文 d9 仅为历史快照 |
| `211 passed, 9 skipped` | 条件成立但依赖“无可用 Key”或排除 online 测试 | 本机 `.env` 有 Key，按离线隔离命令得到 `211 passed, 0 failed`；未隔离则 8 个在线测试失败 |
| P1 Batch D/E 已完成 | PASS | 三个示例、`run_loop`、Layer 2/3 和离线全量均支持该结论 |
| 兼容端点的 Qwen 真实调用成功 | PASS | 三个模型 canary 和结构化/Chat 端到端均在本机通过；仍需保存脱敏截图/日志 |
| P2 已完全关闭 | 基本完成 | 客户端适配与真实调用已验证；P3 仍需整理可交付证据，不再重复试模型 |
| P3 可复现交付已完成 | 不足 | 当前只有同一环境代码级复跑；第二环境、固定运行包和人工确认尚未形成 |

因此，当前项目不能简单写成“所有验收已完成”。准确表述是：**P0 可信输出门禁和 P1 竞赛闭环在当前 commit 已通过本机离线验证；P2 在线证据与 P3 独立复现/交付证据仍未在本机闭合。**

## 4. 可复现性分层验收

| 层级 | 需要固定的内容 | 当前状态 | 验收缺口 |
|---|---|---|---|
| 源码层 | commit、分支、远端关系、受保护文件未被覆盖 | **PASS** | 提交前由有权限终端再 fetch 一次 |
| 依赖层 | Python、OS、依赖版本、时区、IERS 离线策略 | **本机 PASS / 跨机未证实** | 没有 lock 文件和第二环境记录 |
| 计算层 | 固定 JSON 输入、Astropy cache 隔离、offline 模式 | **PASS** | 将命令和环境变量写入 README/交付包 |
| Claim/交付层 | claims、trace、manifest、outcome、validation、模板回退 | **PASS（211 测试）** | 需要提交脱敏运行样例，而非只提交代码 |
| 模型层 | Key 权限、兼容端点、具体模型、超时、调用次数 | **本机 PASS（依赖在线服务）** | 固化脱敏日志/截图，并准备离线回退 |
| 证据层 | 三案例运行目录、截图、人工确认、Hash | **PARTIAL** | P3 固化并脱敏；不能把 `runs/` 被 gitignore 当成证据已提交 |
| 独立环境层 | 第二台 Windows 或干净 CI 的安装与复跑 | **未验证** | 至少一次从 README 到 211 离线测试的独立记录 |

推荐的离线验收命令（PowerShell，系统 Temp 路径需按机器生成唯一目录）：

```powershell
$env:STARPLAN_MODEL_MODE = "offline"
$env:ASTROPY_CACHE_DIR = "$env:TEMP\starplan_astropy"
python -m compileall -q starplan_skills scripts tests
python -m pytest tests --ignore=tests/test_qwen_integration.py -p no:cacheprovider -q
python scripts/validate_examples.py
python tests/layer23_validation.py
python scripts/cross_validate.py
python scripts/run_loop.py examples/case_03_observation_review.json
```

推荐的在线验收要求（在能访问百炼的终端执行，不把 Key 写入命令行历史）：

1. 从 `.env` 加载 Key，设置 `STARPLAN_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`、`STARPLAN_QWEN_TIMEOUT=60`、`STARPLAN_QWEN_RETRIES=1`。
2. 分别设置 `STARPLAN_QWEN_MODEL=qwen3.7-plus` 和团队实际授权的第二个模型，各执行一次最小 `call_qwen`，记录模型名、耗时、`finish_reason` 和错误类型。
3. 选成功模型执行一次结构化 M31 或 NL 入口，保存 `model_call_log.jsonl`、`run_outcome.json`、`calculation_manifest.json` 和脱敏截图。
4. 另执行一次 `STARPLAN_MODEL_MODE=offline`，确认同一输入在无网络时仍生成确定性模板，且不把被阻断的模型原文返回给用户。

## 5. Completion Status

| 项目计划阶段 | 当前状态 | 依据 |
|---|---|---|
| P0 可信输出与 fail-closed | 已完成（本机复核） | 211 离线测试、Layer 2/3、三案例通过 |
| P1 Batch D：现实活动时段/三视图/安全清单 | 已完成（本机复核） | M31/M42 运行结果与测试通过 |
| P1 Batch E：下一轮输入/二次运行/before-after | 已完成（本机复核） | `run_loop` 4.22s，第二次运行 passed |
| P2：兼容端点与真实 Qwen 证据 | 基本完成（本机复核） | 三个模型 canary、M31/M42、案例三、正确 UTF-8 Chat 和项目自带 9 个在线测试均通过；仍需把脱敏证据固化到 P3 |
| P3：三案例固定运行包/第二环境/人工确认 | 未完成 | `runs/` 被忽略，本机尚无第二环境记录和签名 |
| P4：PPT/PDF、视频、加载演示 | 未完成 | 本轮未生成提交材料 |

## 6. 下一阶段计划

### Phase R-1：把离线验收变成真正可复现的门禁

- 修改在线测试的 skip/marker 逻辑，使 `STARPLAN_MODEL_MODE=offline` 优先级高于 `.env` Key；增加一条回归测试，证明有 Key 时 offline 仍不联网。
- 固定一份 Python/依赖版本记录，并把临时目录、IERS 禁网和测试命令写入 README。
- 验收标准：带 `.env` 的机器执行离线命令也能稳定得到 `211 passed`，在线测试显示为 skip 或被 marker 排除，不出现 `WinError 10013`。

### Phase R-2：在线证据（本轮已完成）

- 只选两个团队实际有权限的模型；每个模型一次最小 canary，成功后只用成功模型跑一条 M31/NL 端到端。
- 记录总耗时、模型调用次数、最终 `RunOutcome`、是否采用 ExpressionPlan、失败时的模板回退；不保存 Key、完整提示词或含个人信息的原始响应。
- 本轮验收结果：三个模型 canary 均 `stop`；`qwen3.7-plus` 和 `qwen3.8-max` 的 M31 结构化入口均 `validation=passed`；正确 UTF-8 Chat 完成 4 个工具调用并 `public_output_validation=passed`；没有把 Key 或完整原始响应写入报告。
- 后续只需固化证据，不再无目的地切换模型或重复调用。

### Phase R-3：P3 固化交付证据

- 从 M31、M42、案例三各生成一份脱敏运行包，包含输入、关键中间结果、最终输出、manifest、outcome、validation、人工确认入口和 SHA-256 清单。
- 在第二台电脑或干净 CI 按 README 安装并复跑离线命令，保留原始命令输出和耗时。
- 验收标准：第二环境离线零失败；三案例状态和关键字段一致；所有实时 Qwen 证据标注机器、时间、模型和外部依赖。

### Phase R-4：演示与提交材料冻结

- 主演示采用结构化入口 + 已验证运行复现；Chat 只在其真实状态和耗时满足验收后作为补充。
- PPT/PDF 用一页展示四层可复现性矩阵和“在线失败 → 确定性回退”路径；视频不依赖现场重新联网。
- 验收标准：10 分钟内完整展示计划、科学窗口、现实活动时段、三视图、复盘、下一轮 before/after 和 Claim 证据；不打开 `.env` 或泄漏代理信息。

## 7. 立即下一步

1. 先由能写 `.git/FETCH_HEAD` 的终端再次 `git fetch origin`，确认没有新提交覆盖 `6d2bbbb`。
2. 优先修 R-01 的测试隔离逻辑；这是一处小改动，却直接决定“有 Key 的机器能否复现离线报告”。
3. 把本轮在线 canary、M31/M42/案例三/Chat 和 9 个在线测试的脱敏运行摘要、显式 basetemp 命令和截图固化到 P3 交付包，不再重复试模型。
4. 保留现有历史报告归档；旧 P0 worktree 已清理，后续不要在没有同步最新 `main` 的 worktree 上继续修改。
5. 代码和报告下一次提交前重新检查 `git status`、`git diff --check`、完整 diff 和 `origin/main...HEAD`，避免把归档操作误推成业务回退。

## 8. 本轮结论

当前最可靠、可以对外承诺的结论是：**StarPlan v0.8 的确定性天文计算、Claim/fail-closed 防护、现实活动时段、三类视图、复盘到下一轮闭环均已在本机离线通过；真实 Qwen 的兼容端点、模型切换和正确 UTF-8 Chat 也已在本机通过；第二环境、脱敏运行包和人工确认仍未完成。** 这不是“代码没做完”，而是“代码能力、在线依赖和交付证据必须分层标注”。

## 9. 本轮环境与编码修复（2026-08-04）

### 9.1 变更范围

- 新增 `StarPlan/starplan_skills/encoding.py`，以 `TextIOWrapper.reconfigure()` 初始化 UTF-8；不替换 `sys.stdout`/`sys.stderr` 对象，避免破坏 pytest capture 和宿主应用。
- `starplan_skills` 包入口、Layer 1/2/3 直接校验脚本均调用统一初始化；文件读写本来已经显式使用 UTF-8。
- 新增 `StarPlan/scripts/bootstrap_windows.ps1`：创建项目 `.venv`，按 `requirements.txt` SHA-256 标记判断是否已安装，依赖未变化时不重复安装。
- 新增 `StarPlan/scripts/run_utf8.ps1`：设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、PowerShell/Console 输入输出编码，并使用项目 `.venv` 执行脚本。
- `run_offline_ci.bat` 增加 `chcp 65001`、Python UTF-8 环境变量和 `.venv` 优先选择；离线测试继续显式指定可写 basetemp/cache。
- README 增加 Windows 一次性初始化和 UTF-8 运行命令，明确不应通过默认 GBK 管道传递中文测试载荷。

### 9.2 验收标准

1. `python -m compileall -q starplan_skills scripts tests` 通过，新增 PowerShell 文件仅含 ASCII 控制文本，避免 PowerShell 5.1 解析自身时再次乱码。
2. 包入口下 `sys.stdin/stdout/stderr` 的编码为 UTF-8；pytest capture 对象不提供 `reconfigure` 时保持原对象且全量测试通过。
3. `run_offline_ci.bat` 和 README 中的 Windows 命令在有 `.env` 时仍保持离线，不触发 Qwen 网络调用。
4. `bootstrap_windows.ps1` 首次运行安装依赖并写入哈希标记，第二次运行只复用环境；requirements 变化才重新安装。

### 9.3 新增问题及处置

| 严重度 | 问题 | 处置 | 状态 |
|---|---|---|---|
| WARNING ENV-01 | 初版 bootstrap 健康检查要求导入项目未使用、requirements 未声明的 `pandas`，导致新 `.venv` 被误判为不完整 | 健康检查收敛到 requirements 中实际声明并由代码使用的依赖；README 同步移除过时 pandas 条目 | 已修复 |
| WARNING ENV-02 | 原 `.bat` 含非 ASCII 长横线且为 LF；cmd 切换代码页前解析注释时产生误命令噪声 | 注释改为 ASCII、文件统一 CRLF，并在入口设置 `chcp 65001`/`PYTHONUTF8` | 已修复 |
| WARNING ENV-03 | 原批处理使用仓库 `.ci_tmp`，本机历史 ACL 会触发 pytest 临时目录 PermissionError | 改为每次使用系统 Temp 唯一目录，并预创建 pytest/Astropy 缓存目录 | 已修复 |

### 9.4 本机实测结果

| 检查 | 结果 | 备注 |
|---|---|---|
| 默认 GBK Python 导入包后打印中文 | PASS | `sys.stdin/stdout/stderr` 均为 UTF-8，中文样例无问号或乱码 |
| PowerShell 5.1 解析两个 `.ps1` | PASS | 脚本控制文本为 ASCII，未触发编码解析错误 |
| `bootstrap_windows.ps1` | PASS | `.venv` 使用 Python 3.13.7；首次安装后健康检查通过，第二次执行约 2 秒并复用哈希 |
| `run_utf8.ps1 scripts/run_case.py ...case_02...` | PASS | M42 不可观测回退正常，中文路径和提示完整显示，约 3.5 秒 |
| `cmd /d /c scripts\\run_offline_ci.bat` | PASS | 编译通过、示例 3/3、离线 pytest **211 passed，64.67 秒**；无 `WinError 5`、无 Astropy cache warning、无 cmd 误解析噪声 |

初始化过程中健康检查曾暂时暴露 `pandas` 未安装；复核发现项目代码没有导入 pandas，`requirements.txt` 也未声明它，故将健康检查收敛到 requirements 中实际声明的依赖，避免为了环境检查引入无用安装。

### 9.5 剩余边界

- `.venv` 和哈希标记属于本机环境，不提交到 Git；另一台电脑仍需首次运行 bootstrap。
- 依赖版本仍由 `requirements.txt` 的下限约束，尚未形成跨平台 lock 文件；本轮解决的是重复安装和 Windows 编码边界，不把它误报为完整跨机数值复现。
- 真实在线调用的 Key、代理和模型配额与 UTF-8 环境无关，仍按 P2/P3 的在线证据要求单独记录。
- 旧测试遗留目录 `StarPlan/.ci_tmp/pytest-cache-codex-20260803` 仍存在，但其 ACL 拒绝当前进程读取/删除；它不在 Git 跟踪范围内，新的 `run_offline_ci.bat` 已改用系统 Temp 唯一目录，因此不会再参与测试或造成运行失败。若要彻底清除，应由有权限的本机终端定点删除该目录，不应扩大到仓库根目录。

### 9.6 本轮审查报告重组（2026-08-04）

- `starplan-skill-package-full-review-2026-08-03.md` 的第 1--8 节已改为当前有效状态摘要：基线、211 条离线回归、真实 Qwen 证据、P0/P1 完成情况和 P2/P3/P4 剩余交付项均前置；第 9--13 节保留详细实测与历史追溯。
- 本轮只修改审查文档的结构和结论表述，没有修改 `claims.py`、`rendering.py`、`runner.py`、`run_outcome.py` 或测试实现；没有新增业务行为或绕过验证门禁。
- UTF-8 读取、`git diff --check` 和前半部分关键词复核通过；`git diff --check` 仅报告现有 LF/CRLF 提示和 ACL 残留目录警告，无空白错误。
