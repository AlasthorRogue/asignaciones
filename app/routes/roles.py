from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..database import get_db_connection
from ..utils.csrf import csrf_required
from ..utils.security import limiter

roles_bp = Blueprint('roles', __name__)

@roles_bp.route('/roles', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_roles():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    if not session.get('permissions', {}).get('roles'):
        flash("No tiene permisos para acceder a esta sección.", "error")
        return redirect(url_for('reports.dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            role_name = request.form['role_name'].upper()
            try:
                cursor.execute("INSERT INTO Roles (RoleName) VALUES (?)", (role_name,))
                role_id = cursor.execute("SELECT @@IDENTITY").fetchval()
                
                # Add default permissions (all off)
                menu_keys = ['dashboard', 'companies', 'users', 'roles', 'terminals', 'staff', 'warehouses', 'device_types', 'assignments', 'inventory', 'stock', 'reports']
                for key in menu_keys:
                    cursor.execute("INSERT INTO Permissions (RoleID, MenuKey, CanAccess) VALUES (?, ?, 0)", (role_id, key))
                
                conn.commit()
                flash(f"Rol '{role_name}' creado.", "success")
            except Exception as e:
                flash("Error al crear el rol.", "error")

        elif action == 'update_permissions':
            role_id = request.form['role_id']
            menu_keys = ['dashboard', 'companies', 'users', 'roles', 'terminals', 'staff', 'warehouses', 'device_types', 'assignments', 'inventory', 'stock', 'reports']
            
            try:
                for key in menu_keys:
                    val = 1 if request.form.get(f'perm_{key}') == 'on' else 0
                    cursor.execute("UPDATE Permissions SET CanAccess = ? WHERE RoleID = ? AND MenuKey = ?", (val, role_id, key))
                
                conn.commit()
                flash("Permisos actualizados.", "success")
                
                # If current user's role was updated, refresh their session permissions
                if int(role_id) == session.get('role_id'):
                    cursor.execute("SELECT MenuKey, CanAccess FROM Permissions WHERE RoleID = ?", (role_id,))
                    perms = cursor.fetchall()
                    session['permissions'] = {p.MenuKey: bool(p.CanAccess) for p in perms}
                    
            except Exception as e:
                flash("Error al actualizar los permisos.", "error")

        elif action == 'delete':
            role_id = request.form['role_id']
            if int(role_id) == session.get('role_id'):
                flash("No puede eliminar su propio rol.", "error")
            else:
                cursor.execute("DELETE FROM Roles WHERE RoleID = ?", (role_id,))
                conn.commit()
                flash("Rol eliminado.", "success")

        conn.close()
        return redirect(url_for('roles.manage_roles'))

    cursor.execute("SELECT RoleID, RoleName FROM Roles")
    roles = cursor.fetchall()
    
    # Get all permissions for display
    cursor.execute("SELECT RoleID, MenuKey, CanAccess FROM Permissions")
    all_perms_raw = cursor.fetchall()
    
    # Organize permissions by RoleID
    permissions = {}
    for p in all_perms_raw:
        if p.RoleID not in permissions:
            permissions[p.RoleID] = {}
        permissions[p.RoleID][p.MenuKey] = bool(p.CanAccess)

    cursor.execute("EXEC sp_GetTerminals")
    terminals = cursor.fetchall()
    
    conn.close()
    return render_template('roles.html', roles=roles, permissions=permissions, terminals=terminals)
