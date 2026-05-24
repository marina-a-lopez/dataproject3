data "google_compute_image" "debian" {
  family  = "debian-12"
  project = "debian-cloud"
}

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
    network    = var.vpc_id
    subnetwork = var.subnet_id
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
        server cloudsql ${var.db_host}:5432 check
    HAPROXY

    systemctl restart haproxy
  EOF

  depends_on = [var.vpc_id]
  lifecycle {
    ignore_changes = [metadata_startup_script]
  }
}

resource "time_sleep" "esperar_proxy" {
  depends_on      = [google_compute_instance.proxy_datastream]
  create_duration = "300s"
}

resource "google_datastream_private_connection" "datastream_pc" {
  display_name          = "Private connectivity Datastream"
  location              = var.region
  private_connection_id = "datastream-private-conn"

  vpc_peering_config {
    vpc    = var.vpc_id
    subnet = "10.3.0.0/29"
  }

  lifecycle {
    ignore_changes = [create_without_validation]
  }
}

resource "google_datastream_connection_profile" "postgres_cp" {
  display_name          = "Conexion origen Postgres"
  location              = var.region
  connection_profile_id = "postgres-source-cp"
  create_without_validation = true

  postgresql_profile {
    hostname = google_compute_instance.proxy_datastream.network_interface[0].network_ip
    port     = 5432
    username = var.db_user
    password = var.db_password
    database = var.db_name
  }

  private_connectivity {
    private_connection = google_datastream_private_connection.datastream_pc.id
  }

  depends_on = [
    google_datastream_private_connection.datastream_pc,
    time_sleep.esperar_proxy
  ]

  lifecycle {
    ignore_changes = [create_without_validation]
  }
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
        dataset_id = "${var.project_id}:${var.raw_dataset_id}"
      }
    }
  }

  backfill_all {}
  create_without_validation = true

  lifecycle {
    ignore_changes = [create_without_validation, source_config, destination_config]
  }
}
