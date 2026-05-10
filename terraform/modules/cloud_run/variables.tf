variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "backend_sa_email" {
  type = string
}

variable "frontend_sa_email" {
  type = string
}

variable "cloudsql_connection_name" {
  type = string
}

variable "database_url_secret_id" {
  type = string
}

variable "document_bucket_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "gemini_api_key_secret_id" {
  type = string
}

variable "rag_corpus_id_secret_id" {
  type = string
}
