# StarPlan Loop 错误检查与阶段计划 — 2026-07-31 同步后复查

日期：2026-07-31
基准 commit：`5d17b96`（本地 `main` 与 `origin/main` 一致）
复查性质：同步团队更新后的静态审查、运行验证和纠错计划
范围：`StarPlan/` 全部新增科学修复、验证报告、离线 CI 与可信输出主链路

## 1. 同步内容摘要

本次同步包含 5 个团队提交：

| 提交 | 团队完成内容 | 复查结论 |
|---|---|---|
| `8d93cf0` | 修复高纬度极昼被误判可观测；区分纬度永久受限与日期受限目标的替代建议；新增 5 个边界测试 | 科学边界修复有效，5/5 通过 |
| `cc36a69` | 重写 `outreach_pack`，声称修复设备约束、文字溯源、季节提示、拱极星、月光风险、目标类型和 JSON 回退等 P1-P9 | 部分有效；主链路仍保留自由文本和无来源模板事实，不能按“P1-P8 全部完成”验收 |
| `48bfef5` | 删除 `StarPlan/docs` 旧验证文档目录 | 目录清理有效；验证材料已集中到 `数据验证日志/` |
| `ae5b238` | 新增 `outreach_pack` 科学性测试报告 | 报告记录的是修复前/问题发现结果，不能作为当前通过证据，且与 `cc36a69` 的“已修复”描述冲突 |
| `5d17b96` | 新增 `astroplan` 独立交叉校验脚本、校验日志和阶段报告 | 2 个固定案例共 12/12 通过；边界覆盖仍有限，异常处理未 fail-closed |

工作区已有的 `AGENTS.md`、置信度结果 JSON 以及归档移动均未修改或覆盖。

## 2. Error Check

### 2.1 运行验证结果

| 检查 | 命令/范围 | 结果 | 结论 |
|---|---|---:|---|
| 编译 | `python -m compileall -q starplan_skills scripts tests` | PASS | 代码可编译 |
| 示例校验 | `python scripts/validate_examples.py` | 3/3 | 示例 Schema 通过 |
| Layer 1 目录科学校验 | `python tests/layer1_validation.py` | 10/10 轮，0 issue | 目录范围、星座、类型属性、别名一致 |
| Layer 2/3 目录来源校验 | `python tests/layer23_validation.py` | 10/10 轮，0 issue | provenance、坐标、星等、SIMBAD fixture 一致 |
| 极昼/纬度边界 | `tests/test_observability_edge_cases.py` | 5 passed | WARNING-1/2 修复有效 |
| C-3 不可观测包 | `tests/test_not_observable_pack_c3.py` | 10 passed | 取消/替代包分支行为有效 |
| 月距与科学边界 | `test_moon_separation_c1.py` + edge cases | 11 passed | 坐标计算回归通过 |
| 幻觉对抗 | `test_hallucination_protection.py`、`test_chat_hallucination_c4.py`、`test_mock_qwen_adversarial.py` | 41 passed | 组件级对抗用例通过 |
| `astroplan` 交叉校验 | `python scripts/cross_validate.py` | 12/12 | 固定 M31/M42 计算量在容差内一致 |
| Layer 3 端到端 | `tests/test_layer3_e2e.py` | 6 passed，3 failed，3 errors，2 skipped；收尾阶段再触发 1 次临时目录清理异常 | 3 个真实代码失败：错误月光阻断理由、缺 `claims.json`、缺 `sentence_claim_map.json`；3 个 `tmp_path` fixture 错误属于环境权限问题 |
| 离线 CI | `cmd /c scripts\\run_offline_ci.bat` | 124 passed，4 failed，4 errors，2 skipped，非零退出 | 3 个端到端代码失败 + 1 个 `TemporaryDirectory` 失败；4 个 pytest 临时目录错误；不能宣称离线 CI 通过 |

离线 CI 确实设置了 `STARPLAN_MODEL_MODE=offline`，输出中没有网络成功调用证据；但因为测试失败，不能把“零网络调用”与“整套验收通过”混为一谈。

### 2.2 CRITICAL

#### CRITICAL-1：Claim Registry 已存在但没有接入 `run_starplan`

**证据**：`starplan_skills/claims.py`、`rendering.py`、`expression_validator.py` 和相应单元测试均存在；但 `starplan_skills/runner.py` 在计算完成后直接调用 `generate_outreach_pack()`，没有构造 `AllowedClaimsBuilder`，也没有调用 `builder.save()`、表达计划验证或渲染 trace。`runs/test_p2_moonlight/` 实际只有 11 个文件，没有 `claims.json`、`expression_plan.json` 或 `render_trace.json`，`run_outcome.json` 的 `claims_registry_hash` 为 `null`。

**影响**：项目计划要求的“所有用户可见事实先进入本次运行 Claim Registry”尚未成立；组件测试通过不能替代端到端接入验收。不可观测分支也直接绕过 Registry。

**必须修改的位置**：

1. 在 `StarPlan/starplan_skills/runner.py` 的 observability 成功后、outreach 生成前构造 `AllowedClaimsBuilder`，为 observable 和 not-observable 两条路径都写出 `claims.json`。
2. 修改 `StarPlan/starplan_skills/outreach_pack.py::generate_outreach_pack`，接收当前 run 的 claims builder；模板、Qwen 表达计划和不可观测回退全部调用 `rendering.py`，禁止再从 `target/obs` 直接拼事实句。
3. 每次进入 Claim 阶段必须写 `expression_plan.json` 和 `render_trace.json`；任一 Claim/句式/作用域校验失败，输出确定性回退并将 validation 置为 `blocked` 或明确 warning。
4. 将 `tests/test_layer3_e2e.py` 的 `claims.json`、全句映射和 artifact contract 断言恢复为强制门槛，而不是只在组件测试中验证。

**状态**：未修复。Layer 3 的 `test_claims_json_exists` 已实际失败。

#### CRITICAL-2：不可观测原因被写死为“最高高度角过低”

**证据**：`StarPlan/starplan_skills/outreach_pack.py` 的 `_build_not_observable_talking_points()` 和 `_write_not_observable_markdown()` 无条件输出“最高高度角过低”。在 `runs/test_p2_moonlight/outreach_pack.md` 中，M31 实际峰值约 85°、真正阻断因素是 `moon severe`，最终仍出现“最高高度角过低”和“地平线以下”。`tests/test_layer3_e2e.py::test_blocking_reason_mentions_moon` 已复现失败。

**影响**：对用户给出错误取消原因；月光、极昼、地平线、airmass 和设备约束会被同一段错误文案覆盖，直接破坏科学解释和复盘依据。

**必须修改的位置**：

1. 在 `StarPlan/starplan_skills/observability_plan.py` 生成结构化 blocking reason，按实际违反的约束登记 Claim，例如 `moon.impact`、`obs.no_dark_window`、`obs.altitude_constraint`、`obs.airmass_constraint`。
2. 在 `outreach_pack.py` 仅渲染存在且排序明确的 reason Claims；不得在模板中默认补“高度角过低”。
3. 为满月、极昼、目标低于地平线、airmass 超限和纬度永久受限分别增加端到端反例，断言用户文本只出现真实原因。

**状态**：未修复。此项为当前最直接的用户可见科学错误。

#### CRITICAL-3：模板仍包含未经数据支持的事实性陈述

**证据**：

- `_season_safety_note()` 直接生成 `0°C`、`5-15°C`、`10°C` 等温度预测，但当前工具没有天气数据；这只是按月份猜测，不是“动态事实”。
- `_build_talking_points()` 直接写入“数十亿颗恒星”“恒星诞生的摇篮”等目标知识，未进入 Claim Registry。
- `_build_not_observable_talking_points()` 直接写入“当前季节处于太阳方向附近/地平线以下”和“最佳观测季节”，对月光阻断和纬度永久受限均不成立。
- `_build_schedule()` 直接写入“等待天空完全变暗”，没有对应的 procedural Claim 或可验证等待时长。

**影响**：P2/P3/P4/P6 的报告结论与当前实现不一致；数字正则只能拦 Qwen 数字，无法保护这些代码模板产生的文字事实。

**必须修改的位置**：

1. 删除没有天气工具支持的具体温度；改为无温度的安全流程，或新增明确标注“外部天气数据待确认”的 `UNCONFIRMED` Claim。
2. 将目标类型科普、可见性、设备能力、季节/太阳方向和安全流程改为版本化推导规则生成的 Claim；没有输入证据就不输出。
3. `_build_not_observable_talking_points()` 只渲染目标身份、业务状态、实际 blocking reason 和有证据的替代建议；纬度受限时只能建议换地点，不能说等待季节。
4. 用统一 renderer 覆盖 Markdown、结构化返回和回退文本，禁止再保留第二套自由字符串出口。

**状态**：未修复，属于可信输出架构的阻断项。

#### CRITICAL-4：RunOutcome、Manifest 和 Validation Report 仍未形成单一终态出口

**证据**：`runner.py` 先用 `RunOutcome` 写 `run_outcome.json`，随后独立调用 `_write_validation_report(run_dir, resolved, obs_result, None)`；报告没有接收 RunOutcome/Manifest。旧 `_build_manifest()` 仍留在文件中，存在第二套状态推导。当前 M31 满月运行的三个文件虽然分别写出 `not_observable`、`passed` 和 `EXPECTED_FAILURE`，但没有 Claim hash、render trace 或完整 artifact contract 的一致校验。

**影响**：未来任何一条路径都可能出现状态互相矛盾；“报告写了 PASS”不能证明用户输出和 Registry 通过。项目计划要求的 `run_outcome.json` 单一事实来源尚未兑现。

**必须修改的位置**：

1. 删除或停用 `runner.py::_build_manifest()`，只允许 `RunOutcome.build_manifest()` 构建 Manifest。
2. 将 `_write_validation_report()` 改为只接收最终 RunOutcome，并从同一对象读取 business/validation/delivery 三轴、Claim hash、artifact 列表和问题码。
3. 在 finalize 阶段校验必需文件存在、重新计算 hash，再写 Manifest、Report 和 Outcome；早期失败也必须按终态 artifact contract 留痕。
4. `validation_status=passed` 只能由验证结果计算，不得由“没有 Qwen warning”推断。

**状态**：未修复，需与 CRITICAL-1 一起处理。

### 2.3 WARNING

#### WARNING-1：地点纬度在 `outreach_pack` 中仍硬编码为 36.49

`_build_talking_points()` 和 `_generate_talking_points_qwen()` 使用 `latitude = 36.49` 判断拱极星。换到南半球或其他纬度，北极星等特殊目标的表述会错误。应把实际地点纬度作为参数进入 Claim/规则，禁止从默认济南值推断。

#### WARNING-2：交叉校验异常被吞掉，且只覆盖两个固定案例

`StarPlan/scripts/cross_validate.py:96-109` 对可观测判定使用 `except Exception`，异常时只打印，不向结果集合加入失败项，脚本仍可能以 0 退出。应让异常成为失败结果并非零退出，并增加高纬度、南天目标、月光阻断、纬度受限和时区跨日案例。

#### WARNING-3：离线 CI 的临时目录策略在本机仍不可写

`scripts/run_offline_ci.bat:16-18,44` 指向固定的仓库 `.ci_tmp`。本次官方命令产生 4 个 pytest fixture 错误，均在清理/扫描该目录时触发 `WinError 5`；`TestClaimsSave::test_save_creates_file` 还在系统 `TemporaryDirectory` 写 `claims.json` 时失败。脚本注释声称“dedicated writable temp dir”，但没有做写入、删除和权限预检，也没有把 `TEMP`/`TMP` 一并切到该运行的唯一目录。应为每次运行创建 GUID/时间戳临时根目录，把 `TEMP`、`TMP`、`--basetemp` 和 pytest cache 同时指向它，先完成 create/write/read/delete smoke test，再启动测试；结束时若清理失败应单独报告，不能覆盖真实测试汇总。

#### WARNING-4：模型调用事实仍由 `outreach.qwen_used` 推测

`runner.py` 的 `_write_model_call_log()` 和 Outcome 更新根据最终 pack 的 `qwen_used` 补写事件；Qwen 实际调用后失败并模板回退时，调用事实可能被记成“未调用”。应只从 `qwen_client` 的真实事件聚合 `called/successful/accepted_for_delivery`，不能由最终交付形式反推。

#### WARNING-5：Chat 仍是独立的数字正则摘要路径

`run_starplan_chat()` 虽然不把模型原文放进 public dict，这是有效改进，但仍由 `_check_chat_hallucination()` 做数字检查，再调用 `_build_deterministic_summary()` 拼接结果，未复用 Claim Registry/render trace；`verification["passed"]` 仍容易被误读为“模型文本可信”。应让 Chat 与 structured mode 共用 Registry、RunOutcome、renderer 和 artifact contract。

#### WARNING-6：Windows 离线 CI 日志存在乱码和批处理解析噪声

`run_offline_ci.bat` 当前为 UTF-8、LF 换行且未设置控制台 UTF-8。实际执行中 Python 输出的中文路径和业务文案全部乱码，退出后还出现若干 `is not recognized as an internal or external command` 噪声。即使测试逻辑不受影响，这类日志也不适合作为可审计验收证据。应将 `.bat` 固定为 Windows 兼容的 CRLF，开头设置 `chcp 65001 >nul`、`PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`；同时保持批处理自身注释/控制语句为 ASCII，并增加 CI 日志中关键中文样例的可读性检查。

### 2.4 INFO / 已确认无害

1. `compileall`、目录验证、边界计算和 12/12 `astroplan` 对账均通过；当前没有证据表明 `observability_plan` 的核心高度角、暮光、月相近似在固定案例上错误。
2. Astropy `CacheMissingWarning` 和 pytest cache 警告来自本机缓存目录权限，不是天文结果错误；但应在验收环境中显式设置可写缓存，避免把 warning 当作“干净通过”。
3. `ae5b238` 的 `outreach_pack_science_test_report.md` 与 `cc36a69` 的修复说明互相冲突；前者应标为历史问题发现报告，不能继续作为“当前通过”引用。

## 3. 完成度对照

| 项目计划阶段/门槛 | 当前状态 | 证据 |
|---|---|---|
| 本地确定性天文计算与固定案例 | **完成且有独立校验** | Layer 1/2/3 目录校验、边界 5/5、`astroplan` 12/12 |
| 极昼与纬度受限目标修复 | **完成** | `8d93cf0`，边界测试通过 |
| `outreach_pack` P1-P8 科学修复 | **部分完成** | 设备和月光提示有所改善；温度、文字事实、阻断理由和纬度仍有残留 |
| P0-A Claim 封存/篡改单元能力 | **组件完成，主链路未接入** | `claims.py`/validator 对抗测试通过；运行目录无 `claims.json` |
| P0-B 统一渲染与不可观测完整分支 | **未完成** | `outreach_pack.py` 仍直接拼接两套 Markdown/文本 |
| P0-C RunOutcome 全路径终态 | **部分完成** | Outcome 已创建，但早期失败 artifact、Report、Manifest 仍不统一 |
| P1-B 真实离线 CI | **未完成** | 官方 bat 非零退出；真实失败与临时目录权限同时存在 |
| 科学交叉校验 | **固定案例完成，覆盖不足** | 2 案例 12/12；异常吞掉且未覆盖边界矩阵 |
| 第 5 周演示入口与提交材料 | **尚未达到进入条件** | Claim/render/终态矩阵和离线 CI 尚未通过总验收 |

本轮不能按历史报告中的“110 tests pass”“P1-P8 已完成”推进到展示阶段；这些结论早于当前主链路复查，已由本报告中的反例 supersede。

## 4. Phase Plan

### R0：先修复验证环境和可重复基线

**修改范围**：`StarPlan/scripts/run_offline_ci.bat`、pytest 配置/运行说明。
**工作**：建立唯一临时根目录；将 `TEMP`、`TMP`、pytest basetemp 和 cache 全部指向该目录；预检创建、写入、读取、删除；统一 UTF-8 控制台与 CRLF 批处理格式；CI 失败时保留失败摘要而非在 pytest 清理阶段二次报错。
**验收标准**：在有无 `.env` key 两种环境下，离线 CI 都能跑到完整 pytest 汇总；无 `WinError 5`、无 cache cleanup error、无中文乱码和批处理误解析噪声；任何测试失败都以真实测试失败退出。

### R1：接通 Claim Registry 和统一 Renderer

**修改范围**：`runner.py`、`outreach_pack.py`、`claims.py`、`rendering.py`、`expression_validator.py`、`schemas.py`。
**工作**：

1. 计算完成后统一构建并保存 `claims.json`，两条业务分支都必须执行。
2. Qwen 只返回 `claim_id/sentence_variant_id/order/tone`；模板模式也只能选择 Claim，不得写自由事实句。
3. 每次写出 `expression_plan.json`、`render_trace.json`；Markdown 与结构化输出都由同一 renderer 产生。
4. 删除或改写温度、太阳方向、最佳季节、数十亿颗恒星、恒星诞生区、等待天空完全变暗等未授权文案。

**验收标准**：

- M31 可观测、M42 夏季不可观测、M31 满月、极昼、纬度受限各自产生 `claims.json` 和 render trace。
- 用户可见事实句 Claim 映射覆盖率 100%；未知/越权/无来源 Claim 使 validation blocked 或确定性回退。
- 运行目录不存在“有用户文案但无 Claim/trace”的文件。

### R2：修正不可观测原因和 RunOutcome 终态

**修改范围**：`observability_plan.py`、`outreach_pack.py`、`run_outcome.py`、`runner.py`、`tests/test_layer3_e2e.py`。
**工作**：

1. 把 moon/daylight/altitude/airmass/latitude-limited 原因变成结构化 reason Claims，按实际约束渲染。
2. 让 `validation_report.md`、`calculation_manifest.json`、`run_outcome.json` 从同一 finalize 过程生成，并验证文件清单与 hash。
3. 工具错误、目标歧义、数据不足和验证阻断均产生定义明确的 public result 与基础审计产物，不再依靠调用者捕获异常判断状态。

**验收标准**：六类终态（observable、not_observable、needs_confirmation、data_insufficient、tool_error、validation_blocked）逐一通过 E2E；每类状态三份状态文件一致，必需 artifact 齐全；满月反例不出现“高度角过低”。

### R3：修正地点语义、模型事件和交叉校验门槛

**修改范围**：`outreach_pack.py`、`qwen_client.py`、`runner.py`、`scripts/cross_validate.py`。
**工作**：传入真实纬度/经度和时区；模型调用日志由真实事件聚合；交叉校验异常变成失败项并非零退出；扩展固定矩阵至高纬度、南天、月光、纬度受限和跨日时区。

**验收标准**：非济南地点的拱极判断与天文计算地点一致；Qwen 调用失败但发生过请求时 `called=true, accepted_for_delivery=false`；交叉校验任何异常或差异超容差都使命令失败。

### R4：重新验收、修正文档和再进入展示阶段

**工作**：重新运行官方离线 CI、固定案例和反例；更新 README、skills contract 和阶段报告中的完成状态；把 `ae5b238` 的问题发现报告标明历史版本并链接本报告。

**总验收标准**：

1. 用户可见无来源事实率为 0。
2. Claim/render trace 覆盖率为 100%。
3. 六类终态状态一致、artifact contract 完整。
4. 离线 CI 零失败、零错误、零真实网络调用。
5. 固定案例可复现，科学交叉校验通过扩展矩阵。

在 R4 全部通过前，不进入复杂前端、行星扩展或比赛展示包装。

## 5. Immediate Next Actions

1. 先修 R0 临时目录预检并保存一次完整失败摘要，确保后续每次测试结果可区分环境错误和代码错误。
2. 直接修 `outreach_pack.py` 的 CRITICAL-2/3：移除硬编码阻断理由和无来源模板事实，同时补满月、极昼、纬度受限三组反例。
3. 在 `runner.py` 接入 `AllowedClaimsBuilder` 与统一 renderer，先让两个固定案例都生成 `claims.json`、`expression_plan.json`、`render_trace.json`。
4. 完成 R2 六终态 E2E 后，再修模型事件聚合和 Chat 共用 renderer；不要继续以现有数字正则通过作为幻觉防护完成证明。
5. 只有 R0-R4 总验收全部满足，才按 project plan 进入演示入口和提交材料阶段。

## 6. 复查结论

本次同步确实提高了确定性天文计算的科学可信度，尤其是极昼、纬度受限和固定案例交叉校验；但它没有把 Claim Registry、统一渲染和 RunOutcome 证据链接入真实 `run_starplan` 输出。当前版本可作为“科学计算修复后的中间基线”，不能作为“幻觉防护和全链路验收完成版”。
