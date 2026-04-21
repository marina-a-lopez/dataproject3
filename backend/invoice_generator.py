from fpdf import FPDF
from datetime import datetime

class PremiumInvoicePDF(FPDF):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.set_auto_page_break(auto=True, margin=20)
        
        # Colores corporativos (Aura Finance / Aitonomo)
        self.c_primary = (10, 25, 47)      # #0A192F
        self.c_secondary = (17, 34, 64)    # #112240
        self.c_accent = (212, 175, 55)     # #D4AF37
        self.c_text_dark = (15, 23, 42)    # #0F172A
        self.c_text_body = (51, 65, 85)    # #334155
        self.c_text_muted = (100, 116, 139)# #64748B
        self.c_danger = (239, 68, 68)      # #EF4444
        self.c_surface = (244, 247, 249)   # #F4F7F9
        self.c_white = (255, 255, 255)
        
        self.add_page()

    def header(self):
        # Logo / Nombre emisor
        self.set_y(15)
        self.set_font('Helvetica', 'B', 24)
        self.set_text_color(*self.c_primary)
        sender = self.data.get('sender_name', 'AITONOMO').upper()
        self.cell(100, 10, sender, ln=False, align='L')
        
        # Etiqueta FACTURA
        self.set_font('Helvetica', 'B', 24)
        self.set_text_color(*self.c_accent)
        self.cell(0, 10, 'FACTURA', ln=True, align='R')
        
        # Linea separadora elegante
        self.set_draw_color(*self.c_primary)
        self.set_line_width(0.5)
        self.line(10, 28, 200, 28)
        
        self.ln(5)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(*self.c_surface)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(*self.c_text_muted)
        self.cell(0, 4, 'El pago debe realizarse en un plazo de 30 dias mediante transferencia bancaria.', 0, 1, 'C')
        self.cell(0, 4, 'Gracias por su confianza en nuestros servicios.', 0, 1, 'C')

    def generate(self, output_path):
        # Datos del emisor vs Cliente
        self.set_y(35)
        
        x_start = 10
        x_client = 110
        y_current = self.get_y()
        
        # Headers DE y A:
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(*self.c_text_muted)
        
        self.set_xy(x_start, y_current)
        self.cell(90, 5, 'DE:', ln=False)
        
        self.set_xy(x_client, y_current)
        self.cell(90, 5, 'FACTURAR A:', ln=True)
        
        # Nombres
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(*self.c_primary)
        
        y_names = self.get_y()
        self.set_xy(x_start, y_names)
        sender = self.data.get('sender_name', 'Aitonomo')
        self.cell(90, 6, sender, ln=False)
        
        self.set_xy(x_client, y_names)
        client_name = self.data.get('client_name', 'Cliente Desconocido')
        self.cell(90, 6, client_name, ln=True)
        
        # Addresses
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*self.c_text_body)
        
        y_addrs = self.get_y()
        
        # Emisor info
        self.set_xy(x_start, y_addrs)
        self.multi_cell(90, 5, "Paseo de la Castellana 1, Madrid\nVAT: ES-B12345678\ncontact@aitonomo.com", align='L')
        y_emisor_end = self.get_y()
        
        # Cliente info
        self.set_xy(x_client, y_addrs)
        address = self.data.get('client_address', '')
        if address:
            self.multi_cell(90, 5, address, align='L')
        
        # Detalles de Factura (Fechas, numero) en formato tarjeta gris suave
        y_details = max(y_emisor_end, self.get_y()) + 8
        self.set_y(y_details)
        
        # Background box for Invoice Details
        self.set_fill_color(*self.c_surface)
        self.rect(10, y_details, 190, 16, 'F')
        
        self.set_y(y_details + 3)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(*self.c_text_muted)
        
        self.set_x(15)
        self.cell(50, 4, 'NO. FACTURA', ln=False)
        self.set_x(80)
        self.cell(50, 4, 'FECHA DE EMISION', ln=False)
        self.set_x(140)
        self.cell(50, 4, 'FECHA DE VTO', ln=True)
        
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*self.c_primary)
        
        self.set_x(15)
        inv_num = self.data.get('invoice_number', 'DRAFT')
        self.cell(50, 5, f"#{inv_num}", ln=False)
        
        self.set_x(80)
        fecha = self.data.get('date', datetime.now().strftime('%Y-%m-%d'))
        self.cell(50, 5, f"{fecha}", ln=False)
        
        self.set_x(140)
        vto = self.data.get('due_date', '')
        if vto:
            self.set_text_color(*self.c_danger)
            self.cell(50, 5, f"{vto}", ln=True)
        else:
            self.cell(50, 5, "-", ln=True)
            
        self.ln(12)
        
        # Tabla de items
        self.set_fill_color(*self.c_primary)
        self.set_text_color(*self.c_white)
        self.set_font('Helvetica', 'B', 9)
        
        # Cabecera oscura, texto blanco
        self.cell(90, 9, "  DESCRIPCION", 0, 0, 'L', True)
        self.cell(30, 9, "CANT", 0, 0, 'C', True)
        self.cell(35, 9, "PRECIO UNIT", 0, 0, 'R', True)
        self.cell(35, 9, "IMPORTE EUR  ", 0, 1, 'R', True)
        
        # Filas de la tabla
        self.set_font('Helvetica', '', 10)
        
        total_amount = 0.0
        items = self.data.get('items', [])
        
        fill = False
        self.set_fill_color(250, 252, 253) # Alternate subtle cyan-grey
        
        for item in items:
            description = item.get('description', 'Articulo/Servicio')
            
            def safe_float(val, default=0.0):
                try:
                    if val is None: return default
                    return float(val)
                except (ValueError, TypeError):
                    return default

            qty = safe_float(item.get('quantity'), 1.0)
            price = safe_float(item.get('unit_price'), 0.0)
            total = safe_float(item.get('total'), qty * price)
            
            self.set_text_color(*self.c_text_dark)
            self.cell(90, 10, f"  {description[:45]}", 0, 0, 'L', fill)
            self.set_text_color(*self.c_text_body)
            self.cell(30, 10, str(int(qty)), 0, 0, 'C', fill)
            self.cell(35, 10, f"{price:,.2f}", 0, 0, 'R', fill)
            self.set_text_color(*self.c_text_dark)
            self.cell(35, 10, f"{total:,.2f}  ", 0, 1, 'R', fill)
            
            total_amount += total
            fill = not fill
            
        # Linea gruesa separadora despues de items
        self.ln(2)
        self.set_draw_color(*self.c_text_muted)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)
        
        # Total extraido
        extracted_total = self.data.get('total_amount')
        try:
            final_total = float(extracted_total) if extracted_total else total_amount
        except:
            final_total = total_amount
        
        # Seccion de totales y notas de pago alineadas paralelamente
        y_totals_start = self.get_y()
        self.set_y(y_totals_start)
        
        # Columna Derecha (Subtotales y Total)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*self.c_text_muted)
        
        self.set_x(120)
        self.cell(35, 6, "Subtotal", 0, 0, 'R')
        self.cell(35, 6, f"{final_total:,.2f}", 0, 1, 'R')
        
        tax = final_total * 0.21
        self.set_x(120)
        self.cell(35, 6, "IVA (21%)", 0, 0, 'R')
        self.cell(35, 6, f"{tax:,.2f}", 0, 1, 'R')
        
        self.ln(2)
        
        # Linea encima del total
        curr_y = self.get_y()
        self.set_draw_color(*self.c_primary)
        self.set_line_width(0.7)
        self.line(130, curr_y, 200, curr_y)
        self.ln(3)
        
        # Etiqueta de total y cantidad
        self.set_x(130)
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(*self.c_primary)
        self.cell(30, 8, "TOTAL", 0, 0, 'L')
        
        self.set_text_color(*self.c_accent)
        self.cell(30, 8, f"{(final_total + tax):,.2f} EUR ", 0, 1, 'R')
        
        # Columna Izquierda (Aviso o Metodo de Pago)
        self.set_y(y_totals_start)
        self.set_x(10)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(*self.c_text_muted)
        self.cell(100, 5, "METODO DE PAGO", ln=True)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*self.c_text_body)
        
        sender_name = self.data.get('sender_name', 'Aitonomo S.L.')
        sender_iban = self.data.get('sender_iban') or 'PENDIENTE DE CONFIGURAR EN PERFIL'
        self.multi_cell(100, 5, f"Transferencia Bancaria a:\n{sender_name}\nIBAN: {sender_iban}\nRef: Factura #{self.data.get('invoice_number', 'DRAFT')}", align='L')
        
        self.output(output_path)

