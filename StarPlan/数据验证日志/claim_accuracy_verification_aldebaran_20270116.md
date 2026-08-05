# Claim 准确性核验日志：毕宿五 / 济南四门塔 / 2027-01-16

- **核验对象**: runs/毕宿五_济南-四门塔_20270116_095007（Qwen 在线模式，qwen3.7-plus）
- **核验方式**: 独立 Astropy 8.0.1 重算（不经过 starplan_skills 代码）+ 权威星表值比对
- **核验时间**: 2026-08-05
- **Claim 总数**: 49（claims.json，registry_hash=3c98027f6e93065d）
- **结论**: **全部准确，无编造**。数值型 Claim 与独立重算一致（差异均在采样误差内），事实型 Claim 与 SIMBAD/Hipparcos 权威值一致。

## 一、数值型 Claim 交叉验证

| Claim | 值 | 独立重算 | 判定 |
|---|---|---|---|
| obs.twilight_end（暮光结束） | 18:50 | 18:50（太阳高度≤-18°内插） | ✅ 完全一致 |
| obs.peak_altitude | 70.08° | 70.075°（21:06 CST） | ✅ 差 0.005° |
| obs.peak_airmass | 1.064 | sec(z)=1.0637 | ✅ 差 0.0003 |
| obs.recommended_window | 19:05~01:20 | 暗夜且高度≥30°精确区间 18:51~01:23 | ✅ 15分钟网格版，方向保守（不晚开始、不提前结束） |
| moon.phase（照亮比例） | 0.581 | 整夜区间 0.557~0.624，午夜 0.588 | ✅ 在合理区间内 |
| moon.separation（最小月距） | 32.46° | 1分钟采样最小 32.25°（黎明前） | ✅ 差0.21°=15分钟网格采样效应；与自身csv末行(05:50:32, 32.46°)完全自洽 |
| Data points（validation_report） | 44 | observability.csv 恰44数据行 | ✅ |
| 活动时段（setup 18:50:32/观测90分钟/收尾20:50:32） | 90+15+15 政策 | 算术自洽 | ✅ |

窗口细节说明：网格起点 19:05:32.8125 = 暮光结束 18:50:32.8125 + 15min；窗口终点 01:20:32.8125 为最后一个高度≥30°的网格点（精确跌破时刻 01:23）。

## 二、事实型 Claim 与权威数据比对

| Claim | 值 | 权威参考 | 判定 |
|---|---|---|---|
| target.coordinates | RA=68.9802° (=04h35m55.2s) | SIMBAD/Hipparcos α Tau: 04h35m55.239s | ✅ |
| target.coordinates | Dec=16.5093° (=+16°30'33.5") | SIMBAD: +16°30'33.49" | ✅ |
| target.visual_magnitude | 0.85 | 毕宿五为慢不规则变星，V≈0.85~0.86 | ✅ |
| target.constellation | Taurus | α Tau 属金牛座 | ✅ |
| target.type | star | 恒星（K5III） | ✅ |
| target.angular_size | unconfirmed | 亮星无角直径数据，正确标记未确认 | ✅ fail-closed 符合预期 |
| 数据来源声明 | built_in_catalog_v1 | catalog_provenance.json 声明 SIMBAD J2000 ICRS | ✅ 一致 |

## 三、派生型 Claim 规则审查

- **moon.impact = 月光无影响**: 依据 constraints_config.yaml 的 `bright_star_magnitude_threshold: 2.5` 豁免规则（视星等亮于2.5的点源目标不受月光判定约束），毕宿五 0.85 等，豁免成立，与文档化规则一致。
  - 备注：若不适用豁免，照亮比例0.58+月距32°按 impact_levels 表应判 moderate。对0.85等亮星而言"月光不影响可见性"在天文实践上成立，规则本身合理。
- **derived.visibility.naked_eye = 肉眼可见（理想暗天条件下）**: 0.85等远亮于肉眼极限6等，派生正确。
- **derived.equipment.match = 双筒适合**: 亮星目标，设备匹配派生合理。

## 四、备注（INFO，非错误）

1. moon.separation 为15分钟网格最小值（32.46°），真实连续最小约32.25°，属采样效应，非编造。
2. 面向公众的"月光无影响"表述基于亮星豁免规则；若未来目标是暗弱深空天体，同晚条件将判 moderate，需注意表述差异。
3. 表达层问题（与Claim准确性无关，另行记录）：Qwen版讲解要点未选用视星等/峰值高度/暮光/月距等数值Claim；标题用标准名Aldebaran而非中文输入名；星座名Taurus未本地化。
