"""
数据真实性测试用例集
====================

从手工测试矩阵图里抽取的核心业务用例, 每条:
    - 业务域
    - 问题 (用户原问法)
    - 预期 Q-ID (从问答手册找 SQL 范式, 作"基准")
    - 预期数据名 (用于对比)

基准路径: 用 SQL 范式直接查达梦 (人工核对过的)
LLM 路径: 走 /api/chat-stream (LLM 改写过的 SQL)
对比: 两边数据是否一致 (行数 / 关键指标 / 数值)
"""
from __future__ import annotations
from typing import Optional


# 用例结构: (业务域, 问题, Q-ID, 预期数据名/列, 备注)
CASES: list[dict] = [
    # ====== 总体核查 ======
    {"domain": "总体核查", "question": "总设备数", "qid": "3.1", "metric": "总数"},
    {"domain": "总体核查", "question": "在线设备数", "qid": "3.x", "metric": "在线数"},
    {"domain": "总体核查", "question": "设备管家", "qid": "3.x", "metric": "设备数"},
    {"domain": "总体核查", "question": "待处理告警", "qid": "2.1", "metric": "未处理数"},

    # ====== 能源 1 (量计) ======
    {"domain": "能源1量计", "question": "今日总用电量", "qid": "5.1", "metric": "总用电"},
    {"domain": "能源1量计", "question": "今日总用水量", "qid": "5.1", "metric": "总用水"},
    {"domain": "能源1量计", "question": "用能结构分析图", "qid": "5.1", "metric": "结构占比"},
    {"domain": "能源1量计", "question": "能量概览", "qid": "5.1", "metric": "总能量"},
    {"domain": "能源1量计", "question": "表计总数", "qid": "5.1", "metric": "表计数"},
    {"domain": "能源1量计", "question": "今日用水率", "qid": "5.x", "metric": "水耗"},
    {"domain": "能源1量计", "question": "用能结构分析图", "qid": "5.1", "metric": "能介结构"},

    # ====== 计量 1 (量计) ======
    {"domain": "计量1量计", "question": "计量项目总数", "qid": "5.7", "metric": "项目数"},
    {"domain": "计量1量计", "question": "配套关系", "qid": "5.7", "metric": "配套清单"},
    {"domain": "计量1量计", "question": "水表项目", "qid": "5.x", "metric": "水表清单"},
    {"domain": "计量1量计", "question": "计量规则配置", "qid": "5.x", "metric": "规则数"},

    # ====== 计量 2 (量计) ======
    {"domain": "计量2量计", "question": "本月总用电", "qid": "5.1", "metric": "月用电"},
    {"domain": "计量2量计", "question": "本月总用水", "qid": "5.1", "metric": "月用水"},
    {"domain": "计量2量计", "question": "尖峰平谷", "qid": "5.6", "metric": "分时电量"},

    # ====== 分析报表类 ======
    {"domain": "分析报表", "question": "整点同环比", "qid": "1.4", "metric": "登录次数"},
    {"domain": "分析报表", "question": "今日下设备", "qid": "3.x", "metric": "下设备数"},
    {"domain": "分析报表", "question": "设备总数", "qid": "3.1", "metric": "设备总数"},
    {"domain": "分析报表", "question": "登录趋势", "qid": "1.4", "metric": "登录数"},
    {"domain": "分析报表", "question": "今日下班", "qid": "1.4", "metric": "下班数"},
    {"domain": "分析报表", "question": "设备总数据", "qid": "1.x", "metric": "数据量"},

    # ====== 变配电 ======
    {"domain": "变配电", "question": "在线总数", "qid": "3.2", "metric": "在线数"},
    {"domain": "变配电", "question": "离线总数", "qid": "3.2", "metric": "离线数"},
    {"domain": "变配电", "question": "今日能耗", "qid": "5.1", "metric": "今日能耗"},
    {"domain": "变配电", "question": "平均功率", "qid": "5.1", "metric": "平均功率"},

    # ====== 空调机组 ======
    {"domain": "空调机组", "question": "空调机组总数", "qid": "3.x", "metric": "机组数"},
    {"domain": "空调机组", "question": "在线数", "qid": "3.2", "metric": "在线"},
    {"domain": "空调机组", "question": "离线数", "qid": "3.2", "metric": "离线"},
    {"domain": "空调机组", "question": "平均pm2.5", "qid": "8.x", "metric": "pm2.5"},
    {"domain": "空调机组", "question": "列表", "qid": "3.x", "metric": "清单"},

    # ====== 新风机组 ======
    {"domain": "新风机组", "question": "图形看板", "qid": "3.x", "metric": "看板"},
    {"domain": "新风机组", "question": "工艺看板", "qid": "3.x", "metric": "看板"},
    {"domain": "新风机组", "question": "总条数", "qid": "3.1", "metric": "总数"},
    {"domain": "新风机组", "question": "在线数", "qid": "3.2", "metric": "在线"},
    {"domain": "新风机组", "question": "离线数", "qid": "3.2", "metric": "离线"},

    # ====== 排风机 ======
    {"domain": "排风机", "question": "总条数", "qid": "3.1", "metric": "总数"},
    {"domain": "排风机", "question": "在线数", "qid": "3.2", "metric": "在线"},
    {"domain": "排风机", "question": "离线数", "qid": "3.2", "metric": "离线"},
    {"domain": "排风机", "question": "平均温度", "qid": "8.x", "metric": "温度"},
    {"domain": "排风机", "question": "图形看板", "qid": "3.x", "metric": "看板"},

    # ====== 热回收 ======
    {"domain": "热回收", "question": "总条数", "qid": "3.1", "metric": "总数"},
    {"domain": "热回收", "question": "在线数", "qid": "3.2", "metric": "在线"},
    {"domain": "热回收", "question": "回收效率", "qid": "3.x", "metric": "效率"},
    {"domain": "热回收", "question": "总能耗", "qid": "5.1", "metric": "总能耗"},

    # ====== 污水 ======
    {"domain": "污水", "question": "总条数", "qid": "3.1", "metric": "总数"},
    {"domain": "污水", "question": "在线数", "qid": "3.2", "metric": "在线"},
    {"domain": "污水", "question": "点位位置", "qid": "3.x", "metric": "位置"},
    {"domain": "污水", "question": "当班", "qid": "1.4", "metric": "值班"},

    # ====== 给水 ======
    {"domain": "给水", "question": "点位位置", "qid": "3.x", "metric": "位置"},
    {"domain": "给水", "question": "工单", "qid": "1.4", "metric": "工单数"},

    # ====== 热水 ======
    {"domain": "热水", "question": "设备型号", "qid": "3.x", "metric": "型号"},

    # ====== 燃气 ======
    {"domain": "燃气", "question": "设备名称", "qid": "3.x", "metric": "名称"},
    {"domain": "燃气", "question": "数据采集", "qid": "1.x", "metric": "数据量"},

    # ====== 分室内 ======
    {"domain": "分室内", "question": "分室内今日耗电", "qid": "5.1", "metric": "今日耗电"},
    {"domain": "分室内", "question": "分室内碳排放", "qid": "5.8", "metric": "碳排放"},
    {"domain": "分室内", "question": "分室内节能量", "qid": "5.x", "metric": "节能"},

    # ====== 分内分 ======
    {"domain": "分内分", "question": "分内分计能", "qid": "5.1", "metric": "能耗"},
    {"domain": "分内分", "question": "分内分用能", "qid": "5.1", "metric": "用能"},

    # ====== 报警机房告 ======
    {"domain": "报警机房", "question": "报警设备", "qid": "11.x", "metric": "设备数"},
    {"domain": "报警机房", "question": "工单状态", "qid": "14.x", "metric": "状态"},
    {"domain": "报警机房", "question": "报警类型", "qid": "2.3", "metric": "类型分布"},

    # ====== 门禁 ======
    {"domain": "门禁", "question": "事件列表", "qid": "10.2", "metric": "事件数"},
    {"domain": "门禁", "question": "事件趋势", "qid": "10.2", "metric": "趋势"},
    {"domain": "门禁", "question": "事件状态", "qid": "10.x", "metric": "状态"},
    {"domain": "门禁", "question": "门禁设备", "qid": "10.1", "metric": "设备数"},
    {"domain": "门禁", "question": "按部门", "qid": "10.x", "metric": "按部门统计"},

    # ====== 会签管理 ======
    {"domain": "会签", "question": "火化率", "qid": "14.x", "metric": "火化率"},
    {"domain": "会签", "question": "数据状态", "qid": "14.x", "metric": "状态"},
    {"domain": "会签", "question": "处理状态", "qid": "14.x", "metric": "处理状态"},
    {"domain": "会签", "question": "工单状态", "qid": "14.x", "metric": "工单"},

    # ====== 会前管理 ======
    {"domain": "会前", "question": "会议列表", "qid": "15.1", "metric": "列表"},
    {"domain": "会前", "question": "会议时间", "qid": "15.1", "metric": "时间"},
    {"domain": "会前", "question": "会议类型", "qid": "15.x", "metric": "类型"},
    {"domain": "会前", "question": "会议纪要", "qid": "15.1", "metric": "纪要"},

    # ====== 会中管理 ======
    {"domain": "会中", "question": "进行中会议", "qid": "15.1", "metric": "进行中"},
    {"domain": "会中", "question": "报告生成", "qid": "15.x", "metric": "报告"},
    {"domain": "会中", "question": "议事厅", "qid": "15.x", "metric": "议事"},
    {"domain": "会中", "question": "声音文件", "qid": "15.x", "metric": "音频"},

    # ====== 会后管理 ======
    {"domain": "会后", "question": "已结束", "qid": "15.3", "metric": "已结束"},
    {"domain": "会后", "question": "知识库", "qid": "15.3", "metric": "知识库"},
    {"domain": "会后", "question": "总条报告", "qid": "15.3", "metric": "报告数"},
    {"domain": "会后", "question": "优化建议", "qid": "15.3", "metric": "建议"},

    # ====== 扬饭客流 ======
    {"domain": "客流", "question": "今日总客流", "qid": "13.3", "metric": "总客流"},
    {"domain": "客流", "question": "平均停留", "qid": "13.x", "metric": "平均停留"},
    {"domain": "客流", "question": "分时趋势", "qid": "13.2", "metric": "分时"},

    # ====== 场饭跟踪 ======
    {"domain": "场饭", "question": "今日活动", "qid": "15.1", "metric": "活动数"},
    {"domain": "场饭", "question": "待等签", "qid": "15.x", "metric": "待签"},
    {"domain": "场饭", "question": "平均停留", "qid": "13.x", "metric": "停留"},

    # ====== 设备类型 ======
    {"domain": "设备类型", "question": "设备类型", "qid": "3.x", "metric": "类型数"},
    {"domain": "设备类型", "question": "设备总数", "qid": "3.1", "metric": "总数"},
    {"domain": "设备类型", "question": "在线数", "qid": "3.2", "metric": "在线"},
    {"domain": "设备类型", "question": "离线数", "qid": "3.2", "metric": "离线"},

    # ====== 报警告警 ======
    {"domain": "报警", "question": "待处理", "qid": "2.1", "metric": "未处理"},
    {"domain": "报警", "question": "处理中", "qid": "2.x", "metric": "处理中"},
    {"domain": "报警", "question": "已处理", "qid": "2.x", "metric": "已处理"},
    {"domain": "报警", "question": "总条数", "qid": "2.1", "metric": "总数"},
    {"domain": "报警", "question": "近处理", "qid": "2.1", "metric": "近处理"},

    # ====== 接口平台 ======
    {"domain": "接口", "question": "接平台总条数", "qid": "16.x", "metric": "接口数"},
    {"domain": "接口", "question": "活跃", "qid": "16.x", "metric": "活跃"},
    {"domain": "接口", "question": "异常", "qid": "16.x", "metric": "异常"},
    {"domain": "接口", "question": "报备", "qid": "16.x", "metric": "报备"},
    {"domain": "接口", "question": "测试中", "qid": "16.x", "metric": "测试中"},

    # ====== 数字运行图 ======
    {"domain": "数字运行", "question": "总数据", "qid": "1.4", "metric": "总数据"},
    {"domain": "数字运行", "question": "数据库总", "qid": "1.4", "metric": "库总"},
    {"domain": "数字运行", "question": "数据表", "qid": "1.x", "metric": "表数"},
]


def all_cases() -> list[dict]:
    """拿全部用例"""
    return list(CASES)


def by_domain() -> dict[str, list[dict]]:
    """按业务域分组"""
    out: dict[str, list[dict]] = {}
    for c in CASES:
        out.setdefault(c["domain"], []).append(c)
    return out


def get_case(idx: int) -> dict:
    """按索引拿用例 (0-based)"""
    return CASES[idx]


if __name__ == "__main__":
    print(f"=== 数据真实性测试用例集 ===")
    print(f"总数: {len(CASES)}")
    by = by_domain()
    print(f"业务域: {len(by)} 个")
    for d, cases in by.items():
        print(f"  - {d}: {len(cases)} 条")
    print(f"\n前 3 条样例:")
    for c in CASES[:3]:
        print(f"  {c}")
