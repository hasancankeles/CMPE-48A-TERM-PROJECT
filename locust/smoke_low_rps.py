from locust import HttpUser, task, between


class SmokeUser(HttpUser):
    """
    Low-rate smoke test:
    - Validates that the LB/Ingress routes work and API is reachable.
    - Use before running larger experiments.
    """

    wait_time = between(2, 5)

    @task
    def smoke(self):
        self.client.get("/", name="/")
        self.client.get("/api/healthz/", name="/api/healthz/")
        self.client.get("/api/time", params={"name": "locust"}, name="/api/time?name=locust")

