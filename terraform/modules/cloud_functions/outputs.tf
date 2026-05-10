output "function_url" {
  value = google_cloudfunctions2_function.bdns_processor.service_config[0].uri
}
