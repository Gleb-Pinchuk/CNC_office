import logging
import os
import re
from hmac import compare_digest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.xlsx_export import export_custom_sheet_to_xlsx_bytes
from sections.models import SectionTable, SectionTableMonthlyArchive

from .remark_utils import parse_input_date
from .reports import generate_monitoring_report_docx, report_filename
from .sheet_utils import find_sheet_by_name, get_workbook_sheets, set_cell_value
from .student_sheet import find_one_student_row, list_groups, search_students
from .week_column import pick_week_col_by_date

logger = logging.getLogger(__name__)


def _bot_secret_ok(request) -> bool:
    secret = getattr(settings, "CNC_BOT_API_SECRET", "") or os.getenv(
        "CNC_BOT_API_SECRET", ""
    )
    if not secret:
        logger.warning("CNC_BOT_API_SECRET не задан")
        return False
    token = request.headers.get("X-CNC-Bot-Token", "")
    return compare_digest(token, secret)


def _get_bot_owner():
    User = get_user_model()
    username = getattr(settings, "CNC_BOT_TABLE_OWNER_USERNAME", None) or os.getenv(
        "CNC_BOT_TABLE_OWNER_USERNAME", ""
    )
    if not username:
        logger.error("CNC_BOT_TABLE_OWNER_USERNAME не задан в окружении")
        return None
    # Создаем пользователя если он не существует
    owner, created = User.objects.get_or_create(username=username)
    if created:
        logger.info(f"Создан пользователь-владелец таблиц: {username}")
    return owner


class BotGatewayView(APIView):
    """
    Единая точка для VK-бота. Заголовок: X-CNC-Bot-Token
    POST JSON: { "action": "...", ... }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        if not _bot_secret_ok(request):
            return Response(
                {"detail": "Недопустимый токен бота"}, status=status.HTTP_403_FORBIDDEN
            )

        action = (request.data.get("action") or "").strip().lower()
        owner = _get_bot_owner()
        if not owner:
            return Response(
                {
                    "detail": "Задайте CNC_BOT_TABLE_OWNER_USERNAME в окружении (владелец таблицы)."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if action == "lookup_table":
            return self._lookup_table(request, owner)
        if action == "list_sheets":
            return self._list_sheets(request, owner)
        if action == "get_sheet_data":
            return self._get_sheet_data(request, owner)
        if action == "set_cell":
            return self._set_cell(request, owner)
        if action == "list_groups":
            return self._list_groups(request, owner)
        if action == "search_students":
            return self._search_students(request, owner)
        if action == "set_student_remark":
            return self._set_student_remark(request, owner)
        if action == "list_students":
            return self._list_students(request, owner)
        if action == "get_student_profile":
            return self._get_student_profile(request, owner)
        if action == "set_student_status":
            return self._set_student_status(request, owner)
        if action == "export_table_xlsx":
            return self._export_table_xlsx(request, owner)
        if action == "list_report_archives":
            return self._list_report_archives(request, owner)
        if action == "export_monitoring_report_docx":
            return self._export_monitoring_report_docx(request, owner)
        return Response(
            {"detail": f"Неизвестное action: {action}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _sheet_data_for_table(self, table: SectionTable, sheet_name: str):
        sheets, _ = get_workbook_sheets(table.content or {})
        sh = find_sheet_by_name(sheets, sheet_name)
        if not sh:
            return None, None
        return sh, sh.get("data") or []

    def _bot_cols(self):
        return (
            int(getattr(settings, "BOT_SHEET_FIO_COL", 2)),
            int(getattr(settings, "BOT_SHEET_GROUP_COL", 1)),
            int(getattr(settings, "BOT_SHEET_STATUS_COL", 12)),
            int(getattr(settings, "BOT_SHEET_REMARK_COL", 11)),
        )

    @staticmethod
    def _status_col_from_header(sheet_data, fallback_col: int) -> int:
        if not sheet_data or not isinstance(sheet_data[0], list):
            return fallback_col
        for idx, value in enumerate(sheet_data[0]):
            header = str(value or "").strip().lower()
            if header in {"состояние", "статус", "статус учебы", "статус обучения"}:
                return idx
        return fallback_col

    def _social_cols(self):
        raw = (
            getattr(settings, "BOT_SHEET_SOCIAL_COLS", "")
            or os.getenv("BOT_SHEET_SOCIAL_COLS", "4,5,6")
        )
        out = []
        for part in str(raw).split(","):
            p = part.strip()
            if not p:
                continue
            try:
                out.append(int(p))
            except ValueError:
                continue
        return out

    @staticmethod
    def _platform_label(platform: str) -> str:
        p = (platform or "").strip().lower()
        if p == "vk":
            return "VK"
        if p == "tiktok":
            return "TikTok"
        return "TG"

    @staticmethod
    def _platform_from_header(header_value: str) -> str:
        hv = (header_value or "").strip().lower()
        if not hv:
            return ""
        if "tiktok" in hv or "тикток" in hv or "тик ток" in hv:
            return "tiktok"
        if "vk" in hv or "вк" in hv or "вконтакте" in hv:
            return "vk"
        if "tg" in hv or "тг" in hv or "telegram" in hv or "телеграм" in hv:
            return "tg"
        return ""

    @staticmethod
    def _clean_token(token: str) -> str:
        t = (token or "").strip()
        t = t.strip("()[]{}<>\"'`")
        t = t.rstrip(".,:;!?")
        # Часто в таблице пишут префиксы вроде "тг:@name", "vk: id123"
        t = re.sub(
            r"^(tg|тг|telegram|телеграм|vk|вк|tiktok|тикток)\s*[:\-]\s*",
            "",
            t,
            flags=re.IGNORECASE,
        )
        return t.strip()

    @staticmethod
    def _guess_platform(token: str, raw_cell: str, default_platform: str) -> str:
        t = (token or "").lower()
        cell = (raw_cell or "").lower()
        if "tiktok" in t or "tiktok" in cell or "тикток" in t or "тикток" in cell:
            return "tiktok"
        if "vk.com" in t or t.startswith("id") or t.startswith("club") or t.startswith("public"):
            return "vk"
        if "t.me" in t or "telegram" in t or "телеграм" in t:
            return "tg"
        if t.startswith("@"):
            # Если в ячейке было явно "vk"/"tiktok", @ считаем для этой сети.
            if "vk" in cell or "вк" in cell:
                return "vk"
            if "tiktok" in cell or "тикток" in cell:
                return "tiktok"
            return default_platform or "tg"
        return default_platform or "tg"

    @staticmethod
    def _normalize_social_url(token: str, platform: str) -> str:
        t = (token or "").strip()
        if not t:
            return ""
        if t.startswith(("http://", "https://")):
            return t
        if "vk.com/" in t and not t.startswith(("http://", "https://")):
            return f"https://{t}"
        if "t.me/" in t and not t.startswith(("http://", "https://")):
            return f"https://{t}"
        if "tiktok.com/" in t and not t.startswith(("http://", "https://")):
            return f"https://{t}"
        if t.startswith("@"):
            nick = t[1:]
            if not nick:
                return ""
            if platform == "vk":
                return f"https://vk.com/{nick}"
            if platform == "tiktok":
                return f"https://www.tiktok.com/@{nick}"
            return f"https://t.me/{nick}"
        # Plain username without protocol/@
        if platform == "tiktok":
            nick = t.lstrip("@")
            if re.match(r"^[A-Za-z0-9._]{2,64}$", nick):
                return f"https://www.tiktok.com/@{nick}"
        if platform == "tg" and re.match(r"^[A-Za-z0-9_]{3,64}$", t):
            return f"https://t.me/{t}"
        if platform == "vk" and re.match(r"^[A-Za-z0-9._]{2,64}$", t):
            return f"https://vk.com/{t}"
        if platform == "vk" and re.match(r"^(id|club|public)\d+$", t, flags=re.IGNORECASE):
            return f"https://vk.com/{t}"
        return ""

    def _extract_social_links(self, row, header_row=None):
        if not isinstance(row, list):
            return [], []
        links = []
        profiles = []
        seen = set()
        seen_cols = set()
        preferred = ["tg", "vk", "tiktok"]
        candidates = []
        for pos, idx in enumerate(self._social_cols()):
            candidates.append((idx, pos))
            seen_cols.add(idx)
        if isinstance(header_row, list):
            for idx, header_value in enumerate(header_row):
                if idx in seen_cols:
                    continue
                if self._platform_from_header(str(header_value or "")):
                    candidates.append((idx, None))
                    seen_cols.add(idx)
        for pos, (idx, configured_pos) in enumerate(candidates):
            if idx < 0 or idx >= len(row):
                continue
            raw = "" if row[idx] is None else str(row[idx]).strip()
            if not raw:
                continue
            header_hint = ""
            if isinstance(header_row, list) and idx < len(header_row):
                header_hint = str(header_row[idx] or "")
            default_platform = self._platform_from_header(header_hint) or (
                preferred[configured_pos]
                if configured_pos is not None and configured_pos < len(preferred)
                else preferred[pos]
                if pos < len(preferred)
                else "tg"
            )
            parts = [p for p in re.split(r"[\s,;\n]+", raw) if p and p.strip()]
            if not parts:
                parts = [raw]
            for part in parts:
                cleaned = self._clean_token(part)
                if not cleaned:
                    continue
                platform = self._guess_platform(cleaned, raw, default_platform)
                link = self._normalize_social_url(cleaned, platform)
                if not link or link in seen:
                    continue
                seen.add(link)
                links.append(link)
                profiles.append({"label": self._platform_label(platform), "url": link})
        return links, profiles

    def _list_groups(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        _, gcol, _, _ = self._bot_cols()
        _, data = self._sheet_data_for_table(table, sheet_name)
        if data is None:
            return Response(
                {"detail": "Лист не найден"}, status=status.HTTP_404_NOT_FOUND
            )
        groups = list_groups(data, gcol)
        return Response({"groups": groups, "sheet_name": sheet_name})

    def _list_students(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        group_filter = request.data.get("group") or request.data.get("group_name")
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        fio_c, gcol, st_c, _ = self._bot_cols()
        _, data = self._sheet_data_for_table(table, sheet_name)
        if data is None:
            return Response(
                {"detail": "Лист не найден"}, status=status.HTTP_404_NOT_FOUND
            )
        st_c = self._status_col_from_header(data, st_c)
        students = search_students(
            data,
            fio_col=fio_c,
            group_col=gcol,
            status_col=st_c,
            group_filter=group_filter,
            query=None,
            skip_dismissed=False,
        )
        return Response({"students": students, "sheet_name": sheet_name})

    def _search_students(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        group_filter = request.data.get("group") or request.data.get("group_name")
        query = request.data.get("query") or request.data.get("q")
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        fio_c, gcol, st_c, _ = self._bot_cols()
        _, data = self._sheet_data_for_table(table, sheet_name)
        if data is None:
            return Response(
                {"detail": "Лист не найден"}, status=status.HTTP_404_NOT_FOUND
            )
        st_c = self._status_col_from_header(data, st_c)
        students = search_students(
            data,
            fio_col=fio_c,
            group_col=gcol,
            status_col=st_c,
            group_filter=group_filter,
            query=query,
            skip_dismissed=False,
        )
        return Response({"students": students, "sheet_name": sheet_name})

    def _get_student_profile(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        student_fio = (request.data.get("student_fio") or "").strip()
        group_filter = request.data.get("group") or request.data.get("group_name")
        if not student_fio:
            return Response(
                {"detail": "Нужен student_fio"}, status=status.HTTP_400_BAD_REQUEST
            )
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        fio_c, gcol, st_c, rcol_default = self._bot_cols()
        remark_date_raw = (request.data.get("remark_date") or "").strip()
        remark_date = parse_input_date(remark_date_raw) if remark_date_raw else None
        _, data = self._sheet_data_for_table(table, sheet_name)
        if data is None:
            return Response(
                {"detail": "Лист не найден"}, status=status.HTTP_404_NOT_FOUND
            )
        st_c = self._status_col_from_header(data, st_c)
        one, allm = find_one_student_row(
            data,
            student_fio,
            fio_col=fio_c,
            group_col=gcol,
            status_col=st_c,
            group_filter=group_filter,
            skip_dismissed=False,
        )
        if not one:
            return Response({"detail": "Студент не найден"}, status=status.HTTP_404_NOT_FOUND)
        if len(allm) > 1 and not (group_filter or "").strip():
            return Response(
                {"detail": "Несколько совпадений, укажите group", "candidates": allm[:15]},
                status=status.HTTP_409_CONFLICT,
            )
        row_idx = one["row_index"]
        row = data[row_idx] if row_idx < len(data) and isinstance(data[row_idx], list) else []
        rcol = pick_week_col_by_date(data, remark_date) if remark_date else None
        if rcol is None:
            rcol = rcol_default
        remark_value = ""
        if rcol < len(row):
            remark_value = "" if row[rcol] is None else str(row[rcol])
        header_row = data[0] if data and isinstance(data[0], list) else None
        social_links, social_profiles = self._extract_social_links(row, header_row=header_row)
        return Response(
            {
                "student": {
                    "row_index": row_idx,
                    "fio": one.get("fio", ""),
                    "group": one.get("group", ""),
                    "status": one.get("status", ""),
                    "remark_value": remark_value,
                    "remark_col": rcol,
                    # Backward-compat для старых клиентов бота
                    "social_links": social_links,
                    # Новый формат для красивого отображения с подписью сети
                    "social_profiles": social_profiles,
                }
            }
        )

    def _set_student_remark(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        student_fio = (request.data.get("student_fio") or "").strip()
        remark_date_raw = (request.data.get("remark_date") or "").strip()
        remark_text = request.data.get("remark_text")
        if remark_text is not None:
            remark_text = str(remark_text).strip()
        group_filter = request.data.get("group") or request.data.get("group_name")
        no_phrase = (request.data.get("no_remarks_phrase") or "замечаний нет").strip()

        if not student_fio or not remark_date_raw:
            return Response(
                {"detail": "Нужны student_fio и remark_date (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rd = parse_input_date(remark_date_raw)
        if not rd:
            return Response(
                {"detail": "Неверный формат даты remark_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fio_c, gcol, st_c, rcol_default = self._bot_cols()
        with transaction.atomic():
            table = (
                SectionTable.objects.select_for_update()
                .filter(owner=owner, id=table_id)
                .first()
            )
            if not table:
                return Response(
                    {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
                )
            sh, data = self._sheet_data_for_table(table, sheet_name)
            if data is None:
                return Response(
                    {"detail": "Лист не найден"}, status=status.HTTP_404_NOT_FOUND
                )
            st_c = self._status_col_from_header(data, st_c)
            one, allm = find_one_student_row(
                data,
                student_fio,
                fio_col=fio_c,
                group_col=gcol,
                status_col=st_c,
                group_filter=group_filter,
            )
            if not one:
                return Response(
                    {"detail": "Студент не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if len(allm) > 1 and not (group_filter or "").strip():
                return Response(
                    {
                        "detail": "Несколько совпадений, укажите group",
                        "candidates": allm[:15],
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            row_idx = one["row_index"]
            if row_idx >= len(data):
                return Response(
                    {"detail": "Некорректная строка"}, status=status.HTTP_400_BAD_REQUEST
                )
            row = data[row_idx]
            rcol = pick_week_col_by_date(data, rd) or rcol_default
            # В выбранной недельной колонке храним только итоговый текст замечания,
            # без префикса даты (дата уже определяет саму колонку недели).
            if remark_text and str(remark_text).strip():
                new_cell = str(remark_text).strip()
            else:
                new_cell = no_phrase
            content = table.content if isinstance(table.content, dict) else {}
            set_cell_value(content, sheet_name, row_idx, rcol, new_cell)
            table.content = content
            table.needs_nextcloud_push = True
            table.save(update_fields=["content", "needs_nextcloud_push", "updated_at"])
        logger.info(
            "Замечание по студенту: table=%s sheet=%s row=%s date=%s",
            table_id,
            sheet_name,
            row_idx,
            remark_date_raw,
        )
        return Response(
            {
                "status": "ok",
                "table_id": table.id,
                "row_index": row_idx,
                "remark_col": rcol,
            }
        )

    def _set_student_status(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        student_fio = (request.data.get("student_fio") or "").strip()
        new_status = (request.data.get("status_value") or "").strip()
        group_filter = request.data.get("group") or request.data.get("group_name")
        if not student_fio or not new_status:
            return Response(
                {"detail": "Нужны student_fio и status_value"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fio_c, gcol, st_c, _ = self._bot_cols()
        with transaction.atomic():
            table = (
                SectionTable.objects.select_for_update()
                .filter(owner=owner, id=table_id)
                .first()
            )
            if not table:
                return Response(
                    {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
                )
            _, data = self._sheet_data_for_table(table, sheet_name)
            if data is None:
                return Response(
                    {"detail": "Лист не найден"}, status=status.HTTP_404_NOT_FOUND
                )
            st_c = self._status_col_from_header(data, st_c)
            one, allm = find_one_student_row(
                data,
                student_fio,
                fio_col=fio_c,
                group_col=gcol,
                status_col=st_c,
                group_filter=group_filter,
                skip_dismissed=False,
            )
            if not one:
                return Response(
                    {"detail": "Студент не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if len(allm) > 1 and not (group_filter or "").strip():
                return Response(
                    {
                        "detail": "Несколько совпадений, укажите group",
                        "candidates": allm[:15],
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            row_idx = one["row_index"]
            content = table.content if isinstance(table.content, dict) else {}
            set_cell_value(content, sheet_name, row_idx, st_c, new_status)
            table.content = content
            table.needs_nextcloud_push = True
            table.save(update_fields=["content", "needs_nextcloud_push", "updated_at"])
        return Response(
            {
                "status": "ok",
                "table_id": table.id,
                "row_index": row_idx,
                "status_col": st_c,
            }
        )

    def _find_table(self, owner, section_type: str, title_contains: str):
        qs = SectionTable.objects.filter(owner=owner, section_type=section_type)
        if title_contains:
            # Нормализуем поисковый запрос: убираем лишние пробелы, заменяем дефисы/подчеркивания
            search_term = title_contains.strip().lower()
            # Пробуем найти по частичному совпадению
            qs = qs.filter(title__icontains=search_term)

        table = qs.order_by("-updated_at").first()

        # Если не нашли, пробуем без учета title_contains (возможно таблица называется иначе)
        if not table and title_contains:
            logger.warning(
                f"Таблица с '{title_contains}' не найдена, пробуем найти любую таблицу типа {section_type}"
            )
            qs_fallback = SectionTable.objects.filter(owner=owner, section_type=section_type)
            table = qs_fallback.order_by("-updated_at").first()

        return table

    def _lookup_table(self, request, owner):
        section_type = request.data.get("section_type") or "rangers"
        title_contains = (
                request.data.get("title_contains") or request.data.get("table_title") or ""
        )

        logger.info(
            f"Поиск таблицы: owner={owner.username}, section_type={section_type}, title_contains={title_contains}")

        table = self._find_table(owner, section_type, title_contains)

        if not table:
            # Детальная отладка: какие таблицы вообще есть
            all_tables = SectionTable.objects.filter(owner=owner)
            if all_tables.exists():
                all_info = [(t.id, t.title, t.section_type) for t in all_tables]
                logger.error(f"Таблица не найдена. Доступные таблицы у владельца {owner.username}: {all_info}")
            else:
                logger.error(f"У владельца {owner.username} нет ни одной таблицы в БД")

            # Проверяем таблицы без привязки к владельцу (для диагностики)
            all_any = SectionTable.objects.filter(section_type=section_type)
            if all_any.exists():
                other_owners = [(t.id, t.title, t.owner.username if t.owner else 'None') for t in all_any[:10]]
                logger.warning(f"Таблицы типа '{section_type}' существуют, но у других владельцев: {other_owners}")

            return Response(
                {
                    "detail": f"Таблица не найдена. Проверьте: 1) CNC_BOT_TABLE_OWNER_USERNAME='{owner.username}' 2) section_type='{section_type}' 3) title содержит '{title_contains}'. Таблицы в БД могут иметь другого владельца.",
                    "debug": {
                        "owner_username": owner.username,
                        "section_type": section_type,
                        "title_search": title_contains,
                        "tables_count": all_tables.count(),
                    }
                },
                status=status.HTTP_404_NOT_FOUND
            )

        logger.info(f"Таблица найдена: id={table.id}, title={table.title}")
        sheets, ai = get_workbook_sheets(table.content or {})
        names = [str(s.get("name") or f"Лист{i + 1}") for i, s in enumerate(sheets)]
        return Response(
            {
                "id": table.id,
                "title": table.title,
                "section_type": table.section_type,
                "sheet_names": names,
                "active_sheet_index": ai,
            }
        )

    def _list_sheets(self, request, owner):
        table_id = request.data.get("table_id")
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        sheets, ai = get_workbook_sheets(table.content or {})
        names = [str(s.get("name") or f"Лист{i + 1}") for i, s in enumerate(sheets)]
        return Response({"sheet_names": names, "active_sheet_index": ai})

    def _get_sheet_data(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        sheets, _ = get_workbook_sheets(table.content or {})
        sh = find_sheet_by_name(sheets, sheet_name)
        if not sh:
            return Response(
                {"detail": "Лист не найден"}, status=status.HTTP_404_NOT_FOUND
            )
        data = sh.get("data") or []
        return Response({"data": data, "sheet_name": sh.get("name")})

    def _set_cell(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = request.data.get("sheet_name")
        row = request.data.get("row")
        col = request.data.get("col")
        value = request.data.get("value", "")
        try:
            row = int(row)
            col = int(col)
        except (TypeError, ValueError):
            return Response(
                {"detail": "row и col должны быть числами (0-based)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            table = (
                SectionTable.objects.select_for_update()
                .filter(owner=owner, id=table_id)
                .first()
            )
            if not table:
                return Response(
                    {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
                )
            content = table.content if isinstance(table.content, dict) else {}
            set_cell_value(
                content, sheet_name, row, col, "" if value is None else str(value)
            )
            table.content = content
            table.needs_nextcloud_push = True
            table.save(update_fields=["content", "needs_nextcloud_push", "updated_at"])
        logger.info(f"Ячейка обновлена: table_id={table_id}, sheet={sheet_name}, row={row}, col={col}, value={value}")
        return Response({"status": "ok", "table_id": table.id, "row": row, "col": col})

    def _export_table_xlsx(self, request, owner):
        table_id = request.data.get("table_id")
        section_type = request.data.get("section_type") or "rangers"
        title_contains = (
            request.data.get("title_contains") or request.data.get("table_title") or ""
        )
        year = request.data.get("year")
        month = request.data.get("month")
        if table_id:
            table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        else:
            table = self._find_table(owner, section_type, title_contains)
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        content = table.content if isinstance(table.content, dict) else {}
        filename = (table.title or "table").replace("/", "_").replace("\\", "_")
        if year and month:
            try:
                year_i = int(year)
                month_i = int(month)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "year и month должны быть числами"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            archive = SectionTableMonthlyArchive.objects.filter(
                table=table, year=year_i, month=month_i
            ).first()
            if not archive:
                return Response(
                    {"detail": "Архив таблицы за указанный месяц не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            content = archive.content if isinstance(archive.content, dict) else {}
            filename = f"{filename}_{month_i:02d}.{year_i}"
        xlsx = export_custom_sheet_to_xlsx_bytes(
            table.title, content
        )
        resp = HttpResponse(
            xlsx,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        return resp

    def _list_report_archives(self, request, owner):
        table_id = request.data.get("table_id")
        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )
        archives = [
            {
                "year": archive.year,
                "month": archive.month,
                "label": f"{archive.month:02d}.{archive.year}",
            }
            for archive in table.monthly_archives.order_by("-year", "-month")[:3]
        ]
        return Response({"archives": archives})

    def _export_monitoring_report_docx(self, request, owner):
        table_id = request.data.get("table_id")
        sheet_name = (request.data.get("sheet_name") or "").strip()
        if not sheet_name:
            return Response(
                {"detail": "Нужен sheet_name"}, status=status.HTTP_400_BAD_REQUEST
            )

        table = SectionTable.objects.filter(owner=owner, id=table_id).first()
        if not table:
            return Response(
                {"detail": "Таблица не найдена"}, status=status.HTTP_404_NOT_FOUND
            )

        year = request.data.get("year")
        month = request.data.get("month")
        content = table.content if isinstance(table.content, dict) else {}
        filename_year = filename_month = None
        if year and month:
            try:
                year_i = int(year)
                month_i = int(month)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "year и month должны быть числами"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            archive = SectionTableMonthlyArchive.objects.filter(
                table=table, year=year_i, month=month_i
            ).first()
            if not archive:
                return Response(
                    {"detail": "Архив за указанный месяц не найден"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            content = archive.content if isinstance(archive.content, dict) else {}
            filename_year, filename_month = year_i, month_i

        try:
            docx = generate_monitoring_report_docx(
                table_title=table.title,
                content=content,
                sheet_name=sheet_name,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        resp = HttpResponse(
            docx,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        filename = report_filename(sheet_name, filename_year, filename_month)
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp


class BotHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not _bot_secret_ok(request):
            return Response({"ok": False}, status=status.HTTP_403_FORBIDDEN)
        return Response({"ok": True, "bot_api": "nextcloud-db-sync"})
