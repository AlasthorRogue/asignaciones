import pyodbc

conn_str = 'Driver={ODBC Driver 17 for SQL Server};Server=PF3LE15J;Database=HGT_Assignments;Trusted_Connection=yes;'
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Check if sp_CreateAssignment has PreviousUser
query = "SELECT definition FROM sys.sql_modules WHERE object_id = OBJECT_ID('sp_CreateAssignment')"
cursor.execute(query)
row = cursor.fetchone()
if row:
    if 'PreviousUser' in str(row[0]):
        print('sp_CreateAssignment ya tiene PreviousUser')
    else:
        print('sp_CreateAssignment NO tiene PreviousUser - Actualizando...')
        
        # Get the actual SP definition from file
        with open(r'C:\Users\T_OALMARZAO\Desktop\DESAROLLO\ASIGNACIÓN\app\db_migration_mobile_fields.sql', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract CREATE PROCEDURE sp_CreateAssignment
        start = content.find('CREATE PROCEDURE sp_CreateAssignment')
        if start > 0:
            # Find the GO after it
            go_pos = content.find('GO', start)
            proc_sql = content[start:go_pos]
            
            # Only execute if contains PreviousUser
            if 'PreviousUser' in proc_sql:
                print('Ejecutando sp_CreateAssignment actualizado...')
                # Drop and recreate
                try:
                    cursor.execute("IF OBJECT_ID('sp_CreateAssignment', 'P') IS NOT NULL DROP PROCEDURE sp_CreateAssignment")
                    conn.commit()
                except:
                    pass
                
                # Split and execute
                statements = proc_sql.split('GO')
                for stmt in statements:
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith('IF OBJECT_ID'):
                        try:
                            cursor.execute(stmt)
                            conn.commit()
                        except Exception as e:
                            print(f'Warning: {e}')
                print('sp_CreateAssignment actualizado OK')
conn.close()
print('Proceso completado')
