from flask import Blueprint, render_template, session, redirect, url_for, request, send_file, current_app
from ..database import get_db_connection
import pandas as pd
import io
import os
from datetime import datetime


stock_bp = Blueprint('stock', __name__)

@stock_bp.route('/stock')
def view_stock():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query for aggregated stock by Device Type
    query = """
    SELECT 
        DT.TypeName,
        COUNT(A.AssignmentID) AS Total,
        SUM(CASE WHEN A.WarehouseID IS NOT NULL THEN 1 ELSE 0 END) AS InStock,
        SUM(CASE WHEN A.StaffID IS NOT NULL THEN 1 ELSE 0 END) AS Assigned
    FROM DeviceTypes DT
    LEFT JOIN Assignments A ON DT.DeviceTypeID = A.DeviceTypeID
    GROUP BY DT.TypeName
    ORDER BY DT.TypeName
    """
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    stock_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # Query for equipment assigned by terminal (through Staff)
    terminal_query = """
    SELECT 
        T.Name AS TerminalName,
        DT.TypeName,
        COUNT(A.AssignmentID) AS EquipmentCount
    FROM Assignments A
    INNER JOIN Terminals T ON A.TerminalID = T.TerminalID
    LEFT JOIN DeviceTypes DT ON A.DeviceTypeID = DT.DeviceTypeID
    GROUP BY T.Name, DT.TypeName
    ORDER BY T.Name, DT.TypeName
    """
    cursor.execute(terminal_query)
    terminal_data = cursor.fetchall()
    
    # Process terminal data for charts
    terminals = {}
    device_types = set()
    
    for row in terminal_data:
        terminal = row[0]
        device_type = row[1]
        count = row[2]
        
        if terminal not in terminals:
            terminals[terminal] = {}
        terminals[terminal][device_type] = count
        device_types.add(device_type)
    
    # Convert to lists for JSON serialization
    terminal_names = list(terminals.keys())
    device_type_list = list(device_types)
    
    # Create datasets for Chart.js
    datasets = []
    colors = ['#FF6600', '#4ecdc4', '#212A37', '#8a6b9e', '#c8b89a', '#27ae60', '#f39c12']
    
    for i, dtype in enumerate(device_type_list):
        dataset = {
            'label': dtype,
            'data': [],
            'backgroundColor': colors[i % len(colors)],
            'borderColor': colors[i % len(colors)],
            'borderWidth': 1
        }
        for terminal in terminal_names:
            dataset['data'].append(terminals.get(terminal, {}).get(dtype, 0))
        datasets.append(dataset)
    
    chart_data = {
        'terminals': terminal_names,
        'datasets': datasets
    }
    
    conn.close()
    return render_template('stock.html', stock_data=stock_data, chart_data=chart_data)

@stock_bp.route('/stock/export')
def export_stock():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    from openpyxl.styles import Font, Fill, PatternFill, Alignment, Border, Side
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT 
        DT.TypeName AS [Tipo de Dispositivo],
        COUNT(A.AssignmentID) AS [Total Global],
        SUM(CASE WHEN A.WarehouseID IS NOT NULL THEN 1 ELSE 0 END) AS [En Bodega (Stock)],
        SUM(CASE WHEN A.StaffID IS NOT NULL THEN 1 ELSE 0 END) AS [Asignado a Personal]
    FROM DeviceTypes DT
    LEFT JOIN Assignments A ON DT.DeviceTypeID = A.DeviceTypeID
    GROUP BY DT.TypeName
    ORDER BY DT.TypeName
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    conn.close()
    
    df = pd.DataFrame.from_records([list(r) for r in rows], columns=columns)
    
    # HGT Colors
    hgt_orange = 'FF6600'
    hgt_greyblue = '212A37'
    hgt_aqua = '68BFAD'
    hgt_white = 'FFFFFF'
    hgt_light_grey = 'E8E8E8'
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Resumen Stock HGT')
        
        workbook = writer.book
        worksheet = writer.sheets['Resumen Stock HGT']

        # Styles
        header_font = Font(name='Helvetica Neue LT Pro', size=11, bold=True, color=hgt_white)
        header_fill = PatternFill(start_color=hgt_greyblue, end_color=hgt_greyblue, fill_type='solid')
        data_font = Font(name='Helvetica Neue LT Pro', size=10, color=hgt_greyblue)
        thin_border = Border(
            left=Side(style='thin', color=hgt_greyblue),
            right=Side(style='thin', color=hgt_greyblue),
            top=Side(style='thin', color=hgt_greyblue),
            bottom=Side(style='thin', color=hgt_greyblue)
        )
        
        # Column widths & styles
        col_widths = [30, 15, 20, 20]
        for idx, col in enumerate(worksheet.columns):
            column_letter = col[0].column_letter
            worksheet.column_dimensions[column_letter].width = col_widths[idx] if idx < len(col_widths) else 20
            
            for cell in col:
                if cell.row == 1:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    cell.border = thin_border
                else:
                    cell.font = data_font
                    cell.border = thin_border
                    if cell.row % 2 == 0:
                        cell.fill = PatternFill(start_color=hgt_light_grey, end_color=hgt_light_grey, fill_type='solid')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'Resumen_Stock_HGT_{datetime.now().strftime("%d%m%Y")}.xlsx'
    )
