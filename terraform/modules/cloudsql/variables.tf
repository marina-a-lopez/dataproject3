variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_vpc_connection" {
  type = string
}

variable "postgres_password" {
  type      = string
  sensitive = true
}
