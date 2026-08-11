import pyodbc

conn_str = 'Driver={ODBC Driver 17 for SQL Server};Server=PF3LE15J;Database=HGT_Assignments;Trusted_Connection=yes;'
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Verify ALL indexes on key tables
print('=== TODOS LOS INDICES ===')

print('AssignmentHistory:')
cursor.execute("SELECT name, type_desc FROM sys.indexes WHERE object_id = OBJECT_ID('AssignmentHistory')")
for row in cursor.fetchall():
    print(f'  - {row[0]} ({row[1]})')

print('Assignments:')
cursor.execute("SELECT name, type_desc FROM sys.indexes WHERE object_id = OBJECT_ID('Assignments')")
for row in cursor.fetchall():
    print(f'  - {row[0]} ({row[1]})')

print('Staff:')
cursor.execute("SELECT name, type_desc FROM sys.indexes WHERE object_id = OBJECT_ID('Staff')")
for row in cursor.fetchall():
    print(f'  - {row[0]} ({row[1]})')

conn.close()
