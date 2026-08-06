import dmPython
conn = dmPython.connect(
    host='localhost',
    port=5236,
    user='SYSDBA',
    password='Dameng123',
    schema='FWBZ'
)
cursor = conn.cursor()
cursor.execute('SELECT * FROM FWBZ."table_activeMeet_info" WHERE "id" = 1 AND ROWNUM <= 1')
rows = cursor.fetchall()
for row in rows:
    print(row)
cursor.close()
conn.close()

