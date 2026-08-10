"""AI报告历史记录 Schema"""
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field


class AIReportHistoryBase(BaseModel):
    """报告基础信息"""
    report_type: str = Field(..., description="报告类型: run/predict/energy/fault")
    title: str = Field(..., description="报告标题")
    time_range: str = Field(..., description="时间范围: day/week/month/quarter/year")
    target_id: Optional[int] = Field(None, description="目标ID")
    target_name: Optional[str] = Field(None, description="目标名称")
    scope: Optional[str] = Field(None, description="范围")


class AIReportHistoryCreate(AIReportHistoryBase):
    """创建报告记录"""
    content: str = Field(..., description="报告内容")
    summary: Optional[str] = Field(None, description="报告摘要")
    query_params: Optional[dict] = Field(None, description="查询参数")
    query_data: Optional[dict] = Field(None, description="原始查询数据")


class AIReportHistoryUpdate(BaseModel):
    """更新报告记录"""
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None


class AIReportHistoryResponse(AIReportHistoryBase):
    """报告响应"""
    id: int
    content: str
    summary: Optional[str] = None
    query_params: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AIReportHistoryListItem(BaseModel):
    """报告列表项（不含完整内容）"""
    id: int
    report_type: str
    title: str
    time_range: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    scope: Optional[str] = None
    summary: Optional[str] = None
    data_volume: str = Field(..., description="数据量（如：12设备/8告警）")
    status: str = Field(..., description="状态: 已完成/生成中/失败")
    created_at: datetime

    class Config:
        from_attributes = True


class AIReportHistoryListResponse(BaseModel):
    """报告列表响应"""
    items: List[AIReportHistoryListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class AIReportStatsResponse(BaseModel):
    """报告统计响应"""
    total_count: int = Field(..., description="报告总数")
    by_type: dict = Field(..., description="按类型统计")
    by_time_range: dict = Field(..., description="按时长范围统计")
    recent_count: int = Field(..., description="最近7天报告数")
