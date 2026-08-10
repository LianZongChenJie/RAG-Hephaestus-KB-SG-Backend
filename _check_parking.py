from app.services.chat_service import ChatService
svc = ChatService()

# 测试有问题的 SQL
bad_sql = 'SELECT "id", "date", SUM("today_entry_count") FROM FWBZ."table_parking_count" GROUP BY "date" ORDER BY "stat_date" DESC LIMIT 100'
print("原始:", bad_sql)
fixed = svc._fix_group_by(bad_sql)
print("修复后:", fixed)

from app.core.dameng import execute_query
try:
    result = execute_query(fixed)
    print("查询结果:", len(result), "条 ✓")
    for r in result:
        print(r)
except Exception as e:
    print("查询失败:", e)
