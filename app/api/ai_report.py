"""AI报告接口"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.middlewares.access_log import inject_response
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
    EnergyAnalysisRequest,
    EnergyAnalysisResponse,
    AIFaultQueryResponse,
    AIFaultAnalyzeRequest,
    EnergyAnalysisQueryResponse,
    EnergyAnalysisAnalyzeRequest,
)
from app.services.ai_report_service import AIReportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-report", tags=["AI报告"])


@router.post("/run", response_model=AIRunReportResponse)
async def generate_ai_run_report(request: Request, body: AIRunReportRequest) -> AIRunReportResponse:
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

        resp = AIRunReportResponse(**report)
        inject_response(request, resp.model_dump())
        return resp

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
    AI故障分析报告（便捷模式）

    基于AI分析设备故障数据，识别故障根因与潜在规律，提供维保建议。
    **此接口会依次执行：查询数据 → 调用LLM分析，预计耗时20-30秒。**

    如需更快响应（<1秒），请使用拆分接口：
    - POST /api/ai-report/fault/query（快速返回数据）
    - POST /api/ai-report/fault/analyze（LLM分析）

    **时间范围**：day/week/month/quarter/year
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
        raise HTTPException(status_code=503, detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Ollama 响应超时，请稍后重试")
    except Exception as exc:
        logger.exception("AI故障分析报告生成失败")
        raise HTTPException(status_code=500, detail=f"AI故障分析报告生成失败: {str(exc)}")


@router.post("/fault/query", response_model=AIFaultQueryResponse)
async def query_fault_data(body: AIFaultReportRequest) -> AIFaultQueryResponse:
    """
    AI故障数据查询（快速模式）

    仅查询故障相关数据，不调用LLM分析。**预计耗时 <1秒**。

    前端可先调用此接口快速展示数据，再决定是否调用 /fault/analyze 接口触发AI分析。

    **时间范围**：day/week/month/quarter/year
    """
    try:
        service = AIReportService()
        query_data = await service.query_fault_data(
            time_range=body.time_range.value,
            venue_name=body.venue_name,
            device_id=body.device_id,
            device_name=body.device_name,
            zone_name=body.zone_name,
        )
        return AIFaultQueryResponse(**query_data)

    except Exception as exc:
        logger.exception("查询故障数据失败")
        raise HTTPException(status_code=500, detail=f"查询故障数据失败: {str(exc)}")


@router.post("/fault/analyze", response_model=AIFaultReportResponse)
async def analyze_fault_report(body: AIFaultAnalyzeRequest) -> AIFaultReportResponse:
    """
    AI故障分析（LLM推理模式）

    基于 /fault/query 接口返回的数据，调用LLM生成分析报告。**预计耗时 20-30秒**。

    **支持两种传参方式**：
    1. 前端平铺结构（query_params/fault_stats 等作为顶层字段）
    2. 嵌套结构（time_range + query_data）

    示例请求（平铺结构，推荐）：
    ```json
    {
        "query_params": {
            "time_range": "month",
            "venue_name": "演唱会",
            "start_date": "2026-07-12",
            "end_date": "2026-08-11"
        },
        "fault_stats": { "total_faults": 13580, "affected_devices": 19 },
        "fault_by_category": [...],
        "fault_by_level": [...],
        "fault_list": [...]
    }
    ```
    """
    try:
        service = AIReportService()

        # 判断传入格式：平铺结构 vs 嵌套结构
        if body.query_params is not None:
            # 方式1：前端平铺结构
            time_range = body.query_params.get("time_range") or body.time_range or "month"
            venue_name = body.query_params.get("venue_name") or body.venue_name
            device_id = body.query_params.get("device_id") or body.device_id
            device_name = body.query_params.get("device_name") or body.device_name
            zone_name = body.query_params.get("zone_name") or body.zone_name
            # 构建 query_data 供 service 使用
            query_data = {
                "query_params": body.query_params,
                "fault_stats": body.fault_stats or {},
                "fault_by_category": body.fault_by_category or [],
                "fault_by_level": body.fault_by_level or [],
                "fault_list": body.fault_list or [],
                "device_fault_count": body.device_fault_count or [],
                "fault_time_distribution": body.fault_time_distribution or [],
                "fault_space_distribution": body.fault_space_distribution or [],
                "fault_device_category": body.fault_device_category or [],
                "response_rate_stats": body.response_rate_stats or {},
                "complaint_stats": body.complaint_stats or {},
                "complaint_list": body.complaint_list or [],
                "recent_trends": body.recent_trends or {},
            }
        else:
            # 方式2：嵌套结构（兼容性）
            time_range = body.time_range or "month"
            venue_name = body.venue_name
            device_id = body.device_id
            device_name = body.device_name
            zone_name = body.zone_name
            query_data = body.query_data or {}

        report = await service.analyze_fault_data(
            time_range=time_range,
            query_data=query_data,
            venue_name=venue_name,
            device_id=device_id,
            device_name=device_name,
            zone_name=zone_name,
        )
        return AIFaultReportResponse(**report)

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Ollama 响应超时，请稍后重试")
    except Exception as exc:
        logger.exception("AI故障分析失败")
        raise HTTPException(status_code=500, detail=f"AI故障分析失败: {str(exc)}")


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
async def list_venues(request: Request) -> VenueListResponse:
    """
    获取会展列表

    返回所有可用的会展场馆信息，用于报告筛选
    """
    try:
        venues = AIReportService.list_venues()
        resp = VenueListResponse(items=venues, total=len(venues))
        inject_response(request, resp.model_dump())
        return resp
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
    request: Request,
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

        resp = AIReportHistoryListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
        inject_response(request, resp.model_dump())
        return resp
    except Exception as exc:
        logger.exception("查询报告列表失败")
        raise HTTPException(
            status_code=500,
            detail=f"查询报告列表失败: {str(exc)}",
        )


@router.get("/history/{report_id}", response_model=AIReportHistoryResponse)
async def get_ai_report(request: Request, report_id: int) -> AIReportHistoryResponse:
    """
    获取AI报告详情

    根据报告ID获取完整的报告内容
    """
    try:
        report = AIReportHistoryService.get_report_by_id(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="报告不存在")

        resp = AIReportHistoryResponse(**report)
        inject_response(request, resp.model_dump())
        return resp
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("获取报告详情失败")
        raise HTTPException(
            status_code=500,
            detail=f"获取报告详情失败: {str(exc)}",
        )


@router.get("/stats", response_model=AIReportStatsResponse)
async def get_ai_report_stats(request: Request) -> AIReportStatsResponse:
    """
    获取AI报告统计

    返回报告总数、按类型统计、按时间范围统计等信息
    """
    try:
        stats = AIReportHistoryService.get_stats()
        resp = AIReportStatsResponse(**stats)
        inject_response(request, resp.model_dump())
        return resp
    except Exception as exc:
        logger.exception("获取报告统计失败")
        raise HTTPException(
            status_code=500,
            detail=f"获取报告统计失败: {str(exc)}",
        )


@router.delete("/history/{report_id}")
async def delete_ai_report(request: Request, report_id: int) -> dict:
    """
    删除AI报告

    根据报告ID删除指定报告
    """
    try:
        success = AIReportHistoryService.delete_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail="报告不存在或删除失败")

        resp = {"message": "报告删除成功", "id": report_id}
        inject_response(request, resp)
        return resp
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("删除报告失败")
        raise HTTPException(
            status_code=500,
            detail=f"删除报告失败: {str(exc)}",
        )


# ==================== AI能源分析报告接口 ====================

@router.post("/energy-analysis", response_model=EnergyAnalysisResponse)
async def generate_energy_analysis_report(request: Request, body: EnergyAnalysisRequest) -> EnergyAnalysisResponse:
    """
    AI能源分析报告（便捷模式）

    基于实时数据对能源系统（空调机组、新风机组、配�系统、冷源系统、光伏系统）进行综合分析，
    生成包含分析总结、优化建议和异常警告的报告。
    **此接口会依次执行：查询数据 → 调用LLM分析，预计耗时 20-30秒。**

    如需更快响应（<1秒），请使用拆分接口：
    - POST /api/ai-report/energy-analysis/query（快速返回数据）
    - POST /api/ai-report/energy-analysis/analyze（LLM分析）

    **子系统类型**：overview/air_condition/fresh_air/power_distribution/cold_source/photovoltaic/all
    """
    try:
        service = AIReportService()

        report = await service.generate_energy_analysis_report(
            system_type=body.system_type.value,
            venue_name=body.venue_name,
            time_range=body.time_range.value if body.time_range else "day",
            device_name=body.device_name,
        )

        resp = EnergyAnalysisResponse(**report)
        inject_response(request, resp.model_dump())
        return resp

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
        logger.exception("AI能源分析报告生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"AI能源分析报告生成失败: {str(exc)}",
        )


@router.post("/energy-analysis/query", response_model=EnergyAnalysisQueryResponse)
async def query_energy_data(body: EnergyAnalysisRequest) -> EnergyAnalysisQueryResponse:
    """
    AI能源数据查询（快速模式）

    仅查询能源系统数据，不调用LLM分析。**预计耗时 <1秒**。

    前端可先调用此接口快速展示数据，再决定是否调用 /energy-analysis/analyze 接口触发AI分析。
    """
    try:
        service = AIReportService()
        query_data = await service.query_energy_data(
            system_type=body.system_type.value,
            venue_name=body.venue_name,
            time_range=body.time_range.value if body.time_range else "day",
            device_name=body.device_name,
        )
        return EnergyAnalysisQueryResponse(**query_data)
    except Exception as exc:
        logger.exception("查询能源数据失败")
        raise HTTPException(status_code=500, detail=f"查询能源数据失败: {str(exc)}")


@router.post("/energy-analysis/analyze", response_model=EnergyAnalysisResponse)
async def analyze_energy_report(body: EnergyAnalysisAnalyzeRequest) -> EnergyAnalysisResponse:
    """
    AI能源分析（LLM推理模式）

    基于 /energy-analysis/query 接口返回的数据，调用LLM生成分析报告。**预计耗时 20-30秒**。

    **支持两种传参方式**：
    1. 前端平铺结构（overview/air_condition 等作为顶层字段）
    2. 嵌套结构（兼容性）
    """
    try:
        service = AIReportService()

        # 判断传入格式：平铺结构 vs 嵌套结构
        if body.overview is not None or body.query_params is not None:
            # 方式1：前端平铺结构
            system_type = body.query_params.get("system_type") if body.query_params else body.system_type or "overview"
            venue_name = body.query_params.get("venue_name") if body.query_params else body.venue_name
            # 修复：如果 time_range 为 None 或空，使用默认值 "month"
            time_range = (body.query_params.get("time_range") if body.query_params else None) or body.time_range or "month"
            device_name = body.query_params.get("device_name") if body.query_params else body.device_name
            # 确保 query_params 中的 time_range 有值（避免保存到数据库时为 null）
            safe_query_params = body.query_params.copy() if body.query_params else {}
            if not safe_query_params.get("time_range"):
                safe_query_params["time_range"] = time_range
            
            query_data = {
                "query_params": safe_query_params,
                "overview": body.overview or {},
                "air_condition": body.air_condition or {},
                "fresh_air": body.fresh_air or {},
                "power_distribution": body.power_distribution or {},
                "cold_source": body.cold_source or {},
                "photovoltaic": body.photovoltaic or {},
                "meter_data": body.meter_data or {},
                "today_usage": body.today_usage or {},
                "venue_electricity_compare": body.venue_electricity_compare or {},
                "energy_structure": body.energy_structure or {},
            }
        else:
            # 方式2：嵌套结构（兼容性）
            system_type = body.system_type or "overview"
            venue_name = body.venue_name
            time_range = body.time_range or "month"
            device_name = body.device_name
            query_data = {}

        report = await service.analyze_energy_data(
            system_type=system_type,
            query_data=query_data,
            venue_name=venue_name,
            time_range=time_range,
            device_name=device_name,
        )
        return EnergyAnalysisResponse(**report)

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Ollama 响应超时，请稍后重试")
    except Exception as exc:
        logger.exception("AI能源分析失败")
        raise HTTPException(status_code=500, detail=f"AI能源分析失败: {str(exc)}")


@router.get("/energy-analysis/systems")
async def list_energy_systems(request: Request) -> dict:
    """
    获取能源系统列表

    返回所有可用的能源子系统类型
    """
    systems = [
        {"code": "overview", "name": "全系统概览", "icon": "dashboard"},
        {"code": "air_condition", "name": "空调机组", "icon": "ac"},
        {"code": "fresh_air", "name": "新风机组", "icon": "wind"},
        {"code": "power_distribution", "name": "配电系统", "icon": "electricity"},
        {"code": "cold_source", "name": "冷源系统", "icon": "snowflake"},
        {"code": "photovoltaic", "name": "光伏系统", "icon": "sun"},
        {"code": "all", "name": "全部系统", "icon": "all"},
    ]
    return {"items": systems, "total": len(systems)}
