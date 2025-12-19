# Live System Access (GCP)

The system is currently deployed on Google Cloud Platform (GKE) and is accessible via the public Load Balancer IP below.

## Endpoints

- Frontend (web UI): `http://136.110.255.27/`
- Backend API base: `http://136.110.255.27/api/`
- Health check: `http://136.110.255.27/api/healthz/`

## Demo Video

- Demo video folder: `https://drive.google.com/drive/folders/1aLoeVQ6kg_AfrwQ5XEJEF-TgjloBCVuz?usp=sharing`

## Repository

- GitHub repository: `https://github.com/hasancankeles/CMPE-48A-TERM-PROJECT.git`

## Quick Verification

- Frontend: open `http://136.110.255.27/` in a browser.
- Backend API (example):
  - `curl -s http://136.110.255.27/api/healthz/`

## Optional: Project Access (Read-Only)

If you want to inspect the live deployment in the GCP Console (Terraform resources, GKE workloads, Cloud Storage buckets, Cloud Functions, Monitoring dashboards, etc.), we can grant temporary read-only access to the GCP project.

Please provide a Google account email address, and we will add it with read-only roles (e.g., Viewer + Kubernetes Engine Viewer + Monitoring Viewer).
