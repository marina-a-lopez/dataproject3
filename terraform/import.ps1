$PROJECT = "project3grupo4"
$REGION = "europe-southwest1"

# Networking
terraform import module.networking.google_compute_network.vpc "projects/$PROJECT/global/networks/vpc-aitonomo"
terraform import module.networking.google_compute_subnetwork.subnet "projects/$PROJECT/regions/$REGION/subnetworks/subnet-aitonomo"
terraform import module.networking.google_compute_global_address.private_ip_range "projects/$PROJECT/global/addresses/private-ip-range-aitonomo"
terraform import module.networking.google_service_networking_connection.private_vpc_connection "$PROJECT/servicenetworking.googleapis.com"
terraform import module.networking.google_compute_firewall.permitir_datastream_proxy "projects/$PROJECT/global/firewalls/permitir-datastream-proxy"
terraform import module.networking.google_compute_firewall.permitir_dataflow_interno "projects/$PROJECT/global/firewalls/permitir-dataflow-interno"

# Storage
terraform import module.storage.google_storage_bucket.document_bucket "bucket-aitonomo-docs"
terraform import module.storage.google_storage_bucket.dataflow_staging "${PROJECT}-dataflow-staging"
terraform import module.storage.google_storage_bucket.functions_bucket "${PROJECT}-cloud-functions"

# PubSub
terraform import module.pubsub.google_pubsub_topic.topic_tickets "projects/$PROJECT/topics/topic-tickets"
terraform import module.pubsub.google_pubsub_topic.topic_bdns "projects/$PROJECT/topics/topic-procesar-bdns"

# BigQuery
terraform import module.bigquery.google_bigquery_dataset.raw_dataset "projects/$PROJECT/datasets/aitonomo_raw"
terraform import module.bigquery.google_bigquery_dataset.billing_dataset "projects/$PROJECT/datasets/gcp_billing_export"
terraform import module.bigquery.google_bigquery_dataset.analytics_dataset "projects/$PROJECT/datasets/aitonomo_analytics"

# BigQuery Tables
terraform import module.bigquery.google_bigquery_table.bq_usuarios "projects/$PROJECT/datasets/aitonomo_raw/tables/public_usuarios"
terraform import module.bigquery.google_bigquery_table.bq_clientes "projects/$PROJECT/datasets/aitonomo_raw/tables/public_clientes"
terraform import module.bigquery.google_bigquery_table.bq_productos "projects/$PROJECT/datasets/aitonomo_raw/tables/public_productos"
terraform import module.bigquery.google_bigquery_table.bq_gastos "projects/$PROJECT/datasets/aitonomo_raw/tables/public_gastos"
terraform import module.bigquery.google_bigquery_table.bq_facturas "projects/$PROJECT/datasets/aitonomo_raw/tables/public_facturas"
terraform import module.bigquery.google_bigquery_table.bq_presupuestos "projects/$PROJECT/datasets/aitonomo_raw/tables/public_presupuestos"
terraform import module.bigquery.google_bigquery_table.bq_subvenciones "projects/$PROJECT/datasets/aitonomo_raw/tables/public_subvenciones"
terraform import module.bigquery.google_bigquery_table.bq_calendario_eventos "projects/$PROJECT/datasets/aitonomo_raw/tables/public_calendario_eventos"
terraform import module.bigquery.google_bigquery_table.view_investor_kpis "projects/$PROJECT/datasets/aitonomo_analytics/tables/kpis_crecimiento_mensual"

# IAM - Service Accounts
terraform import module.iam.google_service_account.backend_sa "projects/$PROJECT/serviceAccounts/backend-cloud-run-sa@${PROJECT}.iam.gserviceaccount.com"
terraform import module.iam.google_service_account.frontend_sa "projects/$PROJECT/serviceAccounts/frontend-cloud-run-sa@${PROJECT}.iam.gserviceaccount.com"
terraform import module.iam.google_service_account.dataflow_sa "projects/$PROJECT/serviceAccounts/dataflow-pipeline-sa@${PROJECT}.iam.gserviceaccount.com"
terraform import module.iam.google_service_account.github_actions_sa "projects/$PROJECT/serviceAccounts/github-actions-deployer@${PROJECT}.iam.gserviceaccount.com"
terraform import module.iam.google_service_account.cloud_function_sa "projects/$PROJECT/serviceAccounts/bdns-processor-sa@${PROJECT}.iam.gserviceaccount.com"

# IAM - Secrets
terraform import module.iam.google_secret_manager_secret.gemini_api_key "projects/$PROJECT/secrets/gemini-api-key"
terraform import module.iam.google_secret_manager_secret.rag_corpus_id "projects/$PROJECT/secrets/rag-corpus-id"

# CloudSQL
terraform import module.cloudsql.google_sql_database_instance.postgres_instance "projects/$PROJECT/instances/db-aitonomo"
terraform import module.cloudsql.google_sql_user.postgres_user "$PROJECT/db-aitonomo/admin"
terraform import module.cloudsql.google_sql_database.aitonomo_db "projects/$PROJECT/instances/db-aitonomo/databases/aitonomo_db"
terraform import module.cloudsql.google_secret_manager_secret.database_url "projects/$PROJECT/secrets/database-url"

# Cloud Run
terraform import module.cloud_run.google_artifact_registry_repository.repo "projects/$PROJECT/locations/$REGION/repositories/repo-aitonomo"
terraform import module.cloud_run.google_cloud_run_v2_service.backend "projects/$PROJECT/locations/$REGION/services/api-backend"
terraform import module.cloud_run.google_cloud_run_v2_service.frontend "projects/$PROJECT/locations/$REGION/services/web-frontend"
terraform import module.cloud_run.google_cloud_run_v2_service.dashboard "projects/$PROJECT/locations/$REGION/services/investor-dashboard"

# Cloud Functions
terraform import module.cloud_functions.google_cloudfunctions2_function.bdns_processor "projects/$PROJECT/locations/$REGION/functions/bdns-processor"
terraform import module.cloud_functions.google_cloud_scheduler_job.bdns_daily "projects/$PROJECT/locations/europe-west1/jobs/bdns-daily-trigger"

# Datastream
terraform import module.datastream.google_compute_instance.proxy_datastream "projects/$PROJECT/zones/${REGION}-a/instances/proxy-datastream-cloudsql"
terraform import module.datastream.google_datastream_private_connection.datastream_pc "projects/$PROJECT/locations/$REGION/privateConnections/datastream-private-conn"
terraform import module.datastream.google_datastream_connection_profile.postgres_cp "projects/$PROJECT/locations/$REGION/connectionProfiles/postgres-source-cp"
terraform import module.datastream.google_datastream_connection_profile.bigquery_cp "projects/$PROJECT/locations/$REGION/connectionProfiles/bigquery-dest-cp"
terraform import module.datastream.google_datastream_stream.postgres_to_bq "projects/$PROJECT/locations/$REGION/streams/postgres-to-bq-stream"

Write-Host "`n=== Import complete! Run 'terraform plan' to verify. ===" -ForegroundColor Green
