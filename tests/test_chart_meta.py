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

    def test_prefer_dims_picks_run_state_after_same_category(self):
        rows = _device_rows()
        for row in rows:
            row["category_id"] = 8
            row["device_type"] = "2"
        plan = plan_stat_chart(
            source_sql=DEVICE_SQL,
            keys=list(rows[0].keys()),
            question="切片甲",
            data=rows,
            catalog=self.cat,
            prefer_dims=("run_state", "status", "online"),
        )
        assert plan is not None
        assert plan.cat_key == "run_state"
        assert plan.cat_label == "在线情况"


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


class TestChartSliceFollowup:
    def setup_method(self):
        self.svc = ChatService.__new__(ChatService)
        self.slices = ["风机盘管", "AHU-04-机组", "变压器"]

    def test_match_by_slice_name_only(self):
        assert self.svc._match_last_chart_slice("风机盘管", self.slices) == "风机盘管"
        assert self.svc._match_last_chart_slice("变压器", self.slices) == "变压器"
        assert (
            self.svc._match_last_chart_slice("「AHU-04-机组」", self.slices)
            == "AHU-04-机组"
        )

    def test_match_when_slice_name_appears_in_question(self):
        assert (
            self.svc._match_last_chart_slice("这个变压器有哪些", self.slices)
            == "变压器"
        )

    def test_ignore_view_all_and_unrelated(self):
        assert self.svc._match_last_chart_slice("查看全部", self.slices) is None
        assert (
            self.svc._match_last_chart_slice("请查看并介绍设备信息", self.slices)
            is None
        )
        assert self.svc._match_last_chart_slice("今天天气如何", self.slices) is None

    def test_compose_filters_by_last_chart_join(self):
        ctx = {
            "sql": DEVICE_SQL,
            "cat_key": "category_id",
            "join": {
                "to_table": "equipment_category",
                "to_column": "id",
                "name_column": "category_name",
                "join_type": "LEFT",
                "label_cn": "设备类别",
            },
        }
        sql = self.svc._compose_slice_filter_sql(ctx, "风机盘管")
        assert "SELECT src.*" in sql
        assert 'LEFT JOIN "FWBZ"."equipment_category" slice_dim' in sql
        assert "NVL(slice_dim.\"category_name\", '未知') = '风机盘管'" in sql
        assert "LIMIT 500" not in sql

    def test_parent_slices_remain_after_successive_category_views(self):
        from app.chat import chat_service as cs

        ip = "slice-parent-test"
        parent_slices = ["切片甲", "切片乙", "切片丙"]
        join = {
            "to_table": "equipment_category",
            "to_column": "id",
            "name_column": "category_name",
        }
        cs._LAST_CHART_FOLLOWUP[ip] = {
            "sql": DEVICE_SQL,
            "cat_key": "category_id",
            "join": join,
            "slices": list(parent_slices),
        }
        try:
            ctx = self.svc._load_chart_followup(ip)
            sql_a = self.svc._compose_slice_filter_sql(ctx, "切片甲")
            assert " = '切片甲'" in sql_a
            assert "slice_dim" in sql_a

            # 下钻图（在线/离线）若误调用 remember，也不能覆盖父图类别
            self.svc._remember_chart_followup(
                ip,
                sql=sql_a,
                question="切片甲",
                qid="q1",
                echarts={
                    "option": {
                        "xAxis": {"data": ["离线", "在线"]},
                        "series": [],
                    },
                    "_followup": {"cat_key": "run_state"},
                },
            )
            ctx = self.svc._load_chart_followup(ip)
            assert ctx["slices"] == parent_slices
            assert ctx["cat_key"] == "category_id"

            assert self.svc._match_last_chart_slice("切片乙", ctx["slices"]) == "切片乙"
            sql_b = self.svc._compose_slice_filter_sql(ctx, "切片乙")
            assert " = '切片乙'" in sql_b
            assert " = '切片甲'" not in sql_b
            assert 'FROM "FWBZ"."device"' in sql_b

            assert self.svc._match_last_chart_slice("切片丙", ctx["slices"]) == "切片丙"
        finally:
            cs._LAST_CHART_FOLLOWUP.pop(ip, None)
