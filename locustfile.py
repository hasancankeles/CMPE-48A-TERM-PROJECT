from locust import HttpUser, task, between


class WebsiteUser(HttpUser):
    # Keep a modest think time to mimic real users
    wait_time = between(1, 2)

    @task(3)
    def home(self):
        self.client.get("/")

    @task(3)
    def foods_catalog(self):
        self.client.get("/api/foods/")

    @task(1)
    def api_time(self):
        # Add required name param to avoid 400s
        self.client.get("/api/time", params={"name": "locust"})

    @task(1)
    def health(self):
        self.client.get("/api/healthz/")
