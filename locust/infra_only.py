from locust import HttpUser, task, between


class InfraOnlyUser(HttpUser):
    """
    Infra-only workload to reduce application/third-party variability.
    Focuses on endpoints that should be fast and internal:
    - GET /api/healthz/
    - GET /api/time?name=locust
    Includes a light GET / to still exercise Ingress routing.
    """

    wait_time = between(0.2, 0.8)

    @task(1)
    def home_light(self):
        self.client.get("/")

    @task(4)
    def health(self):
        self.client.get("/api/healthz/")

    @task(4)
    def api_time(self):
        self.client.get("/api/time", params={"name": "locust"})

