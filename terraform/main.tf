#storage bucket para almacenar pdfs, etc

resource "google_storage_bucket" "document_bucket" {
  name          = "bucket-aitonomo-docs-${var.project_id}"
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
  deletion_protection = false
  settings {
    tier = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size = 100
    edition           = "ENTERPRISE"

    ip_configuration {
      ipv4_enabled    = true
      authorized_networks {
        name  = "Mac-Marina"
        value = "95.120.242.61/32"
      # private_network = data.google_compute_network.vpc_aitonomo.id
    }
   }
  }
  lifecycle {
    prevent_destroy = true
    }
}

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
