resource "google_service_account" "backend_sa" {
  account_id   = "backend-cloud-run-sa"
  display_name = "Service Account para Backend Cloud Run"
}

resource "google_service_account" "frontend_sa" {
  account_id   = "frontend-cloud-run-sa"
  display_name = "Service Account para Frontend Cloud Run"
}

resource "google_service_account" "dataflow_sa" {
  account_id   = "dataflow-pipeline-sa"
  display_name = "Service Account para Dataflow pipeline de gastos"
}

resource "google_service_account" "github_actions_sa" {
  account_id   = "github-actions-deployer"
  display_name = "Service Account para GitHub Actions CI/CD"
  project      = var.project_id
}

# Backend permissions
resource "google_project_iam_member" "backend_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_storage_bucket_iam_member" "backend_storage_admin" {
  bucket = var.document_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_pubsub_topic_iam_member" "backend_pubsub_publisher_tickets" {
  topic  = var.topic_name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_bigquery_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_bigquery_jobUser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

# Datastream permissions
resource "google_project_service_identity" "datastream_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "datastream.googleapis.com"
}

resource "google_bigquery_dataset_iam_member" "datastream_bq_editor" {
  project    = var.project_id
  dataset_id = var.raw_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_project_service_identity.datastream_sa.email}"
}

resource "google_project_iam_member" "datastream_network_viewer" {
  project = var.project_id
  role    = "roles/compute.networkViewer"
  member  = "serviceAccount:${google_project_service_identity.datastream_sa.email}"
}

resource "google_project_iam_member" "datastream_cloudsql_viewer" {
  project = var.project_id
  role    = "roles/cloudsql.viewer"
  member  = "serviceAccount:${google_project_service_identity.datastream_sa.email}"
}

# Cloud Run public access
resource "google_cloud_run_v2_service_iam_member" "acceso_publico_backend" {
  location = var.region
  name     = var.backend_cloud_run_name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "acceso_publico_frontend" {
  location = var.region
  name     = var.frontend_cloud_run_name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "acceso_publico_dashboard" {
  location = var.region
  name     = var.dashboard_cloud_run_name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Dataflow permissions
resource "google_project_iam_member" "dataflow_permissions" {
  for_each = toset([
    "roles/dataflow.worker",
    "roles/pubsub.subscriber",
    "roles/storage.objectAdmin",
    "roles/cloudsql.client",
    "roles/aiplatform.user",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

# CI/CD permissions
resource "google_project_iam_member" "roles_cicd" {
  for_each = toset([
    "roles/artifactregistry.admin",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
    "roles/resourcemanager.projectIamAdmin"
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"
}
