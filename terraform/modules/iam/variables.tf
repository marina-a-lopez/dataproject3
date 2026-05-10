variable "project_id" {
  type = string
}

variable "document_bucket_name" {
  type = string
}

variable "topic_name" {
  type = string
}

variable "raw_dataset_id" {
  type = string
}

variable "datastream_sa_email" {
  type = string
}

variable "backend_cloud_run_name" {
  type = string
}

variable "frontend_cloud_run_name" {
  type = string
}

variable "dashboard_cloud_run_name" {
  type = string
}

variable "region" {
  type = string
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
}

variable "rag_corpus_id" {
  type    = string
  default = "pending"
}
