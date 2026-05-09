resource "google_compute_network" "vpc" {
  name                    = "vpc-aitonomo"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "subnet-aitonomo"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}

resource "google_compute_global_address" "private_ip_range" {
  name          = "private-ip-range-aitonomo"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

resource "google_compute_firewall" "permitir_datastream_proxy" {
  name    = "permitir-datastream-proxy"
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_ranges = ["10.3.0.0/29"]
}

resource "google_compute_firewall" "permitir_dataflow_interno" {
  name    = "permitir-dataflow-interno"
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
    ports    = ["12345-12346"]
  }

  source_ranges = ["10.0.0.0/24"]
  target_tags   = ["dataflow"]
}
