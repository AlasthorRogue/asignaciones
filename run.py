import sys
import os
import time
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, request, session
from flask_session import Session

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')

    is_production = os.getenv('FLASK_ENV', 'development') == 'production'

    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY no está configurada. "
            "Define SECRET_KEY en el archivo .env o como variable de entorno."
        )
    app.secret_key = secret_key

    allowed_origins_raw = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5000')
    ALLOWED_ORIGINS = []
    for o in allowed_origins_raw.split(','):
        o = o.strip()
        if not o:
            continue
        if '*' in o:
            continue
        if not o.startswith('http://') and not o.startswith('https://'):
            continue
        ALLOWED_ORIGINS.append(o)

    secure_cookie_default = 'True' if is_production else 'False'
    secure_cookie = os.getenv('SESSION_COOKIE_SECURE', secure_cookie_default).lower() == 'true'
    httponly_cookie = os.getenv('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    samesite_cookie = os.getenv('SESSION_COOKIE_SAMESITE', 'Strict')
    session_lifetime = int(os.getenv('PERMANENT_SESSION_LIFETIME', '1800'))
    session_type = os.getenv('SESSION_TYPE', 'filesystem')
    session_permanent = os.getenv('SESSION_PERMANENT', 'True').lower() == 'true'
    session_file_dir = os.getenv('SESSION_FILE_DIR', os.path.join(app.instance_path, 'flask_session'))

    app.config.update(
        SESSION_COOKIE_SECURE=secure_cookie,
        SESSION_COOKIE_HTTPONLY=httponly_cookie,
        SESSION_COOKIE_SAMESITE=samesite_cookie,
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=session_lifetime),
        SESSION_TYPE=session_type,
        SESSION_PERMANENT=session_permanent,
    )

    if session_type != 'null':
        if session_type == 'filesystem':
            app.config.update(
                SESSION_FILE_DIR=session_file_dir,
                SESSION_FILE_THRESHOLD=500,
                SESSION_FILE_MODE=0o600,
            )

        Session(app)

    from app.utils.security import limiter, check_session_timeout
    limiter.init_app(app)

    from app.utils.csrf import inject_csrf_token
    app.context_processor(inject_csrf_token)

    @app.after_request
    def add_security_headers(response):
        origin = request.headers.get('Origin', '')
        if origin in ALLOWED_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        else:
            response.headers['Access-Control-Allow-Origin'] = ''
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        if is_production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdnjs.cloudflare.com https://code.jquery.com "
            "https://cdn.datatables.net https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' "
            "https://cdnjs.cloudflare.com https://fonts.googleapis.com "
            "https://cdn.datatables.net https://cdn.jsdelivr.net; "
            "font-src 'self' "
            "https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
        if request.method == 'OPTIONS':
            response.status_code = 200
        return response

    @app.before_request
    def session_idle_timeout():
        if request.endpoint and request.endpoint != 'auth.login' and request.endpoint != 'static':
            if check_session_timeout():
                if request.is_json or request.path.startswith('/api/'):
                    from flask import jsonify
                    return jsonify({'error': 'Session expired'}), 401

    @app.before_request
    def update_activity():
        if 'user_id' in session:
            session['last_activity'] = time.time()

    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.terminals import terminals_bp
    from app.routes.assignments import assignments_bp
    from app.routes.reports import reports_bp
    from app.routes.staff import staff_bp
    from app.routes.inventory import inventory_bp
    from app.routes.companies import companies_bp
    from app.routes.device_types import device_types_bp
    from app.routes.warehouses import warehouses_bp
    from app.routes.stock import stock_bp
    from app.routes.api import api_bp
    from app.routes.returns import returns_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(terminals_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(returns_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(device_types_bp)
    app.register_blueprint(warehouses_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(api_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app

if __name__ == '__main__':
    app = create_app()
    is_production = os.getenv('FLASK_ENV', 'development') == 'production'
    app.run(host='127.0.0.1', port=5000, debug=not is_production)
