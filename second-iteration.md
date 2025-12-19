## Second Iteration – Load Test Summary (post–resource bump, 15k-user push)

**What changed**
- Backend pod resources increased to requests 1 vCPU / 1.5 GiB, limits 2 vCPU / 2 GiB.
- HPA headroom raised to minReplicas=2, maxReplicas=8, target CPU=60% (HPA requested up to 8).
- New larger node pool (`bigger-pool`) in place; frontend rebuilt with correct API base.

**Test setup**
- Locust UI, endpoints: `/`, `/api/foods/`, `/api/time?name=locust`, `/api/healthz/`.
- Load: ~15,000 users (aggressive push), spawn ramp in UI, duration ~5–10 minutes.
- Target: `http://136.110.255.27` (Ingress).

**Key results (Locust)**
- Throughput: burst into 700–900 rps; sustained ~700–800 rps with high failures during the plateau.
- Latency (latest run table):
  - `/` median 7.2 s, p95 22 s, p99 50 s.
  - `/api/foods/` median 7.5 s, p95 37 s, p99 74 s.
  - `/api/healthz/` / `/api/time` median 7.5 s, p95 37 s, p99 72–77 s.
  - Aggregated median 7.4 s, p95 33 s, p99 62 s.
- Failures: ~112k failures (111,937) out of ~209k requests; failures rose as soon as the plateau started.

**Infra/resource observations (Cloud Monitoring & logs)**
- HPA requested 7–8 pods, but cluster-autoscaler scale-up failed: `CPUS_ALL_REGIONS` quota exceeded and node-pool max=3. Only 4 pods remained Running; additional replicas stayed Pending or were deleted.
- Nodes (bigger-pool): CPU low (~18% / 9%); memory ample.
- Backend pods: CPU modest (~100–260m); numerous readiness/liveness probe timeouts during peak; Gunicorn worker timeouts (`WORKER TIMEOUT`, “no URI read”, SIGKILL).
- Load balancer latency climbed with failures; request rate flattened once errors surged.
- MySQL VM: CPU/memory/IO modest—DB not the bottleneck.

**Interpretation**
- At ~15k users the backend could not keep up: p95 33–62 s and >100k failures/surge. HPA asked for up to 8 replicas, but autoscaler was blocked by quota (CPUS_ALL_REGIONS) and node-pool max=3, so extra pods could not land; existing pods then timed out (Gunicorn worker timeouts, probe failures). Nodes and DB were not saturated—capacity was capped by quota and app timeouts under overload.

**Decision**
- This was an experimental push run; increasing capacity would require higher CPU quotas and/or larger nodes. We are not pursuing further scale-up. We will revert to the original smaller node pool plan (3× e2-medium) for ongoing use and documentation.
