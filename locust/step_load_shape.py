import os
from dataclasses import dataclass

from locust import HttpUser, LoadTestShape, between, task


@dataclass(frozen=True)
class StepConfig:
    step_users: int
    step_duration_s: int
    max_users: int


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


STEP = StepConfig(
    step_users=_env_int("LOCUST_STEP_USERS", 200),
    step_duration_s=_env_int("LOCUST_STEP_DURATION_S", 60),
    max_users=_env_int("LOCUST_MAX_USERS", 2000),
)


class StepLoadShape(LoadTestShape):
    """
    Step load test: increases user count in steps to help identify the knee point.

    Defaults:
    - +200 users every 60s, up to 2000 users

    Override via env vars:
    - LOCUST_STEP_USERS
    - LOCUST_STEP_DURATION_S
    - LOCUST_MAX_USERS
    """

    def tick(self):
        run_time = self.get_run_time()
        step_index = int(run_time // STEP.step_duration_s)
        user_count = min(STEP.max_users, (step_index + 1) * STEP.step_users)

        if user_count <= 0:
            return None

        # Spawn rate equals step size to reach new level within ~1 minute
        spawn_rate = max(1, STEP.step_users)
        return user_count, spawn_rate


class StepLoadUser(HttpUser):
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

