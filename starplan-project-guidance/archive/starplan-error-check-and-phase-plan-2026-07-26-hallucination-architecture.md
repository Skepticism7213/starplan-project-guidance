# StarPlan Loop 错误排查报告与阶段安排（幻觉防护架构文档）

日期：2026-07-26

项目起始：2026-07-18 ｜ 截止：2026-09-01 ｜ 当前进度：第 3 周验收加固提案

---

## 一、本轮错误排查结论

本轮只新增指导文档 `starplan-hallucination-prevention-architecture.md`，没有修改 StarPlan 代码、数据、Schema、测试或运行配置。

静态检查结果：**0 个 CRITICAL，0 个 WARNING，3 个 INFO（均确认无害）。**

运行时检查结果：本轮没有受影响的代码或案例，因此没有重复运行天文计算、固定案例或在线 Qwen 测试，也不据此声称任何架构能力已经实现。

### CRITICAL

无。

### WARNING

无。

### INFO

| # | 检查项 | 结果 | 处理状态 |
|---|---|---|---|
| 1 | UTF-8 和异常字符 | 文档可按 UTF-8 完整读取，未发现 Unicode replacement character | 确认无害 |
| 2 | Markdown 代码围栏 | 共 18 个围栏标记，数量成对；包含 1 个 Mermaid 图 | 确认无害 |
| 3 | Source of Truth 边界 | 文档明确标记为“实施提案”，没有宣称自动取代项目计划 | 确认无害 |

### 受影响案例确认

- 代码和数据变更：无。
- 受影响的固定案例：无。
- 编译和运行：不适用；本轮没有可导致案例编译或运行回归的实现变更。
- 在线模型调用：未执行，避免把非确定性在线结果作为文档验收条件。

---

## 二、当前完成度对照项目计划

| 计划阶段 | 计划目标 | 本轮状态 |
|---|---|---|
| 第 1 周 | 冻结范围、Schema、案例和验证规则 | 未改变；提案建议后续重新冻结 Claim Schema 和状态机 |
| 第 2 周 | 目标解析与本地可观测性计算 | 未改变；提案补充公共坐标计算和回归守护要求 |
| 第 3 周 | Qwen 编排和科普活动包 | 新增完整加固指导，但尚未实施，不能记为代码验收完成 |
| 第 4 周 | 观测日志和复盘闭环 | 未改变；提案要求未来复盘归因复用 Evidence Claim 架构 |
| 第 5 周 | 演示入口和案例固化 | 未开始；建议在核心 fail-closed 架构完成后再推进 |
| 第 6 周 | 评测、报告和视频 | 未开始；提案给出了可用于评测的硬性指标 |

本轮完成的是架构指导材料，不是功能实现。项目计划中的现行状态不应因本文件而自动更新。

---

## 三、下一阶段计划

### Phase A：设计冻结

工作：冻结 Claim Schema、业务状态、数值显示规则、信任边界和验收指标；经团队确认后先更新项目计划，再同步 transfer log 和 diff log。

验收标准：Schema 有成功和失败示例；每个业务状态有确定性输出；团队确认 Qwen 默认只生成表达计划。

阻塞项：需要团队正式确认本提案是否成为项目基线。

风险：若跳过决策冻结直接改代码，Claim、状态和日志结构可能多次返工。

### Phase B 至 Phase C：Claim Registry 与 Qwen 安全协议

工作：实现 Allowed Claims Builder、安全句式、结构化表达计划、验证器和确定性回退。

验收标准：所有用户可见事实具备 Claim 映射；原始 Qwen 文本不存在直达用户路径；API 失败时仍能离线输出。

阻塞项：需要先完成 Phase A。

风险：只扩展现有正则或关键词列表会保留架构漏洞，不得作为 Phase 完成依据。

### Phase D 至 Phase F：状态机、证据链和对抗验收

工作：在 runner 层实现完整状态机，封装科学计算公共函数，建立 RunOutcome 和追加式审计事件，完成四层测试。

验收标准：用户可见无来源事实率为 0；验证失败原文泄漏率为 0；业务分支覆盖率和 Claim 映射覆盖率均为 100%。

阻塞项：需要稳定的离线 fixtures；真实 Qwen canary 需要 API Key 和调用额度，但不得阻塞离线核心验收。

风险：把真实 Qwen 测试作为默认 CI 条件会引入网络、额度和随机性问题。

---

## 四、立即下一步

1. 团队评审 `starplan-hallucination-prevention-architecture.md`，明确接受、修改或拒绝的条目。
2. 如接受，先在项目计划中记录 Claim Registry、Qwen 表达计划和 RunOutcome 决策。
3. 让 Qwen 只执行 Phase A，不要一次性跨越所有 Phase 改造代码。
4. Phase A 完成后生成新的 mandatory error-check report，并在验收通过后进入 Phase B。

---

## 五、本轮文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `starplan-hallucination-prevention-architecture.md` | 新增 | 可直接交给 Qwen 的完整幻觉防护架构和实施规范 |
| `starplan-error-check-and-phase-plan-2026-07-26-hallucination-architecture.md` | 新增 | 本次文档工作的强制错误检查和阶段安排 |
