"""AI报告接口"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.schemas.ai_report import (
    AIRunReportRequest,
    AIRunReportResponse,
    AIPredictReportRequest,
    AIPredictReportResponse,
    AIEnergyReportRequest,
    AIEnergyReportResponse,
    AIFaultReportRequest,
    AIFaultReportResponse,
    AICarbonReportRequest,
    AICarbonReportResponse,
    VenueListResponse,
)
from app.services.ai_report_service import AIReportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-report", tags=["AI报告"])


@router.post("/run", response_model=AIRunReportResponse)
async def generate_ai_run_report(body: AIRunReportRequest) -> AIRunReportResponse:
    """
    AI运行报告

    基于AI对设备运行数据、告警数据、能耗数据进行深度分析，生成运行报告。

    **报告范围**：
    - all: 全园区整体报告
    - zone: 分区报告（需指定 zone_name）
    - device: 单台设备报告（需指定 device_id 或 device_name）

    **时间范围**：
    - day: 日报
    - week: 周报
    - month: 月报
    - quarter: 季度报告
    - year: 年度报告

    **会展名称**：
    - 可选参数，指定后只统计该会展的数据

    示例请求：
    ```json
    {
        "scope": "all",
        "time_range": "week",
        "venue_name": "1号馆"
    }
    ```
    """
    try:
        service = AIReportService()

        # 生成报告
        report = await service.generate_run_report(
            scope=body.scope.value,
            time_range=body.time_range.value,
            venue_name=body.venue_name,
            zone_name=body.zone_name,
            device_id=body.device_id,
            device_name=body.device_name,
        )

        return AIRunReportResponse(**report)

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用",
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama 响应超时，请稍后重试",
        )
    except Exception as exc:
        logger.exception("AI运行报告生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"AI运行报告生成失败: {str(exc)}",
        )


@router.post("/predict", response_model=AIPredictReportResponse)
async def generate_ai_predict_report(body: AIPredictReportRequest) -> AIPredictReportResponse:
    """
    AI预测报告

    基于AI时序分析模型，预测设备能耗趋势和关键参数变化，提前识别潜在风险。

    **预测类型**：
    - energy: 能耗趋势预测
    - device: 设备运行参数预警
    - all: 综合预测分析

    **时间范围**：
    - day: 未来1天
    - week: 未来7天
    - month: 未来30天
    - quarter: 未来90天

    **会展名称**：
    - 可选参数，指定后只统计该会展的数据

    示例请求：
    ```json
    {
        "predict_type": "all",
        "time_range": "week",
        "venue_name": "1号馆"
    }
    ```
    """
    try:
        service = AIReportService()

        report = await service.generate_predict_report(
            predict_type=body.predict_type,
            time_range=body.time_range.value,
            venue_name=body.venue_name,
            device_id=body.device_id,
            device_name=body.device_name,
        )

        return AIPredictReportResponse(**report)

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用",
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama 响应超时，请稍后重试",
        )
    except Exception as exc:
        logger.exception("AI预测报告生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"AI预测报告生成失败: {str(exc)}",
        )


@router.post("/energy", response_model=AIEnergyReportResponse)
async def generate_ai_energy_report(body: AIEnergyReportRequest) -> AIEnergyReportResponse:
    """
    AI节能报告

    基于AI分析用能数据，对比优化策略实施前后的能耗变化，量化节能效果。

    **时间范围**：
    - week: 周报
    - month: 月报
    - quarter: 季度报告
    - year: 年度报告

    **会展名称**：
    - 可选参数，指定后只统计该会展的数据

    示例请求：
    ```json
    {
        "time_range": "quarter",
        "venue_name": "1号馆"
    }
    ```
    """
    try:
        service = AIReportService()

        report = await service.generate_energy_report(
            time_range=body.time_range.value,
            venue_name=body.venue_name,
            zone_name=body.zone_name,
        )

        return AIEnergyReportResponse(**report)

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用",
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama 响应超时，请稍后重试",
        )
    except Exception as exc:
        logger.exception("AI节能报告生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"AI节能报告生成失败: {str(exc)}",
        )


@router.post("/fault", response_model=AIFaultReportResponse)
async def generate_ai_fault_report(body: AIFaultReportRequest) -> AIFaultReportResponse:
    """
    AI故障分析报告

    基于AI分析设备故障数据，识别故障根因与潜在规律，提供维保建议。

    **时间范围**：
    - day: 日报
    - week: 周报
    - month: 月报
    - quarter: 季度报告
    - year: 年度报告

    **会展名称**：
    - 可选参数，指定后只统计该会展的数据

    示例请求：
    ```json
    {
        "time_range": "month",
        "venue_name": "1号馆"
    }
    ```
    """
    try:
        service = AIReportService()

        report = await service.generate_fault_report(
            time_range=body.time_range.value,
            venue_name=body.venue_name,
            device_id=body.device_id,
            device_name=body.device_name,
            zone_name=body.zone_name,
        )

        return AIFaultReportResponse(**report)

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用",
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama 响应超时，请稍后重试",
        )
    except Exception as exc:
        logger.exception("AI故障分析报告生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"AI故障分析报告生成失败: {str(exc)}",
        )


@router.post("/carbon", response_model=AICarbonReportResponse)
async def generate_ai_carbon_report(body: AICarbonReportRequest) -> AICarbonReportResponse:
    """
    多模态能碳计算报告

    基于AI对电、水、气、热四类能源的实时计量数据进行分析，融合物理机理模型与机器学习算法，
    对园区能碳排放进行多维度精准核算。

    **时间范围**：
    - day: 日报
    - week: 周报
    - month: 月报
    - quarter: 季度报告
    - year: 年度报告

    **会展名称**：
    - 可选参数，指定后只统计该会展的数据

    示例请求：
    ```json
    {
        "time_range": "month",
        "venue_name": "1号馆"
    }
    ```
    """
    try:
        service = AIReportService()

        report = await service.generate_carbon_report(
            time_range=body.time_range.value,
            venue_name=body.venue_name,
            zone_name=body.zone_name,
        )

        return AICarbonReportResponse(**report)

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用",
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama 响应超时，请稍后重试",
        )
    except Exception as exc:
        logger.exception("多模态能碳计算报告生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"多模态能碳计算报告生成失败: {str(exc)}",
        )


# ==================== 会展信息接口 ====================

@router.get("/venues", response_model=VenueListResponse)
async def list_venues() -> VenueListResponse:
    """
    获取会展列表

    返回所有可用的会展场馆信息，用于报告筛选
    """
    try:
        venues = AIReportService.list_venues()
        return VenueListResponse(
            items=venues,
            total=len(venues)
        )
    except Exception as exc:
        logger.exception("获取会展列表失败")
        raise HTTPException(
            status_code=500,
            detail=f"获取会展列表失败: {str(exc)}",
        )


# ==================== 报告历史查询接口 ====================

from app.schemas.ai_report_history import (
    AIReportHistoryListResponse,
    AIReportHistoryResponse,
    AIReportStatsResponse,
)
from app.services.ai_report_history_service import AIReportHistoryService
from fastapi import Query


@router.get("/history", response_model=AIReportHistoryListResponse)
async def list_ai_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    report_type: str = Query(None, description="报告类型: run/predict/energy/fault"),
    time_range: str = Query(None, description="时间范围: day/week/month/quarter/year"),
    target_name: str = Query(None, description="目标名称搜索"),
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
) -> AIReportHistoryListResponse:
    """
    查询AI报告历史列表

    支持分页、筛选和搜索
    """
    try:
        items, total = AIReportHistoryService.list_reports(
            page=page,
            page_size=page_size,
            report_type=report_type,
            time_range=time_range,
            target_name=target_name,
            start_date=start_date,
            end_date=end_date,
        )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return AIReportHistoryListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as exc:
        logger.exception("查询报告列表失败")
        raise HTTPException(
            status_code=500,
            detail=f"查询报告列表失败: {str(exc)}",
        )


@router.get("/history/{report_id}", response_model=AIReportHistoryResponse)
async def get_ai_report(report_id: int) -> AIReportHistoryResponse:
    """
    获取AI报告详情

    根据报告ID获取完整的报告内容
    """
    try:
        report = AIReportHistoryService.get_report_by_id(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="报告不存在")

        return AIReportHistoryResponse(**report)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("获取报告详情失败")
        raise HTTPException(
            status_code=500,
            detail=f"获取报告详情失败: {str(exc)}",
        )


@router.get("/stats", response_model=AIReportStatsResponse)
async def get_ai_report_stats() -> AIReportStatsResponse:
    """
    获取AI报告统计

    返回报告总数、按类型统计、按时间范围统计等信息
    """
    try:
        stats = AIReportHistoryService.get_stats()
        return AIReportStatsResponse(**stats)
    except Exception as exc:
        logger.exception("获取报告统计失败")
        raise HTTPException(
            status_code=500,
            detail=f"获取报告统计失败: {str(exc)}",
        )


@router.delete("/history/{report_id}")
async def delete_ai_report(report_id: int) -> dict:
    """
    删除AI报告

    根据报告ID删除指定报告
    """
    try:
        success = AIReportHistoryService.delete_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail="报告不存在或删除失败")

        return {"message": "报告删除成功", "id": report_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("删除报告失败")
        raise HTTPException(
            status_code=500,
            detail=f"删除报告失败: {str(exc)}",
        )
