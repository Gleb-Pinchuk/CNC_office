from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from django.contrib.auth import get_user_model
from django.db import transaction

from bot_api.evidence import upsert_remark_evidence
from bot_api.sheet_utils import get_workbook_sheets, set_cell_value
from bot_api.student_sheet import search_students
from bot_api.week_column import pick_week_col_by_date
from sections.models import SectionTable

from .classifier import LightweightClassifier, MatchResult
from .config import load_moderation_config
from .rules_store import load_rules
from .social_scan import SocialEntry, fetch_social_entries

logger = logging.getLogger(__name__)


@dataclass
class ScanStats:
    checked_students: int = 0
    flagged_students: int = 0
    updated_cells: int = 0
    evidence_saved: int = 0


def _clean_token(token: str) -> str:
    t = (token or "").strip().strip("()[]{}<>\"'`")
    t = t.rstrip(".,:;!?")
    t = re.sub(
        r"^(tg|тг|telegram|телеграм|vk|вк|tiktok|тикток)\s*[:\-]\s*",
        "",
        t,
        flags=re.IGNORECASE,
    )
    return t.strip()


def _guess_platform(token: str, raw_cell: str, default_platform: str) -> str:
    t = token.lower()
    cell = raw_cell.lower()
    if "tiktok" in t or "тикток" in t or "tiktok" in cell:
        return "tiktok"
    if "vk.com" in t or t.startswith("id") or t.startswith(("club", "public")):
        return "vk"
    if "t.me" in t or "telegram" in t or "телеграм" in t:
        return "tg"
    if t.startswith("@"):
        if "vk" in cell or "вк" in cell:
            return "vk"
        if "tiktok" in cell or "тикток" in cell:
            return "tiktok"
        return default_platform
    return default_platform


def _normalize_url(token: str, platform: str) -> str:
    t = token.strip()
    if not t:
        return ""
    if t.startswith(("http://", "https://")):
        return t
    if "vk.com/" in t or "t.me/" in t or "tiktok.com/" in t:
        return f"https://{t}"
    if t.startswith("@"):
        nick = t[1:]
        if platform == "vk":
            return f"https://vk.com/{nick}"
        if platform == "tiktok":
            return f"https://www.tiktok.com/@{nick}"
        return f"https://t.me/{nick}"
    if platform == "vk":
        return f"https://vk.com/{t}"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{t.lstrip('@')}"
    return f"https://t.me/{t}"


def _platform_from_header(header_value: str) -> str:
    hv = (header_value or "").strip().lower()
    if "tiktok" in hv or "тикток" in hv or "тик ток" in hv:
        return "tiktok"
    if "vk" in hv or "вк" in hv or "вконтакте" in hv:
        return "vk"
    if "tg" in hv or "тг" in hv or "telegram" in hv or "телеграм" in hv:
        return "tg"
    return "tg"


def _extract_social_links(row: list, header_row: Optional[list], social_cols: list[int]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    preferred = ["tg", "vk", "tiktok"]
    for pos, idx in enumerate(social_cols):
        if idx < 0 or idx >= len(row):
            continue
        raw = "" if row[idx] is None else str(row[idx]).strip()
        if not raw:
            continue
        header_hint = ""
        if isinstance(header_row, list) and idx < len(header_row):
            header_hint = str(header_row[idx] or "")
        default_platform = _platform_from_header(header_hint) or preferred[min(pos, 2)]
        parts = [p for p in re.split(r"[\s,;\n]+", raw) if p and p.strip()] or [raw]
        for part in parts:
            cleaned = _clean_token(part)
            if not cleaned:
                continue
            platform = _guess_platform(cleaned, raw, default_platform)
            url = _normalize_url(cleaned, platform)
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(url)
    return out


def _platform_from_url(url: str) -> str:
    u = (url or "").lower()
    if "t.me/" in u or "telegram." in u:
        return "tg"
    if "tiktok.com/" in u:
        return "tiktok"
    if "vk.com/" in u:
        return "vk"
    return ""


def _find_table(owner, section_type: str, title_fragment: str) -> Optional[SectionTable]:
    qs = SectionTable.objects.filter(owner=owner, section_type=section_type)
    if title_fragment:
        qs = qs.filter(title__icontains=title_fragment)
    return qs.order_by("-updated_at").first()


def _build_remark(match: MatchResult, link: str, scan_date: date) -> str:
    # В таблицу пишем краткий итог, как просил заказчик.
    return (match.remark_text or "выявлен запрещенный контент").strip()


def _guess_image_meta(url: str, content_type: str) -> tuple[str, str]:
    ct = (content_type or "").lower().split(";")[0].strip()
    path = urlparse(url or "").path.lower()
    if "png" in ct or path.endswith(".png"):
        return "evidence.png", "image/png"
    if "webp" in ct or path.endswith(".webp"):
        return "evidence.webp", "image/webp"
    return "evidence.jpg", "image/jpeg"


def download_evidence_bytes(
    url: str,
    *,
    timeout_sec: int = 10,
    proxy_url: str = "",
) -> Optional[tuple[bytes, str, str]]:
    """Скачать превью поста для RemarkEvidence. (raw, filename, content_type) или None."""
    if not (url or "").strip():
        return None
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    try:
        resp = requests.get(url, timeout=timeout_sec, proxies=proxies)
        resp.raise_for_status()
        raw = resp.content or b""
        if not raw:
            return None
        filename, content_type = _guess_image_meta(url, resp.headers.get("Content-Type", ""))
        return raw, filename, content_type
    except Exception:
        logger.warning("Не удалось скачать evidence thumbnail: %s", url[:200], exc_info=True)
        return None


def _save_hit_evidence(
    *,
    table: SectionTable,
    sheet_name: str,
    student_fio: str,
    remark_date: date,
    entry: SocialEntry,
    timeout_sec: int,
    proxy_url: str,
) -> bool:
    downloaded = download_evidence_bytes(
        entry.thumbnail_url,
        timeout_sec=timeout_sec,
        proxy_url=proxy_url,
    )
    if not downloaded:
        logger.info(
            "Evidence skip (no thumbnail) fio=%s sheet=%s post=%s",
            student_fio,
            sheet_name,
            (entry.post_url or "")[:120],
        )
        return False
    raw, filename, content_type = downloaded
    try:
        upsert_remark_evidence(
            table=table,
            sheet_name=sheet_name,
            student_fio=student_fio,
            remark_date=remark_date,
            raw=raw,
            filename=filename,
            content_type=content_type,
        )
        return True
    except Exception:
        logger.exception(
            "Evidence upsert failed fio=%s sheet=%s",
            student_fio,
            sheet_name,
        )
        return False


def run_social_moderation_scan(
    *,
    scan_date: Optional[date] = None,
    dry_run: bool = True,
    max_students: Optional[int] = None,
    save_evidence: bool = True,
) -> ScanStats:
    cfg = load_moderation_config()
    if not cfg.table_owner_username:
        raise RuntimeError("Не задан CNC_BOT_TABLE_OWNER_USERNAME")

    rules = load_rules(cfg.rules_path)
    classifier = LightweightClassifier(
        rules=rules,
        block_hash_distance=cfg.block_hash_distance,
        allow_hash_distance=cfg.allow_hash_distance,
        timeout_sec=cfg.request_timeout_sec,
    )
    User = get_user_model()
    owner = User.objects.filter(username=cfg.table_owner_username).first()
    if not owner:
        raise RuntimeError(f"Не найден владелец таблиц: {cfg.table_owner_username}")

    table = _find_table(owner, cfg.section_type, cfg.title_fragment)
    if not table:
        raise RuntimeError("Таблица для модерации не найдена")

    content = table.content if isinstance(table.content, dict) else {}
    sheets, _ = get_workbook_sheets(content)
    stats = ScanStats()
    today = scan_date or datetime.now().date()
    stop = False

    if not sheets:
        logger.warning("Social moderation: no sheets found in table content")
        return stats

    for sheet in sheets:
        sheet_name = str(sheet.get("name") or "")
        data = sheet.get("data") or []
        if not data:
            continue
        header_row = data[0] if isinstance(data[0], list) else None
        week_col = pick_week_col_by_date(data, today) or cfg.remark_col
        students = search_students(
            data,
            fio_col=cfg.fio_col,
            group_col=cfg.group_col,
            status_col=cfg.status_col,
            skip_dismissed=True,
        )
        if not students:
            logger.info("Social moderation: no students in sheet '%s'", sheet_name)
            continue
        for student in students:
            if max_students and stats.checked_students >= max_students:
                stop = True
                break
            row_idx = int(student["row_index"])
            row = (
                data[row_idx]
                if row_idx < len(data) and isinstance(data[row_idx], list)
                else []
            )
            links = _extract_social_links(row, header_row, cfg.social_cols)[
                : cfg.max_links_per_student
            ]
            stats.checked_students += 1
            violation: Optional[tuple[str, MatchResult, SocialEntry]] = None
            for link in links:
                platform = _platform_from_url(link)
                if cfg.skip_tg and platform == "tg":
                    continue
                if cfg.skip_tiktok and platform == "tiktok":
                    continue
                entries = fetch_social_entries(
                    link,
                    cfg.max_entries_per_link,
                    cfg.ytdlp_timeout_sec,
                    proxy_url=cfg.proxy_url,
                )
                for entry in entries:
                    result = classifier.classify(entry)
                    if result.is_violation:
                        violation = (link, result, entry)
                        break
                if violation:
                    break
            if not violation:
                continue

            stats.flagged_students += 1
            link, match, entry = violation
            remark = _build_remark(match, link, today)
            if dry_run:
                logger.info(
                    "[dry-run] %s / %s -> %s (thumb=%s)",
                    sheet_name,
                    student.get("fio", ""),
                    remark,
                    bool(entry.thumbnail_url),
                )
                continue

            set_cell_value(content, sheet_name, row_idx, week_col, remark)
            stats.updated_cells += 1
            if save_evidence:
                if _save_hit_evidence(
                    table=table,
                    sheet_name=sheet_name,
                    student_fio=str(student.get("fio") or ""),
                    remark_date=today,
                    entry=entry,
                    timeout_sec=cfg.request_timeout_sec,
                    proxy_url=cfg.proxy_url,
                ):
                    stats.evidence_saved += 1
        if stop:
            break

    if not dry_run and stats.updated_cells:
        with transaction.atomic():
            SectionTable.objects.filter(pk=table.pk).update(
                content=content,
                needs_nextcloud_push=True,
            )

    logger.info(
        "Social moderation finished: checked=%s flagged=%s cells=%s evidence=%s dry_run=%s",
        stats.checked_students,
        stats.flagged_students,
        stats.updated_cells,
        stats.evidence_saved,
        dry_run,
    )
    return stats
