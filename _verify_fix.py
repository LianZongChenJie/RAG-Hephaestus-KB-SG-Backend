# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.core.dameng import execute_query

# 验证修复后的SQL: 在线/离线
sql = """
    SELECT
        ec."category_name",
        COUNT(d."id") as device_count,
        SUM(CASE WHEN d."run_state" = '在线' THEN 1 ELSE 0 END) as online_count,
        SUM(CASE WHEN d."run_state" = '离线' THEN 1 ELSE 0 END) as offline_count
    FROM FWBZ."equipment_category" ec
    INNER JOIN FWBZ."device" d ON d."category_id" = ec."id"
    WHERE 1=1
    GROUP BY ec."category_name"
    ORDER BY device_count DESC
    LIMIT 15
"""
rows = execute_query(sql)
all_ok = True
for r in rows:
    online = r['online_count'] or 0
    offline = r['offline_count'] or 0
    total = online + offline
    ok = total == r['device_count']
    if not ok:
        all_ok = False
    flag = 'OK' if ok else 'FAIL'
    print(f'{r["category_name"]}: device={r["device_count"]} online={online} offline={offline} sum={total} [{flag}]')

print()
if all_ok:
    print('ALL OK - online + offline = device_count')
else:
    print('HAS INCONSISTENCY')
