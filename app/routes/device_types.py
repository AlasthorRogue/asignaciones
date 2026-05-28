from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..database import get_db_connection
from ..utils.csrf import csrf_required
from ..utils.security import limiter

device_types_bp = Blueprint('device_types', __name__)

@device_types_bp.route('/device-types', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_device_types():
    if 'user_id' not in session: return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            if not session.get('permissions', {}).get('create_device_type'):
                flash("No tiene permisos para crear tipos de equipo.", "danger")
                return redirect(url_for('device_types.manage_device_types'))
            type_name = request.form['type_name']
            brand = request.form['brand']
            model = request.form['model']
            try:
                cursor.execute("EXEC sp_CreateDeviceType @TypeName=?, @Brand=?, @Model=?", (type_name, brand, model))
                conn.commit()
                flash("Tipo de equipo creado.", "success")
            except Exception as e:
                err_msg = str(e)
                if "UIDX_DeviceTypes_FullModel" in err_msg or "2627" in err_msg or "2601" in err_msg:
                    from flask import current_app
                    current_app.logger.warning(f"Duplicate device type: {type_name} {brand} {model} from user {session.get('user_id')}")
                    flash("Error: Esa combinación de Tipo, Marca y Modelo ya existe.", "danger")
                else:
                    flash("Error al crear el tipo de equipo.", "danger")
            
        elif action == 'update':
            if not session.get('permissions', {}).get('edit_device_type'):
                flash("No tiene permisos para editar tipos de equipo.", "danger")
                return redirect(url_for('device_types.manage_device_types'))
            device_type_id = request.form['device_type_id']
            type_name = request.form['type_name']
            brand = request.form['brand']
            model = request.form['model']
            try:
                cursor.execute("EXEC sp_UpdateDeviceType @DeviceTypeID=?, @TypeName=?, @Brand=?, @Model=?", 
                               (device_type_id, type_name, brand, model))
                conn.commit()
                flash("Tipo de equipo actualizado.", "success")
            except Exception as e:
                if "UIDX_DeviceTypes_FullModel" in str(e):
                    flash("Error: Ya existe un equipo con esa combinación de Tipo, Marca y Modelo.", "danger")
                else:
                    flash("Error al actualizar el tipo de equipo.", "danger")
            
        elif action == 'delete':
            if not session.get('permissions', {}).get('delete_device_type'):
                flash("No tiene permisos para eliminar tipos de equipo.", "danger")
                return redirect(url_for('device_types.manage_device_types'))
            device_type_id = request.form['device_type_id']
            cursor.execute("SELECT COUNT(*) FROM Assignments WHERE DeviceTypeID=?", (device_type_id,))
            if cursor.fetchone()[0] > 0:
                flash("No se puede eliminar: Existen equipos de este tipo registrados en inventario.", "danger")
            else:
                try:
                    cursor.execute("EXEC sp_DeleteDeviceType @DeviceTypeID=?", (device_type_id,))
                    conn.commit()
                    flash("Tipo de equipo eliminado.", "success")
                except Exception as e:
                    flash("Error al eliminar el tipo de equipo.", "danger")

        return redirect(url_for('device_types.manage_device_types'))

    cursor.execute("EXEC sp_GetDeviceTypes")
    device_types = cursor.fetchall()
    conn.close()
    
    return render_template('device_types.html', device_types=device_types)
