# Terraform IaC for NutriHub (GCP)

This folder provisions the core infra:
- Artifact Registry (Docker)
- GKE Standard cluster with a managed node pool (Workload Identity enabled)
- Backend service account + bucket for static/media
- MySQL VM (e2-micro) + firewall from the GKE pod CIDR

## Prereqs
- Terraform >= 1.5
- gcloud authenticated (`gcloud auth application-default login`)
- Set vars: `project_id`, `region`, `zone` (defaults: europe-west1, europe-west1-b)

## Usage
```bash
cd infra/terraform
terraform init
terraform apply -var "project_id=term-project-480817"
# review/apply
```

After apply:
1) Get credentials and deploy k8s manifests:
```bash
gcloud container clusters get-credentials <cluster_name> --zone <zone> --project <project_id>
kubectl apply -f deploy/gke/k8s-manifests.yaml
```
2) Replace placeholders in `deploy/gke/k8s-manifests.yaml`:
   - `YOUR_PROJECT_ID` -> your project
   - `MYSQL_HOST` -> the private IP from `mysql_vm_ip` output
   - bucket name and secrets
3) Build/push images to the Artifact Registry repo and redeploy:
```bash
docker build -t <region>-docker.pkg.dev/<project_id>/nutrihub/backend:latest backend
docker push  -t <region>-docker.pkg.dev/<project_id>/nutrihub/backend:latest
docker build -t <region>-docker.pkg.dev/<project_id>/nutrihub/frontend:latest frontend \
  --build-arg VITE_API_BASE_URL=/api --build-arg BUILD=DEV
docker push  -t <region>-docker.pkg.dev/<project_id>/nutrihub/frontend:latest
kubectl rollout restart deploy/backend -n nutrihub
kubectl rollout restart deploy/frontend -n nutrihub
```

Notes:
- GKE uses Workload Identity; KSA `backend-sa` is annotated to use GSA `nutrihub-backend`.
- Firewall `allow-mysql-from-gke` allows the pod CIDR from the created cluster to reach MySQL on 3306.
- MySQL VM has an ephemeral external IP; remove `access_config {}` if you want private-only and use Cloud NAT or bastion.
- Adjust node count/machine types in `variables.tf` to match cost/perf targets.
- Optional daily stats scheduler: set `enable_daily_stats_job=true`, `stats_job_target_url` to the backend endpoint (e.g. `https://<domain>/api/stats/run/`), and `stats_job_auth_header` to the same value you set as `CRON_STATS_TOKEN` in `backend-secrets`.
- Serverless stats worker (Cloud Run): set `enable_stats_worker=true`, `stats_worker_image` to your built image, `stats_worker_auth_header` to the shared secret, and `stats_worker_mysql_host`/credentials to reach MySQL. Scheduler will call the Cloud Run `/run` endpoint daily. A VPC connector is created to reach the MySQL private IP; adjust `stats_worker_vpc_cidr` if needed. The in-cluster GKE stats endpoint is removed.
