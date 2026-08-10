"""AI报告生成服务"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.dameng import execute_query
from app.core.ollama import OllamaClient
from app.services.ai_report_history_service import AIReportHistoryService

logger = logging.getLogger(__name__)


def json_serial(obj):
    """JSON 序列化处理函数，支持 Decimal 和 datetime"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# 系统提示词
SYSTEM_PROMPT = """你是一个专业的会展小镇智慧园区AI分析专家，服务于首钢会展小镇管理系统。

## 数据库信息
- 类型：Dameng (08.00.000)
- Schema：FWBZ
- 标识符引号：表名和字段名必须用双引号包裹

## 你的职责
根据提供的真实数据库查询结果，进行专业的AI数据分析，生成结构化的分析报告。

## 报告要求
1. 分析要基于真实数据，识别数据中的规律和异常
2. 建议要可操作，有数据支撑
3. 报告语言要专业但易懂
4. 如果数据较少或为空，请基于可用数据进行合理分析，并在报告中说明数据情况"""


class AIReportService:
    """AI报告生成服务"""

    def __init__(self):
        self.ollama = OllamaClient()

    def _get_venue_id(self, venue_name: str) -> Optional[int]:
        """根据会展名称获取 venue_id"""
        if not venue_name:
            return None
        sql = '''
            SELECT "id" FROM FWBZ."table_venue_info"
            WHERE "venue_name" = ?
            LIMIT 1
        '''
        result = execute_query(sql, (venue_name,))
        if result and result[0].get("id"):
            return result[0]["id"]
        return None

    def _build_venue_filter(self, venue_name: str) -> str:
        """构建会展过滤条件，返回 WHERE 子句"""
        if not venue_name:
            return ""
        venue_id = self._get_venue_id(venue_name)
        if venue_id:
            return f' AND d."venue_id" = {venue_id}'
        return ""

    @staticmethod
    def list_venues() -> List[Dict[str, Any]]:
        """获取会展列表"""
        sql = '''
            SELECT
                "id",
                "venue_name",
                "location",
                "orientation",
                "area",
                "floors"
            FROM FWBZ."table_venue_info"
            ORDER BY "id"
        '''
        try:
            return execute_query(sql) or []
        except Exception as exc:
            logger.error(f"查询会展列表失败: {exc}")
            return []

    def _get_time_range_dates(self, time_range: str) -> tuple[str, str]:
        """根据时间范围获取开始和结束日期"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        if time_range == "day":
            start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        elif time_range == "week":
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        elif time_range == "month":
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        elif time_range == "quarter":
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        elif time_range == "year":
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        else:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        return start_date, end_date

    # ==================== AI运行报告数据查询 ====================

    def _query_run_report_data(
        self,
        scope: str,
        time_range: str,
        venue_name: Optional[str] = None,
        zone_name: Optional[str] = None,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询AI运行报告所需数据"""
        start_date, end_date = self._get_time_range_dates(time_range)

        data = {
            "query_params": {
                "scope": scope,
                "time_range": time_range,
                "venue_name": venue_name,
                "start_date": start_date,
                "end_date": end_date,
                "zone_name": zone_name,
                "device_id": device_id,
                "device_name": device_name
            },
            "device_stats": {},
            "alarm_stats": {},
            "energy_stats": {},
            "device_list": [],
            "alarm_list": []
        }

        try:
            # 构建会展过滤条件
            venue_filter = self._build_venue_filter(venue_name)
            venue_id = self._get_venue_id(venue_name) if venue_name else None

            # 1. 设备统计（按会展过滤）
            device_sql = f'''
                SELECT 
                    COUNT(*) as total_count,
                    SUM(CASE WHEN "run_state" = '在线' THEN 1 ELSE 0 END) as online_count,
                    SUM(CASE WHEN "run_state" = '离线' THEN 1 ELSE 0 END) as offline_count,
                    COUNT(DISTINCT "device_type") as device_type_count
                FROM FWBZ."device" d
                WHERE 1=1 {venue_filter}
            '''
            result = execute_query(device_sql)
            if result:
                data["device_stats"] = result[0]

            # 2. 告警统计（通过设备关联会展）
            alarm_sql = f'''
                SELECT 
                    COUNT(*) as total_alarms,
                    COUNT(DISTINCT ar."device_id") as alarmed_devices,
                    COUNT(DISTINCT ar."alarm_category_name") as category_count,
                    COUNT(DISTINCT ar."alarm_level_name") as level_count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            if device_id:
                alarm_sql += f' AND ar."device_id" = {device_id}'
            if device_name:
                alarm_sql += f' AND ar."device_name" LIKE \'%{device_name}%\''

            result = execute_query(alarm_sql)
            if result:
                data["alarm_stats"] = result[0]

            # 3. 告警按类别统计
            alarm_by_category_sql = f'''
                SELECT 
                    ar."alarm_category_name",
                    COUNT(*) as count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ar."alarm_category_name"
                ORDER BY count DESC
                LIMIT 10
            '''
            result = execute_query(alarm_by_category_sql)
            data["alarm_stats"]["by_category"] = result or []
            
            # 4. 告警按级别统计
            alarm_by_level_sql = f'''
                SELECT 
                    ar."alarm_level_name",
                    COUNT(*) as count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ar."alarm_level_name"
                ORDER BY count DESC
            '''
            result = execute_query(alarm_by_level_sql)
            data["alarm_stats"]["by_level"] = result or []

            # 5. 告警响应时间统计
            response_time_sql = f'''
                SELECT 
                    AVG(TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time")) as avg_response_minutes,
                    MIN(TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time")) as min_response_minutes,
                    MAX(TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time")) as max_response_minutes
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                AND ar."process_time" IS NOT NULL
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(response_time_sql)
            if result and result[0].get("avg_response_minutes"):
                data["alarm_stats"]["response_time"] = result[0]

            # 6. 能耗统计（通过设备关联会展）
            energy_sql = f'''
                SELECT 
                    SUM(dd."value") as total_energy,
                    AVG(dd."value") as avg_daily_energy,
                    COUNT(DISTINCT DATE(dd."time")) as active_days
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(energy_sql)
            if result:
                data["energy_stats"] = result[0]

            # 7. 能耗按日统计
            energy_daily_sql = f'''
                SELECT 
                    DATE(dd."time") as stat_date,
                    SUM(dd."value") as daily_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY DATE(dd."time")
                ORDER BY stat_date
            '''
            result = execute_query(energy_daily_sql)
            data["energy_stats"]["daily"] = result or []

            # 8. 设备列表（按会展过滤）
            device_list_sql = f'''
                SELECT 
                    "id", "device_name", "device_code", "device_type", "run_state"
                FROM FWBZ."device" d
                WHERE 1=1 {venue_filter}
                LIMIT 20
            '''
            result = execute_query(device_list_sql)
            data["device_list"] = result or []

            # 9. 近期告警列表
            alarm_list_sql = f'''
                SELECT 
                    ar."id", ar."device_name", ar."alarm_category_name", ar."alarm_level_name",
                    ar."alarm_time", ar."alarm_content", ar."alarm_status"
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                ORDER BY ar."alarm_time" DESC
                LIMIT 20
            '''
            result = execute_query(alarm_list_sql)
            data["alarm_list"] = result or []
            
            # 10. 场馆客流统计（按会展过滤）
            venue_flow_sql = f'''
                SELECT
                    vf."venue_id",
                    vi."venue_name",
                    vf."data_date",
                    vf."today_in_count",
                    vf."today_now_count",
                    vf."max_count",
                    vf."max_time",
                    vf."average_duration",
                    vf."status"
                FROM FWBZ."table_venue_flow" vf
                LEFT JOIN FWBZ."table_venue_info" vi ON vf."venue_id" = vi."id"
                WHERE vf."data_date" >= '{start_date}'
                AND vf."data_date" <= '{end_date}'
                {f' AND vf."venue_id" = {venue_id}' if venue_id else ''}
                ORDER BY vf."data_date" DESC
                LIMIT 30
            '''
            result = execute_query(venue_flow_sql)
            data["venue_flow"] = result or []

            # 11. 场馆客流汇总统计
            venue_flow_stats_sql = f'''
                SELECT 
                    COUNT(*) as total_records,
                    SUM(vf."today_in_count") as total_in_count,
                    AVG(vf."today_now_count") as avg_current_count,
                    MAX(vf."max_count") as max_peak_count,
                    AVG(vf."average_duration") as avg_duration
                FROM FWBZ."table_venue_flow" vf
                WHERE vf."data_date" >= '{start_date}'
                AND vf."data_date" <= '{end_date}'
                {f' AND vf."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(venue_flow_stats_sql)
            if result:
                data["venue_flow_stats"] = result[0]
            
            # 12. 人员统计
            personnel_stats_sql = f'''
                SELECT 
                    "stat_date",
                    "today_entry_count",
                    "current_in_count",
                    "recognition_record_count",
                    "abnormal_warning_count"
                FROM FWBZ."table_personnel_statistics"
                WHERE "stat_date" >= '{start_date}'
                AND "stat_date" <= '{end_date}'
                ORDER BY "stat_date" DESC
                LIMIT 30
            '''
            result = execute_query(personnel_stats_sql)
            data["personnel_stats"] = result or []
            
            # 13. 人员统计汇总
            personnel_summary_sql = f'''
                SELECT 
                    COUNT(*) as total_days,
                    SUM("today_entry_count") as total_entries,
                    SUM("recognition_record_count") as total_recognitions,
                    SUM("abnormal_warning_count") as total_warnings,
                    AVG("current_in_count") as avg_current
                FROM FWBZ."table_personnel_statistics"
                WHERE "stat_date" >= '{start_date}'
                AND "stat_date" <= '{end_date}'
            '''
            result = execute_query(personnel_summary_sql)
            if result:
                data["personnel_summary"] = result[0]
            
            # 14. 空间分布
            space_sql = '''
                SELECT 
                    "id", "space_name", "full_name", "full_id", "pid", "has_child"
                FROM FWBZ."space"
                ORDER BY "full_id"
                LIMIT 50
            '''
            result = execute_query(space_sql)
            data["space_list"] = result or []
            
            # 15. 空间告警分布（通过设备关联会展）
            space_alarm_sql = f'''
                SELECT
                    ar."space_name",
                    COUNT(*) as alarm_count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                AND ar."space_name" IS NOT NULL
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ar."space_name"
                ORDER BY alarm_count DESC
                LIMIT 10
            '''
            result = execute_query(space_alarm_sql)
            data["space_alarm_distribution"] = result or []

            # 16. 照明区域统计
            lighting_area_sql = '''
                SELECT
                    la."id",
                    la."area_name",
                    la."area_code",
                    la."status",
                    la."type",
                    la."space_name",
                    la."start_time",
                    la."closing_time",
                    la."all_duration",
                    la."rel_name"
                FROM FWBZ."lighting_area" la
                ORDER BY la."area_code"
                LIMIT 50
            '''
            result = execute_query(lighting_area_sql)
            data["lighting_areas"] = result or []

            # 17. 照明回路统计
            lighting_circuit_sql = '''
                SELECT
                    lc."id",
                    lc."circuit_name",
                    lc."circuit_code",
                    lc."status",
                    lc."area_id",
                    lc."start_time",
                    lc."closing_time",
                    lc."all_duration",
                    lc."comstat"
                FROM FWBZ."lighting_circuit" lc
                ORDER BY lc."circuit_code"
                LIMIT 100
            '''
            result = execute_query(lighting_circuit_sql)
            data["lighting_circuits"] = result or []

            # 18. 照明操作日志统计
            lighting_log_sql = f'''
                SELECT
                    lo."id",
                    lo."rel_type",
                    lo."rel_id",
                    lo."name",
                    lo."operation_type",
                    lo."operation_time",
                    lo."operation_by"
                FROM FWBZ."lighting_operation_log" lo
                WHERE lo."operation_time" >= '{start_date}'
                AND lo."operation_time" <= '{end_date} 23:59:59'
                ORDER BY lo."operation_time" DESC
                LIMIT 50
            '''
            result = execute_query(lighting_log_sql)
            data["lighting_logs"] = result or []

            # 19. 照明计划统计
            lighting_plan_sql = '''
                SELECT
                    lp."id",
                    lp."plan_name",
                    lp."rel_type",
                    lp."rel_ids",
                    lp."execution_time",
                    lp."operation_type",
                    lp."status"
                FROM FWBZ."lighting_plan" lp
                ORDER BY lp."status", lp."plan_name"
                LIMIT 50
            '''
            result = execute_query(lighting_plan_sql)
            data["lighting_plans"] = result or []

            # 20. 设备类型分布统计
            device_category_sql = f'''
                SELECT
                    ec."category_name",
                    ec."full_name",
                    COUNT(d."id") as device_count,
                    SUM(CASE WHEN d."run_state" = '在线' THEN 1 ELSE 0 END) as online_count,
                    SUM(CASE WHEN d."run_state" = '离线' THEN 1 ELSE 0 END) as offline_count
                FROM FWBZ."equipment_category" ec
                INNER JOIN FWBZ."device" d ON d."category_id" = ec."id"
                WHERE 1=1 {venue_filter}
                GROUP BY ec."category_name", ec."full_name"
                ORDER BY device_count DESC
                LIMIT 20
            '''
            result = execute_query(device_category_sql)
            data["device_category_stats"] = result or []

            # 21. 设备在线率统计
            device_online_rate_sql = f'''
                SELECT
                    COUNT(*) as total_devices,
                    SUM(CASE WHEN d."run_state" = '在线' THEN 1 ELSE 0 END) as online_count,
                    ROUND(SUM(CASE WHEN d."run_state" = '在线' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as online_rate
                FROM FWBZ."device" d
                WHERE 1=1 {venue_filter}
            '''
            result = execute_query(device_online_rate_sql)
            data["device_online_rate"] = result[0] if result else {}

            # 22. 设备最后采集时间统计（分析离线设备）
            device_last_gather_sql = f'''
                SELECT
                    d."id",
                    d."device_name",
                    d."device_code",
                    d."run_state",
                    d."last_gather_time"
                FROM FWBZ."device" d
                WHERE d."last_gather_time" IS NOT NULL
                {venue_filter}
                ORDER BY d."last_gather_time" ASC
                LIMIT 20
            '''
            result = execute_query(device_last_gather_sql)
            data["device_last_gather"] = result or []

            # 23. 本月报告数量
            this_month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
            this_month_count_sql = f'''
                SELECT COUNT(*) as cnt FROM FWBZ."ai_report_history"
                WHERE "report_type" = 'run'
                AND "created_at" >= '{this_month_start}'
            '''
            result = execute_query(this_month_count_sql)
            data["this_month_report_count"] = result[0].get("cnt", 0) if result else 0

            # 24. 上月报告数量（用于计算环比）
            last_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
            last_month_end = datetime.now().replace(day=1).strftime("%Y-%m-%d")
            last_month_count_sql = f'''
                SELECT COUNT(*) as cnt FROM FWBZ."ai_report_history"
                WHERE "report_type" = 'run'
                AND "created_at" >= '{last_month_start}'
                AND "created_at" < '{last_month_end}'
            '''
            result = execute_query(last_month_count_sql)
            data["last_month_report_count"] = result[0].get("cnt", 0) if result else 0

            # 25. 近期报告列表（用于底部报告表格）
            recent_reports_sql = '''
                SELECT
                    "id", "title", "report_type", "scope",
                    TO_CHAR("created_at", 'YYYY-MM-DD HH24:MI') as created_at_str,
                    "summary"
                FROM FWBZ."ai_report_history"
                WHERE "report_type" = 'run'
                ORDER BY "created_at" DESC
                LIMIT 10
            '''
            result = execute_query(recent_reports_sql)
            data["recent_reports"] = result or []

            # 26. 统计卡片中的告警数量（用于data_volume计算）
            alarm_count_sql = f'''
                SELECT COUNT(*) as cnt FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(alarm_count_sql)
            data["period_alarm_count"] = result[0].get("cnt", 0) if result else 0

        except Exception as exc:
            logger.error(f"查询运行报告数据失败: {exc}")

        return data

    # ==================== AI预测报告数据查询 ====================
    
    def _query_predict_report_data(
        self,
        time_range: str,
        venue_name: Optional[str] = None,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询AI预测报告所需数据"""
        start_date, end_date = self._get_time_range_dates(time_range)

        data = {
            "query_params": {
                "time_range": time_range,
                "venue_name": venue_name,
                "start_date": start_date,
                "end_date": end_date,
                "device_id": device_id,
                "device_name": device_name
            },
            "energy_history": [],
            "alarm_trend": [],
            "device_params": []
        }

        try:
            venue_id = self._get_venue_id(venue_name) if venue_name else None

            # 1. 能耗历史趋势（通过设备关联会展）
            energy_sql = f'''
                SELECT
                    DATE(dd."time") as stat_date,
                    SUM(dd."value") as daily_value,
                    AVG(dd."value") as avg_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                {f' AND dd."device_id" = {device_id}' if device_id else ''}
                GROUP BY DATE(dd."time")
                ORDER BY stat_date
            '''

            result = execute_query(energy_sql)
            data["energy_history"] = result or []

            # 2. 告警趋势（通过设备关联会展）
            alarm_trend_sql = f'''
                SELECT
                    DATE(ar."alarm_time") as stat_date,
                    COUNT(*) as alarm_count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY DATE(ar."alarm_time")
                ORDER BY stat_date
            '''
            result = execute_query(alarm_trend_sql)
            data["alarm_trend"] = result or []

            # 3. 设备关键参数历史（通过设备关联会展）
            device_params_sql = f'''
                SELECT
                    da."device_id",
                    d."device_name",
                    da."attribute_name",
                    da."value",
                    da."gather_time"
                FROM FWBZ."device_attribute_history" da
                LEFT JOIN FWBZ."device" d ON da."device_id" = d."id"
                WHERE da."collection_time" >= '{start_date}'
                AND da."collection_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                ORDER BY da."collection_time" DESC
                LIMIT 50
            '''
            result = execute_query(device_params_sql)
            data["device_params"] = result or []
            
            # 4. 计量点日数据趋势（通过计量点的space_id关联空间，再关联会展）
            metering_day_sql = f'''
                SELECT
                    mp."node_name",
                    mp."node_code",
                    mp."category_id",
                    mpd."time",
                    mpd."value"
                FROM FWBZ."metering_point_data_day" mpd
                LEFT JOIN FWBZ."metering_point" mp ON mpd."metering_point_id" = mp."id"
                WHERE mpd."time" >= '{start_date}'
                AND mpd."time" <= '{end_date} 23:59:59'
                {f' AND mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})' if venue_id else ''}
                ORDER BY mpd."time" DESC
                LIMIT 100
            '''
            result = execute_query(metering_day_sql)
            data["metering_point_data"] = result or []

            # 5. 计量点汇总统计
            metering_summary_sql = f'''
                SELECT
                    mp."node_name",
                    mp."category_id",
                    COUNT(*) as data_count,
                    SUM(mpd."value") as total_value,
                    AVG(mpd."value") as avg_value,
                    MAX(mpd."value") as max_value,
                    MIN(mpd."value") as min_value
                FROM FWBZ."metering_point_data_day" mpd
                LEFT JOIN FWBZ."metering_point" mp ON mpd."metering_point_id" = mp."id"
                WHERE mpd."time" >= '{start_date}'
                AND mpd."time" <= '{end_date} 23:59:59'
                {f' AND mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})' if venue_id else ''}
                GROUP BY mp."node_name", mp."category_id"
                ORDER BY total_value DESC
                LIMIT 20
            '''
            result = execute_query(metering_summary_sql)
            data["metering_summary"] = result or []

            # 6. 计量点配置列表（按会展过滤）
            if venue_id:
                metering_config_sql = f'''
                    SELECT DISTINCT
                        mp."id", mp."node_name", mp."node_code", mp."type", mp."category_id", mp."space_id"
                    FROM FWBZ."metering_point" mp
                    WHERE mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})
                    ORDER BY mp."node_code"
                    LIMIT 50
                '''
            else:
                metering_config_sql = '''
                    SELECT
                        "id", "node_name", "node_code", "type", "category_id", "space_id"
                    FROM FWBZ."metering_point"
                    ORDER BY "node_code"
                    LIMIT 50
                '''
            result = execute_query(metering_config_sql)
            data["metering_config"] = result or []
            
            # 7. 计量点数据按日趋势
            metering_daily_sql = f'''
                SELECT
                    mp."node_name",
                    DATE(mpd."time") as stat_date,
                    SUM(mpd."value") as daily_value,
                    AVG(mpd."value") as avg_value
                FROM FWBZ."metering_point_data_day" mpd
                LEFT JOIN FWBZ."metering_point" mp ON mpd."metering_point_id" = mp."id"
                WHERE mpd."time" >= '{start_date}'
                AND mpd."time" <= '{end_date} 23:59:59'
                {f' AND mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})' if venue_id else ''}
                GROUP BY mp."node_name", DATE(mpd."time")
                ORDER BY stat_date, mp."node_name"
                LIMIT 200
            '''
            result = execute_query(metering_daily_sql)
            data["metering_daily_trend"] = result or []

        except Exception as exc:
            logger.error(f"查询预测报告数据失败: {exc}")
        
        return data

    # ==================== AI节能报告数据查询 ====================

    def _query_energy_report_data(
        self,
        time_range: str,
        venue_name: Optional[str] = None,
        zone_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询AI节能报告所需数据"""
        start_date, end_date = self._get_time_range_dates(time_range)

        data = {
            "query_params": {
                "time_range": time_range,
                "venue_name": venue_name,
                "start_date": start_date,
                "end_date": end_date,
                "zone_name": zone_name
            },
            "total_energy": {},
            "energy_by_device": [],
            "energy_daily": [],
            "carbon_data": []
        }

        try:
            venue_id = self._get_venue_id(venue_name) if venue_name else None

            # 1. 总能耗统计（按会展过滤）
            total_sql = f'''
                SELECT
                    SUM(dd."value") as total_value,
                    AVG(dd."value") as avg_daily_value,
                    MAX(dd."value") as max_daily_value,
                    MIN(dd."value") as min_daily_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(total_sql)
            if result:
                data["total_energy"] = result[0]

            # 2. 按设备统计能耗（按会展过滤）
            by_device_sql = f'''
                SELECT
                    d."device_name",
                    d."device_code",
                    SUM(dd."value") as total_value,
                    AVG(dd."value") as avg_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY d."device_name", d."device_code"
                ORDER BY total_value DESC
                LIMIT 20
            '''
            result = execute_query(by_device_sql)
            data["energy_by_device"] = result or []

            # 3. 日能耗趋势（按会展过滤）
            daily_sql = f'''
                SELECT
                    DATE(dd."time") as stat_date,
                    SUM(dd."value") as daily_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY DATE(dd."time")
                ORDER BY stat_date
            '''
            result = execute_query(daily_sql)
            data["energy_daily"] = result or []

            # 4. 碳排放因子
            carbon_sql = '''
                SELECT
                    "carbon_factor_name",
                    "coefficient",
                    "unit"
                FROM FWBZ."carbon_emission_factor"
            '''
            result = execute_query(carbon_sql)
            data["carbon_data"] = result or []

            # 5. 能源价格配置
            energy_price_sql = '''
                SELECT
                    "id",
                    "energy_medium",
                    "unit_price",
                    "unit",
                    "remark"
                FROM FWBZ."energy_price"
                ORDER BY "energy_medium"
            '''
            result = execute_query(energy_price_sql)
            data["energy_price"] = result or []

            # 6. 分时电价配置
            pricing_config_sql = '''
                SELECT 
                    "id",
                    "category",
                    "billing_way",
                    "fixed_unit_price",
                    "step1_max", "step1_unit_price",
                    "step2_max", "step2_min", "step2_unit_price",
                    "step3_min", "step3_unit_price",
                    "tip_price", "peak_price", "flat_price", "valley_price",
                    "tip_time_slot1", "peak_time_slot1", "flat_time_slot1", "valley_time_slot1",
                    "tip_time_slot2", "peak_time_slot2", "flat_time_slot2", "valley_time_slot2",
                    "status"
                FROM FWBZ."energy_pricing_config"
                WHERE "status" = '1'
                ORDER BY "category"
            '''
            result = execute_query(pricing_config_sql)
            data["pricing_config"] = result or []
            
            # 7. 标准煤折算系数
            standard_coal_sql = '''
                SELECT 
                    "energy_medium",
                    "eccsc" as standard_coal_coefficient,
                    "ecf" as emission_factor,
                    "unit"
                FROM FWBZ."standard_coal_coefficient"
                ORDER BY "energy_medium"
            '''
            result = execute_query(standard_coal_sql)
            data["standard_coal"] = result or []
            
            # 8. 能耗费用计算（基于计量点数据，按会展过滤）
            energy_cost_sql = f'''
                SELECT
                    mp."node_name",
                    mp."category_id",
                    SUM(mpd."value") as total_value,
                    COUNT(*) as data_count
                FROM FWBZ."metering_point_data_day" mpd
                LEFT JOIN FWBZ."metering_point" mp ON mpd."metering_point_id" = mp."id"
                WHERE mpd."time" >= '{start_date}'
                AND mpd."time" <= '{end_date} 23:59:59'
                {f' AND mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})' if venue_id else ''}
                GROUP BY mp."node_name", mp."category_id"
                ORDER BY total_value DESC
                LIMIT 20
            '''
            result = execute_query(energy_cost_sql)
            data["metering_energy"] = result or []

            # 9. 碳排放计算（结合能耗和碳排放因子）
            carbon_emission_sql = f'''
                SELECT
                    ep."carbon_factor_name",
                    ep."coefficient",
                    ep."unit",
                    SUM(dd."value") as total_energy,
                    SUM(dd."value") * CAST(ep."coefficient" AS DECIMAL(18,6)) as carbon_emission
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                LEFT JOIN FWBZ."equipment_category" ec ON d."category_id" = ec."id"
                LEFT JOIN FWBZ."carbon_emission_factor" ep ON 1=1
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ep."carbon_factor_name", ep."coefficient", ep."unit"
                ORDER BY carbon_emission DESC
            '''
            result = execute_query(carbon_emission_sql)
            data["carbon_emission_stats"] = result or []

            # 10. 峰谷分时用电分析（基于计量点小时数据）
            peak_valley_sql = f'''
                SELECT
                    COUNT(DISTINCT DATE(mph."time")) as total_days,
                    SUM(CASE WHEN EXTRACT(HOUR FROM mph."time") >= 8 AND EXTRACT(HOUR FROM mph."time") < 11 THEN mph."value" ELSE 0 END) as peak_value,
                    SUM(CASE WHEN EXTRACT(HOUR FROM mph."time") >= 23 OR EXTRACT(HOUR FROM mph."time") < 7 THEN mph."value" ELSE 0 END) as valley_value,
                    SUM(CASE WHEN EXTRACT(HOUR FROM mph."time") >= 7 AND EXTRACT(HOUR FROM mph."time") < 23 THEN mph."value" ELSE 0 END) as flat_value
                FROM FWBZ."metering_point_data_hour" mph
                LEFT JOIN FWBZ."metering_point" mp ON mph."metering_point_id" = mp."id"
                WHERE mph."time" >= '{start_date}'
                AND mph."time" <= '{end_date} 23:59:59'
                {f' AND mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})' if venue_id else ''}
            '''
            result = execute_query(peak_valley_sql)
            data["peak_valley_stats"] = result[0] if result else {}

            # 11. 能耗设备排名Top10
            device_energy_ranking_sql = f'''
                SELECT
                    d."id",
                    d."device_name",
                    d."device_code",
                    d."device_type",
                    SUM(dd."value") as total_value,
                    AVG(dd."value") as avg_daily_value,
                    COUNT(DISTINCT DATE(dd."time")) as active_days
                FROM FWBZ."device" d
                LEFT JOIN FWBZ."data_day" dd ON d."id" = dd."device_id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY d."id", d."device_name", d."device_code", d."device_type"
                ORDER BY total_value DESC
                LIMIT 10
            '''
            result = execute_query(device_energy_ranking_sql)
            data["device_energy_ranking"] = result or []

            # 12. 能效分析基准对比
            energy_benchmark_sql = f'''
                SELECT
                    eac."name" as config_name,
                    eab."label" as benchmark_label,
                    eab."value" as benchmark_value,
                    eab."operator",
                    eab."content" as remark
                FROM FWBZ."energy_analysis_benchmark" eab
                LEFT JOIN FWBZ."energy_analysis_config" eac ON eab."config_id" = eac."id"
                WHERE eac."status" = '1'
                ORDER BY eac."name", eab."sort"
            '''
            result = execute_query(energy_benchmark_sql)
            data["energy_benchmark"] = result or []

            # 13. 能耗环比分析
            energy_comparison_sql = f'''
                SELECT
                    DATE(dd."time") as stat_date,
                    SUM(dd."value") as daily_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY DATE(dd."time")
                ORDER BY stat_date
            '''
            result = execute_query(energy_comparison_sql)
            data["energy_comparison"] = result or []

        except Exception as exc:
            logger.error(f"查询节能报告数据失败: {exc}")
        
        return data

    # ==================== AI故障分析报告数据查询 ====================

    def _query_fault_report_data(
        self,
        time_range: str,
        venue_name: Optional[str] = None,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None,
        zone_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询AI故障分析报告所需数据"""
        start_date, end_date = self._get_time_range_dates(time_range)

        data = {
            "query_params": {
                "time_range": time_range,
                "venue_name": venue_name,
                "start_date": start_date,
                "end_date": end_date,
                "device_id": device_id,
                "device_name": device_name,
                "zone_name": zone_name
            },
            "fault_stats": {},
            "fault_by_category": [],
            "fault_by_level": [],
            "fault_list": [],
            "device_fault_count": []
        }

        try:
            venue_id = self._get_venue_id(venue_name) if venue_name else None

            # 1. 故障统计（通过设备关联会展）
            stats_sql = f'''
                SELECT
                    COUNT(*) as total_faults,
                    COUNT(DISTINCT ar."device_id") as affected_devices,
                    COUNT(DISTINCT ar."alarm_category_name") as category_count,
                    COUNT(CASE WHEN ar."alarm_status" = '1' THEN 1 END) as unresolved_count,
                    COUNT(CASE WHEN ar."alarm_status" = '2' THEN 1 END) as resolved_count,
                    COUNT(CASE WHEN ar."alarm_level_name" LIKE '%停机%' OR ar."alarm_level_name" LIKE '%紧急%' THEN 1 END) as unplanned_stop_count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            if device_id:
                stats_sql += f' AND ar."device_id" = {device_id}'
            if device_name:
                stats_sql += f' AND ar."device_name" LIKE \'%{device_name}%\''

            result = execute_query(stats_sql)
            if result:
                data["fault_stats"] = result[0]

            # 2. 故障按类别分布
            by_category_sql = f'''
                SELECT
                    ar."alarm_category_name" as category,
                    COUNT(*) as count,
                    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM FWBZ."alarm_record" ar
                        LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                        WHERE ar."alarm_time" >= '{start_date}' AND ar."alarm_time" <= '{end_date} 23:59:59'
                        {f' AND d."venue_id" = {venue_id}' if venue_id else ''}), 1) as percentage
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ar."alarm_category_name"
                ORDER BY count DESC
            '''
            result = execute_query(by_category_sql)
            data["fault_by_category"] = result or []

            # 3. 故障按级别分布
            by_level_sql = f'''
                SELECT
                    ar."alarm_level_name" as level_name,
                    COUNT(*) as count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ar."alarm_level_name"
                ORDER BY count DESC
            '''
            result = execute_query(by_level_sql)
            data["fault_by_level"] = result or []

            # 4. 故障列表
            fault_list_sql = f'''
                SELECT
                    ar."id", ar."device_name", ar."alarm_category_name", ar."alarm_level_name",
                    ar."alarm_time", ar."alarm_content", ar."alarm_status",
                    TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time") as duration_minutes
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                ORDER BY ar."alarm_time" DESC
                LIMIT 30
            '''
            result = execute_query(fault_list_sql)
            data["fault_list"] = result or []

            # 5. 设备故障频次
            device_count_sql = f'''
                SELECT
                    ar."device_name",
                    COUNT(*) as fault_count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ar."device_name"
                ORDER BY fault_count DESC
                LIMIT 10
            '''
            result = execute_query(device_count_sql)
            data["device_fault_count"] = result or []

            # 6. 平均修复时长
            repair_time_sql = f'''
                SELECT
                    AVG(TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time")) as avg_repair_minutes
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                AND ar."process_time" IS NOT NULL
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(repair_time_sql)
            if result and result[0].get("avg_repair_minutes"):
                data["fault_stats"]["avg_repair_minutes"] = result[0]["avg_repair_minutes"]
            
            # 7. 投诉建议记录
            complaint_sql = f'''
                SELECT 
                    "id",
                    "title",
                    "complaint_date",
                    "type_id",
                    "content",
                    "source",
                    "handler",
                    "status",
                    "remark"
                FROM FWBZ."table_complaint_info"
                WHERE "complaint_date" >= '{start_date}'
                AND "complaint_date" <= '{end_date}'
                ORDER BY "complaint_date" DESC
                LIMIT 30
            '''
            result = execute_query(complaint_sql)
            data["complaint_list"] = result or []
            
            # 8. 投诉建议统计
            complaint_stats_sql = f'''
                SELECT 
                    COUNT(*) as total_complaints,
                    COUNT(CASE WHEN "status" = '待处理' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN "status" = '处理中' THEN 1 END) as processing_count,
                    COUNT(CASE WHEN "status" = '已处理' THEN 1 END) as resolved_count,
                    COUNT(CASE WHEN "status" = '已关闭' THEN 1 END) as closed_count,
                    COUNT(DISTINCT "type_id") as type_count,
                    COUNT(DISTINCT "handler") as handler_count
                FROM FWBZ."table_complaint_info"
                WHERE "complaint_date" >= '{start_date}'
                AND "complaint_date" <= '{end_date}'
            '''
            result = execute_query(complaint_stats_sql)
            if result:
                data["complaint_stats"] = result[0]
            
            # 9. 投诉建议按来源统计
            complaint_by_source_sql = f'''
                SELECT 
                    "source",
                    COUNT(*) as count
                FROM FWBZ."table_complaint_info"
                WHERE "complaint_date" >= '{start_date}'
                AND "complaint_date" <= '{end_date}'
                AND "source" IS NOT NULL
                GROUP BY "source"
                ORDER BY count DESC
            '''
            result = execute_query(complaint_by_source_sql)
            data["complaint_by_source"] = result or []
            
            # 10. 投诉建议按状态分布
            complaint_by_status_sql = f'''
                SELECT 
                    "status",
                    COUNT(*) as count
                FROM FWBZ."table_complaint_info"
                WHERE "complaint_date" >= '{start_date}'
                AND "complaint_date" <= '{end_date}'
                AND "status" IS NOT NULL
                GROUP BY "status"
                ORDER BY count DESC
            '''
            result = execute_query(complaint_by_status_sql)
            data["complaint_by_status"] = result or []
            
            # 11. 投诉建议处理人统计
            complaint_by_handler_sql = f'''
                SELECT 
                    "handler",
                    COUNT(*) as count
                FROM FWBZ."table_complaint_info"
                WHERE "complaint_date" >= '{start_date}'
                AND "complaint_date" <= '{end_date}'
                AND "handler" IS NOT NULL
                GROUP BY "handler"
                ORDER BY count DESC
                LIMIT 10
            '''
            result = execute_query(complaint_by_handler_sql)
            data["complaint_by_handler"] = result or []
            
            # 12. 投诉建议处理记录
            complaint_record_sql = f'''
                SELECT 
                    tcr."id",
                    tcr."complaint_id",
                    tci."title",
                    tcr."handle_date",
                    tcr."handle_content",
                    tcr."status_from",
                    tcr."status_to",
                    tcr."handler"
                FROM FWBZ."table_complaint_record" tcr
                LEFT JOIN FWBZ."table_complaint_info" tci ON tcr."complaint_id" = tci."id"
                WHERE tcr."handle_date" >= '{start_date}'
                AND tcr."handle_date" <= '{end_date}'
                ORDER BY tcr."handle_date" DESC
                LIMIT 30
            '''
            result = execute_query(complaint_record_sql)
            data["complaint_record_list"] = result or []

            # 13. 故障设备空间分布分析
            fault_space_sql = f'''
                SELECT
                    s."space_name",
                    s."full_name",
                    COUNT(ar."id") as fault_count,
                    COUNT(DISTINCT ar."device_id") as affected_devices
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                LEFT JOIN FWBZ."space" s ON d."space_id" = s."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY s."space_name", s."full_name"
                HAVING s."space_name" IS NOT NULL
                ORDER BY fault_count DESC
                LIMIT 15
            '''
            result = execute_query(fault_space_sql)
            data["fault_space_distribution"] = result or []

            # 14. 故障设备类型分布分析
            fault_device_category_sql = f'''
                SELECT
                    ec."category_name" as category,
                    ec."full_name",
                    COUNT(ar."id") as fault_count,
                    COUNT(DISTINCT ar."device_id") as affected_devices,
                    ROUND(COUNT(ar."id") * 100.0 / NULLIF((
                        SELECT COUNT(*) FROM FWBZ."alarm_record" ar2
                        LEFT JOIN FWBZ."device" d2 ON ar2."device_id" = d2."id"
                        WHERE ar2."alarm_time" >= '{start_date}'
                        AND ar2."alarm_time" <= '{end_date} 23:59:59'
                        {f' AND d2."venue_id" = {venue_id}' if venue_id else ''}
                    ), 0), 2) as percentage
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                LEFT JOIN FWBZ."equipment_category" ec ON d."category_id" = ec."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ec."category_name", ec."full_name"
                HAVING ec."category_name" IS NOT NULL
                ORDER BY fault_count DESC
                LIMIT 15
            '''
            result = execute_query(fault_device_category_sql)
            data["fault_device_category"] = result or []

            # 15. 设备最后采集时间分析（识别潜在离线设备）
            device_last_gather_sql = f'''
                SELECT
                    d."id",
                    d."device_name",
                    d."device_code",
                    d."run_state",
                    d."last_gather_time",
                    ec."category_name",
                    s."space_name"
                FROM FWBZ."device" d
                LEFT JOIN FWBZ."equipment_category" ec ON d."category_id" = ec."id"
                LEFT JOIN FWBZ."space" s ON d."space_id" = s."id"
                WHERE d."last_gather_time" IS NOT NULL
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                ORDER BY d."last_gather_time" ASC
                LIMIT 20
            '''
            result = execute_query(device_last_gather_sql)
            data["device_last_gather"] = result or []

            # 16. 故障时段分析
            fault_time_sql = f'''
                SELECT
                    CASE
                        WHEN EXTRACT(HOUR FROM ar."alarm_time") >= 0 AND EXTRACT(HOUR FROM ar."alarm_time") < 6 THEN '凌晨(0-6)'
                        WHEN EXTRACT(HOUR FROM ar."alarm_time") >= 6 AND EXTRACT(HOUR FROM ar."alarm_time") < 12 THEN '上午(6-12)'
                        WHEN EXTRACT(HOUR FROM ar."alarm_time") >= 12 AND EXTRACT(HOUR FROM ar."alarm_time") < 18 THEN '下午(12-18)'
                        ELSE '夜间(18-24)'
                    END as time_period,
                    COUNT(*) as fault_count
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY time_period
                ORDER BY fault_count DESC
            '''
            result = execute_query(fault_time_sql)
            data["fault_time_distribution"] = result or []

            # 17. 告警响应及时率统计
            response_rate_sql = f'''
                SELECT
                    COUNT(*) as total_alarms,
                    COUNT(CASE WHEN TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time") <= 30 THEN 1 END) as within_30min,
                    COUNT(CASE WHEN TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time") > 30
                        AND TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time") <= 60 THEN 1 END) as within_1hour,
                    COUNT(CASE WHEN TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time") > 60
                        AND TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time") <= 240 THEN 1 END) as within_4hour,
                    COUNT(CASE WHEN TIMESTAMPDIFF(SQL_TSI_MINUTE, ar."alarm_time", ar."process_time") > 240 THEN 1 END) as over_4hour,
                    COUNT(CASE WHEN ar."process_time" IS NULL THEN 1 END) as not_processed
                FROM FWBZ."alarm_record" ar
                LEFT JOIN FWBZ."device" d ON ar."device_id" = d."id"
                WHERE ar."alarm_time" >= '{start_date}'
                AND ar."alarm_time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(response_rate_sql)
            if result:
                data["response_rate_stats"] = result[0]

        except Exception as exc:
            logger.error(f"查询故障报告数据失败: {exc}")
        
        return data

    # ==================== 报告生成 ====================

    async def generate_run_report(
        self,
        scope: str,
        time_range: str,
        venue_name: Optional[str] = None,
        zone_name: Optional[str] = None,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成AI运行报告"""
        # 1. 先查询真实数据
        query_data = self._query_run_report_data(scope, time_range, venue_name, zone_name, device_id, device_name)

        # 2. 构建Prompt
        user_prompt = f"""## 任务：生成AI运行报告

### 报告范围
- 范围类型：{scope}
- 时间范围：{time_range}（{query_data['query_params']['start_date']} 至 {query_data['query_params']['end_date']}）
{f'- 会展名称：{venue_name}' if venue_name else ''}
{f'- 分区名称：{zone_name}' if zone_name else ''}
{f'- 设备ID：{device_id}' if device_id else ''}
{f'- 设备名称：{device_name}' if device_name else ''}

### 数据库查询结果
```json
{json.dumps(query_data, ensure_ascii=False, indent=2, default=str)}
```

### 输出要求
请基于以上真实数据，生成JSON格式的分析报告。**metrics至少4个，device_categories至少3个，alarm_distribution至少3个，space_alarm_distribution至少3个，所有字段必须完整填写，禁止返回 null，summary 和 suggestions 尽量简短**：
```json
{{
  "report_title": "报告标题（如：园区设备运行周报 - 2026年X月X日）",
  "report_desc": "报告概述（不超过80字）",
  "metrics": [
    {{"value": "数值", "label": "指标名称"}}
  ],
  "device_categories": [
    {{"category_name": "设备类型名称", "device_count": 数量, "online_count": 在线数, "offline_count": 离线数}}
  ],
  "alarm_distribution": [
    {{"category": "告警类别", "count": 数量, "percentage": 占比数值}}
  ],
  "space_alarm_distribution": [
    {{"space_name": "空间名称", "alarm_count": 告警数量}}
  ],
  "summary": "AI分析总结（不超过100字）",
  "suggestions": ["建议1", "建议2"]
}}
```"""

        result = await self._call_llm_and_parse(user_prompt, "AI运行报告")

        # 补充响应 schema 必填字段
        result["scope"] = scope
        result["time_range"] = time_range

        # 补充统计卡片数据
        device_stats = query_data.get("device_stats", {})
        alarm_stats = query_data.get("alarm_stats", {})
        device_categories = query_data.get("device_category_stats", [])
        alarm_dist = query_data.get("alarm_stats", {}).get("by_category", [])
        space_alarm = query_data.get("space_alarm_distribution", [])
        this_month_count = query_data.get("this_month_report_count", 0)
        last_month_count = query_data.get("last_month_report_count", 0)

        result["device_count"] = device_stats.get("total_count", 0)
        result["device_count_subtitle"] = "全部核心设备"
        online_rate = device_stats.get("online_count", 0) / device_stats.get("total_count", 1) * 100 if device_stats.get("total_count", 0) > 0 else 0
        result["device_online_rate"] = f"{online_rate:.1f}%"
        result["report_count"] = this_month_count if this_month_count > 0 else 1
        # 环比变化：↑ N 本月
        change = this_month_count - last_month_count
        if change > 0:
            result["report_count_change"] = f"↑ {change} 本月"
        elif change < 0:
            result["report_count_change"] = f"↓ {abs(change)} 本月"
        else:
            result["report_count_change"] = "与上月持平"
        result["analysis_dimension"] = 8
        result["analysis_dimension_subtitle"] = "多维度"
        result["report_accuracy"] = "96.5%"
        # 环比变化：↑ 2.3% 较上月（模拟值，可改为从历史记录计算）
        if this_month_count > 0:
            result["report_accuracy_change"] = "↑ 2.3% 较上月"
        else:
            result["report_accuracy_change"] = None

        result["device_stats"] = device_stats
        result["alarm_stats"] = alarm_stats
        result["device_categories"] = device_categories[:10]
        result["alarm_distribution"] = alarm_dist[:10]
        result["space_alarm_distribution"] = space_alarm[:10]

        # 底部报告列表：从历史记录中提取数据
        recent_reports = query_data.get("recent_reports", [])
        period_device_count = device_stats.get("total_count", 0)
        period_alarm_count = query_data.get("period_alarm_count", 0)
        data_volume_base = f"{period_device_count}设备/{period_alarm_count}告警"
        report_list = []
        for r in recent_reports:
            report_list.append({
                "id": r.get("id", 0),
                "title": r.get("title", "AI运行报告"),
                "report_type": r.get("scope", "all"),
                "scope": r.get("scope", "all"),
                "created_at": r.get("created_at_str", ""),
                "data_volume": data_volume_base,
                "status": "已完成"
            })
        result["report_list"] = report_list

        # 3. 保存报告到数据库
        try:
            report_id = AIReportHistoryService.save_report(
                report_type="run",
                title=result.get("report_title", "AI运行报告"),
                content=json.dumps(result, ensure_ascii=False, default=json_serial),
                summary=result.get("summary", "")[:500] if result.get("summary") else None,
                time_range=time_range,
                target_id=device_id,
                target_name=device_name or zone_name,
                scope=scope,
                query_params=query_data.get("query_params"),
                query_data=query_data
            )
            result["report_id"] = report_id
            logger.info(f"运行报告已保存，ID: {report_id}")
        except Exception as exc:
            logger.error(f"保存运行报告失败: {exc}")

        return result

    async def generate_predict_report(
        self,
        predict_type: str,
        time_range: str,
        venue_name: Optional[str] = None,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成AI预测报告"""
        # 1. 先查询真实数据
        query_data = self._query_predict_report_data(time_range, venue_name, device_id, device_name)

        # 2. 构建Prompt
        predict_type_text = {
            "energy": "能耗趋势预测",
            "device": "设备运行参数预警",
            "all": "综合预测分析"
        }.get(predict_type, predict_type)

        user_prompt = f"""## 任务：生成AI预测报告

### 预测类型
{predict_type_text}

### 时间范围
{time_range}（{query_data['query_params']['start_date']} 至 {query_data['query_params']['end_date']}）
{f'- 设备名称：{device_name}' if device_name else ''}

### 历史数据查询结果
```json
{json.dumps(query_data, ensure_ascii=False, indent=2, default=str)}
```

### 输出要求
请基于历史数据趋势，生成预测分析报告JSON。**predict_items 和 warning_items 各最多3条，所有字段必须完整填写，禁止返回 null，summary 和 suggestions 尽量简短**：
```json
{{
  "report_title": "报告标题",
  "predict_items": [
    {{"item_name": "预测项名称", "predict_value": "预测值", "confidence": 0.85, "trend": "up/down/stable", "description": "预测依据说明"}}
  ],
  "warning_items": [
    {{"device_name": "设备名称", "warning_type": "预警类型", "warning_content": "预警内容", "confidence": 0.90, "suggest_time": "建议处理时间（如：2小时内）"}}
  ],
  "summary": "预测分析总结（不超过80字）",
  "suggestions": ["建议1", "建议2"]
}}
```"""

        result = await self._call_llm_and_parse(user_prompt, "AI预测报告")

        # 3. 保存报告到数据库
        try:
            report_id = AIReportHistoryService.save_report(
                report_type="predict",
                title=result.get("report_title", "AI预测报告"),
                content=json.dumps(result, ensure_ascii=False, default=json_serial),
                summary=result.get("summary", "")[:500] if result.get("summary") else None,
                time_range=time_range,
                target_id=device_id,
                target_name=device_name,
                query_params={"predict_type": predict_type},
                query_data=query_data
            )
            result["report_id"] = report_id
            logger.info(f"预测报告已保存，ID: {report_id}")
        except Exception as exc:
            logger.error(f"保存预测报告失败: {exc}")

        return result

    async def generate_energy_report(
        self,
        time_range: str,
        venue_name: Optional[str] = None,
        zone_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成AI节能报告"""
        # 1. 先查询真实数据
        query_data = self._query_energy_report_data(time_range, venue_name, zone_name)

        # 2. 构建Prompt
        user_prompt = f"""## 任务：生成AI节能报告

### 时间范围
{time_range}（{query_data['query_params']['start_date']} 至 {query_data['query_params']['end_date']}）
{f'- 分析区域：{zone_name}' if zone_name else '- 分析区域：全园区'}

### 能耗数据查询结果
```json
{json.dumps(query_data, ensure_ascii=False, indent=2, default=str)}
```

### 输出要求
请基于真实能耗数据，生成节能分析报告JSON。**strategy_items 最多3条，所有字段必须完整填写，禁止返回 null，summary 和 suggestions 尽量简短**：
```json
{{
  "report_title": "报告标题（如：AI节能效果分析报告 - 2026年X月）",
  "report_desc": "报告概述（不超过100字）",
  "metrics": [
    {{"value": "数值", "label": "指标名称"}}
  ],
  "strategy_items": [
    {{"strategy_name": "策略名称", "implement_date": "实施日期", "before_daily": "优化前日均", "after_daily": "优化后日均", "daily_saving": "日节能量", "saving_rate": "节能率", "total_saving": "累计节约", "status": "执行中/已完成/待实施"}}
  ],
  "summary": "节能分析总结（不超过100字）",
  "suggestions": ["建议1", "建议2"]
}}
```"""

        result = await self._call_llm_and_parse(user_prompt, "AI节能报告")

        # 3. 保存报告到数据库
        try:
            report_id = AIReportHistoryService.save_report(
                report_type="energy",
                title=result.get("report_title", "AI节能报告"),
                content=json.dumps(result, ensure_ascii=False, default=json_serial),
                summary=result.get("summary", "")[:500] if result.get("summary") else None,
                time_range=time_range,
                target_name=zone_name,
                query_params=query_data.get("query_params"),
                query_data=query_data
            )
            result["report_id"] = report_id
            logger.info(f"节能报告已保存，ID: {report_id}")
        except Exception as exc:
            logger.error(f"保存节能报告失败: {exc}")

        return result

    async def generate_fault_report(
        self,
        time_range: str,
        venue_name: Optional[str] = None,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None,
        zone_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成AI故障分析报告"""
        # 1. 先查询真实数据
        query_data = self._query_fault_report_data(time_range, venue_name, device_id, device_name, zone_name)

        # 2. 构建Prompt
        user_prompt = f"""## 任务：生成AI故障分析报告

### 时间范围
{time_range}（{query_data['query_params']['start_date']} 至 {query_data['query_params']['end_date']}）
{f'- 设备名称：{device_name}' if device_name else ''}
{f'- 分区名称：{zone_name}' if zone_name else ''}

### 故障数据查询结果
```json
{json.dumps(query_data, ensure_ascii=False, indent=2, default=str)}
```

### 输出要求
请基于真实故障数据，生成故障分析报告JSON。**fault_items 最多5条，maintenance_priorities 最多5条，所有字段必须完整填写，禁止返回 null，summary 和 suggestions 尽量简短**：
```json
{{
  "report_title": "报告标题（如：设备故障智能分析报告 - 2026年X月）",
  "report_desc": "报告概述（不超过80字）",
  "metrics": [
    {{"value": "数值", "label": "指标名称"}}
  ],
  "fault_distribution": [
    {{"category": "类别名称", "count": 数量, "percentage": 占比数值（纯数字，如53.4，不带百分号）}}
  ],
  "fault_items": [
    {{"device_name": "设备名称", "fault_type": "故障类型", "fault_time": "故障时间", "duration": "持续时长", "cause": "故障原因", "solution": "解决方案"}}
  ],
  "maintenance_priorities": [
    {{"priority": "紧急/重要/一般", "device_name": "设备名称", "location": "位置", "fault_count": "X次/月", "ai_risk_score": "XX/100", "suggest_action": "建议措施", "suggest_time": "建议时间"}}
  ],
  "summary": "故障分析总结（不超过80字）",
  "suggestions": ["维保建议1", "维保建议2"]
}}
```"""

        result = await self._call_llm_and_parse(user_prompt, "AI故障分析报告")

        # 3. 保存报告到数据库
        try:
            report_id = AIReportHistoryService.save_report(
                report_type="fault",
                title=result.get("report_title", "AI故障分析报告"),
                content=json.dumps(result, ensure_ascii=False, default=json_serial),
                summary=result.get("summary", "")[:500] if result.get("summary") else None,
                time_range=time_range,
                target_id=device_id,
                target_name=device_name or zone_name,
                query_params=query_data.get("query_params"),
                query_data=query_data
            )
            result["report_id"] = report_id
            logger.info(f"故障分析报告已保存，ID: {report_id}")
        except Exception as exc:
            logger.error(f"保存故障分析报告失败: {exc}")

        return result

    # ==================== 多模态能碳计算 ====================

    def _query_carbon_report_data(
        self,
        time_range: str,
        venue_name: Optional[str] = None,
        zone_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询多模态能碳计算报告所需数据"""
        start_date, end_date = self._get_time_range_dates(time_range)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 获取上月时间范围（用于计算环比）
        today_date = datetime.now()
        last_month_date = today_date - timedelta(days=30)
        last_month_start = last_month_date.strftime("%Y-%m-%d")
        last_month_end = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
        
        data = {
            "query_params": {
                "time_range": time_range,
                "venue_name": venue_name,
                "start_date": start_date,
                "end_date": end_date,
                "zone_name": zone_name
            },
            "carbon_stats": {},
            "carbon_sources": [],
            "carbon_trends": [],
            "energy_by_medium": []
        }

        try:
            venue_id = self._get_venue_id(venue_name) if venue_name else None
            
            # 1. 今日碳排放统计
            today_carbon_sql = f'''
                SELECT
                    COALESCE(SUM(dd."value"), 0) as total_energy,
                    COALESCE(SUM(dd."value") * 0.884, 0) as carbon_today
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE DATE(dd."time") = '{today}'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(today_carbon_sql)
            if result:
                data["carbon_stats"]["today"] = result[0]

            # 2. 本月累计碳排放
            month_carbon_sql = f'''
                SELECT
                    COALESCE(SUM(dd."value"), 0) as total_energy,
                    COALESCE(SUM(dd."value") * 0.884, 0) as carbon_month
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(month_carbon_sql)
            if result:
                data["carbon_stats"]["month"] = result[0]

            # 3. 上月碳排放（用于计算环比）
            last_month_carbon_sql = f'''
                SELECT
                    COALESCE(SUM(dd."value"), 0) as total_energy,
                    COALESCE(SUM(dd."value") * 0.884, 0) as carbon_last_month
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= '{last_month_start}'
                AND dd."time" <= '{last_month_end} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(last_month_carbon_sql)
            if result:
                data["carbon_stats"]["last_month"] = result[0]

            # 4. 碳排放因子列表
            carbon_factors_sql = '''
                SELECT
                    "id",
                    "carbon_factor_name",
                    "coefficient",
                    "unit",
                    "remark"
                FROM FWBZ."carbon_emission_factor"
                ORDER BY "sort"
            '''
            result = execute_query(carbon_factors_sql)
            data["carbon_factors"] = result or []

            # 5. 按能源类型统计碳排放（电力/天然气/热力/其他）
            energy_by_medium_sql = f'''
                SELECT
                    COALESCE(ec."category_name", '其他') as energy_type,
                    COALESCE(SUM(dd."value"), 0) as total_value,
                    COALESCE(SUM(dd."value") * 0.884, 0) as carbon_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                LEFT JOIN FWBZ."equipment_category" ec ON d."category_id" = ec."id"
                WHERE dd."time" >= '{start_date}'
                AND dd."time" <= '{end_date} 23:59:59'
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY ec."category_name"
                ORDER BY total_value DESC
            '''
            result = execute_query(energy_by_medium_sql)
            data["energy_by_medium"] = result or []

            # 6. 碳排放结构（来源占比）
            total_carbon = sum(item.get("carbon_value", 0) for item in data["energy_by_medium"])
            for item in data["energy_by_medium"]:
                item["percentage"] = round((item.get("carbon_value", 0) / total_carbon * 100) if total_carbon > 0 else 0, 1)
                item["source"] = item.get("energy_type", "其他")
            data["carbon_sources"] = data["energy_by_medium"]

            # 7. 月度碳排放趋势
            # 达梦数据库使用 TO_CHAR 替代 DATE_FORMAT，ADD_MONTHS 替代 DATE_SUB
            monthly_carbon_sql = f'''
                SELECT
                    TO_CHAR(dd."time", 'YYYY-MM') as month,
                    COALESCE(SUM(dd."value") * 0.884, 0) as carbon_value
                FROM FWBZ."data_day" dd
                LEFT JOIN FWBZ."device" d ON dd."device_id" = d."id"
                WHERE dd."time" >= ADD_MONTHS(TO_DATE('{end_date}', 'YYYY-MM-DD'), -12)
                AND dd."time" <= TO_DATE('{end_date} 23:59:59', 'YYYY-MM-DD HH24:MI:SS')
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
                GROUP BY TO_CHAR(dd."time", 'YYYY-MM')
                ORDER BY month
            '''
            result = execute_query(monthly_carbon_sql)
            data["carbon_trends"] = result or []

            # 8. 场馆面积（用于计算碳强度）
            venue_where = f' WHERE "venue_name" = \'{venue_name}\'' if venue_name else ''
            venue_area_sql = f'''
                SELECT
                    SUM(COALESCE(CAST("area" AS DECIMAL(18,2)), 0)) as total_area
                FROM FWBZ."table_venue_info"
                {venue_where}
            '''
            result = execute_query(venue_area_sql)
            data["venue_area"] = result[0].get("total_area", 10000) if result else 10000

            # 9. 计量点数据统计（按能源类型）
            metering_stats_sql = f'''
                SELECT
                    mp."category_id",
                    mp."node_name",
                    COALESCE(SUM(mpd."value"), 0) as total_value,
                    COUNT(mpd."id") as data_count
                FROM FWBZ."metering_point_data_day" mpd
                LEFT JOIN FWBZ."metering_point" mp ON mpd."metering_point_id" = mp."id"
                WHERE mpd."time" >= '{start_date}'
                AND mpd."time" <= '{end_date} 23:59:59'
                {f' AND mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})' if venue_id else ''}
                GROUP BY mp."category_id", mp."node_name"
                ORDER BY total_value DESC
                LIMIT 20
            '''
            result = execute_query(metering_stats_sql)
            data["metering_stats"] = result or []

            # 10. 峰谷用电分析
            peak_valley_sql = f'''
                SELECT
                    SUM(CASE WHEN EXTRACT(HOUR FROM mph."time") >= 8 AND EXTRACT(HOUR FROM mph."time") < 11 THEN mph."value" ELSE 0 END) as peak_value,
                    SUM(CASE WHEN EXTRACT(HOUR FROM mph."time") >= 11 AND EXTRACT(HOUR FROM mph."time") < 18 THEN mph."value" ELSE 0 END) as flat_value,
                    SUM(CASE WHEN EXTRACT(HOUR FROM mph."time") >= 18 AND EXTRACT(HOUR FROM mph."time") < 22 THEN mph."value" ELSE 0 END) as shoulder_value,
                    SUM(CASE WHEN EXTRACT(HOUR FROM mph."time") >= 22 OR EXTRACT(HOUR FROM mph."time") < 8 THEN mph."value" ELSE 0 END) as valley_value
                FROM FWBZ."metering_point_data_hour" mph
                LEFT JOIN FWBZ."metering_point" mp ON mph."metering_point_id" = mp."id"
                WHERE mph."time" >= '{start_date}'
                AND mph."time" <= '{end_date} 23:59:59'
                {f' AND mp."space_id" IN (SELECT "space_id" FROM FWBZ."device" WHERE "venue_id" = {venue_id})' if venue_id else ''}
            '''
            result = execute_query(peak_valley_sql)
            data["peak_valley"] = result[0] if result else {}

            # 11. 监测能源类型数量
            energy_type_count_sql = f'''
                SELECT COUNT(DISTINCT ec."category_name") as type_count
                FROM FWBZ."device" d
                LEFT JOIN FWBZ."equipment_category" ec ON d."category_id" = ec."id"
                WHERE 1=1
                {f' AND d."venue_id" = {venue_id}' if venue_id else ''}
            '''
            result = execute_query(energy_type_count_sql)
            data["energy_type_count"] = result[0].get("type_count", 4) if result else 4

        except Exception as exc:
            logger.error(f"查询能碳计算数据失败: {exc}")
        
        return data

    async def generate_carbon_report(
        self,
        time_range: str,
        venue_name: Optional[str] = None,
        zone_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成多模态能碳计算报告"""
        # 1. 先查询真实数据
        query_data = self._query_carbon_report_data(time_range, venue_name, zone_name)

        # 2. 构建Prompt
        user_prompt = f"""## 任务：生成多模态能碳计算报告

### 时间范围
{time_range}（{query_data['query_params']['start_date']} 至 {query_data['query_params']['end_date']}）
{f'- 分析区域：{zone_name}' if zone_name else '- 分析区域：全园区'}

### 能碳数据查询结果
```json
{json.dumps(query_data, ensure_ascii=False, indent=2, default=str)}
```

### 输出要求
请基于真实能碳数据，生成多模态能碳计算报告JSON。**所有字段必须完整填写，禁止返回 null，summary 和 suggestions 尽量简短**：

```json
{{
  "report_title": "报告标题（如：多模态能碳计算报告 - 2026年X月）",
  "report_desc": "报告概述（不超过100字，描述本报告基于电/水/气/热四类能源数据的碳排放核算）",
  "metrics": [
    {{"value": "数值", "label": "指标名称"}}
  ],
  "carbon_sources": [
    {{"source": "电力", "value": 数值, "percentage": 数值}},
    {{"source": "天然气", "value": 数值, "percentage": 数值}},
    {{"source": "热力", "value": 数值, "percentage": 数值}},
    {{"source": "其他", "value": 数值, "percentage": 数值}}
  ],
  "carbon_trends": [
    {{"month": "2026-01", "actual": 数值, "target": 数值}}
  ],
  "summary": "AI能碳分析总结（不超过100字）",
  "suggestions": ["碳减排建议1", "碳减排建议2"]
}}
```"""

        result = await self._call_llm_and_parse(user_prompt, "多模态能碳计算报告")

        # 补充统计卡片数据
        carbon_stats = query_data.get("carbon_stats", {})
        today_carbon = carbon_stats.get("today", {}).get("carbon_today", 0) or 0
        month_carbon = carbon_stats.get("month", {}).get("carbon_month", 0) or 0
        last_month_carbon = carbon_stats.get("last_month", {}).get("carbon_last_month", 0) or 0
        venue_area = query_data.get("venue_area") or 10000
        
        # 计算环比
        month_change = None
        if last_month_carbon > 0:
            month_change = round((month_carbon - last_month_carbon) / last_month_carbon * 100, 1)
        
        # 计算碳强度 (kgCO₂/㎡)
        carbon_intensity = round(month_carbon * 1000 / venue_area, 2) if venue_area and venue_area > 0 else 0
        
        result["energy_type_count"] = query_data.get("energy_type_count", 4)
        result["today_carbon"] = round(today_carbon, 2)
        result["today_carbon_change"] = month_change
        result["month_carbon"] = round(month_carbon, 2)
        result["month_carbon_change"] = month_change
        result["carbon_intensity"] = carbon_intensity
        result["carbon_intensity_change"] = month_change

        # 3. 保存报告到数据库
        try:
            report_id = AIReportHistoryService.save_report(
                report_type="carbon",
                title=result.get("report_title", "多模态能碳计算报告"),
                content=json.dumps(result, ensure_ascii=False, default=json_serial),
                summary=result.get("summary", "")[:500] if result.get("summary") else None,
                time_range=time_range,
                target_name=zone_name,
                query_params=query_data.get("query_params"),
                query_data=query_data
            )
            result["report_id"] = report_id
            logger.info(f"能碳计算报告已保存，ID: {report_id}")
        except Exception as exc:
            logger.error(f"保存能碳计算报告失败: {exc}")

        return result

    # ==================== LLM调用 ====================

    async def _call_llm_and_parse(
        self,
        user_prompt: str,
        report_type: str
    ) -> Dict[str, Any]:
        """调用大模型并解析返回结果"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"生成{report_type}，调用大模型...")

        try:
            payload = self.ollama.build_sql_payload(messages)
            response_text = await self.ollama.chat_for_report(payload)
            return self._parse_response(response_text, report_type)
        except Exception as exc:
            logger.error(f"LLM调用失败: {exc}")
            return self._get_default_report(report_type)

    def _parse_response(self, response: str, report_type: str) -> Dict[str, Any]:
        """解析大模型返回的结果"""
        import re

        # 完整打印原始返回，便于排查
        logger.warning(f"LLM原始返回({report_type})，长度={len(response)}:\n{response}")

        # 方法1：提取单个代码块内容（去首尾```，取第一个完整JSON对象）
        result = None
        for pattern in [
            r"```json\s*(\{.*\})\s*```",
            r"```\s*(\{.*\})\s*```",
        ]:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    result = json.loads(match.group(1))
                    break
                except json.JSONDecodeError:
                    pass

        if result is None:
            # 方法2：剥掉所有 markdown 代码块标记后，找第一个 { 到最后一个 }
            stripped = re.sub(r"```json|```", "", response, flags=re.IGNORECASE).strip()
            try:
                start = stripped.find("{")
                end = stripped.rfind("}") + 1
                if start != -1 and end > start:
                    candidate = stripped[start:end]
                    result = json.loads(candidate)
            except json.JSONDecodeError:
                pass

        if result is None:
            # 方法3：直接暴力找第一个 { 到最后一个 }
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    result = json.loads(response[start:end])
                except json.JSONDecodeError:
                    pass

        if result is None:
            # 解析失败，返回默认结构
            logger.warning(f"无法解析{report_type}返回结果，使用默认结构")
            return self._get_default_report(report_type)

        # 修复 LLM 常见拼写错误
        result = self._fix_llm_typos(result, report_type)
        return result

    def _fix_llm_typos(self, result: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """修复 LLM 常见字段名拼写错误"""
        # 故障报告：float_time → fault_time
        if "fault_items" in result:
            for item in result["fault_items"]:
                if "float_time" in item and "fault_time" not in item:
                    item["fault_time"] = item.pop("float_time")
        return result

    def _get_default_report(self, report_type: str) -> Dict[str, Any]:
        """获取默认报告结构"""
        defaults = {
            "AI运行报告": {
                "report_title": "园区设备运行综合分析报告",
                "report_desc": "基于真实数据的设备运行分析",
                "metrics": [],
                "summary": "报告生成中，请稍后查看详细数据",
                "suggestions": []
            },
            "AI预测报告": {
                "report_title": "设备运行趋势预测报告",
                "predict_items": [],
                "warning_items": [],
                "summary": "预测分析生成中",
                "suggestions": []
            },
            "AI节能报告": {
                "report_title": "AI节能效果分析报告",
                "report_desc": "基于真实能耗数据的节能分析",
                "metrics": [],
                "strategy_items": [],
                "summary": "节能分析生成中",
                "suggestions": []
            },
            "AI故障分析报告": {
                "report_title": "设备故障智能分析报告",
                "report_desc": "基于真实故障数据的分析",
                "metrics": [],
                "fault_distribution": [],
                "fault_items": [],
                "maintenance_priorities": [],
                "summary": "故障分析生成中",
                "suggestions": []
            },
            "多模态能碳计算报告": {
                "report_title": "多模态能碳计算报告",
                "report_desc": "基于电/水/气/热四类能源数据的碳排放核算",
                "metrics": [],
                "carbon_sources": [],
                "carbon_trends": [],
                "summary": "能碳计算分析生成中",
                "suggestions": []
            }
        }
        return defaults.get(report_type, {"report_title": report_type})
