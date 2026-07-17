"""Сохранение и удаление скринов-доказательств замечаний."""

from __future__ import annotations

import os
from datetime import date
from typing import Optional

from django.core.files.base import ContentFile
from django.db import transaction

from bot_api.models import RemarkEvidence
from sections.models import SectionTable

ALLOWED_EVIDENCE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
ALLOWED_EVIDENCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024


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
        return "Допустимы только jpg/png/webp"
    if not ct and ext and ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        return "Допустимы только jpg/png/webp"
    return None


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
    err = validate_evidence_upload(raw=raw, filename=filename, content_type=content_type)
    if err:
        raise ValueError(err)

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
    save_name = evidence_filename(filename, content_type)
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
