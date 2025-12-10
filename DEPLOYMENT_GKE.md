# GCP Deployment (GKE Standard)

This walkthrough matches the requested architecture: GKE Standard (3-node pool) behind a Cloud HTTP(S) Load Balancer, backend Django + HPA, frontend Nginx, MySQL on a Compute Engine VM (private IP), Cloud Storage for static/media, Cloud Functions for async jobs, and a Locust VM for load testing.

> All commands assume you are in the repo root and have `gcloud`, `docker`, and `kubectl` installed and authenticated.

## 1) Set environment variables
```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west1"   # pick one
export ZONE="europe-west1-b"   # in the same region
export REPO="nutrihub"
```

## 2) Artifact Registry and images
```bash
gcloud services enable artifactregistry.googleapis.com container.googleapis.com compute.googleapis.com \
  cloudfunctions.googleapis.com cloudbuild.googleapis.com

gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION --description="NutriHub images"
gcloud auth configure-docker $REGION-docker.pkg.dev

# Backend image
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest ./backend
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest

# Frontend image (prod config and API path)
docker build \
  --build-arg VITE_API_BASE_URL=/api \
  --build-arg BUILD=PROD \
  -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest ./frontend
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest
```

## 3) MySQL on a Compute Engine VM (private IP)
```bash
gcloud compute networks subnets list  # choose a subnet (or use default)
gcloud compute instances create mysql-vm \
  --zone=$ZONE --machine-type=e2-medium \
  --subnet=default \
  --tags=mysql \
  --image-family=debian-12 --image-project=debian-cloud

gcloud compute ssh mysql-vm --zone=$ZONE
sudo apt update && sudo apt install -y mysql-server
sudo mysql_secure_installation
mysql -u root -p -e "CREATE DATABASE mydb; CREATE USER 'django'@'%' IDENTIFIED BY 'djangopass'; GRANT ALL PRIVILEGES ON mydb.* TO 'django'@'%'; FLUSH PRIVILEGES;"
```
Open port 3306 only to the cluster:
```bash
CLUSTER_CIDR=$(gcloud container clusters describe nutrihub --zone=$ZONE --format='value(clusterIpv4Cidr)')
gcloud compute firewall-rules create allow-mysql-from-gke \
  --allow=tcp:3306 --target-tags=mysql --source-ranges=$CLUSTER_CIDR
```
Note the VM’s **internal IP**; use it as `MYSQL_HOST` in the manifest.

## 4) Cloud Storage for static/media
```bash
export BUCKET="nutrihub-static-media"
gsutil mb -l $REGION gs://$BUCKET

# Service account for Django to access the bucket
gcloud iam service-accounts create nutrihub-backend --display-name="NutriHub backend"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:nutrihub-backend@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```
Enable Workload Identity on the cluster (next section) and map `backend-sa` (K8s) to this GSA.

> The current code does not yet use Cloud Storage. Add `django-storages` and `google-cloud-storage`, then configure in `backend/project/settings.py`:
```python
INSTALLED_APPS += ["storages"]
DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
GS_BUCKET_NAME = os.environ["CLOUD_STORAGE_BUCKET"]
STATICFILES_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
```
If you skip this, uploaded files will stay on the pod filesystem (not durable).

## 5) Create a GKE Standard cluster (not Autopilot)
```bash
gcloud container clusters create nutrihub \
  --zone=$ZONE \
  --num-nodes=3 \
  --machine-type=e2-standard-4 \
  --workload-pool=$PROJECT_ID.svc.id.goog \
  --release-channel=regular \
  --enable-ip-alias

gcloud container clusters get-credentials nutrihub --zone=$ZONE --project=$PROJECT_ID
```
Bind the backend KSA to the GSA (for bucket access):
```bash
gcloud iam service-accounts add-iam-policy-binding \
  nutrihub-backend@$PROJECT_ID.iam.gserviceaccount.com \
  --member="serviceAccount:$PROJECT_ID.svc.id.goog[nutrihub/backend-sa]" \
  --role="roles/iam.workloadIdentityUser"

kubectl annotate serviceaccount backend-sa \
  iam.gke.io/gcp-service-account=nutrihub-backend@$PROJECT_ID.iam.gserviceaccount.com \
  -n nutrihub --overwrite
```

## 6) Prepare and apply Kubernetes manifests
Update placeholders in `deploy/gke/k8s-manifests.yaml`:
- `YOUR_PROJECT_ID`, `REGION`, `nutrihub-ip`, `MYSQL_HOST`, and bucket name.
- Set real secrets (`DJANGO_SECRET_KEY`, API keys, DB password).

Apply:
```bash
kubectl apply -f deploy/gke/k8s-manifests.yaml
kubectl get pods,svc,ingress,hpa -n nutrihub
```
The Ingress (class `gce`) creates the Cloud HTTP(S) Load Balancer.

## 7) Domain and TLS
```bash
gcloud compute addresses create nutrihub-ip --global
gcloud compute addresses describe nutrihub-ip --global --format='value(address)'
```
- Put that IP in DNS A records for `nutrihub.fit` and `www.nutrihub.fit`.
- Keep the same IP in the Ingress annotation `kubernetes.io/ingress.global-static-ip-name`.
- The `ManagedCertificate` in the manifest will provision TLS automatically.

## 8) Cloud Functions (async jobs)
If you have a Python handler `main.py` with `def hello_http(request): ...`:
```bash
gcloud functions deploy nutrihub-async \
  --region=$REGION \
  --runtime=python312 \
  --trigger-http \
  --allow-unauthenticated
```
Call it from the backend for background work, or trigger via Pub/Sub depending on your logic.

## 9) Locust VM for load testing
```bash
gcloud compute instances create locust-vm \
  --zone=$ZONE --machine-type=e2-medium \
  --subnet=default --tags=locust \
  --image-family=debian-12 --image-project=debian-cloud
gcloud compute ssh locust-vm --zone=$ZONE
sudo apt update && sudo apt install -y python3-pip
pip install locust
cat > locustfile.py <<'EOF'
from locust import HttpUser, task, between
class WebsiteUser(HttpUser):
    wait_time = between(1, 5)
    @task
    def view_home(self):
        self.client.get("/")
    @task
    def hit_api(self):
        self.client.get("/api/")  # adjust to real endpoints
EOF
locust -f locustfile.py --host https://nutrihub.fit --web-port 8089
```
Open firewall for the web UI if needed, or use an SSH tunnel.

## 10) Smoke checks
- `kubectl get ingress -n nutrihub` → note the LB IP.
- `kubectl logs -n nutrihub deploy/backend` to watch migrations/collectstatic.
- `kubectl get hpa -n nutrihub` to see autoscaling status.
- Hit `https://nutrihub.fit` in a browser; `/api/` should return the Django API.

## 11) Teardown (when done)
```bash
gcloud container clusters delete nutrihub --zone=$ZONE
gcloud compute addresses delete nutrihub-ip --global
gcloud compute instances delete mysql-vm locust-vm --zone=$ZONE
gsutil rm -r gs://$BUCKET
gcloud artifacts repositories delete $REPO --location=$REGION
```

That’s the full path to mirror the architecture diagram on GCP. If you want me to wire `django-storages` into the codebase so Cloud Storage is used automatically, tell me and I’ll add the changes. 
