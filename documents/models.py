# documents/models.py
from django.db import models
from django.conf import settings


class Document(models.Model):
    """
    Документ (Таблица Luckysheet или Текст)
    """
    DOC_TYPE_CHOICES = [
        ('spreadsheet', '📊 Таблица'),
        ('text', '📝 Текст'),
    ]

    title = models.CharField(max_length=255, verbose_name='Название')
    doc_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        default='spreadsheet',
        verbose_name='Тип документа'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Владелец'
    )
    content = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Содержимое (Luckysheet data)'
    )
    is_editable = models.BooleanField(
        default=True,
        verbose_name='Можно редактировать'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['owner', '-updated_at']),
            models.Index(fields=['doc_type', '-updated_at']),
        ]

    def __str__(self):
        return f'{self.get_doc_type_display()} - {self.title}'

    @property
    def owner_username(self):
        return self.owner.username
