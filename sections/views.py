# sections/views.py
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.xlsx_export import export_custom_sheet_to_xlsx_bytes
from bot_api.sheet_utils import set_cell_value
from files.models import LiveCellPresence

from .models import SectionTable
from .serializers import SectionTableSerializer

PRESENCE_TTL_SECONDS = 30


def _apply_changed_cells(content, changed_cells):
    result = content if isinstance(content, dict) else {}
    for item in changed_cells:
        if not isinstance(item, dict):
            continue
        try:
            row = int(item.get("row"))
            col = int(item.get("col"))
        except (TypeError, ValueError):
            continue
        if row < 0 or col < 0:
            continue
        sheet_name = item.get("sheet_name")
        value = "" if item.get("value") is None else str(item.get("value"))
        set_cell_value(result, sheet_name, row, col, value)
    return result


def _cleanup_stale_presence(file_type: str, file_id: int):
    cutoff = timezone.now() - timedelta(seconds=PRESENCE_TTL_SECONDS)
    LiveCellPresence.objects.filter(
        file_type=file_type, file_id=file_id, updated_at__lt=cutoff
    ).delete()


def _presence_payload(file_type: str, file_id: int):
    _cleanup_stale_presence(file_type, file_id)
    rows = (
        LiveCellPresence.objects.filter(file_type=file_type, file_id=file_id)
        .select_related("user")
        .order_by("user__username")
    )
    return [
        {
            "username": item.user.username,
            "sheet_name": item.sheet_name or "",
            "row": item.row,
            "col": item.col,
            "updated_at": item.updated_at,
        }
        for item in rows
    ]


class SectionTableViewSet(viewsets.ModelViewSet):
    """
    CRUD для таблиц разделов (Посещаемость, Рейнджеры, Ведомости)
    """

    queryset = SectionTable.objects.all()
    serializer_class = SectionTableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Фильтруем таблицы по section_type из query параметра.
        Показываем таблицы владельца + таблицы с общим доступом.
        """
        user = self.request.user
        from files.models import FilePermission

        permitted_ids = FilePermission.objects.filter(
            file_type="section_table", user=user
        ).values_list("file_id", flat=True)
        queryset = SectionTable.objects.filter(
            Q(owner=user) | Q(id__in=permitted_ids)
        ).distinct()
        section_type = self.request.query_params.get("section_type", None)
        if section_type:
            queryset = queryset.filter(section_type=section_type)
        return queryset.order_by("-updated_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        """
        При создании таблицы автоматически устанавливаем owner и section_type
        """
        section_type = self.request.data.get("section_type", "attendance")
        serializer.save(owner=self.request.user, section_type=section_type)

    @action(detail=True, methods=["post"], url_path="save_content")
    def save_content(self, request, pk=None):
        """
        Сохранение содержимого таблицы (Handsontable data)
        """
        table = self.get_object()
        if table.owner != request.user:
            from files.models import FilePermission

            can_write = FilePermission.objects.filter(
                file_type="section_table",
                file_id=table.id,
                user=request.user,
                permission="write",
            ).exists()
            if not can_write:
                return Response(
                    {"detail": "Нет прав на редактирование"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        content = request.data.get("content", {})
        changed_cells = request.data.get("changed_cells")

        if not isinstance(content, dict):
            return Response(
                {"detail": "content должен быть объектом"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(changed_cells, list) and changed_cells:
            with transaction.atomic():
                locked = SectionTable.objects.select_for_update().get(id=table.id)
                locked.content = _apply_changed_cells(locked.content, changed_cells)
                locked.save(update_fields=["content", "updated_at"])
                table = locked
        else:
            table.content = content
            table.save(update_fields=["content", "updated_at"])

        return Response(
            {
                "status": "saved",
                "table_id": table.id,
                "content_keys": list(content.keys()),
                "updated_at": table.updated_at,
                "content": table.content,
            }
        )

    @action(detail=True, methods=["get", "post"], url_path="presence")
    def presence(self, request, pk=None):
        table = self.get_object()
        file_type = "section_table"
        file_id = table.id

        if request.method == "POST":
            editing = bool(request.data.get("editing", True))
            if not editing:
                LiveCellPresence.objects.filter(
                    file_type=file_type, file_id=file_id, user=request.user
                ).delete()
                return Response(
                    {
                        "status": "cleared",
                        "presence": _presence_payload(file_type, file_id),
                        "ttl_seconds": PRESENCE_TTL_SECONDS,
                    }
                )
            try:
                row = int(request.data.get("row"))
                col = int(request.data.get("col"))
            except (TypeError, ValueError):
                return Response(
                    {"detail": "row и col должны быть числами"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if row < 0 or col < 0:
                return Response(
                    {"detail": "row и col должны быть >= 0"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sheet_name = str(request.data.get("sheet_name") or "").strip()[:120]
            LiveCellPresence.objects.update_or_create(
                file_type=file_type,
                file_id=file_id,
                user=request.user,
                defaults={"sheet_name": sheet_name, "row": row, "col": col},
            )

        return Response(
            {
                "presence": _presence_payload(file_type, file_id),
                "ttl_seconds": PRESENCE_TTL_SECONDS,
            }
        )

    @action(detail=True, methods=["get"], url_path="export_xlsx")
    def export_xlsx(self, request, pk=None):
        table = self.get_object()
        xlsx = export_custom_sheet_to_xlsx_bytes(
            table.title, table.content if isinstance(table.content, dict) else {}
        )
        resp = HttpResponse(
            xlsx,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        filename = (table.title or "table").replace("/", "_").replace("\\", "_")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        return resp

    @action(detail=True, methods=["post"], url_path="share")
    def share(self, request, pk=None):
        """
        Поделиться таблицей с другим пользователем
        """
        table = self.get_object()

        if table.owner != request.user:
            return Response(
                {"detail": "Только владелец может предоставлять доступ"},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = request.data.get("username")
        permission = request.data.get("permission", "read")

        if not username:
            return Response(
                {"detail": "Укажите имя пользователя"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": f"Пользователь {username} не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user == table.owner:
            return Response(
                {"detail": "Вы уже владелец этой таблицы"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from files.models import FilePermission

        perm, created = FilePermission.objects.get_or_create(
            file_type="section_table",
            file_id=table.id,
            user=user,
            defaults={"permission": permission},
        )

        if not created:
            perm.permission = permission
            perm.save()

        return Response(
            {"status": "shared", "username": username, "permission": permission}
        )

    @action(
        detail=False, methods=["get"], url_path="by_section/(?P<section_type>[^/.]+)"
    )
    def by_section(self, request, section_type=None):
        """
        Получить все таблицы для конкретного раздела
        """
        tables = SectionTable.objects.filter(
            section_type=section_type, owner=request.user
        ).order_by("-updated_at")
        serializer = self.get_serializer(tables, many=True)
        return Response(serializer.data)
