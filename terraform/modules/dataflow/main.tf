resource "null_resource" "lanzar_dataflow" {
  triggers = {
    db_host       = var.db_host
    pipeline_hash = filesha1(var.pipeline_path)
  }

  provisioner "local-exec" {
    command = <<EOT
python ${var.pipeline_path} \
  --project_id=${var.project_id} \
  --db_host=${var.db_host} \
  --db_name=aitonomo_db \
  --db_user=admin \
  --db_pass="${var.postgres_password}" \
  --runner=DataflowRunner \
  --region=${var.region} \
  --network=${var.vpc_name} \
  --subnetwork=regions/${var.region}/subnetworks/${var.subnet_name} \
  --temp_location=gs://${var.dataflow_staging_bucket}/temp \
  --staging_location=gs://${var.dataflow_staging_bucket}/staging \
  --service_account_email=${var.dataflow_sa_email} \
  --requirements_file=../dataflow/requirements.txt \
  --job_name=pipeline-gastos-${substr(filesha1(var.pipeline_path), 0, 6)} \
  --streaming \
  --no_wait_until_finish
EOT
  }
}
