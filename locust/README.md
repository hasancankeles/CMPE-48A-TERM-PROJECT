# Locust Test Scripts

This repo includes multiple Locust scripts for different workload patterns (smoke, infra-only, mixed web/API, spike/step/soak). All scripts target the same host, which you provide via `--host`.

## Quick Start

```bash
pip install locust
locust -f locust/baseline_web_mix.py --host http://136.110.255.27
```

## Scripts

- `locust/baseline_web_mix.py`
  - Balanced “realistic” mix: `/`, `/api/foods/`, `/api/time?name=locust`, `/api/healthz/`.
  - Use this for the main baseline comparisons.

- `locust/infra_only.py`
  - Infra-only signals: `/api/time?name=locust`, `/api/healthz/` (and a light `/` hit).
  - Use this to isolate cluster/LB/backend overhead without the heavier `/api/foods/` endpoint.

- `locust/smoke_low_rps.py`
  - Very light smoke test to validate routing and basic health before a big run.

- `locust/step_load_shape.py`
  - Step-load shape (automatic user count over time) to provoke scaling and find “knee” points.
  - Best used in headless mode.

- `locust/spike_shape.py`
  - Spike test shape to observe transient overload behavior and recovery.
  - Best used in headless mode.

- `locust/soak_shape.py`
  - Soak test shape for longer steady-state stability checks.
  - Best used in headless mode.

## Headless Examples

```bash
# Step-load for 10 minutes (example)
locust -f locust/step_load_shape.py --host http://136.110.255.27 --headless -u 1 -r 1 --run-time 10m

# Spike test for 8 minutes (example)
locust -f locust/spike_shape.py --host http://136.110.255.27 --headless -u 1 -r 1 --run-time 8m

# Soak test for 30 minutes (example)
locust -f locust/soak_shape.py --host http://136.110.255.27 --headless -u 1 -r 1 --run-time 30m
```

Notes:
- For shape-based scripts, the `-u/-r` values are ignored for the user count (the shape controls it), but Locust still requires them.
- Use the Locust Web UI for interactive runs and for exporting charts/tables.

