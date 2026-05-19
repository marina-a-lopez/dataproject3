moved {
  from = google_artifact_registry_repository.repo_aitonomo
  to   = module.cloud_run.google_artifact_registry_repository.repo
}

moved {
  from = google_bigquery_dataset.analytics_dataset
  to   = module.bigquery.google_bigquery_dataset.analytics_dataset
}

moved {
  from = google_bigquery_dataset.billing_dataset
  to   = module.bigquery.google_bigquery_dataset.billing_dataset
}

moved {
  from = google_bigquery_dataset.raw_dataset
  to   = module.bigquery.google_bigquery_dataset.raw_dataset
}

moved {
  from = google_bigquery_dataset_iam_member.datastream_bq_editor
  to   = module.iam.google_bigquery_dataset_iam_member.datastream_bq_editor
}

moved {
  from = google_bigquery_table.bq_clientes
  to   = module.bigquery.google_bigquery_table.bq_clientes
}

moved {
  from = google_bigquery_table.bq_facturas
  to   = module.bigquery.google_bigquery_table.bq_facturas
}

moved {
  from = google_bigquery_table.bq_gastos
  to   = module.bigquery.google_bigquery_table.bq_gastos
}

moved {
  from = google_bigquery_table.bq_presupuestos
  to   = module.bigquery.google_bigquery_table.bq_presupuestos
}

moved {
  from = google_bigquery_table.bq_productos
  to   = module.bigquery.google_bigquery_table.bq_productos
}

moved {
  from = google_bigquery_table.bq_subvenciones
  to   = module.bigquery.google_bigquery_table.bq_subvenciones
}

moved {
  from = google_bigquery_table.bq_usuarios
  to   = module.bigquery.google_bigquery_table.bq_usuarios
}

moved {
  from = google_bigquery_table.view_investor_kpis
  to   = module.bigquery.google_bigquery_table.view_investor_kpis
}

moved {
  from = google_cloud_run_v2_service.backend_cloud_run
  to   = module.cloud_run.google_cloud_run_v2_service.backend
}

moved {
  from = google_cloud_run_v2_service.dashboard_cloud_run
  to   = module.cloud_run.google_cloud_run_v2_service.dashboard
}

moved {
  from = google_cloud_run_v2_service.frontend_cloud_run
  to   = module.cloud_run.google_cloud_run_v2_service.frontend
}

moved {
  from = google_cloud_run_v2_service_iam_member.acceso_publico_backend
  to   = module.iam.google_cloud_run_v2_service_iam_member.acceso_publico_backend
}

moved {
  from = google_cloud_run_v2_service_iam_member.acceso_publico_dashboard
  to   = module.iam.google_cloud_run_v2_service_iam_member.acceso_publico_dashboard
}

moved {
  from = google_cloud_run_v2_service_iam_member.acceso_publico_frontend
  to   = module.iam.google_cloud_run_v2_service_iam_member.acceso_publico_frontend
}

moved {
  from = google_datastream_connection_profile.bigquery_cp
  to   = module.datastream.google_datastream_connection_profile.bigquery_cp
}

moved {
  from = google_datastream_connection_profile.postgres_cp
  to   = module.datastream.google_datastream_connection_profile.postgres_cp
}

moved {
  from = google_datastream_stream.postgres_to_bq
  to   = module.datastream.google_datastream_stream.postgres_to_bq
}

moved {
  from = google_project_iam_member.backend_bigquery_jobUser
  to   = module.iam.google_project_iam_member.backend_bigquery_jobUser
}

moved {
  from = google_project_iam_member.backend_bigquery_viewer
  to   = module.iam.google_project_iam_member.backend_bigquery_viewer
}

moved {
  from = google_project_iam_member.backend_sql_client
  to   = module.iam.google_project_iam_member.backend_sql_client
}

moved {
  from = google_project_iam_member.backend_vertex_ai_user
  to   = module.iam.google_project_iam_member.backend_vertex_ai_user
}

moved {
  from = google_project_iam_member.dataflow_permissions
  to   = module.iam.google_project_iam_member.dataflow_permissions
}

moved {
  from = google_project_iam_member.roles_cicd
  to   = module.iam.google_project_iam_member.roles_cicd
}

moved {
  from = google_project_iam_member.secret_accessor
  to   = module.iam.google_project_iam_member.secret_accessor
}

moved {
  from = google_project_service_identity.datastream_sa
  to   = module.iam.google_project_service_identity.datastream_sa
}

moved {
  from = google_pubsub_subscription.sub_tickets
  to   = module.pubsub.google_pubsub_subscription.sub_tickets
}

moved {
  from = google_pubsub_topic.topic_tickets
  to   = module.pubsub.google_pubsub_topic.topic_tickets
}

moved {
  from = google_pubsub_topic_iam_member.backend_pubsub_publisher_tickets
  to   = module.iam.google_pubsub_topic_iam_member.backend_pubsub_publisher_tickets
}

moved {
  from = google_secret_manager_secret.database_url
  to   = module.cloudsql.google_secret_manager_secret.database_url
}

moved {
  from = google_secret_manager_secret.gemini_api_key
  to   = module.iam.google_secret_manager_secret.gemini_api_key
}

moved {
  from = google_secret_manager_secret_version.database_url_version
  to   = module.cloudsql.google_secret_manager_secret_version.database_url_version
}

moved {
  from = google_secret_manager_secret_version.gemini_api_key_version
  to   = module.iam.google_secret_manager_secret_version.gemini_api_key_version
}

moved {
  from = google_service_account.backend_sa
  to   = module.iam.google_service_account.backend_sa
}

moved {
  from = google_service_account.dataflow_sa
  to   = module.iam.google_service_account.dataflow_sa
}

moved {
  from = google_service_account.frontend_sa
  to   = module.iam.google_service_account.frontend_sa
}

moved {
  from = google_service_account.github_actions_sa
  to   = module.iam.google_service_account.github_actions_sa
}

moved {
  from = google_sql_database.aitonomo_db
  to   = module.cloudsql.google_sql_database.aitonomo_db
}

moved {
  from = google_sql_database_instance.postgres_instance
  to   = module.cloudsql.google_sql_database_instance.postgres_instance
}

moved {
  from = google_sql_user.postgres_user
  to   = module.cloudsql.google_sql_user.postgres_user
}

moved {
  from = google_storage_bucket.dataflow_staging
  to   = module.storage.google_storage_bucket.dataflow_staging
}

moved {
  from = google_storage_bucket.document_bucket
  to   = module.storage.google_storage_bucket.document_bucket
}

moved {
  from = google_storage_bucket_iam_member.backend_storage_admin
  to   = module.iam.google_storage_bucket_iam_member.backend_storage_admin
}
