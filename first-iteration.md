## First Iteration (Post–Node Pool Upgrade) – Load Test Summary

**What changed**
- Switched to a new, larger node pool (`bigger-pool`), keeping the same ingress IP (136.110.255.27).
- Backend still at 500m CPU / 1Gi limits and 250m / 512Mi requests (2 replicas); HPA set to min=2, max=4, target CPU 60%.
- Frontend rebuilt with `VITE_API_BASE_URL=http://136.110.255.27/api` to fix missing `/api/` prefix in requests.

**Test setup**
- Locust UI, endpoints: `/`, `/api/foods/`, `/api/time?name=locust`, `/api/healthz/`.
- Load: ~800 users (steady), spawn rate as configured in UI, runtime ~5 minutes.
- Target: `http://136.110.255.27` (Ingress).

**Key results (Locust)**
- Throughput: peaked ~450–500 req/s then flattened ~120–150 req/s.
- Latency:
  - `/` median ~110 ms, p95 ~120–150 ms.
  - `/api/foods/` median ~3.6 s, p95 ~19 s, p99 ~33 s.
  - `/api/healthz/` median ~3.3 s, p95 ~19 s, p99 ~31 s.
  - `/api/time?name=locust` median ~3.4 s, p95 ~18 s, p99 ~31 s.
  - Aggregated median ~390 ms, p95 ~16 s, p99 ~27 s.
- Failures: 0.

**Infra/resource observations (Cloud Monitoring)**
- Nodes (bigger-pool): CPU low overall; brief bump early then ~10–20% CPU. Memory ample.
- Backend pods: CPU briefly spiked, then low; memory ~200–300 MiB. No sustained node CPU pressure.
- HPA: scaled up to 4 replicas briefly, then back down; min=2, max=4 in effect.
- LB: latency peaked then declined; request rate flattened ~150 rps.
- MySQL VM: CPU modest (~10–20%), memory stable (~12–13 GiB), disk IO low.

**Interpretation**
- Despite larger nodes and frontend fix, backend latency remains high (p95 up to ~19–33s) and RPS flattens because backend pods are still resource-constrained at 500m CPU limits and only 2–4 replicas. DB and nodes are not saturated. The bottleneck remains in the backend tier (insufficient per-pod CPU and replica headroom), not in the load generator or MySQL.

**Next steps**
- Apply higher backend pod resources: requests 1 vCPU / 1.5 GiB; limits 2 vCPU / 2 GiB; restart deployment.
- Increase HPA headroom: minReplicas=2, maxReplicas=8, target CPU=60%.
- Re-run a “push” 10-minute test with higher load (1500 users, spawn rate 100/s) and compare p95/p99 and RPS.
- If latency persists after more CPU/replicas, inspect the app/DB path (slow queries, external calls), because node/VM headroom is not the limiter.
