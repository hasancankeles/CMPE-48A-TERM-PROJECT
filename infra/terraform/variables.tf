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
