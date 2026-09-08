from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from redis import Redis


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "pamirnet-api",
            "build": settings.PAMIRNET_BUILD_SHA,
        }
    )


def readiness(request):
    checks = {"database": False, "redis": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone() == (1,)
    except Exception:
        checks["database"] = False

    try:
        client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        checks["redis"] = bool(client.ping())
    except Exception:
        checks["redis"] = False

    ready = all(checks.values())
    return JsonResponse(
        {
            "status": "ready" if ready else "unavailable",
            "service": "pamirnet-api",
            "build": settings.PAMIRNET_BUILD_SHA,
            "checks": checks,
        },
        status=200 if ready else 503,
    )
