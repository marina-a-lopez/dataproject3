#storage bucket para almacenar pdfs, etc

resource "google_storage_bucket" "document_bucket" {
  name          = "bucket-aitonomo-docs"
  location      = var.region
  force_destroy = false
  # storage_class = "STANDARD"
}

#pubsub para enviar mensajes
resource "google_pubsub_topic" "topic-batch-upload" {
  name = "topic-lote-facturas"
}

resource "google_pubsub_subscription" "topic-batch-upload-sub" {
  name  = "${google_pubsub_topic.topic-batch-upload.name}-sub"
  topic = google_pubsub_topic.topic-batch-upload.name
}

# bd en cloud sql con ip privada

# data "google_compute_network" "vpc_aitonomo" {
#   name    = "vpc-aitonomo"
#   project = var.project_id
# }

resource "google_sql_database_instance" "postgres_instance" {
  name = "aitonomo-db"
  region = var.region
  database_version = "POSTGRES_17"
  deletion_protection = true
  settings {
    tier = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size = 100
    edition           = "ENTERPRISE"

    ip_configuration {
      ipv4_enabled    = true
      authorized_networks {
        name  = "Admin-IP"
        value = var.admin_ip
      }
      # private_network = data.google_compute_network.vpc_aitonomo.id
    }
   }
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
        name  = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
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
    }
  }
  depends_on = [docker_registry_image.frontend_push]
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

# ---------------------------------------------------------
# 6. GOOGLE SECRET MANAGER (Seguridad de Variables)
# ---------------------------------------------------------

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key_version" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key
}

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