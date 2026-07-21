"""Сохранение и удаление скринов-доказательств замечаний."""

from __future__ import annotations

import io
import logging
import os
from datetime import date
from typing import Optional

from django.core.files.base import ContentFile
from django.db import transaction

from bot_api.models import RemarkEvidence
from sections.models import SectionTable

logger = logging.getLogger(__name__)

ALLOWED_EVIDENCE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/x-ms-bmp",
    "image/gif",
    "image/tiff",
}
ALLOWED_EVIDENCE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024


def normalize_evidence_to_jpeg(raw: bytes, *, quality: int = 88) -> Optional[bytes]:
    """Любой растровый скрин → JPEG для хранения и Word (BMP/PNG/WebP и т.д.)."""
    if not raw:
        return None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as img:
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=quality, optimize=True)
            return out.getvalue()
    except Exception:
        logger.debug("Evidence normalize to JPEG failed", exc_info=True)
        return None


def evidence_bytes_for_docx(raw: bytes) -> Optional[bytes]:
    """Байты, пригодные для python-docx add_picture."""
    if not raw:
        return None
    converted = normalize_evidence_to_jpeg(raw)
    if converted:
        return converted
    # Уже JPEG/PNG — пробуем как есть
    if raw[:3] == b"\xff\xd8\xff" or raw[:8] == b"\x89PNG\r\n\x1a\n":
        return raw
    return None


def normalize_fio(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def evidence_filename(original_name: str, content_type: str = "") -> str:
    ext = os.path.splitext(original_name or "")[1].lower()
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        ct = (content_type or "").lower()
        if "png" in ct:
            ext = ".png"
        elif "webp" in ct:
            ext = ".webp"
        else:
            ext = ".jpg"
    return f"evidence{ext}"


def validate_evidence_upload(
    *,
    raw: bytes,
    filename: str = "",
    content_type: str = "",
) -> Optional[str]:
    if not raw:
        return "Пустой файл доказательства"
    if len(raw) > MAX_EVIDENCE_BYTES:
        return "Файл доказательства больше 10 МБ"
    ext = os.path.splitext(filename or "")[1].lower()
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct and ct not in ALLOWED_EVIDENCE_CONTENT_TYPES and ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        return "Допустимы только изображения (jpg/png/webp/bmp и др.)"
    if not ct and ext and ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        return "Допустимы только изображения (jpg/png/webp/bmp и др.)"
    return None


def prepare_evidence_for_storage(
    *,
    raw: bytes,
    filename: str = "",
    content_type: str = "",
) -> tuple[bytes, str, str]:
    """Проверка размера + конвертация в JPEG для единообразного хранения."""
    if not raw:
        raise ValueError("Пустой файл доказательства")
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise ValueError("Файл доказательства больше 10 МБ")
    jpeg = normalize_evidence_to_jpeg(raw)
    if jpeg:
        return jpeg, "evidence.jpg", "image/jpeg"
    err = validate_evidence_upload(raw=raw, filename=filename, content_type=content_type)
    if err:
        raise ValueError(err)
    save_name = evidence_filename(filename, content_type)
    ct = (content_type or "image/jpeg").lower().split(";")[0].strip()
    return raw, save_name, ct


@transaction.atomic
def upsert_remark_evidence(
    *,
    table: SectionTable,
    sheet_name: str,
    student_fio: str,
    remark_date: date,
    raw: bytes,
    filename: str = "",
    content_type: str = "",
) -> RemarkEvidence:
    fio = normalize_fio(student_fio)
    sheet = (sheet_name or "").strip()
    raw, save_name, content_type = prepare_evidence_for_storage(
        raw=raw,
        filename=filename,
        content_type=content_type,
    )

    existing = (
        RemarkEvidence.objects.select_for_update()
        .filter(
            table=table,
            sheet_name=sheet,
            student_fio=fio,
            remark_date=remark_date,
        )
        .first()
    )
    if existing:
        existing.delete_file()
        existing.image.save(save_name, ContentFile(raw), save=True)
        return existing

    evidence = RemarkEvidence(
        table=table,
        sheet_name=sheet,
        student_fio=fio,
        remark_date=remark_date,
    )
    evidence.image.save(save_name, ContentFile(raw), save=True)
    return evidence


@transaction.atomic
def delete_remark_evidence(
    *,
    table: SectionTable,
    sheet_name: str,
    student_fio: str,
    remark_date: date,
) -> bool:
    fio = normalize_fio(student_fio)
    sheet = (sheet_name or "").strip()
    obj = (
        RemarkEvidence.objects.select_for_update()
        .filter(
            table=table,
            sheet_name=sheet,
            student_fio=fio,
            remark_date=remark_date,
        )
        .first()
    )
    if not obj:
        return False
    obj.delete_file()
    obj.delete()
    return True


@transaction.atomic
def delete_all_remark_evidence_for_student(
    *,
    table: SectionTable,
    sheet_name: str,
    student_fio: str,
) -> int:
    """Удаляет все скрины замечаний студента на листе. Возвращает число удалённых."""
    fio = normalize_fio(student_fio)
    sheet = (sheet_name or "").strip()
    qs = list(
        RemarkEvidence.objects.select_for_update().filter(
            table=table,
            sheet_name=sheet,
            student_fio=fio,
        )
    )
    for obj in qs:
        obj.delete_file()
        obj.delete()
    return len(qs)


def load_evidence_bytes_map(
    *,
    table: SectionTable,
    sheet_name: str,
) -> dict[tuple[str, date], bytes]:
    """Ключ: (нормализованное ФИО lower, дата) -> bytes изображения."""
    sheet = (sheet_name or "").strip()
    out: dict[tuple[str, date], bytes] = {}
    qs = RemarkEvidence.objects.filter(table=table, sheet_name=sheet)
    for item in qs:
        key = (normalize_fio(item.student_fio).lower(), item.remark_date)
        try:
            with item.image.open("rb") as fh:
                out[key] = fh.read()
        except Exception:
            continue
    return out
