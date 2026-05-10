-- Habilitamos la extensión para poder manejar UUIDs nativamente en PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. TABLA: usuarios (No tiene dependencias, se crea primero)
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    nif_cif VARCHAR(20) UNIQUE NOT NULL,
    domicilio_fiscal TEXT NOT NULL,
    poblacion VARCHAR(100),
    provincia VARCHAR(100),
    codigo_postal VARCHAR(20),
    email VARCHAR(150) UNIQUE NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    cnae VARCHAR(10),
    iban VARCHAR(50),
    profile_picture VARCHAR(255),
    gmail_token VARCHAR(255),
    irpf_rate NUMERIC(5,4) DEFAULT 0.20,
    tarifa_hora NUMERIC(12,2) DEFAULT 0.00,
    precio_servicio NUMERIC(12,2) DEFAULT 0.00,
    desc_servicio VARCHAR(100) DEFAULT 'Servicio Base',
    precio_producto NUMERIC(12,2) DEFAULT 0.00,
    desc_producto VARCHAR(100) DEFAULT 'Producto',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. TABLA: calendario_eventos (Depende de usuarios)
CREATE TABLE IF NOT EXISTS calendario_eventos (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha TIMESTAMP WITH TIME ZONE NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT,
    tipo VARCHAR(20) DEFAULT 'personal',
    color VARCHAR(10) DEFAULT '#4a90e2',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. TABLA: clientes (Depende de usuarios)
CREATE TABLE IF NOT EXISTS clientes (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre_empresa VARCHAR(150) NOT NULL,
    nif_cif VARCHAR(20) NOT NULL,
    telefono VARCHAR(20),
    email VARCHAR(150),
    direccion_fiscal TEXT NOT NULL,
    poblacion VARCHAR(100),
    provincia VARCHAR(100),
    codigo_postal VARCHAR(20),
    direccion_comercial TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. TABLA: productos (Depende de usuarios)
CREATE TABLE IF NOT EXISTS productos (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    precio_unitario NUMERIC(12,2) NOT NULL DEFAULT 0.0,
    tipo VARCHAR(50) NOT NULL DEFAULT 'Servicio',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. TABLA: gastos (Depende de usuarios)
CREATE TABLE IF NOT EXISTS gastos (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    proveedor VARCHAR(255),
    concepto VARCHAR(255),
    importe_total NUMERIC(12,2) NOT NULL DEFAULT 0.0,
    tipo_iva NUMERIC(5,2) DEFAULT 21.00,
    url_ticket VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. TABLA: facturas (Depende de usuarios y clientes)
CREATE TABLE IF NOT EXISTS facturas (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    cliente_id UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    numero_factura_secuencial INTEGER NOT NULL,
    codigo_factura VARCHAR(50) NOT NULL,
    fecha_expedicion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento TIMESTAMP WITH TIME ZONE,
    total_base NUMERIC(12,2) NOT NULL,
    total_impuestos NUMERIC(12,2) NOT NULL,
    importe_total NUMERIC(12,2) NOT NULL,
    tipo_iva NUMERIC(5,2) DEFAULT 21.00,
    json_lineas JSONB NOT NULL,
    url_pdf VARCHAR(500),
    hash_registro VARCHAR(64) NOT NULL,
    hash_anterior VARCHAR(64),
    estado_verifactu VARCHAR(20) DEFAULT 'Pendiente',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT _usuario_num_factura_uc UNIQUE (usuario_id, numero_factura_secuencial)
);

-- 7. TABLA: presupuestos (Depende de usuarios y clientes)
CREATE TABLE IF NOT EXISTS presupuestos (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    cliente_id UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    numero_presupuesto_secuencial INTEGER NOT NULL,
    codigo_presupuesto VARCHAR(50) NOT NULL,
    fecha_expedicion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_validez TIMESTAMP WITH TIME ZONE,
    total_base NUMERIC(12,2) NOT NULL,
    total_impuestos NUMERIC(12,2) NOT NULL,
    importe_total NUMERIC(12,2) NOT NULL,
    tipo_iva NUMERIC(5,2) DEFAULT 21.00,
    json_lineas JSONB NOT NULL,
    url_pdf VARCHAR(500),
    estado VARCHAR(20) DEFAULT 'Pendiente',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT _usuario_num_presupuesto_uc UNIQUE (usuario_id, numero_presupuesto_secuencial)
);

-- 8. TABLA: subvenciones (Para RAG y búsquedas semánticas)
CREATE TABLE IF NOT EXISTS subvenciones (
    id UUID PRIMARY KEY,
    id_bdns VARCHAR(100) UNIQUE NOT NULL,
    titulo TEXT NOT NULL,
    cnae_target VARCHAR(50),
    fecha_cierre TIMESTAMP WITH TIME ZONE,
    texto_completo TEXT NOT NULL,
    embedding vector(768)
);