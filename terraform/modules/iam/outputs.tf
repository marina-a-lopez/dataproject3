output "backend_sa_email" {
  value = google_service_account.backend_sa.email
}

output "frontend_sa_email" {
  value = google_service_account.frontend_sa.email
}

output "dataflow_sa_email" {
  value = google_service_account.dataflow_sa.email
}

output "cloud_function_sa_email" {
  value = google_service_account.cloud_function_sa.email
}

output "gemini_api_key_secret_id" {
  value = google_secret_manager_secret.gemini_api_key.secret_id
}

output "rag_corpus_id_secret_id" {
  value = google_secret_manager_secret.rag_corpus_id.secret_id
}
