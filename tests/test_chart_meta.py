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

    def test_union_device_list_charts_by_category_name(self):
        data = [
            {"category_name": "楼控设备", "cnt": 1443},
            {"category_name": "电表设备", "cnt": 662},
            {"category_name": "冷源设备", "cnt": 144},
            {"category_name": "安防设备", "cnt": 3109},
        ]
        sql = (
            'SELECT \'楼控设备\' AS "category_name", COUNT(*) AS "cnt" '
            'FROM "FWBZ"."device" WHERE "device_type"=\'2\' '
            "UNION ALL "
            "SELECT '电表设备', COUNT(*) FROM \"FWBZ\".\"device\" WHERE \"device_type\"='1'"
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(data[0].keys()),
            question="查看设备列表",
            data=data,
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.cat_key == "category_name"
        assert plan.already_aggregated is True
        assert plan.metric_key == "cnt"
        assert plan.cat_label == "分类名"

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
        for i, row in enumerate(rows):
            row["category_id"] = 8
            row["device_type"] = "2"
            row["run_state"] = "1" if i % 2 else "0"
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

    def test_security_drill_skips_unknown_online_and_uses_region(self):
        rows = [
            {
                "category_name": "门禁控制器",
                "id": i,
                "device_name": f"控制器{i}",
                "index_code": f"acs{i}",
                "online": "未知" if i < 18 else "在线",
                "region_name": f"区域{i % 3}",
                "device_type": "四门控制器" if i < 10 else "八门控制器",
            }
            for i in range(20)
        ]
        sql = (
            'SELECT src.* FROM (SELECT \'门禁控制器\' AS "category_name", '
            '"id", "name" AS "device_name", "index_code", '
            '\'未知\' AS "online", "region_name", "dev_type_desc" AS "device_type" '
            'FROM "FWBZ"."table_acs_device") src '
            "WHERE CAST(src.\"category_name\" AS VARCHAR) = '门禁控制器'"
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(rows[0].keys()),
            question="门禁控制器",
            data=rows,
            catalog=self.cat,
            prefer_dims=(
                "online",
                "run_state",
                "region_name",
                "space_name",
                "venue_name",
                "device_type",
                "status",
            ),
        )
        assert plan is not None
        assert plan.cat_key == "region_name"
        assert plan.cat_label == "空间位置"

    def test_security_drill_falls_to_device_type_when_online_and_region_unknown(self):
        rows = [
            {
                "category_name": "门禁控制器",
                "device_name": f"控制器{i}",
                "online": "未知",
                "region_name": None,
                "device_type": "四门控制器" if i < 10 else "八门控制器",
            }
            for i in range(20)
        ]
        plan = plan_stat_chart(
            source_sql='SELECT * FROM "FWBZ"."table_acs_device"',
            keys=list(rows[0].keys()),
            question="门禁控制器",
            data=rows,
            catalog=self.cat,
            prefer_dims=(
                "online",
                "run_state",
                "region_name",
                "device_type",
            ),
        )
        assert plan is not None
        assert plan.cat_key == "device_type"
        assert plan.cat_label == "设备类型"

    def test_security_drill_uses_online_when_informative(self):
        rows = [
            {
                "category_name": "门禁控制器",
                "device_name": f"控制器{i}",
                "online": "在线" if i < 12 else "离线",
                "region_name": f"区域{i % 2}",
                "device_type": "四门控制器",
            }
            for i in range(20)
        ]
        plan = plan_stat_chart(
            source_sql='SELECT * FROM "FWBZ"."table_acs_device"',
            keys=list(rows[0].keys()),
            question="门禁控制器",
            data=rows,
            catalog=self.cat,
            prefer_dims=("online", "run_state", "device_type", "region_name"),
        )
        assert plan is not None
        assert plan.cat_key == "online"
        assert plan.cat_label == "在线情况"

    def test_chinese_category_alias_beats_device_name(self):
        rows = [
            {
                "device_name": f"设备{i}",
                "设备类型ID": 8 if i < 5 else 62,
                "设备类型名称": "备用" if i < 5 else "风机盘管",
            }
            for i in range(10)
        ]
        sql = (
            'SELECT "device_name", "category_id" AS "设备类型ID", '
            '(SELECT "full_name" FROM "FWBZ"."equipment_category" '
            'WHERE "id" = "d"."category_id") AS "设备类型名称" '
            'FROM "FWBZ"."device" "d"'
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(rows[0].keys()),
            question="请查看并介绍设备信息",
            data=rows,
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.cat_key == "设备类型名称"
        assert plan.join is None

    def test_device_info_uses_category_even_if_llm_only_selected_name_and_state(self):
        rows = [
            {"device_name": f"设备{i}", "run_state": "1"}
            for i in range(10)
        ]
        sql = (
            'SELECT "device_name", "run_state" FROM "FWBZ"."device" '
            'ORDER BY "create_time" DESC LIMIT 500 OFFSET 0'
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(rows[0].keys()),
            question="请查看并介绍设备信息",
            data=rows,
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.cat_key == "category_id"
        assert plan.join is not None
        assert plan.join.to_table == "equipment_category"
        assert plan.join.name_column == "category_name"


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

    def test_ensure_listing_adds_type_fk_from_relation(self):
        sql = (
            'SELECT "device_name", "run_state" FROM "FWBZ"."device" '
            'ORDER BY "create_time" DESC LIMIT 500 OFFSET 0'
        )
        out = self.svc._ensure_listing_type_fk(sql, catalog=_catalog())
        assert out.startswith('SELECT "category_id", "device_name", "run_state"')
        assert self.svc._ensure_listing_type_fk(out, catalog=_catalog()) == out

    def test_chart_sql_falls_back_to_device_table_when_select_omits_category(self):
        from app.chat.meta_nl import DimJoin

        join = DimJoin(
            to_table="equipment_category",
            to_column="id",
            name_column="category_name",
            label_cn="设备类别",
        )
        inner = 'SELECT "device_name", "run_state" FROM "FWBZ"."device"'
        sql = self.svc._compose_chart_sql(
            inner,
            cat_key="category_id",
            count_mode=True,
            full_stats=True,
            dim_join=join,
            fact_table="device",
        )
        assert 'SELECT "category_id"\nFROM "FWBZ"."device"' in sql
        assert 'LEFT JOIN "FWBZ"."equipment_category" chart_dim' in sql
        assert '"device_name"' not in sql.split("FROM", 1)[-1].split("JOIN", 1)[0]

    def test_user_sql_patched_then_chart_counts_by_category_name(self):
        llm_sql = (
            'SELECT "device_name", "run_state" FROM "FWBZ"."device" '
            'ORDER BY "create_time" DESC LIMIT 500 OFFSET 0'
        )
        table_sql = self.svc._ensure_listing_type_fk(llm_sql, catalog=_catalog())
        assert '"category_id"' in table_sql
        rows = [
            {
                "category_id": 8 if i < 6 else 62,
                "device_name": f"设备{i}",
                "run_state": "1",
            }
            for i in range(10)
        ]
        plan = plan_stat_chart(
            source_sql=table_sql,
            keys=list(rows[0].keys()),
            question="请查看并介绍设备信息",
            data=rows,
            catalog=_catalog(),
        )
        assert plan.cat_key == "category_id"
        chart_sql = self.svc._compose_chart_sql(
            table_sql,
            cat_key=plan.cat_key,
            count_mode=True,
            full_stats=True,
            dim_join=plan.join,
            fact_table=plan.fact_table,
        )
        assert "COUNT(*) AS value" in chart_sql
        assert 'NVL(chart_dim."category_name", \'未知\') AS name' in chart_sql
        assert "run_state" not in chart_sql.split("GROUP BY", 1)[-1]


class TestListingTypeFkFromMeta:
    """明细出图走 hephaestus_meta_nl_relation，不拦截「设备信息」问句。"""

    def setup_method(self):
        reset_catalog_cache()
        self.svc = ChatService.__new__(ChatService)
        self.cat = _catalog()

    def test_device_listing_missing_fk_still_plans_category_join(self):
        rows = [{"device_name": f"设备{i}", "run_state": "1"} for i in range(10)]
        sql = (
            'SELECT "device_name", "run_state" FROM "FWBZ"."device" '
            'ORDER BY "create_time" DESC LIMIT 500 OFFSET 0'
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(rows[0].keys()),
            question="请查看并介绍设备信息",
            data=rows,
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.cat_key == "category_id"
        assert plan.join is not None
        assert plan.join.to_table == "equipment_category"
        assert plan.join.name_column == "category_name"

    def test_status_question_still_uses_run_state(self):
        rows = [{"device_name": f"设备{i}", "run_state": "1"} for i in range(10)]
        sql = (
            'SELECT "device_name", "run_state" FROM "FWBZ"."device" '
            'ORDER BY "create_time" DESC LIMIT 500 OFFSET 0'
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(rows[0].keys()),
            question="设备运行状态分布",
            data=rows,
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.cat_key == "run_state"

    def test_alarm_listing_uses_device_category_id_relation(self):
        rows = [{"alarm_content": f"告警{i}", "alarm_level": "1"} for i in range(8)]
        sql = (
            'SELECT "alarm_content", "alarm_level" '
            'FROM "FWBZ"."alarm_record"'
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(rows[0].keys()),
            question="查看告警记录",
            data=rows,
            catalog=self.cat,
        )
        assert plan is not None
        assert plan.cat_key == "device_category_id"
        assert plan.join is not None
        assert plan.join.to_table == "equipment_category"

    def test_ensure_injects_alarm_type_fk(self):
        sql = 'SELECT "alarm_content" FROM "FWBZ"."alarm_record"'
        out = self.svc._ensure_listing_type_fk(sql, catalog=self.cat)
        assert out.startswith('SELECT "device_category_id", "alarm_content"')

    def test_ensure_skips_aggregated_sql(self):
        sql = (
            'SELECT "run_state", COUNT(*) AS cnt FROM "FWBZ"."device" '
            'GROUP BY "run_state"'
        )
        assert self.svc._ensure_listing_type_fk(sql, catalog=self.cat) == sql


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

    def test_compose_filters_chinese_category_alias(self):
        ctx = {
            "sql": (
                'SELECT "device_name", "category_id" AS "设备类型ID", '
                '(SELECT "full_name" FROM "FWBZ"."equipment_category" '
                'WHERE "id" = "d"."category_id") AS "设备类型名称" '
                'FROM "FWBZ"."device" "d"'
            ),
            "cat_key": "设备类型名称",
            "join": None,
        }
        sql = self.svc._compose_slice_filter_sql(ctx, "备用")
        assert 'src."设备类型名称"' in sql
        assert " = '备用'" in sql
        assert 'src."device_name"' not in sql.split("WHERE", 1)[-1]

    def test_device_list_slice_maps_to_listing_qid(self):
        ctx = {
            "qid": "7.1",
            "sql": (
                "SELECT '楼控设备' AS \"category_name\", COUNT(*) AS \"cnt\" "
                'FROM "FWBZ"."device" WHERE "device_type"=\'2\' '
                "UNION ALL SELECT '安防设备', COUNT(*) FROM \"FWBZ\".\"table_camera_resource\""
            ),
            "cat_key": "category_name",
            "slices": ["楼控设备", "电表设备", "冷源设备", "安防设备"],
        }
        assert self.svc._sql_is_category_count_overview(ctx["sql"])
        assert self.svc._listing_qid_for_chart_slice(ctx, "楼控设备") == "7.2"
        assert self.svc._listing_qid_for_chart_slice(ctx, "冷源设备") == "7.3"
        assert self.svc._listing_qid_for_chart_slice(ctx, "电表设备") == "7.4"
        assert self.svc._listing_qid_for_chart_slice(ctx, "安防设备") == "7.5"

    def test_device_listing_slice_does_not_remap_to_overview(self):
        ctx = {
            "qid": "7.2",
            "sql": (
                'SELECT d."id", d."device_name", ec."category_name" '
                'FROM "FWBZ"."device" d '
                'LEFT JOIN "FWBZ"."equipment_category" ec ON ec."id" = d."category_id" '
                "WHERE d.\"device_type\" = '2' LIMIT 500"
            ),
            "cat_key": "category_name",
        }
        assert not self.svc._sql_is_category_count_overview(ctx["sql"])
        assert self.svc._listing_qid_for_chart_slice(ctx, "风机盘管") is None

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

    def test_union_slice_sql_does_not_overwrite_parent_followup(self):
        from app.chat import chat_service as cs

        ip = "union-slice-parent-test"
        parent_slices = ["摄像头", "门禁", "门禁控制器"]
        cs._LAST_CHART_FOLLOWUP[ip] = {
            "sql": 'SELECT \'摄像头\' AS "category_name" FROM "FWBZ"."table_camera_resource"',
            "cat_key": "category_name",
            "join": None,
            "slices": list(parent_slices),
        }
        try:
            ctx = self.svc._load_chart_followup(ip)
            sql_a = self.svc._compose_slice_filter_sql(ctx, "门禁控制器")
            assert "CAST(src.\"category_name\" AS VARCHAR) = '门禁控制器'" in sql_a
            assert self.svc._is_chart_slice_sql(sql_a)

            self.svc._remember_chart_followup(
                ip,
                sql=sql_a,
                question="门禁控制器",
                qid="q75",
                echarts={
                    "option": {
                        "xAxis": {"data": ["区域A", "区域B"]},
                        "series": [],
                    },
                    "_followup": {"cat_key": "region_name"},
                },
            )
            ctx = self.svc._load_chart_followup(ip)
            assert ctx["slices"] == parent_slices
            assert ctx["cat_key"] == "category_name"
        finally:
            cs._LAST_CHART_FOLLOWUP.pop(ip, None)


class TestChartRegroupByColumn:
    def setup_method(self):
        self.svc = ChatService.__new__(ChatService)

    def test_parse_explicit_group_phrases(self):
        assert self.svc._parse_chart_regroup_phrase("按照空间位置统计") == "空间位置"
        assert self.svc._parse_chart_regroup_phrase("请按区域名称列统计") == "区域名称"
        assert self.svc._parse_chart_regroup_phrase("换成按在线情况分组") == "在线情况"
        assert self.svc._parse_chart_regroup_phrase("按 area_name 列出图") == "area_name"
        assert self.svc._parse_chart_regroup_phrase("查看安防设备") is None
        assert self.svc._parse_chart_regroup_phrase("门禁控制器") is None

    def test_resolve_aliases_against_last_keys(self):
        keys = ["id", "circuit_name", "status", "area_name", "area_id"]
        assert self.svc._resolve_chart_dim_phrase("空间位置", keys) == "area_name"
        assert self.svc._resolve_chart_dim_phrase("区域名称", keys) == "area_name"
        assert self.svc._resolve_chart_dim_phrase("status", keys) == "status"
        assert self.svc._resolve_chart_dim_phrase("在线情况", keys) == "status"
        assert self.svc._resolve_chart_dim_phrase("设备类型", keys) is None

    def test_force_prefer_uses_requested_column(self):
        from app.chat.meta_nl import plan_stat_chart, reset_catalog_cache

        reset_catalog_cache()
        rows = [
            {
                "status": "开启" if i < 6 else "关闭",
                "area_name": f"区域{i % 3}",
                "circuit_name": f"回路{i}",
            }
            for i in range(12)
        ]
        sql = (
            'SELECT c."status", a."area_name", c."circuit_name" '
            'FROM "FWBZ"."lighting_circuit" c '
            'LEFT JOIN "FWBZ"."lighting_area" a ON a."id" = c."area_id"'
        )
        plan = plan_stat_chart(
            source_sql=sql,
            keys=list(rows[0].keys()),
            question="按照空间位置统计",
            data=rows,
            catalog=_catalog(),
            prefer_dims=["area_name"],
            force_prefer=True,
        )
        assert plan is not None
        assert plan.cat_key == "area_name"
        assert plan.cat_label == "区域名称"
