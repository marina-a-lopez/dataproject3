# ---------------------------------------------------------
# SERVICE ACCOUNTS PARA CLOUD RUN
# ---------------------------------------------------------
resource "google_service_account" "backend_sa" {
  account_id   = "backend-cloud-run-sa"
  display_name = "Service Account para Backend Cloud Run"
}

resource "google_service_account" "frontend_sa" {
  account_id   = "frontend-cloud-run-sa"
  display_name = "Service Account para Frontend Cloud Run"
}

# ---------------------------------------------------------
# PERMISOS PARA EL BACKEND (Cloud SQL, Storage, PubSub)
# ---------------------------------------------------------
resource "google_project_iam_member" "backend_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_storage_bucket_iam_member" "backend_storage_admin" {
  bucket = google_storage_bucket.document_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_pubsub_topic_iam_member" "backend_pubsub_publisher_tickets" {
  topic  = google_pubsub_topic.topic_tickets.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

# Permisos para llamar a Vertex AI (Gemini)
resource "google_project_iam_member" "backend_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

# Permisos para que el Backend pueda consultar BigQuery (Dashboard Inversores)
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

# ---------------------------------------------------------
# PERMISOS PARA DATASTREAM (Escritura en BigQuery)
# ---------------------------------------------------------
resource "google_project_service_identity" "datastream_sa" {
  provider = google-beta
  project = var.project_id
  service = "datastream.googleapis.com"
}

resource "google_bigquery_dataset_iam_member" "datastream_bq_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.raw_dataset.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_project_service_identity.datastream_sa.email}"
}

# ---------------------------------------------------------
# ACCESO PÚBLICO A INTERNET (Para que la gente vea la web)
# ---------------------------------------------------------
resource "google_cloud_run_v2_service_iam_member" "acceso_publico_backend" {
  location = google_cloud_run_v2_service.backend_cloud_run.location
  name     = google_cloud_run_v2_service.backend_cloud_run.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "acceso_publico_frontend" {
  location = google_cloud_run_v2_service.frontend_cloud_run.location
  name     = google_cloud_run_v2_service.frontend_cloud_run.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "acceso_publico_dashboard" {
  location = google_cloud_run_v2_service.dashboard_cloud_run.location
  name     = google_cloud_run_v2_service.dashboard_cloud_run.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------
# SERVICE ACCOUNT PARA DATAFLOW (Pipeline de Gastos)
# ---------------------------------------------------------
resource "google_service_account" "dataflow_sa" {
  account_id   = "dataflow-pipeline-sa"
  display_name = "Service Account para Dataflow pipeline de gastos"
}

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

# Bucket de staging para los workers de Dataflow
resource "google_storage_bucket" "dataflow_staging" {
  name          = "${var.project_id}-dataflow-staging"
  location      = var.region
  force_destroy = true
}


# ---------------------------------------------------------
# GITHUB ACTIONS CI/CD
# ---------------------------------------------------------
resource "google_service_account" "github_actions_sa" {
  account_id   = "github-actions-deployer"
  display_name = "Service Account para GitHub Actions CI/CD"
  project      = var.project_id
}

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