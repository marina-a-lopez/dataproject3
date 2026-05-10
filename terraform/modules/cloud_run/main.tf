resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "repo-aitonomo"
  format        = "DOCKER"
}

locals {
  backend_hash   = sha1(join("", [for f in fileset("${path.root}/../backend", "**") : filesha1("${path.root}/../backend/${f}")]))
  frontend_hash  = sha1(join("", [for f in fileset("${path.root}/../static", "**") : filesha1("${path.root}/../static/${f}")]))
  dashboard_hash = sha1(join("", [for f in fileset("${path.root}/../dashboard-buss", "**") : filesha1("${path.root}/../dashboard-buss/${f}")]))
}

resource "docker_image" "backend_image" {
  name = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/backend:${local.backend_hash}"
  build {
    context    = "${path.root}/../backend/"
    dockerfile = "Dockerfile"
    platform   = "linux/amd64"
  }
}

resource "docker_registry_image" "backend_push" {
  name          = docker_image.backend_image.name
  keep_remotely = true
}

resource "google_cloud_run_v2_service" "backend" {
  name                = "api-backend"
  location            = var.region
  deletion_protection = false

  template {
    service_account = var.backend_sa_email

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
      image = docker_registry_image.backend_push.name
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
  depends_on = [docker_registry_image.backend_push]
}

resource "docker_image" "frontend_image" {
  name = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/frontend:${local.frontend_hash}"
  build {
    context    = "${path.root}/../static/"
    dockerfile = "Dockerfile"
    platform   = "linux/amd64"
  }
}

resource "docker_registry_image" "frontend_push" {
  name          = docker_image.frontend_image.name
  keep_remotely = true
}

resource "google_cloud_run_v2_service" "frontend" {
  name                = "web-frontend"
  location            = var.region
  deletion_protection = false

  template {
    service_account = var.frontend_sa_email
    containers {
      image = docker_registry_image.frontend_push.name
      ports {
        container_port = 80
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }
  depends_on = [docker_registry_image.frontend_push]
}

resource "docker_image" "dashboard_image" {
  name = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/dashboard:${local.dashboard_hash}"
  build {
    context    = "${path.root}/../dashboard-buss/"
    dockerfile = "Dockerfile"
    platform   = "linux/amd64"
  }
}

resource "docker_registry_image" "dashboard_push" {
  name          = docker_image.dashboard_image.name
  keep_remotely = true
}

resource "google_cloud_run_v2_service" "dashboard" {
  name                = "investor-dashboard"
  location            = var.region
  deletion_protection = false

  template {
    service_account = var.frontend_sa_email
    containers {
      image = docker_registry_image.dashboard_push.name
      ports {
        container_port = 80
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }
  depends_on = [docker_registry_image.dashboard_push]
}
