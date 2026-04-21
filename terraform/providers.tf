terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "google" {
    project = var.project_id
    region = var.region
    user_project_override = true
}

# Configuración para que el provider de Docker pueda subir imágenes a Google Artifact Registry
data "google_client_config" "default" {}

provider "docker" {
  registry_auth {
    address  = "${var.region}-docker.pkg.dev"
    username = "oauth2accesstoken"
    password = data.google_client_config.default.access_token
  }
}
