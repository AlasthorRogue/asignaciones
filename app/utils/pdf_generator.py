import os
from fpdf import FPDF
from datetime import datetime
from flask import current_app

# Brand Colors RGB
ORANGE = (255, 102, 0)
GREYBLUE = (33, 42, 55)

class HGTPDF(FPDF):
    def header(self):
        logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo_hgt_documento.png')
        
        if os.path.exists(logo_path):
            # x=10, y=8, w=45 (adjust size to fit)
            self.image(logo_path, 10, 8, 45)
        else:
            # Fallback to text if image not found
            self.set_font('helvetica', 'B', 12)
            self.set_text_color(*GREYBLUE)
            self.cell(0, 6, 'Hanseatic Global Terminals', ln=1, align='L')
        
        # Thin Grey Line (Removed as requested)
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(*GREYBLUE)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def clean_text(txt):
    if not txt:
        return ""
    # Simplest way to avoid fpdf latin-1 issues if not using full utf8 font
    return str(txt).replace("'", "").replace('"', "")

def create_assignment_pdf(staff_data, assignments, company_data):
    """Generates a responsibility contract PDF for a staff member's assignments."""
    pdf = HGTPDF()
    pdf.add_page()
    
    # Determine dynamic spacing and font size to fit on one page
    num_asn = len(assignments)
    if num_asn > 8:
        base_f = 8
        ln_s = 4
    elif num_asn > 4:
        base_f = 9
        ln_s = 5
    else:
        base_f = 10
        ln_s = 6

    # Title
    pdf.set_font('helvetica', 'B', base_f + 2)
    pdf.set_text_color(0, 0, 0)
    title = 'CONTRATO DE ENTREGA Y RESPONSABILIDAD POR DISPOSITIVOS'
    pdf.cell(0, 10, title, ln=1, align='C')
    # Underline
    w = pdf.get_string_width(title) + 6
    x = (210 - w) / 2
    pdf.line(x, pdf.get_y()-2, x+w, pdf.get_y()-2)
    pdf.ln(ln_s)
    
    # Entre
    pdf.set_font('helvetica', 'B', base_f)
    pdf.cell(0, ln_s, 'ENTRE:', ln=1, align='L')
    pdf.ln(1)

    pdf.set_font('helvetica', '', base_f)
    company_name = getattr(company_data, 'Name', 'N/A')
    company_rut = getattr(company_data, 'RUT', 'N/A')
    
    pdf.set_x(15)
    pdf.multi_cell(0, ln_s, f'1. La Empresa {company_name}, con RUT {company_rut}, en adelante "la Empresa".')
    
    staff_rut = getattr(staff_data, 'RUT', 'N/A')
    staff_fullname = f"{getattr(staff_data, 'FirstName', '')} {getattr(staff_data, 'LastName', '')}"
    staff_area = getattr(staff_data, 'WorkArea', 'N/A')
    staff_terminal = getattr(staff_data, 'TerminalName', 'N/A')
    
    pdf.set_x(15)
    pdf.multi_cell(0, ln_s, f'2. El Trabajador {staff_fullname}, con RUT {staff_rut}, perteneciente al área de {staff_area} en el terminal {staff_terminal}, en adelante "el Trabajador".')
    pdf.ln(2)

    pdf.multi_cell(0, ln_s, 'Ambas partes acuerdan celebrar el presente contrato en los siguientes términos:')
    pdf.ln(2)

    # Clausulas
    pdf.set_font('helvetica', 'B', base_f)
    pdf.cell(0, ln_s, 'CLÁUSULAS:', ln=1, align='L')
    pdf.ln(1)

    # PRIMERO
    text_primero = 'La Empresa hace entrega al Trabajador '
    text_primero += 'del siguiente dispositivo ' if len(assignments) <= 1 else 'de los siguientes dispositivos '
    text_primero += 'para el cumplimiento de sus labores:'
    
    pdf.set_font('helvetica', 'B', base_f)
    pdf.write(ln_s, 'PRIMERO: ')
    pdf.set_font('helvetica', '', base_f)
    pdf.write(ln_s, text_primero + '\n')
    pdf.ln(2)

    for asn in assignments:
        tipo = getattr(asn, 'Type', '')
        modelo = getattr(asn, 'Model', '')
        serie = getattr(asn, 'Serial', '')
        
        pdf.set_x(15)
        pdf.set_font('helvetica', '', base_f)
        bullet_text = f"{chr(149)} Dispositivo: {tipo} {modelo} (Serie: {serie})"
        pdf.multi_cell(0, ln_s - 1, bullet_text)
        pdf.ln(1)

    # SEGUNDO
    pdf.set_font('helvetica', 'B', base_f)
    pdf.write(ln_s, 'SEGUNDO: ')
    pdf.set_font('helvetica', '', base_f)
    pdf.write(ln_s, 'El Trabajador declara recibir el dispositivo en perfecto estado de funcionamiento y se compromete a:\n')
    
    pdf.set_x(15)
    pdf.multi_cell(0, ln_s - 1, '1. Utilizar correctamente el dispositivo y mantenerlo en buen estado.\n'
                          '2. Informar de inmediato a su jefatura cualquier deterioro o desperfecto causado por el transcurso del tiempo, uso normal, o fallas técnicas.\n'
                          '3. Tomar todas las medidas razonables de resguardo para evitar su pérdida, robo o daño por uso negligente.')
    pdf.ln(1)

    # TERCERO, CUARTO, QUINTO, SEXTO (Combined to save space if needed)
    clauses = [
        ('TERCERO: ', 'El trabajador se compromete a utilizar los equipos asignados siguiendo los protocolos de uso establecidos por la empresa.'),
        ('CUARTO: ', 'La Empresa se compromete a realizar las inspecciones o inventarios necesarios para verificar el estado de los bienes entregados bajo este contrato.'),
        ('QUINTO: ', 'La devolución del dispositivo deberá realizarse en las mismas condiciones en que fue entregado, salvo el desgaste natural.'),
        ('SEXTO: ', 'Este contrato es parte integrante del Reglamento Interno de la Empresa y de los acuerdos laborales vigentes.')
    ]

    for t_c, body in clauses:
        pdf.set_font('helvetica', 'B', base_f)
        pdf.write(ln_s, t_c)
        pdf.set_font('helvetica', '', base_f)
        pdf.write(ln_s, body + '\n')
        pdf.ln(1)

    # FIRMAS
    pdf.ln(2)
    pdf.set_font('helvetica', 'B', base_f)
    pdf.cell(0, ln_s, 'FIRMAS:', ln=1, align='L')
    pdf.set_font('helvetica', '', base_f)
    pdf.multi_cell(0, ln_s, 'En señal de conformidad, las partes firman el presente documento en dos ejemplares del mismo tenor y efecto.')
    pdf.ln(4)

    # Divider line
    y_div = pdf.get_y()
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.5)
    pdf.line(10, y_div, 200, y_div)
    pdf.ln(5)

    # Signatures Grid
    col_width = 95
    
    # Empresa column
    pdf.set_font('helvetica', 'B', base_f - 1)
    pdf.cell(col_width, 5, 'Por la Empresa:', ln=0, align='L')
    pdf.cell(col_width, 5, 'Por el Trabajador:', ln=1, align='L')
    
    pdf.set_font('helvetica', '', base_f - 1)
    pdf.cell(col_width, 5, 'Nombre: ALEX IGHNAIM FLORES', ln=0, align='L')
    pdf.cell(col_width, 5, f'Nombre: {staff_fullname}', ln=1, align='L')
    
    pdf.cell(col_width, 5, 'Cargo: Jefe división Tecnología', ln=0, align='L')
    pdf.cell(col_width, 5, f'RUT: {staff_rut}', ln=1, align='L')
    
    pdf.ln(10)
    y_line = pdf.get_y()
    # Signature Lines
    pdf.line(15, y_line, 85, y_line)
    pdf.line(115, y_line, 185, y_line)
    
    pdf.set_y(y_line + 1)
    pdf.set_font('helvetica', 'I', 7)
    pdf.cell(col_width, 4, 'Firma', align='C')
    pdf.cell(col_width, 4, 'Firma', ln=1, align='C')
    
    pdf.ln(2)
    current_date = datetime.now().strftime('%d/%m/%Y')
    pdf.set_font('helvetica', '', base_f - 1)
    pdf.cell(col_width, 5, f'Fecha: {current_date}', align='L')
    pdf.cell(col_width, 5, f'Fecha: {current_date}', ln=1, align='L')

    reports_dir = os.path.join(current_app.root_path, 'static', 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    staff_id = getattr(staff_data, 'StaffID', '0')
    company_id = getattr(company_data, 'CompanyID', '0')
    assignment_id_str = f"_asn_{assignments[0].AssignmentID}" if len(assignments) == 1 else "_all"
    filename = f"asignacion_staff_{staff_id}_co_{company_id}{assignment_id_str}.pdf"
    filepath = os.path.join(reports_dir, filename)
    
    pdf.output(filepath)
    return filepath
