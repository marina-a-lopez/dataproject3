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

variable "backend_image" {
  description = "Imagen Docker del backend (gestionada por CI/CD)"
  type        = string
  default     = "europe-southwest1-docker.pkg.dev/proyectodataia3/repo-aitonomo/backend:c3e6ae7f121037a11f2915da5d1de735f63e56bf"
}

variable "frontend_image" {
  description = "Imagen Docker del frontend web (gestionada por CI/CD)"
  type        = string
  default     = "europe-southwest1-docker.pkg.dev/proyectodataia3/repo-aitonomo/frontend:d253468b9f73c0f75abc4e9d8204f8d910351476"
}

variable "dashboard_image" {
  description = "Imagen Docker del dashboard de inversores (gestionada por CI/CD)"
  type        = string
  default     = "europe-southwest1-docker.pkg.dev/proyectodataia3/repo-aitonomo/dashboard:a916c795429475ab9f41f248941e36c1e5e9b73a"
}
