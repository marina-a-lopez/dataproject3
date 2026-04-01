import os
import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime, Text, JSON, UniqueConstraint, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID

# SQLite UUID
class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value

Base = declarative_base()

class Usuario(Base):
    __tablename__ = 'usuarios'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    nif_cif = Column(String(20), unique=True, nullable=False)
    domicilio_fiscal = Column(Text, nullable=False)
    poblacion = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    codigo_postal = Column(String(20), nullable=True)
    email = Column(String(150), unique=True, nullable=False)
    telefono = Column(String(20), nullable=False)
    password_hash = Column(String(128), nullable=False) # Contraseña encriptada
    cnae = Column(String(10), nullable=True)
    iban = Column(String(50), nullable=True)
    profile_picture = Column(String(255), nullable=True)
    gmail_token = Column(String(255), nullable=True)
    irpf_rate = Column(Float, default=0.20)

    
    # Configuración de precios
    tarifa_hora = Column(Float, default=0.00)
    precio_servicio = Column(Float, default=0.00)
    desc_servicio = Column(String(100), default="Servicio Base")
    precio_producto = Column(Float, default=0.00)
    desc_producto = Column(String(100), default="Producto")
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relaciones con otras tablas
    clientes = relationship("Cliente", back_populates="usuario")
    facturas = relationship("Factura", back_populates="usuario")
    productos = relationship("Producto", back_populates="usuario")
    gastos = relationship("Gasto", back_populates="usuario", cascade="all, delete-orphan")
    eventos_calendario = relationship("CalendarioEvento", back_populates="usuario", cascade="all, delete-orphan")


class CalendarioEvento(Base):
    """Eventos del calendario del autónomo: personales, fiscales o de factura."""
    __tablename__ = 'calendario_eventos'

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(GUID(), ForeignKey('usuarios.id'), nullable=False)

    fecha = Column(DateTime, nullable=False)           # Fecha del evento
    titulo = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    tipo = Column(String(20), default='personal')      # 'fiscal' | 'personal' | 'factura'
    color = Column(String(10), default='#4a90e2')      # Hex color for UI badge

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="eventos_calendario")



class Cliente(Base):
    __tablename__ = 'clientes'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(GUID(), ForeignKey('usuarios.id'), nullable=False)
    nombre_empresa = Column(String(150), nullable=False)
    nif_cif = Column(String(20), nullable=False)
    telefono = Column(String(20))
    email = Column(String(150))
    direccion_fiscal = Column(Text, nullable=False)
    poblacion = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    codigo_postal = Column(String(20), nullable=True)
    direccion_comercial = Column(Text)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    usuario = relationship("Usuario", back_populates="clientes")
    facturas = relationship("Factura", back_populates="cliente")

class Producto(Base):
    __tablename__ = "productos"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(GUID(), ForeignKey("usuarios.id"), nullable=False)
    
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio_unitario = Column(Float, nullable=False, default=0.0)
    tipo = Column(String(50), nullable=False, default="Servicio") # 'Producto' o 'Servicio'
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    usuario = relationship("Usuario", back_populates="productos")


class Factura(Base):
    __tablename__ = 'facturas'
    __table_args__ = (
        UniqueConstraint('usuario_id', 'numero_factura_secuencial', name='_usuario_num_factura_uc'),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(GUID(), ForeignKey('usuarios.id'), nullable=False)
    cliente_id = Column(GUID(), ForeignKey('clientes.id'), nullable=False)
    numero_factura_secuencial = Column(Integer, nullable=False) # Para asegurar correlatividad
    codigo_factura = Column(String(50), nullable=False) # Ej: F-2024-001
    fecha_expedicion = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    fecha_vencimiento = Column(DateTime, nullable=True) # Used for overdue 'Moroso' status calculation
    total_base = Column(Float, nullable=False)
    total_impuestos = Column(Float, nullable=False)
    importe_total = Column(Float, nullable=False)
    json_lineas = Column(JSON, nullable=False)
    
    # VeriFactu Fields
    hash_registro = Column(String(64), nullable=False)
    hash_anterior = Column(String(64), nullable=True)
    estado_verifactu = Column(String(20), default='Pendiente') # Pendiente, Remitido, Aceptado
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    usuario = relationship("Usuario", back_populates="facturas")
    cliente = relationship("Cliente", back_populates="facturas")

class Gasto(Base):
    __tablename__ = 'gastos'
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(GUID(), ForeignKey('usuarios.id'), nullable=False)
    
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    proveedor = Column(String(255), nullable=True)
    concepto = Column(String(255), nullable=True)
    importe_total = Column(Float, nullable=False, default=0.0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    usuario = relationship("Usuario", back_populates="gastos")

# inicializar la bbdd
DB_PATH = "sqlite:///aitonomos.db"
engine = create_engine(DB_PATH, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
