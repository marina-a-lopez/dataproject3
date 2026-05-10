# Importaciones de FastAPI
import logging
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AItonomoAPI")
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import uvicorn
from pathlib import Path
import os
import tempfile
import uuid
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
import vertexai

# Cargar variables de entorno antes de inicializar Vertex AI
load_dotenv()

# Inicialización de Vertex AI (debe ocurrir antes de importar los agentes que usan GenerativeModel)
vertexai.init(
    project=os.getenv('GCP_PROJECT_ID'),
    location=os.getenv('GCP_LOCATION', 'europe-southwest1')
)

# Importaciones locales (instancian agentes que requieren Vertex AI ya inicializado)
from database import get_db, init_db, Usuario, Cliente, Factura, Presupuesto, Producto, Gasto, CalendarioEvento, Subvencion
from voice import process_voice_to_text, extract_line_data, extract_client_data
from invoice_generator import PremiumInvoicePDF
import processor as proc
from agents.extraction_agent import extraction_agent_instance
from agents.subsidies_agent import subsidies_agent_instance
from agents.rag_subsidies_agent import rag_subsidies_agent_instance
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from google.cloud import bigquery
from google.cloud import pubsub_v1
from StorageManager import StorageManager

sm = StorageManager()

app = FastAPI(title="AItonomo Pro API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear directorio static y base de datos
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
# En Cloud Run, el sistema de archivos es de solo lectura excepto /tmp.
# Intentamos crear el directorio en /tmp si falla en el directorio local, 
# o simplemente usamos el directorio local si estamos en un entorno persistente.
try:
    os.makedirs(STATIC_DIR, exist_ok=True)
except Exception:
    STATIC_DIR = Path("/tmp/static")
    os.makedirs(STATIC_DIR, exist_ok=True)
init_db()

# Configurar base de datos para Datastream (Publication y Replication Slot)
try:
    db_session = next(get_db())
    
    # 0. Otorgar permisos de replicación al usuario (Obligatorio en Cloud SQL)
    try:
        db_session.execute(text("ALTER USER admin WITH REPLICATION;"))
        db_session.commit()
    except Exception as e:
        print(f"Datastream Auth Error: {e}")
        db_session.rollback()

    # 1. Crear Publicación
    try:
        db_session.execute(text("CREATE PUBLICATION datastream_pub FOR ALL TABLES;"))
        db_session.commit()
    except Exception as e:
        print(f"Datastream Pub Error: {e}")
        db_session.rollback()
        
    # 2. Crear Slot de Replicación
    try:
        db_session.execute(text("SELECT pg_create_logical_replication_slot('datastream_slot', 'pgoutput');"))
        db_session.commit()
    except Exception as e:
        print(f"Datastream Slot Error: {e}")
        db_session.rollback()
        
    db_session.close()
except Exception as e:
    pass

# Vertex AI ya ha sido inicializado al principio del archivo

# Modelos Pydantic para peticiones JSON
class LoginRequest(BaseModel):
    dni: str
    password: str

class RegisterRequest(BaseModel):
    nombre: str
    apellidos: str
    nif_cif: str = Field(pattern=r"^[A-Z0-9]{9}$")
    domicilio: str
    poblacion: str = ""
    provincia: str = ""
    codigo_postal: str = ""
    cnae: Optional[str] = None
    iae: Optional[str] = None
    email: EmailStr
    telefono: str = Field(pattern=r"^\+?[0-9]{9,15}$")
    password: str

class ClientCreate(BaseModel):
    user_id: str
    name: str
    nif_cif: str = Field(pattern=r"^[A-Z0-9]{9}$")
    email: EmailStr
    phone: str = Field(pattern=r"^\+?[0-9]{9,15}$")
    direccion: str
    poblacion: str = ""
    provincia: str = ""
    codigo_postal: str = ""

class InvoiceCreate(BaseModel):
    user_id: str
    client_id: str
    fecha: str
    due_date: Optional[str] = None
    items: list

class ExpenseCreate(BaseModel):
    user_id: str
    fecha: str
    proveedor: str
    concepto: str
    importe_total: float
    url_ticket: str = ""
    status: str = "confirmed"
    is_deducible: bool = True
    porcentaje_iva: int = 100
    porcentaje_irpf: int = 100
    clarification_reason: Optional[str] = None

class InvoiceStatusUpdate(BaseModel):
    status: str

class QuoteCreate(BaseModel):
    user_id: str
    client_id: str
    fecha: str
    fecha_validez: Optional[str] = None
    items: list

class QuoteStatusUpdate(BaseModel):
    status: str

class ProductCreate(BaseModel):
    user_id: str
    nombre: str
    descripcion: str = ""
    precio_unitario: float
    tipo: str = "Servicio"

class ChatRequest(BaseModel):
    user_id: str
    message: str

class IRPFUpdateRequest(BaseModel):
    irpf_rate: float


# Tabla oficial 2025 de tramos de cotización de autónomos (SS)
# (rendimiento_neto_mensual_max, base_minima, cuota_minima_aprox, label_tramo)
# Cuota mínima calculada al tipo total del ~31.4% sobre la base mínima
_TRAMOS_SS_2025 = [
    (670,     653.59,  230.00, "Tramo 1 (hasta 670 €)"),
    (900,     718.95,  253.00, "Tramo 2 (670 – 900 €)"),
    (1166.7,  849.67,  299.00, "Tramo 3 (900 – 1.167 €)"),
    (1300,    950.98,  335.00, "Tramo 4 (1.167 – 1.300 €)"),
    (1500,    960.78,  338.00, "Tramo 5 (1.300 – 1.500 €)"),
    (1700,    960.78,  338.00, "Tramo 6 (1.500 – 1.700 €)"),
    (1850,   1143.79,  403.00, "Tramo 7 (1.700 – 1.850 €)"),
    (2030,   1209.15,  426.00, "Tramo 8 (1.850 – 2.030 €)"),
    (2330,   1274.51,  449.00, "Tramo 9 (2.030 – 2.330 €)"),
    (2760,   1356.21,  478.00, "Tramo 10 (2.330 – 2.760 €)"),
    (3190,   1437.91,  506.00, "Tramo 11 (2.760 – 3.190 €)"),
    (3620,   1521.61,  536.00, "Tramo 12 (3.190 – 3.620 €)"),
    (4050,   1601.31,  564.00, "Tramo 13 (3.620 – 4.050 €)"),
    (6000,   1732.03,  610.00, "Tramo 14 (4.050 – 6.000 €)"),
    (float('inf'), 1928.10, 679.00, "Tramo 15 (más de 6.000 €)"),
]

def calcular_cuota_autonomo(rendimiento_neto_mensual: float) -> dict:
    """Calcula la cuota mensual SS según el sistema de tramos 2025."""
    if rendimiento_neto_mensual <= 0:
        # Sin rendimiento positivo -> tramo 1 mínimo
        return {"cuota": 230.00, "base_cotizacion": 653.59, "tramo": "Tramo 1 (sin beneficio)", "tramo_num": 1}
    
    for i, (limite, base, cuota, label) in enumerate(_TRAMOS_SS_2025):
        if rendimiento_neto_mensual <= limite:
            return {
                "cuota": cuota,
                "base_cotizacion": base,
                "tramo": label,
                "tramo_num": i + 1
            }
    # Fallback (no deberia ocurrir)
    return {"cuota": 679.00, "base_cotizacion": 1928.10, "tramo": "Tramo 15", "tramo_num": 15}


# Funciones de autenticación
def get_user_by_dni(db: Session, nif_cif: str):
    return db.query(Usuario).filter(Usuario.nif_cif == nif_cif).first()

def get_user_by_id(db: Session, user_id: str):
    return db.query(Usuario).filter(Usuario.id == user_id).first()

@app.post("/api/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    print(f"DEBUG LOGIN - Given DNI: '{req.dni}', Given Pass: '{req.password}'")
    try:
        user = get_user_by_dni(db, req.dni)
        print(f"DEBUG LOGIN - User found in DB: {user is not None}")
        if user:
            pwd_check = check_password_hash(user.password_hash, req.password)
            print(f"DEBUG LOGIN - Password match: {pwd_check}")
            if pwd_check:
                return {"success": True, "user_id": str(user.id), "dni": user.nif_cif}
        
        print("DEBUG LOGIN - Returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG LOGIN - Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno durante el login: {str(e)}")

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}

@app.post("/api/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing_user_nif = get_user_by_dni(db, req.nif_cif)
    if existing_user_nif:
        raise HTTPException(status_code=400, detail="Este DNI/CIF ya está registrado en la base de datos principal.")
        
    existing_user_email = db.query(Usuario).filter(Usuario.email == req.email).first()
    if existing_user_email:
        raise HTTPException(status_code=400, detail="Este Email ya está registrado y tiene una cuenta activa.")
        
    hashed_pwd = generate_password_hash(req.password, method='pbkdf2:sha256')

    new_user = Usuario(
        nombre=req.nombre,
        apellidos=req.apellidos,
        nif_cif=req.nif_cif,
        domicilio_fiscal=req.domicilio,
        poblacion=req.poblacion,
        provincia=req.provincia,
        codigo_postal=req.codigo_postal,
        cnae=req.cnae,
        iae=req.iae,
        email=req.email,
        telefono=req.telefono,
        password_hash=hashed_pwd
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"success": True, "message": "Usuario creado con éxito"}

# ─── Helpers de filtrado por período ────────────────────────────────────────
from calendar import monthrange

MONTH_NAMES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
QUARTER_NAMES_ES = ["", "Q1 (Ene-Mar)", "Q2 (Abr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dic)"]

def _get_period_range(period: str, offset: int) -> tuple:
    """
    Returns (start_dt, end_dt, period_label, has_next) for a given period type and offset.
    offset=0 means current period, offset=-1 means previous, etc.
    """
    now = datetime.now(timezone.utc)

    if period == "mensual":
        year = now.year
        month = now.month + offset
        # Normalize month overflow
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        last_day = monthrange(year, month)[1]
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        label = f"{MONTH_NAMES_ES[month]} {year}"
        # has_next: can we go one forward? Only if we haven't reached current month
        has_next = (year, month) < (now.year, now.month)

    elif period == "trimestral":
        current_q = (now.month - 1) // 3 + 1
        total_q = (now.year - 2020) * 4 + current_q  # absolute quarter index from 2020
        target_q_abs = total_q + offset
        target_year = 2020 + (target_q_abs - 1) // 4
        target_q = ((target_q_abs - 1) % 4) + 1
        q_start_month = (target_q - 1) * 3 + 1
        q_end_month = q_start_month + 2
        last_day = monthrange(target_year, q_end_month)[1]
        start = datetime(target_year, q_start_month, 1, tzinfo=timezone.utc)
        end = datetime(target_year, q_end_month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        label = f"{QUARTER_NAMES_ES[target_q]} {target_year}"
        has_next = (target_year, target_q) < (now.year, current_q)

    else:  # anual
        year = now.year + offset
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        label = str(year)
        has_next = year < now.year

    return start, end, label, has_next

def _date_in_range(dt, start, end) -> bool:
    """Checks if a date (naive or aware) falls within [start, end]."""
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return start <= dt <= end

# ─── Dashboard endpoint ──────────────────────────────────────────────────────

# Funciones de dashboard y CRM (obtención de datos)
@app.get("/api/dashboard/{user_id}")
async def get_dashboard(
    user_id: str,
    period: str = "anual",
    offset: int = 0,
    db: Session = Depends(get_db)
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Compute period date range
    period_start, period_end, period_label, has_next_period = _get_period_range(period, offset)

    # Fetch ALL invoices (for overdue check + recent transactions) then split
    all_invoices = db.query(Factura).filter(Factura.usuario_id == user.id).all()
    all_gastos = db.query(Gasto).filter(Gasto.usuario_id == user.id, Gasto.status == 'confirmed').all()

    # Overdue check (always global - not period-filtered)
    current_date = datetime.now(timezone.utc)
    for invoice in all_invoices:
        if invoice.estado_verifactu in ['Pendiente', 'Enviada'] and invoice.fecha_vencimiento:
            if invoice.fecha_vencimiento.replace(tzinfo=timezone.utc) < current_date:
                invoice.estado_verifactu = 'Moroso'
    db.commit()

    clients = db.query(Cliente).filter(Cliente.usuario_id == user.id).count()

    # Filter by period
    invoices = [f for f in all_invoices if _date_in_range(f.fecha_expedicion, period_start, period_end)]
    gastos = [g for g in all_gastos if _date_in_range(g.fecha, period_start, period_end)]

    # Cálculo financiero sobre el período
    total_base_ingresos = sum(f.total_base for f in invoices if f.estado_verifactu in ['Pagada', 'Enviada'])
    total_iva_repercutido = sum(f.total_impuestos for f in invoices if f.estado_verifactu in ['Pagada', 'Enviada'])

    total_base_gastos = 0
    total_iva_soportado = 0
    
    for g in gastos:
        # Retrocompatibilidad: Si en BD está como deducible pero el motivo aclara que no lo es, se descarta.
        is_deducible_real = g.is_deducible and not (g.clarification_reason and 'no es deducible' in g.clarification_reason.lower())
        
        if is_deducible_real:
            p_iva = g.porcentaje_iva if g.porcentaje_iva is not None else 100
            p_irpf = g.porcentaje_irpf if g.porcentaje_irpf is not None else 100
            
            base_total = float(g.importe_total) / 1.21
            iva_total = float(g.importe_total) - base_total
            
            total_base_gastos += base_total * (p_irpf / 100.0)
            total_iva_soportado += iva_total * (p_iva / 100.0)

    net_balance = total_base_ingresos - total_base_gastos
    iva_a_pagar = total_iva_repercutido - total_iva_soportado

    current_irpf_rate = user.irpf_rate if user.irpf_rate is not None else 0.20
    irpf_estimado = (net_balance * current_irpf_rate) if net_balance > 0 else 0
    net_balance_after_taxes = net_balance - irpf_estimado

    # Cuota SS: always computed as monthly rendimiento neto
    # If period is "mensual" use that month's net directly. Otherwise annualise then /12.
    if period == "mensual":
        net_for_ss = net_balance
    elif period == "trimestral":
        net_for_ss = net_balance / 3
    else:
        net_for_ss = net_balance / 12 if net_balance > 0 else 0
    rendimiento_neto_mensual = (net_for_ss * 0.93) if net_for_ss > 0 else 0
    cuota_ss = calcular_cuota_autonomo(rendimiento_neto_mensual)

    total_revenue_pagadas = sum(f.importe_total for f in invoices if f.estado_verifactu == 'Pagada')
    pending_revenue = sum(f.importe_total for f in invoices if f.estado_verifactu in ['Pendiente', 'Enviada'])
    overdue_revenue = sum(f.importe_total for f in invoices if f.estado_verifactu == 'Moroso')
    total_expenses = sum(g.importe_total for g in gastos)

    # Recent transactions from the filtered period
    recent = []
    for f in invoices:
        client = db.query(Cliente).filter(Cliente.id == f.cliente_id).first()
        recent.append({
            "type": "invoice",
            "id": str(f.id),
            "date": f.fecha_expedicion.isoformat() if hasattr(f.fecha_expedicion, 'isoformat') else str(f.fecha_expedicion),
            "name": client.nombre_empresa if client else "Desconocido",
            "amount": float(f.importe_total),
            "status": f.estado_verifactu
        })
    for g in gastos:
        recent.append({
            "type": "expense",
            "id": str(g.id),
            "date": g.fecha.isoformat() if hasattr(g.fecha, 'isoformat') else str(g.fecha),
            "name": g.proveedor,
            "amount": float(g.importe_total),
            "status": "Gasto"
        })
    recent.sort(key=lambda x: x["date"], reverse=True)
    recent = recent[:10]

    return {
        "period": {
            "type": period,
            "offset": offset,
            "label": period_label,
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "has_next": has_next_period,
        },
        "metrics": {
            "total_revenue": total_revenue_pagadas,
            "pending_revenue": pending_revenue,
            "overdue_revenue": overdue_revenue,
            "total_expenses": total_expenses,
            "net_balance": net_balance,
            "net_balance_after_taxes": net_balance_after_taxes,
            "delta_revenue": f"+{len(invoices) * 2}%",
            "base_imponible_ingresos": total_base_ingresos,
            "base_imponible_gastos": total_base_gastos,
            "iva_repercutido": total_iva_repercutido,
            "iva_soportado": total_iva_soportado,
            "iva_a_pagar": iva_a_pagar,
            "irpf_estimado": irpf_estimado,
            "irpf_rate": current_irpf_rate,
            "cuota_autonomo": cuota_ss["cuota"],
            "base_cotizacion_ss": cuota_ss["base_cotizacion"],
            "tramo_ss": cuota_ss["tramo"],
            "tramo_ss_num": cuota_ss["tramo_num"],
            "rendimiento_neto_mensual": rendimiento_neto_mensual
        },
        "recent_transactions": recent,
        "clients_count": clients
    }

@app.get("/api/clients/{user_id}")
async def get_clients(user_id: str, db: Session = Depends(get_db)):
    clients = db.query(Cliente).filter(Cliente.usuario_id == user_id).all()
    return [{
        "id": str(c.id),
        "name": c.nombre_empresa,
        "nif_cif": c.nif_cif,
        "email": c.email,
        "phone": c.telefono,
        "direccion": c.direccion_fiscal,
        "poblacion": c.poblacion,
        "provincia": c.provincia,
        "codigo_postal": c.codigo_postal
    } for c in clients]

@app.post("/api/clients")
async def create_client(req: ClientCreate, db: Session = Depends(get_db)):
    # Comprueba si el cliente ya existe
    existing_client = db.query(Cliente).filter(
        Cliente.usuario_id == req.user_id,
        (Cliente.nif_cif == req.nif_cif) | (Cliente.email == req.email)
    ).first()
    
    if existing_client:
        if existing_client.nif_cif == req.nif_cif:
            raise HTTPException(status_code=400, detail="Ya tienes un cliente registrado con este NIF/CIF.")
        if existing_client.email == req.email:
            raise HTTPException(status_code=400, detail="Ya tienes un cliente registrado con este Email.")

    new_client = Cliente(
        usuario_id=req.user_id,
        nombre_empresa=req.name,
        nif_cif=req.nif_cif,
        email=req.email,
        telefono=req.phone,
        direccion_fiscal=req.direccion,
        poblacion=req.poblacion,
        provincia=req.provincia,
        codigo_postal=req.codigo_postal
    )
    db.add(new_client)
    db.commit()
    return {"success": True, "message": "Client added"}

@app.put("/api/clients/{user_id}/{client_id}")
async def update_client(user_id: str, client_id: str, req: ClientCreate, db: Session = Depends(get_db)):
    client = db.query(Cliente).filter(Cliente.usuario_id == user_id, Cliente.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    client.nombre_empresa = req.name
    client.nif_cif = req.nif_cif
    client.email = req.email
    client.telefono = req.phone
    client.direccion_fiscal = req.direccion
    client.poblacion = req.poblacion
    client.provincia = req.provincia
    client.codigo_postal = req.codigo_postal
    
    db.commit()
    return {"success": True, "message": "Client updated"}

@app.get("/api/clients/{user_id}/{client_id}")
async def get_client_profile(user_id: str, client_id: str, db: Session = Depends(get_db)):
    client = db.query(Cliente).filter(Cliente.id == client_id, Cliente.usuario_id == user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    invoices = db.query(Factura).filter(Factura.cliente_id == client.id).all()
    
    return {
        "success": True,
        "client": {
            "id": str(client.id),
            "name": client.nombre_empresa,
            "nif_cif": client.nif_cif,
            "email": client.email,
            "phone": client.telefono,
            "direccion": client.direccion_fiscal,
            "poblacion": client.poblacion,
            "provincia": client.provincia,
            "codigo_postal": client.codigo_postal,
            "created_at": client.created_at.isoformat() if client.created_at else None
        },
        "invoices": [{
            "id": str(f.id),
            "invoice_number": f.codigo_factura,
            "date": f.fecha_expedicion.isoformat(),
            "amount": f.importe_total,
            "status": f.estado_verifactu
        } for f in reversed(invoices)]
    }

@app.delete("/api/clients/{user_id}/{client_id}")
async def delete_client(user_id: str, client_id: str, db: Session = Depends(get_db)):
    client = db.query(Cliente).filter(Cliente.id == client_id, Cliente.usuario_id == user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    #Nota: Se procede sin eliminación en cascada de facturas para preservar el historial fiscal.
    #Las facturas se mantendrán en la base de datos pero el cliente_id se establecerá a null/deleted.
    db.delete(client)
    db.commit()
    return {"success": True, "message": "Cliente eliminado"}

# Facturas
@app.get("/api/invoices/{user_id}")
async def get_invoices(user_id: str, db: Session = Depends(get_db)):
    invoices = db.query(Factura).filter(Factura.usuario_id == user_id).all()
    res = []
    for f in invoices:
        client = db.query(Cliente).filter(Cliente.id == f.cliente_id).first()
        res.append({
            "id": str(f.id),
            "invoice_number": f.codigo_factura,
            "date": f.fecha_expedicion.isoformat(),
            "client_name": client.nombre_empresa if client else "Desconocido",
            "amount": f.importe_total,
            "status": f.estado_verifactu
        })
    return list(reversed(res))

@app.post("/api/invoices")
async def save_invoice(req: InvoiceCreate, db: Session = Depends(get_db)):
    user = get_user_by_id(db, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    # Obtiene el número secuencial de la última factura
    last_invoice = db.query(Factura).filter(Factura.usuario_id == req.user_id).order_by(Factura.numero_factura_secuencial.desc()).first()
    if last_invoice and last_invoice.numero_factura_secuencial is not None:
        seq_num = last_invoice.numero_factura_secuencial + 1
    else:
        seq_num = 1
    
    # Calcula los totales
    total_base = 0.0
    for item in req.items:
        total_base += float(item.get('cantidad', 1)) * float(item.get('precio_unitario', 0))
    total_impuestos = total_base * 0.21
    importe_total = total_base + total_impuestos
    
    fecha_exp = datetime.fromisoformat(req.fecha) if 'T' in req.fecha else datetime.strptime(req.fecha, "%d-%m-%Y")
    
    fecha_ven_obj = None
    if req.due_date:
        fecha_ven_obj = datetime.fromisoformat(req.due_date) if 'T' in req.due_date else datetime.strptime(req.due_date, "%d-%m-%Y")

    # Obtiene el hash del registro anterior
    prev_hash = last_invoice.hash_registro if last_invoice else None
    
    # Crea el objeto de la factura
    factura = Factura(
        usuario_id=req.user_id,
        cliente_id=req.client_id,
        numero_factura_secuencial=seq_num,
        codigo_factura=f"F-{fecha_exp.year}-{seq_num:03d}",
        fecha_expedicion=fecha_exp,
        fecha_vencimiento=fecha_ven_obj,
        total_base=total_base,
        total_impuestos=total_impuestos,
        importe_total=importe_total,
        json_lineas=req.items,
        hash_anterior=prev_hash,
        estado_verifactu='Enviada' # Establece el estado por defecto
    )
    
    factura.hash_registro = "TEMPORARY_DISABLED"
    
    db.add(factura)
    db.commit()
    db.refresh(factura)

    # --- NUEVO: Generar el PDF y subirlo al Bucket ---
    client = db.query(Cliente).filter(Cliente.id == req.client_id).first()
    
    mapped_items = []
    for item in req.items:
        qty = float(item.get('cantidad', 1))
        price = float(item.get('precio_unitario', 0))
        mapped_items.append({
            "description": item.get('concepto', 'Articulo'),
            "quantity": qty,
            "unit_price": price,
            "total": qty * price
        })
        
    # 1. Preparamos los datos para el PDF
    doc_data = {
        "invoice_number": factura.codigo_factura.split('-')[-1],
        "date": factura.fecha_expedicion.strftime("%d-%m-%Y"),
        "due_date": factura.fecha_vencimiento.strftime("%d-%m-%Y") if factura.fecha_vencimiento else None,
        "client_name": client.nombre_empresa if client else "Cliente Registrado",
        "client_address": f"{client.direccion_fiscal or ''}\n{client.codigo_postal or ''} {client.poblacion or ''}".strip() if client else "",
        "client_nif": client.nif_cif if client else "",
        "client_contact": f"Email: {client.email or '-'}\nTel: {client.telefono or '-'}" if client else "",
        "items": mapped_items,
        "total_amount": factura.total_base,
        "sender_name": f"{user.nombre} {user.apellidos}",
        "sender_iban": user.iban,
        "sender_nif": user.nif_cif,
        "sender_email": user.email,
        "sender_address": f"{user.domicilio_fiscal or ''}\n{user.codigo_postal or ''} {user.poblacion or ''} {user.provincia or ''}".strip()
    }
    
    # 2. Creamos un archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
        
    # 3. Dibujamos el PDF
    pdf = PremiumInvoicePDF(doc_data)
    pdf.generate(tmp_path)
    
    # 4. Lo leemos y se lo damos al mensajero (StorageManager)
    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()
        
    url_nube = sm.upload_file(pdf_bytes, f"invoices/{factura.codigo_factura}.pdf")
    
    # 5. Guardamos el link en la base de datos y borramos el temporal
    factura.url_pdf = url_nube
    db.commit()
    os.remove(tmp_path)


    return {"success": True, "message": "Factura guardada", "invoice_id": str(factura.id)}

# Productos
@app.get("/api/products/{user_id}")
async def get_products(user_id: str, db: Session = Depends(get_db)):
    productos = db.query(Producto).filter(Producto.usuario_id == user_id).all()
    res = []
    for p in productos:
        res.append({
            "id": str(p.id),
            "nombre": p.nombre,
            "descripcion": p.descripcion,
            "precio_unitario": p.precio_unitario,
            "tipo": p.tipo
        })
    return res

@app.post("/api/products")
async def add_product(req: ProductCreate, db: Session = Depends(get_db)):
    nuevo_producto = Producto(
        usuario_id=req.user_id,
        nombre=req.nombre,
        descripcion=req.descripcion,
        precio_unitario=req.precio_unitario,
        tipo=req.tipo
    )
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)
    return {"success": True, "message": "Producto añadido", "product_id": str(nuevo_producto.id)}

@app.put("/api/products/{user_id}/{product_id}")
async def update_product(user_id: str, product_id: str, req: ProductCreate, db: Session = Depends(get_db)):
    producto = db.query(Producto).filter(Producto.id == product_id, Producto.usuario_id == user_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    producto.nombre = req.nombre
    producto.descripcion = req.descripcion
    producto.precio_unitario = req.precio_unitario
    producto.tipo = req.tipo
    
    db.commit()
    return {"success": True, "message": "Producto actualizado"}

@app.delete("/api/products/{user_id}/{product_id}")
async def delete_product(user_id: str, product_id: str, db: Session = Depends(get_db)):
    producto = db.query(Producto).filter(Producto.id == product_id, Producto.usuario_id == user_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.delete(producto)
    db.commit()
    return {"success": True, "message": "Producto eliminado"}
@app.delete("/api/invoices/{user_id}/{invoice_id}")
async def delete_invoice(user_id: str, invoice_id: str, db: Session = Depends(get_db)):
    factura = db.query(Factura).filter(Factura.id == invoice_id, Factura.usuario_id == user_id).first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    db.delete(factura)
    db.commit()
    return {"success": True, "message": "Factura eliminada"}

@app.patch("/api/invoices/{user_id}/{invoice_id}/status")
async def update_invoice_status(user_id: str, invoice_id: str, req: InvoiceStatusUpdate, db: Session = Depends(get_db)):
    factura = db.query(Factura).filter(Factura.id == invoice_id, Factura.usuario_id == user_id).first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    factura.estado_verifactu = req.status
    db.commit()
    return {"success": True, "message": "Estado actualizado"}

# Presupuestos
@app.get("/api/quotes/{user_id}")
async def get_quotes(user_id: str, db: Session = Depends(get_db)):
    quotes = db.query(Presupuesto).filter(Presupuesto.usuario_id == user_id).all()
    res = []
    for f in quotes:
        client = db.query(Cliente).filter(Cliente.id == f.cliente_id).first()
        res.append({
            "id": str(f.id),
            "quote_number": f.codigo_presupuesto,
            "date": f.fecha_expedicion.isoformat(),
            "client_name": client.nombre_empresa if client else "Desconocido",
            "client_id": str(client.id) if client else None,
            "client_nif": client.nif_cif if client else None,
            "items": f.json_lineas,
            "amount": f.importe_total,
            "status": f.estado
        })
    return list(reversed(res))

@app.post("/api/quotes")
async def save_quote(req: QuoteCreate, db: Session = Depends(get_db)):
    user = get_user_by_id(db, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    last_quote = db.query(Presupuesto).filter(Presupuesto.usuario_id == req.user_id).order_by(Presupuesto.numero_presupuesto_secuencial.desc()).first()
    seq_num = (last_quote.numero_presupuesto_secuencial + 1) if last_quote else 1
    
    total_base = 0.0
    for item in req.items:
        total_base += float(item.get('cantidad', 1)) * float(item.get('precio_unitario', 0))
    total_impuestos = total_base * 0.21
    importe_total = total_base + total_impuestos
    
    fecha_exp = datetime.fromisoformat(req.fecha) if 'T' in req.fecha else datetime.strptime(req.fecha, "%d-%m-%Y")
    fecha_ven_obj = None
    if req.fecha_validez:
        fecha_ven_obj = datetime.fromisoformat(req.fecha_validez) if 'T' in req.fecha_validez else datetime.strptime(req.fecha_validez, "%d-%m-%Y")

    presupuesto = Presupuesto(
        usuario_id=req.user_id,
        cliente_id=req.client_id,
        numero_presupuesto_secuencial=seq_num,
        codigo_presupuesto=f"P-{fecha_exp.year}-{seq_num:03d}",
        fecha_expedicion=fecha_exp,
        fecha_validez=fecha_ven_obj,
        total_base=total_base,
        total_impuestos=total_impuestos,
        importe_total=importe_total,
        json_lineas=req.items,
        estado='Enviado'
    )
    
    db.add(presupuesto)
    db.commit()
    db.refresh(presupuesto)

    client = db.query(Cliente).filter(Cliente.id == req.client_id).first()
    mapped_items = []
    for item in req.items:
        qty = float(item.get('cantidad', 1))
        price = float(item.get('precio_unitario', 0))
        mapped_items.append({
            "description": item.get('concepto', 'Articulo'),
            "quantity": qty,
            "unit_price": price,
            "total": qty * price
        })
        
    doc_data = {
        "invoice_number": presupuesto.codigo_presupuesto.split('-')[-1],
        "date": presupuesto.fecha_expedicion.strftime("%d-%m-%Y"),
        "due_date": presupuesto.fecha_validez.strftime("%d-%m-%Y") if presupuesto.fecha_validez else None,
        "client_name": client.nombre_empresa if client else "Cliente Registrado",
        "client_address": f"{client.direccion_fiscal or ''}\n{client.codigo_postal or ''} {client.poblacion or ''}".strip() if client else "",
        "client_nif": client.nif_cif if client else "",
        "client_contact": f"Email: {client.email or '-'}\nTel: {client.telefono or '-'}" if client else "",
        "items": mapped_items,
        "total_amount": presupuesto.total_base,
        "sender_name": f"{user.nombre} {user.apellidos}",
        "sender_iban": user.iban,
        "sender_nif": user.nif_cif,
        "sender_email": user.email,
        "sender_address": f"{user.domicilio_fiscal or ''}\n{user.codigo_postal or ''} {user.poblacion or ''} {user.provincia or ''}".strip()
    }
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
        
    pdf = PremiumInvoicePDF(doc_data, doc_type="PRESUPUESTO")
    pdf.generate(tmp_path)
    
    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()
        
    url_nube = sm.upload_file(pdf_bytes, f"quotes/{presupuesto.codigo_presupuesto}.pdf")
    presupuesto.url_pdf = url_nube
    db.commit()
    os.remove(tmp_path)

    return {"success": True, "message": "Presupuesto guardado", "quote_id": str(presupuesto.id)}

@app.delete("/api/quotes/{user_id}/{quote_id}")
async def delete_quote(user_id: str, quote_id: str, db: Session = Depends(get_db)):
    presupuesto = db.query(Presupuesto).filter(Presupuesto.id == quote_id, Presupuesto.usuario_id == user_id).first()
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    db.delete(presupuesto)
    db.commit()
    return {"success": True, "message": "Presupuesto eliminado"}

@app.patch("/api/quotes/{user_id}/{quote_id}/status")
async def update_quote_status(user_id: str, quote_id: str, req: QuoteStatusUpdate, db: Session = Depends(get_db)):
    presupuesto = db.query(Presupuesto).filter(Presupuesto.id == quote_id, Presupuesto.usuario_id == user_id).first()
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    presupuesto.estado = req.status
    db.commit()
    return {"success": True, "message": "Estado actualizado"}

@app.get("/api/generate_pdf_quote/{quote_id}")
async def fetch_and_generate_pdf_quote(quote_id: str, db: Session = Depends(get_db)):
    try:
        presupuesto = db.query(Presupuesto).filter(Presupuesto.id == quote_id).first()
        if not presupuesto:
             raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
        
        if presupuesto.url_pdf:
            blob_name = f"quotes/{presupuesto.codigo_presupuesto}.pdf"
            pdf_bytes = sm.download_file(blob_name)
            if pdf_bytes:
                from fastapi import Response
                return Response(
                    content=pdf_bytes, 
                    media_type="application/pdf", 
                    headers={"Content-Disposition": f"attachment; filename={presupuesto.codigo_presupuesto}.pdf"}
                )

        usuario = db.query(Usuario).filter(Usuario.id == presupuesto.usuario_id).first()
        cliente = db.query(Cliente).filter(Cliente.id == presupuesto.cliente_id).first()
        
        mapped_items = []
        for line in presupuesto.json_lineas:
            qty = float(line.get('cantidad', 1))
            price = float(line.get('precio_unitario', 0))
            mapped_items.append({
                "description": line.get('concepto', 'Item'),
                "quantity": qty,
                "unit_price": price,
                "total": qty * price
            })
            
        doc_data = {
            "invoice_number": presupuesto.codigo_presupuesto.split('-')[-1],
            "date": presupuesto.fecha_expedicion.strftime("%d-%m-%Y"),
            "due_date": presupuesto.fecha_validez.strftime("%d-%m-%Y") if presupuesto.fecha_validez else None,
            "client_name": cliente.nombre_empresa,
            "client_address": f"{cliente.direccion_fiscal or ''}\n{cliente.codigo_postal or ''} {cliente.poblacion or ''}".strip(),
            "client_nif": cliente.nif_cif,
            "client_contact": f"Email: {cliente.email or '-'}\nTel: {cliente.telefono or '-'}",
            "items": mapped_items,
            "total_amount": float(presupuesto.total_base),
            "sender_name": f"{usuario.nombre} {usuario.apellidos}",
            "sender_iban": usuario.iban,
            "sender_nif": usuario.nif_cif,
            "sender_email": f"Email: {usuario.email}\nTel: {usuario.telefono}",
            "sender_address": f"{usuario.domicilio_fiscal or ''}\n{usuario.codigo_postal or ''} {usuario.poblacion or ''} {usuario.provincia or ''}".strip()
        }
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
            
        pdf = PremiumInvoicePDF(doc_data, doc_type="PRESUPUESTO")
        pdf.generate(tmp_path)
        
        return FileResponse(
            path=tmp_path, 
            media_type="application/pdf", 
            filename=f"{presupuesto.codigo_presupuesto}.pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF Generation Error: {e}")

# Gastos
@app.get("/api/expenses/{user_id}")
async def get_expenses(user_id: str, db: Session = Depends(get_db)):
    gastos = db.query(Gasto).filter(Gasto.usuario_id == user_id, Gasto.status == 'confirmed').order_by(Gasto.fecha.desc()).all()
    return [{
        "id": str(g.id),
        "fecha": g.fecha.strftime("%Y-%m-%d"),
        "proveedor": g.proveedor or "Varios",
        "concepto": g.concepto or "Gasto genérico",
        "importe_total": float(g.importe_total),
        "is_deducible": g.is_deducible,
        "porcentaje_iva": g.porcentaje_iva if g.porcentaje_iva is not None else 100,
        "porcentaje_irpf": g.porcentaje_irpf if g.porcentaje_irpf is not None else 100,
        "clarification_reason": g.clarification_reason
    } for g in gastos]

@app.get("/api/expense_drafts/{user_id}")
async def get_expense_drafts(user_id: str, db: Session = Depends(get_db)):
    drafts = db.query(Gasto).filter(Gasto.usuario_id == user_id, Gasto.status == 'draft').order_by(Gasto.created_at.desc()).all()
    return [{"id": str(g.id), "fecha": g.fecha.strftime("%Y-%m-%d"), "proveedor": g.proveedor or "", "concepto": g.concepto or "", "importe_total": float(g.importe_total), "url_ticket": g.url_ticket or ""} for g in drafts]

@app.patch("/api/expenses/{expense_id}/confirm")
async def confirm_expense_patch(expense_id: str, req: ExpenseCreate, db: Session = Depends(get_db)):
    gasto = db.query(Gasto).filter(Gasto.id == expense_id).first()
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    try:
        gasto.fecha = datetime.strptime(req.fecha, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except:
        pass
    gasto.proveedor = req.proveedor
    gasto.concepto = req.concepto
    gasto.importe_total = req.importe_total
    gasto.status = 'confirmed'
    db.commit()
    return {"success": True}

@app.post("/api/expenses")
async def save_expense(req: ExpenseCreate, db: Session = Depends(get_db)):
    try:
        user = db.query(Usuario).filter(Usuario.id == req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        try:
            fecha_obj = datetime.strptime(req.fecha, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except:
            fecha_obj = datetime.now(timezone.utc)
            
        nuevo_gasto = Gasto(
            usuario_id=user.id,
            fecha=fecha_obj,
            proveedor=req.proveedor,
            concepto=req.concepto,
            importe_total=req.importe_total,
            url_ticket=req.url_ticket,
            status=req.status,
            is_deducible=req.is_deducible,
            porcentaje_iva=req.porcentaje_iva,
            porcentaje_irpf=req.porcentaje_irpf,
            clarification_reason=req.clarification_reason
        )
        db.add(nuevo_gasto)
        db.commit()
        return {"success": True, "expense_id": str(nuevo_gasto.id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/expenses/{user_id}/{expense_id}")
async def delete_expense(user_id: str, expense_id: str, db: Session = Depends(get_db)):
    gasto = db.query(Gasto).filter(Gasto.id == expense_id, Gasto.usuario_id == user_id).first()
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    db.delete(gasto)
    db.commit()
    return {"success": True}

# Integraciones con IA


@app.post("/api/process_document")
async def process_document(
    file: UploadFile = File(...), 
    user_id: str = Form(None), 
    db: Session = Depends(get_db)):
    
    try:
        contents = await file.read()
        mime_type = file.content_type
        
        # Construye el contexto del catálogo para la IA si los detalles del usuario están presentes
        catalog_context = ""
        if user_id:
            productos = db.query(Producto).filter(Producto.usuario_id == user_id).all()
            if productos:
                catalog_context = "CATÁLOGO DEL USUARIO (Usa estos conceptos y precios si coinciden con lo mencionado):\n"
                for p in productos:
                    catalog_context += f"- {p.nombre}: {p.precio_unitario}€ ({p.tipo})\n"
        
        # 1. Notas de voz via GenAI
        if mime_type.startswith("audio") or mime_type == "video/mp4" or mime_type == 'audio/webm':
            text = process_voice_to_text(contents)
            client_data = extract_client_data(text)
            line_data = extract_line_data(text, catalog_context)
            
            return {
                "extracted_text": text,
                "client_name": client_data.get('nombre_empresa', ''),
                "client_nif": client_data.get('nif_cif', ''),
                "client_address": client_data.get('direccion_fiscal', ''),
                "items": line_data.get('lineas', []),
                "date": datetime.now().strftime("%d-%m-%Y")
            }
            
        # 2. PDF/Imagen via Processor.py
        data = proc.extract_invoice_data(contents, mime_type)
        if "error" in data:
            raise HTTPException(status_code=500, detail=data["error"])
        
        # Normaliza el formato de los items para el frontend
        normalized_items = []
        for i in data.get('items', []):
            normalized_items.append({
                "concepto": i.get("description", "Item"),
                "cantidad": i.get("quantity", 1),
                "precio_unitario": i.get("unit_price", 0)
            })
            
        return {
            "client_name": data.get("client_name", ""),
            "items": normalized_items,
            "date": data.get("date", datetime.now().strftime("%d-%m-%Y")),
            "total_amount": data.get("total_amount")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process_expense")
async def process_expense(file: UploadFile = File(...), user_id: str = Form(default=""), fcm_token: str = Form(default=""), db: Session = Depends(get_db)):
    """Sube el ticket a GCS, guarda draft en PostgreSQL y publica en Pub/Sub para que Dataflow procese con Gemini."""
    try:
        contents = await file.read()
        mime_type = file.content_type
        ext = os.path.splitext(file.filename)[1]
        object_name = f"expenses/ticket_{int(datetime.now().timestamp())}{ext}"
        sm.upload_file(contents, object_name)
        ticket_url = f"gs://{sm.bucket_name}/{object_name}"

        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        draft = Gasto(
            usuario_id=user.id,
            fecha=datetime.now(timezone.utc),
            importe_total=0.0,
            url_ticket=ticket_url,
            status='draft'
        )
        db.add(draft)
        db.commit()

        project_id = os.getenv("GCP_PROJECT_ID", "")
        publisher = pubsub_v1.PublisherClient()
        publisher.publish(
            publisher.topic_path(project_id, "topic-tickets"),
            json.dumps({
                "expense_id": str(draft.id),
                "user_id": user_id,
                "fcm_token": fcm_token,
                "bucket_name": sm.bucket_name,
                "object_name": object_name,
                "mime_type": mime_type,
            }).encode("utf-8")
        )

        return {"success": True, "expense_id": str(draft.id), "ticket_url": ticket_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/expense_status/{expense_id}")
async def expense_status(expense_id: str, db: Session = Depends(get_db)):
    gasto = db.query(Gasto).filter(Gasto.id == expense_id).first()
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {
        "status": gasto.status,
        "data": {
            "proveedor": gasto.proveedor or "",
            "fecha": gasto.fecha.strftime("%Y-%m-%d") if gasto.proveedor else "",
            "concepto": gasto.concepto or "",
            "importe_total": float(gasto.importe_total),
            "url_ticket": gasto.url_ticket or ""
        } if gasto.status == 'draft' and gasto.proveedor else {}
    }

@app.post("/api/v1/expenses/extract")
async def extract_expense_v1(file: UploadFile = File(...), user_id: str = Form(...), db: Session = Depends(get_db)):
    """
    Endpoint de la Fase 1 (Group 1: Data Extraction & Profiling).
    Recibe un ticket, consulta el perfil del usuario, valida contextualmente
    con Gemini 2.5 y retorna los datos y si necesita HITL (Human In The Loop).
    """
    try:
        # 1. Validar que el usuario existe en DB principal
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # 2. Leer contenido y mimetype
        contents = await file.read()
        mime_type = file.content_type

        # 3. Procesar mediante el Data Extraction Agent
        result = extraction_agent_instance.process_receipt_with_context(
            file_bytes=contents, 
            mime_type=mime_type, 
            user=user,
            db=db
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return {
            "success": True,
            "extracted_data": result.get("extracted_data"),
            "user_context_applied": result.get("user_context_applied"),
            "hitl_required": result.get("hitl_required")
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id debe ser un entero válido para el mock")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process_client_voice")
async def process_client_voice(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        text = process_voice_to_text(contents)
        client_data = extract_client_data(text)
        
        return {
            "success": True,
            "extracted_text": text,
            "data": {
                "nombre_empresa": client_data.get('nombre_empresa', ''),
                "nif_cif": client_data.get('nif_cif', ''),
                "telefono": client_data.get('telefono', ''),
                "email": client_data.get('email', ''),
                "direccion_fiscal": client_data.get('direccion_fiscal', ''),
                "provincia": "", # Infer if possible, currently simple passthrough
                "poblacion": "",
                "codigo_postal": ""
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/generate_pdf/{invoice_id}")
async def fetch_and_generate_pdf(invoice_id: str, db: Session = Depends(get_db)):
    try:
        factura = db.query(Factura).filter(Factura.id == invoice_id).first()
        if not factura:
             raise HTTPException(status_code=404, detail="Factura no encontrada")
        # SI YA TIENE LINK, LO TRAEMOS DE LA NUBE (Más rápido)
        if factura.url_pdf:
        # El nombre en la nube es invoices/F-2025-001.pdf
            blob_name = f"invoices/{factura.codigo_factura}.pdf"
            pdf_bytes = sm.download_file(blob_name)
        
            if pdf_bytes:
                from fastapi import Response
                return Response(
                    content=pdf_bytes, 
                    media_type="application/pdf", 
                    headers={"Content-Disposition": f"attachment; filename={factura.codigo_factura}.pdf"}
                )

    # SI NO TIENE LINK (Facturas viejas), LA CREAMOS     
        usuario = db.query(Usuario).filter(Usuario.id == factura.usuario_id).first()
        cliente = db.query(Cliente).filter(Cliente.id == factura.cliente_id).first()
        
        mapped_items = []
        for line in factura.json_lineas:
            qty = float(line.get('cantidad', 1))
            price = float(line.get('precio_unitario', 0))
            mapped_items.append({
                "description": line.get('concepto', 'Item'),
                "quantity": qty,
                "unit_price": price,
                "total": qty * price
            })
            
        doc_data = {
            "invoice_number": factura.codigo_factura.split('-')[-1], # e.g. "001"
            "date": factura.fecha_expedicion.strftime("%d-%m-%Y"),
            "due_date": factura.fecha_vencimiento.strftime("%d-%m-%Y") if factura.fecha_vencimiento else None,
            "client_name": cliente.nombre_empresa,
            "client_address": f"{cliente.direccion_fiscal or ''}\n{cliente.codigo_postal or ''} {cliente.poblacion or ''}".strip(),
            "client_nif": cliente.nif_cif,
            "client_contact": f"Email: {cliente.email or '-'}\nTel: {cliente.telefono or '-'}",
            "items": mapped_items,
            "total_amount": float(factura.total_base),
            "sender_name": f"{usuario.nombre} {usuario.apellidos}",
            "sender_iban": usuario.iban,
            "sender_nif": usuario.nif_cif,
            "sender_email": f"Email: {usuario.email}\nTel: {usuario.telefono}",
            "sender_address": f"{usuario.domicilio_fiscal or ''}\n{usuario.codigo_postal or ''} {usuario.poblacion or ''} {usuario.provincia or ''}".strip()
        }
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
            
        pdf = PremiumInvoicePDF(doc_data)
        pdf.generate(tmp_path)
        
        return FileResponse(
            path=tmp_path, 
            media_type="application/pdf", 
            filename=f"{factura.codigo_factura}.pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF Generation Error: {e}")

@app.post("/api/invoices/{user_id}/{invoice_id}/send")
async def send_invoice_email(user_id: str, invoice_id: str, db: Session = Depends(get_db)):
    try:
        user = get_user_by_id(db, user_id)
        if not user.gmail_token:
            raise HTTPException(status_code=400, detail="El usuario no tiene un Token de Gmail configurado en su perfil.")
        
        factura = db.query(Factura).filter(Factura.id == invoice_id).first()
        cliente = db.query(Cliente).filter(Cliente.id == factura.cliente_id).first()
        
        if not cliente.email:
            raise HTTPException(status_code=400, detail="El cliente no tiene un email configurado.")
            
        mapped_items = []
        for line in factura.json_lineas:
            qty = float(line.get('cantidad', 1))
            price = float(line.get('precio_unitario', 0))
            mapped_items.append({
                "description": line.get('concepto', 'Item'),
                "quantity": qty,
                "unit_price": price,
                "total": qty * price
            })
            
        doc_data = {
            "invoice_number": factura.codigo_factura.split('-')[-1],
            "date": factura.fecha_expedicion.strftime("%d-%m-%Y"),
            "due_date": factura.fecha_vencimiento.strftime("%d-%m-%Y") if factura.fecha_vencimiento else None,
            "client_name": cliente.nombre_empresa,
            "client_address": f"{cliente.direccion_fiscal or ''}\n{cliente.codigo_postal or ''} {cliente.poblacion or ''}".strip(),
            "client_nif": cliente.nif_cif,
            "client_contact": f"Email: {cliente.email or '-'}\nTel: {cliente.telefono or '-'}",
            "items": mapped_items,
            "total_amount": float(factura.total_base),
            "sender_name": f"{user.nombre} {user.apellidos}",
            "sender_iban": user.iban,
            "sender_nif": user.nif_cif,
            "sender_email": user.email,
            "sender_address": f"{user.domicilio_fiscal or ''}\n{user.codigo_postal or ''} {user.poblacion or ''} {user.provincia or ''}".strip()
        }
            
        
        # En lugar de fabricarlo, lo pedimos a la nube
        blob_name = f"invoices/{factura.codigo_factura}.pdf"
        pdf_content = sm.download_file(blob_name)
        
        if not pdf_content:
            # Si por algún motivo no está en la nube, lo generamos
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
             tmp_path = tmp.name
            
            pdf = PremiumInvoicePDF(doc_data)
            pdf.generate(tmp_path)
            with open(tmp_path, "rb") as f:
                pdf_content = f.read()
            os.remove(tmp_path) 

        # Build Email
        msg = MIMEMultipart()
        msg['From'] = user.email
        msg['To'] = cliente.email
        msg['Subject'] = f"Factura {factura.codigo_factura} - {user.nombre} {user.apellidos}"
        
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <p>Estimado/a {cliente.nombre_empresa},</p>
                <p>Adjunto a este correo encontrará la factura correspondiente a los últimos servicios prestados.</p>
                <ul>
                    <li><strong>Referencia:</strong> {factura.codigo_factura}</li>
                    <li><strong>Importe Total:</strong> {factura.total_base} €</li>
                    <li><strong>Fecha de Emisión:</strong> {factura.fecha_expedicion.strftime("%d/%m/%Y")}</li>
                </ul>
                <p>Si tiene cualquier duda o consulta, por favor, responda a este mismo correo.</p>
                <br>
                <p>Atentamente,</p>
                <p><strong>{user.nombre} {user.apellidos}</strong><br>{user.nif_cif}</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        
        pdf_attachment = MIMEApplication(pdf_content, _subtype="pdf")
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=f"{factura.codigo_factura}.pdf")
        msg.attach(pdf_attachment)
            
            
        # Send via SMTP
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(user.email, user.gmail_token)
        server.send_message(msg)
        server.quit()
        
        return {"success": True, "message": "Email enviado correctamente."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_with_consultant(req: ChatRequest, db: Session = Depends(get_db)):
    user = get_user_by_id(db, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    invoices = db.query(Factura).filter(Factura.usuario_id == user.id).all()
    gastos = db.query(Gasto).filter(Gasto.usuario_id == user.id).all()
    clientes = db.query(Cliente).filter(Cliente.usuario_id == user.id).all()
    
    user_context = {
        "usuario": f"{user.nombre} {user.apellidos}",
        "cnae": user.cnae,
        "resumen": {
            "total_ingresos": float(sum(f.importe_total for f in invoices)),
            "total_gastos": float(sum(g.importe_total for g in gastos)),
            "num_clientes": len(clientes)
        },
        "clientes": [
            {"nombre": c.nombre_empresa, "nif_cif": c.nif_cif, "email": c.email} for c in clientes
        ],
        "facturas_completas": [
            {
                "numero": f.codigo_factura,
                "cliente": f.cliente.nombre_empresa if f.cliente else "Desconocido",
                "fecha": f.fecha_expedicion.isoformat() if hasattr(f.fecha_expedicion, 'isoformat') else str(f.fecha_expedicion),
                "importe_base": float(f.total_base),
                "importe_total": float(f.importe_total),
                "estado": f.estado_verifactu
            } 
            for f in sorted(invoices, key=lambda x: str(x.fecha_expedicion), reverse=True)
        ],
        "gastos_completos": [
            {
                "fecha": g.fecha.isoformat() if hasattr(g.fecha, 'isoformat') else str(g.fecha), 
                "proveedor": g.proveedor, 
                "concepto": g.concepto,
                "importe": float(g.importe_total)
            }
            for g in sorted(gastos, key=lambda x: str(x.fecha), reverse=True)
        ]
    }
    
    response = proc.ask_ai_consultant(user_context, req.message)
    if "error" in response:
        raise HTTPException(status_code=500, detail=response["error"])
        
    return {"success": True, "answer": response["answer"]}

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return {
        "success": True,
        "profile": {
            "nombre": user.nombre,
            "apellidos": user.apellidos,
            "nif_cif": user.nif_cif,
            "domicilio": user.domicilio_fiscal,
            "poblacion": user.poblacion,
            "provincia": user.provincia,
            "codigo_postal": user.codigo_postal,
            "cnae": user.cnae,
            "iae": user.iae,
            "iban": user.iban,
            "gmail_token": user.gmail_token,
            "email": user.email,
            "telefono": user.telefono,
            "profile_picture": user.profile_picture,
            "desc_producto": user.desc_producto
        }
    }

@app.get("/api/subsidies/{sub_id}/details")
async def get_subsidy_details(sub_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de una subvención y una explicación generada por IA."""
    logger.info(f"Petición de detalles para ID: {sub_id}")
    sub = db.query(Subvencion).filter(Subvencion.id == sub_id).first()
    if not sub:
        sub = db.query(Subvencion).filter(Subvencion.id_bdns == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subvención no encontrada")
    try:
        ai_info = rag_subsidies_agent_instance.explain_subsidy(sub.texto_completo)
        return {
            "success": True,
            "id_bdns": sub.id_bdns,
            "titulo": sub.titulo,
            "organismo": "Ver descripción en detalles",
            "fecha_cierre": sub.fecha_cierre.isoformat() if sub.fecha_cierre else "N/A",
            "texto_completo": sub.texto_completo,
            "explicacion_ia": ai_info.get("explicacion"),
            "link_boe": ai_info.get("link_boe")
        }
    except Exception as e:
        logger.error(f"Error obteniendo detalles de subvención: {e}")
        raise HTTPException(status_code=500, detail="Error procesando detalles de la subvención")


@app.get("/api/subsidies/{user_id}")
async def get_subsidies(user_id: str, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    response = subsidies_agent_instance.get_subsidies_for_user(user, db)
    if response.get("status") == "error":
        raise HTTPException(status_code=500, detail=response.get("error"))
        
    return response

class ScrapedTextRequest(BaseModel):
    texto_sucio: str

# @app.post("/api/extract-subsidies")
# async def extract_subsidies(req: ScrapedTextRequest):
#     """
#     Recibe texto en bruto extraído mediante web scraping y usa Gemini
#     para devolver las subvenciones en un formato estructurado de texto plano.
#     """
#     if not req.texto_sucio or not req.texto_sucio.strip():
#         raise HTTPException(status_code=400, detail="El texto a procesar no puede estar vacío.")
#         
#     resultado = subsidies_extractor_instance.process_scraped_text(req.texto_sucio)
#     return {"resultado": resultado}



@app.get("/api/avatars/{filename}")
async def get_avatar(filename: str):
    try:
        avatar_bytes = sm.download_file(f"avatars/{filename}")
        if not avatar_bytes:
            raise HTTPException(status_code=404, detail="Avatar no encontrado")
        
        ext = os.path.splitext(filename)[1].lower()
        media_type = "image/jpeg"
        if ext == ".png": media_type = "image/png"
        elif ext in [".webp", ".gif"]: media_type = f"image/{ext[1:]}"
            
        from fastapi import Response
        return Response(content=avatar_bytes, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ticket/{object_path:path}")
async def get_ticket(object_path: str):
    try:
        from fastapi import Response
        file_bytes = sm.download_file(object_path)
        if not file_bytes:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        ext = os.path.splitext(object_path)[1].lower()
        media_type = "image/jpeg"
        if ext == ".png": media_type = "image/png"
        elif ext == ".pdf": media_type = "application/pdf"
        elif ext in [".webp", ".gif"]: media_type = f"image/{ext[1:]}"
        return Response(content=file_bytes, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.put("/api/profile/{user_id}/irpf")
async def update_irpf_rate(user_id: str, req: IRPFUpdateRequest, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    user.irpf_rate = req.irpf_rate
    db.commit()
    return {"success": True, "message": "Tasa de IRPF actualizada con éxito", "irpf_rate": user.irpf_rate}

@app.post("/api/profile/{user_id}")
async def update_profile(
    user_id: str,
    nombre: str = Form(...),
    apellidos: str = Form(...),
    domicilio: str = Form(...),
    nif_cif: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(...),
    poblacion: str = Form(""),
    provincia: str = Form(""),
    codigo_postal: str = Form(""),
    cnae: str = Form(""),
    iae: str = Form(""),
    iban: str = Form(""),
    gmail_token: str = Form(""),
    avatar: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    user.nombre = nombre
    user.apellidos = apellidos
    user.domicilio_fiscal = domicilio
    user.nif_cif = nif_cif
    user.email = email
    user.telefono = telefono
    user.poblacion = poblacion
    user.provincia = provincia
    user.codigo_postal = codigo_postal
    user.cnae = cnae if cnae else None
    user.iae = iae if iae else None
    if iban:
        user.iban = iban
    if gmail_token:
        user.gmail_token = gmail_token
    
    if avatar and avatar.filename:
        # Save file
        ext = os.path.splitext(avatar.filename)[1]
        filename = f"{user_id}_{int(datetime.now().timestamp())}{ext}"

        # Leemos el archivo y lo enviamos al Bucket de Google
        contenido = await avatar.read()
        url_nube = sm.upload_file(contenido, f"avatars/{filename}")
        
        # Guardamos un path relativo hacia nuestro nuevo endpoint puente
        user.profile_picture = f"/api/avatars/{filename}"
        
    db.commit()
    return {"success": True, "message": "Perfil actualizado", "profile_picture": user.profile_picture, "nombre": user.nombre}


@app.get("/api/subsidies/recommendations/{user_id}")
async def get_rag_recommendations(user_id: str, db: Session = Depends(get_db)):
    """Obtiene recomendaciones de subvenciones usando Vertex AI RAG Engine."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        recs = rag_subsidies_agent_instance.get_recommendations(user, db)
        return {"success": True, "recommendations": recs}
    except Exception as e:
        logger.error(f"Error en RAG recommendations: {e}")
        raise HTTPException(status_code=500, detail="Error procesando recomendaciones RAG")


@app.get("/api/subsidies/matching/{user_id}")
async def get_matching_subsidies(user_id: str, db: Session = Depends(get_db)):
    """Busca subvenciones en la BD que coincidan exactamente con el CNAE del usuario."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user_cnae = user.cnae
    if not user_cnae:
        return {"success": True, "subsidies": [], "message": "Usuario sin CNAE definido"}
    
    # Buscamos coincidencias en cnae_target. 
    # El scraper guarda strings tipo '6201, 6202' o similares.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    subsidies = db.query(Subvencion).filter(
        Subvencion.cnae_target.ilike(f"%{user_cnae}%")
    ).all()
    
    # Formateamos para el front, filtrando por fecha de cierre
    results = []
    for s in subsidies:
        if s.fecha_cierre:
            fecha_cierre_aware = s.fecha_cierre.replace(tzinfo=timezone.utc) if s.fecha_cierre.tzinfo is None else s.fecha_cierre
            if fecha_cierre_aware <= now:
                continue
        ai_info = rag_subsidies_agent_instance.explain_subsidy(s.texto_completo)
        results.append({
            "id": str(s.id),
            "id_bdns": s.id_bdns,
            "titulo": s.titulo,
            "cnae_target": s.cnae_target,
            "fecha_publicacion": s.fecha_publicacion.strftime("%d/%m/%Y") if s.fecha_publicacion else None,
            "fecha_cierre": s.fecha_cierre.strftime("%d/%m/%Y") if s.fecha_cierre else None,
            "importe_maximo": ai_info.get("importe_maximo"),
            "explicacion": ai_info.get("explicacion"),
            "link_boe": ai_info.get("link_boe"),
            "link_bdns": ai_info.get("link_bdns"),
        })
    
    return {"success": True, "subsidies": results}



@app.post("/api/subsidies/ingest-callback")
async def subsidy_ingest_callback(data: dict, db: Session = Depends(get_db)):
    """Endpoint llamado por la Cloud Function tras una ingesta exitosa."""
    new_sub_id = data.get("id_bdns")
    if not new_sub_id:
        return {"success": False, "message": "Falta id_bdns"}
    
    # Buscar la subvención recién insertada
    sub = db.query(Subvencion).filter(Subvencion.id_bdns == new_sub_id).first()
    if not sub:
        return {"success": False, "message": "Subvención no encontrada en BD"}
    
    # Notificar a usuarios con CNAE coincidente
    notified_count = 0
    if sub.cnae_target:
        cnaes = [c.strip() for c in sub.cnae_target.split(",")]
        for cnae in cnaes:
            matching_users = db.query(Usuario).filter(Usuario.cnae == cnae).all()
            for user in matching_users:
                # Aquí iría la lógica de envío de email o push notification
                logger.info(f"NOTIFICACIÓN: El usuario {user.email} coincide con la subvención {sub.titulo}")
                notified_count += 1
                
    return {"success": True, "notified_users": notified_count}


# ─── Calendar API ─────────────────────────────────────────────────────────────

def _get_fiscal_dates(year: int) -> list[dict]:
    """Returns the standard fiscal deadlines for Spanish autónomos in a given year."""
    events = []
    # Mod. 303 & 130 quarterly deadlines (20th of Jan, Apr, Jul, Oct)
    quarters = [
        (1, 20, "Límite Mod. 303 & 130 — Q4 del año anterior"),
        (4, 20, "Límite Mod. 303 & 130 — Q1"),
        (7, 20, "Límite Mod. 303 & 130 — Q2"),
        (10, 20, "Límite Mod. 303 & 130 — Q3"),
    ]
    for month, day, title in quarters:
        events.append({
            "id": f"fiscal-303-{year}-{month}",
            "fecha": f"{year}-{month:02d}-{day:02d}",
            "titulo": title,
            "descripcion": "Presentación trimestral de IVA (Mod. 303) e IRPF (Mod. 130) a la Agencia Tributaria.",
            "tipo": "fiscal",
            "color": "#7DB04B"
        })
    # Cuota SS — 20th of every month
    for month in range(1, 13):
        events.append({
            "id": f"fiscal-ss-{year}-{month}",
            "fecha": f"{year}-{month:02d}-20",
            "titulo": "Cuota Autónomo — Seguridad Social",
            "descripcion": "Fecha límite de ingreso de la cuota mensual de autónomos a la Seguridad Social.",
            "tipo": "fiscal",
            "color": "#7DB04B"
        })
    # Annual income tax (Renta) — June 30
    events.append({
        "id": f"fiscal-renta-{year}",
        "fecha": f"{year}-06-30",
        "titulo": "Límite Declaración de la Renta",
        "descripcion": "Fecha límite para presentar la Declaración Anual del IRPF (ejercicio anterior).",
        "tipo": "fiscal",
        "color": "#7DB04B"
    })
    return events


class EventoCreate(BaseModel):
    fecha: str           # Spanish format DD-MM-YYYY
    titulo: str
    descripcion: Optional[str] = None
    color: str = "#4a90e2"


@app.get("/api/calendar/{user_id}")
async def get_calendar(
    user_id: str,
    year: int = None,
    month: int = None,
    include_invoices: bool = True,
    db: Session = Depends(get_db)
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    now = datetime.now(timezone.utc)
    year = year or now.year
    month = month or now.month

    # Date range for the requested month
    from calendar import monthrange
    last_day = monthrange(year, month)[1]
    range_start = datetime(year, month, 1, tzinfo=timezone.utc)
    range_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    events = []

    # 1. Fiscal dates for this year
    fiscal = _get_fiscal_dates(year)
    for e in fiscal:
        e_date = datetime.fromisoformat(e["fecha"]).replace(tzinfo=timezone.utc)
        if range_start <= e_date <= range_end:
            events.append(e)

    # 2. User personal events in this month
    user_events = db.query(CalendarioEvento).filter(
        CalendarioEvento.usuario_id == user.id,
        CalendarioEvento.fecha >= range_start,
        CalendarioEvento.fecha <= range_end
    ).all()
    for ev in user_events:
        events.append({
            "id": str(ev.id),
            "fecha": ev.fecha.strftime("%d-%m-%Y"),
            "titulo": ev.titulo,
            "descripcion": ev.descripcion,
            "tipo": ev.tipo,
            "color": ev.color
        })

    # 3. Invoice due dates (if requested)
    if include_invoices:
        invoices_due = db.query(Factura).filter(
            Factura.usuario_id == user.id,
            Factura.fecha_vencimiento >= range_start,
            Factura.fecha_vencimiento <= range_end,
            Factura.estado_verifactu.in_(["Enviada", "Pendiente", "Moroso"])
        ).all()
        for f in invoices_due:
            if f.fecha_vencimiento:
                client = db.query(Cliente).filter(Cliente.id == f.cliente_id).first()
                name = client.nombre_empresa if client else "Cliente"
                events.append({
                    "id": f"invoice-{str(f.id)}",
                    "fecha": f.fecha_vencimiento.strftime("%d-%m-%Y"),
                    "titulo": f"Vencimiento: {f.codigo_factura}",
                    "descripcion": f"Factura de {name} — {f.importe_total:.2f} €",
                    "tipo": "factura",
                    "color": "#e74c3c"
                })

    return {"year": year, "month": month, "events": events}


@app.post("/api/calendar/{user_id}/evento")
async def create_calendar_event(user_id: str, evento: EventoCreate, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    fecha_dt = datetime.fromisoformat(evento.fecha).replace(tzinfo=timezone.utc)
    new_event = CalendarioEvento(
        usuario_id=user.id,
        fecha=fecha_dt,
        titulo=evento.titulo,
        descripcion=evento.descripcion,
        tipo="personal",
        color=evento.color
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return {"success": True, "id": str(new_event.id)}


@app.delete("/api/calendar/{user_id}/evento/{event_id}")
async def delete_calendar_event(user_id: str, event_id: str, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    ev = db.query(CalendarioEvento).filter(
        CalendarioEvento.id == event_id,
        CalendarioEvento.usuario_id == user.id
    ).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    db.delete(ev)
    db.commit()
    return {"success": True}

# ─── Dashboard Inversores (Conexión BQ) ───────────────────────────────────────

@app.get("/api/investor-metrics")
async def get_investor_metrics():
    try:
        client = bigquery.Client()
        project_id = client.project # Coge tu proyecto automáticamente
        
        # 1. Obtener KPIs de negocio
        query_kpis = f"""
            SELECT * FROM `{project_id}.aitonomo_analytics.kpis_crecimiento_mensual`
            ORDER BY mes ASC
        """
        results_kpis = client.query(query_kpis).result()
        
        kpis = []
        for row in results_kpis:
            kpis.append({
                "mes": row.mes.strftime("%Y-%m") if row.mes else "Desconocido",
                "nuevos_usuarios": row.nuevos_usuarios,
                "facturas_generadas": row.facturas_generadas,
                "gmv_gestionado_eur": float(row.gmv_gestionado_eur) if row.gmv_gestionado_eur else 0.0
            })
            
        # 2. Obtener costes reales de GCP (Burn Rate)
        billing_data = []
        try:
            # Usamos un wildcard (*) porque el nombre final depende del ID de tu cuenta de facturación
            query_billing = f"""
                SELECT 
                    FORMAT_TIMESTAMP('%Y-%m', usage_start_time) as mes,
                    ROUND(SUM(cost), 2) as coste_gcp
                FROM `{project_id}.gcp_billing_export.gcp_billing_export_v1_*`
                WHERE cost_type = 'regular'
                  AND currency = 'EUR'
                GROUP BY 1
                ORDER BY 1 ASC
            """
            results_billing = client.query(query_billing).result()
            for row in results_billing:
                billing_data.append({
                    "mes": row.mes,
                    "coste_gcp": float(row.coste_gcp) if row.coste_gcp else 0.0
                })
        except Exception as e:
            # Si GCP aún no ha volcado los primeros datos, devolvemos array vacío para que no crashee
            print(f"Aviso: La tabla de facturación aún no está lista en BQ: {e}")
            pass
        
        return {"success": True, "kpis": kpis, "billing": billing_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Servicio de archivos estáticos (Frontend SPA) ---
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
# Reload trigger
