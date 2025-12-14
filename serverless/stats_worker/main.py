import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

# Ensure backend code is on path for Django imports
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
sys.path.append(os.path.abspath(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

import django  # noqa: E402

django.setup()

from analytics.services import compute_daily_stats  # noqa: E402

app = FastAPI(title="Stats Worker", version="1.0.0")


def _require_token(header_token: Optional[str], expected: str):
    if not expected:
        raise HTTPException(status_code=503, detail="CRON_STATS_TOKEN not configured")
    if header_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.post("/run")
def run_stats(
    payload: Optional[dict] = Body(default=None),
    auth_header: Optional[str] = Header(default=None, alias="X-Cron-Auth"),
):
    """
    Trigger daily stats computation. Protected by X-Cron-Auth header.
    Optional body: {"date": "YYYY-MM-DD"} to backfill a specific date.
    """
    expected = os.environ.get("CRON_STATS_TOKEN", "")
    _require_token(auth_header, expected)

    target_date = None
    if payload and "date" in payload:
        try:
            target_date = datetime.strptime(payload["date"], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    result = compute_daily_stats(target_date)
    status_code = 201 if result.created else 200
    return JSONResponse(
        status_code=status_code,
        content={
            "stats": {
                "date": str(result.stats.date),
                "computed_at": result.stats.computed_at.isoformat(),
                "duration_ms": result.stats.duration_ms,
                "total_users": result.stats.total_users,
                "total_posts": result.stats.total_posts,
                "total_recipes": result.stats.total_recipes,
                "total_comments": result.stats.total_comments,
                "total_likes": result.stats.total_likes,
                "total_food_entries": result.stats.total_food_entries,
                "total_food_proposals": result.stats.total_food_proposals,
                "total_meal_plans": result.stats.total_meal_plans,
                "total_daily_logs": result.stats.total_daily_logs,
                "total_food_log_entries": result.stats.total_food_log_entries,
                "notes": result.stats.notes,
            },
            "created": result.created,
            "duration_ms": result.duration_ms,
        },
    )


@app.get("/healthz")
def health():
    return {"status": "ok"}
