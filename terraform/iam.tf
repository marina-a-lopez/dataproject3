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

resource "google_pubsub_topic_iam_member" "backend_pubsub_publisher" {
  topic  = google_pubsub_topic.topic-batch-upload.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
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