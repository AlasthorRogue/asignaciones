from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app, send_file
from ..database import get_db_connection
from datetime import datetime
import os
from ..utils.csrf import csrf_required
import pyodbc
from ..utils.security import validate_file_upload, MAX_UPLOAD_SIZE, safe_error, limiter

assignments_bp = Blueprint('assignments', __name__)

@assignments_bp.route('/assignments', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_assignments():
    if 'user_id' not in session: return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            if not session.get('permissions', {}).get('create_assignment'):
                flash("No tiene permisos para crear asignaciones.", "danger")
                return redirect(url_for('assignments.manage_assignments'))
            staff_id = request.form.get('staff_id')
            warehouse_id = request.form.get('warehouse_id')
            device_type_id = request.form['device_type_id']
            serial = request.form['serial']
            asset_type = request.form.get('asset_type', 'Fijo')
            date_val = request.form.get('date')
            
            is_temp = 1 if request.form.get('is_temporary') == 'on' else 0
            ret_date = request.form.get('expected_return_date')
            
            if not date_val:
                date_val = datetime.now()
            else:
                date_val = datetime.strptime(date_val, '%Y-%m-%d')
                
            if not ret_date:
                ret_date = None
            else:
                ret_date = datetime.strptime(ret_date, '%Y-%m-%d')
                
            company_id = request.form.get('company_id')
                
            try:
                user_id = session.get('user_id')
                is_mobile = 1 if request.form.get('is_mobile') == 'on' else 0
                mobile_company = request.form.get('mobile_company')
                mobile_number = request.form.get('mobile_number')
                mobile_sim = request.form.get('mobile_sim')
                terminal_id = request.form.get('terminal_id')

                # sp_CreateAssignment ... @TerminalID
                cursor.execute("EXEC sp_CreateAssignment @StaffID=?, @WarehouseID=?, @DeviceTypeID=?, @Serial=?, @AssetType=?, @Date=?, @CompanyID=?, @IsTemporary=?, @ExpectedReturnDate=?, @UserID=?, @IsMobile=?, @MobileCompany=?, @MobileNumber=?, @MobileSIM=?, @TerminalID=?", 
                               (staff_id or None, warehouse_id or None, device_type_id, serial, asset_type, date_val, company_id, is_temp, ret_date, user_id, is_mobile, mobile_company, mobile_number, mobile_sim, terminal_id or None))
                conn.commit()
                flash("Asignación creada correctamente.", "success")
            except Exception as e:
                err_msg = str(e)
                if isinstance(e, pyodbc.Error) and len(e.args) > 1:
                    err_details = str(e.args[1])
                    if "UIDX_Assignments_GlobalSerial" in err_details or "2627" in err_details or "2601" in err_details:
                        from flask import current_app
                        current_app.logger.warning(f"Duplicate serial on create: {serial} from user {session.get('user_id')}")
                        flash("Error: Ese número de serie ya se encuentra asignado.", "danger")
                    else:
                        flash("Error de base de datos al crear la asignación.", "danger")
                else:
                    flash("Error inesperado al crear la asignación.", "danger")
        elif action == 'update':
            if not session.get('permissions', {}).get('edit_assignment'):
                flash("No tiene permisos para editar asignaciones.", "danger")
                return redirect(url_for('assignments.manage_assignments'))
            assignment_id = request.form['assignment_id']
            staff_id = request.form.get('staff_id')
            warehouse_id = request.form.get('warehouse_id')
            device_type_id = request.form['device_type_id']
            serial = request.form['serial']
            asset_type = request.form.get('asset_type', 'Fijo')
            date_val = request.form.get('date')
            if not date_val:
                date_val = datetime.now()
            else:
                date_val = datetime.strptime(date_val, '%Y-%m-%d')
            
            is_temp = 1 if request.form.get('is_temporary') == 'on' else 0
            ret_date = request.form.get('expected_return_date')
            if not ret_date:
                ret_date = None
            else:
                ret_date = datetime.strptime(ret_date, '%Y-%m-%d')
            
            company_id = request.form.get('company_id')
            
            try:
                user_id = session.get('user_id')
                is_mobile = 1 if request.form.get('is_mobile') == 'on' else 0
                mobile_company = request.form.get('mobile_company')
                mobile_number = request.form.get('mobile_number')
                mobile_sim = request.form.get('mobile_sim')
                terminal_id = request.form.get('terminal_id')

                # sp_UpdateAssignment ... @TerminalID
                cursor.execute("EXEC sp_UpdateAssignment @AssignmentID=?, @DeviceTypeID=?, @Serial=?, @Date=?, @StaffID=?, @WarehouseID=?, @AssetType=?, @CompanyID=?, @IsTemporary=?, @ExpectedReturnDate=?, @UserID=?, @IsMobile=?, @MobileCompany=?, @MobileNumber=?, @MobileSIM=?, @TerminalID=?", 
                               (assignment_id, device_type_id, serial, date_val, staff_id or None, warehouse_id or None, asset_type, company_id, is_temp, ret_date, user_id, is_mobile, mobile_company, mobile_number, mobile_sim, terminal_id or None))
                conn.commit()
                flash("Asignación actualizada.", "success")
            except Exception as e:
                if isinstance(e, pyodbc.Error):
                    flash("Error de base de datos al actualizar la asignación.", "danger")
                else:
                    flash("Error inesperado al actualizar la asignación.", "danger")
            
        elif action == 'delete':
            if not session.get('permissions', {}).get('delete_assignments'):
                flash("No tiene permisos para eliminar asignaciones.", "danger")
            else:
                assignment_id = request.form['assignment_id']
                date_val = datetime.now()
                cursor.execute("EXEC sp_DeleteAssignment @AssignmentID=?, @Date=?", (assignment_id, date_val))
                conn.commit()
                flash("Asignación eliminada.", "success")
            
        elif action == 'upload_document':
            assignment_id = request.form['assignment_id']
            if 'document' not in request.files:
                flash("No se seleccionó ningún archivo.", "danger")
            else:
                file = request.files['document']
                if file.filename == '':
                    flash("No se seleccionó ningún archivo.", "danger")
                else:
                    valid, err_msg = validate_file_upload(file, ['pdf'])
                    if not valid:
                        flash(err_msg, "danger")
                    else:
                        file.stream.seek(0, os.SEEK_END)
                        size = file.stream.tell()
                        file.stream.seek(0)
                        if size > MAX_UPLOAD_SIZE:
                            flash(f"El archivo excede el tamaño máximo de {MAX_UPLOAD_SIZE // (1024*1024)} MB.", "danger")
                        else:
                            filename = f"signed_assignment_{assignment_id}_{int(datetime.now().timestamp())}.pdf"
                            save_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'signed_docs')
                            os.makedirs(save_dir, exist_ok=True)
                            save_path = os.path.join(save_dir, filename)
                            file.save(save_path)

                            db_path = f"signed_docs/{filename}"
                            cursor.execute("UPDATE Assignments SET SignedDocumentPath=? WHERE AssignmentID=?", (db_path, assignment_id))
                            conn.commit()
                            flash("Documento firmado subido correctamente.", "success")
            
        return redirect(url_for('assignments.manage_assignments'))

    cursor.execute("EXEC sp_GetAssignments")
    assignments = cursor.fetchall()
    
    cursor.execute("EXEC sp_GetStaff")
    staff = cursor.fetchall()
    
    cursor.execute("EXEC sp_GetCompanies")
    companies = cursor.fetchall()
    
    cursor.execute("EXEC sp_GetDeviceTypes")
    device_types = cursor.fetchall()

    cursor.execute("SELECT WarehouseID, Name, TerminalID FROM Warehouses")
    warehouses = cursor.fetchall()

    cursor.execute("SELECT TerminalID, Name FROM Terminals")
    terminals = cursor.fetchall()
    
    conn.close()
    return render_template('assignments.html', assignments=assignments, staff=staff, companies=companies, device_types=device_types, warehouses=warehouses, terminals=terminals, now=datetime.now())

@assignments_bp.route('/assignments/<int:assignment_id>/data')
def assignment_data(assignment_id):
    if 'user_id' not in session:
        return {'error': 'No autorizado'}, 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            A.AssignmentID, A.StaffID, A.WarehouseID, A.TerminalID,
            A.DeviceTypeID, A.Serial, A.AssetType, A.CompanyID,
            A.IsTemporary, A.ExpectedReturnDate,
            A.IsMobile, A.MobileCompany, A.MobileNumber, A.MobileSIM,
            A.AssignmentDate
        FROM Assignments A
        WHERE A.AssignmentID = ?
    """, (assignment_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {'error': 'No encontrado'}, 404

    return {
        'AssignmentID': row.AssignmentID,
        'StaffID': str(row.StaffID or ''),
        'WarehouseID': str(row.WarehouseID or ''),
        'TerminalID': str(row.TerminalID or ''),
        'DeviceTypeID': str(row.DeviceTypeID or ''),
        'Serial': row.Serial or '',
        'AssetType': row.AssetType or 'FIJO',
        'CompanyID': str(row.CompanyID or ''),
        'IsTemporary': row.IsTemporary or False,
        'ExpectedReturnDate': row.ExpectedReturnDate.strftime('%Y-%m-%d') if row.ExpectedReturnDate else '',
        'IsMobile': 1 if row.IsMobile else 0,
        'MobileCompany': row.MobileCompany or '',
        'MobileNumber': row.MobileNumber or '',
        'MobileSIM': row.MobileSIM or '',
        'AssignmentDate': row.AssignmentDate.strftime('%Y-%m-%d') if row.AssignmentDate else ''
    }

@assignments_bp.route('/assignments/<int:assignment_id>/document')
def view_document(assignment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if not session.get('permissions', {}).get('view_document'):
        flash("No tiene permisos para ver documentos.", "danger")
        return redirect(url_for('assignments.manage_assignments'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SignedDocumentPath FROM Assignments WHERE AssignmentID=?", (assignment_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row.SignedDocumentPath:
        flash("No hay documento asociado a esta asignación.", "warning")
        return redirect(url_for('assignments.manage_assignments'))

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.normpath(os.path.join(base_dir, 'uploads'))
    requested_path = os.path.normpath(os.path.join(uploads_dir, row.SignedDocumentPath))

    if not requested_path.startswith(uploads_dir):
        flash("Ruta de archivo inválida.", "danger")
        return redirect(url_for('assignments.manage_assignments'))

    if not os.path.exists(requested_path):
        flash("El archivo no se encuentra en el servidor.", "danger")
        return redirect(url_for('assignments.manage_assignments'))

    return send_file(requested_path, mimetype='application/pdf')
