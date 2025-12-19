import os

from locust import HttpUser, LoadTestShape, between, task


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


SOAK_USERS = _env_int("LOCUST_SOAK_USERS", 600)
SOAK_S = _env_int("LOCUST_SOAK_S", 1800)  # 30 minutes


class SoakShape(LoadTestShape):
    """
    Soak test:
    - Holds a constant user count for a longer duration.

    Defaults:
    - 600 users for 1800s (30 minutes)

    Override via env vars:
    - LOCUST_SOAK_USERS
    - LOCUST_SOAK_S
    """

    def tick(self):
        run_time = self.get_run_time()
        if run_time > SOAK_S:
            return None
        return SOAK_USERS, max(1, SOAK_USERS // 20)


class SoakUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(4)
    def foods_catalog(self):
        self.client.get("/api/foods/")

    @task(2)
    def api_time(self):
        self.client.get("/api/time", params={"name": "locust"})

    @task(2)
    def health(self):
        self.client.get("/api/healthz/")

