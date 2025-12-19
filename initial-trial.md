## Initial Trial – Load Test Summary

**Test setup**
- Scenario: Locust UI (HTTP), endpoints `/`, `/api/foods/`, `/api/time?name=locust`, `/api/healthz/` (random-meal excluded).
- Load pattern: 800 users, spawn rate 50 users/s, runtime 10 minutes.
- Target: GKE Ingress/LB at `http://136.110.255.27`.
- Backend deployment: 2 vCPU/4 GiB nodepool (3× e2-medium). Backend pods limited to ~500m CPU each; HPA min=2, max=6, target CPU=60%. MySQL on e2-micro.

**Key metrics (Locust UI)**
- Throughput: ~100–150 req/s steady.
- Latency:
  - `/` median ~110 ms, p95 ~110 ms.
  - `/api/foods/` median ~6.8 s, p95 ~18 s, p99 ~22 s.
  - `/api/healthz/` and `/api/time?name=locust` similar to `/api/foods/` (median ~6.5–6.6 s, p95 ~18 s, p99 ~22 s).
  - Aggregated median ~1.1 s, p95 ~17 s, p99 ~21 s.
- Errors: 2352 of 73844 of requests failed in total.

**Infra/resource observations (Cloud Monitoring)**
- Backend HPA: scaled to max=6 and stayed pinned there for the run (ScalingLimited=True).
- Backend pod CPU: ~0.5 cores per pod (matches 500m limit), flat-topped → CPU-limited/throttled. Pod memory ~900 MiB, stable.
- Nodes: one node ~1.0–1.2 cores (60% of e2-medium), others ~0.5–0.7 cores → cluster had spare headroom; pod CPU limits prevented using it.
- LB: request rate ~100–150 rps; latency rose to ~2–3 s; 5xx spikes during peak.
- MySQL VM (e2-micro): CPU ~10–20%, memory ~8.8 GiB steady, disk IO ~1.5 MiB/s → DB not saturated.
- Frontend was rebuilt with `VITE_API_BASE_URL=http://136.110.255.27/api` to fix 405s from missing `/api/` prefix.

**Interpretation (bottleneck)**
- The app tier is the bottleneck. Each backend pod is capped at 500m CPU, and HPA maxed out at 6 replicas, so total backend compute is constrained. Nodes still had free CPU, and DB was healthy, while request latency and LB 5xx increased under load. Classic signal of pod CPU saturation/throttling and insufficient replica ceiling.

**Infra constraints observed**
- Regional `IN_USE_ADDRESSES` quota is 4. We resolved capacity by scaling the old pool to 0 and creating a new, larger pool (`bigger-pool`) with bigger nodes; ingress IP stayed the same.

**Planned remediation test (iteration 2)**
- Objective: relieve backend CPU throttling on the new larger node pool and demonstrate improved p95/p99 and fewer 5xx.
- Backend resources (planned): requests 600m CPU / 900Mi; limits 1 vCPU / 1.5 GiB; 2 replicas.
- HPA: min=2, max=6, target CPU=60%.
- Load: 600 users, spawn rate 30 users/s, duration 5 minutes (same endpoints as baseline).
- Success criteria: lower p95/p99 vs baseline on `/api/foods/`, reduced LB 5xx, backend pods not pinned at 100% of request; HPA scales within 2–4 as needed.
