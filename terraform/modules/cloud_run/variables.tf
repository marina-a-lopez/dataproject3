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
  default     = "europe-southwest1-docker.pkg.dev/project3grupo4/repo-aitonomo/backend:b133cb7b80b163146d7beeb090db189f13583a63"
}

variable "frontend_image" {
  description = "Imagen Docker del frontend web (gestionada por CI/CD)"
  type        = string
  default     = "europe-southwest1-docker.pkg.dev/project3grupo4/repo-aitonomo/frontend:6a439fafcd5c9c3241a77e78e820b2f965cbff10"
}

variable "dashboard_image" {
  description = "Imagen Docker del dashboard de inversores (gestionada por CI/CD)"
  type        = string
  default     = "europe-southwest1-docker.pkg.dev/project3grupo4/repo-aitonomo/dashboard:d170c06db202ffbdab0f14f650a2ce987157ee5f"
}
