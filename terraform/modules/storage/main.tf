resource "google_storage_bucket" "document_bucket" {
  name          = "bucket-aitonomo-docs"
  location      = var.region
  force_destroy = false
}

resource "google_storage_bucket" "dataflow_staging" {
  name          = "${var.project_id}-dataflow-staging"
  location      = var.region
  force_destroy = true
}
