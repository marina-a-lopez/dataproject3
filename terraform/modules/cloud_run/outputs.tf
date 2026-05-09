output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  value = google_cloud_run_v2_service.frontend.uri
}

output "dashboard_url" {
  value = google_cloud_run_v2_service.dashboard.uri
}

output "backend_name" {
  value = google_cloud_run_v2_service.backend.name
}

output "frontend_name" {
  value = google_cloud_run_v2_service.frontend.name
}

output "dashboard_name" {
  value = google_cloud_run_v2_service.dashboard.name
}
