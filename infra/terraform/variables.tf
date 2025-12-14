variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "europe-west1-b"
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
  default     = "nutrihub"
}

variable "gke_machine_type" {
  description = "Machine type for GKE nodes"
  type        = string
  default     = "e2-medium"
}

variable "gke_node_count" {
  description = "Number of nodes in the default pool"
  type        = number
  default     = 3
}

variable "gke_disk_gb" {
  description = "Disk size for GKE nodes"
  type        = number
  default     = 30
}

variable "mysql_machine_type" {
  description = "Machine type for the MySQL VM"
  type        = string
  default     = "e2-micro"
}

variable "mysql_disk_gb" {
  description = "Boot disk size for the MySQL VM"
  type        = number
  default     = 20
}

variable "locust_machine_type" {
  description = "Machine type for the Locust load test VM"
  type        = string
  default     = "e2-standard-2"
}

variable "locust_zone" {
  description = "Zone for the Locust VM"
  type        = string
  default     = "us-central1-a"
}

variable "locust_disk_gb" {
  description = "Boot disk size for the Locust VM"
  type        = number
  default     = 20
}

variable "locust_allow_cidr" {
  description = "CIDR(s) allowed to reach the Locust UI (8089). Restrict to your IP."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "artifact_repo" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "nutrihub"
}

variable "bucket_name" {
  description = "GCS bucket for static/media"
  type        = string
  default     = "nutrihub-static-media"
}

variable "static_ip_name" {
  description = "Global static IP name for the ingress"
  type        = string
  default     = "nutrihub-ip"
}

variable "enable_daily_stats_job" {
  description = "Whether to create the daily stats Cloud Scheduler job"
  type        = bool
  default     = false
}

variable "stats_job_target_url" {
  description = "HTTPS endpoint that triggers daily stats computation"
  type        = string
  default     = ""
}

variable "stats_job_auth_header" {
  description = "Shared secret value sent as X-Cron-Auth to the stats endpoint"
  type        = string
  default     = ""
  sensitive   = true
}

variable "stats_job_schedule" {
  description = "Cron schedule for the stats job"
  type        = string
  default     = "0 0 * * *"
}

variable "stats_job_time_zone" {
  description = "Time zone for the stats scheduler"
  type        = string
  default     = "Etc/UTC"
}
