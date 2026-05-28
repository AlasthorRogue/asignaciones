import time
import re
import secrets
import uuid
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..database import get_db_connection
from werkzeug.security import check_password_hash
from ..utils.security import limiter
from ..utils.csrf import generate_csrf_token, validate_csrf_token, csrf_required

auth_bp = Blueprint('auth', __name__)

def validate_username(username):
    if not username or len(username) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_.-]+$', username))

def validate_password(password):
    if not password or len(password) > 128:
        return False
    return True

def validate_password_complexity(password):
    if not password or len(password) > 128:
        return False
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[^A-Za-z0-9]', password):
        return False
    return True

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

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    csrf_token_val = generate_csrf_token()

    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        if not validate_csrf_token(token):
            flash("Credenciales inválidas", "error")
            return render_template('login.html', csrf_token=generate_csrf_token())

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not validate_username(username):
            flash("Credenciales inválidas", "error")
            return render_template('login.html', csrf_token=generate_csrf_token())

        if not validate_password_complexity(password):
            flash("Credenciales inválidas", "error")
            return render_template('login.html', csrf_token=generate_csrf_token())

        conn = get_db_connection()
        if not conn:
            flash("Error de conexión a la base de datos.", "error")
            return render_template('login.html', csrf_token=generate_csrf_token())

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
            session['permissions'] = {p.MenuKey: bool(p.CanAccess) for p in perms}

            conn.close()
            log_login_attempt(username, True, ip_address)
            return redirect(url_for('reports.dashboard'))
        else:
            conn.close()
            log_login_attempt(username, False, ip_address)
            time.sleep(1)
            flash("Credenciales inválidas", "error")

    return render_template('login.html', csrf_token=csrf_token_val)

@auth_bp.route('/logout', methods=['POST'])
@csrf_required
def logout():
    session.clear()
    response = redirect(url_for('auth.login'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
