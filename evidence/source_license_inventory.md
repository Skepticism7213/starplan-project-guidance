# 来源与许可证清单

更新时间：2026-08-05　|　适用范围：`StarPlan/` 与 `evidence/` 提交包

## 一、软件依赖

| 依赖 | 用途 | 许可证 | 版本要求 |
|---|---|---|---|
| Astropy | 天体坐标框架、时间系统、高度/方位/airmass 计算 | BSD 3-Clause | >=6.0（本机 8.0.1） |
| astroplan | 观测约束与窗口计算 | BSD 3-Clause | >=0.9（本机 0.10.1） |
| NumPy | 数值计算 | BSD 3-Clause | >=1.24 |
| matplotlib | 高度-时间曲线图 | PSF（宽松许可） | >=3.7 |
| pydantic | 输入输出 Schema 验证 | MIT | >=2.0 |
| PyYAML | 配置文件解析 | MIT | >=6.0 |
| dashscope | 阿里云百炼 Qwen API | Apache-2.0 | >=1.20.0 |
| python-dotenv | .env 配置加载 | BSD 3-Clause | >=1.0 |
| tzdata | Windows 时区数据库 | Apache-2.0 | >=2024.1 |
| pytest | 测试 | MIT | >=7.0（仅开发） |

说明：本项目**不修改上述上游源码**，只通过其公开 API 组装 AI Ready 工作流；
确定性天文计算由 Astropy/astroplan 完成，模型不参与数值生成。

## 二、数据来源

| 数据 | 来源 | 许可证/授权说明 | 复现方式 |
|---|---|---|---|
| 内置目标目录 `built_in_catalog_v1.json`（110 Messier + 40 亮星） | SIMBAD（CDS，斯特拉斯堡）TAP 查询；Yale Bright Star Catalog；Messier 目录文献值 | SIMBAD 数据可自由使用并建议致谢 CDS；Yale BSC 为公共领域数据 | `StarPlan/scripts/simbad_tap_query.py`，查询日期 2026-07-18 |
| 星座归属 | IAU 星座边界（Roman 1987） | 公共事实数据 | 由 J2000 坐标判定 |
| 中文别名 | 中文天文名词审定、国家天文台译名 | 公共知识 | 人工整理并记录于 `catalog_provenance.json` |
| 内置地点表 `locations_v1.json`（8 城市） | 团队录入，经纬度经地图与权威时区资料核对 | 自建数据 | 文件内标注 |
| 约束阈值 `constraints_config.yaml` | 团队按固定案例与参考工具校准 | 自建规则 | 文件内标注规则版本 |

原始 SIMBAD 查询结果未随仓库提交（数据本身可复现）；`catalog_provenance.json`
记录每个字段的来源、精度与校验历史。

## 三、改造内容说明（开源/已有工具 → AI Ready）

1. 把 Astropy/astroplan 的底层计算封装为 4 个 Skills（目标解析、可观测性计划、
   科普活动包、观测复盘），提供统一 JSON Schema 输入输出。
2. 增加 Claim Registry 证据链：所有用户可见事实句映射到确定性计算结果，
   模型只能选择允许的句子变体，不能生成自由数值文本。
3. 增加运行审计：输入、中间结果、模型调用日志、验证报告、RunOutcome 落盘，
   保证可复现。
4. 增加 QoderWork/Qwen 智能体接入层（MCP stdio 适配器），宿主模型负责
   自然语言理解与转达，工具层固定离线确定性计算。

## 四、AI 调用方式

- 基座模型：Qwen 系列（QoderWork 应用内置）。
- 调用方式：QoderWork 应用内挂载 Skill（`StarPlan/qoderwork-skill/SKILL.md`）
  并通过 MCP 调用 `StarPlan/scripts/starplan_mcp_server.py` 的 7 个工具。
- 凭证：应用内录屏记录 Skill 触发链与工具调用链；不提交 API Key。
- 模型边界：数值与事实句由确定性工具与模板渲染，模型只做编排和原文转达。

## 五、需随最终材料一并声明的致谢

- 天文数据：CDS/SIMBAD（斯特拉斯堡）。
- 软件：Astropy 与 astroplan 开发团队。
- 阿里云：百炼平台与 Qwen 系列模型。
