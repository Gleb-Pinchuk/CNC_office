import os
import re

from django.db import models


def remark_evidence_upload_to(instance, filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    sheet = re.sub(r"[^\w\-]+", "_", (instance.sheet_name or "sheet"), flags=re.UNICODE)[:60]
    fio = re.sub(r"[^\w\-]+", "_", (instance.student_fio or "student"), flags=re.UNICODE)[:60]
    return (
        f"remark_evidence/{instance.table_id}/{sheet}/"
        f"{instance.remark_date.isoformat()}_{fio}{ext}"
    )


class RemarkEvidence(models.Model):
    """Скрин-доказательство замечания: table + лист + ФИО + дата."""

    table = models.ForeignKey(
        "sections.SectionTable",
        on_delete=models.CASCADE,
        related_name="remark_evidences",
        verbose_name="Таблица",
    )
    sheet_name = models.CharField(max_length=255, verbose_name="Лист / направление")
    student_fio = models.CharField(max_length=255, verbose_name="ФИО студента")
    remark_date = models.DateField(verbose_name="Дата замечания")
    image = models.FileField(upload_to=remark_evidence_upload_to, verbose_name="Скрин")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Доказательство замечания"
        verbose_name_plural = "Доказательства замечаний"
        constraints = [
            models.UniqueConstraint(
                fields=["table", "sheet_name", "student_fio", "remark_date"],
                name="unique_remark_evidence_per_student_date",
            )
        ]
        indexes = [
            models.Index(fields=["table", "sheet_name", "student_fio"]),
            models.Index(fields=["table", "sheet_name", "remark_date"]),
        ]

    def __str__(self):
        return f"{self.sheet_name}:{self.student_fio}:{self.remark_date}"

    def delete_file(self) -> None:
        if self.image:
            self.image.delete(save=False)


class StudentTrash(models.Model):
    """Отчисленный студент: полная строка листа + TTL 30 дней."""

    table = models.ForeignKey(
        "sections.SectionTable",
        on_delete=models.CASCADE,
        related_name="trashed_students",
        verbose_name="Таблица",
    )
    sheet_name = models.CharField(max_length=255, verbose_name="Лист / направление")
    student_fio = models.CharField(max_length=255, verbose_name="ФИО студента")
    group_name = models.CharField(max_length=255, blank=True, default="", verbose_name="Группа")
    row_data = models.JSONField(default=list, verbose_name="Строка листа")
    original_row_index = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Исходный индекс строки"
    )
    deleted_at = models.DateTimeField(auto_now_add=True, verbose_name="Удалён")
    expires_at = models.DateTimeField(verbose_name="Удалить навсегда после")

    class Meta:
        verbose_name = "Студент в корзине"
        verbose_name_plural = "Корзина студентов"
        ordering = ["-deleted_at"]
        indexes = [
            models.Index(fields=["table", "sheet_name", "expires_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["table", "sheet_name", "student_fio"]),
        ]

    def __str__(self):
        return f"{self.sheet_name}:{self.student_fio} (до {self.expires_at.date()})"
