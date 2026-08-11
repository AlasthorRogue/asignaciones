from flask import Blueprint, render_template, session, redirect, url_for, request, send_file
from ..database import get_db_connection
from ..utils.pdf_generator import create_assignment_pdf
import os

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("EXEC sp_GetAssignmentHistory")
    history = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', history=history)

@reports_bp.route('/search')
def search():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("EXEC sp_GetStaff")
    staff_members = cursor.fetchall()
    
    selected_staff = request.args.get('staff_id')
    staff_data = None
    assignments = []
    
    if selected_staff:
        cursor.execute("EXEC sp_GetStaffDetailsAndAssignments @StaffID=?", (selected_staff,))
        staff_data = cursor.fetchone()
        if cursor.nextset():
            assignments = cursor.fetchall()
            
    conn.close()
    return render_template('search.html', staff_members=staff_members, staff_data=staff_data, assignments=assignments, selected_staff=int(selected_staff) if selected_staff else None)

@reports_bp.route('/pdf/<int:staff_id>')
def generate_pdf(staff_id):
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("EXEC sp_GetStaffDetailsAndAssignments @StaffID=?", (staff_id,))
    staff_data = cursor.fetchone()
    assignments = []
    if cursor.nextset():
        assignments = cursor.fetchall()
    conn.close()
    
    company_id = request.args.get('company_id', type=int)
    assignment_id = request.args.get('assignment_id', type=int)
    
    if not staff_data:
        return "Staff member not found", 404
    
    # Filter assignments by company
    filtered_assignments = [a for a in assignments if a.CompanyID == company_id]
    
    # Filter by assignment_id explicitly if provided
    if assignment_id:
        filtered_assignments = [a for a in filtered_assignments if a.AssignmentID == assignment_id]
    
    if not filtered_assignments:
        return "No assignments found for this criteria", 404
    
    # Get company info from the first filtered assignment
    company_data = type('Company', (object,), {
        'CompanyID': filtered_assignments[0].CompanyID,
        'Name': filtered_assignments[0].CompanyName,
        'RUT': filtered_assignments[0].CompanyRUT
    })
    
    pdf_path = create_assignment_pdf(staff_data, filtered_assignments, company_data)
    return send_file(pdf_path, as_attachment=True)
