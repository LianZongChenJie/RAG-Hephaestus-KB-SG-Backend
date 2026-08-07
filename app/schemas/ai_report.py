"""AI报告相关数据模型"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class AIRunReportResponse(BaseModel):
    """AI运行报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID(已保存到数据库)")
    report_title: str = Field(..., description="报告标题")
    report_desc: str = Field(..., description="报告描述")
    scope: str = Field(..., description="报告范围")
    time_range: str = Field(..., description="时间范围")
    metrics: List[AIMetricItem] = Field(default_factory=list, description="核心指标")
    summary: str = Field(..., description="AI分析总结")
    suggestions: List[str] = Field(default_factory=list, description="优化建议")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细数据")


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
    confidence: float = Field(..., description="置信度(0-1)")
    trend: str = Field(..., description="趋势: up=上升, down=下降, stable=稳定")
    description: str = Field(..., description="预测描述")


class AIWarningItem(BaseModel):
    """预警项"""
    device_name: str = Field(..., description="设备名称")
    warning_type: str = Field(..., description="预警类型")
    warning_content: str = Field(..., description="预警内容")
    confidence: float = Field(..., description="置信度")
    suggest_time: str = Field(..., description="建议处理时间")


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
    before_daily: str = Field(..., description="优化前日均")
    after_daily: str = Field(..., description="优化后日均")
    daily_saving: str = Field(..., description="日节能量")
    saving_rate: str = Field(..., description="节能率")
    total_saving: str = Field(..., description="累计节约")
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
    category: str = Field(..., description="类别")
    count: int = Field(..., description="数量")
    percentage: float = Field(..., description="占比")


class AIFaultItem(BaseModel):
    """故障项"""
    device_name: str = Field(..., description="设备名称")
    fault_type: str = Field(..., description="故障类型")
    fault_time: str = Field(..., description="故障时间")
    duration: str = Field(..., description="持续时长")
    cause: str = Field(..., description="故障原因")
    solution: str = Field(..., description="解决方案")


class AIFaultReportResponse(BaseModel):
    """AI故障分析报告响应"""
    report_id: Optional[int] = Field(None, description="报告ID(已保存到数据库)")
    report_title: str = Field(..., description="报告标题")
    report_desc: str = Field(..., description="报告描述")
    metrics: List[AIMetricItem] = Field(default_factory=list, description="核心指标")
    fault_distribution: List[AIFaultDistribution] = Field(default_factory=list, description="故障类型分布")
    fault_items: List[AIFaultItem] = Field(default_factory=list, description="典型故障列表")
    summary: str = Field(..., description="AI分析总结")
    suggestions: List[str] = Field(default_factory=list, description="维保建议")


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
