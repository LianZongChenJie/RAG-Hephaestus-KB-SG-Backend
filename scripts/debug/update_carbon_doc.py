# -*- coding: utf-8 -*-
import re

doc_path = r"E:\纵联宸捷\首钢项目\会展小镇项目\RAG-Hephaestus-KB-SG-Backend\docs\API接口文档.md"

with open(doc_path, "r", encoding="utf-8") as f:
    content = f.read()

old_json = '''```json
{
    "report_id": 25,
    "report_title": "多模态能碳计算报告 - 2026年6月",
    "report_desc": "本报告基于会展小镇内电、水、气、热四类能源的实时计量数据，融合物理机理模型与机器学习算法，对园区能碳排放进行多维度精准核算。",
    "energy_type_count": 4,
    "today_carbon": 28.5,
    "today_carbon_change": -3.2,
    "month_carbon": 856.3,
    "month_carbon_change": -5.8,
    "carbon_intensity": 0.45,
    "carbon_intensity_change": -8.2,
    "metrics": [
        {
            "value": "856.3",
            "label": "本月碳排(吨CO₂)"
        },
        {
            "value": "-5.8%",
            "label": "环比变化"
        },
        {
            "value": "0.45",
            "label": "碳强度(kg/㎡)"
        },
        {
            "value": "12.3%",
            "label": "减排潜力"
        }
    ],
    "carbon_sources": [
        {
            "source": "电力",
            "value": 582.28,
            "percentage": 68.0
        },
        {
            "source": "天然气",
            "value": 188.39,
            "percentage": 22.0
        },
        {
            "source": "热力",
            "value": 59.94,
            "percentage": 7.0
        },
        {
            "source": "其他",
            "value": 25.69,
            "percentage": 3.0
        }
    ],
    "carbon_trends": [
        {
            "month": "2026-01",
            "actual": 920.5,
            "target": 950.0
        },
        {
            "month": "2026-02",
            "actual": 875.3,
            "target": 920.0
        },
        {
            "month": "2026-03",
            "actual": 892.1,
            "target": 900.0
        }
    ],
    "summary": "本月碳排放总量为856.3吨CO₂，较上月下降5.8%。电力是主要碳排放来源，占比68%，建议重点优化用电结构。",
    "suggestions": [
        "优化空调系统运行策略，降低电力消耗",
        "推广绿色能源使用，减少碳排放",
        "建立碳排放预警机制，实时监控碳排放异常"
    ]
}
```'''

new_json = '''```json
{
    "report_id": 27,
    "report_title": "多模态能碳计算报告 - 2026年9月",
    "report_desc": "本报告基于低压配电能源数据，核算首钢会展小镇演唱会场馆在2026年8月至9月的碳排放绩效。数据显示本月碳排放量环比上升，主要源于电力消耗增加，需重点关注用电高峰期的能效优化与负荷管理。",
    "energy_type_count": 19,
    "today_carbon": 22118.56,
    "today_carbon_change": 6.2,
    "month_carbon": 378290.12,
    "month_carbon_change": 6.2,
    "carbon_intensity": 37829.01,
    "carbon_intensity_change": 6.2,
    "metrics": [
        {"value": "378,290.12", "label": "本月总碳排放量 (吨CO₂)"},
        {"value": "+6.2%", "label": "环比变化"},
        {"value": "37.83", "label": "碳强度 (kgCO₂/m²)"},
        {"value": "427,930", "label": "本月总能耗 (kWh)"}
    ],
    "carbon_sources": [
        {"source": "电力",   "value": 378290.12, "percentage": 100.0},
        {"source": "天然气", "value": 0.0,        "percentage": 0.0},
        {"source": "热力",   "value": 0.0,        "percentage": 0.0},
        {"source": "其他",   "value": 0.0,        "percentage": 0.0}
    ],
    "carbon_trends": [
        {"month": "2026-08", "actual": 176897.24, "target": 159207.52},
        {"month": "2026-09", "actual": 201392.88, "target": 181253.59}
    ],
    "carbon_analysis": {
        "performance": {
            "monthly_carbon": 378290.12,
            "month_over_month_change": "+6.2%",
            "carbon_intensity": 37.83,
            "reduction_potential": "12.5%"
        },
        "source_analysis": {
            "total_carbon": 378290.12,
            "sources": [
                {"source": "电力",   "value": 378290.12, "percentage": 100.0},
                {"source": "天然气", "value": 0.0,        "percentage": 0.0},
                {"source": "热力",   "value": 0.0,        "percentage": 0.0},
                {"source": "其他",   "value": 0.0,        "percentage": 0.0}
            ]
        },
        "trend_analysis": {
            "trend_items": [
                {"month": "2026-08", "actual": 176897.24, "target": 159207.52},
                {"month": "2026-09", "actual": 201392.88, "target": 181253.59}
            ],
            "peak_month": "2026-09",
            "trough_month": "2026-08",
            "average": 189145.06
        },
        "target_comparison": {
            "months": ["2026-08", "2026-09"],
            "actual_data": [176897.24, 201392.88],
            "target_data": [159207.52, 181253.59],
            "exceed_count": 2,
            "achieve_count": 0
        },
        "core_conclusion": "本月碳排放环比上升6.2%，主要受电力消耗驱动。建议优化演唱会期间照明与空调负荷，利用峰谷电价策略降低峰值用电，预计可释放12.5%减排潜力。"
    },
    "summary": "本月园区碳排放总量为37.8万吨，碳强度达37.83kgCO₂/m²。电力是唯一排放源且占比100%。9月排放创近两月新高，已连续两个月超出基于均值90%设定的减排目标。需立即介入用电管理。",
    "suggestions": [
        "实施演唱会期间分时段照明控制策略，避免全功率运行。",
        "调整空调系统启停时间，利用夜间谷电蓄冷或预冷。",
        "排查高耗能设备（如舞台灯光、大型音响）的待机能耗。"
    ]
}
```'''

if old_json in content:
    new_content = content.replace(old_json, new_json, 1)
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("SUCCESS: carbon JSON replaced")
else:
    print("ERROR: old JSON not found in file")
    # Try to find partial match
    if '"report_id": 25' in content:
        print("Found 'report_id: 25' in file")
    if '多模态能碳计算报告' in content:
        print("Found '多模态能碳计算报告' in file")
