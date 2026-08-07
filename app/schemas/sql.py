"""SQL 生成相关数据模型"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.chat import ChatMessage


class GenerateSQLRequest(BaseModel):
    """SQL 生成请求"""
    question: str = Field(..., description="用户的问题")
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="历史对话上下文"
    )


class GenerateSQLResponse(BaseModel):
    """SQL 生成响应"""
    sql: str = Field(..., description="生成的 SQL 语句")
    explanation: Optional[str] = Field(
        None,
        description="SQL 说明（如有）"
    )


class GenerateSQLByDeviceRequest(BaseModel):
    """根据设备ID生成SQL请求"""
    device_id: int = Field(..., description="设备ID")
    question: str = Field(
        default="查询该设备的基本信息",
        description="要查询的内容描述，如：'查询该设备的基本信息和运行状态'"
    )


class GenerateSQLByDeviceResponse(BaseModel):
    """根据设备ID生成SQL响应"""
    device_id: int = Field(..., description="设备ID")
    question: str = Field(..., description="原始问题")
    sql: str = Field(..., description="生成的 SQL 语句")
    explanation: Optional[str] = Field(
        None,
        description="SQL 说明（如有）"
    )


class ReportType(str, Enum):
    """报告类型"""
    DEVICE = "device"        # 设备报告
    VENUE = "venue"          # 场馆报告
    EXHIBITION = "exhibition" # 展会报告


class GenerateReportSQLRequest(BaseModel):
    """生成报告SQL请求"""
    report_type: ReportType = Field(
        ...,
        description="报告类型: device=设备报告, venue=场馆报告, exhibition=展会报告"
    )
    target_id: int = Field(..., description="目标ID: 设备ID/场馆ID/展会ID")
    target_name: Optional[str] = Field(None, description="目标名称(可选)")


class ReportMetricItem(BaseModel):
    """报告指标项"""
    name: str = Field(..., description="指标名称")
    sql: str = Field(..., description="对应的SQL语句")
    description: Optional[str] = Field(None, description="指标说明")


class GenerateReportSQLResponse(BaseModel):
    """生成报告SQL响应"""
    report_type: str = Field(..., description="报告类型")
    target_id: int = Field(..., description="目标ID")
    target_name: Optional[str] = Field(None, description="目标名称")
    metrics: List[ReportMetricItem] = Field(
        default_factory=list,
        description="报告指标列表"
    )


class MetricData(BaseModel):
    """单个指标的数据"""
    name: str = Field(..., description="指标名称")
    value: Any = Field(..., description="指标值（可以是数字、字符串或字典）")
    description: Optional[str] = Field(None, description="指标说明")


class GenerateSuggestionsRequest(BaseModel):
    """生成优化建议请求"""
    report_type: ReportType = Field(
        ...,
        description="报告类型: device=设备报告, venue=场馆报告, exhibition=展会报告"
    )
    target_id: int = Field(..., description="目标ID")
    target_name: Optional[str] = Field(None, description="目标名称")
    metrics: List[MetricData] = Field(
        ...,
        description="报告数据指标列表，从SQL查询结果中获取"
    )
    focus_areas: Optional[List[str]] = Field(
        default=None,
        description="关注领域，可选：人员服务/设备能耗/会展数据"
    )


class SuggestionItem(BaseModel):
    """单条优化建议"""
    title: str = Field(..., description="建议标题")
    content: str = Field(..., description="建议内容")
    impact: Optional[str] = Field(None, description="预期效果，如：降低能耗15%")
    category: Optional[str] = Field(None, description="建议类别")


class GenerateSuggestionsResponse(BaseModel):
    """生成优化建议响应"""
    report_type: str = Field(..., description="报告类型")
    target_id: int = Field(..., description="目标ID")
    suggestions: List[SuggestionItem] = Field(
        default_factory=list,
        description="优化建议列表"
    )


class ExecuteSQLRequest(BaseModel):
    """执行SQL查询请求"""
    sql: str = Field(..., description="要执行的SQL语句（只支持SELECT查询）")
    params: Optional[List[Any]] = Field(
        default=None,
        description="SQL参数（可选）"
    )


class ExecuteSQLResponse(BaseModel):
    """执行SQL查询响应"""
    columns: List[str] = Field(..., description="列名列表")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="数据行")
    row_count: int = Field(..., description="返回行数")
    execution_time: float = Field(..., description="执行耗时（秒）")


class MetricDataResult(BaseModel):
    """报告指标数据结果"""
    name: str = Field(..., description="指标名称")
    description: Optional[str] = Field(None, description="指标说明")
    category: Optional[str] = Field(None, description="指标分类：人员服务/设备能耗/会展数据")
    columns: List[str] = Field(default_factory=list, description="列名")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="数据行")
    row_count: int = Field(default=0, description="行数")
    sql: str = Field(..., description="执行的SQL")


class GenerateFullReportRequest(BaseModel):
    """生成完整报告请求（串联：生成SQL → 执行 → 生成建议）"""
    report_type: ReportType = Field(
        ...,
        description="报告类型: device=设备报告, venue=场馆报告, exhibition=展会报告"
    )
    target_id: Optional[int] = Field(None, description="目标ID: 设备ID/场馆ID/展会ID（非必填）")
    target_name: Optional[str] = Field(None, description="目标名称")
    focus_areas: Optional[List[str]] = Field(
        default=None,
        description="关注领域：人员服务/设备能耗/会展数据"
    )


class GenerateFullReportResponse(BaseModel):
    """生成完整报告响应"""
    report_type: str = Field(..., description="报告类型")
    target_id: Optional[int] = Field(None, description="目标ID")
    target_name: Optional[str] = Field(None, description="目标名称")
    data: List[MetricDataResult] = Field(default_factory=list, description="报告数据")
    suggestions: List[SuggestionItem] = Field(default_factory=list, description="优化建议")
