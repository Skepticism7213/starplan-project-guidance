# Error Check 与 Phase Plan — Chat 产物对齐 + 宿主转达合同批次

日期：2026-08-05
基线：分支 `feature/chat-artifacts-host-guidance`（`ac6c101` + `23f9359`）以 `--no-ff` 合并入 `main`
范围：`StarPlan/starplan_skills/runner.py`、`StarPlan/skills.yaml`、`StarPlan/tests/test_chat_artifacts_run_dir.py`（新增）

## 一、Error Check（静态 + 运行时扫描）

对本批次触及的代码与数据逐项检查：

| 严重级 | 发现 | 处置 |
|---|---|---|
| INFO | `_exec_observability_plan` 闭包引用 `run_dir`：该变量在函数体后段（`run_dir = get_run_dir(run_id)`）赋值，先于 `call_qwen_chat` 的任何工具调用 | 已确认为安全（闭包按引用捕获，时序上不存在未赋值窗口）；代码注释已写明 |
| INFO | obs dump 新增非空 `observability_csv_path` / `visibility_curve_path` 字段后，finalizer 的 Claim 范围重建是否受影响 | 已用专门回归测试钉死：`test_chat_delivery_unaffected_by_artifact_paths` 验证 validation=passed、三文件齐全、三轴状态正确 |
| INFO | `test_chat_artifacts_run_dir.py` 的 LF→CRLF 换行告警 | Windows 正常现象，不影响 pytest 收集与执行 |
| INFO | `tests/confidence_test_results.json` 时间戳随测试运行变动 | 按团队纪律不提交（结果恒为 150/150，无实质变化） |
| INFO | `StarPlan/.ci_tmp/pytest-cache-codex-20260803/` ACL 残留，git 操作报 Permission denied 警告 | 继承自 2026-08-03，不影响测试；待有权限时定点清理 |

未发现 CRITICAL / WARNING 级问题。受影响用例编译、运行均无错误，见下。

**运行时验证**：

- 新增测试单跑：2 passed（3.28s）。
- 分支尖端离线全量门禁 `scripts/run_offline_ci.bat`：**230 passed, 0 failed（93.98s）**，编译、3 示例、网络 tripwire 同时通过。
- 合并态（main）重跑同一门禁：**230 passed, 0 failed（93.31s）**，与分支尖端一致。
- 科学交叉校验 `scripts/cross_validate.py`：**12/12 PASS**（本批次未触及计算，属门禁一致性确认）。
- 端到端演示复验：模拟 Chat 对话脚本重跑，运行目录由 11 个文件增至 **13 个**，新增 `observability.csv`（2690 B，含表头与逐时刻数据）与 `visibility_curve.png`（62510 B，PNG 魔数校验通过）；用户可见回复与三轴状态不变（observable / passed / template）。

## 二、Completion Status（对照项目计划）

本批次不在原 P0–P5 排期内，属 2026-08-04 勘察发现的两个小缺口的定点关闭，未挤占任何既定阶段：

1. **Chat 产物对齐**（2026-08-04 对话演示中发现）：chat 工具执行器调 `compute_observability` 未传 `run_dir`，导致 chat 运行目录缺少 `observability.csv` 与 `visibility_curve.png`——两者均在 skills.yaml orchestrator 产物清单与 privacy.py 导出白名单中声明。已修复并回归钉死。结构化入口（24 文件）与 Chat 入口（13 文件）的产物差异现在只来自 chat 不产生的计划类文件，不再有"声明了却不生成"的不一致。
2. **宿主转达合同**（2026-08-04 双通道讨论中发现）：外部宿主模型加载本包时如何转达渲染内容此前无约束。skills.yaml 新增 `orchestrator.host_guidance` 四条：事实句原样引用渲染文档、禁止自产/改写天文数值、BLOCKED 时如实告知零交付、仅允许补充非事实性内容。

其余阶段状态不变：P2 智能体加载证据、R-02 依赖锁、P3 三案例脱敏包 + 第二环境复跑 + 人工确认、P4 PDF + 视频、P5 冻结提交（内部硬截止 2026-09-01 00:00 北京时间）均未开始。版本号维持 0.8.0（本批为修复与合同文档，未升版）。

## 三、Phase Plan（未来一至两周）

**P2 证据收尾（优先）**
- 动作：用团队最新有效 Key，在目标智能体形态下录制一次"自然语言触发 → 四工具链 → Claim 渲染 → 公共返回"，保存脱敏截图与 `model_call_log.jsonl`；同时录制"裸 Qwen vs Qwen+StarPlan"对照实验（负责人已拍板必做），用 astropy 独立计算作标准答案。
- 验收：至少一次真实加载 + 一次成功调用留痕；对照实验数值偏差成表；离线模式下同一输入 30 秒内确定性完成。
- 阻塞项：有效 Key（Key-1/2 已失效，Key-3 仅兼容端点）；需轮换所有明文流转过的 Key。

**P3 交付证据包**
- 动作：三案例（M31 可观测 / M42 不可观测+已验证替代 / 案例三复盘闭环）固定输入+中间结果+输出+SHA-256；第二环境复跑；人工确认签名。chat 产物对齐后，chat 形态的运行记录也可纳入证据包（13 文件完整）。
- 验收：第二环境离线零失败；三案例终态与主环境一致；补上"自定义地点（location_detail）零测试覆盖"的回归（2026-08-04 勘察遗留）。
- 风险：第二台机器的 Windows ACL/Temp 问题（有 2026-08-03 隔离方案可复用）。

**P4 材料冻结（与 P3 并行）**
- 动作：20 页内 PDF（负责人已定调：偏设计深度，架构清晰；防幻觉章节为核心权重）；10 分钟内视频（主线三案例 + 双通道输出演示）；"第三方依赖与许可证"表（pip-licenses 生成）与数据来源声明成文。
- 验收：页数/时长逐项核对；无 Key、无代理端口、无本机绝对路径。

## 四、Immediate Next Actions

1. 团队确认可用 Key 并完成轮换 → 安排 P2 录制日（含对照实验）。
2. 确认官网报名状态（6/30 已截止，硬门槛，高于一切材料工作）。
3. P3 开工：先出三案例脱敏包目录结构与 SHA-256 清单模板。
4. （选做，随 P3）补自定义地点回归测试一条。
