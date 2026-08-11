import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import CONNECTION_STRING, get_db_connection

APP_PROCEDURES = [
    "sp_LoginUser",
    "sp_CreateUser", "sp_UpdateUser", "sp_DeleteUser", "sp_GetUsers",
    "sp_CreateStaff", "sp_UpdateStaff", "sp_DeleteStaff", "sp_GetStaff",
    "sp_CreateTerminal", "sp_UpdateTerminal", "sp_DeleteTerminal", "sp_GetTerminals",
    "sp_CreateCompany", "sp_UpdateCompany", "sp_DeleteCompany", "sp_GetCompanies",
    "sp_CreateDeviceType", "sp_UpdateDeviceType", "sp_DeleteDeviceType", "sp_GetDeviceTypes",
    "sp_CreateAssignment", "sp_UpdateAssignment", "sp_DeleteAssignment", "sp_GetAssignments",
    "sp_GetStaffDetailsAndAssignments",
    "sp_GetAssignmentHistory",
]

EXEC_PATTERNS = [
    (r"EXEC\s*\(", "EXEC() with literal string - potential SQL injection"),
    (r"EXECUTE\s*\(", "EXECUTE() with literal string - potential SQL injection"),
    (r"sp_executesql\s+N'[^']*'\s*,\s*N'[^']*'\s*,\s*(?!@)", "sp_executesql without parameters - unsafe"),
]

CONCAT_PATTERNS = [
    (r"\'\s*\+\s*@", "String concatenation with variable - potential SQL injection"),
    (r"@\w+\s*\+\s*\'", "String concatenation with variable - potential SQL injection"),
]

SAFE_PATTERNS = [
    (r"sp_executesql\s+N'[^']*'\s*,\s*N'[^']*'\s*,\s*@", "sp_executesql WITH parameters - safe"),
]

def color(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.platform != "win32" else text

def green(text):
    return color(text, "92")

def red(text):
    return color(text, "91")

def yellow(text):
    return color(text, "93")

def audit_procedure(cursor, proc_name):
    cursor.execute(
        "SELECT definition FROM sys.sql_modules WHERE object_id = OBJECT_ID(?)",
        (proc_name,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    definition = row[0]
    issues = []
    safe_indicators = []

    for pattern, desc in EXEC_PATTERNS:
        if re.search(pattern, definition, re.IGNORECASE):
            issues.append((pattern, desc))

    has_exec = bool(re.search(r"(?:EXEC|EXECUTE|sp_executesql)\s*\(", definition, re.IGNORECASE))

    if has_exec:
        for pattern, desc in CONCAT_PATTERNS:
            if re.search(pattern, definition, re.IGNORECASE):
                issues.append((pattern, desc))

    for pattern, desc in SAFE_PATTERNS:
        if re.search(pattern, definition, re.IGNORECASE):
            safe_indicators.append(desc)

    has_dynamic_sql = has_exec
    has_parameterized = bool(re.search(r"N'@\w+", definition, re.IGNORECASE))

    return {
        "name": proc_name,
        "definition": definition,
        "issues": issues,
        "safe_indicators": safe_indicators,
        "has_dynamic_sql": has_dynamic_sql,
        "has_parameterized": has_parameterized,
    }


def main():
    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database.")
        sys.exit(1)

    cursor = conn.cursor()
    print(f"{'='*70}")
    print(f"  AUDITORIA DE STORED PROCEDURES - HGT Assignments")
    print(f"{'='*70}\n")

    results = []
    for proc_name in APP_PROCEDURES:
        result = audit_procedure(cursor, proc_name)
        if result:
            results.append(result)

    safe_count = 0
    warning_count = 0
    unsafe_count = 0

    for r in results:
        if r["issues"]:
            unsafe_count += 1
            print(f"{red('[!] VULNERABLE:')} {r['name']}")
            for _, desc in r["issues"]:
                print(f"      {red('->')} {desc}")
            print()
        elif r["has_dynamic_sql"] and not r["has_parameterized"]:
            warning_count += 1
            print(f"{yellow('[?] REVISAR:')} {r['name']} (usa EXEC/sp_executesql)")
            print()
        else:
            safe_count += 1

    print(f"{'='*70}")
    print(f"  RESUMEN")
    print(f"{'='*70}")
    print(f"  Procedures auditados: {len(results)}")
    print(f"  {green('Seguros')}:          {safe_count}")
    print(f"  {yellow('Requieren revision')}: {warning_count}")
    print(f"  {red('Vulnerables')}:       {unsafe_count}")
    print()

    if unsafe_count > 0:
        print(f"{'='*70}")
        print(f"  PROCEDURES VULNERABLES - DETALLE")
        print(f"{'='*70}\n")
        for r in results:
            if not r["issues"]:
                continue
            print(f"--- {red(r['name'])} ---")
            for line in r["definition"].split("\n")[:30]:
                print(f"  {line}")
            if len(r["definition"].split("\n")) > 30:
                print(f"  ... ({len(r['definition'].split('\n')) - 30} lines truncated)")
            print()

    conn.close()

    if unsafe_count > 0:
        print(f"\n{red('RECOMENDACION:')}")
        print("  Reemplazar EXEC(@sql) con sp_executesql parametrizado:")
        print()
        print("  En vez de:")
        print('    SET @sql = \'SELECT * FROM Users WHERE Username = \'\'\' + @Username + \'\'\'\'')
        print("    EXEC(@sql)")
        print()
        print("  Usar:")
        print("    EXEC sp_executesql")
        print("         N'SELECT * FROM Users WHERE Username = @Username',")
        print("         N'@Username NVARCHAR(100)',")
        print("         @Username = @Username")
        print()
        sys.exit(1)

    print(f"\n{green('OK: Todos los stored procedures revisados son seguros.')}")


if __name__ == "__main__":
    main()
