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

variable "database_url" {
  description = "URL de conexión a la base de datos PostgreSQL"
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  description = "API Key de Google Gemini"
  type        = string
  sensitive   = true
}

variable "rag_corpus_id" {
  description = "ID del corpus RAG de Vertex AI para subvenciones (crear con setup_rag_corpus.py)"
  type        = string
  default     = "pending"
}