from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..database import get_db_connection
from werkzeug.security import generate_password_hash
from ..utils.csrf import csrf_required
from ..utils.security import limiter
from ..routes.auth import validate_password_complexity

PASSWORD_REQUIREMENTS = "La contraseña debe tener al menos 8 caracteres, mayúsculas, minúsculas, números y un carácter especial."

users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_users():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    # Permission check: must have 'users' OR 'roles' permission to see this combined page
    perms = session.get('permissions', {})
    if not perms.get('users') and not perms.get('roles'):
        flash("No tiene permisos para acceder a esta sección.", "error")
        return redirect(url_for('reports.dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        
        # --- User Actions ---
        if action == 'create':
            if not session.get('permissions', {}).get('create_user'):
                flash("No tiene permisos para crear usuarios.", "danger")
                return redirect(url_for('users.manage_users'))
            username = request.form['username']
            password = request.form['password']
            if not validate_password_complexity(password):
                flash(PASSWORD_REQUIREMENTS, "danger")
                return redirect(url_for('users.manage_users'))
            fullname = request.form['fullname']
            terminal_id = request.form.get('terminal_id') or None
            role_id = request.form['role_id']
            pw_hash = generate_password_hash(password)
            cursor.execute("EXEC sp_CreateUser @Username=?, @PasswordHash=?, @FullName=?, @TerminalID=?, @RoleID=?", 
                           (username, pw_hash, fullname, terminal_id, role_id))
            conn.commit()
            flash("Usuario creado exitosamente.", "success")
            
        elif action == 'update':
            if not session.get('permissions', {}).get('edit_user'):
                flash("No tiene permisos para editar usuarios.", "danger")
                return redirect(url_for('users.manage_users'))
            user_id = request.form['user_id']
            fullname = request.form['fullname']
            terminal_id = request.form.get('terminal_id') or None
            role_id = request.form['role_id']
            cursor.execute("EXEC sp_UpdateUser @UserID=?, @FullName=?, @TerminalID=?, @RoleID=?", 
                           (user_id, fullname, terminal_id, role_id))
            conn.commit()
            flash("Usuario actualizado.", "success")
            
        elif action == 'change_password':
            if not session.get('permissions', {}).get('edit_user'):
                flash("No tiene permisos para cambiar contraseñas.", "danger")
                return redirect(url_for('users.manage_users'))
            target_user_id = request.form.get('user_id')
            new_password = request.form.get('new_password', '')
            if not validate_password_complexity(new_password):
                flash(PASSWORD_REQUIREMENTS, "danger")
                return redirect(url_for('users.manage_users'))
            pw_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE Users SET PasswordHash = ? WHERE UserID = ?", (pw_hash, target_user_id))
            conn.commit()
            flash("Contraseña actualizada exitosamente.", "success")

        elif action == 'delete':
            if not session.get('permissions', {}).get('delete_user'):
                flash("No tiene permisos para eliminar usuarios.", "danger")
                return redirect(url_for('users.manage_users'))
            user_id = request.form['user_id']
            cursor.execute("EXEC sp_DeleteUser @UserID=?", (user_id,))
            conn.commit()
            flash("Usuario eliminado.", "success")

        # --- Role Actions ---
        elif action == 'create_role':
            if not session.get('permissions', {}).get('create_role'):
                flash("No tiene permisos para crear roles.", "danger")
                return redirect(url_for('users.manage_users'))
            role_name = request.form['role_name'].upper()
            try:
                cursor.execute("INSERT INTO Roles (RoleName) VALUES (?)", (role_name,))
                role_id = cursor.execute("SELECT @@IDENTITY").fetchval()
                menu_keys = ALL_PERMISSION_KEYS
                for key in menu_keys:
                    cursor.execute("INSERT INTO Permissions (RoleID, MenuKey, CanAccess) VALUES (?, ?, 0)", (role_id, key))
                conn.commit()
                flash(f"Rol '{role_name}' creado.", "success")
            except Exception as e:
                flash("Error al crear rol.", "error")

        elif action == 'update_permissions':
            if not session.get('permissions', {}).get('roles'):
                flash("No tiene permisos para gestionar roles.", "danger")
                return redirect(url_for('users.manage_users'))
            role_id = request.form['role_id']
            menu_keys = ALL_PERMISSION_KEYS
            try:
                for key in menu_keys:
                    val = 1 if request.form.get(f'perm_{key}') == 'on' else 0
                    cursor.execute("UPDATE Permissions SET CanAccess = ? WHERE RoleID = ? AND MenuKey = ?", (val, role_id, key))
                conn.commit()
                flash("Permisos de rol actualizados.", "success")
            except Exception as e:
                flash("Error al actualizar permisos.", "error")

        elif action == 'delete_role':
            if not session.get('permissions', {}).get('delete_role'):
                flash("No tiene permisos para eliminar roles.", "danger")
                return redirect(url_for('users.manage_users'))
            role_id = request.form['role_id']
            if int(role_id) == session.get('role_id'):
                flash("No puede eliminar su propio rol.", "error")
            else:
                cursor.execute("DELETE FROM Roles WHERE RoleID = ?", (role_id,))
                conn.commit()
                flash("Rol eliminado.", "success")
            
        conn.close()
        return redirect(url_for('users.manage_users'))

    # GET Request
    cursor.execute("EXEC sp_GetUsers")
    users = cursor.fetchall()
    
    cursor.execute("EXEC sp_GetTerminals")
    terminals = cursor.fetchall()
    
    cursor.execute("SELECT RoleID, RoleName FROM Roles")
    roles = cursor.fetchall()

    # Get all permissions for display
    cursor.execute("SELECT RoleID, MenuKey, CanAccess FROM Permissions")
    all_perms_raw = cursor.fetchall()
    permissions = {}
    for p in all_perms_raw:
        if p.RoleID not in permissions:
            permissions[p.RoleID] = {}
        permissions[p.RoleID][p.MenuKey] = bool(p.CanAccess)
    
    conn.close()
    return render_template('users.html', users=users, roles=roles, terminals=terminals, permissions=permissions)
