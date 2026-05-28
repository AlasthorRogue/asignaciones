from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..database import get_db_connection
from ..utils.csrf import csrf_required
from ..utils.security import limiter

terminals_bp = Blueprint('terminals', __name__)

@terminals_bp.route('/terminals', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_terminals():
    if 'user_id' not in session: return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            if not session.get('permissions', {}).get('create_terminal'):
                flash("No tiene permisos para crear terminales.", "danger")
                return redirect(url_for('terminals.manage_terminals'))
            name = request.form['name']
            location = request.form['location']
            try:
                cursor.execute("EXEC sp_CreateTerminal @Name=?, @Location=?", (name, location))
                conn.commit()
                flash("Terminal creado.", "success")
            except Exception as e:
                err_msg = str(e)
                if "2627" in err_msg or "2601" in err_msg:
                    from flask import current_app
                    current_app.logger.warning(f"Duplicate terminal: {name} from user {session.get('user_id')}")
                    flash("Error: Ya existe un terminal con ese nombre.", "danger")
                else:
                    flash("Error al crear el terminal.", "danger")
            
        elif action == 'update':
            if not session.get('permissions', {}).get('edit_terminal'):
                flash("No tiene permisos para editar terminales.", "danger")
                return redirect(url_for('terminals.manage_terminals'))
            terminal_id = request.form['terminal_id']
            name = request.form['name']
            location = request.form['location']
            try:
                cursor.execute("EXEC sp_UpdateTerminal @TerminalID=?, @Name=?, @Location=?", (terminal_id, name, location))
                conn.commit()
                flash("Terminal actualizado.", "success")
            except Exception as e:
                err_msg = str(e)
                if "2627" in err_msg or "2601" in err_msg:
                    from flask import current_app
                    current_app.logger.warning(f"Duplicate terminal on update: {name} from user {session.get('user_id')}")
                    flash("Error: No se puede actualizar. El nombre ya está en uso.", "danger")
                else:
                    flash("Error al actualizar el terminal.", "danger")
            
        elif action == 'delete':
            if not session.get('permissions', {}).get('delete_terminal'):
                flash("No tiene permisos para eliminar terminales.", "danger")
                return redirect(url_for('terminals.manage_terminals'))
            terminal_id = request.form['terminal_id']
            cursor.execute("EXEC sp_DeleteTerminal @TerminalID=?", (terminal_id,))
            conn.commit()
            flash("Terminal eliminado.", "success")

        return redirect(url_for('terminals.manage_terminals'))

    cursor.execute("EXEC sp_GetTerminals")
    terminals = cursor.fetchall()
    conn.close()
    
    return render_template('terminals.html', terminals=terminals)
