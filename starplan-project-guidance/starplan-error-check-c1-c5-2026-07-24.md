# StarPlan Loop 错误排查报告与阶段安排（C-1 ~ C-5 修复批次）

日期：2026-07-24
项目起始：2026-07-18 ｜ 截止：2026-09-01 ｜ 当前进度：第 3 周（Qwen 集成已完成，本轮为质量修复）

---

## 一、本轮错误排查结论

对 `observability_plan.py`、`runner.py`、`outreach_pack.py`、`schemas.py` 做了完整排查，发现并修复 **5 个 CRITICAL 级问题**。修复后全量测试 54/54 通过，3 个固定案例回归全部通过。

### 已修复的 CRITICAL 级问题

| # | 问题 | 文件 | 修复方式 |
|---|---|---|---|
| C-1 | `observability_plan.py` 在 ICRS 目标与 GCRS 月球坐标之间直接调用 `separation()`，同时全局屏蔽 `NonRotationTransformationWarning`。M31 在 2026-10-17 23:13 代码结果约 33.6°，正确值约 105.6°，差 72° | observability_plan.py | 改为 `target_altaz.separation(moon_altaz)`（同框架 AltAz）；删除全局警告屏蔽；清理无用 `import warnings` |
| C-2 | `run_starplan()` 对 `requires_confirmation=true` 只打印警告；只要置信度非 0 就继续计算。歧义目标被系统擅自选定，违反 skills.yaml "人工确认后再继续" | runner.py, schemas.py, exceptions.py(新) | 歧义时抛出 `TargetConfirmationRequired` 异常中断管道；新增 `confirmed_target` 字段供人工选择后旁路 |
| C-3 | M42 案例正确算出不可观测，但 `outreach_pack` 仍无条件生成观测活动包，包含"今晚我们观测 M42"等矛盾表述 | outreach_pack.py, schemas.py | `generate_outreach_pack` 顶部加入 `is_observable` 分流；不可观测时生成取消/改期/替代目标包（`pack_type="not_observable"`） |
| C-4 | Chat 模式幻觉核查 `passed=false`（检出 15 个不可溯源数值）但 1964 字最终回答仍被返回，"模型不编数值"是软提示而非执行边界 | runner.py | Fail closed：核查失败时用 `_build_deterministic_summary(captured)` 确定性渲染替代 Qwen 自由文本；原文保存在 `blocked_content` 供审计 |
| C-5 | manifest 的 `validation_status="passed"` 硬编码；模型信息永远写 "Qwen3.7-Max" 即使模板模式未调用 Qwen；用户覆盖约束、验证问题未被记录 | runner.py, schemas.py | `_build_manifest` 完全重写：动态计算 validation_status；model.called 反映实际调用；记录 manual_overrides、validation_issues、qwen_used；intermediate_files 在全部文件写入后采集 |

### 新增测试覆盖

| 测试文件 | 测试数 | 覆盖内容 |
|---|---|---|
| `tests/test_moon_separation_c1.py` | 6 | AltAz 角距基准值、旧 bug 值对比、管道输出验证 |
| `tests/test_target_confirmation_c2.py` | 11 | 歧义拦截、异常信息、confirmed_target 旁路、边界 |
| `tests/test_not_observable_pack_c3.py` | 10 | 取消包内容、禁止观测语言、替代建议、M31 不受影响 |
| `tests/test_chat_hallucination_c4.py` | 19 | 幻觉检测、确定性渲染、坐标来源核查、fail-closed 逻辑 |
| 原有 `tests/test_hallucination_protection.py` | 8 | 未修改，仍通过 |
| **合计** | **54** | **全部通过** |

### 3 案例回归结果

| 案例 | 预期行为 | 实际结果 |
|---|---|---|
| M31 + 四门塔 + 2026-10-17 | 可观测，正常活动包 | ✅ Observable, 窗口 18:58~04:28, 峰值 85.0°, pack_type=observation, vs=passed, qwen=True |
| M42 + 四门塔 + 2026-07-25 | 不可观测，取消/替代包 | ✅ Not observable, 最高 -5.7°, pack_type=not_observable, vs=target_not_observable, qwen=False |
| M31 + 四门塔 + 2026-10-17 + 复盘 | 可观测 + 偏差分析 | ✅ Observable, 偏差 2~3 项, pack_type=observation, vs=passed |

### 确认无害的 INFO 级项

- 月相计算（sun-moon elongation）使用 GCRS 同框架 separation，物理正确，不受 C-1 影响。已加注释标明。
- `astroplan` 在 venv 中已安装但 `observability_plan` 实际用纯 Astropy 实现。manifest 中 `astroplan_version` 如实记录已安装版本。
- `_write_validation_report` 的 manifest 参数改为 Optional，不影响已有调用。

---

## 二、当前完成度对照项目计划

| 计划阶段 | 计划目标 | 实际状态 |
|---|---|---|
| 第 1 周 | 冻结范围、Schema、案例、验证规则 | ✅ 已完成 |
| 第 2 周 | 跑通目标解析 + 本地可观测性计算 | ✅ 已完成 |
| 第 3 周 | 接入 Qwen 编排 + 科普活动包 | ✅ 已完成（含本轮质量修复） |
| 第 4 周 | 观测日志 + 复盘闭环 | 🟡 规则版已完成，Qwen 辅助归因未做 |
| 第 5 周 | 演示入口 + 3 类案例 | ⏳ 待开始 |
| 第 6 周 | 打磨评测、报告、视频 | ⏳ 待开始 |

**本轮修复使第 3 周交付物达到可答辩质量。** 核心改进：月光数据物理正确、歧义目标有人工确认门、不可观测不生成矛盾材料、幻觉检测从软提示变为执行边界、证据链如实记录。

---

## 三、接下来几周的阶段安排

### 第 4 周剩余（07-25 ~ 08-01）：复盘增强 + 星表重建

核心任务：

1. **星表坐标重建**：`built_in_catalog_v1.json` 中 37/150 条坐标偏差 >2 角分（最差 M23 错 4.4°），需用 SIMBAD 权威值重建。核验结果已存 `workspace/catalog_simbad_check.json`。
2. **Qwen 辅助归因**：`observation_review.py` 当前为规则版（关键词匹配），需接入 Qwen 做自然语言归因，结论必须可追溯到证据。
3. **test_qwen_integration.py 补写**：被引用但不存在的集成测试文件。

**阶段验收：** 星表坐标全部偏差 <2 角分；复盘报告引用具体证据字段；集成测试可跑。

**阻塞项：** 星表重建需要网络访问 SIMBAD（astroquery 已装入 venv）。

### 第 5 周（08-01 ~ 08-08）：演示入口与案例固化

核心任务：

1. **轻量演示面板**：Streamlit 或 FastAPI（待团队确认），展示 Skill 输入→工具调用→中间结果→验证报告→复盘。
2. **一键复现**：固定命令跑通 3 个案例并生成完整运行目录。
3. **失败场景完善**：名称歧义（C-2 已修）、地点缺失、整晚不可见（C-3 已修）、强月光、日志信息不足。
4. **C-4 演示**：展示 chat 模式幻觉拦截的 before/after 对比。

**阶段验收：** 新环境可复跑；失败场景可解释；评委能在有限时间内看懂。

### 第 6 周（08-08 ~ 09-01）：评测、报告与提交材料

核心任务：

1. **科学交叉校验**：用 Stellarium/KStars 对固定案例交叉校验。
2. **对照实验**：传统人工流程 vs StarPlan 的时间、遗漏项、可复现性对比。
3. **提交材料**：PPT/PDF（≤20页）、技术报告、源码、Skills 清单与流程图、3 类任务运行记录、10 分钟演示视频。

**阶段验收：** 材料齐全；可复现；Qwen 边界和调用证据清楚。

---

## 四、风险提示

1. **星表坐标重建**（第 4 周最大风险）：37 条偏差坐标影响所有下游计算。若 SIMBAD 不可达，备选方案是用 Astropy 内置的 Messier 列表（仅 110 条，缺亮星部分）。
2. **演示技术未确认**：Streamlit vs FastAPI 仍待团队决定，影响第 5 周启动。
3. **Qwen 调用额度**：百炼免费额度有限，演示和测试需控制调用次数。
4. **GitHub 推送**：本轮修改尚未 commit/push，需尽快推送避免积压。

---

## 五、立即可做的下一步

1. **Commit 并推送本轮全部修改**（5 个修复 + 4 个测试文件 + schema 变更）。
2. **星表坐标重建**：用 `workspace/catalog_simbad_check.json` 中的 SIMBAD 权威值替换 `built_in_catalog_v1.json` 中 37 条偏差坐标。
3. **补写 `test_qwen_integration.py`**：至少覆盖 NL 解析和 outreach Qwen 生成的端到端路径。
4. **团队确认演示技术选择**（Streamlit vs FastAPI）。

---

## 六、本轮修改文件清单

| 文件 | 变更类型 | 关联修复 |
|---|---|---|
| `starplan_skills/observability_plan.py` | 修改 | C-1 |
| `starplan_skills/runner.py` | 修改 | C-2, C-4, C-5 |
| `starplan_skills/outreach_pack.py` | 修改 | C-3 |
| `starplan_skills/schemas.py` | 修改 | C-2, C-3, C-5 |
| `starplan_skills/exceptions.py` | 新增 | C-2 |
| `starplan_skills/__init__.py` | 修改 | C-2 |
| `tests/test_moon_separation_c1.py` | 新增 | C-1 |
| `tests/test_target_confirmation_c2.py` | 新增 | C-2 |
| `tests/test_not_observable_pack_c3.py` | 新增 | C-3 |
| `tests/test_chat_hallucination_c4.py` | 新增 | C-4 |
