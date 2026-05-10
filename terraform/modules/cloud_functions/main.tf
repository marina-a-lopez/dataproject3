locals {
  source_dir  = "${path.root}/../backend/cloud_functions/bdns_processor"
  output_path = "${path.root}/../backend/cloud_functions/bdns_processor.zip"
}

data "archive_file" "bdns_zip" {
  type        = "zip"
  source_dir  = local.source_dir
  output_path = local.output_path
}

resource "google_storage_bucket_object" "bdns_source" {
  name   = "cloud_functions/bdns_processor-${data.archive_file.bdns_zip.output_md5}.zip"
  bucket = var.functions_bucket_name
  source = local.output_path
}

resource "google_cloudfunctions2_function" "bdns_processor" {
  name     = "bdns-processor"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = "python311"
    entry_point = "procesar_bdns"
    source {
      storage_source {
        bucket = var.functions_bucket_name
        object = google_storage_bucket_object.bdns_source.name
      }
    }
  }

  service_config {
    max_instance_count = 3
    timeout_seconds    = 540
    available_memory   = "512M"
    service_account_email = var.cloud_function_sa_email

    environment_variables = {
      GCP_PROJECT_ID = var.project_id
      GCP_REGION     = var.region
      DB_HOST        = var.db_host
      DB_USER        = var.db_user
      DB_NAME        = var.db_name
    }

    secret_environment_variables {
      key        = "DB_PASS"
      project_id = var.project_id
      secret     = var.db_password_secret_id
      version    = "latest"
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = "projects/${var.project_id}/topics/topic-procesar-bdns"
    retry_policy   = "RETRY_POLICY_DO_NOT_RETRY"
  }
}

resource "google_cloud_scheduler_job" "bdns_daily" {
  name      = "bdns-daily-trigger"
  project   = var.project_id
  region    = "europe-west1"
  schedule  = "0 3 * * *"
  time_zone = "Europe/Madrid"

  pubsub_target {
    topic_name = "projects/${var.project_id}/topics/topic-procesar-bdns"
    data       = base64encode("{\"trigger\":\"scheduled\"}")
  }
}
