import os
from dataclasses import dataclass

from locust import HttpUser, LoadTestShape, between, task


@dataclass(frozen=True)
class SpikeConfig:
    warmup_users: int
    warmup_s: int
    spike_users: int
    spike_s: int
    recovery_users: int
    recovery_s: int


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


SPIKE = SpikeConfig(
    warmup_users=_env_int("LOCUST_WARMUP_USERS", 300),
    warmup_s=_env_int("LOCUST_WARMUP_S", 120),
    spike_users=_env_int("LOCUST_SPIKE_USERS", 1500),
    spike_s=_env_int("LOCUST_SPIKE_S", 120),
    recovery_users=_env_int("LOCUST_RECOVERY_USERS", 500),
    recovery_s=_env_int("LOCUST_RECOVERY_S", 240),
)


class SpikeShape(LoadTestShape):
    """
    Spike test:
    - Warmup -> spike -> recovery

    Defaults (override via env vars):
    - Warmup: 300 users for 120s (LOCUST_WARMUP_USERS / LOCUST_WARMUP_S)
    - Spike: 1500 users for 120s (LOCUST_SPIKE_USERS / LOCUST_SPIKE_S)
    - Recovery: 500 users for 240s (LOCUST_RECOVERY_USERS / LOCUST_RECOVERY_S)
    """

    def tick(self):
        run_time = self.get_run_time()

        if run_time < SPIKE.warmup_s:
            return SPIKE.warmup_users, max(1, SPIKE.warmup_users // 10)

        run_time -= SPIKE.warmup_s
        if run_time < SPIKE.spike_s:
            return SPIKE.spike_users, max(1, SPIKE.spike_users // 5)

        run_time -= SPIKE.spike_s
        if run_time < SPIKE.recovery_s:
            return SPIKE.recovery_users, max(1, SPIKE.recovery_users // 10)

        return None


class SpikeUser(HttpUser):
    wait_time = between(0.2, 0.8)

    @task(6)
    def health(self):
        self.client.get("/api/healthz/")

    @task(6)
    def api_time(self):
        self.client.get("/api/time", params={"name": "locust"})

    @task(2)
    def foods_catalog(self):
        self.client.get("/api/foods/")

