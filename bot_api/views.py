import os
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from sections.models import SectionTable
from .sheet_utils import get_workbook_sheets, find_sheet_by_name, set_cell_value


def _bot_secret_ok(request) -> bool:
    secret = getattr(settings, 'CNC_BOT_API_SECRET', '') or os.getenv('CNC_BOT_API_SECRET', '')
    if not secret:
        return False
    return request.headers.get('X-CNC-Bot-Token') == secret


def _get_bot_owner():
    User = get_user_model()
    username = getattr(settings, 'CNC_BOT_TABLE_OWNER_USERNAME', None) or os.getenv(
        'CNC_BOT_TABLE_OWNER_USERNAME', ''
    )
    if not username:
        return None
    return User.objects.filter(username=username).first()


class BotGatewayView(APIView):
    """
    Единая точка для VK-бота. Заголовок: X-CNC-Bot-Token
    POST JSON: { "action": "...", ... }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        if not _bot_secret_ok(request):
            return Response({'detail': 'Недопустимый токен бота'}, status=status.HTTP_403_FORBIDDEN)

        action = (request.data.get('action') or '').strip().lower()
        owner = _get_bot_owner()
        if not owner:
            return Response(
                {'detail': 'Задайте CNC_BOT_TABLE_OWNER_USERNAME в окружении (владелец таблицы).'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if action == 'lookup_table':
            return self._lookup_table(request, owner)
        if action == 'list_sheets':
            return self._list_sheets(request, owner)
        if action == 'get_sheet_data':
            return self._get_sheet_data(request, owner)
        if action == 'set_cell':
            return self._set_cell(request, owner)
        return Response({'detail': f'Неизвестное action: {action}'}, status=status.HTTP_400_BAD_REQUEST)

    def _find_table(self, owner, section_type: str, title_contains: str):
        qs = SectionTable.objects.filter(owner=owner, section_type=section_type)
        if title_contains:
            qs = qs.filter(title__icontains=title_contains.strip())
        return qs.order_by('-updated_at').first()

    def _lookup_table(self, request, owner):
        section_type = request.data.get('section_type') or 'rangers'
        title_contains = request.data.get('title_contains') or request.data.get('table_title') or ''
        table = self._find_table(owner, section_type, title_contains)
        if not table:
            return Response({'detail': 'Таблица не найдена'}, status=status.HTTP_404_NOT_FOUND)
        sheets, ai = get_workbook_sheets(table.content or {})
        names = [str(s.get('name') or f'Лист{i+1}') for i, s in enumerate(sheets)]
        return Response({
            'id': table.id,
            'title': table.title,
            'section_type': table.section_type,
            'sheet_names': names,
            'active_sheet_index': ai,
        })

    def _list_sheets(self, request, owner):
        table_id = request.data.get('table_id')
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response({'detail': 'Таблица не найдена'}, status=status.HTTP_404_NOT_FOUND)
        sheets, ai = get_workbook_sheets(table.content or {})
        names = [str(s.get('name') or f'Лист{i+1}') for i, s in enumerate(sheets)]
        return Response({'sheet_names': names, 'active_sheet_index': ai})

    def _get_sheet_data(self, request, owner):
        table_id = request.data.get('table_id')
        sheet_name = request.data.get('sheet_name')
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response({'detail': 'Таблица не найдена'}, status=status.HTTP_404_NOT_FOUND)
        sheets, _ = get_workbook_sheets(table.content or {})
        sh = find_sheet_by_name(sheets, sheet_name)
        if not sh:
            return Response({'detail': 'Лист не найден'}, status=status.HTTP_404_NOT_FOUND)
        data = sh.get('data') or []
        return Response({'data': data, 'sheet_name': sh.get('name')})

    def _set_cell(self, request, owner):
        table_id = request.data.get('table_id')
        sheet_name = request.data.get('sheet_name')
        row = request.data.get('row')
        col = request.data.get('col')
        value = request.data.get('value', '')
        try:
            row = int(row)
            col = int(col)
        except (TypeError, ValueError):
            return Response({'detail': 'row и col должны быть числами (0-based)'}, status=status.HTTP_400_BAD_REQUEST)
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response({'detail': 'Таблица не найдена'}, status=status.HTTP_404_NOT_FOUND)
        content = table.content if isinstance(table.content, dict) else {}
        set_cell_value(content, sheet_name, row, col, '' if value is None else str(value))
        table.content = content
        table.save(update_fields=['content', 'updated_at'])
        return Response({'status': 'ok', 'table_id': table.id, 'row': row, 'col': col})


class BotHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not _bot_secret_ok(request):
            return Response({'ok': False}, status=status.HTTP_403_FORBIDDEN)
        return Response({'ok': True, 'bot_api': 'cnc-office'})
