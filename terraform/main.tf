terraform {
  backend "gcs" {
    bucket  = "tfstate-aitonomo"
    prefix  = "terraform/state"
  }
}

module "networking" {
  source = "./modules/networking"
  region = var.region
}

module "storage" {
  source     = "./modules/storage"
  region     = var.region
  project_id = var.project_id
}

module "pubsub" {
  source = "./modules/pubsub"
}

module "cloudsql" {
  source                 = "./modules/cloudsql"
  region                 = var.region
  vpc_id                 = module.networking.vpc_id
  private_vpc_connection = module.networking.private_vpc_connection
  postgres_password      = var.postgres_password
}

module "bigquery" {
  source     = "./modules/bigquery"
  project_id = var.project_id
  region     = var.region
}

module "iam" {
  source                   = "./modules/iam"
  project_id               = var.project_id
  region                   = var.region
  document_bucket_name     = module.storage.document_bucket_name
  topic_name               = module.pubsub.topic_name
  raw_dataset_id           = module.bigquery.raw_dataset_id
  datastream_sa_email      = ""
  backend_cloud_run_name   = module.cloud_run.backend_name
  frontend_cloud_run_name  = module.cloud_run.frontend_name
  dashboard_cloud_run_name = module.cloud_run.dashboard_name
  gemini_api_key           = var.gemini_api_key
  rag_corpus_id            = var.rag_corpus_id
}

module "cloud_run" {
  source                   = "./modules/cloud_run"
  project_id               = var.project_id
  region                   = var.region
  backend_sa_email         = module.iam.backend_sa_email
  frontend_sa_email        = module.iam.frontend_sa_email
  cloudsql_connection_name = module.cloudsql.connection_name
  database_url_secret_id   = module.cloudsql.database_url_secret_id
  document_bucket_name     = module.storage.document_bucket_name
  vpc_id                   = module.networking.vpc_id
  subnet_id                = module.networking.subnet_id
  gemini_api_key_secret_id = module.iam.gemini_api_key_secret_id
  rag_corpus_id_secret_id  = module.iam.rag_corpus_id_secret_id
}

module "cloud_functions" {
  source                  = "./modules/cloud_functions"
  project_id              = var.project_id
  region                  = var.region
  functions_bucket_name   = module.storage.functions_bucket_name
  cloud_function_sa_email = module.iam.cloud_function_sa_email
  db_host                 = module.cloudsql.private_ip
  db_user                 = module.cloudsql.db_user
  db_name                 = module.cloudsql.db_name
  db_password             = var.postgres_password
  db_password_secret_id   = module.cloudsql.database_url_secret_id
}

module "datastream" {
  source                 = "./modules/datastream"
  project_id             = var.project_id
  region                 = var.region
  vpc_id                 = module.networking.vpc_id
  subnet_id              = module.networking.subnet_id
  raw_dataset_id         = module.bigquery.raw_dataset_id
  db_host                = module.cloudsql.private_ip
  db_user                = module.cloudsql.db_user
  db_password            = var.postgres_password
  db_name                = module.cloudsql.db_name
  cloudsql_instance_name = module.cloudsql.instance_name
}

module "dataflow" {
  source                  = "./modules/dataflow"
  project_id              = var.project_id
  region                  = var.region
  db_host                 = module.cloudsql.private_ip
  postgres_password       = var.postgres_password
  dataflow_staging_bucket = module.storage.dataflow_staging_name
  dataflow_sa_email       = module.iam.dataflow_sa_email
  vpc_name                = module.networking.vpc_name
  subnet_name             = module.networking.subnet_name
}

output "url_backend" {
  value = module.cloud_run.backend_url
}

output "url_frontend" {
  value = module.cloud_run.frontend_url
}

output "url_dashboard" {
  value = module.cloud_run.dashboard_url
}
