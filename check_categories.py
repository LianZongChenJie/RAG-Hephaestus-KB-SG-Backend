from app.core.dameng import get_dameng_connection

conn = get_dameng_connection()
cursor = conn.cursor()

# 查询所有设备分类
cursor.execute('SELECT DISTINCT "category_name", "full_name" FROM FWBZ."equipment_category" ORDER BY "category_name"')
categories = cursor.fetchall()

print("=== 设备分类列表 ===")
for cat in categories:
    print(f"{cat[0]} | {cat[1]}")

# 查询包含冷/热/光伏关键字的分类
print("\n=== 冷源/热/光伏相关分类 ===")
for cat in categories:
    name = str(cat[0] or "") + str(cat[1] or "")
    if "冷" in name or "热" in name or "光" in name or "伏" in name or "CH" in name.upper() or "PV" in name.upper() or "COP" in name.upper():
        print(f"{cat[0]} | {cat[1]}")

cursor.close()
conn.close()
