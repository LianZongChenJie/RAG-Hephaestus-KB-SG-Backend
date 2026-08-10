"""查询达梦数据库表结构"""
from app.core.dameng import execute_query

key_tables = [
    'device', 'alarm_record', 'data_day', 'data_hour',
    'equipment_category', 'table_venue_info', 'space',
    'metering_point', 'metering_point_data_day',
    'table_personnel_statistics', 'table_venue_flow',
    'lighting_area', 'lighting_circuit',
    'energy_pricing_config', 'standard_coal_coefficient',
    'carbon_emission_factor', 'ai_report_history',
    'table_parking_count', 'table_patrolHistory'
]

for t in key_tables:
    sql = f'SELECT COLUMN_NAME, DATA_TYPE FROM USER_TAB_COLUMNS WHERE TABLE_NAME = \'{t}\' ORDER BY COLUMN_ID'
    try:
        cols = execute_query(sql)
        print(f'\n### {t}')
        for c in cols:
            print(f'  {c.get("COLUMN_NAME")} ({c.get("DATA_TYPE")})')
    except Exception as e:
        print(f'{t}: error - {e}')
