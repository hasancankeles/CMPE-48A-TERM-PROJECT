from datetime import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DailyStats
from .serializers import DailyStatsSerializer
from .services import compute_daily_stats


class RunDailyStatsView(APIView):
    """
    Trigger daily stats computation.
    Protected by a shared secret header expected from Cloud Scheduler/Function.
    """

    permission_classes = []  # rely on shared secret

    def post(self, request):
        expected_secret = getattr(settings, "CRON_STATS_TOKEN", "")
        provided_secret = request.headers.get("X-Cron-Auth")

        if not expected_secret:
            return Response(
                {"error": "CRON_STATS_TOKEN is not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if provided_secret != expected_secret:
            return Response(
                {"error": "unauthorized"}, status=status.HTTP_401_UNAUTHORIZED
            )

        date_str = request.data.get("date") if isinstance(request.data, dict) else None
        target_date = None
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "date must be YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        result = compute_daily_stats(target_date)
        serializer = DailyStatsSerializer(result.stats)
        code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK

        return Response(
            {
                "stats": serializer.data,
                "created": result.created,
                "duration_ms": result.duration_ms,
                "timestamp": timezone.now().isoformat(),
            },
            status=code,
        )


class LatestDailyStatsView(APIView):
    """
    Fetch the most recent daily stats (admin only).
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        latest = DailyStats.objects.order_by("-date").first()
        if not latest:
            return Response(
                {"error": "No stats available"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(DailyStatsSerializer(latest).data)
