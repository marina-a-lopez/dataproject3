variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "db_host" {
  type = string
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "dataflow_staging_bucket" {
  type = string
}

variable "dataflow_sa_email" {
  type = string
}

variable "vpc_name" {
  type = string
}

variable "subnet_name" {
  type = string
}

variable "pipeline_path" {
  type    = string
  default = "../dataflow/pipeline_gastos.py"
}
