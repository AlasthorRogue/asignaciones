from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..database import get_db_connection
from ..utils.csrf import csrf_required
from ..utils.security import limiter

companies_bp = Blueprint('companies', __name__)

@companies_bp.route('/companies', methods=['GET', 'POST'])
@csrf_required
@limiter.limit("20 per minute")
def manage_companies():
    if 'user_id' not in session: return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            if not session.get('permissions', {}).get('create_company'):
                flash("No tiene permisos para crear empresas.", "danger")
                return redirect(url_for('companies.manage_companies'))
            name = request.form['name']
            rut = request.form['rut']
            try:
                cursor.execute("EXEC sp_CreateCompany @Name=?, @RUT=?", (name, rut))
                conn.commit()
                flash("Empresa creada.", "success")
            except Exception as e:
                err_msg = str(e)
                if "2627" in err_msg or "2601" in err_msg:
                    from flask import current_app
                    current_app.logger.warning(f"Duplicate company: {name} / {rut} from user {session.get('user_id')}")
                    flash("Error: Ya existe una empresa con ese Nombre o RUT.", "danger")
                else:
                    flash("Error al crear la empresa.", "danger")
            
        elif action == 'update':
            if not session.get('permissions', {}).get('edit_company'):
                flash("No tiene permisos para editar empresas.", "danger")
                return redirect(url_for('companies.manage_companies'))
            company_id = request.form['company_id']
            name = request.form['name']
            rut = request.form['rut']
            try:
                cursor.execute("EXEC sp_UpdateCompany @CompanyID=?, @Name=?, @RUT=?", (company_id, name, rut))
                conn.commit()
                flash("Empresa actualizada.", "success")
            except Exception as e:
                err_msg = str(e)
                if "2627" in err_msg or "2601" in err_msg:
                    from flask import current_app
                    current_app.logger.warning(f"Duplicate company on update: {name} / {rut} from user {session.get('user_id')}")
                    flash("Error: No se pudo actualizar. El Nombre o RUT ya están en uso por otra empresa.", "danger")
                else:
                    flash("Error al actualizar la empresa.", "danger")
            
        elif action == 'delete':
            if not session.get('permissions', {}).get('delete_company'):
                flash("No tiene permisos para eliminar empresas.", "danger")
                return redirect(url_for('companies.manage_companies'))
            company_id = request.form['company_id']
            try:
                cursor.execute("EXEC sp_DeleteCompany @CompanyID=?", (company_id,))
                conn.commit()
                flash("Empresa eliminada.", "success")
            except Exception as e:
                flash("Error al eliminar la empresa. Puede tener equipos asociados.", "danger")

        return redirect(url_for('companies.manage_companies'))

    cursor.execute("EXEC sp_GetCompanies")
    companies = cursor.fetchall()
    conn.close()
    
    return render_template('companies.html', companies=companies)
