# W1-5 修复验证日志

**日期**: 2026-07-24  
**修复人**: m21m0721  
**对应报告**: StarPlan Loop 独立错误排查与阶段安排 (WARNING W-1 ~ W-5)

---

## W-1: layer23_validation.py 健壮性修复

**问题**: 脚本依赖 `data/simbad_dim_otype.json`，文件缺失时直接崩溃；且不覆盖坐标/星等验证。

**修复内容**:
1. `load_data()` 改为检测文件是否存在，缺失时打印警告并返回空dict，SIMBAD相关检查(7/11)自动跳过
2. 新增 Check 5 `check_coordinates`: RA∈[0,360)、Dec∈[-90,90]、重复坐标检测、精度检查(≥3位小数)
3. 新增 Check 6 `check_visual_magnitude`: 恒星[-2,7]、深空[-1,12]范围校验

**测试结果**: 10轮运行，8个精度WARNING（M24/M40/M43/M52/M73/M8/M80坐标仅2位小数），无CRITICAL，非代码错误属数据精度问题。

---

## W-2: 目录验证溯源性补充

**问题**: 星表数据无来源记录，"0.36角秒精度"实为存储分辨率非测量精度，无法追溯SIMBAD查询时间和方法。

**修复内容**:
1. 新建 `data/catalog_provenance.json`，包含:
   - `field_sources`: 8个字段的逐一来源说明（SIMBAD/IAU/Messier文献/ Yale Bright Star Catalog）
   - `simbad_query_info`: 查询服务(TAP)、查询日期(2026-07-18)、坐标历元(J2000.0)、精度说明
   - `validation_history`: 验证记录（layer1 + layer23）
2. `layer23_validation.py` 新增 Check 4 `check_provenance`: 验证溯源文件存在且字段完整

**测试结果**: Provenance check ALL PASS。

---

## W-3: NL解析调用写入审计日志

**问题**: `run_starplan_nl()` 调用 `parse_natural_language(user_text)` 时未传递 `log_path`，导致NL解析的模型调用不出现在 `model_call_log.jsonl` 中。

**修复内容**:
- `runner.py` 中 `run_starplan_nl()` 提前生成 `run_id` 和 `run_dir`
- 将 `log_path = str(run_dir / "model_call_log.jsonl")` 传给 `parse_natural_language()`
- 后续 `run_starplan(input_data, run_id=run_id)` 复用同一目录，日志连续

**验证**: 代码审查确认 log_path 传递链完整（parse_natural_language → call_qwen_json → _log_call）。

---

## W-4: Chat编排工具定义补全

**问题**: `qwen_client.py` 的 `TOOL_DEFINITIONS` 仅3个工具（target_resolve/resolve_location/observability_plan），缺少outreach_pack和observation_review，4-Skill闭环不完整。

**修复内容**:
- 新增 `outreach_pack` 工具定义: 参数含target_name/audience/equipment/goal，描述中注明必须在target_resolve和observability_plan之后调用
- 新增 `observation_review` 工具定义: 参数含target_name/observation_log/planned_window，用于观测回顾评估

**验证**: 模块可正常import，TOOL_DEFINITIONS包含5个工具定义。

---

## W-5: 幻觉防护增强

**问题**: 
1. `_validate_talking_points()` 仅校验阿拉伯数字，不检查文本事实（如"254万光年"、"恒星诞生区"、"肉眼可见"）
2. 安全提示硬编码"10月夜间气温可能降至10°C以下"，7月观测M42也会显示此条

**修复内容**:
1. 文本事实验证（`outreach_pack.py`）:
   - 距离描述拦截: 正则匹配"X光年/X万光年"，事实卡无距离数据则移除
   - 物理性质校验: "恒星诞生区/行星状星云/球状星团"等必须与target_type一致
   - 可见性校验: "肉眼可见"需视星等≤6.0支撑
2. 动态温度提示:
   - 从 `obs_result.date_range[0]` 提取月份
   - 11-2月→冬季保暖(0°C以下)、3-4/10月→春秋保暖(10°C以下)、5/9月→薄外套、6-8月→防蚊补水

**测试结果**: 原有8个幻觉防护单元测试全部PASS，无回归。

---

## 测试汇总

| 测试项 | 结果 |
|--------|------|
| test_confidence_algorithm.py (150条) | 150 PASS / 0 FAIL |
| test_hallucination_protection.py (8条) | 8 PASS / 0 FAIL |
| layer23_validation.py (10轮×8检查) | 8 WARNING(精度) / 0 CRITICAL |

**结论**: W1-5全部修复完成，无回归错误。
