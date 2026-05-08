output "backend_sa_email" {
  value = google_service_account.backend_sa.email
}

output "frontend_sa_email" {
  value = google_service_account.frontend_sa.email
}

output "dataflow_sa_email" {
  value = google_service_account.dataflow_sa.email
}
