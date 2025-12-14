from locust import HttpUser, task, between

class SiteUser(HttpUser):
    wait_time = between(1, 5)
    host = "http://34.54.126.66"

    @task(3)
    def view_frontend(self):
        self.client.get("/")

    @task(1)
    def health(self):
        self.client.get("/api/healthz/")
