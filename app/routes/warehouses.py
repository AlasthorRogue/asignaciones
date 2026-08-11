from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..database import get_db_connection
from ..utils.csrf import csrf_required
from ..utils.security import limiter

warehouses_bp = Blueprint('warehouses', __name__)

@warehouses_bp.route('/warehouses', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_warehouses():
    if 'user_id' not in session: return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            if not session.get('permissions', {}).get('create_warehouse'):
                flash("No tiene permisos para crear bodegas.", "danger")
                return redirect(url_for('warehouses.manage_warehouses'))
            name = request.form['name']
            terminal_id = request.form['terminal_id']
            try:
                cursor.execute("INSERT INTO Warehouses (Name, TerminalID) VALUES (?, ?)", (name, terminal_id))
                conn.commit()
                flash("Bodega creada exitosamente.", "success")
            except Exception as e:
                flash("Error al crear la bodega.", "danger")
            
        elif action == 'update':
            if not session.get('permissions', {}).get('edit_warehouse'):
                flash("No tiene permisos para editar bodegas.", "danger")
                return redirect(url_for('warehouses.manage_warehouses'))
            warehouse_id = request.form['warehouse_id']
            name = request.form['name']
            terminal_id = request.form['terminal_id']
            try:
                cursor.execute("UPDATE Warehouses SET Name=?, TerminalID=? WHERE WarehouseID=?", 
                               (name, terminal_id, warehouse_id))
                conn.commit()
                flash("Bodega actualizada.", "success")
            except Exception as e:
                flash("Error al actualizar la bodega.", "danger")
            
        elif action == 'delete':
            if not session.get('permissions', {}).get('delete_warehouse'):
                flash("No tiene permisos para eliminar bodegas.", "danger")
                return redirect(url_for('warehouses.manage_warehouses'))
            warehouse_id = request.form['warehouse_id']
            try:
                # Check if there are assignments in this warehouse
                cursor.execute("SELECT COUNT(*) FROM Assignments WHERE WarehouseID=?", (warehouse_id,))
                count = cursor.fetchone()[0]
                if count > 0:
                    flash(f"No se puede eliminar: Hay {count} equipos en esta bodega. Reasígnelos primero.", "danger")
                else:
                    cursor.execute("DELETE FROM Warehouses WHERE WarehouseID=?", (warehouse_id,))
                    conn.commit()
                    flash("Bodega eliminada.", "success")
            except Exception as e:
                flash("Error al eliminar la bodega.", "danger")
            
        return redirect(url_for('warehouses.manage_warehouses'))

    cursor.execute("""
        SELECT W.WarehouseID, W.Name, T.Name AS TerminalName, W.TerminalID 
        FROM Warehouses W 
        JOIN Terminals T ON W.TerminalID = T.TerminalID
    """)
    warehouses = cursor.fetchall()
    
    cursor.execute("SELECT TerminalID, Name FROM Terminals")
    terminals = cursor.fetchall()
    
    conn.close()
    return render_template('warehouses.html', warehouses=warehouses, terminals=terminals)
