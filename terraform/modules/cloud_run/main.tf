resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "repo-aitonomo"
  format        = "DOCKER"
}

resource "google_cloud_run_v2_service" "backend" {
  name                = "api-backend"
  location            = var.region
  deletion_protection = false

  template {
    service_account = var.backend_sa_email

    scaling {
      max_instance_count = 10
    }

    vpc_access {
      network_interfaces {
        network    = var.vpc_id
        subnetwork = var.subnet_id
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.cloudsql_connection_name]
      }
    }

    containers {
      image = var.backend_image
      ports {
        container_port = 8080
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = var.database_url_secret_id
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
        value = var.document_bucket_name
      }
      env {
        name  = "GCP_LOCATION"
        value = "us-central1"
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.gemini_api_key_secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "RAG_CORPUS_ID"
        value_source {
          secret_key_ref {
            secret  = var.rag_corpus_id_secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  name                = "web-frontend"
  location            = var.region
  deletion_protection = false

  template {
    service_account = var.frontend_sa_email
    containers {
      image = var.frontend_image
      ports {
        container_port = 80
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

resource "google_cloud_run_v2_service" "dashboard" {
  name                = "investor-dashboard"
  location            = var.region
  deletion_protection = false

  template {
    service_account = var.frontend_sa_email
    containers {
      image = var.dashboard_image
      ports {
        container_port = 80
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}
