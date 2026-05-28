import secrets
import time
from functools import wraps
from flask import session, request, jsonify, flash, redirect, url_for

TOKEN_TTL = 3600

def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
        session['csrf_token_time'] = time.time()
    else:
        token_age = time.time() - session.get('csrf_token_time', 0)
        if token_age > TOKEN_TTL:
            session['csrf_token'] = secrets.token_hex(32)
            session['csrf_token_time'] = time.time()
    return session['csrf_token']

def validate_csrf_token(token):
    expected = session.get('csrf_token')
    if not expected or not token:
        return False
    token_age = time.time() - session.get('csrf_token_time', 0)
    if token_age > TOKEN_TTL:
        return False
    return secrets.compare_digest(str(expected), str(token))

def csrf_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken') or ''
            if not validate_csrf_token(token):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'CSRF token inválido'}), 403
                flash("Token de seguridad inválido. Intente nuevamente.", "error")
                return redirect(request.referrer or url_for('reports.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def inject_csrf_token():
    return {'csrf_token': generate_csrf_token()}
