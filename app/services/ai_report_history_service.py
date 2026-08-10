"""AI报告历史记录服务"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.dameng import execute_query, execute_update, get_dameng_connection

logger = logging.getLogger(__name__)


class AIReportHistoryService:
    """AI报告历史记录服务"""

    # 表名
    TABLE_NAME = "ai_report_history"

    @classmethod
    def init_table(cls) -> bool:
        """初始化报告历史表"""
        # 检查表是否存在（使用达梦兼容的查询方式）
        check_sql = '''
            SELECT COUNT(*) FROM FWBZ."ai_report_history" WHERE 1=1
        '''
        try:
            # 尝试查询，如果表不存在会抛出异常
            result = execute_query(check_sql)
            logger.info("报告历史表已存在")
            return True
        except Exception:
            # 表不存在，创建它
            pass
        
        # 达梦数据库创建序列
        try:
            seq_sql = '''
                CREATE SEQUENCE FWBZ.SEQ_AI_REPORT_HISTORY 
                START WITH 1 
                INCREMENT BY 1 
                NOMAXVALUE
            '''
            execute_update(seq_sql)
        except Exception as exc:
            logger.warning(f"创建序列失败（可能已存在）: {exc}")

        # 创建表（达梦使用序列替代AUTO_INCREMENT）
        try:
            create_sql = '''
                CREATE TABLE FWBZ."ai_report_history" (
                    "id" BIGINT NOT NULL,
                    "report_type" VARCHAR(50) NOT NULL,
                    "title" VARCHAR(500) NOT NULL,
                    "content" CLOB,
                    "summary" VARCHAR(1000),
                    "time_range" VARCHAR(20) NOT NULL,
                    "target_id" BIGINT,
                    "target_name" VARCHAR(255),
                    "scope" VARCHAR(50),
                    "query_params" CLOB,
                    "query_data" CLOB,
                    "created_at" TIMESTAMP,
                    "updated_at" TIMESTAMP,
                    PRIMARY KEY ("id")
                )
            '''
            execute_update(create_sql)
            logger.info("报告历史表创建成功")
            return True
        except Exception as exc:
            logger.error(f"初始化报告历史表失败: {exc}")
            return False

    @classmethod
    def save_report(
        cls,
        report_type: str,
        title: str,
        content: str,
        time_range: str,
        summary: Optional[str] = None,
        target_id: Optional[int] = None,
        target_name: Optional[str] = None,
        scope: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        query_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        保存报告到数据库

        Returns:
            新记录的ID
        """
        # 确保表存在
        cls.init_table()

        # 序列化JSON字段
        query_params_str = json.dumps(query_params, ensure_ascii=False, default=str) if query_params else None
        query_data_str = json.dumps(query_data, ensure_ascii=False, default=str) if query_data else None
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 达梦自增列，插入时不指定id
        sql = '''
            INSERT INTO FWBZ."ai_report_history" (
                "report_type", "title", "content", "summary", "time_range",
                "target_id", "target_name", "scope", "query_params", "query_data",
                "created_at", "updated_at"
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            report_type, title, content, summary, time_range,
            target_id, target_name, scope, query_params_str, query_data_str,
            now, now
        )

        try:
            execute_update(sql, params)
            # 获取刚插入的ID
            result = execute_query('SELECT MAX("id") as new_id FROM FWBZ."ai_report_history"')
            new_id = result[0].get('NEW_ID', 0) if result else 0
            logger.info(f"报告已保存，ID: {new_id}")
            return new_id
        except Exception as exc:
            logger.error(f"保存报告失败: {exc}")
            raise

    @classmethod
    def get_report_by_id(cls, report_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取报告"""
        sql = '''
            SELECT * FROM FWBZ."ai_report_history"
            WHERE "id" = ?
        '''
        try:
            result = execute_query(sql, (report_id,))
            if result:
                report = result[0]
                # 反序列化JSON字段
                if report.get('query_params'):
                    try:
                        report['query_params'] = json.loads(report['query_params'])
                    except:
                        pass
                if report.get('query_data'):
                    try:
                        report['query_data'] = json.loads(report['query_data'])
                    except:
                        pass
                return report
            return None
        except Exception as exc:
            logger.error(f"查询报告失败: {exc}")
            return None

    @classmethod
    def list_reports(
        cls,
        page: int = 1,
        page_size: int = 10,
        report_type: Optional[str] = None,
        time_range: Optional[str] = None,
        target_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        分页查询报告列表

        Returns:
            (报告列表, 总数)
        """
        # 构建WHERE条件
        conditions = []
        params = []

        if report_type:
            conditions.append('"report_type" = ?')
            params.append(report_type)

        if time_range:
            conditions.append('"time_range" = ?')
            params.append(time_range)

        if target_name:
            conditions.append('"target_name" LIKE ?')
            params.append(f'%{target_name}%')

        if start_date:
            conditions.append('"created_at" >= ?')
            params.append(start_date)

        if end_date:
            conditions.append('"created_at" <= ?')
            params.append(f'{end_date} 23:59:59')

        where_clause = ' AND '.join(conditions) if conditions else '1=1'

        # 查询总数
        count_sql = f'''
            SELECT COUNT(*) as total FROM FWBZ."ai_report_history"
            WHERE {where_clause}
        '''
        try:
            count_result = execute_query(count_sql, tuple(params) if params else None)
            total = count_result[0]['total'] if count_result else 0
        except Exception as exc:
            logger.error(f"查询总数失败: {exc}")
            total = 0

        # 查询列表（含content用于解析data_volume）
        offset = (page - 1) * page_size
        list_sql = f'''
            SELECT
                "id", "report_type", "title", "time_range",
                "target_id", "target_name", "scope",
                "summary", "created_at", "updated_at",
                "content"
            FROM FWBZ."ai_report_history"
            WHERE {where_clause}
            ORDER BY "created_at" DESC
            LIMIT ? OFFSET ?
        '''
        params.append(page_size)
        params.append(offset)

        try:
            raw_items = execute_query(list_sql, tuple(params))
            # 解析content JSON，提取data_volume
            items = []
            for raw in (raw_items or []):
                item = {k: v for k, v in raw.items() if k != "content"}
                # 从content JSON中提取设备数和告警数
                content_str = raw.get("content", "")
                device_count = 0
                alarm_count = 0
                try:
                    if content_str:
                        content_json = json.loads(content_str)
                        device_count = content_json.get("device_count", 0) or 0
                        alarm_stats = content_json.get("alarm_stats", {})
                        alarm_count = alarm_stats.get("total_alarms", 0) or 0
                except Exception:
                    pass
                item["data_volume"] = f"{device_count}设备/{alarm_count}告警"
                item["status"] = "已完成"
                items.append(item)
            return items, total
        except Exception as exc:
            logger.error(f"查询报告列表失败: {exc}")
            return [], total

    @classmethod
    def delete_report(cls, report_id: int) -> bool:
        """删除报告"""
        sql = 'DELETE FROM FWBZ."ai_report_history" WHERE "id" = ?'
        try:
            rows = execute_update(sql, (report_id,))
            return rows > 0
        except Exception as exc:
            logger.error(f"删除报告失败: {exc}")
            return False

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """获取报告统计"""
        stats = {
            "total_count": 0,
            "by_type": {},
            "by_time_range": {},
            "recent_count": 0
        }

        try:
            # 总数
            total_sql = 'SELECT COUNT(*) as cnt FROM FWBZ."ai_report_history"'
            result = execute_query(total_sql)
            stats["total_count"] = result[0]['cnt'] if result else 0

            # 按类型统计
            type_sql = '''
                SELECT "report_type", COUNT(*) as cnt
                FROM FWBZ."ai_report_history"
                GROUP BY "report_type"
            '''
            result = execute_query(type_sql)
            stats["by_type"] = {r['report_type']: r['cnt'] for r in result}

            # 按时长范围统计
            range_sql = '''
                SELECT "time_range", COUNT(*) as cnt
                FROM FWBZ."ai_report_history"
                GROUP BY "time_range"
            '''
            result = execute_query(range_sql)
            stats["by_time_range"] = {r['time_range']: r['cnt'] for r in result}

            # 最近7天数量
            recent_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            recent_sql = '''
                SELECT COUNT(*) as cnt FROM FWBZ."ai_report_history"
                WHERE "created_at" >= ?
            '''
            result = execute_query(recent_sql, (recent_date,))
            stats["recent_count"] = result[0]['cnt'] if result else 0

        except Exception as exc:
            logger.error(f"获取统计失败: {exc}")

        return stats
