"""
pdf_helpers.py — Funciones auxiliares para generación de PDFs de facturas y presupuestos.
Centraliza la construcción de doc_data y la generación del PDF para evitar repetición.
"""
import os
import tempfile
from invoice_generator import PremiumInvoicePDF


def build_doc_data(user, client, document, items, is_quote=False):
    """
    Construye el dict de datos que PremiumInvoicePDF necesita.
    
    Args:
        user: objeto Usuario (emisor)
        client: objeto Cliente (receptor)
        document: objeto Factura o Presupuesto
        items: lista de dicts con concepto/cantidad/precio_unitario (json_lineas)
        is_quote: True si es presupuesto, False si es factura
    
    Returns:
        dict con todos los campos para el generador de PDF
    """
    # Mapear items al formato que espera el PDF
    mapped_items = []
    for line in items:
        qty = float(line.get('cantidad', 1))
        price = float(line.get('precio_unitario', 0))
        mapped_items.append({
            "description": line.get('concepto', 'Articulo'),
            "quantity": qty,
            "unit_price": price,
            "total": qty * price
        })
    
    # Código y fecha de vencimiento dependen del tipo de documento
    if is_quote:
        doc_number = document.codigo_presupuesto.split('-')[-1]
        due_date = document.fecha_validez.strftime("%Y-%m-%d") if document.fecha_validez else None
    else:
        doc_number = document.codigo_factura.split('-')[-1]
        due_date = document.fecha_vencimiento.strftime("%Y-%m-%d") if document.fecha_vencimiento else None
    
    return {
        "invoice_number": doc_number,
        "date": document.fecha_expedicion.strftime("%Y-%m-%d"),
        "due_date": due_date,
        "client_name": client.nombre_empresa if client else "Cliente Registrado",
        "client_address": f"{client.direccion_fiscal or ''}\n{client.codigo_postal or ''} {client.poblacion or ''}".strip() if client else "",
        "client_nif": client.nif_cif if client else "",
        "client_contact": f"Email: {client.email or '-'}\nTel: {client.telefono or '-'}" if client else "",
        "items": mapped_items,
        "total_amount": float(document.total_base),
        "tax_rate": float(document.tipo_iva or 21),
        "sender_name": f"{user.nombre} {user.apellidos}",
        "sender_iban": user.iban,
        "sender_nif": user.nif_cif,
        "sender_email": user.email,
        "sender_address": f"{user.domicilio_fiscal or ''}\n{user.codigo_postal or ''} {user.poblacion or ''} {user.provincia or ''}".strip()
    }


def generate_pdf_bytes(doc_data, doc_type="FACTURA"):
    """
    Genera un PDF a partir de doc_data, devuelve los bytes y limpia el archivo temporal.
    
    Args:
        doc_data: dict construido por build_doc_data()
        doc_type: "FACTURA" o "PRESUPUESTO"
    
    Returns:
        bytes del PDF generado
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
    
    pdf = PremiumInvoicePDF(doc_data, doc_type=doc_type)
    pdf.generate(tmp_path)
    
    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()
    
    os.remove(tmp_path)
    return pdf_bytes
