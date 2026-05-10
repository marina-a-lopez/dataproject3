output "instance_name" {
  value = google_sql_database_instance.postgres_instance.name
}

output "connection_name" {
  value = google_sql_database_instance.postgres_instance.connection_name
}

output "private_ip" {
  value = google_sql_database_instance.postgres_instance.private_ip_address
}

output "public_ip" {
  value = google_sql_database_instance.postgres_instance.public_ip_address
}

output "db_name" {
  value = google_sql_database.aitonomo_db.name
}

output "db_user" {
  value = google_sql_user.postgres_user.name
}

output "database_url_secret_id" {
  value = google_secret_manager_secret.database_url.secret_id
}
