output "cluster_name" {
  value = google_container_cluster.gke.name
}

output "cluster_location" {
  value = google_container_cluster.gke.location
}

output "static_ip" {
  value = google_compute_global_address.ingress_ip.address
}

output "artifact_repo" {
  value = google_artifact_registry_repository.repo.repository_id
}

output "bucket_name" {
  value = google_storage_bucket.static_media.name
}

output "mysql_vm_ip" {
  value = google_compute_instance.mysql.network_interface[0].network_ip
}

output "locust_vm_ip" {
  value = google_compute_instance.locust.network_interface[0].access_config[0].nat_ip
}
