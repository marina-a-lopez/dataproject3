resource "google_sql_database_instance" "postgres_instance" {
  name             = "db-aitonomo"
  region           = var.region
  database_version = "POSTGRES_17"
  deletion_protection = true

  settings {
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size         = 100
    disk_autoresize   = true
    edition           = "ENTERPRISE"

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.vpc_id
      enable_private_path_for_google_cloud_services = true
    }

    database_flags {
      name  = "cloudsql.logical_decoding"
      value = "on"
    }
  }

  depends_on = [var.private_vpc_connection]
}

resource "google_sql_user" "postgres_user" {
  name     = "admin"
  instance = google_sql_database_instance.postgres_instance.name
  password = var.postgres_password
}

resource "google_sql_database" "aitonomo_db" {
  name     = "aitonomo_db"
  instance = google_sql_database_instance.postgres_instance.name
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
