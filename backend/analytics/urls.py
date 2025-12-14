from django.urls import path

from .views import LatestDailyStatsView, RunDailyStatsView

urlpatterns = [
    path("run/", RunDailyStatsView.as_view(), name="run-daily-stats"),
    path("latest/", LatestDailyStatsView.as_view(), name="latest-daily-stats"),
]
