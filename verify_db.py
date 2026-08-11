import pyodbc

conn_str = 'Driver={ODBC Driver 17 for SQL Server};Server=PF3LE15J;Database=HGT_Assignments;Trusted_Connection=yes;'
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Verify indexes
print('=== INDICES CREADOS ===')
cursor.execute("SELECT name FROM sys.indexes WHERE object_id IN (OBJECT_ID('AssignmentHistory'), OBJECT_ID('Assignments'), OBJECT_ID('Staff')) AND name LIKE 'IX_%' ORDER BY name")
for row in cursor.fetchall():
    print(f'  - {row[0]}')

# Verify PreviousUser column
print()
print('=== COLUMNA PreviousUser ===')
cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('AssignmentHistory') AND name = 'PreviousUser'")
if cursor.fetchone():
    print('  OK - Columna PreviousUser existe')
else:
    print('  NO - Columna PreviousUser no existe')

# Count history with PreviousUser
cursor.execute("SELECT COUNT(*) FROM AssignmentHistory WHERE PreviousUser IS NOT NULL")
count = cursor.fetchone()[0]
print()
print(f'=== REGISTROS CON PreviousUser: {count} ===')

conn.close()
