import time
from datetime import datetime, timezone
from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status

_START_TIME = time.time()


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check_view(request):
    """
    Lightweight health and readiness check for uptime monitors, load balancers, and DevOps.
    Validates database connectivity, server time, and application uptime.
    """
    db_status = "connected"
    db_latency_ms = None
    is_healthy = True

    t0 = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        db_status = f"error: {str(e)}"
        is_healthy = False

    uptime_seconds = int(time.time() - _START_TIME)

    payload = {
        "status": "healthy" if is_healthy else "degraded",
        "service": "PPHAdmin Enterprise Backend API",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime_seconds,
        "database": {
            "status": db_status,
            "engine": connection.settings_dict.get('ENGINE', '').split('.')[-1],
            "latency_ms": db_latency_ms
        }
    }

    http_status = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JsonResponse(payload, status=http_status)
