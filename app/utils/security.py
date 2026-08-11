import os
import re
import io
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
from flask import session, redirect, url_for, flash, jsonify, request

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["30 per minute"],
    storage_uri="memory://",
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            flash("Debe iniciar sesión para acceder.", "error")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(perm):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            perms = session.get('permissions', {})
            if not perms.get(perm):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Forbidden'}), 403
                flash("No tiene permisos para esta acción.", "error")
                return redirect(url_for('reports.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_session_timeout():
    if 'user_id' in session and 'last_activity' in session:
        import time
        from flask import current_app
        timeout = current_app.config.get('PERMANENT_SESSION_LIFETIME', 1800)
        if isinstance(timeout, int):
            timeout_seconds = timeout
        else:
            timeout_seconds = timeout.total_seconds()
        elapsed = time.time() - session['last_activity']
        if elapsed > timeout_seconds:
            session.clear()
            return True
    return False

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    'pdf': [b'%PDF'],
    'xlsx': [b'PK\x03\x04'],
    'xls': [b'\xd0\xcf\x11\xe0', b'PK\x03\x04'],
}

ALLOWED_MIMETYPES = {
    'pdf': ['application/pdf'],
    'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
             'application/octet-stream'],
    'xls': ['application/vnd.ms-excel',
            'application/octet-stream'],
}

def validate_file_upload(file, allowed_types):
    ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
    if ext not in allowed_types:
        return False, f"Tipo de archivo no permitido: .{ext}. Solo se permiten: {', '.join(allowed_types)}."

    expected_mimes = []
    for t in allowed_types:
        expected_mimes.extend(ALLOWED_MIMETYPES.get(t, []))
    if file.content_type and file.content_type not in expected_mimes:
        return False, f"Tipo MIME no válido: {file.content_type}."

    file.stream.seek(0)
    header = file.read(32)
    file.stream.seek(0)

    if not header:
        return False, "El archivo está vacío."

    valid_magic = False
    for t in allowed_types:
        for magic in ALLOWED_EXTENSIONS.get(t, []):
            if header.startswith(magic):
                valid_magic = True
                break
        if valid_magic:
            break

    if not valid_magic:
        return False, "El contenido del archivo no coincide con el tipo esperado."

    return True, None

def safe_error(msg):
    return "Ocurrió un error inesperado. Contacte a soporte si el problema persiste."
