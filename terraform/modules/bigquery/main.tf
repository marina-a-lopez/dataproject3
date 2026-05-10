resource "google_bigquery_dataset" "raw_dataset" {
  dataset_id  = "aitonomo_raw"
  description = "Datos replicados directamente desde Cloud SQL via Datastream"
  project     = var.project_id
  location    = var.region
}

resource "google_bigquery_table" "bq_usuarios" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_usuarios"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "nombre", "type": "STRING", "mode": "NULLABLE"},
  {"name": "apellidos", "type": "STRING", "mode": "NULLABLE"},
  {"name": "nif_cif", "type": "STRING", "mode": "NULLABLE"},
  {"name": "domicilio_fiscal", "type": "STRING", "mode": "NULLABLE"},
  {"name": "poblacion", "type": "STRING", "mode": "NULLABLE"},
  {"name": "provincia", "type": "STRING", "mode": "NULLABLE"},
  {"name": "codigo_postal", "type": "STRING", "mode": "NULLABLE"},
  {"name": "email", "type": "STRING", "mode": "NULLABLE"},
  {"name": "telefono", "type": "STRING", "mode": "NULLABLE"},
  {"name": "password_hash", "type": "STRING", "mode": "NULLABLE"},
  {"name": "cnae", "type": "STRING", "mode": "NULLABLE"},
  {"name": "iae", "type": "STRING", "mode": "NULLABLE"},
  {"name": "iban", "type": "STRING", "mode": "NULLABLE"},
  {"name": "profile_picture", "type": "STRING", "mode": "NULLABLE"},
  {"name": "gmail_token", "type": "STRING", "mode": "NULLABLE"},
  {"name": "irpf_rate", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "tarifa_hora", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "precio_servicio", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "desc_servicio", "type": "STRING", "mode": "NULLABLE"},
  {"name": "precio_producto", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "desc_producto", "type": "STRING", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "bq_calendario_eventos" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_calendario_eventos"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "usuario_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "fecha", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "titulo", "type": "STRING", "mode": "NULLABLE"},
  {"name": "descripcion", "type": "STRING", "mode": "NULLABLE"},
  {"name": "tipo", "type": "STRING", "mode": "NULLABLE"},
  {"name": "color", "type": "STRING", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF

  lifecycle {
    ignore_changes = [schema]
  }
}
resource "google_bigquery_table" "bq_clientes" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_clientes"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "usuario_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "nombre_empresa", "type": "STRING", "mode": "NULLABLE"},
  {"name": "nif_cif", "type": "STRING", "mode": "NULLABLE"},
  {"name": "telefono", "type": "STRING", "mode": "NULLABLE"},
  {"name": "email", "type": "STRING", "mode": "NULLABLE"},
  {"name": "direccion_fiscal", "type": "STRING", "mode": "NULLABLE"},
  {"name": "poblacion", "type": "STRING", "mode": "NULLABLE"},
  {"name": "provincia", "type": "STRING", "mode": "NULLABLE"},
  {"name": "codigo_postal", "type": "STRING", "mode": "NULLABLE"},
  {"name": "direccion_comercial", "type": "STRING", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "bq_productos" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_productos"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "usuario_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "nombre", "type": "STRING", "mode": "NULLABLE"},
  {"name": "descripcion", "type": "STRING", "mode": "NULLABLE"},
  {"name": "precio_unitario", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "tipo", "type": "STRING", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "bq_gastos" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_gastos"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "usuario_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "fecha", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "proveedor", "type": "STRING", "mode": "NULLABLE"},
  {"name": "concepto", "type": "STRING", "mode": "NULLABLE"},
  {"name": "importe_total", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "tipo_iva", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "url_ticket", "type": "STRING", "mode": "NULLABLE"},
  {"name": "status", "type": "STRING", "mode": "NULLABLE"},
  {"name": "clarification_reason", "type": "STRING", "mode": "NULLABLE"},
  {"name": "is_deducible", "type": "BOOLEAN", "mode": "NULLABLE"},
  {"name": "porcentaje_iva", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "porcentaje_irpf", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "bq_facturas" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_facturas"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "usuario_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "cliente_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "numero_factura_secuencial", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "codigo_factura", "type": "STRING", "mode": "NULLABLE"},
  {"name": "fecha_expedicion", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "fecha_vencimiento", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "total_base", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "total_impuestos", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "importe_total", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "tipo_iva", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "json_lineas", "type": "JSON", "mode": "NULLABLE"},
  {"name": "url_pdf", "type": "STRING", "mode": "NULLABLE"},
  {"name": "hash_registro", "type": "STRING", "mode": "NULLABLE"},
  {"name": "hash_anterior", "type": "STRING", "mode": "NULLABLE"},
  {"name": "estado_verifactu", "type": "STRING", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "bq_presupuestos" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_presupuestos"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "usuario_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "cliente_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "numero_presupuesto_secuencial", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "codigo_presupuesto", "type": "STRING", "mode": "NULLABLE"},
  {"name": "fecha_expedicion", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "fecha_validez", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "total_base", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "total_impuestos", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "importe_total", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "tipo_iva", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "json_lineas", "type": "JSON", "mode": "NULLABLE"},
  {"name": "url_pdf", "type": "STRING", "mode": "NULLABLE"},
  {"name": "estado", "type": "STRING", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "bq_subvenciones" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_subvenciones"
  deletion_protection = false
  table_constraints {
    primary_key { columns = ["id"] }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "id_bdns", "type": "STRING", "mode": "NULLABLE"},
  {"name": "titulo", "type": "STRING", "mode": "NULLABLE"},
  {"name": "cnae_target", "type": "STRING", "mode": "NULLABLE"},
  {"name": "apto_autonomos", "type": "BOOLEAN", "mode": "NULLABLE"},
  {"name": "fecha_publicacion", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "fecha_cierre", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "texto_completo", "type": "STRING", "mode": "NULLABLE"},
  {"name": "embedding", "type": "STRING", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_dataset" "billing_dataset" {
  dataset_id  = "gcp_billing_export"
  description = "Dataset donde GCP volcará automáticamente los costes diarios de infraestructura"
  project     = var.project_id
  location    = "EU"
}

resource "google_bigquery_dataset" "analytics_dataset" {
  dataset_id  = "aitonomo_analytics"
  description = "Vistas analíticas y KPIs pre-calculados para inversores"
  project     = var.project_id
  location    = var.region
}

resource "google_bigquery_table" "view_investor_kpis" {
  dataset_id          = google_bigquery_dataset.analytics_dataset.dataset_id
  table_id            = "kpis_crecimiento_mensual"
  deletion_protection = false

  depends_on = [
    google_bigquery_table.bq_usuarios,
    google_bigquery_table.bq_facturas
  ]

  view {
    use_legacy_sql = false
    query          = <<EOF
      WITH usuarios_mensuales AS (
        SELECT
          DATE_TRUNC(DATE(created_at), MONTH) as mes,
          COUNT(id) as nuevos_usuarios
        FROM `${var.project_id}.${google_bigquery_dataset.raw_dataset.dataset_id}.public_usuarios`
        GROUP BY 1
      ),
      actividad_facturas AS (
        SELECT
          DATE_TRUNC(DATE(created_at), MONTH) as mes,
          COUNT(id) as facturas_generadas,
          SUM(importe_total) as volumen_gestionado_eur
        FROM `${var.project_id}.${google_bigquery_dataset.raw_dataset.dataset_id}.public_facturas`
        GROUP BY 1
      )
      SELECT
        COALESCE(u.mes, f.mes) as mes,
        COALESCE(u.nuevos_usuarios, 0) as nuevos_usuarios,
        COALESCE(f.facturas_generadas, 0) as facturas_generadas,
        COALESCE(f.volumen_gestionado_eur, 0) as gmv_gestionado_eur
      FROM usuarios_mensuales u
      FULL OUTER JOIN actividad_facturas f ON u.mes = f.mes
    EOF
  }
}
