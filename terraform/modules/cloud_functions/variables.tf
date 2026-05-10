variable "project_id" { type = string }
variable "region" { type = string }
variable "functions_bucket_name" { type = string }
variable "cloud_function_sa_email" { type = string }
variable "db_host" { type = string }
variable "db_user" { type = string }
variable "db_name" { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}
variable "db_password_secret_id" { type = string }
