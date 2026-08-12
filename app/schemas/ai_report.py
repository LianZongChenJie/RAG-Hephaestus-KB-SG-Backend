"""AI报告相关数据模型"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ReportScope(str, Enum):
    """报告范围"""
    ALL = "all"           # 全园区
    ZONE = "zone"         # 分区
    DEVICE = "device"      # 单台设备


class TimeRange(str, Enum):
    """时间范围"""
    DAY = "day"           # 日
    WEEK = "week"         # 周
    MONTH = "month"       # 月
    QUARTER = "quarter"   # 季度
    YEAR = "year"         # 年


# ============ AI运行报告 ============

class AIRunReportRequest(BaseModel):
    """AI运行报告请求"""
    scope: ReportScope = Field(..., description="报告范围: all=全园区, zone=分区, device=单台设备")
    time_range: TimeRange = Field(..., description="时间范围: day=日, week=周, month=月, quarter=季度, year=年")
    venue_name: Optional[str] = Field(None, description="会展名称(筛选特定会展的数据)")
    zone_name: Optional[str] = Field(None, description="分区名称(当scope=zone时必填)")
    device_id: Optional[int] = Field(None, description="设备ID(当scope=device时必填)")
    device_name: Optional[str] = Field(None, description="设备名称")


class AIMetricItem(BaseModel):
    """AI报告指标项"""
    value: str = Field(..., description="指标值")
    label: str = Field(..., description="指标标签")


class StatCardItem(BaseModel):
    """统计卡片项"""
    label: str = Field(..., description="指标名称")
    value: str = Field(..., description="指标值")
    change: Optional[str] = Field(None, description="环比变化（如：↑ 12 本月、↑ 2.3% 较上月）")
    subtitle: Optional[str] = Field(None, description="副标题/补充说明（如：全部核心设备）")


class DeviceCategoryItem(BaseModel):
    """设备类型统计项"""
    category_name: str = Field(..., description="设备类型名称")
    device_count: int = Field(..., description="设备数量")
    online_count: int = Field(..., description="在线数量")
    offline_count: int = Field(..., description="离线数量")


class AlarmDistributionItem(BaseModel):
    """告警分布项"""
    category: Optional[str] = Field(None, description="告警类别")
    alarm_category_name: Optional[str] = Field(None, description="告警类别(LLM原始字段)")
    count: int = Field(..., description="告警数量")
    percentage: Optional[float] = Field(None, description="占比")

    @model_validator(mode="before")
    @classmethod
    def _map_alarm_category_name(cls, data):
        if isinstance(data, dict):
            # 兼容 LLM 返回 alarm_category_name 的情况：映射到 category
            if "alarm_category_name" in data and data.get("alarm_category_name"):
                data["category"] = data["alarm_category_name"]
            # 也兼容 category 写错为 alarm_category
            elif "alarm_category" in data and data.get("alarm_category"):
                data["category"] = data["alarm_category"]
            # 兜底：尝试从其他常见字段找
            elif data.get("category") is None:
                for k in ("name", "type", "alarm_type"):
                    if data.get(k):
                        data["category"] = data[k]
                        break
        return data


class SpaceAlarmItem(BaseModel):
    """空间告警分布项"""
    space_name: str = Field(..., description="空间名称")
    alarm_count: int = Field(..., description="告警数量")


class ReportListItem(BaseModel):
    """报告列表项（用于报告摘要区底部的历史报告表格）"""
    id: int = Field(..., description="报告ID")
    title: str = Field(..., description="报告名称")
    report_type: str = Field(..., description="类型: all=整体, zone=分区, device=单台")
    scope: Optional[str] = Field(None, description="分析范围")
    created_at: str = Field(..., description="生成时间")
    data_volume: str = Field(..., description="数据量（如：2,456设备/156告警）")
    status: str = Field(..., description="状态: 已完成/生成中/失败")


class AIRunReportResponse(BaseModel):
    """AI运行报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID(已保存到数据库)")
    report_title: str = Field(..., description="报告标题")
    report_desc: str = Field(..., description="报告描述")
    scope: str = Field(..., description="报告范围")
    time_range: str = Field(..., description="时间范围")

    # 统计卡片数据
    report_count: int = Field(..., description="报告生成数")
    report_count_change: Optional[str] = Field(None, description="报告生成数环比变化（如：↑ 12 本月）")
    device_count: int = Field(..., description="覆盖设备数量")
    device_count_subtitle: Optional[str] = Field(None, description="覆盖设备副标题")
    device_online_rate: Optional[str] = Field(None, description="设备在线率")
    analysis_dimension: int = Field(..., description="分析维度")
    analysis_dimension_subtitle: Optional[str] = Field(None, description="分析维度副标题")
    report_accuracy: Optional[str] = Field(None, description="报告准确率")
    report_accuracy_change: Optional[str] = Field(None, description="报告准确率环比变化（如：↑ 2.3% 较上月）")

    # 核心指标
    metrics: List[AIMetricItem] = Field(default_factory=list, description="核心指标")
    summary: str = Field(..., description="AI分析总结")
    suggestions: List[str] = Field(default_factory=list, description="优化建议")

    # 详细数据
    device_stats: Dict[str, Any] = Field(default_factory=dict, description="设备统计")
    alarm_stats: Dict[str, Any] = Field(default_factory=dict, description="告警统计")
    device_categories: List[DeviceCategoryItem] = Field(default_factory=list, description="设备类型分布")
    alarm_distribution: List[AlarmDistributionItem] = Field(default_factory=list, description="告警类型分布")
    space_alarm_distribution: List[SpaceAlarmItem] = Field(default_factory=list, description="空间告警分布")

    # 报告列表（底部历史报告表格）
    report_list: List[ReportListItem] = Field(default_factory=list, description="近期报告列表")


# ============ AI预测报告 ============

class AIPredictReportRequest(BaseModel):
    """AI预测报告请求"""
    predict_type: str = Field(..., description="预测类型: energy=能耗预测, device=设备预警, all=全部")
    time_range: TimeRange = Field(..., description="预测时间范围")
    venue_name: Optional[str] = Field(None, description="会展名称(筛选特定会展的数据)")
    device_id: Optional[int] = Field(None, description="设备ID(可选)")
    device_name: Optional[str] = Field(None, description="设备名称(可选)")


class AIPredictItem(BaseModel):
    """预测项"""
    item_name: str = Field(..., description="预测项名称")
    predict_value: str = Field(..., description="预测值")
    confidence: Optional[float] = Field(None, description="置信度(0-1)")
    trend: str = Field(..., description="趋势: up=上升, down=下降, stable=稳定")
    description: Optional[str] = Field(None, description="预测描述")


class AIWarningItem(BaseModel):
    """预警项"""
    device_name: str = Field(..., description="设备名称")
    warning_type: str = Field(..., description="预警类型")
    warning_content: str = Field(..., description="预警内容")
    confidence: Optional[float] = Field(None, description="置信度")
    suggest_time: Optional[str] = Field(None, description="建议处理时间")


class AIPredictReportResponse(BaseModel):
    """AI预测报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID(已保存到数据库)")
    report_title: str = Field(..., description="报告标题")
    predict_items: List[AIPredictItem] = Field(default_factory=list, description="预测项列表")
    warning_items: List[AIWarningItem] = Field(default_factory=list, description="预警项列表")
    summary: str = Field(..., description="AI预测总结")
    suggestions: List[str] = Field(default_factory=list, description="建议")


# ============ AI节能报告 ============

class AIEnergyReportRequest(BaseModel):
    """AI节能报告请求"""
    time_range: TimeRange = Field(..., description="时间范围: week=周, month=月, quarter=季度, year=年")
    venue_name: Optional[str] = Field(None, description="会展名称(筛选特定会展的数据)")
    zone_name: Optional[str] = Field(None, description="分区名称(可选)")


class AIStrategyItem(BaseModel):
    """节能策略项"""
    strategy_name: str = Field(..., description="策略名称")
    implement_date: str = Field(..., description="实施日期")
    before_daily: Optional[str] = Field(None, description="优化前日均")
    after_daily: Optional[str] = Field(None, description="优化后日均")
    daily_saving: Optional[str] = Field(None, description="日节能量")
    saving_rate: Optional[str] = Field(None, description="节能率")
    total_saving: Optional[str] = Field(None, description="累计节约")
    status: str = Field(..., description="状态")


class AIEnergyReportResponse(BaseModel):
    """AI节能报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID(已保存到数据库)")
    report_title: str = Field(..., description="报告标题")
    report_desc: str = Field(..., description="报告描述")
    metrics: List[AIMetricItem] = Field(default_factory=list, description="核心指标")
    strategy_items: List[AIStrategyItem] = Field(default_factory=list, description="策略效果列表")
    summary: str = Field(..., description="AI分析总结")
    suggestions: List[str] = Field(default_factory=list, description="节能建议")


# ============ AI故障分析报告 ============

class AIFaultReportRequest(BaseModel):
    """AI故障分析报告请求"""
    time_range: TimeRange = Field(..., description="时间范围")
    venue_name: Optional[str] = Field(None, description="会展名称(筛选特定会展的数据)")
    device_id: Optional[int] = Field(None, description="设备ID(可选)")
    device_name: Optional[str] = Field(None, description="设备名称(可选)")
    zone_name: Optional[str] = Field(None, description="分区名称(可选)")


class AIFaultDistribution(BaseModel):
    """故障分布"""
    category: Optional[str] = Field(None, description="类别")
    alarm_category_name: Optional[str] = Field(None, description="告警类别(LLM原始字段)")
    count: int = Field(..., description="数量")
    percentage: Optional[float] = Field(None, description="占比")

    @model_validator(mode="before")
    @classmethod
    def _map_alarm_category_name(cls, data):
        if isinstance(data, dict):
            if "alarm_category_name" in data and data.get("alarm_category_name"):
                data["category"] = data["alarm_category_name"]
            elif "alarm_category" in data and data.get("alarm_category"):
                data["category"] = data["alarm_category"]
        return data


class MaintenancePriorityItem(BaseModel):
    """设备维保优先级建议"""
    priority: str = Field(..., description="优先级: 紧急/重要/一般")
    device_name: str = Field(..., description="设备名称")
    location: Optional[str] = Field(None, description="位置")
    fault_count: Optional[str] = Field(None, description="故障频次")
    ai_risk_score: Optional[str] = Field(None, description="AI风险评分")
    suggest_action: Optional[str] = Field(None, description="建议措施")
    suggest_time: Optional[str] = Field(None, description="建议时间")


class AIFaultItem(BaseModel):
    """故障项"""
    device_name: str = Field(..., description="设备名称")
    fault_type: str = Field(..., description="故障类型")
    fault_time: str = Field(..., description="故障时间")
    duration: Optional[str] = Field(None, description="持续时长")
    cause: Optional[str] = Field(None, description="故障原因")
    solution: Optional[str] = Field(None, description="解决方案")


class AIFaultReportResponse(BaseModel):
    """AI故障分析报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID(已保存到数据库)")
    report_title: str = Field(..., description="报告标题")
    report_desc: str = Field(..., description="报告描述")
    metrics: List[AIMetricItem] = Field(default_factory=list, description="核心指标")
    fault_distribution: List[AIFaultDistribution] = Field(default_factory=list, description="故障类型分布")
    fault_items: List[AIFaultItem] = Field(default_factory=list, description="典型故障列表")
    maintenance_priorities: List[MaintenancePriorityItem] = Field(default_factory=list, description="设备维保优先级建议")
    summary: str = Field(..., description="AI分析总结")
    suggestions: List[str] = Field(default_factory=list, description="维保建议")


# ============ AI故障分析报告（拆分接口）============

class AIFaultQueryResponse(BaseModel):
    """AI故障数据查询响应（快速返回，不调用LLM）"""
    query_params: Dict[str, Any] = Field(..., description="查询参数")
    fault_stats: Dict[str, Any] = Field(default_factory=dict, description="故障统计")
    fault_by_category: List[Dict[str, Any]] = Field(default_factory=list, description="故障按类别分布")
    fault_by_level: List[Dict[str, Any]] = Field(default_factory=list, description="故障按级别分布")
    fault_list: List[Dict[str, Any]] = Field(default_factory=list, description="故障列表")
    device_fault_count: List[Dict[str, Any]] = Field(default_factory=list, description="设备故障频次")
    fault_time_distribution: List[Dict[str, Any]] = Field(default_factory=list, description="故障时段分布")
    fault_space_distribution: List[Dict[str, Any]] = Field(default_factory=list, description="故障空间分布")
    fault_device_category: List[Dict[str, Any]] = Field(default_factory=list, description="故障设备类型分布")
    response_rate_stats: Dict[str, Any] = Field(default_factory=dict, description="响应及时率统计")
    complaint_stats: Dict[str, Any] = Field(default_factory=dict, description="投诉建议统计")
    complaint_list: List[Dict[str, Any]] = Field(default_factory=list, description="投诉建议列表")


class AIFaultAnalyzeRequest(BaseModel):
    """AI故障分析请求（调用LLM生成分析报告）

    支持两种传参方式：
    1. 前端自行查询后传入的平铺结构（推荐）
    2. time_range + query_data 嵌套结构（兼容性）
    """
    # 方式1：平铺结构（前端直接传 query_params/fault_stats 等字段）
    query_params: Optional[Dict[str, Any]] = Field(None, description="查询参数（time_range, venue_name, device_id 等）")
    fault_stats: Optional[Dict[str, Any]] = Field(None, description="故障统计")
    fault_by_category: Optional[List[Dict[str, Any]]] = Field(None, description="按类别统计")
    fault_by_level: Optional[List[Dict[str, Any]]] = Field(None, description="按级别统计")
    fault_list: Optional[List[Dict[str, Any]]] = Field(None, description="故障明细列表")
    device_fault_count: Optional[List[Dict[str, Any]]] = Field(None, description="按设备统计TOP10")
    fault_time_distribution: Optional[List[Dict[str, Any]]] = Field(None, description="故障时间分布")
    fault_space_distribution: Optional[List[Dict[str, Any]]] = Field(None, description="故障空间分布")
    fault_device_category: Optional[List[Dict[str, Any]]] = Field(None, description="故障设备类别")
    response_rate_stats: Optional[Dict[str, Any]] = Field(None, description="响应及时率统计")
    complaint_stats: Optional[Dict[str, Any]] = Field(None, description="投诉建议统计")
    complaint_list: Optional[List[Dict[str, Any]]] = Field(None, description="投诉建议列表")
    recent_trends: Optional[Dict[str, Any]] = Field(None, description="近7天趋势")

    # 方式2：time_range 单独 + query_data 嵌套结构（兼容性）
    time_range: Optional[str] = Field(None, description="时间范围（单独传参时）")
    venue_name: Optional[str] = Field(None, description="会展名称")
    device_id: Optional[int] = Field(None, description="设备ID")
    device_name: Optional[str] = Field(None, description="设备名称")
    zone_name: Optional[str] = Field(None, description="分区名称")
    query_data: Optional[Dict[str, Any]] = Field(None, description="查询数据（由 /fault/query 接口返回，嵌套结构）")


# ============ 多模态能碳计算 ============

class AICarbonReportRequest(BaseModel):
    """多模态能碳计算请求"""
    time_range: TimeRange = Field(..., description="时间范围: day=日, week=周, month=月, quarter=季度, year=年")
    venue_name: Optional[str] = Field(None, description="会展名称(筛选特定会展的数据)")
    zone_name: Optional[str] = Field(None, description="分区名称(可选)")


class CarbonSourceItem(BaseModel):
    """碳排放来源项"""
    source: str = Field(..., description="来源类型: 电力/天然气/热力/其他")
    value: float = Field(..., description="排放量(吨CO₂)")
    percentage: float = Field(..., description="占比(%)")


class CarbonTrendItem(BaseModel):
    """碳排放趋势项"""
    month: str = Field(..., description="月份")
    actual: Optional[float] = Field(None, description="实际排放量(吨CO₂)")
    target: Optional[float] = Field(None, description="目标排放量(吨CO₂)")


class AICarbonReportResponse(BaseModel):
    """多模态能碳计算报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID(已保存到数据库)")
    report_title: str = Field(..., description="报告标题")
    report_desc: str = Field(..., description="报告描述")
    
    # 统计卡片数据
    energy_type_count: int = Field(..., description="监测能源类型数量")
    today_carbon: float = Field(..., description="今日碳排放(吨CO₂)")
    today_carbon_change: Optional[float] = Field(None, description="今日碳排放环比变化(%)")
    month_carbon: float = Field(..., description="本月累计碳排放(吨CO₂)")
    month_carbon_change: Optional[float] = Field(None, description="本月碳排放环比变化(%)")
    carbon_intensity: float = Field(..., description="碳强度(kgCO₂/㎡)")
    carbon_intensity_change: Optional[float] = Field(None, description="碳强度环比变化(%)")
    
    # 核心指标
    metrics: List[AIMetricItem] = Field(default_factory=list, description="核心指标")
    
    # 碳排放结构分析
    carbon_sources: List[CarbonSourceItem] = Field(default_factory=list, description="碳排放来源占比")
    
    # 碳排放趋势
    carbon_trends: List[CarbonTrendItem] = Field(default_factory=list, description="碳排放月度趋势")
    
    # 总结和建议
    summary: str = Field(..., description="AI分析总结")
    suggestions: List[str] = Field(default_factory=list, description="碳减排建议")


# ============ 会展信息 ============

class VenueInfo(BaseModel):
    """会展场馆信息"""
    id: int = Field(..., description="场馆ID")
    venue_name: str = Field(..., description="场馆名称")
    location: Optional[str] = Field(None, description="位置")
    orientation: Optional[str] = Field(None, description="朝向")
    area: Optional[str] = Field(None, description="建筑面积")
    floors: Optional[int] = Field(None, description="楼层数")


class VenueListResponse(BaseModel):
    """会展列表响应"""
    items: List[VenueInfo]
    total: int


# ============ AI能源分析报告 ============

class EnergySystemType(str, Enum):
    """能源子系统类型"""
    OVERVIEW = "overview"      # 概览
    AIR_CONDITION = "air_condition"   # 空调机组
    FRESH_AIR = "fresh_air"    # 新风机组
    POWER_DISTRIBUTION = "power_distribution"  # 配电系统
    COLD_SOURCE = "cold_source"  # 冷源系统
    PHOTOVOLTAIC = "photovoltaic"  # 光伏系统
    ALL = "all"  # 全部系统


class EnergyAnalysisRequest(BaseModel):
    """AI能源分析报告请求"""
    system_type: EnergySystemType = Field(..., description="子系统类型: overview/air_condition/fresh_air/power_distribution/cold_source/photovoltaic/all")
    venue_name: Optional[str] = Field(None, description="会展名称(筛选特定会展的数据)")
    time_range: Optional[TimeRange] = Field(TimeRange.DAY, description="时间范围(默认当天)")
    device_name: Optional[str] = Field(None, description="设备名称(可选，筛选特定设备)")


class AirConditionData(BaseModel):
    """空调机组数据"""
    total_count: int = Field(0, description="机组总数")
    running_count: Optional[int] = Field(0, description="运行中数量")
    fault_count: Optional[int] = Field(0, description="故障数量")
    avg_cop: Optional[float] = Field(None, description="平均COP能效比")
    today_energy: Optional[float] = Field(None, description="今日能耗")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="设备列表")


class FreshAirData(BaseModel):
    """新风机组数据"""
    total_count: int = Field(0, description="机组总数")
    running_count: Optional[int] = Field(0, description="运行中数量")
    avg_pm25: Optional[float] = Field(None, description="平均PM2.5")
    today_energy: Optional[float] = Field(None, description="今日耗电")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="设备列表")


class PowerDistributionData(BaseModel):
    """配电系统数据"""
    total_count: int = Field(0, description="配电柜总数")
    running_count: Optional[int] = Field(0, description="正常运行数量")
    today_energy: Optional[float] = Field(None, description="今日用电量")
    power_factor: Optional[float] = Field(None, description="功率因数")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="设备列表")


class ColdSourceData(BaseModel):
    """冷源系统数据"""
    total_count: int = Field(0, description="冷水机组总数")
    running_count: Optional[int] = Field(None, description="运行中数量")
    today_cooling: Optional[float] = Field(None, description="今日制冷量")
    avg_cop: Optional[float] = Field(None, description="平均COP")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="设备列表")


class PhotovoltaicData(BaseModel):
    """光伏系统数据"""
    total_count: int = Field(0, description="光伏组串数")
    installed_capacity: Optional[float] = Field(None, description="装机容量(kW)")
    today_generation: Optional[float] = Field(None, description="今日发电量(kWh)")
    efficiency: Optional[float] = Field(None, description="发电效率")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="设备列表")


class OverviewData(BaseModel):
    """概览数据"""
    subsystem_count: int = Field(0, description="对接子系统数")
    device_online_rate: Optional[str] = Field(None, description="设备在线率/数量")
    remote_control_count: Optional[int] = Field(0, description="远程控制设备")
    today_command_count: Optional[int] = Field(0, description="今日指令下发")
    air_conditions: Optional[AirConditionData] = Field(None, description="空调机组数据")
    fresh_air: Optional[FreshAirData] = Field(None, description="新风机组数据")
    power_distribution: Optional[PowerDistributionData] = Field(None, description="配电系统数据")
    cold_source: Optional[ColdSourceData] = Field(None, description="冷源系统数据")
    photovoltaic: Optional[PhotovoltaicData] = Field(None, description="光伏系统数据")


class EnergyMetricCard(BaseModel):
    """能源指标卡片"""
    value: Any = Field(None, description="数值")
    change: Optional[str] = Field(None, description="变化率")
    unit: Optional[str] = Field(None, description="单位")


class VenueElectricityCompare(BaseModel):
    """各场馆用电对比"""
    categories: List[str] = Field(default_factory=list, description="分类")
    data: Dict[str, List[float]] = Field(default_factory=dict, description="数据")


class EnergyStructureAnalysis(BaseModel):
    """用能结构分析"""
    categories: List[str] = Field(default_factory=list, description="分类")
    data: List[float] = Field(default_factory=list, description="数据")


class MeterRealTimeData(BaseModel):
    """表计实时数据"""
    meter_no: str = Field(..., description="表计编号")
    meter_type: str = Field(..., description="表计类型")
    install_location: str = Field(..., description="安装位置")
    today_reading: float = Field(0, description="今日读数")
    today_usage: float = Field(0, description="今日用量")
    month_total: float = Field(0, description="本月累计")
    status: str = Field(..., description="状态")
    detail_link: Optional[str] = Field(None, description="详情链接")


class MeterDataList(BaseModel):
    """表计实时数据列表"""
    items: List[MeterRealTimeData] = Field(default_factory=list, description="表计列表")
    total: int = Field(0, description="总条数")
    page: int = Field(1, description="当前页")
    page_size: int = Field(10, description="每页条数")
    total_pages: int = Field(1, description="总页数")


class EnergyAnalysisResponse(BaseModel):
    """能源分析报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID")
    report_title: str = Field(..., description="报告标题")
    report_time: str = Field(..., description="报告生成时间")
    system_type: str = Field(..., description="分析的系统类型")
    
    # 核心指标卡片
    meter_total: int = Field(0, description="计费表计总数")
    meter_online_rate: str = Field("0%", description="表计在线率")
    today_electricity: EnergyMetricCard = Field(default_factory=EnergyMetricCard, description="今日用电量")
    today_water: EnergyMetricCard = Field(default_factory=EnergyMetricCard, description="今日用水量")
    
    # 图表数据
    venue_electricity_compare: VenueElectricityCompare = Field(default_factory=VenueElectricityCompare, description="各场馆用电对比")
    energy_structure: EnergyStructureAnalysis = Field(default_factory=EnergyStructureAnalysis, description="用能结构分析")
    
    # 表计实时数据
    meter_data: MeterDataList = Field(default_factory=MeterDataList, description="表计实时数据")
    
    # 原始数据
    overview: Optional[OverviewData] = Field(None, description="概览数据")
    air_condition: Optional[AirConditionData] = Field(None, description="空调机组数据")
    fresh_air: Optional[FreshAirData] = Field(None, description="新风机组数据")
    power_distribution: Optional[PowerDistributionData] = Field(None, description="配电系统数据")
    cold_source: Optional[ColdSourceData] = Field(None, description="冷源系统数据")
    photovoltaic: Optional[PhotovoltaicData] = Field(None, description="光伏系统数据")
    
    # AI分析结果
    summary: str = Field("", description="分析总结")
    suggestions: List[str] = Field(default_factory=list, description="优化建议")
    warnings: List[str] = Field(default_factory=list, description="异常警告")


# ============ AI能源分析报告（拆分接口）============

class EnergyAnalysisQueryResponse(BaseModel):
    """AI能源数据查询响应（快速返回，不调用LLM）"""
    query_params: Dict[str, Any] = Field(..., description="查询参数")
    overview: Dict[str, Any] = Field(default_factory=dict, description="概览数据")
    air_condition: Dict[str, Any] = Field(default_factory=dict, description="空调机组数据")
    fresh_air: Dict[str, Any] = Field(default_factory=dict, description="新风机组数据")
    power_distribution: Dict[str, Any] = Field(default_factory=dict, description="配电系统数据")
    cold_source: Dict[str, Any] = Field(default_factory=dict, description="冷源系统数据")
    photovoltaic: Dict[str, Any] = Field(default_factory=dict, description="光伏系统数据")
    meter_data: Dict[str, Any] = Field(default_factory=dict, description="计费表计数据")
    today_usage: Dict[str, Any] = Field(default_factory=dict, description="今日用水用电量")
    venue_electricity_compare: Dict[str, Any] = Field(default_factory=dict, description="各场馆用电对比")
    energy_structure: Dict[str, Any] = Field(default_factory=dict, description="用能结构分析")


class EnergyAnalysisAnalyzeRequest(BaseModel):
    """AI能源分析请求（调用LLM生成分析报告）

    支持两种传参方式：
    1. 前端自行查询后传入的平铺结构（推荐）
    2. 嵌套结构（兼容性）
    """
    # 方式1：平铺结构（前端直接传）
    query_params: Optional[Dict[str, Any]] = Field(None, description="查询参数")
    overview: Optional[Dict[str, Any]] = Field(None, description="概览数据")
    air_condition: Optional[Dict[str, Any]] = Field(None, description="空调机组数据")
    fresh_air: Optional[Dict[str, Any]] = Field(None, description="新风机组数据")
    power_distribution: Optional[Dict[str, Any]] = Field(None, description="配电系统数据")
    cold_source: Optional[Dict[str, Any]] = Field(None, description="冷源系统数据")
    photovoltaic: Optional[Dict[str, Any]] = Field(None, description="光伏系统数据")
    meter_data: Optional[Dict[str, Any]] = Field(None, description="计费表计数据")
    today_usage: Optional[Dict[str, Any]] = Field(None, description="今日用水用电量")
    venue_electricity_compare: Optional[Dict[str, Any]] = Field(None, description="各场馆用电对比")
    energy_structure: Optional[Dict[str, Any]] = Field(None, description="用能结构分析")

    # 方式2：单独参数
    system_type: Optional[str] = Field(None, description="子系统类型")
    venue_name: Optional[str] = Field(None, description="会展名称")
    time_range: Optional[str] = Field(None, description="时间范围")
    device_name: Optional[str] = Field(None, description="设备名称")
