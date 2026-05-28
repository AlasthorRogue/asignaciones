import time
import uuid
from flask import Blueprint, request, session, jsonify
from ..database import get_db_connection
from werkzeug.security import check_password_hash
from datetime import datetime
import pyodbc
from ..utils.security import limiter
from ..utils.csrf import validate_csrf_token, csrf_required
import secrets

api_bp = Blueprint('api', __name__, url_prefix='/api')

def log_login_attempt(username, success, ip_address):
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO LoginAudit (Username, Success, IPAddress, AttemptTime) VALUES (?, ?, ?, GETDATE())",
                (username, 1 if success else 0, ip_address)
            )
            conn.commit()
            conn.close()
    except Exception:
        pass

@api_bp.route('/test', methods=['GET', 'POST'])
def api_test():
    return jsonify({'success': True, 'message': 'API is working'})

@api_bp.route('/csrf-token', methods=['GET'])
def get_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return jsonify({'csrf_token': session['csrf_token']})

@api_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def api_login():
    token = request.headers.get('X-CSRFToken', '')
    if not validate_csrf_token(token):
        return jsonify({'error': 'Invalid CSRF token'}), 401

    data = request.get_json(force=True, silent=True)
    if not data:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
    else:
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    if len(username) > 50 or len(password) > 128:
        return jsonify({'error': 'Invalid credentials'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    cursor = conn.cursor()
    cursor.execute("EXEC sp_LoginUser @Username=?", (username,))
    user = cursor.fetchone()

    ip_address = request.remote_addr or 'unknown'

    if user and check_password_hash(user.PasswordHash, password):
        sess_obj = session._get_current_object()
        if hasattr(sess_obj, 'sid'):
            sess_obj.sid = uuid.uuid4().hex
        session.clear()
        session.permanent = True
        session['csrf_token'] = secrets.token_hex(32)
        session['user_id'] = user.UserID
        session['username'] = user.Username
        session['role_id'] = user.RoleID
        session['role'] = user.Role
        session['fullname'] = user.FullName
        session['last_activity'] = time.time()
        session['ip_address'] = ip_address
        session['login_time'] = time.time()

        cursor.execute("SELECT MenuKey, CanAccess FROM Permissions WHERE RoleID = ?", (user.RoleID,))
        perms = cursor.fetchall()
        permissions = {p.MenuKey: bool(p.CanAccess) for p in perms}
        session['permissions'] = permissions

        conn.close()
        log_login_attempt(username, True, ip_address)
        return jsonify({
            'success': True,
            'user': {
                'id': user.UserID,
                'username': user.Username,
                'fullname': user.FullName,
                'role': user.Role
            },
            'permissions': permissions,
            'csrf_token': session.get('csrf_token')
        })
    else:
        conn.close()
        log_login_attempt(username, False, ip_address)
        time.sleep(1)
        return jsonify({'error': 'Invalid credentials'}), 401

@api_bp.route('/warehouses', methods=['GET'])
def api_get_warehouses():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if not session.get('permissions', {}).get('warehouses'):
        return jsonify({'error': 'Forbidden'}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT WarehouseID, Name FROM Warehouses ORDER BY Name")
    warehouses = cursor.fetchall()
    conn.close()
    result = [{'id': w.WarehouseID, 'name': w.Name} for w in warehouses]
    return jsonify(result)

@api_bp.route('/device_types', methods=['GET'])
def api_get_device_types():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if not session.get('permissions', {}).get('device_types'):
        return jsonify({'error': 'Forbidden'}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DeviceTypeID, TypeName, Brand, Model FROM DeviceTypes ORDER BY TypeName")
    dt = cursor.fetchall()
    conn.close()
    result = [{'id': d.DeviceTypeID, 'type': d.TypeName, 'brand': d.Brand, 'model': d.Model} for d in dt]
    return jsonify(result)

@api_bp.route('/staff', methods=['GET'])
def api_get_staff():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if not session.get('permissions', {}).get('staff'):
        return jsonify({'error': 'Forbidden'}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("EXEC sp_GetStaff")
    staff = cursor.fetchall()
    conn.close()
    result = [{'id': s.StaffID, 'name': s.FirstName + ' ' + s.LastName} for s in staff]
    return jsonify(result)

@api_bp.route('/assignments', methods=['POST'])
@csrf_required
@limiter.limit("20 per minute")
def api_create_assignment():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if not session.get('permissions', {}).get('create_assignment'):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True)
    required = ['serial', 'device_type_id']
    for field in required:
        if field not in data:
            return jsonify({'error': 'Missing field: ' + field}), 400

    serial = data['serial']
    device_type_id = data['device_type_id']

    raw_staff = data.get('staff_id')
    raw_warehouse = data.get('warehouse_id')
    staff_id = int(raw_staff) if raw_staff and str(raw_staff).lower() != 'null' else None
    warehouse_id = int(raw_warehouse) if raw_warehouse and str(raw_warehouse).lower() != 'null' else None

    if not staff_id and not warehouse_id:
        return jsonify({'error': 'Must provide staff_id or warehouse_id'}), 400

    asset_type = data.get('asset_type', 'Fijo')
    raw_company = data.get('company_id')
    company_id = int(raw_company) if raw_company and str(raw_company).lower() != 'null' else None
    is_temporary = 1 if data.get('is_temporary', False) else 0
    expected_return_date = data.get('expected_return_date')
    is_mobile = 1 if data.get('is_mobile', False) else 0
    mobile_company = data.get('mobile_company')
    mobile_number = data.get('mobile_number')
    mobile_sim = data.get('mobile_sim')

    if expected_return_date and str(expected_return_date).lower() != 'null':
        try:
            expected_return_date = datetime.strptime(expected_return_date, '%Y-%m-%d')
        except:
            expected_return_date = None
    else:
        expected_return_date = None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        user_id = session.get('user_id')
        cursor.execute(
            "EXEC sp_CreateAssignment @StaffID=?, @WarehouseID=?, @DeviceTypeID=?, @Serial=?, @AssetType=?, @Date=?, @CompanyID=?, @IsTemporary=?, @ExpectedReturnDate=?, @UserID=?, @IsMobile=?, @MobileCompany=?, @MobileNumber=?, @MobileSIM=?",
            (staff_id, warehouse_id, device_type_id, serial, asset_type, datetime.now(),
             company_id, is_temporary, expected_return_date, user_id, is_mobile,
             mobile_company, mobile_number, mobile_sim))
        conn.commit()
        return jsonify({'success': True, 'message': 'Assignment created'})
    except Exception as e:
        err_msg = str(e)
        if isinstance(e, pyodbc.Error) and len(e.args) > 1:
            err_details = str(e.args[1])
            if 'UIDX' in err_details or '2627' in err_details or '2601' in err_details:
                return jsonify({'error': 'Serial already assigned'}), 409
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        conn.close()

@api_bp.route('/inventory/by_serial/<serial>', methods=['GET'])
def api_get_inventory_by_serial(serial):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if not session.get('permissions', {}).get('inventory'):
        return jsonify({'error': 'Forbidden'}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """SELECT A.AssignmentID, DT.TypeName, DT.Brand, DT.Model, A.Serial,
        COALESCE(S.FirstName + ' ' + S.LastName, '') AS StaffName,
        W.Name AS WarehouseName,
        COALESCE(T.Name, TW.Name) AS TerminalName,
        C.Name AS CompanyName
        FROM Assignments A
        LEFT JOIN Staff S ON A.StaffID = S.StaffID
        LEFT JOIN Warehouses W ON A.WarehouseID = W.WarehouseID
        LEFT JOIN DeviceTypes DT ON A.DeviceTypeID = DT.DeviceTypeID
        LEFT JOIN Companies C ON A.CompanyID = C.CompanyID
        LEFT JOIN Terminals T ON S.TerminalID = T.TerminalID
        LEFT JOIN Terminals TW ON W.TerminalID = TW.TerminalID
        WHERE A.Serial = ?"""
    cursor.execute(query, (serial,))
    row = cursor.fetchone()
    conn.close()
    if row:
        result = {
            'assignment_id': row.AssignmentID,
            'type': row.TypeName,
            'brand': row.Brand,
            'model': row.Model,
            'serial': row.Serial,
            'staff': row.StaffName,
            'warehouse': row.WarehouseName,
            'terminal': row.TerminalName,
            'company': row.CompanyName
        }
        return jsonify(result)
    else:
        return jsonify({'error': 'Not found'}), 404
