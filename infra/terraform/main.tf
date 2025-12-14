provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_artifact_registry_repository" "repo" {
  location       = var.region
  repository_id  = var.artifact_repo
  description    = "NutriHub images"
  format         = "DOCKER"
}

resource "google_compute_global_address" "ingress_ip" {
  name = var.static_ip_name
}

resource "google_container_cluster" "gke" {
  name                     = var.cluster_name
  location                 = var.zone
  remove_default_node_pool = true
  initial_node_count       = 1
  ip_allocation_policy {}

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

resource "google_container_node_pool" "default" {
  name       = "${var.cluster_name}-pool"
  location   = var.zone
  cluster    = google_container_cluster.gke.name
  node_count = var.gke_node_count

  autoscaling {
    min_node_count = 2
    max_node_count = 6
  }

  node_config {
    machine_type = var.gke_machine_type
    disk_type    = "pd-standard"
    disk_size_gb = var.gke_disk_gb
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    labels = {
      env = "prod"
    }
  }

  management {
    auto_repair = true
    auto_upgrade = true
  }
}

resource "google_service_account" "backend" {
  account_id   = "nutrihub-backend"
  display_name = "NutriHub backend"
}

resource "google_storage_bucket" "static_media" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

resource "google_project_iam_member" "backend_bucket_writer" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_service_account_iam_member" "backend_wi" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[nutrihub/backend-sa]"
}

resource "google_compute_instance" "mysql" {
  name         = "mysql-vm"
  machine_type = var.mysql_machine_type
  zone         = var.zone
  tags         = ["mysql"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      type  = "pd-standard"
      size  = var.mysql_disk_gb
    }
  }

  network_interface {
    network = "default"
    access_config {} # remove to go private-only
  }
}

resource "google_compute_firewall" "mysql_from_gke" {
  name    = "allow-mysql-from-gke"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["3306"]
  }

  target_tags   = ["mysql"]
  source_ranges = [google_container_cluster.gke.cluster_ipv4_cidr]
}

resource "google_compute_instance" "locust" {
  name         = "locust-vm"
  machine_type = var.locust_machine_type
  zone         = var.locust_zone
  tags         = ["locust"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      type  = "pd-standard"
      size  = var.locust_disk_gb
    }
  }

  network_interface {
    network = "default"
    access_config {} # external IP for the UI
  }
}

resource "google_compute_firewall" "locust_ui" {
  name    = "allow-locust-ui"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8089"]
  }

  target_tags   = ["locust"]
  source_ranges = var.locust_allow_cidr
}

# Optional: Cloud Scheduler job to trigger daily stats collection
resource "google_cloud_scheduler_job" "daily_stats" {
  count       = var.enable_daily_stats_job ? 1 : 0
  name        = "daily-stats"
  description = "Trigger daily platform statistics collection"
  schedule    = var.stats_job_schedule
  time_zone   = var.stats_job_time_zone

  http_target {
    http_method = "POST"
    uri         = var.stats_job_target_url
    headers = {
      "Content-Type" = "application/json"
      "X-Cron-Auth"  = var.stats_job_auth_header
    }
    body = base64encode("{\"source\":\"cloud-scheduler\"}")
  }
}

# Serverless stats worker (Cloud Run) + optional scheduler
resource "google_vpc_access_connector" "stats_worker" {
  count        = var.enable_stats_worker ? 1 : 0
  name         = var.stats_worker_vpc_connector_name
  region       = var.stats_worker_region != "" ? var.stats_worker_region : var.region
  network      = var.stats_worker_vpc_network
  ip_cidr_range = var.stats_worker_vpc_cidr
}

resource "google_cloud_run_v2_service" "stats_worker" {
  count    = var.enable_stats_worker ? 1 : 0
  name     = "stats-worker"
  location = var.stats_worker_region != "" ? var.stats_worker_region : var.region

  template {
    service_account = null
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.stats_worker_image
      env {
        name  = "CRON_STATS_TOKEN"
        value = var.stats_worker_auth_header
      }
      env {
        name  = "MYSQL_HOST"
        value = var.stats_worker_mysql_host
      }
      env {
        name  = "MYSQL_USER"
        value = var.stats_worker_mysql_user
      }
      env {
        name  = "MYSQL_PASSWORD"
        value = var.stats_worker_mysql_password
      }
      env {
        name  = "MYSQL_DATABASE"
        value = var.stats_worker_mysql_database
      }
      env {
        name  = "MYSQL_PORT"
        value = var.stats_worker_mysql_port
      }
    }

    vpc_access {
      connector = google_vpc_access_connector.stats_worker[0].id
      egress    = "ALL_TRAFFIC"
    }
  }

  ingress     = "INGRESS_TRAFFIC_ALL"
  launch_stage = "GA"
}

resource "google_cloud_run_service_iam_member" "stats_worker_invoker" {
  count    = var.enable_stats_worker ? 1 : 0
  location = google_cloud_run_v2_service.stats_worker[0].location
  project  = var.project_id
  service  = google_cloud_run_v2_service.stats_worker[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_scheduler_job" "stats_worker" {
  count       = var.enable_stats_worker ? 1 : 0
  name        = "stats-worker"
  description = "Trigger Cloud Run stats worker"
  schedule    = var.stats_worker_schedule
  time_zone   = var.stats_worker_time_zone

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.stats_worker[0].uri}/run"
    headers = {
      "Content-Type" = "application/json"
      "X-Cron-Auth"  = var.stats_worker_auth_header
    }
    body = base64encode("{}")
  }
}
