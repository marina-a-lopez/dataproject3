output "document_bucket_name" {
  value = google_storage_bucket.document_bucket.name
}

output "dataflow_staging_name" {
  value = google_storage_bucket.dataflow_staging.name
}

output "functions_bucket_name" {
  value = google_storage_bucket.functions_bucket.name
}
