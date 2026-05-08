variable "project_id" {
  description = "ID del proyecto en GCP"
  type        = string
}

variable "region" {
  description = "Region de GCP"
  type = string
}

variable "postgres_password" {
  description = "Contraseña para el usuario de la base de datos PostgreSQL"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "URL de conexión a la base de datos PostgreSQL"
  type        = string
  sensitive   = true
}