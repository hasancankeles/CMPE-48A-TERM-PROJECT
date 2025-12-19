from locust import HttpUser, task, between


class WebAndApiUser(HttpUser):
    """
    Baseline "mixed" workload:
    - Frontend: GET /
    - Backend API: GET /api/foods/, /api/time?name=locust, /api/healthz/
    """

    wait_time = between(1, 2)

    @task(3)
    def home(self):
        self.client.get("/")

    @task(3)
    def foods_catalog(self):
        self.client.get("/api/foods/")

    @task(1)
    def api_time(self):
        self.client.get("/api/time", params={"name": "locust"})

    @task(1)
    def health(self):
        self.client.get("/api/healthz/")

