import pyodbc

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=PF3LE15J;"
    "Database=HGT_Assignments;"
    "Trusted_Connection=yes;"
)
try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
        
    print("\n--- Procedure sp_UpdateAssignment ---")
    cursor.execute("SELECT definition FROM sys.sql_modules WHERE object_id = OBJECT_ID('sp_UpdateAssignment')")
    row = cursor.fetchone()
    if row:
        print(row[0])

    print("\n--- Procedure sp_GetAssignments ---")
    cursor.execute("SELECT definition FROM sys.sql_modules WHERE object_id = OBJECT_ID('sp_GetAssignments')")
    row = cursor.fetchone()
    if row:
        print(row[0])
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
