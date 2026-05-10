variable "project_id" {
  description = "ID del proyecto en GCP"
  type        = string
}

variable "region" {
  description = "Region de GCP"
  type        = string
}

variable "postgres_password" {
  description = "Contraseña para el usuario de la base de datos PostgreSQL"
  type        = string
  sensitive   = true
}

variable "admin_ip" {
  description = "Dirección IP autorizada para acceder a la base de datos (CIDR, ej. 95.120.242.61/32)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "gemini_api_key" {
  description = "Clave API para Google Gemini (legacy — el backend usa Vertex AI con ADC)"
  type        = string
  sensitive   = true
  default     = "unused-vertex-uses-adc"
}

variable "database_url" {
  description = "URL de conexión (legacy — se construye automáticamente en main.tf desde postgres_password)"
  type        = string
  sensitive   = true
  default     = ""
}
