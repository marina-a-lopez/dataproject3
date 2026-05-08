terraform {
  backend "gcs" {
    bucket  = "tfstate-aitonomo"
    prefix  = "terraform/state"
  }
}

# ---------------------------------------------------------
# 0. RED PRIVADA (VPC + Private Service Access para Cloud SQL)
# ---------------------------------------------------------
resource "google_compute_network" "vpc_aitonomo" {
  name                    = "vpc-aitonomo"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet_aitonomo" {
  name          = "subnet-aitonomo"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc_aitonomo.id
}

# Rango de IPs reservado para el peering con los servicios de Google (Cloud SQL)
resource "google_compute_global_address" "private_ip_range" {
  name          = "private-ip-range-aitonomo"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_aitonomo.id
}

# Peering entre nuestra VPC y la red interna de Google (necesario para Cloud SQL privado)
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_aitonomo.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

resource "google_storage_bucket" "document_bucket" {
  name          = "bucket-aitonomo-docs"
  location      = var.region
  force_destroy = false
}

resource "google_pubsub_topic" "topic_tickets" {
  name = "topic-tickets"
}

resource "google_pubsub_subscription" "sub_tickets" {
  name  = "sub-tickets"
  topic = google_pubsub_topic.topic_tickets.name

  # Tiempo que tiene Dataflow para confirmar que ha procesado el mensaje antes de reintentar
  ack_deadline_seconds       = 60
  message_retention_duration = "604800s" # 7 días
}

# bd en cloud sql con ip privada

# data "google_compute_network" "vpc_aitonomo" {
#   name    = "vpc-aitonomo"
#   project = var.project_id
# }

resource "google_sql_database_instance" "postgres_instance" {
  name = "db-aitonomo"
  region = var.region
  database_version = "POSTGRES_17"
  deletion_protection = true
  settings {
    tier = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size = 100
    disk_autoresize = true
    edition           = "ENTERPRISE"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc_aitonomo.id
      enable_private_path_for_google_cloud_services = true
    }

    # Obligatorio para que Datastream pueda leer los cambios (CDC)
    database_flags {
      name  = "cloudsql.logical_decoding"
      value = "on"
    }
   }
  depends_on = [google_service_networking_connection.private_vpc_connection]
  }
  # lifecycle {
  #   prevent_destroy = true
  #   }

# resource "random_password" "db_password" {
#   length = 16
#   special = true
#   override_special = "!#$%&*()-_=+[]{}<>:?"
# }

resource "google_sql_user" "postgres_user" {
  name = "admin"
  instance = google_sql_database_instance.postgres_instance.name
  # password = random_password.db_password.result
  password = var.postgres_password
}

resource "google_sql_database" "aitonomo_db" {
  name = "aitonomo_db"
  instance = google_sql_database_instance.postgres_instance.name
}





# ---------------------------------------------------------
# 1. ALMACÉN DE IMÁGENES (Artifact Registry)
# ---------------------------------------------------------
resource "google_artifact_registry_repository" "repo_aitonomo" {
  location      = var.region
  repository_id = "repo-aitonomo"
  format        = "DOCKER"
}

# ---------------------------------------------------------
# 2. HASHES (Para que Terraform detecte si cambiaste código)
# ---------------------------------------------------------
locals {
  backend_hash  = sha1(join("", [for f in fileset("${path.module}/../backend", "**") : filesha1("${path.module}/../backend/${f}")]))
  frontend_hash = sha1(join("", [for f in fileset("${path.module}/../static", "**") : filesha1("${path.module}/../static/${f}")]))
  dashboard_hash = sha1(join("", [for f in fileset("${path.module}/../dashboard-buss", "**") : filesha1("${path.module}/../dashboard-buss/${f}")]))
}

# ---------------------------------------------------------
# 3. BACKEND: Crear Imagen, Subirla y Desplegar Cloud Run
# ---------------------------------------------------------
resource "docker_image" "backend_image" {
  name = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo_aitonomo.name}/backend:${local.backend_hash}"
  build {
    context    = "../backend/"
    dockerfile = "Dockerfile"
    platform   = "linux/amd64"
  }
}

resource "docker_registry_image" "backend_push" {
  name          = docker_image.backend_image.name
  keep_remotely = true
}

resource "google_cloud_run_v2_service" "backend_cloud_run" {
  name     = "api-backend"
  location = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.backend_sa.email

    vpc_access {
      network_interfaces {
        network    = google_compute_network.vpc_aitonomo.id
        subnetwork = google_compute_subnetwork.subnet_aitonomo.id
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres_instance.connection_name]
      }
    }

    containers {
      image = docker_registry_image.backend_push.name
      ports {
        container_port = 8080
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      env {
        name  = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_BUCKET_NAME"
        value = google_storage_bucket.document_bucket.name
      }
    }
  }
  depends_on = [docker_registry_image.backend_push]
}

# ---------------------------------------------------------
# 4. FRONTEND: Crear Imagen, Subirla y Desplegar Cloud Run
# ---------------------------------------------------------
resource "docker_image" "frontend_image" {
  name = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo_aitonomo.name}/frontend:${local.frontend_hash}"
  build {
    context    = "../static/"
    dockerfile = "Dockerfile"
    platform   = "linux/amd64"
  }
}

resource "docker_registry_image" "frontend_push" {
  name          = docker_image.frontend_image.name
  keep_remotely = true
}

resource "google_cloud_run_v2_service" "frontend_cloud_run" {
  name     = "web-frontend"
  location = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.frontend_sa.email
    containers {
      image = docker_registry_image.frontend_push.name
      ports {
        container_port = 80
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend_cloud_run.uri
      }
    }
  }
  depends_on = [docker_registry_image.frontend_push]
}

# ---------------------------------------------------------
# 4.5. DASHBOARD INVERSORES: Crear Imagen React y Desplegar
# ---------------------------------------------------------
resource "docker_image" "dashboard_image" {
  name = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo_aitonomo.name}/dashboard:${local.dashboard_hash}"
  build {
    context    = "../dashboard-buss/"
    dockerfile = "Dockerfile"
    platform   = "linux/amd64"
  }
}

resource "docker_registry_image" "dashboard_push" {
  name          = docker_image.dashboard_image.name
  keep_remotely = true
}

resource "google_cloud_run_v2_service" "dashboard_cloud_run" {
  name     = "investor-dashboard"
  location = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.frontend_sa.email
    containers {
      image = docker_registry_image.dashboard_push.name
      ports {
        container_port = 80
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend_cloud_run.uri
      }
    }
  }
  depends_on = [docker_registry_image.dashboard_push]
}

# ---------------------------------------------------------
# 5. OUTPUTS (Para ver las URLs al final)
# ---------------------------------------------------------
output "url_backend" {
  value = google_cloud_run_v2_service.backend_cloud_run.uri
}

output "url_frontend" {
  value = google_cloud_run_v2_service.frontend_cloud_run.uri
}

output "url_dashboard" {
  value = google_cloud_run_v2_service.dashboard_cloud_run.uri
}

# ---------------------------------------------------------
# 6. GOOGLE SECRET MANAGER (Seguridad de Variables)
# ---------------------------------------------------------

# resource "google_secret_manager_secret" "gemini_api_key" {
#   secret_id = "gemini-api-key"
#   replication {
#     auto {}
#   }
# }

# resource "google_secret_manager_secret_version" "gemini_api_key_version" {
#   secret      = google_secret_manager_secret.gemini_api_key.id
#   secret_data = var.gemini_api_key
# }

resource "google_secret_manager_secret" "database_url" {
  secret_id = "database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url_version" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://admin:${var.postgres_password}@/aitonomo_db?host=/cloudsql/${google_sql_database_instance.postgres_instance.connection_name}"
}

# Permiso para que Cloud Run pueda desencriptar y leer los secretos
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

# ---------------------------------------------------------
# 7. BIGQUERY (Data Warehouse)
# ---------------------------------------------------------

resource "google_bigquery_dataset" "raw_dataset" {
  dataset_id    = "aitonomo_raw"
  description   = "Datos replicados directamente desde Cloud SQL via Datastream"
  project = var.project_id
  location      = var.region
}

resource "google_bigquery_table" "bq_usuarios" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_usuarios"
  deletion_protection = false # Cambiar a true en producción
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key {
      columns = ["id"]
    }
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

resource "google_bigquery_table" "bq_clientes" {
  dataset_id          = google_bigquery_dataset.raw_dataset.dataset_id
  table_id            = "public_clientes"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  table_constraints {
    primary_key {
      columns = ["id"]
    }
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
    primary_key {
      columns = ["id"]
    }
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
    primary_key {
      columns = ["id"]
    }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "usuario_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "fecha", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "proveedor", "type": "STRING", "mode": "NULLABLE"},
  {"name": "concepto", "type": "STRING", "mode": "NULLABLE"},
  {"name": "importe_total", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "url_ticket", "type": "STRING", "mode": "NULLABLE"},
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
    primary_key {
      columns = ["id"]
    }
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
    primary_key {
      columns = ["id"]
    }
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
    primary_key {
      columns = ["id"]
    }
  }
  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "id_bdns", "type": "STRING", "mode": "NULLABLE"},
  {"name": "titulo", "type": "STRING", "mode": "NULLABLE"},
  {"name": "cnae_target", "type": "STRING", "mode": "NULLABLE"},
  {"name": "fecha_cierre", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "texto_completo", "type": "STRING", "mode": "NULLABLE"},
  {"name": "embedding", "type": "STRING", "mode": "NULLABLE"}
]
EOF
}

#  ---------------------------------------------------------
# 8. ANALÍTICA E INVERSORES (Business Dashboard)
# ---------------------------------------------------------

# Dataset para recibir los costes de infraestructura de GCP
resource "google_bigquery_dataset" "billing_dataset" {
  dataset_id    = "gcp_billing_export"
  description   = "Dataset donde GCP volcará automáticamente los costes diarios de infraestructura"
  project       = var.project_id
  location      = "EU"
}

# Dataset analítico que agrupa y calcula KPIs limpios para el Dashboard
resource "google_bigquery_dataset" "analytics_dataset" {
  dataset_id    = "aitonomo_analytics"
  description   = "Vistas analíticas y KPIs pre-calculados para inversores"
  project       = var.project_id
  location      = var.region
}

# Vista SQL: Crecimiento de usuarios y Engagement (GMV)
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
    query = <<EOF
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

# ---------------------------------------------------------
# 9. DATASTREAM (Replicación PostgreSQL -> BigQuery)
# ---------------------------------------------------------

# Imagen Debian para la VM proxy
data "google_compute_image" "debian" {
  family  = "debian-12"
  project = "debian-cloud"
}

# VM con HAProxy: intermediario entre Datastream y Cloud SQL (IP privada)
resource "google_compute_instance" "proxy_datastream" {
  name         = "proxy-datastream-cloudsql"
  machine_type = "e2-micro"
  zone         = "${var.region}-a"

  boot_disk {
    initialize_params {
      image = data.google_compute_image.debian.id
    }
  }

  network_interface {
    network    = google_compute_network.vpc_aitonomo.id
    subnetwork = google_compute_subnetwork.subnet_aitonomo.id
    access_config {}
  }

  metadata_startup_script = <<-EOF
    #! /bin/bash
    apt-get update
    apt-get install -y haproxy
    
    cat > /etc/haproxy/haproxy.cfg << 'HAPROXY'
    global
        daemon
        maxconn 256
    defaults
        mode tcp
        timeout connect 5000ms
        timeout client 50000ms
        timeout server 50000ms
    frontend postgres_in
        bind *:5432
        default_backend postgres_out
    backend postgres_out
        server cloudsql ${google_sql_database_instance.postgres_instance.private_ip_address}:5432 check
    HAPROXY
    
    systemctl restart haproxy
  EOF

  depends_on = [google_sql_database_instance.postgres_instance]
}

# Esperar a que HAProxy arranque antes de crear el connection profile
resource "time_sleep" "esperar_proxy" {
  depends_on      = [google_compute_instance.proxy_datastream]
  create_duration = "300s"
}

# Firewall: permitir que Datastream (desde su rango de peering) llegue al proxy
resource "google_compute_firewall" "permitir_datastream_proxy" {
  name    = "permitir-datastream-proxy"
  network = google_compute_network.vpc_aitonomo.id

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_ranges = ["10.3.0.0/29"]
}

# Firewall: puertos internos requeridos por Dataflow workers
resource "google_compute_firewall" "permitir_dataflow_interno" {
  name    = "permitir-dataflow-interno"
  network = google_compute_network.vpc_aitonomo.id

  allow {
    protocol = "tcp"
    ports    = ["12345-12346"]
  }

  source_ranges = ["10.0.0.0/24"]
  target_tags   = ["dataflow"]
}

# Túnel privado entre Datastream y nuestra VPC
resource "google_datastream_private_connection" "datastream_pc" {
  display_name          = "Private connectivity Datastream"
  location              = var.region
  private_connection_id = "datastream-private-conn"

  vpc_peering_config {
    vpc    = google_compute_network.vpc_aitonomo.id
    subnet = "10.3.0.0/29"
  }
}

resource "google_datastream_connection_profile" "postgres_cp" {
  display_name          = "Conexion origen Postgres"
  location              = var.region
  connection_profile_id = "postgres-source-cp"

  postgresql_profile {
    hostname = google_compute_instance.proxy_datastream.network_interface[0].network_ip
    port     = 5432
    username = google_sql_user.postgres_user.name
    password = google_sql_user.postgres_user.password
    database = google_sql_database.aitonomo_db.name
  }

  private_connectivity {
    private_connection = google_datastream_private_connection.datastream_pc.id
  }

  depends_on = [
    google_datastream_private_connection.datastream_pc,
    time_sleep.esperar_proxy
  ]
}

resource "google_datastream_connection_profile" "bigquery_cp" {
  display_name          = "Conexion destino BigQuery"
  location              = var.region
  connection_profile_id = "bigquery-dest-cp"

  bigquery_profile {}
}

resource "google_datastream_stream" "postgres_to_bq" {
  stream_id    = "postgres-to-bq-stream"
  location     = var.region
  display_name = "Replicacion Postgres a BigQuery"

  source_config {
    source_connection_profile = google_datastream_connection_profile.postgres_cp.id
    postgresql_source_config {
      publication      = "datastream_pub"
      replication_slot = "datastream_slot"

      include_objects {
        postgresql_schemas {
          schema = "public"
        }
      }
    }
  }

  destination_config {
    destination_connection_profile = google_datastream_connection_profile.bigquery_cp.id
    bigquery_destination_config {
      data_freshness = "0s"
      single_target_dataset {
        dataset_id = "${var.project_id}:${google_bigquery_dataset.raw_dataset.dataset_id}"
      }
    }
  }

  backfill_all {}

  create_without_validation = true
}

# ---------------------------------------------------------
# 11. DATAFLOW JOB (Pipeline Streaming de Gastos)
# ---------------------------------------------------------
resource "null_resource" "lanzar_dataflow" {
  triggers = {
    db_host       = google_sql_database_instance.postgres_instance.private_ip_address
    pipeline_hash = filesha1("${path.module}/../dataflow/pipeline_gastos.py")
  }

  provisioner "local-exec" {
    command = <<EOT
python ../dataflow/pipeline_gastos.py \
  --project_id=${var.project_id} \
  --db_host=${google_sql_database_instance.postgres_instance.private_ip_address} \
  --db_name=aitonomo_db \
  --db_user=admin \
  --db_pass="${var.postgres_password}" \
  --runner=DataflowRunner \
  --region=${var.region} \
  --network=${google_compute_network.vpc_aitonomo.name} \
  --subnetwork=regions/${var.region}/subnetworks/${google_compute_subnetwork.subnet_aitonomo.name} \
  --temp_location=gs://${google_storage_bucket.dataflow_staging.name}/temp \
  --staging_location=gs://${google_storage_bucket.dataflow_staging.name}/staging \
  --service_account_email=${google_service_account.dataflow_sa.email} \
  --requirements_file=../dataflow/requirements.txt \
  --job_name=pipeline-gastos-${substr(filesha1("${path.module}/../dataflow/pipeline_gastos.py"), 0, 6)} \
  --streaming \
  --no_wait_until_finish
EOT
  }

  depends_on = [
    google_service_account.dataflow_sa,
    google_project_iam_member.dataflow_permissions,
    google_storage_bucket.dataflow_staging,
    google_pubsub_subscription.sub_tickets,
    google_sql_database_instance.postgres_instance,
    google_service_networking_connection.private_vpc_connection,
  ]
}
