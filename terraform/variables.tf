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

variable "admin_ip" {
  description = "Dirección IP autorizada para acceder a la base de datos (CIDR, ej. 95.120.242.61/32)"
  type        = string
}

variable "database_url" {
  description = "URL de conexión a la base de datos PostgreSQL"
  type        = string
  sensitive   = true
}