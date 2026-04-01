from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Create your views here.


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Публичный endpoint для health check (не требует авторизации)"""
    try:
        # Проверяем подключение к БД
        connection.ensure_connection()
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return Response(
        {"status": "ok", "database": db_status, "service": "cnc_office_api"}, status=200
    )
