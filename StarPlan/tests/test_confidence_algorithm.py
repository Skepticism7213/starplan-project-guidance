"""
置信度/候选列表/人工确认算法 合理性检测脚本
15批 × 10条 = 150条测试用例

检测维度：
  批次 1-3:  精确匹配（标准名/别名/NGC编号）
  批次 4-6:  包含/前缀匹配（短前缀、中文部分名）
  批次 7-9:  边界条件（类型过滤、空查询、极短查询）
  批次 10-12: 歧义场景（多高分候选）
  批次 13-15: 无匹配/异常输入（容错性）
"""

import json
import sys
import io
import traceback
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.target_resolve import resolve_target, _match_catalog_entry, _load_catalog


# ═══════════════════════════════════════════════════════════
# 测试用例定义
# ═══════════════════════════════════════════════════════════

TEST_CASES = [
    # ─── 批次 1: 精确匹配 - 标准名 ───
    {"batch": 1, "id": "B01-01", "query": "M31", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "精确匹配标准名M31"},
    {"batch": 1, "id": "B01-02", "query": "M42", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M42"},
     "desc": "精确匹配标准名M42"},
    {"batch": 1, "id": "B01-03", "query": "Sirius", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "Sirius"},
     "desc": "精确匹配标准名Sirius"},
    {"batch": 1, "id": "B01-04", "query": "Vega", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "Vega"},
     "desc": "精确匹配标准名Vega"},
    {"batch": 1, "id": "B01-05", "query": "m31", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "大小写不敏感匹配m31→M31"},
    {"batch": 1, "id": "B01-06", "query": "M1", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M1"},
     "desc": "精确匹配M1（同时是M10-M19,M100-M110的前缀）"},
    {"batch": 1, "id": "B01-07", "query": "Polaris", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "Polaris"},
     "desc": "精确匹配标准名Polaris"},
    {"batch": 1, "id": "B01-08", "query": "M100", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M100"},
     "desc": "精确匹配M100（三位数编号）"},
    {"batch": 1, "id": "B01-09", "query": "Betelgeuse", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "Betelgeuse"},
     "desc": "精确匹配标准名Betelgeuse"},
    {"batch": 1, "id": "B01-10", "query": "M110", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M110"},
     "desc": "精确匹配M110（最大编号）"},

    # ─── 批次 2: 精确匹配 - 别名 ───
    {"batch": 2, "id": "B02-01", "query": "仙女座星系", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "精确匹配中文别名→M31"},
    {"batch": 2, "id": "B02-02", "query": "猎户座大星云", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M42"},
     "desc": "精确匹配中文别名→M42"},
    {"batch": 2, "id": "B02-03", "query": "天狼星", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Sirius"},
     "desc": "精确匹配中文别名→Sirius"},
    {"batch": 2, "id": "B02-04", "query": "织女星", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Vega"},
     "desc": "精确匹配中文别名→Vega"},
    {"batch": 2, "id": "B02-05", "query": "Andromeda Galaxy", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "精确匹配英文别名→M31"},
    {"batch": 2, "id": "B02-06", "query": "Ring Nebula", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M57"},
     "desc": "精确匹配英文别名→M57"},
    {"batch": 2, "id": "B02-07", "query": "北极星", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Polaris"},
     "desc": "精确匹配中文别名→Polaris"},
    {"batch": 2, "id": "B02-08", "query": "昴星团", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M45"},
     "desc": "精确匹配中文别名→M45"},
    {"batch": 2, "id": "B02-09", "query": "参宿四", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Betelgeuse"},
     "desc": "精确匹配中文别名→Betelgeuse"},
    {"batch": 2, "id": "B02-10", "query": "牛郎星", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Altair"},
     "desc": "精确匹配中文别名→Altair"},

    # ─── 批次 3: 精确匹配 - NGC编号 ───
    {"batch": 3, "id": "B03-01", "query": "NGC 224", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "NGC编号匹配→M31"},
    {"batch": 3, "id": "B03-02", "query": "NGC 1976", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M42"},
     "desc": "NGC编号匹配→M42"},
    {"batch": 3, "id": "B03-03", "query": "NGC 6720", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M57"},
     "desc": "NGC编号匹配→M57"},
    {"batch": 3, "id": "B03-04", "query": "NGC 5194", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M51"},
     "desc": "NGC编号匹配→M51"},
    {"batch": 3, "id": "B03-05", "query": "NGC 4486", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M87"},
     "desc": "NGC编号匹配→M87"},
    {"batch": 3, "id": "B03-06", "query": "ngc 224", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "NGC编号小写+空格→M31"},
    {"batch": 3, "id": "B03-07", "query": "NGC 1952", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M1"},
     "desc": "NGC编号匹配→M1"},
    {"batch": 3, "id": "B03-08", "query": "NGC 3031", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M81"},
     "desc": "NGC编号匹配→M81"},
    {"batch": 3, "id": "B03-09", "query": "NGC 7078", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M15"},
     "desc": "NGC编号匹配→M15"},
    {"batch": 3, "id": "B03-10", "query": "NGC 2632", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M44"},
     "desc": "NGC编号匹配→M44"},

    # ─── 批次 4: 包含匹配 - 中文部分名 ───
    {"batch": 4, "id": "B04-01", "query": "仙女座", "type_hint": None,
     "expect": {"confidence_gte": 0.80, "requires_confirmation": True, "candidates_gte": 2},
     "desc": "部分名'仙女座'应匹配M31/M32/M110等多个目标"},
    {"batch": 4, "id": "B04-02", "query": "球状星团", "type_hint": None,
     "expect": {"confidence_gte": 0.80, "requires_confirmation": True, "candidates_gte": 5},
     "desc": "泛称'球状星团'应命中大量目标（检测候选列表是否过长）"},
    {"batch": 4, "id": "B04-03", "query": "猎户座", "type_hint": None,
     "expect": {"confidence_gte": 0.80, "requires_confirmation": True, "candidates_gte": 2},
     "desc": "部分名'猎户座'应匹配M42/M43/M78及猎户座恒星"},
    {"batch": 4, "id": "B04-04", "query": "三角座星系", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M33"},
     "desc": "精确匹配M33别名'三角座星系'"},
    {"batch": 4, "id": "B04-05", "query": "三角座", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M33"},
     "desc": "精确匹配M33别名'三角座'（M33的aliases里包含'三角座'）"},
    {"batch": 4, "id": "B04-06", "query": "星云", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "极泛称'星云'应命中大量目标"},
    {"batch": 4, "id": "B04-07", "query": "人马座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "部分名'人马座'应命中多个人马座目标"},
    {"batch": 4, "id": "B04-08", "query": "室女座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "部分名'室女座'应命中多个室女座目标"},
    {"batch": 4, "id": "B04-09", "query": "蛇夫座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "部分名'蛇夫座'应命中多个蛇夫座目标"},
    {"batch": 4, "id": "B04-10", "query": "后发座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 3},
     "desc": "部分名'后发座'应命中多个后发座目标"},

    # ─── 批次 5: 前缀匹配 - 短编号 ───
    {"batch": 5, "id": "B05-01", "query": "M3", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M3"},
     "desc": "M3精确匹配（但也是M31-M39的前缀）"},
    {"batch": 5, "id": "B05-02", "query": "M1", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M1"},
     "desc": "M1精确匹配（但也是M10-M19,M100-M110的前缀）"},
    {"batch": 5, "id": "B05-03", "query": "M", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 10},
     "desc": "单字母'M'应前缀匹配所有M天体"},
    {"batch": 5, "id": "B05-04", "query": "M10", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M10"},
     "desc": "M10精确匹配（也是M100-M109的前缀）"},
    {"batch": 5, "id": "B05-05", "query": "Si", "type_hint": None,
     "expect": {"requires_confirmation": True},
     "desc": "前缀'Si'应匹配Sirius等"},
    {"batch": 5, "id": "B05-06", "query": "Al", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "前缀'Al'应匹配Altair/Aldebaran/Alioth等多个恒星"},
    {"batch": 5, "id": "B05-07", "query": "M5", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M5"},
     "desc": "M5精确匹配（也是M50-M59的前缀）"},
    {"batch": 5, "id": "B05-08", "query": "M8", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M8"},
     "desc": "M8精确匹配（也是M80-M89的前缀）"},
    {"batch": 5, "id": "B05-09", "query": "M9", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M9"},
     "desc": "M9精确匹配（也是M90-M99的前缀）"},
    {"batch": 5, "id": "B05-10", "query": "M2", "type_hint": None,
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M2"},
     "desc": "M2精确匹配（也是M20-M29的前缀）"},

    # ─── 批次 6: 包含匹配 - 英文部分名 ───
    {"batch": 6, "id": "B06-01", "query": "Galaxy", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "泛称'Galaxy'应命中多个星系目标"},
    {"batch": 6, "id": "B06-02", "query": "Nebula", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "泛称'Nebula'应命中多个星云目标"},
    {"batch": 6, "id": "B06-03", "query": "Cluster", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "泛称'Cluster'应命中多个星团目标"},
    {"batch": 6, "id": "B06-04", "query": "Orion", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 2},
     "desc": "'Orion'应匹配猎户座相关目标"},
    {"batch": 6, "id": "B06-05", "query": "triangulum", "type_hint": None,
     "expect": {"confidence_gte": 0.80, "standard_name": "M33"},
     "desc": "'triangulum'包含于M33别名'Triangulum Galaxy'"},
    {"batch": 6, "id": "B06-06", "query": "andromeda", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 2},
     "desc": "'andromeda'应匹配M31及仙女座恒星"},
    {"batch": 6, "id": "B06-07", "query": "Globular", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "'Globular'应命中多个球状星团"},
    {"batch": 6, "id": "B06-08", "query": "Spiral", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 3},
     "desc": "'Spiral'应命中多个旋涡星系"},
    {"batch": 6, "id": "B06-09", "query": "Star", "type_hint": None,
     "expect": {"requires_confirmation": True},
     "desc": "'Star'应匹配含Star的别名"},
    {"batch": 6, "id": "B06-10", "query": "Crab", "type_hint": None,
     "expect": {"confidence_gte": 0.80, "standard_name": "M1"},
     "desc": "'Crab'包含于M1别名'Crab Nebula'"},

    # ─── 批次 7: 类型过滤 ───
    {"batch": 7, "id": "B07-01", "query": "M31", "type_hint": "deep_sky",
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "正确类型提示不影响结果"},
    {"batch": 7, "id": "B07-02", "query": "M31", "type_hint": "star",
     "expect": {"confidence": 0.5, "note": "类型惩罚后1.0*0.5=0.5，可能触发歧义"},
     "desc": "错误类型提示：M31是deep_sky但指定star"},
    {"batch": 7, "id": "B07-03", "query": "Sirius", "type_hint": "star",
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "Sirius"},
     "desc": "正确类型提示不影响结果"},
    {"batch": 7, "id": "B07-04", "query": "Sirius", "type_hint": "deep_sky",
     "expect": {"confidence": 0.5, "note": "类型惩罚后1.0*0.5=0.5"},
     "desc": "错误类型提示：Sirius是star但指定deep_sky"},
    {"batch": 7, "id": "B07-05", "query": "织女星", "type_hint": "star",
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Vega"},
     "desc": "别名匹配+正确类型=0.95*1.0"},
    {"batch": 7, "id": "B07-06", "query": "织女星", "type_hint": "deep_sky",
     "expect": {"confidence": 0.475, "note": "0.95*0.5=0.475，低于0.5阈值"},
     "desc": "别名匹配+错误类型=0.95*0.5=0.475"},
    {"batch": 7, "id": "B07-07", "query": "M42", "type_hint": "planet",
     "expect": {"confidence": 0.5, "note": "planet类型不存在于目录"},
     "desc": "不存在的类型提示planet"},
    {"batch": 7, "id": "B07-08", "query": "天狼星", "type_hint": "star",
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Sirius"},
     "desc": "中文别名+正确类型"},
    {"batch": 7, "id": "B07-09", "query": "天狼星", "type_hint": "deep_sky",
     "expect": {"confidence": 0.475, "note": "0.95*0.5=0.475"},
     "desc": "中文别名+错误类型"},
    {"batch": 7, "id": "B07-10", "query": "M13", "type_hint": "deep_sky",
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M13"},
     "desc": "正确类型提示不影响结果"},

    # ─── 批次 8: 边界条件 - 空/极短/特殊 ───
    {"batch": 8, "id": "B08-01", "query": "", "type_hint": None,
     "expect": {"raises": "ValueError"},
     "desc": "空字符串应抛出ValueError"},
    {"batch": 8, "id": "B08-02", "query": "   ", "type_hint": None,
     "expect": {"raises": "ValueError"},
     "desc": "纯空格应抛出ValueError"},
    {"batch": 8, "id": "B08-03", "query": "M", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 10},
     "desc": "单字符'M'前缀匹配所有M天体"},
    {"batch": 8, "id": "B08-04", "query": "星", "type_hint": None,
     "expect": {"note": "单字'星'，len<2不触发包含匹配，检测行为"},
     "desc": "单字'星'（长度<2，包含匹配被跳过）"},
    {"batch": 8, "id": "B08-05", "query": "a", "type_hint": None,
     "expect": {"note": "单字符'a'，检测前缀匹配行为"},
     "desc": "单字符'a'"},
    {"batch": 8, "id": "B08-06", "query": "M 31", "type_hint": None,
     "expect": {"confidence": 1.0, "standard_name": "M31", "note": "空格被normalize去除"},
     "desc": "带空格的'M 31'（normalize去空格）"},
    {"batch": 8, "id": "B08-07", "query": "m_31", "type_hint": None,
     "expect": {"confidence": 1.0, "standard_name": "M31", "note": "下划线被normalize去除"},
     "desc": "带下划线的'm_31'（normalize去下划线）"},
    {"batch": 8, "id": "B08-08", "query": "NGC224", "type_hint": None,
     "expect": {"confidence": 0.95, "standard_name": "M31", "note": "NGC无空格"},
     "desc": "'NGC224'无空格（normalize后匹配'NGC 224'→'ngc224'）"},
    {"batch": 8, "id": "B08-09", "query": "  M31  ", "type_hint": None,
     "expect": {"confidence": 1.0, "standard_name": "M31"},
     "desc": "前后有空格的M31"},
    {"batch": 8, "id": "B08-10", "query": "M31", "type_hint": "",
     "expect": {"confidence": 1.0, "requires_confirmation": False, "standard_name": "M31",
                "note": "空字符串type_hint应等同于None"},
     "desc": "空字符串type_hint"},

    # ─── 批次 9: 边界条件 - 数值/坐标验证 ───
    {"batch": 9, "id": "B09-01", "query": "M31", "type_hint": None,
     "expect": {"ra_range": [0, 360], "dec_range": [-90, 90]},
     "desc": "验证返回坐标在有效范围内"},
    {"batch": 9, "id": "B09-02", "query": "Polaris", "type_hint": None,
     "expect": {"dec_gte": 89.0, "note": "北极星赤纬应接近+90°"},
     "desc": "北极星赤纬应>89°"},
    {"batch": 9, "id": "B09-03", "query": "Canopus", "type_hint": None,
     "expect": {"dec_lte": -50.0, "note": "老人星赤纬应<-50°"},
     "desc": "老人星赤纬应<-50°"},
    {"batch": 9, "id": "B09-04", "query": "M42", "type_hint": None,
     "expect": {"ra_range": [80, 90], "dec_range": [-10, 0]},
     "desc": "M42坐标范围验证（猎户座）"},
    {"batch": 9, "id": "B09-05", "query": "Sirius", "type_hint": None,
     "expect": {"ra_range": [95, 105], "dec_range": [-20, -15]},
     "desc": "天狼星坐标范围验证"},
    {"batch": 9, "id": "B09-06", "query": "M1", "type_hint": None,
     "expect": {"ra_range": [80, 90], "dec_range": [20, 25]},
     "desc": "M1坐标范围验证（金牛座）"},
    {"batch": 9, "id": "B09-07", "query": "Vega", "type_hint": None,
     "expect": {"ra_range": [275, 285], "dec_range": [35, 42]},
     "desc": "织女星坐标范围验证"},
    {"batch": 9, "id": "B09-08", "query": "M87", "type_hint": None,
     "expect": {"ra_range": [185, 190], "dec_range": [10, 15]},
     "desc": "M87坐标范围验证（室女座）"},
    {"batch": 9, "id": "B09-09", "query": "Altair", "type_hint": None,
     "expect": {"ra_range": [295, 300], "dec_range": [5, 12]},
     "desc": "牛郎星坐标范围验证"},
    {"batch": 9, "id": "B09-10", "query": "M110", "type_hint": None,
     "expect": {"ra_range": [8, 12], "dec_range": [40, 43]},
     "desc": "M110坐标范围验证（仙女座）"},

    # ─── 批次 10: 歧义场景 - 多高分候选 ───
    {"batch": 10, "id": "B10-01", "query": "仙女座星系", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False,
                "note": "虽然'仙女座'匹配多个，但'仙女座星系'精确匹配M31别名"},
     "desc": "精确别名不应因部分名歧义而误判"},
    {"batch": 10, "id": "B10-02", "query": "人马座球状星团", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M22"},
     "desc": "精确匹配M22别名'人马座球状星团'"},
    {"batch": 10, "id": "B10-03", "query": "蛇夫座球状星团", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M9",
                "note": "M9精确匹配0.95，第二名0.85，分差0.10>=0.08自动确认"},
     "desc": "'蛇夫座球状星团'精确匹配M9，分差足够自动确认"},
    {"batch": 10, "id": "B10-04", "query": "狮子座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 3},
     "desc": "'狮子座'应匹配多个狮子座目标"},
    {"batch": 10, "id": "B10-05", "query": "天鹅座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 2},
     "desc": "'天鹅座'应匹配M29/M39及天鹅座恒星"},
    {"batch": 10, "id": "B10-06", "query": "大熊座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 1,
                "note": "已知数据限制：恒星别名无星座名前缀，仅M109命中"},
     "desc": "'大熊座'匹配（目录覆盖有限，仅深空天体含星座名别名）"},
    {"batch": 10, "id": "B10-07", "query": "御夫座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 3},
     "desc": "'御夫座'应匹配M36/M37/M38及Capella"},
    {"batch": 10, "id": "B10-08", "query": "武仙座球状星团", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M13"},
     "desc": "精确匹配M13别名'武仙座球状星团'"},
    {"batch": 10, "id": "B10-09", "query": "天蝎座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 2},
     "desc": "'天蝎座'应匹配M4/M6/M7/M80及Antares"},
    {"batch": 10, "id": "B10-10", "query": "双子座", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 1,
                "note": "已知数据限制：Pollux/Castor别名为北河三/北河二，不含双子座"},
     "desc": "'双子座'匹配（目录覆盖有限，仅M35含星座名别名）"},

    # ─── 批次 11: 歧义场景 - 阈值边界 ───
    {"batch": 11, "id": "B11-01", "query": "Crab Nebula", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M1"},
     "desc": "精确别名匹配0.95，第二名应<0.5"},
    {"batch": 11, "id": "B11-02", "query": "Eagle Nebula", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M16"},
     "desc": "精确别名匹配0.95"},
    {"batch": 11, "id": "B11-03", "query": "Omega Nebula", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M17"},
     "desc": "精确别名匹配0.95"},
    {"batch": 11, "id": "B11-04", "query": "Dumbbell Nebula", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M27"},
     "desc": "精确别名匹配0.95"},
    {"batch": 11, "id": "B11-05", "query": "Whirlpool Galaxy", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M51"},
     "desc": "精确别名匹配0.95"},
    {"batch": 11, "id": "B11-06", "query": "Sombrero Galaxy", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M104"},
     "desc": "精确别名匹配0.95"},
    {"batch": 11, "id": "B11-07", "query": "Pinwheel Galaxy", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M101"},
     "desc": "精确别名匹配0.95"},
    {"batch": 11, "id": "B11-08", "query": "Bode's Galaxy", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M81"},
     "desc": "精确别名匹配0.95（含撇号）"},
    {"batch": 11, "id": "B11-09", "query": "Cigar Galaxy", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M82"},
     "desc": "精确别名匹配0.95"},
    {"batch": 11, "id": "B11-10", "query": "Sunflower Galaxy", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M63"},
     "desc": "精确别名匹配0.95"},

    # ─── 批次 12: 歧义场景 - 包含匹配导致的歧义 ───
    {"batch": 12, "id": "B12-01", "query": "Galaxy", "type_hint": "deep_sky",
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "'Galaxy'+类型过滤仍应有多候选"},
    {"batch": 12, "id": "B12-02", "query": "Nebula", "type_hint": "deep_sky",
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "'Nebula'+类型过滤"},
    {"batch": 12, "id": "B12-03", "query": "Alpha", "type_hint": "star",
     "expect": {"requires_confirmation": True, "candidates_gte": 5},
     "desc": "'Alpha'+star类型应匹配多颗Alpha星"},
    {"batch": 12, "id": "B12-04", "query": "Beta", "type_hint": "star",
     "expect": {"requires_confirmation": True, "candidates_gte": 3},
     "desc": "'Beta'+star类型应匹配多颗Beta星"},
    {"batch": 12, "id": "B12-05", "query": "参宿", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 4},
     "desc": "'参宿'应匹配参宿一~七（多颗猎户座恒星）"},
    {"batch": 12, "id": "B12-06", "query": "天", "type_hint": None,
     "expect": {"note": "单字'天'，len<2不触发包含匹配"},
     "desc": "单字'天'（长度<2）"},
    {"batch": 12, "id": "B12-07", "query": "天津", "type_hint": None,
     "expect": {"note": "'天津'包含于'天津四'(Deneb别名)"},
     "desc": "'天津'应匹配Deneb（天津四）"},
    {"batch": 12, "id": "B12-08", "query": "河鼓", "type_hint": None,
     "expect": {"confidence_gte": 0.80, "standard_name": "Altair"},
     "desc": "'河鼓'包含于Altair别名'河鼓二'"},
    {"batch": 12, "id": "B12-09", "query": "轩辕", "type_hint": None,
     "expect": {"confidence_gte": 0.80, "standard_name": "Regulus"},
     "desc": "'轩辕'包含于Regulus别名'轩辕十四'"},
    {"batch": 12, "id": "B12-10", "query": "北河", "type_hint": None,
     "expect": {"requires_confirmation": True, "candidates_gte": 2,
                "note": "'北河'匹配'北河二'(Castor)和'北河三'(Pollux)"},
     "desc": "'北河'应歧义（北河二/北河三）"},

    # ─── 批次 13: 无匹配/异常输入 ───
    {"batch": 13, "id": "B13-01", "query": "XYZ123", "type_hint": None,
     "expect": {"confidence": 0.0, "requires_confirmation": True, "standard_name": ""},
     "desc": "完全无意义的输入"},
    {"batch": 13, "id": "B13-02", "query": "哈利波特星云", "type_hint": None,
     "expect": {"confidence": 0.0, "requires_confirmation": True, "standard_name": ""},
     "desc": "虚构目标名"},
    {"batch": 13, "id": "B13-03", "query": "M999", "type_hint": None,
     "expect": {"confidence": 0.0, "requires_confirmation": True, "standard_name": "",
                "note": "M999不存在，但'M'前缀匹配可能给0.3"},
     "desc": "不存在的M编号M999"},
    {"batch": 13, "id": "B13-04", "query": "NGC 99999", "type_hint": None,
     "expect": {"requires_confirmation": True, "note": "不存在的NGC编号"},
     "desc": "不存在的NGC编号"},
    {"batch": 13, "id": "B13-05", "query": "!@#$%", "type_hint": None,
     "expect": {"confidence": 0.0, "requires_confirmation": True},
     "desc": "特殊字符输入"},
    {"batch": 13, "id": "B13-06", "query": "a" * 500, "type_hint": None,
     "expect": {"confidence": 0.0, "requires_confirmation": True, "note": "超长输入不应崩溃"},
     "desc": "超长字符串（500字符）"},
    {"batch": 13, "id": "B13-07", "query": "M31 M42", "type_hint": None,
     "expect": {"note": "多目标输入，normalize后为'm31m42'"},
     "desc": "多目标同时输入"},
    {"batch": 13, "id": "B13-08", "query": "仙女座星系M31", "type_hint": None,
     "expect": {"note": "中文名+编号混合输入"},
     "desc": "中文名+编号混合"},
    {"batch": 13, "id": "B13-09", "query": "\t\n", "type_hint": None,
     "expect": {"raises": "ValueError", "note": "制表符换行符strip后为空"},
     "desc": "制表符/换行符（strip后为空）"},
    {"batch": 13, "id": "B13-10", "query": "M31", "type_hint": None,
     "expect": {"source": "built_in_catalog_v1"},
     "desc": "验证source字段正确"},

    # ─── 批次 14: 候选列表质量 ───
    {"batch": 14, "id": "B14-01", "query": "仙女座", "type_hint": None,
     "expect": {"candidates_contain": ["M31", "M32", "M110"],
                "note": "候选列表应包含所有仙女座目标"},
     "desc": "候选列表完整性-仙女座"},
    {"batch": 14, "id": "B14-02", "query": "猎户座", "type_hint": None,
     "expect": {"candidates_contain": ["M42"],
                "note": "候选列表应包含M42"},
     "desc": "候选列表完整性-猎户座"},
    {"batch": 14, "id": "B14-03", "query": "Al", "type_hint": None,
     "expect": {"candidates_contain": ["Altair", "Aldebaran"],
                "note": "候选列表应包含Al开头的恒星"},
     "desc": "候选列表完整性-Al前缀"},
    {"batch": 14, "id": "B14-04", "query": "球状星团", "type_hint": None,
     "expect": {"candidates_lte": 10, "note": "候选列表上限10条"},
     "desc": "候选列表不超过10条"},
    {"batch": 14, "id": "B14-05", "query": "星云", "type_hint": None,
     "expect": {"candidates_lte": 10},
     "desc": "候选列表上限验证-星云"},
    {"batch": 14, "id": "B14-06", "query": "M1", "type_hint": None,
     "expect": {"requires_confirmation": False,
                "note": "精确匹配M1时不应有候选列表（即使有前缀匹配）"},
     "desc": "精确匹配时候选列表应为空/None"},
    {"batch": 14, "id": "B14-07", "query": "北河", "type_hint": None,
     "expect": {"candidates_contain": ["Castor", "Pollux"]},
     "desc": "候选列表应包含北河二和北河三"},
    {"batch": 14, "id": "B14-08", "query": "参宿", "type_hint": None,
     "expect": {"candidates_contain": ["Betelgeuse", "Rigel"]},
     "desc": "候选列表应包含参宿四和参宿七"},
    {"batch": 14, "id": "B14-09", "query": "M", "type_hint": None,
     "expect": {"candidates_lte": 10, "candidates_gte": 10,
                "note": "候选列表恰好10条（上限）"},
     "desc": "候选列表恰好达到上限10"},
    {"batch": 14, "id": "B14-10", "query": "人马座", "type_hint": None,
     "expect": {"candidates_lte": 10, "candidates_gte": 5},
     "desc": "候选列表数量合理性-人马座"},

    # ─── 批次 15: 综合/回归测试 ───
    {"batch": 15, "id": "B15-01", "query": "仙女座大星云", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M31"},
     "desc": "M31别名'仙女座大星云'精确匹配"},
    {"batch": 15, "id": "B15-02", "query": "七姊妹星团", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M45"},
     "desc": "M45别名'七姊妹星团'精确匹配"},
    {"batch": 15, "id": "B15-03", "query": "奥特曼星云", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "M78"},
     "desc": "M78别名'奥特曼星云'精确匹配"},
    {"batch": 15, "id": "B15-04", "query": "大火", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Antares"},
     "desc": "Antares别名'大火'精确匹配"},
    {"batch": 15, "id": "B15-05", "query": "勾陈一", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Polaris"},
     "desc": "Polaris别名'勾陈一'精确匹配"},
    {"batch": 15, "id": "B15-06", "query": "五车二", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Capella"},
     "desc": "Capella别名'五车二'精确匹配"},
    {"batch": 15, "id": "B15-07", "query": "南门二", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Alpha Centauri"},
     "desc": "Alpha Centauri别名'南门二'精确匹配"},
    {"batch": 15, "id": "B15-08", "query": "北落师门", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Fomalhaut"},
     "desc": "Fomalhaut别名'北落师门'精确匹配"},
    {"batch": 15, "id": "B15-09", "query": "辇道增七", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Albireo"},
     "desc": "Albireo别名'辇道增七'精确匹配"},
    {"batch": 15, "id": "B15-10", "query": "大陵五", "type_hint": None,
     "expect": {"confidence": 0.95, "requires_confirmation": False, "standard_name": "Algol"},
     "desc": "Algol别名'大陵五'精确匹配"},
]


# ═══════════════════════════════════════════════════════════
# 检测引擎
# ═══════════════════════════════════════════════════════════

def run_single_test(case: dict) -> dict:
    """执行单条测试，返回结果记录。"""
    record = {
        "id": case["id"],
        "batch": case["batch"],
        "query": case["query"][:50],  # 截断超长输入
        "type_hint": case["type_hint"],
        "desc": case["desc"],
        "status": "UNKNOWN",
        "issues": [],
        "actual": {},
    }

    expect = case["expect"]

    # 执行 resolve_target
    try:
        result = resolve_target(case["query"], case["type_hint"])
    except ValueError as e:
        if expect.get("raises") == "ValueError":
            record["status"] = "PASS"
            record["actual"] = {"raised": f"ValueError: {e}"}
        else:
            record["status"] = "FAIL"
            record["issues"].append(f"意外ValueError: {e}")
        return record
    except Exception as e:
        record["status"] = "FAIL"
        record["issues"].append(f"意外异常: {type(e).__name__}: {e}")
        return record

    # 如果预期抛异常但没抛
    if expect.get("raises"):
        record["status"] = "FAIL"
        record["issues"].append(f"预期抛出{expect['raises']}但未抛出")
        return record

    # 记录实际输出
    record["actual"] = {
        "standard_name": result.standard_name,
        "confidence": result.confidence,
        "requires_confirmation": result.requires_confirmation,
        "candidates_count": len(result.candidates) if result.candidates else 0,
        "ra_deg": result.ra_deg,
        "dec_deg": result.dec_deg,
        "source": result.source,
    }

    issues = []

    # 检查 confidence 精确值
    if "confidence" in expect:
        if abs(result.confidence - expect["confidence"]) > 0.001:
            issues.append(
                f"confidence不符: 预期{expect['confidence']}, 实际{result.confidence}"
            )

    # 检查 confidence >= 某值
    if "confidence_gte" in expect:
        if result.confidence < expect["confidence_gte"]:
            issues.append(
                f"confidence过低: 预期>={expect['confidence_gte']}, 实际{result.confidence}"
            )

    # 检查 requires_confirmation
    if "requires_confirmation" in expect:
        if result.requires_confirmation != expect["requires_confirmation"]:
            issues.append(
                f"requires_confirmation不符: 预期{expect['requires_confirmation']}, "
                f"实际{result.requires_confirmation}"
            )

    # 检查 standard_name
    if "standard_name" in expect:
        if result.standard_name != expect["standard_name"]:
            issues.append(
                f"standard_name不符: 预期'{expect['standard_name']}', "
                f"实际'{result.standard_name}'"
            )

    # 检查候选列表数量 >=
    if "candidates_gte" in expect:
        actual_count = len(result.candidates) if result.candidates else 0
        if actual_count < expect["candidates_gte"]:
            issues.append(
                f"候选列表过短: 预期>={expect['candidates_gte']}, 实际{actual_count}"
            )

    # 检查候选列表数量 <=
    if "candidates_lte" in expect:
        actual_count = len(result.candidates) if result.candidates else 0
        if actual_count > expect["candidates_lte"]:
            issues.append(
                f"候选列表过长: 预期<={expect['candidates_lte']}, 实际{actual_count}"
            )

    # 检查候选列表包含特定目标
    if "candidates_contain" in expect:
        actual_names = [c.standard_name for c in (result.candidates or [])]
        for expected_name in expect["candidates_contain"]:
            if expected_name not in actual_names:
                issues.append(
                    f"候选列表缺少'{expected_name}', 实际列表: {actual_names[:5]}"
                )

    # 检查坐标范围
    if "ra_range" in expect:
        lo, hi = expect["ra_range"]
        if not (lo <= result.ra_deg <= hi):
            issues.append(f"RA超出范围[{lo},{hi}]: 实际{result.ra_deg}")

    if "dec_range" in expect:
        lo, hi = expect["dec_range"]
        if not (lo <= result.dec_deg <= hi):
            issues.append(f"Dec超出范围[{lo},{hi}]: 实际{result.dec_deg}")

    if "dec_gte" in expect:
        if result.dec_deg < expect["dec_gte"]:
            issues.append(f"Dec过低: 预期>={expect['dec_gte']}, 实际{result.dec_deg}")

    if "dec_lte" in expect:
        if result.dec_deg > expect["dec_lte"]:
            issues.append(f"Dec过高: 预期<={expect['dec_lte']}, 实际{result.dec_deg}")

    # 检查 source
    if "source" in expect:
        if result.source != expect["source"]:
            issues.append(f"source不符: 预期'{expect['source']}', 实际'{result.source}'")

    record["issues"] = issues
    record["status"] = "PASS" if not issues else "FAIL"

    # 附加 note（不算失败，仅记录）
    if "note" in expect:
        record["note"] = expect["note"]

    return record


def run_batch(batch_num: int) -> list[dict]:
    """执行指定批次的所有测试。"""
    batch_cases = [c for c in TEST_CASES if c["batch"] == batch_num]
    results = []
    for case in batch_cases:
        results.append(run_single_test(case))
    return results


def run_all():
    """执行全部15批测试并输出报告。"""
    print(f"{'='*70}")
    print(f"  置信度/候选列表/人工确认 算法合理性检测")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  用例总数: {len(TEST_CASES)} (15批 × 10条)")
    print(f"{'='*70}\n")

    all_results = []
    batch_stats = []

    for batch_num in range(1, 16):
        results = run_batch(batch_num)
        all_results.extend(results)

        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        batch_stats.append((batch_num, passed, failed))

        print(f"  批次 {batch_num:2d}: {passed} PASS / {failed} FAIL")

    # 汇总
    total_pass = sum(1 for r in all_results if r["status"] == "PASS")
    total_fail = sum(1 for r in all_results if r["status"] == "FAIL")

    print(f"\n{'='*70}")
    print(f"  总计: {total_pass} PASS / {total_fail} FAIL / {len(all_results)} TOTAL")
    print(f"{'='*70}")

    # 输出失败详情
    if total_fail > 0:
        print(f"\n{'─'*70}")
        print(f"  失败用例详情:")
        print(f"{'─'*70}")
        for r in all_results:
            if r["status"] == "FAIL":
                print(f"\n  [{r['id']}] {r['desc']}")
                print(f"    输入: query='{r['query']}', type_hint={r['type_hint']}")
                print(f"    实际: {json.dumps(r['actual'], ensure_ascii=False, default=str)}")
                for issue in r["issues"]:
                    print(f"    [FAIL] {issue}")
                if r.get("note"):
                    print(f"    [NOTE] {r['note']}")

    # 输出需关注的PASS（有note的）
    notable = [r for r in all_results if r["status"] == "PASS" and r.get("note")]
    if notable:
        print(f"\n{'─'*70}")
        print(f"  需关注的PASS用例（有备注）:")
        print(f"{'─'*70}")
        for r in notable:
            print(f"  [{r['id']}] {r['desc']}")
            print(f"    [NOTE] {r['note']}")
            if r["actual"]:
                print(f"    实际: confidence={r['actual'].get('confidence')}, "
                      f"requires_confirmation={r['actual'].get('requires_confirmation')}, "
                      f"candidates={r['actual'].get('candidates_count')}")

    # 保存JSON结果
    output_path = Path(__file__).resolve().parent / "confidence_test_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(all_results),
            "passed": total_pass,
            "failed": total_fail,
            "batch_stats": [{"batch": b, "passed": p, "failed": f} for b, p, f in batch_stats],
            "results": all_results,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  详细结果已保存: {output_path}")

    return total_fail


if __name__ == "__main__":
    failures = run_all()
    sys.exit(0 if failures == 0 else 1)
