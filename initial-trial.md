## Initial Trial – Load Test Summary

**Test setup**
- Scenario: Locust UI (HTTP), endpoints `/`, `/api/foods/`, `/api/time?name=locust`, `/api/healthz/` (random-meal excluded).
- Load pattern: 800 users, spawn rate 50 users/s, runtime 5 minutes.
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

**Interpretation (bottleneck)**
- The app tier is the bottleneck. Each backend pod is capped at 500m CPU, and HPA maxed out at 6 replicas, so total backend compute is constrained. Nodes still had free CPU, and DB was healthy, while request latency and LB 5xx increased under load. Classic signal of pod CPU saturation/throttling and insufficient replica ceiling.

**Next steps (to validate improvement)**
- Increase backend pod resources (limits 1 vCPU / 1.5 GiB; requests 750m / 1 GiB).
- Raise HPA ceiling (max 10) and keep target CPU ~60%.
- We will re-run the same 5-minute 800-user, 50/s test and compare p95/p99, Locust failures, and pod CPU headroom.
