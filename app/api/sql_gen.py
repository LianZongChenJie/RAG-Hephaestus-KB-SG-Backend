"""SQL 生成接口"""
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.schemas.sql import (
    ExecuteSQLRequest,
    ExecuteSQLResponse,
    GenerateFullReportRequest,
    GenerateFullReportResponse,
    GenerateReportSQLRequest,
    GenerateReportSQLResponse,
    GenerateSQLByDeviceRequest,
    GenerateSQLByDeviceResponse,
    GenerateSQLRequest,
    GenerateSQLResponse,
    GenerateSuggestionsRequest,
    GenerateSuggestionsResponse,
    MetricDataResult,
    ReportMetricItem,
    SuggestionItem,
)
from app.core.dameng import execute_query
from app.services.sql_service import SQLService, SuggestionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["SQL 生成"])


@router.post("/generate-sql", response_model=GenerateSQLResponse)
async def generate_sql(body: GenerateSQLRequest) -> GenerateSQLResponse:
    """
    根据用户问题和历史上下文，调用大模型生成 SQL 语句。

    - 读取 config/query.json 获取数据库表结构
    - 结合历史对话理解上下文
    - 返回生成的 SQL 及其说明
    """
    try:
        sql_service = SQLService()
        sql, explanation = await sql_service.generate_sql(
            body.question,
            body.history,
        )

        return GenerateSQLResponse(
            sql=sql,
            explanation=explanation,
        )

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
        logger.exception("SQL 生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"SQL 生成失败: {str(exc)}",
        )


@router.post("/device/sql", response_model=GenerateSQLByDeviceResponse)
async def generate_sql_by_device(body: GenerateSQLByDeviceRequest) -> GenerateSQLByDeviceResponse:
    """
    根据设备ID生成 SQL 查询语句。

    前端传入设备ID，系统调用大模型根据该设备ID和query.json表结构，
    生成获取设备相关数据的SQL。

    示例请求：
    ```json
    {
        "device_id": 123,
        "question": "查询该设备的基本信息、告警记录和能耗数据"
    }
    ```

    返回：
    - device_id: 设备ID
    - question: 原始问题
    - sql: 生成的SQL语句
    - explanation: SQL说明（可选）
    """
    try:
        sql_service = SQLService()
        sql, explanation = await sql_service.generate_sql_by_device(
            device_id=body.device_id,
            question=body.question,
        )

        if not sql:
            raise HTTPException(
                status_code=400,
                detail="大模型未能生成有效的SQL语句，请尝试简化问题描述",
            )

        return GenerateSQLByDeviceResponse(
            device_id=body.device_id,
            question=body.question,
            sql=sql,
            explanation=explanation,
        )

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
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("设备SQL生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"设备SQL生成失败: {str(exc)}",
        )


@router.post("/generate-report-sql", response_model=GenerateReportSQLResponse)
async def generate_report_sql(body: GenerateReportSQLRequest) -> GenerateReportSQLResponse:
    """
    根据报告类型和目标ID，生成包含所有指标的SQL列表。

    用于前端获取设备/场馆/展会的完整报告数据。

    - device: 设备报告 (需要 device_id)
    - venue: 场馆报告 (需要 venue_id)
    - exhibition: 展会报告 (需要 exhibition_id)

    返回每个指标对应的SQL语句，前端可并行执行这些SQL获取数据。
    """
    try:
        sql_service = SQLService()

        # 获取指标定义
        metrics_def = await sql_service.generate_report_sql(
            report_type=body.report_type.value,
            target_id=body.target_id,
            target_name=body.target_name,
        )

        # 构建指标SQL列表
        metrics: List[ReportMetricItem] = []
        for metric in metrics_def:
            # 优先使用自定义 SQL，否则动态构建
            if "sql" in metric and "{" in metric["sql"]:
                sql = metric["sql"].replace("{exhibition_id}", str(body.target_id))
                sql = sql.replace("{target_id}", str(body.target_id))
                sql = sql.replace("{exhibition_name}", f"'{body.target_name or ''}'")
            else:
                sql = _build_metric_sql(metric, body.target_id, body.target_name)
            metrics.append(ReportMetricItem(
                name=metric["name"],
                sql=sql,
                description=metric.get("description"),
            ))

        return GenerateReportSQLResponse(
            report_type=body.report_type.value,
            target_id=body.target_id,
            target_name=body.target_name,
            metrics=metrics,
        )

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
        logger.exception("报告SQL生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"报告SQL生成失败: {str(exc)}",
        )


def _build_metric_sql(metric: Dict[str, Any], target_id: Optional[int], target_name: Optional[str] = None) -> str:
    """根据指标定义构建SQL（达梦语法：表名加"", 列名加""）"""
    # 有自定义 sql 的指标跳过
    if "sql" in metric:
        sql = metric["sql"]
        # 替换占位符
        if target_name:
            sql = sql.replace("{exhibition_name}", f"'{target_name}'")
            sql = sql.replace("{target_name}", f"'{target_name}'")
        if target_id:
            sql = sql.replace("{exhibition_id}", str(target_id))
            sql = sql.replace("{target_id}", str(target_id))
        return sql

    table = metric["table"]
    aggregate = metric.get("aggregate")
    aggregate_field = metric.get("aggregate_field")
    filter_field = metric.get("filter_field")
    filter_value = metric.get("filter_value")
    filter_value_from_exhibition = metric.get("filter_value_from_exhibition")
    filter_value_from_config = metric.get("filter_value_from_config")
    filter_value_from_name = metric.get("filter_value_from_name")
    date_field = metric.get("date_field")
    date_start_from_exhibition = metric.get("date_start_from_exhibition")
    date_end_from_exhibition = metric.get("date_end_from_exhibition")
    date_end_from_max = metric.get("date_end_from_max")
    where_extra = metric.get("where_extra")
    distinct = metric.get("distinct", False)
    join_table = metric.get("join_table")
    join_on = metric.get("join_on")
    filter_name = metric.get("filter_name")  # 按会展名称过滤，值为字段名如 "active_name"

    # 根据是否有 JOIN 决定列名前缀
    prefix = "t1." if join_table else ""

    # 构建 SELECT 子句
    if aggregate and aggregate_field:
        agg_func = aggregate.upper()
        if agg_func == "DATEDIFF":
            select_clause = f'DATEDIFF(DAY, MIN("{aggregate_field}"), CURRENT_DATE) as result'
        elif distinct:
            select_clause = f'COUNT(DISTINCT "{aggregate_field}") as result'
        else:
            select_clause = f'{agg_func}("{aggregate_field}") as result'
    else:
        select_clause = "*"

    # 构建 FROM 子句
    if join_table and join_on:
        # 替换 join_on 中的占位符
        resolved_join_on = join_on
        if target_name:
            resolved_join_on = resolved_join_on.replace("{target_name}", f"'{target_name}'")
        if target_id:
            resolved_join_on = resolved_join_on.replace("{target_id}", str(target_id))
        from_clause = f'FWBZ."{table}" t1 JOIN FWBZ."{join_table}" t2 ON {resolved_join_on}'
    else:
        from_clause = f'FWBZ."{table}"'

    # 构建 WHERE 条件
    conditions = []

    # 添加过滤条件
    if filter_field:
        col = f'{prefix}"{filter_field}"'
        if filter_value_from_exhibition:
            # 通过展会名称或ID获取关联字段
            if target_name:
                conditions.append(
                    f'{col} = ('
                    f'SELECT "{filter_value_from_exhibition}" '
                    f'FROM FWBZ."table_activeMeet_info" '
                    f'WHERE "active_name" = \'{target_name}\')'
                )
            elif target_id:
                conditions.append(
                    f'{col} = ('
                    f'SELECT "{filter_value_from_exhibition}" '
                    f'FROM FWBZ."table_activeMeet_info" '
                    f'WHERE "id" = {target_id})'
                )
        elif filter_value_from_name:
            # 通过名称获取关联 ID
            if target_name:
                conditions.append(
                    f'{col} IN ('
                    f'SELECT "{filter_value_from_name}" '
                    f'FROM FWBZ."{join_table or filter_field.replace("_id", "_info")}" '
                    f'WHERE "device_name" = \'{target_name}\' OR "venue_name" = \'{target_name}\')'
                )
        elif filter_value_from_config:
            conditions.append(
                f'{col} = ('
                f'SELECT "config_value" '
                f'FROM FWBZ."business_config" '
                f'WHERE "config_key" = \'{filter_value_from_config}\')'
            )
        elif filter_value is not None:
            if isinstance(filter_value, str) and "%" in filter_value:
                conditions.append(f'{col} LIKE \'{filter_value}\'')
            elif target_id:
                conditions.append(f'{col} = {filter_value}')
            else:
                conditions.append(f'{col} = \'{filter_value}\'')

    # 添加日期过滤
    if date_field and (target_id or target_name):
        date_col = f'{prefix}"{date_field}"'
        # 构建会展表过滤条件（优先使用名称）
        if target_name:
            meet_filter = f'"{filter_name or "active_name"}" = \'{target_name}\''
        elif target_id:
            meet_filter = f'"id" = {target_id}'
        else:
            meet_filter = None

        if date_start_from_exhibition and meet_filter:
            conditions.append(
                f'{date_col} >= ('
                f'SELECT MIN("{date_start_from_exhibition}") '
                f'FROM FWBZ."table_activeMeet_info" '
                f'WHERE {meet_filter})'
            )
        elif aggregate != "DATEDIFF" and meet_filter:
            conditions.append(
                f'{date_col} >= ('
                f'SELECT MIN("start_date") '
                f'FROM FWBZ."table_activeMeet_info" '
                f'WHERE {meet_filter})'
            )

        if date_end_from_exhibition and meet_filter:
            conditions.append(
                f'{date_col} <= ('
                f'SELECT MAX("{date_end_from_exhibition}") '
                f'FROM FWBZ."table_activeMeet_info" '
                f'WHERE {meet_filter})'
            )
        elif date_end_from_max:
            end_col = f'{prefix}"{date_end_from_max}"'
            sub_col = f'{prefix}"{filter_field}"' if filter_field else '1'
            if filter_value_from_exhibition and filter_field and meet_filter:
                sub_filter = f'{sub_col} = (SELECT "{filter_value_from_exhibition}" FROM FWBZ."table_activeMeet_info" WHERE {meet_filter})'
            elif filter_value is not None and filter_field:
                sub_filter = f'{sub_col} = \'{filter_value}\''
            else:
                sub_filter = '1=1'
            conditions.append(
                f'{date_col} <= ('
                f'SELECT MAX("{date_end_from_max}") '
                f'FROM FWBZ."{table}" '
                f'WHERE {sub_filter})'
            )

    # 添加额外条件
    if where_extra:
        extra = where_extra
        if target_name:
            extra = extra.replace("{exhibition_name}", f"'{target_name}'")
            extra = extra.replace("{target_name}", f"'{target_name}'")
        if target_id:
            extra = extra.replace("{exhibition_id}", str(target_id))
            extra = extra.replace("{target_id}", str(target_id))
        conditions.append(extra)

    # 组装 SQL
    sql = f"SELECT {select_clause} FROM {from_clause}"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " LIMIT 1"
    return sql


@router.post("/generate-suggestions", response_model=GenerateSuggestionsResponse)
async def generate_suggestions(body: GenerateSuggestionsRequest) -> GenerateSuggestionsResponse:
    """
    根据报告数据调用大模型生成优化建议。

    前端流程：
    1. 调用 /api/generate-report-sql 获取报告SQL列表
    2. 执行这些SQL获取数据
    3. 将数据传入本接口，生成优化建议

    示例请求：
    ```json
    {
        "report_type": "exhibition",
        "target_id": 1,
        "target_name": "智能制造博览会",
        "metrics": [
            {"name": "总服务人次", "value": "45678", "description": "人员识别记录总数"},
            {"name": "投诉数量", "value": "5", "description": "展会期间投诉告警数量"},
            {"name": "总用电量", "value": "356789 kWh", "description": "展会期间所有设备能耗汇总"},
            {"name": "设备故障数", "value": "12", "description": "故障告警数量"}
        ],
        "focus_areas": ["人员服务", "设备能耗"]
    }
    ```

    返回：
    ```json
    {
        "report_type": "exhibition",
        "target_id": 1,
        "suggestions": [
            {
                "title": "优化空调预冷策略",
                "content": "建议A馆F2层空调提前30分钟预冷",
                "impact": "可降低开展初期能耗峰值15%",
                "category": "设备能耗"
            }
        ]
    }
    ```
    """
    try:
        suggestion_service = SuggestionService()

        # 转换数据格式
        metrics_data = [
            {
                "name": m.name,
                "value": str(m.value) if m.value is not None else "",
                "description": m.description or ""
            }
            for m in body.metrics
        ]

        # 调用大模型生成建议
        suggestions_raw = await suggestion_service.generate_suggestions(
            report_type=body.report_type.value,
            target_id=body.target_id,
            target_name=body.target_name,
            metrics=metrics_data,
            focus_areas=body.focus_areas,
        )

        # 转换返回格式
        suggestions = [
            SuggestionItem(
                title=s.get("title", ""),
                content=s.get("content", ""),
                impact=s.get("impact"),
                category=s.get("category"),
            )
            for s in suggestions_raw
        ]

        return GenerateSuggestionsResponse(
            report_type=body.report_type.value,
            target_id=body.target_id,
            suggestions=suggestions,
        )

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
        logger.exception("优化建议生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"优化建议生成失败: {str(exc)}",
        )


@router.post("/execute-sql", response_model=ExecuteSQLResponse)
async def execute_sql(body: ExecuteSQLRequest) -> ExecuteSQLResponse:
    """
    执行SQL查询（达梦数据库）

    安全限制：只支持 SELECT 查询，禁止 INSERT/UPDATE/DELETE 等操作

    示例请求：
    ```json
    {
        "sql": "SELECT * FROM \"FWBZ\".\"device\" WHERE \"id\" = ?",
        "params": [1]
    }
    ```
    """
    import time

    # 安全检查：只允许 SELECT
    sql_upper = body.sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        raise HTTPException(
            status_code=400,
            detail="只支持 SELECT 查询，禁止 INSERT/UPDATE/DELETE 等操作",
        )

    try:
        start_time = time.time()

        # 执行查询
        params = tuple(body.params) if body.params else None
        rows = execute_query(body.sql, params)

        execution_time = time.time() - start_time

        # 获取列名
        columns = list(rows[0].keys()) if rows else []

        return ExecuteSQLResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time=round(execution_time, 3),
        )

    except Exception as exc:
        logger.exception("SQL执行失败")
        raise HTTPException(
            status_code=500,
            detail=f"SQL执行失败: {str(exc)}",
        )


@router.post("/report/full", response_model=GenerateFullReportResponse)
async def generate_full_report(body: GenerateFullReportRequest) -> GenerateFullReportResponse:
    """
    生成完整报告（串联流程：生成SQL → 执行SQL → 生成优化建议）

    一个接口完成所有步骤，返回报告数据和AI优化建议。

    示例请求（传入 target_id）：
    ```json
    {
        "report_type": "exhibition",
        "target_id": 1,
        "target_name": "智能制造博览会",
        "focus_areas": ["人员服务", "设备能耗", "会展数据"]
    }
    ```

    示例请求（只传入 target_name）：
    ```json
    {
        "report_type": "exhibition",
        "target_name": "智能制造博览会",
        "focus_areas": ["人员服务", "设备能耗", "会展数据"]
    }
    ```

    返回：
    ```json
    {
        "report_type": "exhibition",
        "target_name": "智能制造博览会",
        "data": [
            {
                "name": "总服务人次",
                "columns": ["stat_date", "today_entry_count"],
                "rows": [{"stat_date": "2026-08-01", "today_entry_count": 1234}],
                "row_count": 7
            }
        ],
        "suggestions": [
            {
                "title": "优化空调预冷策略",
                "content": "建议A馆F2层空调提前30分钟预冷",
                "impact": "可降低能耗峰值15%",
                "category": "设备能耗"
            }
        ]
    }
    ```
    """
    import time

    try:
        sql_service = SQLService()
        suggestion_service = SuggestionService()

        # Step 1: 调用大模型生成报告SQL
        metrics_def = await sql_service.generate_report_sql_by_llm(
            report_type=body.report_type.value,
            target_id=body.target_id,
            target_name=body.target_name,
        )

        # 如果大模型没有返回有效SQL，使用默认配置
        if not metrics_def:
            logger.info("大模型未返回SQL，使用默认指标配置")
            metrics_def = await sql_service.generate_report_sql(
                report_type=body.report_type.value,
                target_id=body.target_id,
                target_name=body.target_name,
            )
            # 动态拼接SQL
            for metric in metrics_def:
                metric["sql"] = _build_metric_sql(metric, body.target_id, body.target_name)
                # 自定义SQL的占位符替换
                if "{" in metric["sql"]:
                    metric["sql"] = metric["sql"].replace("{exhibition_id}", str(body.target_id))
                    metric["sql"] = metric["sql"].replace("{target_id}", str(body.target_id))
                    metric["sql"] = metric["sql"].replace("{exhibition_name}", f"'{body.target_name or ''}'")
        else:
            # 替换SQL中的目标ID
            for metric in metrics_def:
                if "sql" in metric and "{" in metric["sql"]:
                    metric["sql"] = metric["sql"].replace("{target_id}", str(body.target_id))
                    metric["sql"] = metric["sql"].replace("{exhibition_id}", str(body.target_id))
                    metric["sql"] = metric["sql"].replace("{exhibition_name}", f"'{body.target_name or ''}'")

        # Step 2: 执行每个SQL获取数据
        report_data: List[MetricDataResult] = []
        metrics_for_suggestion: List[Dict[str, Any]] = []

        for metric in metrics_def:
            sql = metric.get("sql", "")
            if not sql:
                continue

            try:
                rows = execute_query(sql)
                columns = list(rows[0].keys()) if rows else []

                # 计算汇总值用于生成建议
                summary_value = _calculate_summary(metric, rows)

                report_data.append(MetricDataResult(
                    name=metric.get("name", ""),
                    description=metric.get("description"),
                    category=metric.get("category"),
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    sql=sql,
                ))

                metrics_for_suggestion.append({
                    "name": metric.get("name", ""),
                    "value": summary_value,
                    "description": metric.get("description", ""),
                })
            except Exception as exc:
                logger.warning("执行SQL失败 [%s]: %s", metric.get("name", ""), exc)
                report_data.append(MetricDataResult(
                    name=metric.get("name", ""),
                    description=metric.get("description"),
                    category=metric.get("category"),
                    columns=[],
                    rows=[],
                    row_count=0,
                    sql=sql,
                ))
                metrics_for_suggestion.append({
                    "name": metric.get("name", ""),
                    "value": f"查询失败: {exc}",
                    "description": metric.get("description", ""),
                })

        # Step 3: 调用大模型生成优化建议
        suggestions_raw = await suggestion_service.generate_suggestions(
            report_type=body.report_type.value,
            target_id=body.target_id,
            target_name=body.target_name,
            metrics=metrics_for_suggestion,
            focus_areas=body.focus_areas,
        )

        suggestions = [
            SuggestionItem(
                title=s.get("title", ""),
                content=s.get("content", ""),
                impact=s.get("impact"),
                category=s.get("category"),
            )
            for s in suggestions_raw
        ]

        return GenerateFullReportResponse(
            report_type=body.report_type.value,
            target_id=body.target_id,
            target_name=body.target_name,
            data=report_data,
            suggestions=suggestions,
        )

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
        logger.exception("生成完整报告失败")
        raise HTTPException(
            status_code=500,
            detail=f"生成完整报告失败: {str(exc)}",
        )


def _calculate_summary(metric: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    """根据指标类型计算汇总值"""
    if not rows or not rows[0]:
        return "无数据"

    name = metric.get("name", "")
    aggregate = metric.get("aggregate")
    category = metric.get("category", "")

    # 聚合查询直接返回 result 字段
    if aggregate and "result" in rows[0]:
        val = rows[0].get("result")
        if val is None:
            return "0"

        # 根据指标类型格式化输出
        if "用电量" in name or "用电" in name:
            return f"{float(val):,.0f} kWh"
        elif "人次" in name or "客流" in name or "人数" in name:
            return f"{float(val):,.0f}"
        elif "评分" in name:
            return f"{float(val):.1f}/5.0"
        elif "比" in name or "%" in name:
            return f"{float(val):.1f}%"
        elif "时长" in name or "分钟" in name:
            return f"{float(val):.0f}分钟"
        elif "天数" in name:
            return f"{int(float(val))}天"
        else:
            return str(val)

    # 普通查询返回行数
    return f"{len(rows)} 条"
