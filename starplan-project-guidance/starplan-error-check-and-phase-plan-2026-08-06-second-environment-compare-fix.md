# StarPlan Loop 错误排查报告与阶段安排

日期：2026-08-06
项目起始：2026-07-18 ｜ 官方截止：2026-09-05 00:00（北京时间）｜ 内部硬截止：2026-09-01 00:00
当前阶段：P3 证据包与第二环境复现修复

本轮依据：`C:\Users\Skepticism7213\Downloads\second_environment_repro.md`，以及远端协作分支 `origin/codex/p3-hash-compare` 中对应的第二环境记录。远端 `main` 已刷新并确认基线为 `b0ee771`；本轮修复均在该基线上进行。

---

## 一、本轮错误检查

### 1. 第二环境报告发现的问题

第二环境安装和运行本身成功，但在 `b0ee771` 基线上三案例哈希比较均返回失败。问题分为三类：

1. `input.json` 只有 JSON 字段顺序、换行和 `2`/`2.0` 等序列化差异；按字节比较会误报。
2. `claims.json` 的 `source_hash`、`registry_hash` 随中间 JSON 序列化差异级联变化；Claim 值、允许变体、规则哈希和模板哈希并未改变。
3. 案例三的示例输入与 evidence 快照使用了两份不同观测日志：示例为 19:30、`partly_cloudy`、三脚架不稳，快照为 19:45、`clear`、无日志；同时新环境没有生成 facilitator/learner 两个视图。

### 2. 修复项

| 严重度 | 问题 | 修改位置 | 修复方式 | 状态 |
|---|---|---|---|---|
| WARNING | 输入 JSON 序列化差异被当成 STRICT 失败 | `StarPlan/scripts/compare_evidence_hashes.py` | `input.json`、`observation_log.json`、`revised_plan.json`、`next_activity_input.json` 使用递归规范化后的 JSON 语义比较；字典排序、整数浮点等价，列表顺序仍保留 | 已修复 |
| WARNING | Claims 哈希链的机器差异导致误报 | `StarPlan/scripts/compare_evidence_hashes.py` | `_claims_snapshot()` 比较 Claim 内容、稳定 scope/源信息、规则哈希和模板哈希；排除运行期 `source_hash`、`registry_hash` 及可变中间产物链。单次运行内的 `verify_saved_registry()` 仍负责完整性门禁 | 已修复 |
| WARNING | 案例三 evidence 与 canonical example 漂移 | `StarPlan/examples/case_03_observation_review.json`、`evidence/case_03_m31_review_loop/` | 固定活动偏好（90 分钟、准备/收尾时间）和三视图受众；以 19:30、云量和设备偏差日志作为 canonical 输入，重建第一轮、复盘、下一轮和第二轮 evidence | 已修复 |
| WARNING | evidence 脱敏后仍可能携带本机绝对路径 | `StarPlan/scripts/build_evidence_pack.py` | JSON/Markdown/JSONL/TXT 在进入 evidence 前替换 run 目录为 `StarPlan/runs/<run_id>`；未发生替换时保持原始字节，避免无意义 hash 变化 | 已修复 |
| WARNING | evidence 缺少预期产物时只警告并可能保留旧快照 | `StarPlan/scripts/build_evidence_pack.py` | `_copy_case()` 对 canonical 文件和案例三第二轮产物收集缺件；缺件返回 `missing_artifact`，主程序退出码 1，不写新 manifest，避免静默生成不完整提交包 | 已修复 |
| WARNING | manifest 新增未分类文件时可能只显示未知差异 | `StarPlan/scripts/compare_evidence_hashes.py` | 未归入 STRICT/VALUE/TOLERANT 的 manifest 文件：缺失直接失败，字节变化按未分类 STRICT 失败，要求显式增加比较策略 | 已修复 |

### 3. 回归测试与运行证据

| 检查 | 结果 |
|---|---|
| `python -X utf8 -m compileall -q scripts tests` | PASS |
| `pytest tests/test_compare_evidence_hashes.py -q` | **5 passed** |
| `scripts/validate_examples.py` | **5 passed / 0 failed** |
| `scripts/build_evidence_pack.py` | case_01 **18** files；case_02 **16** files；case_03 **25** files；manifest 写入成功 |
| 三案例 `compare_evidence_hashes.py` | **0, 0, 0**；案例三包含第二轮目录 |
| 全量离线回归（排除 `test_qwen_integration.py`） | **242 passed / 0 failed / 0 skipped**，448.37 秒 |
| `git diff --check` | PASS |
| evidence 本机路径扫描 | 未发现 `C:\Users\...`、`E:\...` 等本机运行路径 |

三案例的跨环境比较当前结果为：

- 案例一：输入语义、Claim、渲染产物和状态字段一致。
- 案例二：输入语义、Claim、不可观测状态和替代方案字段一致。
- 案例三：观测日志、三视图、复盘原因、下一轮输入、第二轮计划和状态字段一致；`review_report.md` 的本机路径差异仍按 TOLERANT 处理。

### 4. 未关闭事项与边界

本轮没有发现 CRITICAL。以下项目不是本轮代码错误，但必须在交付前完成：

| 等级 | 事项 | 原因/影响 | 责任动作 |
|---|---|---|---|
| WARNING | 修复后的提交尚未在第二台机器重新复跑 | 用户提供的 237 条记录发生在 `b0ee771`，早于本轮 comparator/build 修复；不能把它当成修复后通过证据 | 在新提交上重新安装并执行 242 条离线测试、三案例和三次 compare |
| WARNING | `build_evidence_pack.py` 依赖 canonical `StarPlan/runs/`（gitignored） | 干净 clone 只有源码和 evidence，不能直接重建 evidence；提交包可验证，但“从零重建”仍需先跑 canonical cases | 提交前按 README 先跑三案例，再构建 evidence；必要时在材料中明确该前置步骤 |
| WARNING | 人工确认、外部科学复核和 QoderWork 录屏尚未完成 | 这些是比赛交付证据，不是哈希脚本问题 | 填写三份 `human_confirmation.md`，完成外部数值复核并固定录屏 run_id |
| INFO | 第二环境报告记录了 `GIT_SSL_NO_VERIFY=1` | 仅为该机器的 Git TLS 环境 workaround，不应成为项目运行要求 | 提交材料中保留为环境备注，不在代码中关闭 TLS 校验 |
| INFO | `loop_before_after.md` 与 `human_confirmation.md` 不在运行产物 hash 列表 | 前者由两轮目录派生，后者需要负责人签名/补注；二者不是静态运行文件 | 重建脚本检查其源产物；提交前人工确认文件另行核验 |

---

## 二、完成度对照项目计划

| 计划阶段 | 当前状态 |
|---|---|
| P0/P1/P2：可信输出、运行时门禁、Skills/MCP 交付 | ✅ 已完成，未改动核心 Claims/渲染/运行时架构 |
| P3：固定三案例、证据包、第二环境可复现 | 🟡 本地代码和证据修复完成；三案例 compare 已通过；等待修复后第二环境复跑和人工确认 |
| P4：PPT/PDF、技术报告、流程图、运行记录、演示视频 | ⏳ 未开始，不应被本轮哈希问题拖延 |
| P5：冻结、全新环境安装、隐私/密钥扫描、最终提交 | ⏳ 待 P3 人工证据完成后启动 |

本轮没有改天文计算、坐标系、观测窗口或 Claim 生成逻辑；修复只收敛了证据快照和跨环境验收，避免科学行为因“为了通过 hash”而被改变。

---

## 三、下一阶段计划

### P3 收尾：修复后第二环境验收

1. 在最新提交上建立全新 venv，安装 `StarPlan/requirements.txt`，保持 `STARPLAN_MODEL_MODE=offline`。
2. 执行 `compileall`、`validate_examples.py`、全量离线 pytest。
3. 运行案例一、案例二、案例三第一轮和第二轮，记录实际 run_id。
4. 使用 `compare_evidence_hashes.py`；三个退出码必须均为 0。
5. 将结果、Python/依赖版本和原始日志写回 `evidence/second_environment_repro.md`，并把新的报告与代码同一提交推送。

**验收标准：** 242（或包含新增测试后的实际总数）passed、0 failed、0 skipped；三案例 compare 为 `0/0/0`；不存在 missing required artifact、STRICT 或 VALUE 失败；evidence 不含本机绝对路径。

### P3 人工证据

1. 三个案例分别标记真实观测、桌面模拟或混合边界。
2. 对 M31 坐标/窗口/峰值高度、M42 不可观测原因/替代目标、案例三复盘偏差和 19:30 修订进行独立核对。
3. 完成中小学生场景的成人陪同、监护人许可和点名流程确认。

### P4 竞赛材料

在 P3 第二环境通过后立即冻结代码功能，集中制作不超过 20 页的 PPT/PDF、三类完整运行记录和 10 分钟内演示视频。重点展示：确定性天文计算、Claim-to-render 证据链、不可观测 fail-closed、日志复盘到下一轮输入的闭环，以及真实/模拟边界。

---

## 四、立即行动

1. 提交本轮代码、证据快照和本报告，推送后让第二环境负责人从新提交复跑。
2. 第二环境通过后，不再反复修改 comparator；只修复真实失败的输入/环境问题。
3. 同步完成三份人工确认和一次外部科学复核，随后进入 PPT/PDF 与演示录屏，不再扩张 MVP 功能。

---

## 五、2026-08-08 补充：第二环境重跑操作手册（纯文档）

为第二环境负责人新增 `evidence/second_environment_rerun_guide.md`，把
"在最新 main 上重跑并更新记录"固化为可执行清单，包含：

- 验收标准（242 passed、三案例 compare 0/0/0、无本机路径）；
- 克隆/全新 venv/依赖安装/版本记录命令；
- 三案例复跑、案例三第二轮补跑、哈希对比的完整命令与结果解读；
- `evidence/second_environment_repro.md` 的填写要点与提交推送流程；
- 交回材料清单与常见问题（TLS 绕过、pytest 临时目录、乱码、STRICT 失败处理）。

本轮为纯文档变更（新增 1 个文件 + 1 处链接），无代码与测试改动；
`git diff --check` 干净，密钥扫描无命中。
