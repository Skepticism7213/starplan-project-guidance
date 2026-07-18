# 星程 StarPlan Loop 项目启动报告

日期：2026-07-18
截止日期：2026-09-01
可用时间：约 6.5 周（45 天）
状态：待团队确认

---

## 1. 项目目标和边界的理解

### 项目目标

StarPlan Loop 的目标不是做一个新的天文观测计划软件——Astropy、astroplan、Stellarium 和 KStars 已经具备成熟的计算能力。项目要做的是：把分散在多个工具中的目标解析、可观测性计算、科普表达、活动记录和反馈修正，改造成 Qwen 智能体可以稳定调用的 AI Ready Skills 包，并且每次运行都保留完整的证据链。

核心叙事应统一表述为：

> 本项目将校园天文观测中"计划—执行—复盘"这一真实但分散的工作流，封装为 Qwen 可调用的闭环 Skills 包，实现工具算、模型讲、报告验、人员确认、日志促改进。

三个必须反复强调的差异点：

1. 确定性计算与大模型分工明确：模型绝不编造天文数值。
2. 从计划生成延伸到实际活动复盘：不是一次性内容生成，而是闭环。
3. 每次运行形成可复现的"观测配方"：输入、计算、规则、模型版本和人工修改均可追踪。

### 技术边界

以下边界不可突破：

- Qwen 负责自然语言理解、任务编排、工具调用和基于事实卡的科普表达。
- Qwen 不得直接编造高度角、方位角、日落时间、月亮位置、行星坐标等关键天文数值。
- 首期优先采用 Python + Astropy/astroplan 等本地可复现工具；在线天文服务不能作为核心演示的单点故障。
- 百炼/Qwen 的模型名称、调用方式、工具调用输入输出和模型版本必须可审计。
- 行星星历、Stellarium/Aladin 接入、校园地平线遮挡模型属于后续扩展，只有在核心闭环稳定后才能加入。

### 明确不做的事项

- 望远镜硬件控制
- 实时天气预报系统
- 账户体系和社区平台
- 覆盖所有类型天体和天象
- 模型微调
- 多智能体编排
- 复杂 3D 前端

### 核心原则

```text
工具算，模型讲，报告验，人员确认，日志促改进。
```

所有关键天文数值必须来自确定性天文工具，并保留来源和中间结果。Qwen 只能基于工具生成的事实卡做任务理解、流程编排和科普表达。

---

## 2. 当前最小可行 MVP 的明确范围

### MVP 必须完成

| 序号 | 内容 | 验收标准 |
|---|---|---|
| 1 | 目标解析：常用目标别名和名称歧义处理 | 输入"M31""仙女座星系""Andromeda"均能解析到同一标准目标；歧义时返回候选列表并要求确认 |
| 2 | 可观测性计算：固定恒星及深空目标 | 对指定目标、地点和日期，输出高度角、方位角、airmass、暮光和月光影响；与 Astropy 官方文档示例交叉一致 |
| 3 | 推荐窗口和备选方案 | 带理由的推荐时段、被淘汰时段及违反的约束；至少支持一个备选目标或备选时间 |
| 4 | 科普活动包 | 基于事实卡生成活动流程、讲解词、设备清单和安全提示；所有数值可追溯到事实卡 |
| 5 | 观测日志复盘 | 导入 CSV 观测日志，输出偏差分类、证据引用和参数确实变化的修订计划 |
| 6 | 轻量调用面板 | 输入参数 → 展示中间计算 → 导出活动包 → 导入日志并展示复盘结果 |
| 7 | 3 组完整案例 | 正常观测、不适合观测、复盘修订，每组包含完整运行目录和验证报告 |
| 8 | 自动测试和复现文档 | 一键命令跑通 3 个案例；新环境按 README 可复跑 |

### 明确延期

| 内容 | 延期原因 |
|---|---|
| 行星和太阳系目标星历 | 需要额外的在线服务依赖和缓存策略，首期范围不可控 |
| Stellarium / Aladin Lite 交互星图 | 属于展示层增强，不增加核心 Skill 价值 |
| 校园地平线遮挡模型 | 需要真实测量数据，适合作为特色扩展 |
| 更多天象模板（流星雨、月食等） | 首期聚焦固定目标，避免范围发散 |
| 多语言科普材料 | 首期只支持中文 |

### 明确不做

望远镜硬件控制、实时天气系统、账户和社区、模型微调、多智能体编排、复杂 3D 前端、覆盖所有天体类型。

---

## 3. 四个核心 Skill 的接口草案

### 3.1 target_resolve

**解决的问题：** 将中文名、英文名或别名解析为标准天体目标，返回坐标、类型和数据来源。

**触发条件：** 用户输入观测目标名称后，作为第一个被调用的 Skill。

**输入：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| target_name | string | 是 | 目标名称，支持中文名、英文名、Messier 编号、NGC 编号等 |
| target_type | string | 否 | 可选提示类型：deep_sky、star、planet、asterism 等 |

**输出：**

| 字段 | 类型 | 说明 |
|---|---|---|
| standard_name | string | 标准名称（如 "M31"） |
| aliases | list[string] | 已知别名列表 |
| target_type | string | 目标类型分类 |
| ra_deg | float | 赤经（度，J2000） |
| dec_deg | float | 赤纬（度，J2000） |
| source | string | 坐标数据来源（如 "built_in_catalog_v1"） |
| confidence | float | 匹配置信度（0-1） |
| candidates | list[object] | 歧义时的候选列表（仅歧义时非空） |
| requires_confirmation | bool | 是否需要人工确认 |

**依赖：** 内置目标目录（built_in_catalog_v1）；首期不依赖在线 SIMBAD/Vizier 查询。

**可能失败的情况：**

- 目标名称无法匹配任何记录 → 返回空结果 + 明确错误提示
- 目标名称匹配到多个候选 → 返回候选列表 + requires_confirmation = true
- 输入为空或格式无法解析 → 返回错误信息

**人工确认点：** 名称歧义时必须要求人工选择，不得自动选择低置信度结果。

**可验证的成功标准：**

- "M31""仙女座星系""Andromeda Galaxy""NGC 224" 均解析到 ra_deg ≈ 10.68, dec_deg ≈ 41.27
- "三角座"返回 M33 而非 M31
- 模糊输入如"星云"返回候选列表而非猜测

---

### 3.2 observability_plan

**解决的问题：** 根据目标坐标、地点、日期和设备约束，计算目标的可观测性并生成观测计划。

**触发条件：** target_resolve 成功返回坐标后。

**输入：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| ra_deg | float | 是 | 目标赤经（度，J2000） |
| dec_deg | float | 是 | 目标赤纬（度，J2000） |
| target_name | string | 是 | 目标标准名称 |
| location | object | 是 | 包含 name、latitude、longitude、elevation、timezone |
| date_range | list[string] | 是 | 日期范围 [start, end]，格式 YYYY-MM-DD |
| equipment | string | 否 | 设备类型：naked_eye、binoculars、small_telescope 等 |
| constraints | object | 否 | 可选自定义约束：最小高度角、最大 airmass 等 |

**输出：**

| 字段 | 类型 | 说明 |
|---|---|---|
| is_observable | bool | 在给定条件下是否可观测 |
| visibility_windows | list[object] | 可见时段列表（含开始、结束、峰值高度） |
| recommended_window | object | 推荐观测时段及理由 |
| eliminated_windows | list[object] | 被淘汰时段及淘汰原因（违反的约束） |
| hourly_data | list[object] | 逐小时高度角、方位角、airmass 数据 |
| twilight | object | 日落、民用暮光、航海暮光、天文暮光时间 |
| moon_info | object | 月相、月亮高度、月亮与目标角距离、月光影响评估 |
| alternative_suggestions | list[object] | 备选时段或备选目标建议 |
| risk_flags | list[object] | 风险标记（低高度、强月光、暮光干扰等） |
| observability_csv_path | string | 详细数据 CSV 文件路径 |
| visibility_curve_path | string | 高度-时间曲线图文件路径 |

**依赖：** Astropy（天体坐标框架）、astroplan（观测者、目标、约束计算）、matplotlib（曲线图）。

**可能失败的情况：**

- 地点、时区或日期不完整 → 停止计算，返回缺失项清单
- 目标整晚在地平线以下 → is_observable = false + 原因 + 备选建议
- 月光影响严重 → 在 risk_flags 中标记 + 备选时段建议
- 天文工具计算异常 → 捕获异常 + 记录到 manifest + 返回错误信息

**人工确认点：** 地点解析到多个候选经纬度时；推荐窗口风险等级为高时。

**可验证的成功标准：**

- M31 在 2026-10-17 北京的推荐窗口峰值高度角与 Astropy 计算一致（误差 < 0.5°）
- 日落和天文暮光时间与 USNO 或 Stellarium 参考值一致（误差 < 2 分钟）
- 相同输入多次运行得到一致结果

---

### 3.3 outreach_pack

**解决的问题：** 将确定性计算结果和经过验证的事实卡转化为面向目标受众的科普活动包。

**触发条件：** observability_plan 成功生成计划后。

**输入：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| fact_cards | list[object] | 是 | 经验证的目标事实卡（名称、类型、距离、视星等、角大小等） |
| calculation_results | object | 是 | observability_plan 的输出（推荐窗口、风险等） |
| audience | string | 是 | 目标受众（如"大学新生""小学生""公众"） |
| equipment | string | 是 | 可用设备 |
| activity_goal | string | 否 | 活动目标描述 |

**输出：**

| 字段 | 类型 | 说明 |
|---|---|---|
| activity_schedule | list[object] | 活动流程时间表 |
| talking_points | list[object] | 讲解词要点（按受众调整难度） |
| equipment_checklist | list[object] | 设备清单和准备建议 |
| safety_notes | list[string] | 安全提示（夜间活动、激光笔使用等） |
| manual_check_items | list[string] | 需要人工核对的事项 |
| unconfirmed_items | list[string] | 事实不足、待确认的内容（不自行补写数值） |
| outreach_pack_md_path | string | Markdown 格式活动包文件路径 |

**依赖：** Qwen/百炼（科普表达生成）；事实卡来源为 target_resolve 和 observability_plan 的输出。

**可能失败的情况：**

- 事实卡不完整（缺少视星等或角大小等关键信息）→ 在 unconfirmed_items 中标记，不补写数值
- Qwen 生成了无法追溯到事实卡的数值 → 验证层拦截并标记
- 受众类型不在预设范围内 → 回退到通用模板并提示

**人工确认点：** 科普稿引用尚未验证的事实时；系统准备替换活动主目标时。

**可验证的成功标准：**

- 科普稿中的每个时间、角度和天体事实都能在 fact_cards 或 calculation_results 中找到对应来源
- 事实不足时，输出中有 unconfirmed_items 而非编造数值
- 对同一输入，生成内容的结构一致（可通过 JSON schema 验证）

---

### 3.4 observation_review

**解决的问题：** 对比原始计划与实际观测日志，识别偏差，生成有证据支撑的修订计划。

**触发条件：** 用户导入实际观测日志后。

**输入：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| original_plan | object | 是 | observability_plan 的输出（或 plan.json） |
| observation_log | object | 是 | 实际观测日志（含实际开始/结束时间、目标、设备、云量、结果、备注） |

**观测日志字段：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| actual_start_time | string | 是 | 实际开始时间（ISO 8601） |
| actual_end_time | string | 是 | 实际结束时间（ISO 8601） |
| targets_observed | list[string] | 是 | 实际观测到的目标列表 |
| targets_missed | list[string] | 否 | 未观测到的目标 |
| equipment_used | string | 是 | 实际使用的设备 |
| cloud_cover | string | 否 | 云量描述（clear / partly_cloudy / overcast） |
| seeing_conditions | string | 否 | 视宁度（good / fair / poor） |
| observer_notes | string | 否 | 观测者备注 |
| success_rating | int | 否 | 自评成功度（1-5） |

**输出：**

| 字段 | 类型 | 说明 |
|---|---|---|
| deviation_summary | list[object] | 偏差分类列表（时间偏差、环境影响、设备/操作问题） |
| evidence_citations | list[object] | 每条偏差引用的计划和日志证据 |
| cause_classification | list[object] | 原因分类：evidence_based（有证据）、possible（可能原因）、undetermined（无法判断） |
| improvement_suggestions | list[object] | 改进建议 |
| revised_plan | object | 修订后的下一次计划（参数确实发生变化） |
| revised_plan_diff | object | 原计划与修订计划的字段级差异 |
| review_report_md_path | string | Markdown 格式复盘报告路径 |
| revised_plan_json_path | string | 修订计划 JSON 文件路径 |

**依赖：** observability_plan 的原始输出；用户提供的观测日志。

**可能失败的情况：**

- 日志信息不足以确定偏差原因 → 在 cause_classification 中标记为 undetermined，不猜测
- 日志字段缺失（如缺少实际开始时间）→ 返回缺失字段提示，部分字段标记为不可比较
- 原计划文件不存在或格式不匹配 → 返回明确错误信息

**人工确认点：** 复盘原因只有弱证据时；系统准备替换下一次活动的主目标时。

**可验证的成功标准：**

- 偏差报告引用了具体的计划字段和日志字段
- 修订计划的参数与原计划有可检测的差异（如推荐时间变化、目标优先级变化）
- 至少区分"有证据的原因"和"无法判断"，不把所有偏差归因于单一因素

---

## 4. 统一输入/输出 Schema 草案

### 4.1 统一输入 Schema

```json
{
  "target": "M31",
  "target_type": null,
  "location": "北京_某高校",
  "location_detail": {
    "name": "某高校",
    "city": "北京",
    "latitude": 39.9,
    "longitude": 116.3,
    "elevation_m": 50,
    "timezone": "Asia/Shanghai"
  },
  "date_range": ["2026-10-17", "2026-10-17"],
  "audience": "天文社新成员",
  "equipment": "binoculars",
  "goal": "校园科普观测",
  "constraints": {
    "min_altitude_deg": 30,
    "max_airmass": 2.0,
    "prefer_early_night": true
  }
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| target | string | 是 | 目标名称 |
| target_type | string | 否 | 可选目标类型提示 |
| location | string | 是 | 地点标识（城市_机构） |
| location_detail | object | 否 | 详细经纬度和时区；如不提供，系统尝试从内置地点表解析 |
| date_range | list[string] | 是 | 日期范围 |
| audience | string | 是 | 受众描述 |
| equipment | string | 是 | 设备类型 |
| goal | string | 否 | 活动目标 |
| constraints | object | 否 | 自定义观测约束 |

### 4.2 统一输出目录结构

每次运行生成独立目录：

```text
runs/case_xxx/
  input.json                  # 原始输入（含 Qwen 解析前后的对照）
  resolved_target.json        # 目标解析结果
  calculation_manifest.json   # 计算证据清单（核心证据文件）
  observability.csv           # 逐时间步计算数据
  visibility_curve.png        # 高度-时间曲线图
  plan.json                   # 观测计划（推荐窗口、风险、备选）
  outreach_pack.md            # 科普活动包
  observation_log.csv         # 实际观测日志（复盘案例使用）
  review_report.md            # 偏差复盘报告
  revised_plan.json           # 修订后的下一次计划
  validation_report.md        # 验证报告
  model_call_log.jsonl        # Qwen 调用审计日志
```

### 4.3 calculation_manifest.json 结构

这是本项目最重要的证据文件：

```json
{
  "run_id": "case_01_m31_beijing",
  "timestamp": "2026-07-20T14:30:00+08:00",
  "input": {
    "raw_user_input": "我们天文社想在北京组织一次看仙女座星系的活动",
    "parsed_input": { "...见统一输入 Schema..." }
  },
  "target": {
    "standard_name": "M31",
    "ra_deg": 10.6847,
    "dec_deg": 41.2692,
    "source": "built_in_catalog_v1",
    "confidence": 0.95
  },
  "location": {
    "name": "北京_某高校",
    "latitude": 39.9,
    "longitude": 116.3,
    "timezone": "Asia/Shanghai"
  },
  "tools": {
    "astropy_version": "6.x",
    "astroplan_version": "0.x",
    "python_version": "3.x"
  },
  "model": {
    "provider": "阿里云百炼",
    "model_name": "qwen-xxx",
    "model_version": "xxx"
  },
  "constraints_applied": {
    "min_altitude_deg": 30,
    "max_airmass": 2.0
  },
  "intermediate_files": [
    "resolved_target.json",
    "observability.csv",
    "visibility_curve.png"
  ],
  "manual_overrides": [],
  "validation_status": "passed"
}
```

### 4.4 resolved_target.json 结构

```json
{
  "standard_name": "M31",
  "aliases": ["仙女座星系", "Andromeda Galaxy", "NGC 224"],
  "target_type": "deep_sky",
  "ra_deg": 10.6847,
  "dec_deg": 41.2692,
  "visual_magnitude": 3.44,
  "angular_size_arcmin": [178, 63],
  "constellation": "Andromeda",
  "source": "built_in_catalog_v1",
  "confidence": 0.95,
  "candidates": null,
  "requires_confirmation": false
}
```

### 4.5 model_call_log.jsonl 格式

每行一条 Qwen 调用记录：

```json
{"timestamp": "...", "call_id": "001", "role": "user", "content": "...", "model": "qwen-xxx", "tool_calls": [], "finish_reason": "stop"}
{"timestamp": "...", "call_id": "001", "role": "assistant", "content": "...", "model": "qwen-xxx", "tool_calls": [{"name": "target_resolve", "arguments": {...}}], "finish_reason": "tool_calls"}
{"timestamp": "...", "call_id": "002", "role": "tool", "tool_name": "target_resolve", "input": {...}, "output": {...}, "duration_ms": 120}
```

---

## 5. 首批 3 个案例及验收标准

### 案例 1：正常可观测活动

**场景：** 北京某高校天文社计划于 2026 年 10 月 17 日（周六）晚间组织面向新成员的 M31 仙女座星系观测活动，使用双筒望远镜。

**输入：**

```json
{
  "target": "M31",
  "location": "北京_某高校",
  "date_range": ["2026-10-17", "2026-10-17"],
  "audience": "天文社新成员",
  "equipment": "binoculars",
  "goal": "校园科普观测"
}
```

**预期行为：**

1. target_resolve 将"M31"解析为标准目标，返回坐标和事实卡。
2. observability_plan 计算当日可观测性，给出推荐时段（含峰值高度角）、暮光时间、月光影响、airmass 曲线。
3. outreach_pack 生成面向新成员的活动流程、讲解词和设备清单。
4. 全部中间结果保存到运行目录。
5. validation_report 通过所有校验。

**验收标准：**

| 序号 | 验收项 | 通过条件 |
|---|---|---|
| 1 | 目标解析 | standard_name = M31，ra_deg 和 dec_deg 与 Astropy 内置星表一致 |
| 2 | 暮光时间 | 天文暮光时间与 Stellarium/USNO 参考值差异 < 2 分钟 |
| 3 | 推荐窗口 | 推荐时段内 M31 高度角 ≥ 30° 且 airmass ≤ 2.0 |
| 4 | 月光影响 | moon_info 包含月亮高度和角距离，风险评估有依据 |
| 5 | 科普活动包 | 所有时间和角度数值可追溯到 fact_cards 或 observability 输出 |
| 6 | 运行目录 | 包含全部 12 个预期文件 |
| 7 | 验证报告 | validation_report 状态为 passed |
| 8 | 可复现 | 相同输入重复运行得到一致结果 |

### 案例 2：不适合观测及备选方案

**场景：** 用户想在 2026 年 7 月 25 日（周六）在北京用双筒望远镜观测猎户座大星云 M42。

**输入：**

```json
{
  "target": "M42",
  "location": "北京_某高校",
  "date_range": ["2026-07-25", "2026-07-25"],
  "audience": "天文社新成员",
  "equipment": "binoculars",
  "goal": "校园科普观测"
}
```

**预期行为：**

1. target_resolve 正常解析 M42。
2. observability_plan 发现 M42 在 7 月底与太阳角距离极小，整晚不可见。
3. 系统不返回"不推荐"了事，而是：展示触发的规则（目标在地平线以下 / 与太阳角距离不足）、展示计算依据（日落时间、目标高度逐时数据）、给出替代建议（推荐当季适合的目标如 M13 武仙座球状星团，或建议等到 11 月至次年 2 月观测 M42）。
4. 如果用户接受备选目标，系统对备选目标走完整流程。

**验收标准：**

| 序号 | 验收项 | 通过条件 |
|---|---|---|
| 1 | 不可观测判断 | is_observable = false，reason 明确 |
| 2 | 规则展示 | eliminated_windows 列出具体违反的约束（高度角、与太阳角距离） |
| 3 | 计算依据 | 逐时数据证明目标确实不可见 |
| 4 | 备选建议 | alternative_suggestions 非空，至少包含一个备选目标或备选日期 |
| 5 | 备选可执行 | 对备选目标可走完整流程（可选验收） |
| 6 | 不编造 | 不生成假的"最佳观测时间" |
| 7 | 验证报告 | validation_report 标记为 expected_failure，原因清楚 |

### 案例 3：实际活动复盘

**场景：** 天文社完成了案例 1 中 10 月 17 日的 M31 观测活动，但活动中出现了以下问题：

- 团队迟到 30 分钟，实际开始时间比计划晚
- 活动中途有约 20 分钟的薄云覆盖
- 双筒望远镜支架不稳定，影响了观测效果
- 新成员表示"找到了 M31 但看不太清楚"

**观测日志（observation_log.csv）：**

```csv
actual_start_time,actual_end_time,targets_observed,targets_missed,equipment_used,cloud_cover,seeing_conditions,observer_notes,success_rating
2026-10-17T20:30:00+08:00,2026-10-17T22:30:00+08:00,M31,,binoculars,partly_cloudy,fair,"迟到30分钟；20:50-21:10有薄云；三脚架不稳；新成员反馈M31不如预期清晰",3
```

**预期行为：**

1. observation_review 读取原计划和日志。
2. 识别偏差：时间偏差（迟到 30 分钟，错过了计划中的早期高高度窗口）、环境影响（薄云 20 分钟）、设备问题（支架不稳）。
3. 对每条偏差引用证据（计划中的推荐开始时间 vs 实际开始时间；日志中的云量记录）。
4. 区分有证据的原因（迟到、薄云、设备）和无法判断的因素（新成员期望管理是否充分）。
5. 生成修订计划：推荐开始时间不变但增加"提前 30 分钟到场"步骤；增加设备检查步骤（三脚架稳定性）；增加"预期管理"说明（M31 目视效果的真实描述）。
6. revised_plan 的参数与原计划有可检测的差异。

**验收标准：**

| 序号 | 验收项 | 通过条件 |
|---|---|---|
| 1 | 偏差识别 | 至少识别出 3 类偏差（时间、环境、设备） |
| 2 | 证据引用 | 每条偏差引用了具体的计划字段和日志字段 |
| 3 | 原因分类 | 区分 evidence_based 和 undetermined |
| 4 | 修订差异 | revised_plan_diff 显示至少 2 个字段发生变化 |
| 5 | 建议具体 | 改进建议不是"下次注意"，而是具体操作（如"增加提前到场步骤"） |
| 6 | 不猜测 | 不对日志中未记录的因素做强归因 |
| 7 | 运行目录 | 包含 review_report.md 和 revised_plan.json |

---

## 6. 技术依赖选择及其理由

| 依赖 | 版本要求 | 用途 | 选择理由 |
|---|---|---|---|
| Python | ≥ 3.10 | 运行时 | Astropy/astroplan 生态标准；团队熟悉度最高（待核实） |
| Astropy | ≥ 6.0 | 天体坐标、时间框架、单位系统 | IAU 标准实现，社区活跃，文档完善，离线可用 |
| astroplan | ≥ 0.9 | 观测约束计算、可观测性分析 | 基于 Astropy 的观测计划工具，API 设计贴合本项目需求 |
| matplotlib | ≥ 3.7 | 高度-时间曲线、可视化 | Python 标准可视化库，生成 PNG 文件 |
| pandas | ≥ 2.0 | CSV 数据处理（observability.csv、observation_log.csv） | 数据处理标准库 |
| pydantic | ≥ 2.0 | Schema 定义和输入验证 | 类型安全、自动生成 JSON Schema、清晰错误信息 |
| dashscope | 最新 | 阿里云百炼 API 调用 | 官方 SDK，直接调用 Qwen 模型 |
| Qwen 模型 | 待核实（建议使用 qwen-max 或 qwen-plus） | 自然语言解析、工具编排、科普表达 | 赛题要求使用阿里云 Qwen 系列 |
| Streamlit 或 FastAPI | 待定 | 轻量演示界面 | Streamlit 开发快、适合演示；FastAPI 更灵活（待团队确认偏好） |

**不选择的技术：**

| 技术 | 不选择的原因 |
|---|---|
| Stellarium/KStars 脚本 | 增加外部依赖，首期核心计算用 Astropy 可离线复现 |
| SIMBAD/Vizier 在线查询 | 在线服务不稳定会成为演示单点故障；仅作可选交叉校验 |
| JPL Horizons | 首期不含太阳系目标，暂不需要 |
| LangChain / LlamaIndex | 框架过重；百炼 SDK + 自定义 tool calling 已足够 |

---

## 7. Qwen 与确定性天文计算的职责分工

### 职责分工表

| 任务 | 负责方 | 边界 |
|---|---|---|
| 理解自然语言输入 | Qwen | 将"我们想看仙女座星系"解析为结构化 JSON |
| 目标名称标准化 | Qwen + 内置目录 | Qwen 调用 target_resolve Skill；Skill 查询内置目录返回结果 |
| 天文数值计算 | Astropy/astroplan | 高度角、方位角、airmass、暮光、月光——全部确定性计算 |
| 推荐窗口决策 | 规则引擎 + 工具输出 | 基于约束规则筛选工具输出，不经 Qwen |
| 科普表达生成 | Qwen | 仅基于事实卡生成讲解词，不得补充工具未提供的数值 |
| 偏差归因 | Qwen + 规则 | Qwen 辅助分类，但必须引用计划和日志中的具体字段 |
| 修订计划生成 | Qwen + 模板 | Qwen 提出修订建议，但参数变化必须可对比和可验证 |
| 数值编造防护 | 验证层 | 拦截 Qwen 输出中无法追溯到工具结果的数值 |

### 幻觉防护机制

Qwen 在以下情况下被要求拒绝或标记，而不是编造数值：

1. 被要求"不调用工具直接给出精确角度"时 → 回复"需要调用计算工具获取准确结果"
2. 事实卡中缺少某项数据时 → 在输出中标记为"待确认"，不自行填充
3. 目标名称有歧义时 → 返回候选列表，不自动选择
4. 观测日志信息不足以归因时 → 标记为"无法判断"，不做强归因

### 审计机制

每次 Qwen 调用记录到 model_call_log.jsonl，包含：时间戳、调用 ID、角色、输入内容、工具调用参数、工具返回结果、模型输出、耗时。

---

## 8. 数据来源、版本和可复现方案

### 数据来源

| 数据类型 | 来源 | 说明 |
|---|---|---|
| 目标坐标和基本信息 | built_in_catalog_v1 | 项目内置目录，包含 Messier 天体（110 个）和常用亮星（约 30-50 个），数据源自公开天文星表 |
| 天文计算 | Astropy/astroplan | IAU 标准算法，离线可用，结果可复现 |
| 交叉校验（可选） | SIMBAD、Stellarium | 仅作为验证参考，不作为核心依赖 |
| 地点信息 | 内置地点表 + 用户输入 | 首期内置 5-10 个常用城市坐标；用户可提供精确经纬度 |

### 版本管理

- calculation_manifest.json 记录每次运行使用的 Astropy 版本、astroplan 版本、Python 版本和 Qwen 模型版本。
- 内置目录 built_in_catalog_v1 有固定版本号，更新时版本号递增。
- requirements.txt 锁定依赖版本。

### 可复现方案

1. **离线可复现：** 核心天文计算全部基于 Astropy/astroplan，不依赖在线服务。相同 Python 版本 + 相同输入 → 相同计算结果。
2. **模型层隔离：** API Key 仅影响 Qwen 的表达层（科普文案的具体措辞），不影响核心天文数值和推荐窗口。
3. **一键复跑：** 提供命令 `python scripts/run_case.py examples/case_01_m31_beijing.json`，自动生成完整运行目录。
4. **复现文档：** README 中包含安装步骤、依赖安装、3 个案例运行命令和预期输出校验方法。

---

## 9. 失败处理和人工确认设计

### 失败处理总则

系统在任何失败点都不返回模糊报错（如"出错了"），而是返回：

1. 失败的具体原因
2. 缺失的信息或数据
3. 建议的下一步操作

### 按 Skill 的失败处理

**target_resolve：**

| 失败场景 | 处理方式 |
|---|---|
| 名称无匹配 | 返回"未找到匹配目标"，建议检查名称拼写或提供更多描述 |
| 名称歧义 | 返回候选列表，设置 requires_confirmation = true，等待人工选择 |
| 输入为空 | 返回"请提供目标名称"，不猜测 |

**observability_plan：**

| 失败场景 | 处理方式 |
|---|---|
| 地点缺失 | 返回"缺少地点信息"，列出所需字段 |
| 日期缺失 | 返回"缺少日期范围"，列出所需字段 |
| 时区不明确 | 返回候选时区列表，要求确认 |
| 目标整晚不可见 | is_observable = false，附带逐时高度数据证明和替代建议 |
| 工具计算异常 | 捕获异常，记录到 manifest，返回错误信息 |

**outreach_pack：**

| 失败场景 | 处理方式 |
|---|---|
| 事实卡不完整 | 在 unconfirmed_items 中标记缺失项，不补写数值 |
| Qwen 生成无法追溯的数值 | 验证层拦截，标记为需人工确认 |
| 受众类型未知 | 回退到通用模板，提示用户确认 |

**observation_review：**

| 失败场景 | 处理方式 |
|---|---|
| 日志字段缺失 | 返回缺失字段清单，标记不可比较项 |
| 原计划不存在 | 返回"缺少原始计划文件"，无法进行复盘 |
| 信息不足以归因 | cause_classification 标记为 undetermined |

### 人工确认点汇总

| 确认点 | 触发条件 | 确认内容 |
|---|---|---|
| 目标歧义 | target_resolve 返回多个候选 | 选择正确的目标 |
| 地点歧义 | 地点名称匹配到多个坐标 | 选择正确的地点 |
| 高风险推荐 | 推荐窗口存在高风险标记 | 确认是否接受风险继续 |
| 科普稿待验证事实 | outreach_pack 中有 unconfirmed_items | 确认或删除相关内容 |
| 复盘弱证据 | 偏差归因只有 possible 级别证据 | 确认是否采纳建议 |
| 替换主目标 | 系统准备替换活动主目标 | 确认替换或保留原目标 |

---

## 10. 按优先级排列的首周任务清单

首周时间为 7 月 18 日至 7 月 25 日。以下任务按优先级排列：

| 优先级 | 任务 | 负责人建议 | 输入 | 输出 |
|---|---|---|---|---|
| P0-1 | 冻结 4 个 Skill 的输入输出 Schema | 全组 | 本启动报告 | skills.yaml + 各 Skill 的 pydantic 模型 |
| P0-2 | 冻结 3 个案例的具体输入 JSON | A | 本启动报告 | examples/ 下 3 个 JSON 文件 |
| P0-3 | 冻结验证规则和阈值 | A + B | Astropy 参考数据 | constraints_config.yaml |
| P0-4 | 建立内置目标目录 v1 | C | 公开 Messier 星表数据 | data/built_in_catalog_v1.json（≥ 110 个 Messier 天体 + 30 个常用亮星） |
| P0-5 | 建立内置地点表 v1 | C | 常用城市坐标 | data/locations_v1.json（5-10 个城市） |
| P0-6 | 搭建项目骨架和统一输出目录 | D | 项目结构设计 | 目录结构 + runner.py 骨架 + output_dir 管理 |
| P0-7 | 完成 target_resolve 最小实现 | C | 内置目录 v1 | 能解析 M31/M42/M13 并处理歧义 |
| P0-8 | 完成 observability_plan 最小实现 | B | Astropy/astroplan | 对 M31+北京+10-17 输出高度角和推荐窗口 |
| P0-9 | 确认百炼/Qwen 调用方式和模型版本 | D | 阿里云百炼账号 | 能成功调用 Qwen 并保存调用日志 |
| P0-10 | 建立 Git 仓库和协作规范 | D + E | 分工表 | GitHub/Gitee 仓库 + 分支策略 + README |

---

## 11. 每项首周任务的完成定义和验证命令

### P0-1：冻结 Schema

**完成定义：** skills.yaml 和各 Skill 的 pydantic 模型已提交到 main 分支；3 个案例的输入 JSON 能通过 Schema 验证。

**验证命令：**

```bash
python -c "from starplan_skills.schemas import InputSchema; InputSchema.model_validate_json(open('examples/case_01_m31_beijing.json').read())"
```

### P0-2：冻结 3 个案例输入

**完成定义：** examples/ 下有 3 个 JSON 文件，字段完整且通过 Schema 验证。

**验证命令：**

```bash
python scripts/validate_examples.py
# 预期：3 个案例全部 PASS
```

### P0-3：冻结验证规则

**完成定义：** constraints_config.yaml 已提交，至少覆盖：最小高度角、最大 airmass、暮光条件、月光影响阈值、设备匹配规则。

**验证命令：**

```bash
python -c "from starplan_skills.config import load_constraints; c = load_constraints(); assert c.min_altitude_deg == 30; print('OK')"
```

### P0-4：内置目标目录 v1

**完成定义：** data/built_in_catalog_v1.json 包含 ≥ 140 个目标，每个目标有 standard_name、ra_deg、dec_deg、target_type、aliases。

**验证命令：**

```bash
python -c "import json; d = json.load(open('data/built_in_catalog_v1.json')); assert len(d) >= 140; assert all('ra_deg' in t for t in d); print(f'{len(d)} targets OK')"
```

### P0-5：内置地点表 v1

**完成定义：** data/locations_v1.json 包含 ≥ 5 个城市，每个有 name、latitude、longitude、timezone。

**验证命令：**

```bash
python -c "import json; d = json.load(open('data/locations_v1.json')); assert len(d) >= 5; assert all('latitude' in loc for loc in d); print(f'{len(d)} locations OK')"
```

### P0-6：项目骨架

**完成定义：** 目录结构符合 transfer-log 中的推荐结构；runner.py 可以 import 且无语法错误。

**验证命令：**

```bash
python -c "from starplan_skills.runner import run_starplan; print('Import OK')"
ls starplan_skills/
# 预期：__init__.py, runner.py, target_resolve.py, observability_plan.py, outreach_pack.py, observation_review.py, validation.py
```

### P0-7：target_resolve 最小实现

**完成定义：** 输入"M31"返回正确的坐标；输入"星云"返回候选列表。

**验证命令：**

```bash
python -c "
from starplan_skills.target_resolve import resolve_target
r = resolve_target('M31')
assert r['standard_name'] == 'M31'
assert abs(r['ra_deg'] - 10.68) < 0.1
print(f'M31: ra={r[\"ra_deg\"]:.4f}, dec={r[\"dec_deg\"]:.4f}')

r2 = resolve_target('星云')
assert r2['requires_confirmation'] == True
print(f'歧义处理: {len(r2[\"candidates\"])} candidates')
"
```

### P0-8：observability_plan 最小实现

**完成定义：** 对 M31 + 北京 + 2026-10-17，输出逐时高度角和推荐窗口；推荐窗口内的峰值高度角与 Astropy 直接计算一致（误差 < 0.5°）。

**验证命令：**

```bash
python -c "
from starplan_skills.observability_plan import compute_observability
r = compute_observability(ra_deg=10.6847, dec_deg=41.2692, target_name='M31', location={'latitude': 39.9, 'longitude': 116.3, 'elevation_m': 50, 'timezone': 'Asia/Shanghai'}, date_range=['2026-10-17', '2026-10-17'])
assert r['is_observable'] == True
print(f'Recommended: {r[\"recommended_window\"]}')
print(f'Peak altitude: {r[\"recommended_window\"][\"peak_altitude_deg\"]:.1f} deg')
"
```

### P0-9：百炼/Qwen 调用确认

**完成定义：** 能成功调用一次 Qwen 模型并保存调用日志到 model_call_log.jsonl；日志中包含模型名称和版本。

**验证命令：**

```bash
python -c "
from starplan_skills.qwen_client import call_qwen
r = call_qwen('你好，请回复OK')
assert 'OK' in r['content']
print(f'Model: {r[\"model\"]}, Response: {r[\"content\"][:50]}')
"
```

### P0-10：Git 仓库和协作规范

**完成定义：** 仓库已建立；README 包含项目简介、安装步骤和运行命令；.env.example 存在；分支策略文档已提交。

**验证命令：**

```bash
git clone <repo_url>
cd StarPlan
cat README.md | head -20
ls .env.example
```

---

## 12. 风险清单

| 风险 | 影响 | 概率 | 规避方案 | 触发后降级方案 |
|---|---|---|---|---|
| 天文计算结果与权威工具有显著差异 | 科学价值受损，评委质疑 | 中 | 首周用 Astropy 官方示例交叉校验；冻结阈值前必须通过 3 个案例验证 | 缩小目标目录和地点范围，只演示已验证的案例 |
| Qwen 生成幻觉数值且未被拦截 | 技术可靠性被质疑 | 高 | 实现验证层：检查 Qwen 输出中的数值是否在 fact_cards 或工具输出中；准备幻觉防护测试集 | 在演示中增加人工校验步骤；展示验证层的拦截能力作为技术亮点 |
| 百炼 API 不稳定或模型版本变更 | 演示时无法调用 | 中 | 保存模型调用日志和版本信息；核心计算不依赖 API；准备离线模式 | 演示时切换到预计算的固定案例结果；说明 API 恢复后可自动运行 |
| 团队 5 人协作无法集成 | 最终无法合并代码 | 中 | 首周冻结 Schema；每周集成测试；main 分支必须能跑通 3 个案例 | 减少并行开发范围，先由 1-2 人跑通主链路再分工 |
| 6.5 周时间不够 | 部分功能未完成 | 高 | 严格按优先级执行；先完成核心闭环再做展示层和增强项 | 砍掉 outreach_pack 或 observation_review，只保留 target_resolve + observability_plan 的完整演示 |
| 被认为"只是套壳 Astropy" | 竞争力不足 | 高 | 强调闭环（计划→执行→复盘）、证据链（manifest）、Qwen 分工和幻觉防护；准备对照实验 | 增加一个真实的校园实测案例作为应用证据 |
| 科普活动包质量低或像模板 | 应用潜力被质疑 | 中 | outreach_pack 必须基于事实卡动态生成；准备不同受众的对比示例 | 降低科普包的自动化程度，增加人工编辑环节 |
| 复盘修订计划参数没有真实变化 | 闭环不被认可 | 中 | revised_plan_diff 自动检测参数变化；设计 3 类偏差确保触发不同修订 | 手动构造一份"理想修订"作为对比，说明自动化修订覆盖了哪些项 |
| 评委不熟悉天文背景 | 无法理解项目价值 | 中 | PPT 和演示用痛点叙事开头；提供"传统流程 vs StarPlan"对照表 | 简化技术细节，聚焦"计划—执行—复盘"闭环的通用价值 |
| 演示视频制作时间不足 | 附加材料缺失 | 中 | 第 5 周开始准备视频脚本；用录屏 + 旁白方式降低制作成本 | 提交完整文字材料代替视频，或提交精简版视频 |

---

## 13. 当前计划中最可能失控的部分

### 最可能失控的部分：Qwen 工具调用与幻觉防护

理由：

1. Qwen 的 tool calling 能力在百炼平台上的具体表现（如函数调用格式、多轮对话状态保持、错误恢复）尚未实际验证。如果百炼的工具调用机制与预期不符，可能影响整个编排层。
2. 让 Qwen "只基于事实卡生成内容、不编造数值"这一约束，需要在提示词工程和验证层两方面同时投入。提示词效果难以提前预测，验证层的规则需要随着实际输出不断调整。
3. 如果 Qwen 在多步编排中出现状态丢失（如忘记前一步的工具返回结果），可能导致重复调用或输出不一致。

**建议的规避措施：**

- 首周 P0-9 任务中，不仅验证"能调用"，还要验证"工具调用后 Qwen 能正确使用返回值"。
- 准备一组幻觉诱导测试（"不要调用工具直接回答""即使没有数据也给我一个精确角度"），在首周就测试 Qwen 的边界。
- 如果百炼的 tool calling 不够稳定，备选方案是用 structured output（JSON mode）+ 手动解析替代原生 function calling。

### 第二可能失控的部分：时间压力下的范围控制

理由：

6.5 周对 5 人团队来说，如果首周 Schema 冻结延迟，后续并行开发会受影响。最大的风险不是"做不完"，而是"每个模块都做了 80% 但没有一个完整闭环"。

**建议的规避措施：**

- 第 2 周末必须有一个案例从头到尾跑通（即使 outreach_pack 还是占位符）。
- 如果第 4 周末 3 个案例不能全部跑通，立即砍掉 outreach_pack 和 observation_review 的复杂实现，用简化版替代。

---

## 14. 需要人类确认的阻塞问题

以下 5 个问题如果无法确认，会阻塞首周后续任务的推进：

**问题 1：首批支持的目标目录范围**

建议：Messier 全部 110 个天体 + 约 30-50 个常用亮星（如天狼星、织女星、北极星等），总计 ≥ 140 个目标。

需要确认：这个范围是否合适？是否有团队特别想加入或排除的目标？

**问题 2：3 个案例的具体日期和地点**

建议：

- 案例 1：M31 + 北京（39.9°N, 116.3°E）+ 2026-10-17
- 案例 2：M42 + 北京 + 2026-07-25（不适合观测）
- 案例 3：M31 + 北京 + 2026-10-17（使用案例 1 的计划 + 模拟观测日志）

需要确认：日期选择是否天文上合理（需交叉验证月相和太阳位置）？地点是否使用虚拟的"北京某高校"还是某个真实校园？

**问题 3：百炼账号和可用模型**

需要确认：团队是否已有阿里云百炼账号？可用的 Qwen 模型版本是什么（qwen-max、qwen-plus、qwen-turbo）？是否有 API 调用额度限制？

**问题 4：演示入口技术选择**

建议：Streamlit（开发速度快、适合演示）。备选：FastAPI + 简单 HTML 前端。

需要确认：团队对哪种技术更熟悉？是否需要前后端分离？

**问题 5：比赛提交平台和截止日期格式**

需要确认：比赛提交入口在哪里？除了 2026-09-01 之外，是否有中期检查或预提交节点？PPT/PDF 和视频是否有具体的格式和大小要求？

---

## Go / No-Go 判断

### 结论：Go —— 可以开始搭建最小骨架

**依据：**

1. 项目范围和边界已经清楚定义，MVP 内容、延期内容和不做内容已明确。
2. 4 个 Skill 的接口已有草案，输入输出字段已定义。
3. 技术栈选择清晰且依赖成熟（Python + Astropy/astroplan 离线可用）。
4. 3 个案例的场景和验收标准已设计。
5. 核心闭环（目标→计算→计划→日志→复盘）的逻辑完整。
6. 6.5 周时间对 MVP 范围可行，前提是严格按优先级执行。

**唯一关键阻塞项：**

百炼账号和 Qwen 模型可用性（问题 3）。如果没有百炼账号或 API 额度不足，Qwen 编排和科普包生成无法实现。但这一阻塞不影响首周的 Schema 冻结、目标目录建立和本地计算验证（P0-1 至 P0-8），建议团队在首周并行解决。

**建议立即执行：**

1. 团队审阅本启动报告，确认或修改 14 项内容。
2. 解决阻塞问题（特别是百炼账号）。
3. 确认后，按 P0-1 至 P0-10 的优先级开始首周任务。

---

*报告结束。在团队确认前，不创建复杂前端，不接入多个外部服务，不开始模型微调，不把未验证的天文数值写入最终材料。*
