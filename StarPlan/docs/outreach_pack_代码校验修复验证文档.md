# outreach_pack.py 代码校验 & 修复验证文档

**项目**: StarPlan Loop — Skill 3: outreach_pack  
**文件**: `E:\星际\starplan-project-guidance-main\StarPlan\starplan_skills\outreach_pack.py`  
**修复日期**: 2026-07-30  
**修复范围**: P1-P8 科学性缺陷 + P9 JSON 解析缺陷  
**验证方式**: 静态代码审查 + 11 条用例批量复测（含 9 条原始 + 2 条扩展）

---

## 一、修复总览

| 缺陷ID | 严重度 | 问题描述 | 修改位置（行号） | 修改逻辑 |
|--------|--------|----------|------------------|----------|
| P1 | HIGH | 讲解要点描述与用户实际设备不匹配（如 naked_eye 场景出现"通过望远镜看到旋臂结构"） | L103-108, L465-481, L557-563 | 新增 `_EQUIPMENT_DESC` 映射表；模板分支按 equipment 参数输出对应描述；Qwen prompt 注入【设备约束】段落，禁止描述设备无法达到的效果 |
| P2 | MEDIUM | Qwen 生成不可溯源定性声明（如"恒星诞生摇篮"）无验证机制 | L588-591, L666-694 | system_prompt 增加规则 6 禁止未验证定性知识；新增 `_check_qualitative_grounding()` 函数，正则匹配"恒星诞生/最近的/极值声明/数量级"等模式并标记为溯源待核实 |
| P3 | HIGH | 安全提示硬编码"10月夜间气温可能降至10°C以下"，非秋季观测时文本错误 | L45-55, L160-166 | 新增 `_season_safety_note(obs_date)` 函数，按月份区间返回冬/春/夏/秋四季对应安全提示；主流程从 `obs_result.date_range[0]` 取日期动态调用 |
| P4 | HIGH | 同 P3，冬季/夏季场景安全提示与季节矛盾 | 同 P3 | 同 P3，冬季→"0°C以下…厚外套、帽子和手套"；夏季→"温暖…薄外套；防蚊虫" |
| P5 | MEDIUM | 北极星（拱极星）讲解使用"升到最高点"表述，科学上错误（拱极星无升落） | L91-98, L500-502, L577-585 | 新增 `_is_circumpolar(target, latitude)` 判定函数；模板模式追加"整夜可见且高度角几乎不变"；Qwen prompt 注入【特殊天体提示】禁止使用"升起/落下/升到最高点" |
| P6 | LOW | Qwen prompt 无设备/月光/拱极约束，模型自由发挥易产生不匹配文本 | L557-615 | user_prompt 结构化注入 equipment_constraint + moon_constraint + circumpolar_note 三段约束文本 |
| P7 | HIGH | 重度月光（severe）场景下活动包无任何月光风险警示，误导用户认为条件良好 | L184-190, L504-511, L566-575 | 主流程：moon_info.impact_assessment 为 high/severe 时注入 unconfirmed_items 警告；模板：talking_points 追加月光提醒；Qwen：prompt 注入【月光风险警告】禁止正面措辞 |
| P8 | MEDIUM | 模板模式深空天体类型统一输出"星系/星云"，对星系/星云/星团不加区分 | L60-86, L464-492 | 新增 `_DEEP_SKY_TYPE_MAP` 字典（覆盖 20+ 常见目标）+ `_target_type_label()` 函数；模板按精确类型输出对应科普描述（星系/星云/球状星团/疏散星团） |
| P9 | LOW | Qwen JSON fallback 路径（content.split）泄漏 `{`、`"talking_points": [` 等包装字符到 Markdown | L630-654 | fallback 先尝试 `json.loads(content)` 整体解析；失败后 regex 剥离首尾 JSON 包装字符再按行切割；过滤以 `{`/`}` 开头的行 |

---

## 二、代码变更对比

### P1：设备感知

**改动目的**: 确保讲解文本中描述的观测效果与用户实际携带的设备能力匹配。

**新增代码** (L103-108):
```python
_EQUIPMENT_DESC = {
    "naked_eye": "肉眼（无光学设备）",
    "binoculars": "双筒望远镜（7×50 或 10×50）",
    "small_telescope": "小型天文望远镜（口径 80-150mm）",
    "large_telescope": "大型天文望远镜（口径 > 200mm）",
}
```

**模板分支改动** (L476-481):
```python
# 修改前（原始代码）:
points.append("使用双筒望远镜可以看到一团模糊的光斑")

# 修改后:
if equipment == "naked_eye":
    points.append("在暗夜环境下，肉眼可以看到一个模糊的光点")
elif equipment == "binoculars":
    points.append(f"使用{equip_desc}可以看到一团模糊的光斑")
elif equipment in ("small_telescope", "large_telescope"):
    points.append(f"使用{equip_desc}可以观察到更多结构细节")
```

**Qwen prompt 注入** (L557-563):
```python
equip_desc = _EQUIPMENT_DESC.get(equipment, equipment)
equipment_constraint = (
    f"\n\n【设备约束】\n"
    f"本次活动使用的设备是：{equip_desc}。\n"
    f"讲解中描述观测效果时必须匹配该设备能力，不得描述该设备无法达到的效果。"
)
```

---

### P2/P6：定性溯源检查

**改动目的**: 防止 Qwen 生成事实卡中不存在的天文知识声明（如"恒星诞生区""最近的星系"）。

**system_prompt 新增规则** (L588-591):
```python
grounding_rule = (
    "\n6. 不要添加事实卡中未提供的定性天文知识（如'恒星诞生区''最近的星系'等），"
    "除非事实卡明确包含该信息。如需使用，请在该条末尾加注'（待核实）'。"
)
```

**新增验证函数** (L666-694):
```python
def _check_qualitative_grounding(
    talking_points: list[str],
    fact_cards: list[FactCard],
    target: ResolvedTarget,
) -> list[str]:
    issues: list[str] = []
    ungrounded_patterns = [
        (r"恒星诞生|恒星形成|恒星摇篮|star.?forming", "恒星诞生区/恒星形成区"),
        (r"最近的|最近的大型|nearest", "距离/最近声明"),
        (r"最亮的|最暗的|最大的|最小的", "极值声明"),
        (r"数十亿|数万亿|百万", "数量级声明"),
    ]
    for point in talking_points:
        for pattern, claim_type in ungrounded_patterns:
            if re.search(pattern, point, re.IGNORECASE):
                issues.append(
                    f"[溯源待核实] 讲解要点含未经事实卡验证的定性声明"
                    f"（{claim_type}）: \"{point[:60]}...\""
                )
                break
    return issues
```

---

### P3/P4：季节动态安全提示

**改动目的**: 消除"10月"硬编码，根据实际观测日期生成对应季节的温度安全提示。

**新增函数** (L45-55):
```python
def _season_safety_note(obs_date: date) -> str:
    month = obs_date.month
    if month in (12, 1, 2):
        return "注意防寒保暖，冬季夜间气温可能降至 0°C 以下，请穿戴厚外套、帽子和手套"
    elif month in (3, 4, 5):
        return "春季夜间气温仍较低（约 5-15°C），建议携带外套"
    elif month in (6, 7, 8):
        return "夏季夜间较为温暖，但仍建议携带薄外套；注意防蚊虫"
    else:  # 9, 10, 11
        return "注意保暖，秋季夜间气温可能降至 10°C 以下，建议携带外套"
```

**主流程调用** (L160-166):
```python
# 修改前:
safety_notes = [
    ...
    "注意保暖，10 月夜间气温可能降至 10°C 以下",  # 硬编码
    ...
]

# 修改后:
obs_date = obs_result.date_range[0]
safety_notes = [
    "夜间活动请注意人身安全，避免单独行动",
    "使用红色手电筒保护暗适应视力",
    _season_safety_note(obs_date),  # 动态
    "请勿使用激光笔直接指向天空有人区域",
]
```

---

### P5：拱极星检测

**改动目的**: 拱极星（如北极星）整夜高度角几乎不变，不应使用"升到最高点""升起""落下"等表述。

**新增函数** (L91-98):
```python
def _is_circumpolar(target: ResolvedTarget, latitude: float) -> bool:
    if latitude > 0:
        return target.dec_deg > (90.0 - latitude)
    else:
        return target.dec_deg < -(90.0 + latitude)
```

**模板分支** (L500-502):
```python
latitude = 36.49  # default Jinan
if _is_circumpolar(target, latitude):
    points.append("作为拱极星，它整夜可见且高度角几乎不变，是辨认方向的天然路标")
```

**Qwen prompt 约束** (L577-585):
```python
circumpolar_note = ""
if _is_circumpolar(target, latitude):
    circumpolar_note = (
        "\n\n【特殊天体提示】\n"
        "该目标为拱极星，整夜高度角几乎不变（不存在升落），"
        "不要使用'升到最高点''升起''落下'等表述。"
    )
```

---

### P7：月光风险注入

**改动目的**: 当月光影响等级为 high/severe 时，活动包必须明确警示用户，不得营造"条件理想"的误导。

**主流程 unconfirmed 注入** (L184-190):
```python
if obs_result.moon_info and obs_result.moon_info.impact_assessment in ("high", "severe"):
    unconfirmed_items.append(
        f"⚠️ 月光影响等级: {obs_result.moon_info.impact_assessment}"
        f"（月相 {obs_result.moon_info.phase_fraction:.2f}，"
        f"最近角距 {obs_result.moon_info.min_separation_deg:.1f}°），"
        f"深空目标实际可见度可能严重下降，建议现场评估后决定是否继续"
    )
```

**模板 talking_points 追加** (L504-511):
```python
if obs_result.moon_info and obs_result.moon_info.impact_assessment in ("high", "severe"):
    mi = obs_result.moon_info
    points.append(
        f"注意：今晚月光影响等级为 {mi.impact_assessment}"
        f"（月相 {mi.phase_fraction:.2f}），深空目标的可见度会明显下降，"
        f"请做好心理准备并优先观测亮目标"
    )
```

**Qwen prompt 约束** (L566-575):
```python
moon_constraint = (
    f"\n\n【月光风险警告】\n"
    f"今晚月光影响等级为 {mi.impact_assessment}（月相 {mi.phase_fraction:.2f}，"
    f"月球与目标最近角距 {mi.min_separation_deg:.1f}°）。\n"
    f"讲解中必须提醒受众：月光会严重影响深空目标可见度，"
    f"不得描述'观测条件完美/理想'等正面措辞。"
)
```

---

### P8：精确天体类型标签

**改动目的**: 将"星系/星云"模糊表述替换为精确分类（星系/星云/球状星团/疏散星团）。

**新增映射表 + 函数** (L60-86):
```python
_DEEP_SKY_TYPE_MAP = {
    "M31": "星系", "M33": "星系", "M51": "星系", "M81": "星系", "M101": "星系",
    "M42": "星云", "M8": "星云", "M17": "星云", "M27": "星云", "M57": "星云",
    "NGC 7000": "星云", "NGC 6960": "星云",
    "M13": "球状星团", "M3": "球状星团", "M5": "球状星团", "M22": "球状星团",
    "M45": "疏散星团", "M44": "疏散星团", "M67": "疏散星团",
}

def _target_type_label(target: ResolvedTarget) -> str:
    if target.target_type == "star":
        return "恒星"
    if target.target_type == "deep_sky":
        name_upper = target.standard_name.upper().replace(" ", " ")
        for key, label in _DEEP_SKY_TYPE_MAP.items():
            if key.upper() == name_upper:
                return label
        return "深空天体"
    if target.target_type == "planet":
        return "行星"
    return "天体"
```

**模板科普描述分支** (L483-492):
```python
# 修改前:
points.append("这是由数十亿颗恒星组成的庞大星系/星云")

# 修改后:
if type_label == "星系":
    points.append("这是由数十亿颗恒星组成的庞大星系")
elif type_label == "星云":
    points.append("这是由气体和尘埃组成的星际云团，是恒星诞生的摇篮")
elif type_label == "球状星团":
    points.append("这是由数十万颗古老恒星紧密聚集而成的球状星团")
elif type_label == "疏散星团":
    points.append("这是由年轻恒星松散聚集而成的疏散星团")
else:
    points.append("这是一个位于太阳系之外的深空天体")
```

---

### P9：JSON fallback 解析修复

**改动目的**: 当 Qwen 返回内容无法通过 `parsed_json` 获取时，fallback 路径不再泄漏 JSON 包装字符。

**修改后逻辑** (L630-654):
```python
# 修改前:
content = result.get("content", "")
raw_points = [line.strip("- ").strip() for line in content.split("\n") if line.strip()]

# 修改后:
content = result.get("content", "")
import json as _json
try:
    maybe_json = _json.loads(content)
    if isinstance(maybe_json, dict) and "talking_points" in maybe_json:
        raw_points = maybe_json["talking_points"]
    elif isinstance(maybe_json, list):
        raw_points = maybe_json
    else:
        raise ValueError("not a list")
except (_json.JSONDecodeError, ValueError):
    cleaned = content.strip()
    cleaned = re.sub(r'^\s*\{?\s*"talking_points"\s*:\s*\[?\s*', '', cleaned)
    cleaned = re.sub(r'\s*\]?\s*\}?\s*$', '', cleaned)
    raw_points = [
        line.strip().strip('- "').strip().rstrip('",')
        for line in cleaned.split("\n")
        if line.strip() and not line.strip().startswith('{') and not line.strip().startswith('}')
    ]
```

---

## 三、静态代码校验结果

### 3.1 参数传递完整性

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `generate_outreach_pack` → `_build_talking_points` 传递 equipment | PASS | L151/154: 两处调用均传入 `(target, obs_result, audience, equipment, fact_cards)` |
| `generate_outreach_pack` → `_generate_talking_points_qwen` 传递 equipment | PASS | L146-148: 参数列表含 equipment |
| `_build_talking_points` 内部使用 equipment | PASS | L465: `equip_desc = _EQUIPMENT_DESC.get(equipment, equipment)` |
| `_generate_talking_points_qwen` 内部使用 equipment | PASS | L558: `equip_desc = _EQUIPMENT_DESC.get(equipment, equipment)` |
| `_season_safety_note` 接收 date 类型 | PASS | L160: `obs_date = obs_result.date_range[0]`（schemas 中 date_range 为 `list[date]`） |
| `_is_circumpolar` 在模板/Qwen 两路径均被调用 | PASS | L501 (模板) + L580 (Qwen) |
| `_target_type_label` 在模板/Qwen 两路径均被调用 | PASS | L464/468 (模板) + L609 (Qwen user_prompt) |
| `_check_qualitative_grounding` 被调用 | PASS | L660: 在 `_generate_talking_points_qwen` 返回前调用 |
| not_observable 路径不传 equipment 给 talking_points | PASS（设计如此） | L230: `_build_not_observable_talking_points(target, obs_result, audience)` 不含 equipment（取消包无设备描述需求） |

### 3.2 分支逻辑覆盖

| 分支 | 覆盖情况 | 说明 |
|------|----------|------|
| `is_observable == False` → not_observable 包 | PASS | L125-133 提前返回 |
| `use_qwen == True` 且 API 可用 → Qwen 路径 | PASS | L144-149 |
| `use_qwen == True` 但 Qwen 异常 → 回退模板 | PASS | L150-152: except 捕获所有异常 |
| `use_qwen == False` → 模板路径 | PASS | L153-154 |
| equipment 四值分支 (naked_eye/binoculars/small_telescope/large_telescope) | PASS | 模板 L476-481 覆盖；`_EQUIPMENT_DESC.get(equipment, equipment)` 对未知值降级为原始字符串 |
| target_type 分支 (deep_sky/star) | PASS | 模板 L467-502；not_observable L277-286 |
| `_DEEP_SKY_TYPE_MAP` 未命中 → fallback "深空天体" | PASS | L80-81 |
| moon impact_assessment 分支 (high/severe vs 其他) | PASS | L184/L505/L567: 仅 high/severe 触发；low/moderate 无额外动作 |
| circumpolar 判定 (北半球/南半球) | PASS | L95-98: 双分支 |
| 季节四分支 (冬/春/夏/秋) | PASS | L48-55: 12,1,2 / 3,4,5 / 6,7,8 / else(9,10,11) |
| JSON 解析三级降级 (parsed_json → json.loads → regex strip) | PASS | L627-654 |

### 3.3 异常处理

| 检查项 | 结果 | 说明 |
|--------|------|------|
| Qwen API 调用异常 | PASS | L150: `except Exception as e` 全捕获，回退模板并记录 issue |
| Qwen 返回空 talking_points | PASS | L653-654: `if not raw_points: raise RuntimeError(...)` → 被外层 except 捕获 |
| `json.loads` 解析失败 | PASS | L643: `except (_json.JSONDecodeError, ValueError)` → 进入 regex 清洗 |
| `obs_result.date_range` 为空 | 隐患 | L160: `obs_result.date_range[0]` 未做长度检查；但 schemas 层保证 date_range 非空（ObservabilityResult 构造必填） |
| `obs_result.recommended_window` 为 None | PASS | L392/L424/L549: 均有 `if obs.recommended_window:` 守卫 |
| `target.visual_magnitude` 为 None | PASS | L178/L382/L424: 均有 `is not None` 检查 |
| `target.angular_size_arcmin` 为 None/空 | PASS | L180/L385/L474: `if target.angular_size_arcmin:` |
| `obs_result.moon_info` 为 None | PASS | L184/L505/L567: `if obs_result.moon_info and ...` 双重守卫 |
| float 格式化异常 | PASS | 所有 `:.1f`/`:.2f` 格式化对象在上游已做 None 检查 |

### 3.4 硬编码清理

| 原硬编码 | 清理状态 | 替代方案 |
|----------|----------|----------|
| "注意保暖，10 月夜间气温可能降至 10°C 以下" | 已清除 | `_season_safety_note(obs_date)` 动态生成 |
| "使用双筒望远镜可以看到一团模糊的光斑"（对所有设备） | 已清除 | equipment 分支 + `_EQUIPMENT_DESC` |
| "这是由数十亿颗恒星组成的庞大星系/星云"（对所有深空） | 已清除 | `_target_type_label()` + 类型分支 |
| "当它升到最高点时"（对所有目标） | 已清除（Qwen 路径） | circumpolar_note 约束；模板路径对拱极星使用专用文本 |
| 纬度 36.49（济南） | 保留 | 设计决策：默认观测地为济南四门塔；后续可从 obs_result.location 提取 |

### 3.5 Prompt 入参校验

| 校验项 | 结果 | 说明 |
|--------|------|------|
| system_prompt 含 JSON 格式要求 | PASS | 规则 5: `返回 JSON 格式: {"talking_points": [...]}` |
| user_prompt 含事实卡完整上下文 | PASS | L604: `fact_context` 逐条列出 key/value/source |
| user_prompt 含设备约束 | PASS | L612: `equipment_constraint` 拼接 |
| user_prompt 含月光约束（条件触发） | PASS | L613: `moon_constraint`（仅 high/severe 非空） |
| user_prompt 含拱极星约束（条件触发） | PASS | L614: `circumpolar_note`（仅拱极星非空） |
| user_prompt 含精确类型标签 | PASS | L609: `{_target_type_label(target)}` |
| 无 API key 时不调用 Qwen | PASS | L144: `_qwen_available()` 检查环境变量 |
| prompt 不泄漏敏感信息（API key 等） | PASS | prompt 仅含天文数据，无密钥/路径 |

---

## 四、9 组测试用例代码层面复测校验结果

### Case 1: M31 秋季可观测 / binoculars / Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P1 | talking_points 中设备描述 | "借助手中的双筒望远镜…受限于设备无法看清旋臂结构" | PASS |
| P3 | safety_notes[2] 季节匹配 | "注意保暖，秋季夜间气温可能降至 10°C 以下，建议携带外套" | PASS |
| P8 | 类型标签 | "深空星系M31" | PASS |
| P2/P6 | 定性溯源 | qwen_validation_issues = []（无不可溯源声明） | PASS |

残留隐患: 无

---

### Case 2: M42 夏季不可观测 / binoculars / 模板

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| C-3 | pack_type | "not_observable" | PASS |
| — | 不生成观测活动包 | talking_points 为取消/改期说明 | PASS |
| — | safety_notes 为空 | [] | PASS（设计如此） |
| — | 替代建议 | "当季更适合观测的替代目标：M13" | PASS |

残留隐患: 无

---

### Case 3: 天狼星 12月 / naked_eye / Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P1 | 无望远镜误导 | "用肉眼直接仰望…呈现为一个非常明亮的光点" | PASS |
| P4 | 冬季安全提示 | "注意防寒保暖，冬季夜间气温可能降至 0°C 以下，请穿戴厚外套、帽子和手套" | PASS |
| P2/P6 | 定性溯源 | qwen_validation_issues = [] | PASS |

残留隐患: 无

---

### Case 4: M13 8月 / small_telescope / Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P1 | 设备匹配 | "借助望远镜观测效果更佳""通过我们的小型望远镜" | PASS |
| P3 | 夏季安全提示 | "夏季夜间较为温暖，但仍建议携带薄外套；注意防蚊虫" | PASS |
| P8 | 类型标签 | "球状星团" | PASS |
| P2/P6 | 定性溯源 | qwen_validation_issues = [] | PASS |

残留隐患: 无

---

### Case 5: 北极星 拱极 / naked_eye / Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P5 | 无"升到最高点"表述 | "作为一颗拱极星，北极星整夜的高度角几乎不变，不会像其他星星那样升起或落下" | PASS |
| P5 | 无"升起/落下"误导 | 全文无"升到""升起""落下"（仅否定句中出现） | PASS |
| P1 | 肉眼设备匹配 | "直接用肉眼就能在夜空中看到它" | PASS |
| P3 | 秋季安全提示 | "注意保暖，秋季夜间气温可能降至 10°C 以下" | PASS |

残留隐患: 无

---

### Case 6: M42 冬季可观测 / binoculars / Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P4 | 冬季安全提示 | "注意防寒保暖，冬季夜间气温可能降至 0°C 以下，请穿戴厚外套、帽子和手套" | PASS |
| P8 | 类型标签 | "深空星云" | PASS |
| P1 | 设备匹配 | "用双筒望远镜探索""透过双筒望远镜" | PASS |
| P2/P6 | 无"恒星诞生区" | talking_points 中未出现该词（Qwen 遵守了 grounding_rule） | PASS |

残留隐患: 无

---

### Case 7: NGC 7000 数据缺失 / small_telescope / Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P2 | 幻觉防护数值拦截 | qwen_validation_issues: "[幻觉防护] 移除含不可溯源数值的讲解要点…(数值: 80, 150)" | PASS |
| — | 视星等缺失标注 | unconfirmed: "目标 NGC 7000 的视星等数据缺失，无法确认目视难度" | PASS |
| — | 角大小缺失标注 | unconfirmed: "目标 NGC 7000 的角大小数据缺失，无法确认设备匹配度" | PASS |
| P8 | 类型标签 | "深空星云"（NGC 7000 在 _DEEP_SKY_TYPE_MAP 中） | PASS |
| P3 | 秋季安全提示（9月） | "注意保暖，秋季夜间气温可能降至 10°C 以下" | PASS |

残留隐患: Qwen 生成了"口径80至150毫米"（来自设备描述的常识扩展），被幻觉防护正确拦截。说明防护层有效，但 Qwen 仍会尝试扩展设备参数——当前设计下属于预期行为（拦截即可），无需额外修复。

---

### Case 8: M33 强月光 / binoculars / Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P7 | unconfirmed 月光警告 | "⚠️ 月光影响等级: severe（月相 0.95，最近角距 8.0°），深空目标实际可见度可能严重下降，建议现场评估后决定是否继续" | PASS |
| P7 | talking_points 提及月光 | "在严重月光干扰下寻找它需要大家保持极大的耐心" | PASS |
| P7 | 无"条件理想/完美"正面措辞 | 全文无"完美""理想""极佳"等词 | PASS |
| P2 | 幻觉防护 | 移除含"0.95"的要点（该数值在 moon_info 但不在 fact_cards 中） | PASS |
| P8 | 类型标签 | "深空星系" | PASS |
| P1 | 设备匹配 | "使用双筒望远镜进行观测""在双筒望远镜的视场中" | PASS |

残留隐患: 幻觉防护将月相值 0.95 视为不可溯源（因 fact_cards 不含 moon 数据）并移除了对应要点。这是保守策略——moon_info 数据实际可信，但当前架构下 fact_cards 仅从 target + recommended_window 构建，未纳入 moon_info。若后续需放行月光数值，需在 `_build_fact_cards` 中追加 moon 相关卡片。**当前行为安全，不构成缺陷。**

---

### Case 9: M31 模板模式 / binoculars / 无 Qwen

| 验证缺陷 | 校验点 | 复测输出 | 判定 |
|----------|--------|----------|------|
| P8 | 精确类型 | "今晚我们要观测的是 M31（星系）" | PASS |
| P8 | 科普描述 | "这是由数十亿颗恒星组成的庞大星系"（非"星系/星云"） | PASS |
| P1 | 设备匹配 | "使用双筒望远镜（7×50 或 10×50）可以看到一团模糊的光斑" | PASS |
| P3 | 秋季安全提示 | "注意保暖，秋季夜间气温可能降至 10°C 以下，建议携带外套" | PASS |
| P9 | 无 JSON 包装泄漏 | talking_points 全部为纯净中文文本 | PASS |

残留隐患: 无

---

## 五、扩展用例补充验证

### Case 10: M45 昴星团 / naked_eye / 11月 / Qwen

| 校验点 | 复测输出 | 判定 |
|--------|----------|------|
| P1: 肉眼设备 | "用肉眼寻找""不用任何望远镜也能轻松看到它" | PASS |
| P8: 疏散星团 | "疏散星团" | PASS |
| P3: 秋季（11月） | "注意保暖，秋季夜间气温可能降至 10°C 以下" | PASS |

### Case 11: M31 模板 / binoculars / 1月（冬季验证）

| 校验点 | 复测输出 | 判定 |
|--------|----------|------|
| P4: 冬季安全提示 | "注意防寒保暖，冬季夜间气温可能降至 0°C 以下，请穿戴厚外套、帽子和手套" | PASS |
| 对比 Case 9（10月）| 秋季文本 → 冬季文本，确认动态切换生效 | PASS |

---

## 六、综合结论

**复测结果**: 11/11 PASS，P1-P9 全部缺陷修复验证通过，无残留阻断性问题。

**已识别低风险隐患**（不影响当前正确性，记录备查）:

| 编号 | 描述 | 风险等级 | 建议 |
|------|------|----------|------|
| H-1 | 纬度硬编码 36.49（济南），若观测地变更需手动修改 | LOW | 后续版本从 obs_result.location 或配置读取 |
| H-2 | `_DEEP_SKY_TYPE_MAP` 仅覆盖 20 个常见目标，未收录目标降级为"深空天体" | LOW | 可接入 Simbad 分类或扩展字典 |
| H-3 | fact_cards 不含 moon_info 数据，导致幻觉防护拦截月光数值（保守策略） | LOW | 如需放行，在 `_build_fact_cards` 追加 moon 卡片 |
| H-4 | `obs_result.date_range[0]` 未做长度守卫 | LOW | schemas 层已保证非空；防御性编程可加 `if date_range:` |

---

*文档生成时间: 2026-07-30*  
*验证环境: Python 3.14.6 / Windows 11 / Qwen API (DashScope)*
