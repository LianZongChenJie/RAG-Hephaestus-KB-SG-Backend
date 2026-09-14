"""统计图表应按 NL 元数据选维度，不能把外键 ID 当 Y 轴。"""
from app.chat.chat_service import ChatService
from app.chat.meta_nl import (
    MetaCatalog,
    _apply_fallback_joins,
    _seed_minimal_columns,
    plan_stat_chart,
    reset_catalog_cache,
)


DEVICE_SQL = (
    'SELECT "id", "device_code", "device_name", "category_id", "space_id", '
    '"magnification", "automatic_algorithm", "sort", "remark", "run_state", '
    '"model_id", "device_type", "last_gather_time", "venue_id" '
    'FROM "FWBZ"."device" LIMIT 500 OFFSET 0'
)


def _catalog():
    cat = MetaCatalog()
    _seed_minimal_columns(cat)
    _apply_fallback_joins(cat)
    return cat


def _device_rows():
    return [
        {
            "id": i,
            "device_code": f"D{i}",
            "device_name": f"设备{i}",
            "category_id": 8 if i < 3 else 62,
            "space_id": 1,
            "magnification": 1.0,
            "run_state": "1",
            "model_id": 1,
            "device_type": "2",
            "venue_id": 1,
        }
        for i in range(10)
    ]


class TestChartMetaPlan:
    def setup_method(self):
        reset_catalog_cache()
        self.cat = _catalog()

    def test_device_listing_counts_by_category_not_id_as_value(self):
        plan = plan_stat_chart(
            source_sql=DEVICE_SQL,
            keys=list(_device_rows()[0].keys()),
            question="请查看并介绍设备信息",
            data=_device_rows(),
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.mode == "count"
        assert plan.cat_key == "category_id"
        assert plan.join is not None
        assert plan.join.to_table == "equipment_category"
        assert plan.join.name_column == "category_name"
        assert plan.metric_key is None

    def test_status_question_uses_run_state(self):
        plan = plan_stat_chart(
            source_sql=DEVICE_SQL,
            keys=list(_device_rows()[0].keys()),
            question="设备运行状态分布",
            data=_device_rows(),
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.cat_key == "run_state"
        assert plan.mode == "count"


class TestComposeChartSql:
    def setup_method(self):
        self.svc = ChatService.__new__(ChatService)

    def test_device_chart_sql_joins_category_name_and_counts(self):
        from app.chat.meta_nl import DimJoin

        join = DimJoin(
            to_table="equipment_category",
            to_column="id",
            name_column="category_name",
            label_cn="设备类别",
        )
        sql = self.svc._compose_chart_sql(
            DEVICE_SQL,
            cat_key="category_id",
            count_mode=True,
            full_stats=False,
            dim_join=join,
        )
        assert "COUNT(*) AS value" in sql
        assert 'LEFT JOIN "FWBZ"."equipment_category" chart_dim' in sql
        assert 'chart_src."category_id" = chart_dim."id"' in sql
        assert "NVL(chart_dim.\"category_name\", '未知') AS name" in sql
        assert "GROUP BY" in sql
        assert "LIMIT 20" in sql
        assert "AS value\nFROM (\nSELECT" in sql or "AS value" in sql
        # 不再把 category_id 直接当 value
        assert '"category_id" AS value' not in sql
