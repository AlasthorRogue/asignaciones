from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file
from ..database import get_db_connection
from datetime import datetime
import os
from ..utils.csrf import csrf_required
from ..utils.security import validate_file_upload, MAX_UPLOAD_SIZE, limiter
from ..utils.pdf_generator import create_return_pdf

returns_bp = Blueprint('returns', __name__)


@returns_bp.route('/returns', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_returns():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            if not session.get('permissions', {}).get('create_return'):
                flash("No tiene permisos para registrar devoluciones.", "danger")
                return redirect(url_for('returns.manage_returns'))

            assignment_id = request.form.get('assignment_id')
            warehouse_id  = request.form.get('warehouse_id')
            return_date   = request.form.get('return_date')
            notes         = request.form.get('notes', '').strip() or None

            if not assignment_id or not warehouse_id:
                flash("Debe seleccionar una asignación y una bodega.", "danger")
                return redirect(url_for('returns.manage_returns'))

            if not return_date:
                return_date = datetime.now()
            else:
                return_date = datetime.strptime(return_date, '%Y-%m-%d')

            # Capture snapshot + staff RUT for the PDF
            cursor.execute("""
                SELECT
                    A.Serial,
                    ISNULL(S.FirstName + ' ' + S.LastName, W2.Name) AS StaffName,
                    ISNULL(S.RUT, '')                                AS StaffRUT,
                    RTRIM(DT.Type + ' ' + ISNULL(DT.Brand,'') + ' ' + ISNULL(DT.Model,'')) AS DeviceDescription
                FROM Assignments A
                LEFT JOIN Staff       S  ON A.StaffID      = S.StaffID
                LEFT JOIN Warehouses  W2 ON A.WarehouseID  = W2.WarehouseID
                LEFT JOIN DeviceTypes DT ON A.DeviceTypeID = DT.DeviceTypeID
                WHERE A.AssignmentID = ?
            """, (assignment_id,))
            row = cursor.fetchone()

            if not row:
                flash("La asignación seleccionada no existe.", "danger")
                conn.close()
                return redirect(url_for('returns.manage_returns'))

            serial      = row.Serial or ''
            staff_name  = row.StaffName or 'Desconocido'
            staff_rut   = row.StaffRUT or ''
            device_desc = row.DeviceDescription.strip()
            user_id     = session.get('user_id')

            # Warehouse name for the PDF
            cursor.execute("SELECT Name FROM Warehouses WHERE WarehouseID=?", (warehouse_id,))
            wrow = cursor.fetchone()
            warehouse_name = wrow.Name if wrow else ''

            try:
                cursor.execute(
                    "EXEC sp_CreateReturn @AssignmentID=?, @WarehouseID=?, @ReturnDate=?, "
                    "@UserID=?, @Notes=?, @StaffName=?, @Serial=?, @DeviceDescription=?",
                    (assignment_id, warehouse_id, return_date, user_id,
                     notes, staff_name, serial, device_desc)
                )
                row_id = cursor.fetchone()
                conn.commit()

                return_id = int(row_id.ReturnID) if row_id and row_id.ReturnID else None

                # Generate the return document automatically
                if return_id:
                    try:
                        pdf_db_path = create_return_pdf(
                            return_id=return_id,
                            staff_name=staff_name,
                            staff_rut=staff_rut,
                            device_description=device_desc,
                            serial=serial,
                            warehouse_name=warehouse_name,
                            return_date=return_date,
                            notes=notes,
                        )
                        cursor.execute(
                            "UPDATE Returns SET SignedDocumentPath=? WHERE ReturnID=?",
                            (pdf_db_path, return_id)
                        )
                        conn.commit()
                    except Exception:
                        pass  # PDF failure must not block the return itself

                # Remove the original assignment (logged to AssignmentHistory)
                cursor.execute(
                    "EXEC sp_DeleteAssignment @AssignmentID=?, @Date=?",
                    (assignment_id, return_date)
                )
                conn.commit()

                flash("Devolución registrada. El documento fue generado automáticamente.", "success")
            except Exception:
                flash("Error al registrar la devolución.", "danger")

        elif action == 'upload_document':
            if not session.get('permissions', {}).get('upload_return_document'):
                flash("No tiene permisos para subir documentos.", "danger")
                return redirect(url_for('returns.manage_returns'))

            return_id = request.form.get('return_id')
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
                            flash(f"El archivo excede el tamaño máximo de {MAX_UPLOAD_SIZE // (1024 * 1024)} MB.", "danger")
                        else:
                            filename = f"signed_return_{return_id}_{int(datetime.now().timestamp())}.pdf"
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            save_dir  = os.path.join(base_dir, 'uploads', 'signed_docs')
                            os.makedirs(save_dir, exist_ok=True)
                            save_path = os.path.join(save_dir, filename)
                            file.save(save_path)
                            db_path = f"signed_docs/{filename}"
                            cursor.execute(
                                "UPDATE Returns SET SignedDocumentPath=? WHERE ReturnID=?",
                                (db_path, return_id)
                            )
                            conn.commit()
                            flash("Documento firmado reemplazado correctamente.", "success")

        elif action == 'delete':
            if not session.get('permissions', {}).get('delete_return'):
                flash("No tiene permisos para eliminar devoluciones.", "danger")
            else:
                return_id = request.form.get('return_id')
                cursor.execute("DELETE FROM Returns WHERE ReturnID=?", (return_id,))
                conn.commit()
                flash("Devolución eliminada.", "success")

        conn.close()
        return redirect(url_for('returns.manage_returns'))

    # GET
    cursor.execute("EXEC sp_GetReturns")
    returns = cursor.fetchall()

    cursor.execute("EXEC sp_GetAssignments")
    assignments = cursor.fetchall()

    cursor.execute("SELECT WarehouseID, Name FROM Warehouses ORDER BY Name")
    warehouses = cursor.fetchall()

    conn.close()
    return render_template(
        'returns.html',
        returns=returns,
        assignments=assignments,
        warehouses=warehouses,
        now=datetime.now()
    )


@returns_bp.route('/returns/<int:return_id>/document')
def view_return_document(return_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if not session.get('permissions', {}).get('view_return_document'):
        flash("No tiene permisos para ver documentos de devolución.", "danger")
        return redirect(url_for('returns.manage_returns'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SignedDocumentPath FROM Returns WHERE ReturnID=?", (return_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row.SignedDocumentPath:
        flash("El documento aún no está disponible para esta devolución.", "warning")
        return redirect(url_for('returns.manage_returns'))

    base_dir     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir  = os.path.normpath(os.path.join(base_dir, 'uploads'))
    requested_path = os.path.normpath(os.path.join(uploads_dir, row.SignedDocumentPath))

    if not requested_path.startswith(uploads_dir):
        flash("Ruta de archivo inválida.", "danger")
        return redirect(url_for('returns.manage_returns'))

    if not os.path.exists(requested_path):
        flash("El archivo no se encuentra en el servidor.", "danger")
        return redirect(url_for('returns.manage_returns'))

    return send_file(requested_path, mimetype='application/pdf')
