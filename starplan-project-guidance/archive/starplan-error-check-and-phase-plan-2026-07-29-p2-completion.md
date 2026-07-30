# StarPlan Loop 错误检查与阶段计划 — P2 完成 + 阶段验收审查

日期：2026-07-29
基线：`2441f43`（P1 提交）+ 本轮未暂存改动
范围：P2（验收和工程卫生）全部 4 项 + 阶段验收标准逐条审查
性质：实现 + 验证 + 审计；未提交（待用户确认后 commit）

## 1. P2 完成清单

| 子项 | 要求 | 实现 | 涉及文件 |
|---|---|---|---|
| P2-1 | Layer 3 端到端用例 | 新增 `test_layer3_e2e.py`：7 个测试类、14 个测试方法覆盖强月光/工具异常/数据不足/Qwen 不可用/纯文字幻觉/Markdown 映射/隐私边界 | `tests/test_layer3_e2e.py` |
| P2-2 | SIMBAD 快照 + M24/M52 | 生成 `data/simbad_dim_otype.json`（150 条，含 otype + 角径）；M24/M52 加入精确六十分界允许列表 | `data/simbad_dim_otype.json`, `tests/layer23_validation.py` |
| P2-3 | 测试工程修复 | 移除 test_confidence_algorithm.py 全局 stdout 替换；class-scoped fixture 加 @classmethod；新增 `scripts/run_offline_ci.bat` | `tests/test_confidence_algorithm.py`, `tests/test_moon_separation_c1.py`, `scripts/run_offline_ci.bat` |
| P2-4 | 脱敏/保留期/导出 | 新增 `privacy.py`：AUDIT_ONLY/DELIVERABLE 文件分类、sanitize_run_for_export()、verify_blocked_content_not_in_output()、保留期策略 | `starplan_skills/privacy.py` |

## 2. 验证结果

| 检查 | 结果 |
|---|---|
| `compileall` | PASS |
| `validate_examples.py` | 3/3 PASS |
| Layer 1（150 目标 × 10 轮） | **0 issues** |
| Layer 2/3（含 SIMBAD 交叉验证） | **0 issues**（Checks 7/11 不再跳过） |
| 离线 pytest（含 confidence + Layer 3 E2E） | **119 passed**, 0 failed, 0 warnings |
| 三固定案例 | 全部退出码 0，RunOutcome 完整 |
| 强月光反例（M31 + max_moon_illumination=0.01） | not_observable，原因提及月光，无虚假高度角声称 |

## 3. 阶段验收标准逐条审查

| # | 标准 | 判定 | 证据 |
|---|---|---|---|
| 1 | 固定三案例和强月光反例均能生成完整 RunOutcome 目录 | **通过** | 三案例 + moonlight 均有 run_outcome.json（含 business/validation/delivery + file_hashes + claims_registry_hash） |
| 2 | render_trace 覆盖 100% 事实句 | **部分通过** | 可观测分支：sentence_claim_map.json 生成且 claim_id 均可溯源。不可观测分支（case 2）：缺 sentence_claim_map（取消包走独立模板路径，事实句来自 blocking_reasons 结构化数据，但映射文件未生成） |
| 3 | 纯文字幻觉/伪造 Claim/协议额外字段/哈希篡改不出现在用户输出 | **通过** | extra=forbid 拒绝协议外字段；哈希重算 + 全零拒绝；Chat 永远确定性渲染；E2E 测试验证 |
| 4 | 三状态正交；不可观测仍可验证通过 | **通过** | case 2: business=not_observable, validation=passed, delivery=template；moonlight 同理 |
| 5 | 默认离线 pytest + Layer 1/2/3 + 三案例可直接运行 | **通过** | `run_offline_ci.bat` 一条命令；119 passed 无 warning；Layer 1/2/3 均 0 issues |

## 4. "本阶段理应做到但没有做到" 8 项逐条审查

| # | 原始缺陷 | 当前状态 | 残留 |
|---|---|---|---|
| 1 | 所有用户可见事实统一经过 Claim 门禁 | **基本完成** | 可观测分支 100% Claim 渲染。不可观测分支的取消/改期文案从 blocking_reasons 结构化数据生成（非自由文本），但 sentence_claim_map 未覆盖该路径 |
| 2 | 业务、验证、交付状态统一且可审计 | **完成** | RunOutcome 三状态正交落盘，state_log 记录转换，file_hashes 绑定 |
| 3 | 不可观测原因忠实于实际约束 | **完成** | blocking_reasons 从 eliminated_windows.violated_constraint 派生；强月光反例验证通过（不再声称高度角过低） |
| 4 | 复盘归因复用 Evidence Claims | **完成** | observation_review 传入 log_path，调用进入 model_call_log；归因分类用结构化字段 |
| 5 | 科学派生规则可解释、可适用 | **完成** | derivation_rule 标注 scope/caveat/missing；深空小角径 → UNCONFIRMED；display_value 加条件限定 |
| 6 | 契约、文档和代码同步 | **完成** | skills.yaml v0.2.0 + README 证据链架构 + MVP 限制 + 产物清单 |
| 7 | Layer 3 和真实验收口径闭合 | **完成** | 14 个 E2E 测试覆盖 6 类场景 + 隐私边界；从 run_starplan 入口断言最终产物 |
| 8 | 可重复验证环境可直接运行 | **完成** | 全局 stdout 替换已移除；fixture 弃用已修；`run_offline_ci.bat` 一条命令 |

## 5. 残留项（不阻塞验收，建议后续处理）

| 优先级 | 项目 | 说明 |
|---|---|---|
| LOW | 不可观测分支 sentence_claim_map | 取消包模板路径未生成映射文件；事实来源是结构化的，但审计覆盖形式不完整 |
| LOW | qwen_client.py TOOL_DEFINITIONS 描述 | 仍写"事实卡"，未提及 Claim Registry（功能不受影响） |
| LOW | 设备匹配独立 Claim | 当前仅影响模板选择，未生成 derived.equipment_match Claim |
| INFO | constraints_applied 为空 | 三案例的 RunOutcome.constraints_applied 只有 refraction_policy，未记录用户自定义约束（如 max_moon_illumination） |

## 6. 文件变更摘要

```
StarPlan/data/simbad_dim_otype.json          | NEW (150 entries)
StarPlan/scripts/run_offline_ci.bat          | NEW
StarPlan/starplan_skills/privacy.py          | NEW
StarPlan/tests/test_layer3_e2e.py            | NEW (14 tests)
StarPlan/tests/layer23_validation.py         | M24/M52 allowlist
StarPlan/tests/test_confidence_algorithm.py  | removed global stdout/stderr
StarPlan/tests/test_moon_separation_c1.py    | @classmethod fixture fix
```

提交时排除 `AGENTS.md`（LOCAL-ONLY）和 `tests/confidence_test_results.json`（运行产物）。
